"""
S3-compatible storage provider for headless team sync.

Handles uploading/downloading index artifacts to/from S3-compatible
buckets (AWS S3, Cloudflare R2, MinIO, Backblaze B2).

All credentials are read from environment variables or passed explicitly.
"""

import json
import logging
import os
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Index artifacts that get zipped and uploaded.
# Must stay in sync with _PRESERVE_FILES in codrag.core.index.
INDEX_ARTIFACTS = [
    # Code index (semantic search)
    "documents.json",
    "embeddings.npy",
    # Trace graph (structural)
    "trace_manifest.json",
    "trace_nodes.jsonl",
    "trace_edges.jsonl",
    # Fast Catalogue (augmentation)
    "trace_augmented.jsonl",
    "trace_augment_manifest.json",
    # Relationship Validation
    "trace_inferred_edges.jsonl",
    # Epistemic Enrichment
    "trace_epistemic.jsonl",
    "trace_epistemic_manifest.json",
    # Cluster Synthesis
    "trace_modules.jsonl",
    # Codebase Atlas
    "atlas.json",
    "atlas_segments_manifest.json",
    # Atlas Routing
    "atlas_routing.json",
    "atlas_routing_embeddings.npy",
    # Knowledge Embedding
    "knowledge_documents.json",
    "knowledge_embeddings.npy",
    "knowledge_manifest.json",
]


@dataclass
class SyncManifest:
    """Version manifest stored alongside the index zip in S3."""
    version: int = 1
    timestamp: float = 0.0
    branch: str = "main"
    commit_sha: str = ""
    content_hash: str = ""
    artifact_count: int = 0
    total_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "content_hash": self.content_hash,
            "artifact_count": self.artifact_count,
            "total_bytes": self.total_bytes,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SyncManifest":
        return cls(
            version=d.get("version", 1),
            timestamp=d.get("timestamp", 0.0),
            branch=d.get("branch", "main"),
            commit_sha=d.get("commit_sha", ""),
            content_hash=d.get("content_hash", ""),
            artifact_count=d.get("artifact_count", 0),
            total_bytes=d.get("total_bytes", 0),
        )


@dataclass
class S3Config:
    """S3-compatible storage configuration."""
    endpoint: str = ""
    bucket: str = ""
    prefix: str = ""
    access_key: str = ""
    secret_key: str = ""
    region: str = "auto"

    @classmethod
    def from_env(cls) -> "S3Config":
        """Load configuration from environment variables."""
        return cls(
            endpoint=os.environ.get("CODRAG_S3_ENDPOINT", ""),
            bucket=os.environ.get("CODRAG_S3_BUCKET", ""),
            prefix=os.environ.get("CODRAG_S3_PREFIX", ""),
            access_key=os.environ.get("CODRAG_S3_ACCESS_KEY", ""),
            secret_key=os.environ.get("CODRAG_S3_SECRET_KEY", ""),
            region=os.environ.get("CODRAG_S3_REGION", "auto"),
        )

    def validate(self) -> List[str]:
        """Return list of missing required fields."""
        errors = []
        if not self.bucket:
            errors.append("S3 bucket is required (CODRAG_S3_BUCKET)")
        if not self.access_key:
            errors.append("S3 access key is required (CODRAG_S3_ACCESS_KEY)")
        if not self.secret_key:
            errors.append("S3 secret key is required (CODRAG_S3_SECRET_KEY)")
        return errors


