"""Extract structural signals from search queries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_KNOWN_EXTENSIONS = (
    r"\.(?:py|ts|tsx|js|jsx|rs|go|java|kt|rb|c|cpp|h|hpp|cs|swift|scala|sh|yaml|yml|toml|json|md)"
)

# Matches file paths containing at least one "/" and ending with a known extension
_FILE_PATH_RE = re.compile(r"(?:^|\s)((?:[\w.@-]+/)+[\w.-]+" + _KNOWN_EXTENSIONS + r")(?:\s|$)")

# Matches bare file names (no "/") ending with a known extension
_FILE_NAME_RE = re.compile(r"(?:^|\s)([\w.-]+" + _KNOWN_EXTENSIONS + r")(?:\s|$)")

# CamelCase: at least two words joined, each starting uppercase
_CAMEL_CASE_RE = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z0-9]*)+)\b")

# snake_case: lowercase letters with at least one underscore
_SNAKE_CASE_RE = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b")

_STOP_WORDS = frozenset({
    "the", "how", "does", "what", "where", "when", "why", "which",
    "this", "that", "with", "from", "for", "and", "not", "but",
    "can", "will", "just", "about", "into",
    "file", "files", "code", "function", "class", "method",
    "work", "works", "look", "explain", "show", "find", "get",
    "use", "uses", "handle", "handles", "module", "modules",
})


@dataclass
class QuerySignals:
    """Structural signals extracted from a search query."""

    file_names: list[str] = field(default_factory=list)
    file_paths: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    @property
    def has_structural_signals(self) -> bool:
        """True if any file names, file paths, or symbols were found."""
        return bool(self.file_names or self.file_paths or self.symbols)

    def compute_coverage(self, content: str) -> dict[str, bool]:
        """For each keyword, check whether it appears in content (case-insensitive)."""
        lower = content.lower()
        return {kw: kw.lower() in lower for kw in self.keywords}

    def coverage_ratio(self, content: str) -> float:
        """Fraction of keywords found in content. Returns 1.0 if no keywords."""
        if not self.keywords:
            return 1.0
        cov = self.compute_coverage(content)
        return sum(cov.values()) / len(cov)


class QueryAnalyzer:
    """Extracts structural signals from natural-language search queries."""

    @staticmethod
    def extract_signals(query: str) -> QuerySignals:
        """Parse *query* and return a :class:`QuerySignals` instance."""

        # --- file paths (must come first so we can exclude their tokens later) ---
        file_paths = _FILE_PATH_RE.findall(query)

        # --- file names (bare, no slash) ---
        file_names: list[str] = []
        for m in _FILE_NAME_RE.findall(query):
            # Skip if this name is the tail of an already-extracted path
            if any(p.endswith(m) for p in file_paths):
                continue
            file_names.append(m)

        # Collect all path/name tokens so we can skip them for symbol extraction
        path_tokens: set[str] = set()
        for p in file_paths + file_names:
            path_tokens.update(re.split(r"[/.]", p))

        # --- symbols ---
        symbols: list[str] = []
        for m in _CAMEL_CASE_RE.findall(query):
            if m not in path_tokens:
                symbols.append(m)
        for m in _SNAKE_CASE_RE.findall(query):
            if m not in path_tokens:
                symbols.append(m)

        # Build the set of tokens already captured as structured signals
        captured: set[str] = set()
        for p in file_paths + file_names:
            captured.update(re.split(r"[/._-]", p))
        for s in symbols:
            # Split CamelCase and snake_case into constituent words
            captured.update(re.sub(r"([A-Z])", r" \1", s).lower().split())
            captured.update(s.lower().split("_"))

        # --- keywords ---
        tokens = re.findall(r"[A-Za-z]{3,}", query)
        keywords: list[str] = []
        seen: set[str] = set()
        for tok in tokens:
            low = tok.lower()
            if low in _STOP_WORDS or low in captured or low in seen:
                continue
            seen.add(low)
            keywords.append(tok.lower())

        return QuerySignals(
            file_names=file_names,
            file_paths=file_paths,
            symbols=symbols,
            keywords=keywords,
        )
