"""
Embedder abstraction for Prep.

Provides a base class and Ollama implementation for generating embeddings.
"""

from __future__ import annotations

import logging
import os
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)


# ── Phase 139 env-var knobs ────────────────────────────────────────
# Documented in CLAUDE.md and docs/Phase139_EmbedderMemoryHardening/.
def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    """Read an int env var, return default on missing/invalid/below-minimum."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        val = int(raw)
        return val if val >= minimum else default
    except ValueError:
        return default


def _env_flag(name: str) -> bool:
    """Read a boolean env var (truthy strings: 1, true, yes)."""
    raw = os.environ.get(name, "").strip().lower()
    return raw in ("1", "true", "yes", "on")


# Phase 139 escape hatch: revert to pre-139 embedder behavior (no
# CoreML opts, no fixed-shape padding, original batch sizes, original
# MAX_LENGTH). Use for emergency rollback if the new path breaks on a
# user's box. Default off.
def _legacy_mode() -> bool:
    return _env_flag("PREP_EMBED_LEGACY")


# Known Ollama embedding model presets.
# Maps model name (or common alias) → {query_prefix, document_prefix}.
# Models not listed here get empty prefixes (no-op).
KNOWN_OLLAMA_MODELS: dict = {
    # nomic-embed-code (code-specialized, Qwen2-7B backbone)
    # Query prefix from official Nomic documentation.
    # matryoshka_dim: model outputs 3584-dim vectors but cosine spread is
    # very narrow at full dim (~0.08).  Truncating to 768 via Matryoshka
    # restores spread to ~0.31, matching the ONNX text model.
    "nomic-embed-code": {
        "query_prefix": "Represent this query for searching relevant code: ",
        "document_prefix": "",
        "matryoshka_dim": 768,
    },
    "manutic/nomic-embed-code": {"dim": 3584, "matryoshka_dim": 768},
    # nomic-embed-text-v2-moe (deprecated: hard 512-token context limit + score compression)
    "nomic-embed-text-v2-moe": {
        "query_prefix": "search_query: ",
        "document_prefix": "search_document: ",
        "max_input_chars": 1_800,
        "num_ctx": 8192,
    },
    "nomic-embed-text-v2-moe:latest": {
        "query_prefix": "search_query: ",
        "document_prefix": "search_document: ",
        "max_input_chars": 1_800,
        "num_ctx": 8192,
    },
    # nomic-embed-text (general-purpose, same model as NativeEmbedder)
    "nomic-embed-text": {
        "query_prefix": "search_query: ",
        "document_prefix": "search_document: ",
        "num_ctx": 8192,
    },
    "nomic-embed-text:latest": {
        "query_prefix": "search_query: ",
        "document_prefix": "search_document: ",
        "num_ctx": 8192,
    },
    "nomic-ai/nomic-embed-text-v1.5": {
        "query_prefix": "search_query: ",
        "document_prefix": "search_document: ",
    },
}


@dataclass(frozen=True)
class EmbeddingResult:
    """Result of an embedding operation."""
    vector: list[float]
    model: str


class Embedder(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> EmbeddingResult:
        """Generate an embedding vector for the given text."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate embeddings for multiple texts."""
        pass


