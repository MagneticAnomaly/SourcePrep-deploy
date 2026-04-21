"""LODExtractor: Structural code compression via trace graph data.

Levels of Detail (LOD 0–5):
  LOD 0 – Full source                          (1:1)
  LOD 1 – Source minus inline comments         (~1.2:1)
  LOD 2 – Signatures + docstrings + ...        (~3-4:1)
  LOD 3 – Class skeletons only                 (~5:1)
  LOD 4 – Imports + symbol name lines          (~8-10:1)
  LOD 5 – File path + augmentation summary     (~15-20:1)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from prep.core.context_tier import ContextTier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class LODResult:
    """Result of a single LOD extraction call."""
    content: str
    lod: int
    input_chars: int
    output_chars: int
    language: Optional[str] = None
    fallback: bool = False
    error: Optional[str] = None

    @property
    def compression_ratio(self) -> float:
        return round(self.input_chars / max(self.output_chars, 1), 2)


# ---------------------------------------------------------------------------
# Language constants
# ---------------------------------------------------------------------------

_BRACE_LANGS = frozenset({
    "javascript", "typescript", "java", "go", "rust",
    "kotlin", "swift", "csharp", "cpp", "c", "dart", "scala", "php",
})

_PLACEHOLDER: Dict[str, str] = {lang: "    // ..." for lang in _BRACE_LANGS}
_PLACEHOLDER["python"] = "    ..."
_PLACEHOLDER["ruby"] = "    # ..."
_PLACEHOLDER["lua"] = "    -- ..."

_IMPORT_RE: Dict[str, re.Pattern] = {
    "python":     re.compile(r"^\s*(import |from \S+ import )"),
    "javascript": re.compile(r"^\s*(import |const \S+ = require|require\()"),
    "typescript": re.compile(r"^\s*(import |const \S+ = require|require\()"),
    "rust":       re.compile(r"^\s*(use |extern crate )"),
    "go":         re.compile(r"^\s*import\b"),
    "java":       re.compile(r"^\s*import "),
    "kotlin":     re.compile(r"^\s*(import |package )"),
    "swift":      re.compile(r"^\s*import "),
    "csharp":     re.compile(r"^\s*(using |namespace )"),
    "cpp":        re.compile(r"^\s*(#include|using namespace)"),
    "c":          re.compile(r"^\s*#include"),
    "php":        re.compile(r"^\s*(use |require|include|namespace )"),
    "ruby":       re.compile(r"^\s*require"),
    "dart":       re.compile(r"^\s*(import |library |part )"),
    "scala":      re.compile(r"^\s*(import |package )"),
}

# Single-line comment patterns for LOD 1 stripping
_COMMENT_RE: Dict[str, List[re.Pattern]] = {
    "python": [re.compile(r"^\s*#")],
    "ruby":   [re.compile(r"^\s*#")],
    "shell":  [re.compile(r"^\s*#")],
    "lua":    [re.compile(r"^\s*--")],
}
for _bl in _BRACE_LANGS:
    _COMMENT_RE[_bl] = [re.compile(r"^\s*//")]


# ---------------------------------------------------------------------------
# Signature-end detection (line number where signature closes)
# ---------------------------------------------------------------------------

def _sig_end_python(lines: List[str], start: int, end: int) -> int:
    """Return the 1-indexed line where the Python def/class signature closes (:)."""
    depth = 0
    for ln in range(start, min(end + 1, start + 25)):
        if ln - 1 >= len(lines):
            break
        text = lines[ln - 1]
        for ch in text:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
        if depth <= 0 and text.rstrip().endswith(":"):
            return ln
    return start


def _sig_end_brace(lines: List[str], start: int, end: int) -> int:
    """Return 1-indexed line containing the opening `{` of the body."""
    depth = 0
    for ln in range(start, min(end + 1, start + 25)):
        if ln - 1 >= len(lines):
            break
        text = lines[ln - 1]
        for ch in text:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "{" and depth <= 0:
                return ln
    return start


def _find_sig_end(lines: List[str], start: int, end: int, language: str) -> int:
    if language == "python":
        return _sig_end_python(lines, start, end)
    if language in _BRACE_LANGS:
        return _sig_end_brace(lines, start, end)
    return start  # fallback: first line only


# ---------------------------------------------------------------------------
# Docstring detection (lines immediately after signature)
# ---------------------------------------------------------------------------

def _find_docstring_end_python(lines: List[str], sig_end: int, end: int) -> int:
    """Return last 1-indexed line of an inline Python docstring, or sig_end."""
    # Skip blank lines after signature
    ln = sig_end + 1
    while ln <= end and not lines[ln - 1].strip():
        ln += 1
    if ln > end:
        return sig_end

    first = lines[ln - 1].lstrip()
    # Triple-quoted docstring
    for quote in ('"""', "'''", 'r"""', "r'''", 'f"""', 'b"""'):
        if first.startswith(quote):
            opener = quote[:3]
            rest = lines[ln - 1]
            # Check if it closes on same line
            pos = rest.find(opener, rest.find(opener) + 3)
            if pos != -1:
                return ln
            # Multi-line: scan until closing triple-quote
            ln += 1
            while ln <= end:
                if opener in lines[ln - 1]:
                    return ln
                ln += 1
            return end
    return sig_end


def _find_docstring_end(lines: List[str], sig_end: int, end: int, language: str) -> int:
    if language == "python":
        return _find_docstring_end_python(lines, sig_end, end)
    return sig_end


# ---------------------------------------------------------------------------
# LOD 1: strip single-line comments
# ---------------------------------------------------------------------------

def _strip_comments(source: str, language: str) -> str:
    patterns = _COMMENT_RE.get(language, [])
    if not patterns:
        return source
    out_lines = []
    for line in source.splitlines():
        if any(p.match(line) for p in patterns):
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


# ---------------------------------------------------------------------------
# LOD 2 / 3 core: build compressed skeleton from symbols
# ---------------------------------------------------------------------------

_STATE_KEEP = 0
_STATE_PLACEHOLDER = 1
_STATE_SKIP = 2


def _infer_body_end(lines: List[str], start: int, language: str) -> int:
    """Infer function/method body end when the trace span is a single line.

    For brace languages (Swift, JS, TS, Java, etc.): find the matching closing brace.
    For Python: find the last line at deeper indentation.

    Returns the 1-indexed end line, or start if inference fails.
    """
    n = len(lines)
    if start < 1 or start > n:
        return start

    decl_line = lines[start - 1]

    if language in _BRACE_LANGS or language in ("swift",):
        # Scan for opening brace, then match to closing brace
        depth = 0
        found_open = False
        for ln in range(start, min(start + 500, n + 1)):
            text = lines[ln - 1]
            for ch in text:
                if ch == "{":
                    depth += 1
                    found_open = True
                elif ch == "}":
                    depth -= 1
                    if found_open and depth == 0:
                        return ln
        return start

    if language == "python":
        # Find indentation of the def/class line, scan until back to same or less
        base_indent = len(decl_line) - len(decl_line.lstrip())
        last_body = start
        for ln in range(start + 1, min(start + 500, n + 1)):
            text = lines[ln - 1]
            if not text.strip():
                continue
            indent = len(text) - len(text.lstrip())
            if indent <= base_indent:
                break
            last_body = ln
        return last_body

    return start


def _build_lod23(
    lines: List[str],
    symbols: List[Dict[str, Any]],
    language: str,
    lod3: bool = False,
) -> str:
    """
    Build LOD 2 or LOD 3 output.

    LOD 2: all symbols get sig+docstring+...
    LOD 3: top-level standalone functions are removed; only class skeletons kept.
    """
    n = len(lines)
    state = [_STATE_KEEP] * (n + 2)  # 1-indexed; index 0 unused

    placeholder_text = _PLACEHOLDER.get(language, _DEFAULT_PLACEHOLDER)

    # Phase 73.3: Expand single-line spans before sorting/processing.
    # Some parsers (Rust tree-sitter for Swift/JS) store only the deprep-compresstion
    # line. We infer the full body span so LOD 2/3 can compress the body.
    expanded_symbols = []
    for sym in symbols:
        span = sym.get("span") or {}
        start = span.get("start_line", 0)
        end = span.get("end_line", 0)
        if start and end and start == end and start <= n:
            inferred_end = _infer_body_end(lines, start, language)
            if inferred_end > start:
                sym = {**sym, "span": {**span, "end_line": inferred_end}}
        expanded_symbols.append(sym)

    # Sort symbols by span size ascending = process innermost first
    syms = sorted(expanded_symbols, key=lambda s: (s["span"]["end_line"] - s["span"]["start_line"]))

    # Identify class spans to distinguish methods from top-level functions
    class_spans = [
        (s["span"]["start_line"], s["span"]["end_line"])
        for s in syms
        if (s.get("metadata") or {}).get("symbol_type") == "class"
    ]

    def _is_nested(start: int) -> bool:
        """Return True if start_line falls inside any class span."""
        return any(cs <= start <= ce for cs, ce in class_spans)

    for sym in syms:
        span = sym.get("span") or {}
        start = span.get("start_line", 0)
        end = span.get("end_line", 0)
        if not start or not end or end < start:
            continue

        meta = sym.get("metadata") or {}
        sym_type = meta.get("symbol_type", "")

        # Classes: keep their definition + docstring but don't suppress body
        # (child methods will handle their own bodies)
        if sym_type == "class":
            sig_end = _find_sig_end(lines, start, end, language)
            doc_end = _find_docstring_end(lines, sig_end, end, language)
            # Suppress class body AFTER docstring up to first child — we'll
            # recover child lines when we process them. But actually: just
            # mark from doc_end+1 onward as SKIP, children will override to KEEP.
            # Since we process innermost first, children are already processed.
            # So we should NOT suppress class body here — children have already
            # placed their KEEP/PLACEHOLDER markers.
            # We only need to ensure sig + docstring are KEEP (they're initialized KEEP).
            continue

        # LOD 3: top-level (non-nested) functions → remove entirely
        if lod3 and not _is_nested(start) and "function" in sym_type:
            for ln in range(start, end + 1):
                if state[ln] == _STATE_KEEP:
                    state[ln] = _STATE_SKIP
            continue

        # Functions/methods: sig + docstring + placeholder + skip body
        sig_end = _find_sig_end(lines, start, end, language)
        doc_end = _find_docstring_end(lines, sig_end, end, language)
        body_start = doc_end + 1

        if body_start > end:
            continue  # No body to suppress

        placed = False
        for ln in range(body_start, end + 1):
            if state[ln] == _STATE_KEEP:
                if not placed:
                    state[ln] = _STATE_PLACEHOLDER
                    placed = True
                else:
                    state[ln] = _STATE_SKIP

    # Build output
    out: List[str] = []
    for ln in range(1, n + 1):
        s = state[ln]
        if s == _STATE_KEEP:
            out.append(lines[ln - 1])
        elif s == _STATE_PLACEHOLDER:
            out.append(placeholder_text)
        # _STATE_SKIP: omit line

    # Remove trailing blank lines
    while out and not out[-1].strip():
        out.pop()

    return "\n".join(out)


# ---------------------------------------------------------------------------
# LOD 2.5: signatures + docstrings, strip module-level constants
# ---------------------------------------------------------------------------


def _build_lod25(
    lines: List[str],
    symbols: List[Dict[str, Any]],
    language: str,
) -> str:
    """LOD 2.5: signatures + docstrings, strip module-level constants.

    Like LOD 2 but also removes lines outside any symbol span that are
    not imports. Addresses weak compression on constant-heavy files
    (e.g., lod_extractor.py achieves 1.3x at LOD 2 but should be ~3x).
    """
    n = len(lines)
    import_pat = _IMPORT_RE.get(language)

    # Phase 73.3: Expand single-line spans (same as _build_lod23)
    expanded_symbols = []
    for sym in symbols:
        span = sym.get("span") or {}
        start = span.get("start_line", 0)
        end = span.get("end_line", 0)
        if start and end and start == end and start <= n:
            inferred_end = _infer_body_end(lines, start, language)
            if inferred_end > start:
                sym = {**sym, "span": {**span, "end_line": inferred_end}}
        expanded_symbols.append(sym)

    # 1. Determine which lines fall inside a symbol span (1-indexed)
    in_symbol: set[int] = set()
    for sym in expanded_symbols:
        span = sym.get("span") or {}
        start = span.get("start_line", 0)
        end = span.get("end_line", 0)
        if start and end:
            for ln in range(start, end + 1):
                in_symbol.add(ln)

    # 2. Run LOD 2 to get the state array (KEEP / PLACEHOLDER / SKIP)
    placeholder_text = _PLACEHOLDER.get(language, _DEFAULT_PLACEHOLDER)
    state = [_STATE_KEEP] * (n + 2)  # 1-indexed

    syms = sorted(expanded_symbols, key=lambda s: (s["span"]["end_line"] - s["span"]["start_line"]))

    class_spans = [
        (s["span"]["start_line"], s["span"]["end_line"])
        for s in syms
        if (s.get("metadata") or {}).get("symbol_type") == "class"
    ]

    for sym in syms:
        span = sym.get("span") or {}
        start = span.get("start_line", 0)
        end = span.get("end_line", 0)
        if not start or not end or end < start:
            continue

        meta = sym.get("metadata") or {}
        sym_type = meta.get("symbol_type", "")

        if sym_type == "class":
            continue

        sig_end = _find_sig_end(lines, start, end, language)
        doc_end = _find_docstring_end(lines, sig_end, end, language)
        body_start = doc_end + 1
        if body_start > end:
            continue

        placed = False
        for ln in range(body_start, end + 1):
            if state[ln] == _STATE_KEEP:
                if not placed:
                    state[ln] = _STATE_PLACEHOLDER
                    placed = True
                else:
                    state[ln] = _STATE_SKIP

    # 3. Build output: only imports + symbol-interior lines
    out: List[str] = []

    # Collect import lines first (preserving order)
    for i, line in enumerate(lines, 1):
        if import_pat and import_pat.match(line):
            out.append(line)

    if out:
        out.append("")  # blank separator after imports

    # Add symbol lines using the LOD 2 state array
    for ln in range(1, n + 1):
        if ln not in in_symbol:
            continue  # skip module-level code (constants, bare assignments, etc.)
        s = state[ln]
        if s == _STATE_KEEP:
            out.append(lines[ln - 1])
        elif s == _STATE_PLACEHOLDER:
            out.append(placeholder_text)
        # _STATE_SKIP: omit

    # Remove trailing blank lines
    while out and not out[-1].strip():
        out.pop()

    return "\n".join(out)


# ---------------------------------------------------------------------------
# LOD 4: imports + symbol first lines
# ---------------------------------------------------------------------------

def _build_lod4(lines: List[str], symbols: List[Dict[str, Any]], language: str) -> str:
    import_pat = _IMPORT_RE.get(language)
    keep_lines: set = set()

    # Keep import lines
    for i, line in enumerate(lines, 1):
        if import_pat and import_pat.match(line):
            keep_lines.add(i)

    # Keep first line of each symbol
    for sym in symbols:
        span = sym.get("span") or {}
        start = span.get("start_line", 0)
        if start:
            keep_lines.add(start)

    out = []
    for i, line in enumerate(lines, 1):
        if i in keep_lines and line.strip():
            out.append(line.rstrip())

    return "\n".join(out)


# ---------------------------------------------------------------------------
# LOD 5: summary from augmentation data
# ---------------------------------------------------------------------------

def _build_lod5(
    file_path: str,
    symbols: List[Dict[str, Any]],
    augmented_data: Optional[Dict[str, Any]],
) -> str:
    from prep.core.ids import stable_file_node_id
    node_id = stable_file_node_id(file_path)
    lines: List[str] = [f"# {file_path}"]

    if augmented_data:
        entry = augmented_data.get(node_id) or {}
        summary = entry.get("summary", "")
        role = entry.get("role", "")
        if summary:
            lines.append(f"## {summary}")
        if role:
            lines.append(f"Role: {role}")

    # Exported symbol names
    exports = sorted({
        sym.get("name", "")
        for sym in symbols
        if sym.get("kind") == "symbol"
        and (sym.get("metadata") or {}).get("is_public", True)
        and sym.get("name")
    })
    if exports:
        lines.append("Exports: " + ", ".join(exports))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Default placeholder for unknown languages
# ---------------------------------------------------------------------------

_DEFAULT_PLACEHOLDER = "    ..."


# ---------------------------------------------------------------------------
# Main extractor class
# ---------------------------------------------------------------------------

def assign_lod(
    score: float,
    *,
    is_trace_expanded: bool = False,
    tier: Optional["ContextTier"] = None,
) -> int:
    """Map a search score to an LOD level.

    When *tier* is provided the thresholds come from the tier's
    ``lod_full``, ``lod_sig``, and ``lod_names`` properties.
    When *tier* is ``None`` Tier 2 defaults are used for backward
    compatibility:

      ≥ 0.50 → LOD 0 (full source — highly relevant)
      0.35–0.49 → LOD 2 (signatures + docstrings)
      0.20–0.34 → LOD 4 (names + imports)
      trace-expanded neighbors → LOD 4
      < 0.20 → LOD 5 (summary only)
    """
    if is_trace_expanded:
        return 4

    if tier is not None:
        t_full = tier.lod_full
        t_sig = tier.lod_sig
        t_names = tier.lod_names
    else:
        # Tier 2 defaults for backward compatibility
        t_full = 0.50
        t_sig = 0.35
        t_names = 0.20

    if score >= t_full:
        return 0
    if score >= t_sig:
        return 2
    if score >= t_names:
        return 4
    return 5


class LODExtractor:
    """
    Extract code at a specified Level of Detail using pre-computed trace data.

    No ML model required. Relies on symbol spans from trace_nodes.jsonl and
    optional LLM summaries from trace_augmented.jsonl.
    """

    def __init__(self, index_dir: Optional[Path] = None):
        self.index_dir = index_dir
        self._augmented_cache: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        file_path: str,
        lod: int,
        trace_nodes: List[Dict[str, Any]],
        repo_root: Path,
        *,
        augmented_data: Optional[Dict[str, Any]] = None,
    ) -> LODResult:
        """
        Extract file content at the requested LOD.

        Args:
            file_path:   Repo-relative POSIX path.
            lod:         Level of detail (0–5).
            trace_nodes: List of trace node dicts (all nodes; filtered internally).
            repo_root:   Absolute path to repo root.
            augmented_data: Optional {node_id: entry_dict} for LOD 5 summaries.

        Returns:
            LODResult with compressed content and metadata.
        """
        abs_path = repo_root / file_path
        try:
            source = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return LODResult(
                content="",
                lod=lod,
                input_chars=0,
                output_chars=0,
                error=str(e),
            )

        input_chars = len(source)
        language = self._detect_language(file_path)

        # Filter symbols for this file
        file_symbols = [
            n for n in trace_nodes
            if n.get("kind") == "symbol" and n.get("file_path") == file_path
        ]

        # Fall back to LOD 0 if no trace data and LOD > 0 requested
        if lod >= 2 and not file_symbols:
            content = source
            return LODResult(
                content=content,
                lod=0,
                input_chars=input_chars,
                output_chars=len(content),
                language=language,
                fallback=True,
            )

        if lod == 0:
            content = source
        elif lod == 1:
            content = _strip_comments(source, language or "")
        elif lod == 2:
            lines = source.splitlines()
            content = _build_lod23(lines, file_symbols, language or "")
        elif lod == 3:
            lines = source.splitlines()
            content = _build_lod23(lines, file_symbols, language or "", lod3=True)
        elif lod == 25:
            lines = source.splitlines()
            content = _build_lod25(lines, file_symbols, language or "")
        elif lod == 4:
            lines = source.splitlines()
            content = _build_lod4(lines, file_symbols, language or "")
        else:  # lod == 5
            content = _build_lod5(file_path, file_symbols, augmented_data)

        return LODResult(
            content=content,
            lod=lod,
            input_chars=input_chars,
            output_chars=len(content),
            language=language,
        )

    def load_augmented_data(self) -> Dict[str, Any]:
        """Load trace_augmented.jsonl from index_dir into a node_id-keyed dict."""
        if self._augmented_cache is not None:
            return self._augmented_cache
        if self.index_dir is None:
            return {}
        path = self.index_dir / "trace_augmented.jsonl"
        result: Dict[str, Any] = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            entry = json.loads(line)
                            nid = entry.get("node_id", "")
                            if nid:
                                result[nid] = entry
            except Exception as e:
                logger.warning("Failed to load trace_augmented.jsonl: %s", e)
        self._augmented_cache = result
        return result

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_language(file_path: str) -> Optional[str]:
        from prep.core.trace import _detect_language
        return _detect_language(file_path)

    @staticmethod
    def assign_lod(
        score: float,
        *,
        is_trace_expanded: bool = False,
        tier: Optional["ContextTier"] = None,
    ) -> int:
        """Delegate to the module-level :func:`assign_lod`."""
        return assign_lod(score, is_trace_expanded=is_trace_expanded, tier=tier)