class S3StorageProvider:
    """Upload/download index artifacts to S3-compatible storage."""

    def __init__(self, config: S3Config):
        self.config = config
        self._client = None

    def _get_client(self):
        """Lazy-init the boto3 S3 client."""
        if self._client is not None:
            return self._client

        try:
            import boto3
            from botocore.config import Config as BotoConfig
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 sync. Install with: pip install boto3"
            )

        kwargs: Dict[str, Any] = {
            "aws_access_key_id": self.config.access_key,
            "aws_secret_access_key": self.config.secret_key,
            "config": BotoConfig(
                retries={"max_attempts": 3, "mode": "adaptive"},
                connect_timeout=10,
                read_timeout=60,
            ),
        }
        if self.config.endpoint:
            kwargs["endpoint_url"] = self.config.endpoint
        if self.config.region and self.config.region != "auto":
            kwargs["region_name"] = self.config.region

        self._client = boto3.client("s3", **kwargs)
        return self._client

    def _s3_key(self, filename: str) -> str:
        """Build the full S3 key from prefix + filename."""
        if self.config.prefix:
            prefix = self.config.prefix.rstrip('/')
            if '..' in prefix or prefix.startswith('/'):
                raise ValueError(f"S3 prefix contains unsafe path segments: {prefix}")
            return f"{prefix}/{filename}"
        return filename

    # ── Upload ────────────────────────────────────────────────

    def upload_index(
        self,
        index_dir: Path,
        branch: str = "main",
        commit_sha: str = "",
    ) -> SyncManifest:
        """Zip index artifacts and upload to S3 with an atomic swap."""
        client = self._get_client()
        bucket = self.config.bucket

        # Collect artifacts that exist
        artifacts = []
        for name in INDEX_ARTIFACTS:
            p = index_dir / name
            if p.exists():
                artifacts.append(p)

        if not artifacts:
            raise ValueError(f"No index artifacts found in {index_dir}")

        # Create zip in a temp file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            total_bytes = 0
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for artifact in artifacts:
                    zf.write(artifact, artifact.name)
                    total_bytes += artifact.stat().st_size

            # Compute content hash of the zip
            h = sha256()
            with open(tmp_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            content_hash = h.hexdigest()[:16]

            # Upload zip to a temp key first (atomic swap)
            zip_key = self._s3_key("index.zip")
            tmp_key = self._s3_key("index.zip.tmp")

            logger.info("Uploading index zip to s3://%s/%s (%d bytes)", bucket, zip_key, tmp_path.stat().st_size)
            client.upload_file(str(tmp_path), bucket, tmp_key)

            # Copy to final key, then delete temp
            client.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": tmp_key},
                Key=zip_key,
            )
            client.delete_object(Bucket=bucket, Key=tmp_key)

            # Build and upload manifest
            manifest = SyncManifest(
                version=1,
                timestamp=time.time(),
                branch=branch,
                commit_sha=commit_sha,
                content_hash=content_hash,
                artifact_count=len(artifacts),
                total_bytes=total_bytes,
            )
            manifest_key = self._s3_key("manifest.json")
            client.put_object(
                Bucket=bucket,
                Key=manifest_key,
                Body=json.dumps(manifest.to_dict(), indent=2).encode(),
                ContentType="application/json",
            )

            logger.info(
                "Upload complete: %d artifacts, %d bytes, hash=%s",
                len(artifacts), total_bytes, content_hash,
            )
            return manifest

        finally:
            tmp_path.unlink(missing_ok=True)

    # ── Download ──────────────────────────────────────────────

    def get_remote_manifest(self) -> Optional[SyncManifest]:
        """Fetch the remote manifest.json. Returns None if not found."""
        client = self._get_client()
        manifest_key = self._s3_key("manifest.json")

        try:
            resp = client.get_object(Bucket=self.config.bucket, Key=manifest_key)
            data = json.loads(resp["Body"].read())
            return SyncManifest.from_dict(data)
        except client.exceptions.NoSuchKey:
            return None
        except Exception as e:
            logger.warning("Failed to fetch remote manifest: %s", e)
            return None

    def download_index(self, target_dir: Path) -> SyncManifest:
        """Download and extract the index zip from S3."""
        client = self._get_client()
        bucket = self.config.bucket
        zip_key = self._s3_key("index.zip")

        # Download to temp file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            logger.info("Downloading index zip from s3://%s/%s", bucket, zip_key)
            client.download_file(bucket, zip_key, str(tmp_path))

            # Extract to a temp directory, then atomic rename
            tmp_target = target_dir.parent / f"{target_dir.name}.tmp"
            if tmp_target.exists():
                shutil.rmtree(tmp_target)
            tmp_target.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(tmp_path, "r") as zf:
                # Zip bomb protection: reject if uncompressed size > 10 GB
                MAX_UNCOMPRESSED_BYTES = 10 * 1024 * 1024 * 1024
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                    raise ValueError(
                        f"Index zip uncompressed size ({total_uncompressed:,} bytes) "
                        f"exceeds safety limit ({MAX_UNCOMPRESSED_BYTES:,} bytes). "
                        f"Possible zip bomb — aborting extraction."
                    )

                # Zip-slip protection: reject entries that escape target dir
                for member in zf.namelist():
                    resolved = (tmp_target / member).resolve()
                    if not str(resolved).startswith(str(tmp_target.resolve())):
                        raise ValueError(f"Zip-slip detected: {member} escapes target directory")
                zf.extractall(tmp_target)

            # Atomic swap: remove old, rename new
            if target_dir.exists():
                shutil.rmtree(target_dir)
            tmp_target.rename(target_dir)

            logger.info("Index extracted to %s", target_dir)

            # Verify content hash of downloaded zip against manifest
            manifest = self.get_remote_manifest()
            if manifest and manifest.content_hash:
                h = sha256()
                with open(tmp_path, "rb") as fh:
                    for chunk in iter(lambda: fh.read(8192), b""):
                        h.update(chunk)
                actual_hash = h.hexdigest()[:16]
                if actual_hash != manifest.content_hash:
                    logger.warning(
                        "SECURITY: Index zip content hash mismatch! "
                        "Expected %s, got %s. The index may have been tampered with.",
                        manifest.content_hash, actual_hash,
                    )

            # Read and return the manifest
            if manifest:
                # Save a local copy
                manifest_path = target_dir / "manifest.json"
                manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2))
            return manifest or SyncManifest()

        finally:
            tmp_path.unlink(missing_ok=True)
