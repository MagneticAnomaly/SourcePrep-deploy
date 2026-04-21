"""Shared JSON extraction utilities for agent engines.

LLMs frequently wrap JSON output in markdown code fences (```json ... ```)
or include preamble text before the actual JSON. These utilities robustly
extract parseable JSON from such responses.
"""
from __future__ import annotations

import json
import re
from typing import Any


def extract_json(raw: str) -> Any:
    """Extract and parse JSON from an LLM response.

    Handles these common LLM output formats:
    1. Raw JSON (best case)
    2. JSON wrapped in ```json ... ``` fences
    3. JSON wrapped in ``` ... ``` fences (no language tag)
    4. JSON buried after preamble text

    Args:
        raw: Raw LLM response string.

    Returns:
        Parsed JSON (dict, list, or primitive).

    Raises:
        ValueError: If no valid JSON can be extracted.
    """
    if not raw or not raw.strip():
        raise ValueError("Empty response — cannot extract JSON")

    text = raw.strip()

    # Strategy 1: Try raw parse first (cheapest)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Strategy 2: Extract from markdown code fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        fenced = fence_match.group(1).strip()
        try:
            return json.loads(fenced)
        except (json.JSONDecodeError, TypeError):
            pass

    # Strategy 3: Find the outermost JSON structure in the text
    # Look for array
    arr_start = text.find("[")
    arr_end = text.rfind("]")
    if arr_start != -1 and arr_end > arr_start:
        candidate = text[arr_start : arr_end + 1]
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            pass

    # Look for object
    obj_start = text.find("{")
    obj_end = text.rfind("}")
    if obj_start != -1 and obj_end > obj_start:
        candidate = text[obj_start : obj_end + 1]
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            pass

    raise ValueError(
        f"Could not extract valid JSON from LLM response. "
        f"First 200 chars: {text[:200]}"
    )
