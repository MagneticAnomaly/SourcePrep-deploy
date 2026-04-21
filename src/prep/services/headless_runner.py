"""
Headless runner for team sync.

Orchestrates the full headless indexing workflow:
1. Clone/checkout the repository
2. Optionally download existing index from S3 (for incremental builds)
3. Run the 11-stage enrichment pipeline
4. Upload the resulting index artifacts to S3

This module is called by the `codrag sync-headless` CLI command.

**Key design decision (P06-S05):**
  The daemon's pipeline uses WorkerFactory → codrag.server singletons.
  The headless runner bypasses all server imports by constructing core
  classes (TraceBuilder, TraceAugmenter, etc.) directly with explicit
  params.  Stages run sequentially in the main thread — no
  BuildOrchestrator thread pool needed.
"""

import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from prep.services.s3_storage import S3Config, S3StorageProvider, SyncManifest

logger = logging.getLogger(__name__)


# ── Provider endpoint defaults ────────────────────────────────

PROVIDER_ENDPOINTS: Dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "google": "https://generativelanguage.googleapis.com",
    "local": "http://127.0.0.1:11434",
}


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

    # Glob filters
    include_globs: List[str] = field(default_factory=list)
    exclude_globs: List[str] = field(default_factory=list)
    max_file_bytes: int = 500_000
    hard_limit_bytes: int = 100_000_000

    # S3
    s3: Optional[S3Config] = None


# ── Stage results ─────────────────────────────────────────────

@dataclass
class StageResult:
    stage: str
    success: bool
    skipped: bool = False
    duration_seconds: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# ── LLM + Embedder factories (server-free) ────────────────────

def headless_create_llm_client(config: HeadlessConfig):
    """Create an LLMClient without importing from prep.server."""
    from prep.core import LLMClient

    provider = config.model_provider
    if provider == "local":
        # Local Ollama — 600s timeout for thinking models (qwen3.5:27b
        # generates 2000-5000+ thinking tokens at ~11 tok/s before content)
        return LLMClient(
            endpoint_url=PROVIDER_ENDPOINTS["local"],
            model=config.model_name,
            provider="ollama",
            timeout=600.0,
        )
    elif provider == "openai":
        return LLMClient(
            endpoint_url=PROVIDER_ENDPOINTS["openai"],
            model=config.model_name,
            provider="openai",
            api_key=config.api_key,
            timeout=120.0,
        )
    elif provider == "anthropic":
        return LLMClient(
            endpoint_url=PROVIDER_ENDPOINTS["anthropic"],
            model=config.model_name,
            provider="anthropic",
            api_key=config.api_key,
            timeout=120.0,
        )
    elif provider == "google":
        return LLMClient(
            endpoint_url=PROVIDER_ENDPOINTS["google"],
            model=config.model_name,
            provider="google",
            api_key=config.api_key,
            timeout=120.0,
        )
    else:
        raise ValueError(f"Unknown model provider: {provider}")


def headless_create_embedder(config: HeadlessConfig):
    """Create an embedder without importing from prep.server."""
    from prep.core import NativeEmbedder, OllamaEmbedder

    if config.embedder == "native":
        native = NativeEmbedder()
        if native.is_available():
            logger.info("Using NativeEmbedder (ONNX, CPU)")
            return native
        logger.warning("NativeEmbedder deps not installed; falling back to Ollama")

    # Fallback / explicit ollama
    logger.info("Using OllamaEmbedder (model=nomic-embed-text)")
    return OllamaEmbedder(
        model="nomic-embed-text",
        base_url=PROVIDER_ENDPOINTS["local"],
    )


# ── Headless Worker Factory ───────────────────────────────────

