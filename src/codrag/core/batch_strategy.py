"""
Batch Strategy — orchestrates multi-item LLM calls for BYOK models.

Provides:
- BatchStrategy: decides whether to batch and at what size for a given stage
- BatchedResponseParser: extracts per-item JSON results from a batched LLM response
- batch_items(): chunks a list of items into batches per the strategy

See docs/Phase35_BYOK/BYOK_BATCH_LIMITS.md for research and design.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .batch_profiles import (
    BatchProfile,
    BatchProfileName,
    BatchStage,
    PROFILE_OFF,
    detect_profile,
    resolve_profile,
)

logger = logging.getLogger(__name__)


# ── Batched Response Parser ──────────────────────────────────────

class BatchedResponseParser:
    """Extracts per-item JSON results from a batched LLM response.

    Tries multiple strategies in order:
    1. Parse as a JSON object with a "results" array key
    2. Parse as a top-level JSON array
    3. Split on newlines and parse each line as JSON (JSONL)
    4. Regex extraction of individual {...} objects

    Each extracted item is matched back to its input by position or by
    an "id"/"file" key if present.
    """

    @staticmethod
    def parse(response_text: str, expected_count: int = 0) -> List[Dict[str, Any]]:
        """Parse a batched response into a list of per-item dicts.

        Args:
            response_text: Raw LLM response text
            expected_count: Expected number of items (for validation, 0 = don't check)

        Returns:
            List of parsed dicts, one per item. May be fewer than expected_count
            if some items failed to parse.
        """
        # Strip think tags before any parsing (Qwen3, DeepSeek-R1, etc.)
        from .llm_client import _strip_think_tags
        text = _strip_think_tags(response_text)
        text = text.strip()
        if not text:
            return []

        # Strategy 1: JSON object with "results" key
        results = BatchedResponseParser._try_results_object(text)
        if results is not None:
            return results

        # Strategy 2: Top-level JSON array
        results = BatchedResponseParser._try_json_array(text)
        if results is not None:
            return results

        # Strategy 3: JSONL (one JSON object per line)
        results = BatchedResponseParser._try_jsonl(text)
        if results is not None:
            return results

        # Strategy 4: Regex extraction of individual {...} objects
        results = BatchedResponseParser._try_regex_extraction(text)
        if results is not None:
            return results

        logger.warning("BatchedResponseParser: all strategies failed for response (%.100s...)", text)
        return []

    @staticmethod
    def _try_results_object(text: str) -> Optional[List[Dict[str, Any]]]:
        """Try parsing as {"results": [...]}."""
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "results" in data:
                results = data["results"]
                if isinstance(results, list):
                    return [r for r in results if isinstance(r, dict)]
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    @staticmethod
    def _try_json_array(text: str) -> Optional[List[Dict[str, Any]]]:
        """Try parsing as a top-level JSON array."""
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [r for r in data if isinstance(r, dict)]
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    @staticmethod
    def _try_jsonl(text: str) -> Optional[List[Dict[str, Any]]]:
        """Try parsing as JSONL (one JSON object per line)."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) < 2:
            return None  # Not useful for single-line (already tried json.loads)

        results = []
        for line in lines:
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    results.append(data)
            except (json.JSONDecodeError, TypeError):
                continue

        # Only accept if we got a reasonable fraction of lines
        if results and len(results) >= len(lines) * 0.5:
            return results
        return None

    @staticmethod
    def _try_regex_extraction(text: str) -> Optional[List[Dict[str, Any]]]:
        """Extract individual JSON objects via balanced-brace regex."""
        results = []
        # Find top-level { ... } blocks (non-greedy, balanced)
        depth = 0
        start = None
        for i, ch in enumerate(text):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    candidate = text[start:i + 1]
                    try:
                        data = json.loads(candidate)
                        if isinstance(data, dict):
                            results.append(data)
                    except (json.JSONDecodeError, TypeError):
                        pass
                    start = None

        return results if results else None


# ── Batch Strategy ───────────────────────────────────────────────

@dataclass
class BatchStrategy:
    """Determines batching behavior for a pipeline stage.

    Created once per stage execution. Holds the resolved batch profile
    and provides helpers for chunking items and parsing responses.
    """
    profile: BatchProfile
    stage: BatchStage

    @property
    def batch_size(self) -> int:
        """Number of items per batch for this stage."""
        return self.profile.batch_size(self.stage)

    @property
    def is_batched(self) -> bool:
        """True if this strategy will batch (more than 1 item per call)."""
        return self.batch_size > 1

    @property
    def profile_name(self) -> str:
        return self.profile.name.value

    def chunk_items(self, items: list) -> List[list]:
        """Split items into batches of the configured size."""
        size = self.batch_size
        if size <= 1:
            return [[item] for item in items]
        return [items[i:i + size] for i in range(0, len(items), size)]

    def parse_response(self, response_text: str, expected_count: int = 0) -> List[Dict[str, Any]]:
        """Parse a batched LLM response into per-item results."""
        return BatchedResponseParser.parse(response_text, expected_count)


def create_batch_strategy(
    provider: str,
    model: str,
    stage: BatchStage,
    profile_override: Optional[str] = None,
) -> BatchStrategy:
    """Create a BatchStrategy for a given model and pipeline stage.

    Args:
        provider: LLM provider ("ollama", "openai", "openai-compatible", "anthropic")
        model: Model name
        stage: Pipeline stage
        profile_override: User override ("auto", "large", "standard", "compact", "off")

    Returns:
        A BatchStrategy configured for this model × stage combination.
    """
    profile = resolve_profile(provider, model, override=profile_override)
    return BatchStrategy(profile=profile, stage=stage)
