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
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.keep_alive = keep_alive
        self.max_input_chars = max_input_chars if max_input_chars is not None else self._DEFAULT_MAX_INPUT_CHARS
        self._readiness_checked = False

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
            result = ollama_ensure_ready(
                url=self.base_url,
                model=self.model,
                timeout_s=preload_timeout,
                keep_alive=self.keep_alive,
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

        endpoints = [
            (
                f"{self.base_url}/api/embed",
                {"model": self.model, "input": text, "keep_alive": self.keep_alive},
                "embeddings",   # response key: list of vectors
            ),
            (
                f"{self.base_url}/api/embeddings",
                {"model": self.model, "prompt": text, "keep_alive": self.keep_alive},
                "embedding",    # response key: single vector
            ),
        ]

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
                    continue  # try next endpoint

                if resp.status_code == 404:
                    continue  # endpoint not available, try next

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

                return EmbeddingResult(
                    vector=[float(x) for x in emb],
                    model=data.get("model") or self.model,
                )
            except (requests.RequestException, ValueError) as e:
                last_err = e
                continue

        raise last_err or RuntimeError("Ollama embedding failed (all endpoints)")

    def embed(self, text: str) -> EmbeddingResult:
        """Generate an embedding for a single text."""
        self._ensure_model_ready()

        last_err: Optional[Exception] = None
        for attempt in range(max(1, self.max_retries)):
            try:
                return self._try_embed_request(text)
            except (requests.RequestException, ValueError) as e:
                last_err = e
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

    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts (sequential for now)."""
        return [self.embed(t) for t in texts]


class NativeEmbedder(Embedder):
    """Built-in ONNX-based embedder using nomic-embed-text-v1.5.

    Runs entirely locally — no Ollama, no cloud API, no torch.
    Model files are downloaded from HuggingFace Hub on first use and
    cached in the standard HF cache directory (~/.cache/huggingface/).

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
        batch_size: int = 32,
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
            document_prefix: Prefix prepended to documents during indexing.
            query_prefix: Prefix prepended to queries during search.
        """
        self.repo_id = repo_id
        self.onnx_file = onnx_file
        self.max_length = max_length
        self.batch_size = batch_size
        self.document_prefix = document_prefix
        self.query_prefix = query_prefix
        self.model_name = f"native:{repo_id.split('/')[-1]}"

        self._session: Optional[Any] = None
        self._tokenizer: Optional[Any] = None

    # -- lazy init ---------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Download (if needed) and load ONNX model + tokenizer."""
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
        sess_opts.inter_op_num_threads = 1
        sess_opts.intra_op_num_threads = 4
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self._session = ort.InferenceSession(
            model_path,
            sess_options=sess_opts,
            providers=["CPUExecutionProvider"],
        )

        logger.info("Native embedding model loaded (%s, dim=%d)", self.model_name, self.DIM)

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