class OllamaEmbedder(Embedder):
    """Ollama-based embedder using the /api/embeddings endpoint."""

    # Conservative char limit for Ollama embedding models.
    # Code/JSON can tokenize at <1 char/token with nomic-embed-text
    # (8192 ctx).  2000 chars is safe for all content types.
    _DEFAULT_MAX_INPUT_CHARS = 2_000

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        timeout_s: int = 60,
        max_retries: int = 4,
        keep_alive: str = "10m",
        max_input_chars: int | None = None,
        num_ctx: int | None = None,
        query_prefix: str | None = None,
        document_prefix: str | None = None,
        matryoshka_dim: int | None = None,
    ):
        """
        Initialize the Ollama embedder.

        Args:
            model: Ollama embedding model name
            base_url: Ollama API base URL
            timeout_s: Request timeout in seconds
            max_retries: Number of retry attempts for transient failures
            keep_alive: How long to keep the model loaded (e.g., "10m", "1h")
            max_input_chars: Truncate input to this many characters before
                             sending to Ollama.  Prevents "input length exceeds
                             context length" 500 errors.  Defaults to 24 000
                             (~8 k tokens for nomic-embed-text).
            query_prefix: Text prepended to queries at search time.  If None,
                          looked up from KNOWN_OLLAMA_MODELS, then defaults to "".
            document_prefix: Text prepended to documents at index time.  If None,
                             looked up from KNOWN_OLLAMA_MODELS, then defaults to "".
            num_ctx: Context window size passed to Ollama via request options.
                     Overrides Ollama's default (often 2048) to unlock the
                     model's full context (e.g., 8192 for nomic-embed-text-v2-moe).
                     If None, looked up from KNOWN_OLLAMA_MODELS preset.
            matryoshka_dim: Truncate embeddings to this many dimensions via
                            Matryoshka representation learning (truncate + L2
                            re-normalize).  High-dim models (e.g., 3584-dim
                            nomic-embed-code) have very narrow cosine spread;
                            truncating to 768 restores discriminative power.
                            If None, looked up from KNOWN_OLLAMA_MODELS preset.
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.keep_alive = keep_alive
        self._readiness_checked = False

        # Resolve prefixes: explicit arg > KNOWN_OLLAMA_MODELS lookup > empty string
        preset = KNOWN_OLLAMA_MODELS.get(model, {})
        self.max_input_chars = max_input_chars if max_input_chars is not None else preset.get("max_input_chars", self._DEFAULT_MAX_INPUT_CHARS)
        self.num_ctx: int | None = num_ctx if num_ctx is not None else preset.get("num_ctx")
        self.query_prefix: str = query_prefix if query_prefix is not None else preset.get("query_prefix", "")
        self.document_prefix: str = document_prefix if document_prefix is not None else preset.get("document_prefix", "")
        self.matryoshka_dim: int | None = matryoshka_dim if matryoshka_dim is not None else preset.get("matryoshka_dim")

    def _ensure_model_ready(self) -> None:
        """Check if the embedding model is loaded and preload if needed.

        Only runs once per embedder lifetime to avoid repeated overhead.
        Uses the model_readiness module to detect cold-start scenarios
        and trigger model loading before the first real request.
        """
        if self._readiness_checked:
            return
        self._readiness_checked = True

        try:
            from prep.core.model_readiness import ModelStatus, ollama_ensure_ready

            # Use a generous timeout for model loading (not the per-request
            # timeout) — after a long LLM run Ollama may need to swap models.
            preload_timeout = max(self.timeout_s, 180)
            preload_options = {"num_ctx": self.num_ctx} if self.num_ctx else None
            result = ollama_ensure_ready(
                url=self.base_url,
                model=self.model,
                timeout_s=preload_timeout,
                keep_alive=self.keep_alive,
                options=preload_options,
            )
            if result.status == ModelStatus.READY:
                logger.info("Embedding model '%s' is ready", self.model)
            elif result.status == ModelStatus.NOT_FOUND:
                logger.error(
                    "Embedding model '%s' not found on %s. Run: ollama pull %s",
                    self.model, self.base_url, self.model,
                )
            else:
                logger.warning(
                    "Embedding model '%s' readiness: %s — %s",
                    self.model, result.status.value, result.message,
                )
        except Exception as e:
            logger.warning("Readiness check failed (non-fatal): %s", e)

    def _try_embed_request(self, text: str) -> EmbeddingResult:
        """Try /api/embed (Ollama ≥0.4) then fall back to /api/embeddings."""
        # Truncate to stay within model context window
        if self.max_input_chars and len(text) > self.max_input_chars:
            logger.debug(
                "Truncating embedding input from %d to %d chars",
                len(text), self.max_input_chars,
            )
            text = text[: self.max_input_chars]

        options: dict = {}
        if self.num_ctx:
            options["num_ctx"] = self.num_ctx

        endpoints = [
            (
                f"{self.base_url}/api/embed",
                {"model": self.model, "input": text, "keep_alive": self.keep_alive,
                 **({"options": options} if options else {})},
                "embeddings",   # response key: list of vectors
            ),
        ]
        # Only fall back to the legacy /api/embeddings endpoint when
        # num_ctx is NOT required.  The legacy endpoint ignores the
        # options dict, so it uses the Ollama model-file default
        # (often 2 048 tokens) — far too small for v2-moe at 2 400
        # chars.  Older Ollama (< 0.4) only has /api/embeddings.
        if not self.num_ctx:
            endpoints.append((
                f"{self.base_url}/api/embeddings",
                {"model": self.model, "prompt": text, "keep_alive": self.keep_alive,
                 **({"options": options} if options else {})},
                "embedding",    # response key: single vector
            ))

        last_err: Exception | None = None
        for url, payload, key in endpoints:
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout_s)

                if resp.status_code >= 500:
                    body = ""
                    try:
                        body = resp.text[:500]
                    except Exception:
                        pass
                    logger.warning(
                        "Ollama %s returned %d: %s", url, resp.status_code, body,
                    )
                    last_err = requests.HTTPError(
                        f"{resp.status_code} Server Error for url: {resp.url} — {body}",
                        response=resp,
                    )
                    # Context-length errors won't be fixed by a different
                    # endpoint — /api/embeddings ignores num_ctx options and
                    # has an even lower limit.  Raise immediately.
                    if "context length" in body.lower():
                        raise last_err
                    continue  # try next endpoint

                if resp.status_code == 404:
                    continue  # endpoint not available, try next

                if resp.status_code == 400:
                    body = ""
                    try:
                        body = resp.text[:500]
                    except Exception:
                        pass
                    logger.warning(
                        "Ollama %s returned 400: %s (input %d chars)",
                        url, body, len(text),
                    )
                    raise requests.HTTPError(
                        f"400 Client Error for url: {resp.url} — {body}",
                        response=resp,
                    )

                resp.raise_for_status()
                data = resp.json() or {}

                # /api/embed returns {"embeddings": [[...]]}
                if key == "embeddings":
                    embs = data.get("embeddings")
                    if isinstance(embs, list) and embs:
                        emb = embs[0]
                    else:
                        emb = None
                else:
                    emb = data.get("embedding")

                if not isinstance(emb, list) or not emb:
                    logger.warning(
                        "Ollama %s returned 200 but '%s' is empty/missing "
                        "(input may still exceed context length, %d chars sent)",
                        url, key, len(text),
                    )
                    last_err = ValueError(
                        f"Ollama response missing '{key}': {str(data)[:200]}"
                    )
                    continue

                vec = [float(x) for x in emb]

                # Matryoshka truncation: keep only the first N dims.
                # High-dim models (e.g., 3584-dim nomic-embed-code) have
                # very narrow cosine spread at full dim; truncating to
                # 768 restores discriminative power.
                if self.matryoshka_dim and len(vec) > self.matryoshka_dim:
                    vec = vec[: self.matryoshka_dim]

                # L2-normalize so dot products equal cosine similarity,
                # consistent with NativeEmbedder output.
                norm = sum(v * v for v in vec) ** 0.5
                if norm > 1e-9:
                    vec = [v / norm for v in vec]

                return EmbeddingResult(
                    vector=vec,
                    model=data.get("model") or self.model,
                )
            except (requests.RequestException, ValueError) as e:
                logger.debug("Ollama %s exception: %s", url, e)
                last_err = e
                continue

        raise last_err or RuntimeError("Ollama embedding failed (all endpoints)")

    def _embed_with_retries(self, text: str) -> EmbeddingResult:
        """Send *text* (already prefixed) to Ollama with retry/back-off.

        On context-length errors the input is progressively truncated
        (75% → 56% → 42% of original) instead of retrying the same
        text.  This handles dense content that exceeds the model's
        token context at the character-level ``max_input_chars`` limit.
        """
        self._ensure_model_ready()

        current_text = text
        last_err: Exception | None = None
        for attempt in range(max(1, self.max_retries)):
            try:
                return self._try_embed_request(current_text)
            except (requests.RequestException, ValueError) as e:
                last_err = e
                err_str = str(e).lower()

                # Context-length error: shorten input instead of
                # retrying the same text that will always fail.
                if "context length" in err_str and len(current_text) > 200:
                    new_len = int(len(current_text) * 0.75)
                    logger.warning(
                        "Context overflow at %d chars — truncating to %d "
                        "(attempt %d/%d)",
                        len(current_text), new_len,
                        attempt + 1, self.max_retries,
                    )
                    current_text = current_text[:new_len]
                    continue  # retry immediately with shorter text

                logger.warning(
                    "Embedding attempt %d/%d failed: %s",
                    attempt + 1, self.max_retries, e,
                )
                if attempt >= self.max_retries - 1:
                    break

                base_delay_s = 0.35 * (2**attempt)
                jitter_s = random.random() * 0.25
                time.sleep(base_delay_s + jitter_s)

        raise last_err or RuntimeError("Ollama embedding failed")

    def embed(self, text: str) -> EmbeddingResult:
        """Embed a single document text (document_prefix applied)."""
        prefixed = self.document_prefix + text if self.document_prefix else text
        return self._embed_with_retries(prefixed)

    def embed_query(self, text: str) -> EmbeddingResult:
        """Embed a search query (query_prefix applied)."""
        prefixed = self.query_prefix + text if self.query_prefix else text
        return self._embed_with_retries(prefixed)

    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Embed multiple document texts (document_prefix applied to each)."""
        return [self._embed_with_retries(self.document_prefix + t if self.document_prefix else t) for t in texts]


