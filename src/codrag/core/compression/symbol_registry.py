"""
Symbol Registry — deterministic short codes for file paths.

Inspired by MemPalace's AAAK dialect: replaces repetitive file paths
and FQNs with 3-5 character uppercase codes. No decoder needed — a
legend block is prepended to the output so any LLM can read it.

Codes are derived from the filename (not the full path) to be
human-guessable: src/codrag/core/swarm_orchestrator.py -> SWO.
Collisions are resolved by appending digits.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional


def _stem_code(path: str, length: int = 3) -> str:
    """Derive a short code from a file path's stem.

    Takes the uppercase initials of underscore/camelCase segments.
    Falls back to first N chars of filename if segments are too short.
    """
    name = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    parts = re.split(r"[_\-]", name)
    if len(parts) >= length:
        code = "".join(p[0] for p in parts[:length] if p).upper()
        if len(code) >= 2:
            return code
    return name[:length].upper()


class SymbolRegistry:
    """Maps file paths to short uppercase codes and back."""

    def __init__(self) -> None:
        self._path_to_code: Dict[str, str] = {}
        self._code_to_path: Dict[str, str] = {}

    def register_paths(self, paths: List[str]) -> None:
        """Register a batch of file paths, generating unique codes."""
        for path in paths:
            if path in self._path_to_code:
                continue
            base_code = _stem_code(path)
            code = base_code
            suffix = 2
            while code in self._code_to_path:
                code = f"{base_code}{suffix}"
                suffix += 1
            self._path_to_code[path] = code
            self._code_to_path[code] = path

    def get_code(self, path: str) -> Optional[str]:
        return self._path_to_code.get(path)

    def resolve(self, code: str) -> Optional[str]:
        return self._code_to_path.get(code)

    def legend(self) -> str:
        if not self._path_to_code:
            return ""
        lines = [f"{code}={path}" for path, code in
                 sorted(self._path_to_code.items(), key=lambda x: x[1])]
        return "LEGEND: " + " | ".join(lines)

    def compress_text(self, text: str) -> str:
        result = text
        for path in sorted(self._path_to_code.keys(), key=len, reverse=True):
            code = self._path_to_code[path]
            result = result.replace(path, code)
        return result

    def __len__(self) -> int:
        return len(self._path_to_code)
