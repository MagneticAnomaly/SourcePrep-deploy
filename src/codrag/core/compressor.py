"""
Context compression abstraction for CoDRAG.

Provides a base class and concrete implementations for compressing
retrieved context before injecting it into LLM prompts.

Implementations:
  - NoopCompressor: pass-through (no compression)
"""

from __future__ import annotations

import logging
import time as _time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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


class StructuralCompressor(ContextCompressor):
    """Compresses context by replacing file paths with short codes.

    Inspired by MemPalace's AAAK dialect. Builds a symbol registry from
    a list of file paths and replaces occurrences in text with 3-5 char
    uppercase codes. A legend is prepended so any LLM can read it.

    This compressor requires no external service — it's pure string
    replacement. Typical compression ratio: 1.3-2.0x for path-heavy
    context (swarm payloads, dependency lists, impact analysis).
    """

    def __init__(self, paths: List[str]) -> None:
        from codrag.core.compression.symbol_registry import SymbolRegistry

        self._registry = SymbolRegistry()
        self._registry.register_paths(paths)

    def compress(
        self,
        text: str,
        *,
        query: str = "",
        budget_chars: int = 0,
        level: str = "standard",
        timeout_s: float = 30.0,
    ) -> CompressResult:
        t0 = _time.monotonic()
        input_chars = len(text)

        if len(self._registry) == 0:
            return CompressResult(
                compressed=text,
                input_chars=input_chars,
                output_chars=input_chars,
            )

        compressed = self._registry.compress_text(text)
        legend = self._registry.legend()

        if legend:
            compressed = legend + "\n\n" + compressed

        if budget_chars > 0 and len(compressed) > budget_chars:
            legend_end = compressed.index("\n\n") + 2 if "\n\n" in compressed else 0
            available = budget_chars - legend_end
            if available > 0:
                compressed = compressed[:legend_end] + compressed[legend_end:legend_end + available]
            else:
                compressed = compressed[:budget_chars]

        output_chars = len(compressed)
        ratio = input_chars / output_chars if output_chars > 0 else 1.0
        elapsed = (_time.monotonic() - t0) * 1000

        return CompressResult(
            compressed=compressed,
            input_chars=input_chars,
            output_chars=output_chars,
            compression_ratio=round(ratio, 2),
            timing_ms=round(elapsed, 1),
        )

    def is_available(self) -> bool:
        return True

    def status(self) -> Dict[str, Any]:
        return {
            "available": True,
            "type": "structural",
            "registered_paths": len(self._registry),
        }