def _detect_onnx_providers() -> list:
    """Detect the best available ONNX execution providers.

    Tries GPU-accelerated providers first, falls back to CPU.
    Order matters: ONNX runtime uses the first available provider.

    Supported accelerated providers:
    - CoreMLExecutionProvider: Apple Silicon (macOS), 3-5x speedup
    - CUDAExecutionProvider: NVIDIA GPUs, 10-50x speedup
    - DmlExecutionProvider: DirectML on Windows (AMD/Intel/NVIDIA)

    Returns a list of provider names to pass to ort.InferenceSession().
    """
    import platform
    try:
        import onnxruntime as ort
    except ImportError:
        return ["CPUExecutionProvider"]

    available = set(ort.get_available_providers())
    providers: list = []

    # macOS: CoreML (Apple Neural Engine + GPU)
    if platform.system() == "Darwin" and "CoreMLExecutionProvider" in available:
        providers.append("CoreMLExecutionProvider")

    # NVIDIA: CUDA
    if "CUDAExecutionProvider" in available:
        providers.append("CUDAExecutionProvider")

    # Windows: DirectML (works with AMD, Intel, NVIDIA)
    if platform.system() == "Windows" and "DmlExecutionProvider" in available:
        providers.append("DmlExecutionProvider")

    # Always include CPU as final fallback
    providers.append("CPUExecutionProvider")
    return providers


def _provider_name(provider_entry: Any) -> str:
    """Return the provider name from either a string or (name, opts) tuple."""
    if isinstance(provider_entry, tuple) and provider_entry:
        return provider_entry[0]
    return str(provider_entry)


def _coreml_cache_dir() -> str:
    """Return a stable directory for CoreML .mlmodelc compilation cache.

    Sharing this across daemon restarts avoids the multi-second
    Espresso compile on every fresh session. Lives under the user's
    cache root, isolated by ONNX file name.
    """
    import pathlib
    base = pathlib.Path(os.path.expanduser("~/.cache/sourceprep/coreml"))
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


