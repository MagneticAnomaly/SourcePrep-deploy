"""
Client-side remote sync service for team mode.

When a project has a `.sourceprep/team_config.json` with sync enabled,
this service periodically checks the team's S3 bucket for a newer
index and downloads it to `.sourceprep/index/remote/`.

The daemon calls `RemoteSyncService.check_and_sync()` on startup,
on manual "Sync Now" button press, and on a configurable polling
interval (default: every 30 minutes).

This module does NOT import from prep.server — it is self-contained
and can be used by both the daemon and the headless CLI.
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from prep.services.s3_storage import S3Config, S3StorageProvider, SyncManifest

logger = logging.getLogger(__name__)

# ── Team config schema ────────────────────────────────────────
# ARCH-2: Import the canonical config filename from core/team_config
# to avoid two modules defining the same constant independently.
try:
    from prep.core.team_config import TEAM_CONFIG_REL_PATH as _TC_REL
    TEAM_CONFIG_FILENAME = _TC_REL.name  # "team_config.json"
except ImportError:
    TEAM_CONFIG_FILENAME = "team_config.json"

SECRETS_FILENAME = ".secrets"


@dataclass
class TeamSyncConfig:
    """Parsed from .sourceprep/team_config.json (committed to repo, secret-free)."""
    enabled: bool = False
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_prefix: str = ""
    poll_interval_minutes: int = 30
    # Privacy capability (P06): fail-closed strip of raw source `content`
    # from documents.json at the S3 upload boundary. Defaults False —
    # BYO/Enterprise buckets (customer's own S3/R2/MinIO) leave content
    # intact unless a future SourcePrep-hosted tier opts in.
    strip_source_content: bool = False

    MIN_POLL_INTERVAL_MINUTES = 5

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TeamSyncConfig":
        sync = d.get("sync", {})
        raw_interval = int(sync.get("poll_interval_minutes", 30))
        safe_interval = max(raw_interval, cls.MIN_POLL_INTERVAL_MINUTES)
        if raw_interval < cls.MIN_POLL_INTERVAL_MINUTES:
            logger.warning(
                "poll_interval_minutes=%d is below minimum (%d). Using %d.",
                raw_interval, cls.MIN_POLL_INTERVAL_MINUTES, safe_interval,
            )
        return cls(
            enabled=bool(sync.get("enabled", False)),
            s3_endpoint=str(sync.get("s3_endpoint", "")),
            s3_bucket=str(sync.get("s3_bucket", "")),
            s3_prefix=str(sync.get("s3_prefix", "")),
            poll_interval_minutes=safe_interval,
            strip_source_content=bool(sync.get("strip_source_content", False)),
        )


def _validate_s3_endpoint(url: str) -> tuple:
    """EA-B1: SSRF prevention for S3 endpoints.

    Returns (safe, reason). Blocks private IPs, metadata endpoints, non-HTTPS.
    """
    import ipaddress
    import socket
    import urllib.parse

    if not url:
        return True, ""

    try:
        parsed = urllib.parse.urlparse(url)

        # Require HTTPS for S3 endpoints (unless localhost for dev)
        hostname = parsed.hostname or ""
        if parsed.scheme != "https" and hostname not in ("localhost", "127.0.0.1"):
            return False, f"S3 endpoint must use HTTPS (got {parsed.scheme}://)"

        # Block cloud metadata endpoints
        if hostname in ("169.254.169.254", "metadata.google.internal"):
            return False, "S3 endpoint targets a cloud metadata service"

        # Resolve and check for private IPs
        try:
            resolved = socket.getaddrinfo(hostname, parsed.port, proto=socket.IPPROTO_TCP)
            for _, _, _, _, sockaddr in resolved:
                ip = ipaddress.ip_address(sockaddr[0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    # Allow localhost for development
                    if ip.is_loopback:
                        continue
                    return False, f"S3 endpoint resolves to private IP: {ip}"
        except (socket.gaierror, ValueError, OSError):
            pass  # DNS failure — allow (may not resolve locally)

        return True, ""
    except Exception as e:
        return False, f"Invalid S3 endpoint URL: {e}"


def _check_secrets_permissions(secrets_path: Path) -> None:
    """EA-B3: Check that .sourceprep/.secrets file has restrictive permissions.

    Warns if the file is world-readable or group-readable (mode should be 0o600).
    """
    if not secrets_path.exists():
        return

    try:
        mode = secrets_path.stat().st_mode & 0o777
        if mode & 0o077:  # group or world bits set
            logger.warning(
                "SECURITY: Secrets file %s has permissive mode %o. "
                "Should be 0600 (owner read/write only). "
                "Fix with: chmod 600 %s",
                secrets_path, mode, secrets_path,
            )
    except OSError as e:
        logger.warning("Could not check permissions on %s: %s", secrets_path, e)


@dataclass
class SyncStatus:
    """Current sync state for a project."""
    enabled: bool = False
    last_sync_at: Optional[float] = None
    last_sync_commit: str = ""
    remote_version: Optional[int] = None
    remote_timestamp: Optional[float] = None
    is_syncing: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "last_sync_at": self.last_sync_at,
            "last_sync_commit": self.last_sync_commit,
            "remote_version": self.remote_version,
            "remote_timestamp": self.remote_timestamp,
            "is_syncing": self.is_syncing,
            "behind_minutes": self._behind_minutes(),
            "error": self.error,
        }

    def _behind_minutes(self) -> Optional[float]:
        if self.remote_timestamp and self.last_sync_at:
            if self.remote_timestamp > self.last_sync_at:
                return (self.remote_timestamp - self.last_sync_at) / 60
        return None


# ── Credential resolution ─────────────────────────────────────

def _resolve_s3_credentials(prep_dir: Path) -> Dict[str, str]:
    """Resolve S3 credentials from env vars or .sourceprep/.secrets file.

    Priority:
    1. Environment variables (PREP_S3_ACCESS_KEY, PREP_S3_SECRET_KEY)
    2. .sourceprep/.secrets JSON file (gitignored)
    """
    access_key = os.environ.get("PREP_S3_ACCESS_KEY", "")
    secret_key = os.environ.get("PREP_S3_SECRET_KEY", "")

    if access_key and secret_key:
        return {"access_key": access_key, "secret_key": secret_key}

    # Try .sourceprep/.secrets file
    secrets_path = prep_dir / SECRETS_FILENAME
    if secrets_path.exists():
        try:
            with open(secrets_path, "r", encoding="utf-8") as f:
                secrets = json.load(f)
            access_key = secrets.get("s3_access_key", "")
            secret_key = secrets.get("s3_secret_key", "")
            if access_key and secret_key:
                return {"access_key": access_key, "secret_key": secret_key}
        except Exception as e:
            logger.warning("Failed to read .sourceprep/.secrets: %s", e)

    return {"access_key": "", "secret_key": ""}


# ── Secrets leakage detection ─────────────────────────────────

_SECRET_KEY_PATTERNS = {"access_key", "secret_key", "api_key", "password", "token", "secret"}


def _check_for_leaked_secrets(data: Dict[str, Any], filepath: str) -> None:
    """Warn if a config dict contains keys that look like credentials.

    team_config.json is committed to Git — it must never contain secrets.
    Credentials belong in env vars or .sourceprep/.secrets (gitignored).
    """
    found: List[str] = []

    def _scan(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                key_lower = k.lower()
                full_path = f"{path}.{k}" if path else k
                if any(pat in key_lower for pat in _SECRET_KEY_PATTERNS):
                    if isinstance(v, str) and len(v) > 4:
                        found.append(full_path)
                _scan(v, full_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _scan(item, f"{path}[{i}]")

    _scan(data)

    if found:
        logger.warning(
            "SECURITY: %s appears to contain credential-like keys: %s. "
            "This file is typically committed to Git. Move secrets to "
            "environment variables (PREP_S3_ACCESS_KEY) or .sourceprep/.secrets (gitignored).",
            filepath, ", ".join(found),
        )


# ── Remote Sync Service ──────────────────────────────────────

class RemoteSyncService:
    """Manages remote index sync for a single project."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.prep_dir = self.project_root / ".sourceprep"
        self.remote_index_dir = self.prep_dir / "index" / "remote"
        self.local_manifest_path = self.remote_index_dir / "manifest.json"

        self._config: Optional[TeamSyncConfig] = None
        self._s3: Optional[S3StorageProvider] = None
        self._status = SyncStatus()
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ── Config loading ────────────────────────────────────────

    def load_config(self) -> Optional[TeamSyncConfig]:
        """Load team_config.json from .sourceprep/ directory."""
        config_path = self.prep_dir / TEAM_CONFIG_FILENAME
        if not config_path.exists():
            self._config = None
            self._status.enabled = False
            return None

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Security: warn if secrets appear to be embedded in the config file
            _check_for_leaked_secrets(data, str(config_path))

            self._config = TeamSyncConfig.from_dict(data)
            self._status.enabled = self._config.enabled
            return self._config
        except Exception as e:
            logger.warning("Failed to parse team_config.json: %s", e)
            self._config = None
            self._status.enabled = False
            return None

    def _get_s3_provider(self) -> Optional[S3StorageProvider]:
        """Create S3 provider from team config + resolved credentials."""
        if self._s3 is not None:
            return self._s3

        if not self._config or not self._config.enabled:
            return None

        creds = _resolve_s3_credentials(self.prep_dir)
        if not creds["access_key"] or not creds["secret_key"]:
            self._status.error = "S3 credentials not found. Set PREP_S3_ACCESS_KEY/PREP_S3_SECRET_KEY or create .sourceprep/.secrets"
            logger.warning(self._status.error)
            return None

        s3_config = S3Config(
            endpoint=self._config.s3_endpoint,
            bucket=self._config.s3_bucket,
            prefix=self._config.s3_prefix,
            access_key=creds["access_key"],
            secret_key=creds["secret_key"],
            strip_source_content=self._config.strip_source_content,
        )

        errors = s3_config.validate()
        if errors:
            self._status.error = "; ".join(errors)
            return None

        self._s3 = S3StorageProvider(s3_config)
        return self._s3

    # ── Local manifest ────────────────────────────────────────

    def _get_local_manifest(self) -> Optional[SyncManifest]:
        """Read the local copy of the remote manifest."""
        if not self.local_manifest_path.exists():
            return None
        try:
            with open(self.local_manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SyncManifest.from_dict(data)
        except Exception:
            return None

    # ── Core sync logic ───────────────────────────────────────

    def check_and_sync(self) -> bool:
        """Check for a newer remote index and download if available.

        Returns True if a new index was downloaded.
        """
        if not self._config:
            self.load_config()
        if not self._config or not self._config.enabled:
            return False

        s3 = self._get_s3_provider()
        if not s3:
            return False

        self._status.is_syncing = True
        self._status.error = None

        try:
            # Check remote manifest
            remote_manifest = s3.get_remote_manifest()
            if remote_manifest is None:
                logger.info("No remote index found in S3 bucket")
                self._status.is_syncing = False
                return False

            self._status.remote_version = remote_manifest.version
            self._status.remote_timestamp = remote_manifest.timestamp

            # Compare with local
            local_manifest = self._get_local_manifest()
            if local_manifest and local_manifest.content_hash == remote_manifest.content_hash:
                logger.debug("Remote index unchanged (hash=%s)", remote_manifest.content_hash)
                self._status.is_syncing = False
                return False

            # Download the new index
            logger.info(
                "New remote index available: commit=%s, downloading...",
                remote_manifest.commit_sha[:8] if remote_manifest.commit_sha else "unknown",
            )

            self.remote_index_dir.mkdir(parents=True, exist_ok=True)
            s3.download_index(self.remote_index_dir)

            # Prune local deltas that are now covered by the fresh remote index
            self._prune_stale_deltas()

            self._status.last_sync_at = time.time()
            self._status.last_sync_commit = remote_manifest.commit_sha
            self._status.is_syncing = False

            logger.info(
                "Remote index synced: branch=%s commit=%s",
                remote_manifest.branch,
                remote_manifest.commit_sha[:8] if remote_manifest.commit_sha else "unknown",
            )
            return True

        except Exception as e:
            self._status.error = str(e)
            self._status.is_syncing = False
            logger.error("Remote sync failed: %s", e)
            return False

    # ── Polling ───────────────────────────────────────────────

    def start_polling(self) -> None:
        """Start a background thread that polls for updates."""
        if not self._config:
            self.load_config()
        if not self._config or not self._config.enabled:
            return

        if self._poll_thread and self._poll_thread.is_alive():
            return  # Already polling

        self._stop_event.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            name="remote-sync-poll",
            daemon=True,
        )
        self._poll_thread.start()
        logger.info(
            "Remote sync polling started (interval: %d min)",
            self._config.poll_interval_minutes,
        )

    def stop_polling(self) -> None:
        """Stop the background polling thread."""
        self._stop_event.set()
        if self._poll_thread:
            self._poll_thread.join(timeout=5)
            self._poll_thread = None

    def _poll_loop(self) -> None:
        """Background polling loop."""
        # Initial sync on startup
        try:
            self.check_and_sync()
        except Exception as e:
            logger.error("Initial remote sync failed: %s", e)

        interval = (self._config.poll_interval_minutes if self._config else 30) * 60

        while not self._stop_event.wait(timeout=interval):
            try:
                self.check_and_sync()
            except Exception as e:
                logger.error("Remote sync poll failed: %s", e)

    # ── Delta pruning ────────────────────────────────────────

    def _prune_stale_deltas(self) -> None:
        """Remove local deltas that are now covered by the fresh remote index.

        Called automatically after a new remote index is downloaded.
        """
        delta_dir = self.prep_dir / "index" / "local_deltas"
        remote_manifest_path = self.remote_index_dir / "trace_manifest.json"

        if not delta_dir.exists() or not remote_manifest_path.exists():
            return

        try:
            from prep.core.layered_index import prune_stale_deltas
            pruned = prune_stale_deltas(remote_manifest_path, delta_dir)
            if pruned > 0:
                logger.info("Pruned %d stale local delta(s) after remote sync", pruned)
        except Exception as e:
            logger.warning("Delta pruning failed (non-fatal): %s", e)

    # ── Status ────────────────────────────────────────────────

    @property
    def status(self) -> SyncStatus:
        return self._status

    def status_dict(self) -> Dict[str, Any]:
        return self._status.to_dict()
