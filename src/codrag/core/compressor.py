"""
Context compression abstraction for CoDRAG.

Provides a base class and concrete implementations for compressing
retrieved context before injecting it into LLM prompts.

Implementations:
  - NoopCompressor:   pass-through (no compression)
  - LinguaCompressor: LLMLingua-2 token pruning for natural-language content
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompressResult:
    """Result of a context compression operation."""

    compressed: str
    input_chars: int
    output_chars: int
    input_tokens: int = 0
    output_tokens: int = 0
    compression_ratio: float = 1.0
    timing_ms: float = 0.0
    error: Optional[str] = None


class ContextCompressor(ABC):
    """Abstract base class for context compression providers."""

    @abstractmethod
    def compress(
        self,
        text: str,
        *,
        query: str = "",
        budget_chars: int = 0,
        level: str = "standard",
        timeout_s: float = 30.0,
    ) -> CompressResult:
        """Compress context text.

        Args:
            text: The context string to compress.
            query: The original search query (helps the compressor focus).
            budget_chars: Target output size in characters. 0 = let compressor decide.
            level: Compression aggressiveness: "light", "standard", "aggressive".
            timeout_s: Hard timeout for the compression call.

        Returns:
            CompressResult with compressed text and metadata.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the compression service is reachable."""
        pass

    def status(self) -> Dict[str, Any]:
        """Get status info from the compression service."""
        return {"available": self.is_available()}




class LinguaCompressor(ContextCompressor):
    """LLMLingua-2 token-pruning compressor for natural-language content.

    Wraps ``llmlingua.PromptCompressor`` with the BERT-base multilingual
    model (178 MB).  The model is lazy-loaded on first ``compress()`` call
    so it never blocks server startup.

    Falls back to noop (returns input unchanged) on any error.
    """

    HF_MODEL_ID = "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"

    # Compression-rate presets  (rate = fraction of tokens *kept*)
    LEVEL_RATES = {
        "light": 0.6,
        "standard": 0.4,
        "aggressive": 0.25,
    }

    # Tokens that must never be removed during compression
    FORCE_TOKENS = [
        # Structural formatting
        "\n", "---", "|",
        # File path components and identifiers
        "@", "/", "_", ".py", ".ts", ".tsx", ".js", ".rs", ".go", ".md",
        ".jsx", ".rb", ".java", ".swift", ".css", ".html", ".json",
        ".toml", ".yaml", ".yml",
        # CoDRAG context markers
        "[", "]", "score=",
        # Common code identifiers that appear in language descriptions
        "(", ")", ":", "::", "->", "=>",
        # Punctuation that changes meaning
        "?", "!",
    ]

    def __init__(self, *, model_id: Optional[str] = None) -> None:
        self._model_id = model_id or self.HF_MODEL_ID
        self._compressor: Any = None  # lazy llmlingua.PromptCompressor
        self._available: Optional[bool] = None

    def _ensure_loaded(self) -> Any:
        """Lazy-load the LLMLingua-2 model on first use."""
        if self._compressor is not None:
            return self._compressor
        try:
            from llmlingua import PromptCompressor  # type: ignore[import-untyped]

            self._compressor = PromptCompressor(
                model_name=self._model_id,
                use_llmlingua2=True,
                device_map="cpu",
            )
            self._available = True
            logger.info("LinguaCompressor loaded model: %s", self._model_id)
        except Exception as exc:
            logger.warning("LinguaCompressor failed to load: %s", exc)
            self._available = False
            self._compressor = None
        return self._compressor

    def compress(
        self,
        text: str,
        *,
        query: str = "",
        budget_chars: int = 0,
        level: str = "standard",
        timeout_s: float = 30.0,
    ) -> CompressResult:
        input_chars = len(text)
        if input_chars == 0:
            return CompressResult(compressed="", input_chars=0, output_chars=0)

        comp = self._ensure_loaded()
        if comp is None:
            # Fallback: return text unchanged
            return CompressResult(
                compressed=text,
                input_chars=input_chars,
                output_chars=input_chars,
                error="LLMLingua-2 model not available",
            )

        rate = self.LEVEL_RATES.get(level, self.LEVEL_RATES["standard"])

        t0 = time.perf_counter()
        try:
            result = comp.compress_prompt(
                [text],
                rate=rate,
                force_tokens=self.FORCE_TOKENS,
                drop_consecutive=True,
            )
            compressed = result.get("compressed_prompt", text)
            output_chars = len(compressed)
            timing_ms = (time.perf_counter() - t0) * 1000
            ratio = input_chars / output_chars if output_chars > 0 else 1.0
            return CompressResult(
                compressed=compressed,
                input_chars=input_chars,
                output_chars=output_chars,
                compression_ratio=round(ratio, 2),
                timing_ms=round(timing_ms, 1),
            )
        except Exception as exc:
            timing_ms = (time.perf_counter() - t0) * 1000
            logger.warning("LinguaCompressor.compress failed: %s", exc)
            return CompressResult(
                compressed=text,
                input_chars=input_chars,
                output_chars=input_chars,
                timing_ms=round(timing_ms, 1),
                error=str(exc),
            )

    def is_available(self) -> bool:
        """Check if llmlingua is installed."""
        if self._available is not None:
            return self._available
        # Quick check without loading the full model
        try:
            import llmlingua  # type: ignore[import-untyped]  # noqa: F401
            return True
        except ImportError:
            return False

    def download_model(self) -> str:
        """Pre-download the LLMLingua-2 model from HuggingFace.
        
        Returns the path to the cached model directory.
        """
        from huggingface_hub import snapshot_download  # type: ignore[import-untyped]
        
        model_path = snapshot_download(
            repo_id=self._model_id,
            allow_patterns=["*.json", "*.bin", "*.safetensors", "*.txt"],
        )
        return model_path

    def status(self) -> Dict[str, Any]:
        loaded = self._compressor is not None
        return {
            "available": self.is_available(),
            "model": self._model_id,
            "loaded": loaded,
            "type": "lingua",
        }


class NoopCompressor(ContextCompressor):
    """Pass-through compressor that returns text unchanged. Used as default."""

    def compress(
        self,
        text: str,
        *,
        query: str = "",
        budget_chars: int = 0,
        level: str = "standard",
        timeout_s: float = 30.0,
    ) -> CompressResult:
        return CompressResult(
            compressed=text,
            input_chars=len(text),
            output_chars=len(text),
        )

    def is_available(self) -> bool:
        return True