def _apply_phase139_provider_opts(providers: list, model_path: str) -> list:
    """Inject Phase 139 conservative provider options.

    - **CoreML (macOS):** disable ANE by default (CPUAndGPU only) to
      sidestep the documented ``setEspressoBlobShapes`` hangs and the
      ANE-pinned memory non-release. Force MLProgram format,
      RequireStaticInputShapes=1, ModelCacheDirectory, and
      FastPrediction specialization.

      ``PREP_COREML_USE_ANE=1`` opts back into ANE.

    - **CUDA / DirectML:** no opts added in Phase 139. CPU EP is
      already tuned in ``_ensure_loaded``.

    Non-macOS platforms see the provider list unchanged (this function
    is a no-op for them). See RESEARCH.md §1.3 + IMPLEMENTATION_PLAN.md
    T1.2.
    """
    import platform
    if platform.system() != "Darwin":
        return providers

    use_ane = _env_flag("PREP_COREML_USE_ANE")
    coreml_opts = {
        # Skip the Apple Neural Engine path by default. ANE has had
        # documented hangs in MLNeuralNetworkEngine.setEspressoBlobShapes
        # on macOS 15+, and ANE memory does not release back to the OS
        # within the daemon's lifetime.
        "MLComputeUnits": "CPUAndNeuralEngine" if use_ane else "CPUAndGPU",
        # Newer code path under maintenance; supports more model formats.
        "ModelFormat": "MLProgram",
        # Dynamic-shape ops fall back to CPU EP per-node instead of
        # triggering an Espresso recompile that can hang.
        "RequireStaticInputShapes": "1",
        # Persist compiled .mlmodelc across daemon restarts.
        "ModelCacheDirectory": _coreml_cache_dir(),
        # macOS 14+ — fewer specialization variants kept in memory.
        "SpecializationStrategy": "FastPrediction",
    }

    out: list = []
    saw_coreml = False
    for entry in providers:
        if _provider_name(entry) == "CoreMLExecutionProvider":
            out.append(("CoreMLExecutionProvider", coreml_opts))
            saw_coreml = True
        else:
            out.append(entry)
    if saw_coreml:
        logger.info(
            "CoreML opts applied: MLComputeUnits=%s, "
            "ModelFormat=MLProgram, RequireStaticInputShapes=1, "
            "ModelCacheDirectory=%s",
            coreml_opts["MLComputeUnits"], coreml_opts["ModelCacheDirectory"],
        )
    return out


# Phase 139: conservative, flat defaults. Bigger machines do NOT batch
# larger — peak memory is what matters, not throughput for a one-time
# index. Override via PREP_EMBED_MAX_BATCH env var.
#
# Pre-Phase-139 defaults (preserved here for PREP_EMBED_LEGACY=1):
#   CoreML/CUDA: 128, DirectML: 64, CPU: 32, scaled up to 128 on big RAM.
# That policy produced ~100 GB physical footprint at B=128 × S=8192
# (see docs/Phase139_EmbedderMemoryHardening/INCIDENT.md).
_PHASE139_BATCH_SIZES = {
    "CoreMLExecutionProvider": 16,
    "CUDAExecutionProvider": 16,
    "DmlExecutionProvider": 16,
    "CPUExecutionProvider": 8,
}

# Retained verbatim for PREP_EMBED_LEGACY=1 rollback path.
_LEGACY_BATCH_SIZES = {
    "CoreMLExecutionProvider": 128,
    "CUDAExecutionProvider": 128,
    "DmlExecutionProvider": 64,
    "CPUExecutionProvider": 32,
}


def _default_batch_size(provider: str) -> int:
    """Return the conservative Phase 139 batch size for *provider*.

    Env override: ``PREP_EMBED_MAX_BATCH`` (absolute integer, applies to
    all providers, must be ≥ 1).

    Legacy mode (``PREP_EMBED_LEGACY=1``) restores the pre-139 table
    plus the per-RAM scaling — for emergency rollback only.
    """
    env_batch = _env_int("PREP_EMBED_MAX_BATCH", 0, minimum=1)
    if env_batch > 0:
        return env_batch

    if _legacy_mode():
        return _legacy_memory_scaled_batch_size(provider)

    return _PHASE139_BATCH_SIZES.get(provider, 8)