class HeadlessWorkerFactory:
    """Creates stage worker functions with explicit config — no server imports.

    Each worker is a callable: (progress_cb) -> Dict[str, Any].
    Progress callback signature: (message: str, current: int, total: int).
    """

    def __init__(
        self,
        repo_root: Path,
        index_dir: Path,
        config: HeadlessConfig,
    ):
        self.repo_root = repo_root
        self.index_dir = index_dir
        self.config = config
        self._llm_client = None  # Lazy-init, shared across stages

    def _get_llm(self):
        if self._llm_client is None:
            self._llm_client = headless_create_llm_client(self.config)
        return self._llm_client

    def _get_batch_profile(self):
        try:
            from prep.core.batch_profiles import resolve_profile
            client = self._get_llm()
            return resolve_profile(client.provider, client.model)
        except Exception:
            return None

    # ── Stage 1: Structural (Rust AST parse) ──────────────────

    def structural_worker(self, progress_cb: Callable) -> Dict[str, Any]:
        from prep.core.trace import TraceBuilder, TraceIndex

        builder = TraceBuilder(
            repo_root=self.repo_root,
            index_dir=self.index_dir,
            include_globs=self.config.include_globs,
            exclude_globs=self.config.exclude_globs,
            max_file_bytes=self.config.max_file_bytes,
            hard_limit_bytes=self.config.hard_limit_bytes,
        )
        builder.build(progress_callback=progress_cb)

        trace_idx = TraceIndex(self.index_dir)
        trace_idx.load()
        return {"stage": "structural", "nodes": trace_idx.node_count()}

    # ── Stage 2: Inferred Edges (LLM) ────────────────────────

    def inferred_edges_worker(self, progress_cb: Callable) -> Dict[str, Any]:
        from prep.core import InferredEdgesAnalyzer

        llm = self._get_llm()
        batch_profile = self._get_batch_profile()

        analyzer = InferredEdgesAnalyzer(
            index_dir=self.index_dir,
            repo_root=str(self.repo_root),
            llm_client=llm,
            batch_profile=batch_profile,
        )
        result = analyzer.run(progress_callback=progress_cb)
        return {
            "stage": "inferred_edges",
            "files_analyzed": result.files_analyzed,
            "edges_written": result.edges_written,
        }

    # ── Stage 3: Catalogue / Augmentation (LLM) ──────────────

    def catalogue_worker(self, progress_cb: Callable) -> Dict[str, Any]:
        from prep.core import TraceAugmenter

        llm = self._get_llm()
        batch_profile = self._get_batch_profile()

        augmenter = TraceAugmenter(
            index_dir=self.index_dir,
            repo_root=str(self.repo_root),
            llm_client=llm,
            batch_profile=batch_profile,
        )
        result = augmenter.run(progress_callback=progress_cb)
        return {"stage": "catalogue", "augmented": result.augmented}

    # ── Stage 4: Validation (pass-through) ────────────────────

    def validation_worker(self, progress_cb: Callable) -> Dict[str, Any]:
        from prep.core.trace import TraceIndex

        progress_cb("Validating relationships", 0, 1)
        trace_idx = TraceIndex(self.index_dir)
        progress_cb("Validation complete", 1, 1)
        return {"stage": "validation", "exists": trace_idx.exists()}

    # ── Stage 5: Knowledge Embedding ──────────────────────────

    def knowledge_worker(self, progress_cb: Callable) -> Dict[str, Any]:
        from prep.core.knowledge import KnowledgeIndex

        embedder = headless_create_embedder(self.config)
        idx = KnowledgeIndex(self.index_dir, embedder)
        result = idx.build(progress_callback=progress_cb)
        return {"stage": "knowledge", **(result or {})}

    # ── Stage 6: Epistemic Enrichment (deep LLM) ─────────────

    def epistemic_worker(self, progress_cb: Callable) -> Dict[str, Any]:
        from prep.core import EpistemicEnricher

        llm = self._get_llm()
        batch_profile = self._get_batch_profile()

        enricher = EpistemicEnricher(
            llm=llm,
            repo_root=self.repo_root,
            index_dir=self.index_dir,
            batch_profile=batch_profile,
        )
        result = enricher.run(progress_callback=progress_cb)
        return {"stage": "enrichment", **(result or {})}

    # ── Stage 7: Clustering (deep LLM) ────────────────────────

    def cluster_worker(self, progress_cb: Callable) -> Dict[str, Any]:
        from prep.core import ClusterSynthesizer

        llm = self._get_llm()
        batch_profile = self._get_batch_profile()

        synthesizer = ClusterSynthesizer(
            llm=llm,
            index_dir=self.index_dir,
            batch_profile=batch_profile,
        )
        result = synthesizer.run(progress_callback=progress_cb)
        return {"stage": "clustering", **(result or {})}

    # ── Stage 8: Atlas generation ─────────────────────────────

    def atlas_worker(self, progress_cb: Callable) -> Dict[str, Any]:
        from prep.core.atlas import CodebaseAtlas

        llm = self._get_llm()
        atlas = CodebaseAtlas(self.index_dir, llm=llm, project_root=self.repo_root)

        # Always regenerate in headless mode (no staleness heuristic)
        doc, segment_docs = atlas.generate_segmented(progress_callback=progress_cb)
        result = {
            "stage": "atlas",
            "chars": doc.char_count,
            "mode": doc.mode,
            "file_count": doc.file_count,
            "module_count": doc.module_count,
            "segment_count": len(segment_docs),
        }

        # Generate routing index
        try:
            embedder = headless_create_embedder(self.config)
            routing_descs = atlas.generate_routing(embedder, progress_callback=progress_cb)
            result["routing_segments"] = len(routing_descs)
        except Exception as e:
            logger.debug("Atlas routing generation skipped: %s", e)
            result["routing_segments"] = 0

        return result

    # ── Stage 9: Deepening (iterative re-enrichment) ──────────

    def deepening_worker(self, progress_cb: Callable) -> Dict[str, Any]:
        from prep.core import EpistemicEnricher, DeepeningLoop

        llm = self._get_llm()

        enricher = EpistemicEnricher(
            llm=llm,
            repo_root=self.repo_root,
            index_dir=self.index_dir,
        )
        loop = DeepeningLoop(
            enricher=enricher,
            index_dir=self.index_dir,
            max_iterations=10,
            batch_size=20,
        )
        result = loop.run(progress_callback=progress_cb)
        return {
            "stage": "deepening",
            "iterations": result.iterations,
            "converged": bool(result.convergence),
        }

    # ── Stage 7: Group Reasoning (cross-file deep reasoning) ──

    def group_reasoning_worker(self, progress_cb: Callable) -> Dict[str, Any]:
        from prep.core import GroupReasoningEngine

        llm = self._get_llm()
        engine = GroupReasoningEngine(llm=llm, index_dir=self.index_dir)
        result = engine.run(progress_callback=progress_cb)
        return {"stage": "group_reasoning", **(result or {})}

    # ── Stage 11: Deep Knowledge (re-embed with deep data) ───

    def deep_knowledge_worker(self, progress_cb: Callable) -> Dict[str, Any]:
        return self.knowledge_worker(progress_cb)


