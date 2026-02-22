"""
Headless runner for team sync.

Orchestrates the full headless indexing workflow:
1. Clone/checkout the repository
2. Optionally download existing index from S3 (for incremental builds)
3. Run the 10-stage enrichment pipeline
4. Upload the resulting index artifacts to S3

This module is called by the `codrag sync-headless` CLI command.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from codrag.services.s3_storage import S3Config, S3StorageProvider, SyncManifest

logger = logging.getLogger(__name__)


@dataclass
class HeadlessConfig:
    """Configuration for a headless sync run."""
    # Repository
    repo_url: str = ""
    repo_path: str = ""  # Pre-cloned path (e.g., from GitHub Actions checkout)
    branch: str = "main"

    # LLM
    model_provider: str = "local"  # local | openai | anthropic | google
    model_name: str = "qwen3:4b"
    api_key: str = ""

    # Embedder
    embedder: str = "native"  # native | ollama

    # Build
    full_rebuild: bool = False

    # S3
    s3: Optional[S3Config] = None


class HeadlessRunner:
    """Runs the full headless indexing pipeline."""

    def __init__(self, config: HeadlessConfig):
        self.config = config
        self._work_dir: Optional[Path] = None
        self._cleanup_work_dir = False

    def run(self) -> SyncManifest:
        """Execute the full headless sync workflow. Returns the upload manifest."""
        try:
            # 1. Resolve the repository path
            repo_path = self._resolve_repo()
            logger.info("Repository path: %s (branch: %s)", repo_path, self.config.branch)

            # 2. Set up the index directory
            index_dir = repo_path / ".codrag" / "index"
            index_dir.mkdir(parents=True, exist_ok=True)

            # 3. Download existing index for incremental rebuild
            s3_provider = None
            if self.config.s3:
                s3_provider = S3StorageProvider(self.config.s3)

                if not self.config.full_rebuild:
                    self._download_existing_index(s3_provider, index_dir)

            # 4. Run the pipeline
            self._run_pipeline(repo_path, index_dir)

            # 5. Upload results
            if s3_provider:
                commit_sha = self._get_commit_sha(repo_path)
                manifest = s3_provider.upload_index(
                    index_dir=index_dir,
                    branch=self.config.branch,
                    commit_sha=commit_sha,
                )
                logger.info(
                    "Sync complete: branch=%s commit=%s artifacts=%d",
                    manifest.branch, manifest.commit_sha[:8], manifest.artifact_count,
                )
                return manifest
            else:
                logger.info("No S3 config — index built locally at %s", index_dir)
                return SyncManifest()

        finally:
            if self._cleanup_work_dir and self._work_dir and self._work_dir.exists():
                logger.info("Cleaning up work directory: %s", self._work_dir)
                shutil.rmtree(self._work_dir, ignore_errors=True)

    def _resolve_repo(self) -> Path:
        """Get the repository path — either pre-cloned or freshly cloned."""
        if self.config.repo_path:
            repo = Path(self.config.repo_path).resolve()
            if not repo.exists():
                raise FileNotFoundError(f"Repository path does not exist: {repo}")
            return repo

        if self.config.repo_url:
            return self._clone_repo()

        raise ValueError("Either --repo-url or --repo-path must be provided")

    def _clone_repo(self) -> Path:
        """Clone the repository to a temp directory."""
        self._work_dir = Path(tempfile.mkdtemp(prefix="codrag-headless-"))
        self._cleanup_work_dir = True
        repo_dir = self._work_dir / "repo"

        url = self.config.repo_url

        # Inject token for HTTPS clones
        git_token = os.environ.get("GIT_TOKEN", "")
        if git_token and url.startswith("https://"):
            # https://github.com/org/repo → https://x-access-token:TOKEN@github.com/org/repo
            url = url.replace("https://", f"https://x-access-token:{git_token}@")

        cmd = [
            "git", "clone",
            "--depth", "1",
            "--branch", self.config.branch,
            "--single-branch",
            url,
            str(repo_dir),
        ]

        logger.info("Cloning repository: %s (branch: %s)", self.config.repo_url, self.config.branch)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")

        return repo_dir

    def _download_existing_index(self, s3: S3StorageProvider, index_dir: Path) -> None:
        """Download existing index from S3 for incremental builds."""
        manifest = s3.get_remote_manifest()
        if manifest is None:
            logger.info("No existing remote index found — will do a full build")
            return

        logger.info(
            "Found remote index: branch=%s commit=%s age=%.0f min",
            manifest.branch,
            manifest.commit_sha[:8] if manifest.commit_sha else "unknown",
            ((__import__("time").time() - manifest.timestamp) / 60) if manifest.timestamp else 0,
        )

        try:
            s3.download_index(index_dir)
            logger.info("Downloaded existing index for incremental rebuild")
        except Exception as e:
            logger.warning("Failed to download existing index — falling back to full build: %s", e)

    def _run_pipeline(self, repo_path: Path, index_dir: Path) -> None:
        """Run the CoDRAG indexing pipeline."""
        # TODO: Wire into the actual pipeline orchestrator.
        # For now, this is a placeholder that calls the build manager directly.
        #
        # The actual implementation will:
        # 1. Create a temporary project pointing at repo_path with index at index_dir
        # 2. Configure the LLM based on self.config.model_provider / model_name
        # 3. Call build_manager.start_project_build() or pipeline_orchestrator.run()
        # 4. Wait for completion
        #
        # This depends on refactoring the pipeline to run without a running daemon.
        logger.info("Running 10-stage enrichment pipeline on %s", repo_path)
        logger.info("  Model: %s/%s", self.config.model_provider, self.config.model_name)
        logger.info("  Embedder: %s", self.config.embedder)
        logger.info("  Index dir: %s", index_dir)

        raise NotImplementedError(
            "Pipeline wiring is not yet implemented. "
            "This is tracked as P06-S05 in the Phase 06 TODO."
        )

    def _get_commit_sha(self, repo_path: Path) -> str:
        """Get the current HEAD commit SHA."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10,
                cwd=repo_path,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""
