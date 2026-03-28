"""
Embedder abstraction for CoDRAG.

Provides a base class and Ollama implementation for generating embeddings.
"""

from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional

import requests

logger = logging.getLogger(__name__)


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
    vector: List[float]
    model: str


class Embedder(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> EmbeddingResult:
        """Generate an embedding vector for the given text."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
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
        max_input_chars: Optional[int] = None,
        num_ctx: Optional[int] = None,
        query_prefix: Optional[str] = None,
        document_prefix: Optional[str] = None,
        matryoshka_dim: Optional[int] = None,
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
        self.num_ctx: Optional[int] = num_ctx if num_ctx is not None else preset.get("num_ctx")
        self.query_prefix: str = query_prefix if query_prefix is not None else preset.get("query_prefix", "")
        self.document_prefix: str = document_prefix if document_prefix is not None else preset.get("document_prefix", "")
        self.matryoshka_dim: Optional[int] = matryoshka_dim if matryoshka_dim is not None else preset.get("matryoshka_dim")

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
            from codrag.core.model_readiness import ollama_ensure_ready, ModelStatus

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

        last_err: Optional[Exception] = None
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
        last_err: Optional[Exception] = None
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

    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
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


# Batch size by provider — GPU can handle much larger batches.
# Scaled by system memory to prevent peak-memory spikes on small machines.
_PROVIDER_BATCH_SIZES = {
    "CoreMLExecutionProvider": 128,
    "CUDAExecutionProvider": 128,
    "DmlExecutionProvider": 64,
    "CPUExecutionProvider": 32,
}


def _memory_scaled_batch_size(provider: str) -> int:
    """Return a batch size for *provider* scaled by available system RAM.

    On machines with ≤ 16 GB RAM the default 128-item GPU batch can
    create ~200 MB of transient numpy arrays during ``_embed_texts()``.
    Halving the batch size approximately halves that peak.

    Falls back to the static defaults if memory detection fails.
    """
    try:
        from codrag.core.context_config import detect_system_memory_gb
        mem_gb = detect_system_memory_gb()
    except Exception:
        mem_gb = 0.0

    base = _PROVIDER_BATCH_SIZES.get(provider, 32)
    if mem_gb <= 0:
        return base  # detection failed, use defaults
    if mem_gb <= 16:
        return max(8, base // 2)   # 64 for GPU, 16 for CPU
    if mem_gb <= 64:
        return max(16, base * 3 // 4)  # 96 for GPU, 24 for CPU
    return base  # 65 GB+ — full defaults


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
    MAX_LENGTH = 8192
    DIM = 768

    def __init__(
        self,
        repo_id: str = HF_REPO_ID,
        onnx_file: str = ONNX_FILE,
        max_length: int = MAX_LENGTH,
        batch_size: int = 0,
        document_prefix: str = "search_document: ",
        query_prefix: str = "search_query: ",
    ):
        """
        Initialize the native ONNX embedder.

        Args:
            repo_id: HuggingFace repo ID for the model.
            onnx_file: Path within the repo to the ONNX model file.
            max_length: Maximum token sequence length (nomic-embed-text supports 8192).
            batch_size: Maximum texts per ONNX inference call.
                        0 = auto-detect based on execution provider
                        (128 for GPU, 32 for CPU).
            document_prefix: Prefix prepended to documents during indexing.
            query_prefix: Prefix prepended to queries during search.
        """
        self.repo_id = repo_id
        self.onnx_file = onnx_file
        self.max_length = max_length
        self._requested_batch_size = batch_size
        self.batch_size = batch_size if batch_size > 0 else 32  # default until GPU detected
        self.document_prefix = document_prefix
        self.query_prefix = query_prefix
        self.model_name = f"native:{repo_id.split('/')[-1]}"
        self.active_provider: str = "CPUExecutionProvider"

        self._session: Optional[Any] = None
        self._tokenizer: Optional[Any] = None

    # -- lazy init ---------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Download (if needed) and load ONNX model + tokenizer.

        Automatically selects the best available execution provider:
        CoreML on Apple Silicon, CUDA on NVIDIA, CPU as fallback.
        Adjusts batch_size based on the active provider.
        """
        if self._session is not None and self._tokenizer is not None:
            return

        try:
            from huggingface_hub import hf_hub_download  # type: ignore[import-untyped]
            import onnxruntime as ort  # type: ignore[import-untyped]
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

        # Detect best available provider
        providers = _detect_onnx_providers()

        # CPU-specific thread tuning (ignored by GPU providers)
        if providers[0] == "CPUExecutionProvider":
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
                providers[0], e,
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

        # Auto-detect batch size based on active provider
        if self._requested_batch_size <= 0:
            self.batch_size = _memory_scaled_batch_size(self.active_provider)

        logger.info(
            "Native embedding model loaded (%s, dim=%d, provider=%s, batch_size=%d)",
            self.model_name, self.DIM, self.active_provider, self.batch_size,
        )

    # -- core embedding ----------------------------------------------------

    def _embed_texts(self, texts: List[str]) -> "np.ndarray":
        """Embed a list of texts, returning an (N, DIM) float32 array."""
        import numpy as np  # local import keeps module-level import list light

        self._ensure_loaded()
        assert self._tokenizer is not None
        assert self._session is not None

        encodings = self._tokenizer.encode_batch(texts)

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

    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple document texts (batched ONNX inference)."""
        if not texts:
            return []

        prefixed = [self.document_prefix + t for t in texts]
        results: List[EmbeddingResult] = []

        for start in range(0, len(prefixed), self.batch_size):
            chunk = prefixed[start : start + self.batch_size]
            vecs = self._embed_texts(chunk)
            for vec in vecs:
                results.append(EmbeddingResult(vector=vec.tolist(), model=self.model_name))

        return results

    def is_available(self) -> bool:
        """Check if required dependencies are installed."""
        try:
            import onnxruntime  # noqa: F401
            import tokenizers  # noqa: F401
            import huggingface_hub  # noqa: F401
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

    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        return [self.embed(t) for t in texts]