# ── Stage definitions for the sequential runner ───────────────

HEADLESS_STAGES = [
    ("structural",       "Stage 1/11: Structural (AST parse)"),
    ("inferred_edges",   "Stage 2/11: Inferred Edges (LLM)"),
    ("catalogue",        "Stage 3/11: Catalogue (LLM)"),
    ("validation",       "Stage 4/11: Validation"),
    ("knowledge",        "Stage 5/11: Knowledge Embedding"),
    ("enrichment",       "Stage 6/11: Epistemic Enrichment (deep LLM)"),
    ("group_reasoning",  "Stage 7/11: Group Reasoning (deep LLM, think)"),
    ("clustering",       "Stage 8/11: Clustering (deep LLM)"),
    ("atlas",            "Stage 9/11: Atlas Generation"),
    ("deepening",        "Stage 10/11: Deepening Loop"),
    ("deep_knowledge",   "Stage 11/11: Deep Knowledge Embedding"),
]


# ── The Headless Runner ───────────────────────────────────────

class HeadlessRunner:
    """Runs the full headless indexing pipeline."""

    def __init__(self, config: HeadlessConfig):
        self.config = config
        self._work_dir: Optional[Path] = None
        self._cleanup_work_dir = False
        self.stage_results: List[StageResult] = []

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
            "--",  # Prevent flag injection via malicious URLs
            url,
            str(repo_dir),
        ]

        logger.info("Cloning repository: %s (branch: %s)", self.config.repo_url, self.config.branch)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            # Sanitize stderr to avoid leaking GIT_TOKEN if injected into URL
            stderr = result.stderr
            if git_token and git_token in stderr:
                stderr = stderr.replace(git_token, "***")
            raise RuntimeError(f"Git clone failed: {stderr}")

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
            ((time.time() - manifest.timestamp) / 60) if manifest.timestamp else 0,
        )

        try:
            s3.download_index(index_dir)
            logger.info("Downloaded existing index for incremental rebuild")
        except Exception as e:
            logger.warning("Failed to download existing index — falling back to full build: %s", e)

    def _run_pipeline(self, repo_path: Path, index_dir: Path) -> None:
        """Run all 11 stages sequentially using the HeadlessWorkerFactory."""
        factory = HeadlessWorkerFactory(
            repo_root=repo_path,
            index_dir=index_dir,
            config=self.config,
        )

        # Map stage IDs to worker methods
        workers: Dict[str, Callable] = {
            "structural":      factory.structural_worker,
            "inferred_edges":  factory.inferred_edges_worker,
            "catalogue":       factory.catalogue_worker,
            "validation":      factory.validation_worker,
            "knowledge":       factory.knowledge_worker,
            "enrichment":      factory.epistemic_worker,
            "group_reasoning": factory.group_reasoning_worker,
            "clustering":      factory.cluster_worker,
            "atlas":           factory.atlas_worker,
            "deepening":       factory.deepening_worker,
            "deep_knowledge":  factory.deep_knowledge_worker,
        }

        def _make_progress_cb(sid: str) -> Callable:
            """Factory to avoid closure-capture-by-reference bug in loops."""
            def progress_cb(message: str, current: int, total: int, baseline: int = 0) -> None:
                # F-44: accept and ignore baseline so workers can pass it through
                # uniformly. The headless harness only logs, so the cached/new
                # split isn't visible here, but we track it for consistency.
                if total > 0:
                    pct = int(current / total * 100)
                    if baseline > 0:
                        logger.info(
                            "  [%s %d%%] %s (%d/%d, %d baseline)",
                            sid, pct, message, current, total, baseline,
                        )
                    else:
                        logger.info("  [%s %d%%] %s (%d/%d)", sid, pct, message, current, total)
            return progress_cb

        total_start = time.time()

        for stage_id, stage_label in HEADLESS_STAGES:
            worker = workers[stage_id]
            logger.info("─── %s ───", stage_label)

            progress_cb = _make_progress_cb(stage_id)

            stage_start = time.time()
            try:
                details = worker(progress_cb)
                duration = time.time() - stage_start
                self.stage_results.append(StageResult(
                    stage=stage_id,
                    success=True,
                    duration_seconds=duration,
                    details=details,
                ))
                logger.info("  ✓ %s completed in %.1fs", stage_id, duration)

            except Exception as e:
                duration = time.time() - stage_start
                self.stage_results.append(StageResult(
                    stage=stage_id,
                    success=False,
                    duration_seconds=duration,
                    error=str(e),
                ))
                logger.error("  ✗ %s failed after %.1fs: %s", stage_id, duration, e)
                # Structural failure is fatal — can't continue without AST
                if stage_id == "structural":
                    raise RuntimeError(f"Structural stage failed (fatal): {e}") from e
                # Other failures are non-fatal — log and continue
                logger.warning("  Continuing despite %s failure...", stage_id)

        total_duration = time.time() - total_start
        succeeded = sum(1 for r in self.stage_results if r.success)
        failed = sum(1 for r in self.stage_results if not r.success)
        logger.info(
            "Pipeline complete: %d/%d stages succeeded in %.1fs (%d failed)",
            succeeded, len(self.stage_results), total_duration, failed,
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