def _legacy_memory_scaled_batch_size(provider: str) -> int:
    """Pre-Phase-139 batch policy, retained for PREP_EMBED_LEGACY=1."""
    try:
        from prep.core.context_config import detect_system_memory_gb
        mem_gb = detect_system_memory_gb()
    except Exception:
        mem_gb = 0.0

    base = _LEGACY_BATCH_SIZES.get(provider, 32)
    if mem_gb <= 0:
        return base
    if mem_gb <= 16:
        return max(8, base // 2)
    if mem_gb <= 64:
        return max(16, base * 3 // 4)
    return base


# Phase 139 bucket boundaries for fixed-shape padding (see RESEARCH.md
# §3.3 + CORPUS_PROFILE.md). 100% of observed corpus fits ≤512; the
# 1024 bucket is safety margin for the chunker's 1.5× slack ceiling.
_DEFAULT_SEQ_BUCKETS = (128, 256, 512, 1024)

# Phase 139 PR2: token budget for batch dispatch (RESEARCH.md §3.5 +
# IMPLEMENTATION_PLAN.md T2.1). One ONNX call accumulates inputs until
# bucket_seq × batch_size > max_batch_tokens. Memory becomes a flat
# ceiling regardless of input length mix.
#
# Override via PREP_EMBED_MAX_BATCH_TOKENS (must be ≥ 128).
_DEFAULT_MAX_BATCH_TOKENS = 8192


def _max_batch_tokens() -> int:
    """Token budget for one ONNX dispatch. Env: PREP_EMBED_MAX_BATCH_TOKENS."""
    return _env_int("PREP_EMBED_MAX_BATCH_TOKENS", _DEFAULT_MAX_BATCH_TOKENS, minimum=128)


def _emit_provider_downgrade_event(*, requested: str, active: str) -> None:
    """T5.3: one-line telemetry when ORT silently downgrades the EP."""
    if not _env_flag("PREP_RSS_TELEMETRY"):
        return
    try:
        import json as _json
        from datetime import UTC, datetime

        from prep.services import rss_sampler
        rec = {
            "ts": datetime.now(UTC).isoformat(),
            "event": "provider_downgrade",
            "payload": {"requested": requested, "active": active},
        }
        log_path = rss_sampler._default_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(_json.dumps(rec) + "\n")
    except Exception as e:
        logger.debug("provider_downgrade telemetry failed (non-fatal): %s", e)


def _emit_embed_batch_event(*, batch_size: int, seq_len: int, wall_ms: float, provider: str) -> None:
    """Phase 139 T5.2: per-batch embedder telemetry. Routes through the
    daemon RSS log (same file as the sampler) when PREP_RSS_TELEMETRY is
    enabled. Fail-quiet — telemetry must never break a pipeline.
    """
    if not _env_flag("PREP_RSS_TELEMETRY"):
        return
    try:
        import json as _json
        from datetime import UTC, datetime

        from prep.core import memory_guard
        from prep.services import rss_sampler

        snap = memory_guard.sample()
        rec = {
            "ts": datetime.now(UTC).isoformat(),
            "event": "embed_batch",
            "payload": {
                "batch_size": batch_size,
                "seq_len": seq_len,
                "wall_ms": round(wall_ms, 2),
                "rss_gb": round(snap.rss_gb, 3),
                "provider": provider,
            },
        }
        log_path = rss_sampler._default_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(_json.dumps(rec) + "\n")
    except Exception as e:
        logger.debug("embed_batch telemetry failed (non-fatal): %s", e)


def _seq_buckets(max_length: int) -> tuple:
    """Return ascending bucket boundaries, all ≤ *max_length*.

    Buckets above max_length are filtered out. If max_length is smaller
    than the smallest bucket, returns (max_length,).
    """
    out = tuple(b for b in _DEFAULT_SEQ_BUCKETS if b <= max_length)
    return out if out else (max_length,)


def _pick_bucket(token_lens: list[int], buckets: tuple, max_length: int) -> int:
    """Return the smallest bucket ceiling that fits the longest token sequence.

    If all sequences exceed every bucket, returns *max_length* (which
    will trigger upstream truncation).
    """
    longest = max(token_lens) if token_lens else 0
    for b in buckets:
        if longest <= b:
            return b
    return max_length


def _pad_2d(rows: list[list[int]], target_len: int, pad_value: int = 0) -> Any:
    """Right-pad/truncate each row of *rows* to *target_len*, return int64 ndarray.

    The shape is always ``(len(rows), target_len)``. Rows longer than
    target_len are truncated. Used by Phase 139 fixed-shape padding so
    the ONNX graph sees a finite set of (batch, seq) shapes.
    """
    import numpy as np
    out = np.full((len(rows), target_len), pad_value, dtype=np.int64)
    for i, row in enumerate(rows):
        n = min(len(row), target_len)
        if n > 0:
            out[i, :n] = row[:n]
    return out


class NativeEmbedder(Embedder):
    """Built-in ONNX-based embedder using nomic-embed-text-v1.5.

    Runs entirely locally — no Ollama, no cloud API, no torch.
    Model files are downloaded from HuggingFace Hub on first use and
    cached in the standard HF cache directory (~/.cache/huggingface/).

    GPU acceleration is automatic when available:
    - macOS: CoreML (Apple Neural Engine + Metal GPU), 3-5x faster
    - NVIDIA: CUDA (requires onnxruntime-gpu), 10-50x faster
    - Windows: DirectML (requires onnxruntime-directml)
    Falls back to CPU if no GPU provider is available.

    Dependencies: onnxruntime, tokenizers, huggingface-hub.
    """

    HF_REPO_ID = "nomic-ai/nomic-embed-text-v1.5"
    ONNX_FILE = "onnx/model_quantized.onnx"
    TOKENIZER_FILE = "tokenizer.json"
    # Phase 139: 8192 → 1024. Profile of real corpus (5K-doc sample of
    # this repo) shows max observed token length is 322; chunker caps
    # raw chunks at ~675 tokens worst case (chunking.py:214 max_chars
    # 1800 × 1.5 slack). 1024 gives ~3× safety margin.
    # Pre-Phase-139 value (8192) restored when PREP_EMBED_LEGACY=1.
    # Override via PREP_EMBED_MAX_LEN env var.
    MAX_LENGTH = 1024
    LEGACY_MAX_LENGTH = 8192
    DIM = 768

    def __init__(
        self,
        repo_id: str = HF_REPO_ID,
        onnx_file: str = ONNX_FILE,
        max_length: int = 0,
        batch_size: int = 0,
        document_prefix: str = "search_document: ",
        query_prefix: str = "search_query: ",
        *,
        _from_factory: bool = False,
    ):
        """
        Initialize the native ONNX embedder.

        Args:
            repo_id: HuggingFace repo ID for the model.
            onnx_file: Path within the repo to the ONNX model file.
            max_length: Maximum token sequence length. ``0`` = use the
                        Phase-139 default (1024) or the
                        ``PREP_EMBED_MAX_LEN`` env override.
                        ``PREP_EMBED_LEGACY=1`` restores 8192.
            batch_size: Maximum texts per ONNX inference call.
                        ``0`` = auto-detect based on execution provider
                        (Phase 139: 16 for GPU/CoreML, 8 for CPU).
                        Override via ``PREP_EMBED_MAX_BATCH``.
            document_prefix: Prefix prepended to documents during indexing.
            query_prefix: Prefix prepended to queries during search.
            _from_factory: Set by ``embedder_factory.create_embedder()``
                           to suppress the direct-construction warning.
                           **Do not pass manually** — go through the
                           factory so the singleton cache is honored
                           (Phase 139 Q11).
        """
        # Phase 139 Q11: warn loudly when constructed outside the
        # factory. Bypasses the singleton cache and re-loads the ONNX
        # session, defeating the duplicate-session fix.
        if not _from_factory:
            logger.warning(
                "NativeEmbedder() constructed directly — bypasses the "
                "process-wide singleton cache and re-loads the ONNX "
                "session. Use prep.services.embedder_factory."
                "create_embedder() instead. (Phase 139)"
            )

        self.repo_id = repo_id
        self.onnx_file = onnx_file

        # Resolve max_length: explicit arg > env var > Phase-139 default
        # (or LEGACY_MAX_LENGTH under PREP_EMBED_LEGACY=1).
        if max_length > 0:
            self.max_length = max_length
        else:
            env_max_len = _env_int("PREP_EMBED_MAX_LEN", 0, minimum=1)
            if env_max_len > 0:
                self.max_length = env_max_len
            elif _legacy_mode():
                self.max_length = self.LEGACY_MAX_LENGTH
            else:
                self.max_length = self.MAX_LENGTH

        # Resolve batch_size: explicit arg > env var > provider default.
        # The env override is applied here at construction so logs are
        # accurate; provider-specific defaults still apply in _ensure_loaded.
        self._requested_batch_size = batch_size
        if batch_size > 0:
            self.batch_size = batch_size
        else:
            # Provisional until _ensure_loaded determines active provider.
            self.batch_size = _default_batch_size("CPUExecutionProvider")

        self.document_prefix = document_prefix
        self.query_prefix = query_prefix
        self.model_name = f"native:{repo_id.split('/')[-1]}"
        self.active_provider: str = "CPUExecutionProvider"

        self._session: Any | None = None
        self._tokenizer: Any | None = None
        # PR2 T3.2: idle-release timer reads this; updated on each embed call.
        import time as _time
        self._last_embed_ts: float = _time.monotonic()

    def close(self) -> None:
        """Drop the ONNX session and tokenizer references.

        Per RESEARCH.md §1.1, this is **not** guaranteed to reclaim
        CoreML/ANE memory in the live process — ORT's CoreML EP does
        not return memory to the OS until process exit (open issue
        #26831). Restart the daemon for full reclaim.

        Call from ``embedder_factory.close_shared_embedders()`` on
        ``/pipeline/rebuild/stop`` and graceful shutdown.
        """
        import gc
        self._session = None
        self._tokenizer = None
        gc.collect()
        logger.debug("NativeEmbedder.close(): dropped session reference")

    # -- lazy init ---------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Download (if needed) and load ONNX model + tokenizer.

        Automatically selects the best available execution provider:
        CoreML on Apple Silicon, CUDA on NVIDIA, CPU as fallback.
        Adjusts batch_size based on the active provider.

        Phase 139: applies SessionOptions memory tuning
        (``enable_cpu_mem_arena=False`` + ``enable_mem_pattern=False``)
        and macOS-only CoreML provider options. See
        ``docs/Phase139_EmbedderMemoryHardening/RESEARCH.md`` §1.3.
        Bypass via ``PREP_EMBED_LEGACY=1``.
        """
        if self._session is not None and self._tokenizer is not None:
            return

        try:
            import onnxruntime as ort  # type: ignore[import-untyped]
            from huggingface_hub import hf_hub_download  # type: ignore[import-untyped]
            from tokenizers import Tokenizer  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "NativeEmbedder requires: pip install onnxruntime tokenizers huggingface-hub"
            ) from e

        logger.info("Loading native embedding model %s ...", self.repo_id)

        tok_path = hf_hub_download(self.repo_id, self.TOKENIZER_FILE)
        model_path = hf_hub_download(self.repo_id, self.onnx_file)

        self._tokenizer = Tokenizer.from_file(tok_path)
        self._tokenizer.enable_truncation(max_length=self.max_length)
        self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")

        sess_opts = ort.SessionOptions()
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        # Phase 139: disable CPU memory arena and memory pattern to cut
        # baseline footprint. RESEARCH.md §2.3 (ORT issue #11627).
        # Legacy mode preserves the historic behavior.
        if not _legacy_mode():
            try:
                sess_opts.enable_cpu_mem_arena = False
                sess_opts.enable_mem_pattern = False
            except AttributeError:
                logger.debug("ORT version does not expose mem_arena/mem_pattern flags")

        # Detect best available provider
        providers = _detect_onnx_providers()

        # Phase 139: layer in provider-specific options. CoreML opts only
        # apply on macOS; on Linux/Windows the provider tuple is unchanged.
        if not _legacy_mode():
            providers = _apply_phase139_provider_opts(providers, model_path)

        # CPU-specific thread tuning (ignored by GPU providers)
        if _provider_name(providers[0]) == "CPUExecutionProvider":
            sess_opts.inter_op_num_threads = 1
            sess_opts.intra_op_num_threads = 4

        try:
            self._session = ort.InferenceSession(
                model_path,
                sess_options=sess_opts,
                providers=providers,
            )
        except Exception as e:
            # GPU provider failed (e.g., CUDA OOM, CoreML compile error).
            # Fall back to CPU silently.
            logger.warning(
                "GPU provider %s failed, falling back to CPU: %s",
                _provider_name(providers[0]), e,
            )
            sess_opts.inter_op_num_threads = 1
            sess_opts.intra_op_num_threads = 4
            self._session = ort.InferenceSession(
                model_path,
                sess_options=sess_opts,
                providers=["CPUExecutionProvider"],
            )

        # Determine which provider is actually active
        active = self._session.get_providers()
        self.active_provider = active[0] if active else "CPUExecutionProvider"

        # PR2 T5.3: detect silent CoreML/CUDA → CPU downgrade. ORT will
        # accept a provider list and quietly drop unsupported entries.
        # If we asked for a GPU/CoreML/DML provider and ended up on CPU,
        # surface it so users notice their "acceleration" isn't happening.
        requested_first = _provider_name(providers[0])
        if requested_first != "CPUExecutionProvider" and self.active_provider == "CPUExecutionProvider":
            logger.warning(
                "Requested execution provider %s but session reports %s — "
                "silent downgrade. Verify provider deps (onnxruntime-gpu / "
                "onnxruntime-directml) or check Phase 139 CoreML opts.",
                requested_first, self.active_provider,
            )
            _emit_provider_downgrade_event(
                requested=requested_first, active=self.active_provider,
            )

        # Auto-detect batch size based on active provider
        if self._requested_batch_size <= 0:
            self.batch_size = _default_batch_size(self.active_provider)

        # Cache bucket boundaries derived from the final max_length
        self._seq_buckets = _seq_buckets(self.max_length)

        logger.info(
            "Native embedding model loaded (%s, dim=%d, provider=%s, "
            "batch_size=%d, max_length=%d, buckets=%s%s)",
            self.model_name, self.DIM, self.active_provider, self.batch_size,
            self.max_length, self._seq_buckets,
            " [LEGACY mode]" if _legacy_mode() else "",
        )

    # -- core embedding ----------------------------------------------------

    def _embed_texts(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts, returning an (N, DIM) float32 array.

        Phase 139: tokenize with dynamic padding to the longest item,
        then pad up to the smallest bucket ceiling that fits. This
        keeps inference on a small, finite set of (batch, seq) shapes
        — critical for CoreML EP which recompiles per shape.
        Legacy mode (``PREP_EMBED_LEGACY=1``) restores the pre-139
        ``pad_to_longest`` only behavior.
        """
        import numpy as np  # local import keeps module-level import list light

        self._ensure_loaded()
        assert self._tokenizer is not None
        assert self._session is not None

        # Tokenize (padding="longest" within batch is the tokenizer default
        # because enable_padding was set in _ensure_loaded without a fixed length).
        encodings = self._tokenizer.encode_batch(texts)

        # Phase 139: snap the per-batch sequence length up to the
        # smallest matching bucket so the ONNX graph sees a finite set
        # of shapes. Without this, CoreML EP recompiles per shape and
        # may hang on macOS 15+ (RESEARCH.md §1.2).
        if not _legacy_mode() and getattr(self, "_seq_buckets", None):
            token_lens = [len(e.ids) for e in encodings]
            bucket_seq = _pick_bucket(token_lens, self._seq_buckets, self.max_length)
            input_ids = _pad_2d(
                [e.ids for e in encodings], bucket_seq, pad_value=0,
            )
            attention_mask = _pad_2d(
                [e.attention_mask for e in encodings], bucket_seq, pad_value=0,
            )
        else:
            input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

        token_type_ids = np.zeros_like(input_ids)

        outputs = self._session.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )
        hidden = outputs[0]  # (N, seq_len, 768)

        # Mean pooling over non-padding tokens
        mask_expanded = attention_mask[:, :, np.newaxis].astype(np.float32)
        summed = np.sum(hidden * mask_expanded, axis=1)
        counts = np.sum(mask_expanded, axis=1)
        mean_pooled = summed / np.maximum(counts, 1e-9)

        # L2 normalize
        norms = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
        normalized = mean_pooled / np.maximum(norms, 1e-9)

        return normalized

    # -- public interface --------------------------------------------------

    def embed(self, text: str) -> EmbeddingResult:
        """Generate an embedding for a single text (document prefix applied)."""
        prefixed = self.document_prefix + text
        vec = self._embed_texts([prefixed])[0]
        return EmbeddingResult(vector=vec.tolist(), model=self.model_name)

    def embed_query(self, text: str) -> EmbeddingResult:
        """Generate an embedding for a search query (query prefix applied)."""
        prefixed = self.query_prefix + text
        vec = self._embed_texts([prefixed])[0]
        return EmbeddingResult(vector=vec.tolist(), model=self.model_name)

    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate embeddings for multiple document texts.

        Phase 139 PR2: length-sorted bucket dispatch with token-budget
        batching (RESEARCH.md §3.5 + IMPLEMENTATION_PLAN.md T2.1, T2.2).

        1. Tokenize all texts once.
        2. Group by bucket (smallest matching ceiling).
        3. Within each bucket, accumulate items until
           ``len(batch) × bucket_seq > max_batch_tokens``.
        4. Dispatch one ONNX call per batch.
        5. Reassemble in original order.

        The memory ceiling per dispatch is ~``max_batch_tokens × hidden_dim``
        regardless of input length mix — the small-input case processes
        far more items per call than the old flat-batch policy.

        Memory guard: each dispatched batch is guarded by ``memory_guard.check``.
        On trip, the active batch is halved until it fits or bottoms out
        at 1 (``MemoryCeilingExceeded`` raises in that case).

        ``PREP_EMBED_LEGACY=1`` restores the pre-PR-2 flat-stride path.
        """
        if not texts:
            return []

        prefixed = [self.document_prefix + t for t in texts]

        if _legacy_mode():
            # Legacy: flat stride, no memory guard.
            results: list[EmbeddingResult] = []
            for start in range(0, len(prefixed), self.batch_size):
                chunk = prefixed[start : start + self.batch_size]
                vecs = self._embed_texts(chunk)
                for vec in vecs:
                    results.append(EmbeddingResult(vector=vec.tolist(), model=self.model_name))
            return results

        # Phase 139 PR2 path
        self._ensure_loaded()
        self._touch_idle()
        return self._dispatch_token_budget(prefixed)

    def _dispatch_token_budget(self, prefixed: list[str]) -> list[EmbeddingResult]:
        """Length-sorted bucket dispatch with token-budget batching."""
        assert self._tokenizer is not None
        import numpy as np

        from prep.core import memory_guard

        encodings = self._tokenizer.encode_batch(prefixed)
        buckets = getattr(self, "_seq_buckets", None) or _seq_buckets(self.max_length)
        budget = _max_batch_tokens()

        # Group input indices by the smallest matching bucket. Inside each
        # bucket, sort longest-first so similar-length items cluster.
        per_bucket: dict[int, list[int]] = {b: [] for b in buckets}
        for idx, enc in enumerate(encodings):
            token_len = len(enc.ids)
            bucket = self.max_length
            for b in buckets:
                if token_len <= b:
                    bucket = b
                    break
            per_bucket.setdefault(bucket, []).append(idx)

        for b in per_bucket:
            per_bucket[b].sort(key=lambda i: len(encodings[i].ids), reverse=True)

        # Pre-allocate the output array so we can place vectors at their
        # original index without a second sort pass.
        out_vectors: list[np.ndarray | None] = [None] * len(prefixed)
        active_batch = self.batch_size  # upper bound; budget shrinks per bucket

        for bucket_seq, idxs in per_bucket.items():
            if not idxs:
                continue
            # Effective batch from budget: how many bucket_seq-long items fit.
            budget_batch = max(1, budget // bucket_seq)
            batch_cap = max(1, min(active_batch, budget_batch))

            i = 0
            while i < len(idxs):
                snap = memory_guard.check(can_shrink=(batch_cap > 1), op="embed_batch")
                if snap.over_ceiling and batch_cap > 1:
                    batch_cap = max(1, batch_cap // 2)
                    logger.warning(
                        "Memory guard tripped — shrinking embedder batch to %d "
                        "(RSS %.2f GB / ceiling %.2f GB)",
                        batch_cap, snap.rss_gb, snap.ceiling_gb,
                    )
                    continue

                batch_idxs = idxs[i : i + batch_cap]
                input_ids = _pad_2d(
                    [encodings[j].ids for j in batch_idxs], bucket_seq, pad_value=0,
                )
                attention_mask = _pad_2d(
                    [encodings[j].attention_mask for j in batch_idxs], bucket_seq, pad_value=0,
                )
                vecs = self._embed_token_batch(input_ids, attention_mask)
                for k, orig_idx in enumerate(batch_idxs):
                    out_vectors[orig_idx] = vecs[k]
                i += batch_cap

        # Sanity: every slot filled.
        assert all(v is not None for v in out_vectors), "dispatch dropped an input"
        return [
            EmbeddingResult(vector=v.tolist(), model=self.model_name)
            for v in out_vectors  # type: ignore[union-attr]
        ]

    def _embed_token_batch(self, input_ids: Any, attention_mask: Any) -> Any:
        """Run one ONNX inference on pre-padded inputs and return pooled embeddings.

        Inner loop of the token-budget dispatcher. ``input_ids`` and
        ``attention_mask`` are int64 ndarrays of shape (B, S). Returns a
        (B, DIM) float32 array, L2-normed.
        """
        import time

        import numpy as np

        assert self._session is not None
        token_type_ids = np.zeros_like(input_ids)

        t0 = time.monotonic()
        outputs = self._session.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )
        wall_ms = (time.monotonic() - t0) * 1000.0
        hidden = outputs[0]  # (B, S, 768)

        mask_expanded = attention_mask[:, :, np.newaxis].astype(np.float32)
        summed = np.sum(hidden * mask_expanded, axis=1)
        counts = np.sum(mask_expanded, axis=1)
        mean_pooled = summed / np.maximum(counts, 1e-9)

        norms = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
        normalized = mean_pooled / np.maximum(norms, 1e-9)

        # T5.2: per-batch telemetry (opt-in via PREP_RSS_TELEMETRY).
        _emit_embed_batch_event(
            batch_size=int(input_ids.shape[0]),
            seq_len=int(input_ids.shape[1]),
            wall_ms=wall_ms,
            provider=self.active_provider,
        )
        return normalized

    def _touch_idle(self) -> None:
        """Update the idle timestamp so the idle-release timer knows we're active."""
        import time
        self._last_embed_ts = time.monotonic()

    @staticmethod
    def is_available() -> bool:
        """Check if required dependencies are installed.

        Static — can be called as ``NativeEmbedder.is_available()`` for
        feature detection without constructing an instance (which would
        bypass the Phase 139 singleton cache and trigger the
        direct-construction warning).
        """
        try:
            import huggingface_hub  # noqa: F401
            import onnxruntime  # noqa: F401
            import tokenizers  # noqa: F401
            return True
        except ImportError:
            return False

    def download_model(self) -> str:
        """Pre-download the model files. Returns the path to the ONNX model."""
        from huggingface_hub import hf_hub_download  # type: ignore[import-untyped]

        hf_hub_download(self.repo_id, self.TOKENIZER_FILE)
        model_path = hf_hub_download(self.repo_id, self.onnx_file)
        return model_path


class FakeEmbedder(Embedder):
    """
    Fake embedder for testing that generates deterministic pseudo-embeddings.
    
    Does NOT require Ollama or any external service.
    """

    def __init__(self, model: str = "fake-embed", dim: int = 384):
        self.model = model
        self.dim = dim

    def embed(self, text: str) -> EmbeddingResult:
        """Generate a deterministic embedding based on text hash."""
        # Use hashlib (not built-in hash()) for cross-run determinism
        import hashlib
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**31)
        rng = random.Random(seed)
        vector = [rng.gauss(0, 1) for _ in range(self.dim)]
        # Normalize to unit length
        norm = sum(x * x for x in vector) ** 0.5
        vector = [x / norm for x in vector]
        return EmbeddingResult(vector=vector, model=self.model)

    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        return [self.embed(t) for t in texts]
