"""
Trace Augmenter for CoDRAG.

LLM-based augmentation of trace nodes with summaries, roles, and confidence scores.
Implements the Phase 1 pipeline (Steps 2-3) from LLM_TRACE_AUGMENTATION_RESEARCH.md.

Key design constraints:
- Each LLM call is self-contained (~2-4k tokens), never whole-repo context.
- Augmentation is stored as an overlay (trace_augmented.jsonl), never modifies trace_nodes.
- Confidence scores (0.0-1.0) on every generated attribute.
- Incremental: only re-augments nodes whose source file hash changed.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

AUGMENT_FORMAT_VERSION = "1.0"

# Symbol roles the fast model can assign
VALID_ROLES = frozenset({
    "entry_point", "handler", "utility", "model", "config",
    "test", "internal", "script", "api", "core", "ui",
    "documentation",
})

# Document types for markdown files
VALID_DOC_TYPES = frozenset({
    "research", "design_spec", "plan", "guide", "reference",
    "changelog", "readme", "todo", "status", "analysis", "overview",
})

VALID_DOC_STATUSES = frozenset({
    "active", "completed", "shelved", "superseded", "draft", "stale",
})

# Checkpoint interval: save augmentations every N items to avoid losing
# progress on mid-run crashes (LLM parse errors, OOM, timeouts, etc.).
_CHECKPOINT_INTERVAL_DEFAULT = 500


def _get_checkpoint_interval() -> int:
    """Read checkpoint_interval from global advanced_config, with fallback."""
    try:
        from codrag.services.settings_store import settings
        adv = settings.get("advanced_config")
        if adv and isinstance(adv, dict):
            return int(adv.get("checkpoint_interval", _CHECKPOINT_INTERVAL_DEFAULT))
    except Exception:
        pass
    return _CHECKPOINT_INTERVAL_DEFAULT


# ── Re-exports from llm_client.py (Refactor 2, GAP-1) ────────────────
# These were originally defined here.  Kept as re-exports so that
# existing ``from .augmenter import LLMClient`` etc. still work.
from .llm_client import (  # noqa: F401
    LLMClient,
    _get_llm_concurrency,
    _parse_confidence,
    _parse_json_response,
    _repair_truncated_json,
    _strip_think_tags,
)


@dataclass
class AugmentationEntry:
    """Single augmentation overlay for a trace node."""
    node_id: str
    summary: str
    role: str
    confidence: float
    augmented_at: str
    model: str
    version: int = 1
    validated: bool = False
    validated_at: Optional[str] = None
    validated_by: Optional[str] = None
    file_hash: Optional[str] = None  # hash of source when augmented, for staleness
    related_files: Optional[List[str]] = None  # LLM-hypothesized related files (feeds Pass 0.5)
    doc_type: Optional[str] = None  # for .md files: research, design_spec, plan, etc.
    doc_status: Optional[str] = None  # for .md files: active, completed, shelved, etc.

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "node_id": self.node_id,
            "summary": self.summary,
            "role": self.role,
            "confidence": round(self.confidence, 3),
            "augmented_at": self.augmented_at,
            "model": self.model,
            "version": self.version,
            "validated": self.validated,
        }
        if self.validated_at:
            d["validated_at"] = self.validated_at
        if self.validated_by:
            d["validated_by"] = self.validated_by
        if self.file_hash:
            d["file_hash"] = self.file_hash
        if self.related_files:
            d["related_files"] = self.related_files
        if self.doc_type:
            d["doc_type"] = self.doc_type
        if self.doc_status:
            d["doc_status"] = self.doc_status
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AugmentationEntry":
        return cls(
            node_id=d["node_id"],
            summary=d.get("summary", ""),
            role=d.get("role", "internal"),
            confidence=_parse_confidence(d.get("confidence"), 0.0),
            augmented_at=d.get("augmented_at", ""),
            model=d.get("model", "unknown"),
            version=int(d.get("version", 1)),
            validated=bool(d.get("validated", False)),
            validated_at=d.get("validated_at"),
            validated_by=d.get("validated_by"),
            file_hash=d.get("file_hash"),
            related_files=d.get("related_files"),
            doc_type=d.get("doc_type"),
            doc_status=d.get("doc_status"),
        )




@dataclass
class AugmentResult:
    """Result of an augmentation run."""
    total_nodes: int = 0
    augmented: int = 0
    skipped: int = 0
    failed: int = 0
    synthetic: int = 0  # entries created from path metadata (no LLM)
    tokens_used: int = 0
    duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)


# LLMClient class is now in llm_client.py (re-exported above)


# ── Prompt templates ──────────────────────────────────────────────────

SYMBOL_SUMMARY_SYSTEM = """You are a code analyst. You produce concise, accurate summaries of code symbols.
You MUST respond with valid JSON only. No markdown, no explanation outside the JSON."""

SYMBOL_SUMMARY_PROMPT = """Analyze this code symbol and provide a summary.

Symbol: {name} ({symbol_type})
File: {file_path}
Lines: {start_line}-{end_line}

Source code:
```
{source_code}
```

File imports: {imports}

Respond with this exact JSON format:
{{"summary": "1-2 sentence description of what this symbol does", "role": "{role_hint}", "confidence": 0.85}}

Where role is one of: entry_point, handler, utility, model, config, test, internal, script, api, core, ui

JSON response:"""

FILE_ROLE_SYSTEM = """You are a code analyst. You classify files by their role in a codebase.
You MUST respond with valid JSON only."""

FILE_ROLE_PROMPT = """Classify this file's role in the codebase.

File: {file_path}
Symbols defined: {symbol_names}
Imports: {imports}

{content_label}:
```
{head}
```

Respond with this exact JSON format:
{{"summary": "1 sentence file purpose", "role": "utility", "confidence": 0.85, "key_exports": ["symbol1", "symbol2"], "related_files": ["path/to/related.py"]}}

Where role is one of: api, core, model, utility, config, test, script, ui, documentation
related_files: list up to 5 files this file most likely relates to (by path)

JSON response:"""

DOC_ROLE_SYSTEM = """You are a documentation analyst. You classify documentation files by their type, status, and relationship to the codebase.
You MUST respond with valid JSON only."""

DOC_ROLE_PROMPT = """Analyze this documentation file.

File: {file_path}
Sections: {section_names}
File references found: {file_refs}
Link targets: {link_targets}

{content_label}:
```
{content}
```

Respond with this exact JSON format:
{{"summary": "1-2 sentence doc purpose", "role": "documentation", "confidence": 0.85, "doc_type": "design_spec", "doc_status": "active", "related_files": ["src/core/trace.py", "src/core/augmenter.py"]}}

Where doc_type is one of: research, design_spec, plan, guide, reference, changelog, readme, todo, status, analysis, overview
Where doc_status is one of: active, completed, shelved, superseded, draft, stale
related_files: list up to 5 code files this doc most closely describes or references

JSON response:"""


# _strip_think_tags, _parse_json_response, _repair_truncated_json
# are now in llm_client.py (re-exported above)


class TraceAugmenter:
    """
    Augments trace nodes with LLM-generated summaries, roles, and confidence scores.

    Architecture:
    - Reads trace_nodes.jsonl + trace_edges.jsonl (static trace).
    - Calls a fast/small LLM per symbol node.
    - Writes trace_augmented.jsonl (overlay, never modifies static trace).
    - Supports incremental runs via file hash comparison.
    """

    def __init__(
        self,
        index_dir: str | Path,
        repo_root: str | Path,
        llm_client: LLMClient,
        batch_profile: Optional["BatchProfile"] = None,
    ):
        self.index_dir = Path(index_dir).resolve()
        self.repo_root = Path(repo_root).resolve()
        self.llm = llm_client
        self._batch_profile = batch_profile

        self.augmented_path = self.index_dir / "trace_augmented.jsonl"
        self.augment_manifest_path = self.index_dir / "trace_augment_manifest.json"

    def load_existing(self) -> Dict[str, AugmentationEntry]:
        """Load existing augmentations from disk."""
        entries: Dict[str, AugmentationEntry] = {}
        if self.augmented_path.exists():
            try:
                with open(self.augmented_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            d = json.loads(line)
                            entry = AugmentationEntry.from_dict(d)
                            entries[entry.node_id] = entry
            except Exception as e:
                logger.warning("Failed to load existing augmentations: %s", e)
        return entries

    def load_trace_nodes(self) -> List[Dict[str, Any]]:
        """Load trace nodes from the static trace index."""
        nodes_path = self.index_dir / "trace_nodes.jsonl"
        nodes: List[Dict[str, Any]] = []
        if nodes_path.exists():
            with open(nodes_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        nodes.append(json.loads(line))
        return nodes

    def load_trace_edges(self) -> List[Dict[str, Any]]:
        """Load trace edges from the static trace index."""
        edges_path = self.index_dir / "trace_edges.jsonl"
        edges: List[Dict[str, Any]] = []
        if edges_path.exists():
            with open(edges_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        edges.append(json.loads(line))
        return edges

    def load_file_hashes(self) -> Dict[str, str]:
        """Load file hashes from the trace manifest for staleness detection."""
        manifest_path = self.index_dir / "trace_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                return manifest.get("file_hashes", {})
            except Exception:
                pass
        return {}

    def _needs_augmentation(
        self,
        node: Dict[str, Any],
        existing: Dict[str, AugmentationEntry],
        file_hashes: Dict[str, str],
    ) -> bool:
        """Check if a node needs (re-)augmentation."""
        node_id = node["id"]
        if node_id not in existing:
            return True
        entry = existing[node_id]
        # Check if source file changed since last augmentation
        file_path = node.get("file_path", "")
        if file_path and entry.file_hash:
            current_hash = file_hashes.get(file_path)
            if current_hash and current_hash != entry.file_hash:
                return True
        return False

    def _read_source_snippet(self, file_path: str, span: Optional[Dict[str, int]], max_chars: int = 2000) -> str:
        """Read source code for a symbol, limited to max_chars."""
        try:
            full_path = self.repo_root / file_path
            if not full_path.exists():
                return ""
            text = full_path.read_text(encoding="utf-8", errors="ignore")
            if span:
                lines = text.splitlines()
                start = max(0, span.get("start_line", 1) - 1)
                end = min(len(lines), span.get("end_line", len(lines)))
                snippet = "\n".join(lines[start:end])
            else:
                snippet = text
            return snippet[:max_chars]
        except Exception:
            return ""

    def _get_file_head(self, file_path: str, max_lines: int = 30) -> str:
        """Read the first N lines of a file."""
        try:
            full_path = self.repo_root / file_path
            if not full_path.exists():
                return ""
            text = full_path.read_text(encoding="utf-8", errors="ignore")
            lines = text.splitlines()[:max_lines]
            return "\n".join(lines)
        except Exception:
            return ""

    def _get_strategic_excerpt(
        self,
        file_path: str,
        section_nodes: List[Dict[str, Any]],
        head_lines: int = 300,
        section_lines: int = 50,
        max_total: int = 1000,
    ) -> str:
        """Read head + top-ranked sections for strategic LLM input.

        Uses Rust-extracted section metadata (ref_count) to select the
        most important sections from the file, rather than blindly reading
        the first N lines.
        """
        try:
            full_path = self.repo_root / file_path
            if not full_path.exists():
                return ""
            text = full_path.read_text(encoding="utf-8", errors="ignore")
            lines = text.splitlines()
        except Exception:
            return ""

        # Always include the head
        head = lines[:head_lines]
        parts: List[tuple] = [("head", head)]
        budget = max_total - len(head)

        # Rank sections by importance (ref_count descending, then by depth)
        ranked = sorted(
            section_nodes,
            key=lambda s: (
                s.get("metadata", {}).get("ref_count", 0),
                s.get("metadata", {}).get("header_depth", 6),
            ),
            reverse=True,
        )

        for sec in ranked:
            if budget <= 0:
                break
            span = sec.get("span")
            if not span:
                continue
            start = span.get("start_line", 1) - 1  # 0-indexed
            if start < head_lines:
                continue  # already covered by head
            end = min(start + section_lines, span.get("end_line", start + section_lines))
            end = min(end, len(lines))
            chunk = lines[start:end]
            parts.append((sec.get("name", "section"), chunk))
            budget -= len(chunk)

        # Format with section markers so LLM knows these are excerpts
        output: List[str] = []
        for name, chunk in parts:
            if name != "head":
                output.append(f"--- [Section: {name}] ---")
            output.extend(chunk)
        return "\n".join(output)

    def _get_file_imports(self, file_path: str, edges: List[Dict[str, Any]], nodes: Dict[str, Dict[str, Any]]) -> str:
        """Get import statements for a file from trace edges."""
        file_node_id = None
        for nid, n in nodes.items():
            if n.get("file_path") == file_path and n.get("kind") == "file":
                file_node_id = nid
                break
        if not file_node_id:
            return ""
        imports = []
        for e in edges:
            if e.get("source") == file_node_id and e.get("kind") == "imports":
                imp = e.get("metadata", {}).get("import", "")
                if imp:
                    imports.append(imp)
        return ", ".join(imports[:20])

    # ── Synthetic fallback entries ─────────────────────────────────
    #
    # When LLM augmentation fails for any reason (network, parse, empty
    # source), we still need an augmentation entry so that the knowledge
    # index covers every traced file.  These helpers derive a useful
    # summary from file metadata alone — no LLM call needed.

    @staticmethod
    def _infer_role_from_path(file_path: str) -> str:
        """Heuristic role from file path segments."""
        fp = file_path.lower()
        if "test" in fp:
            return "test"
        if "config" in fp or fp.endswith((".json", ".toml", ".yaml", ".yml", ".ini", ".env")):
            return "config"
        if "doc" in fp or fp.endswith((".md", ".rst", ".txt")):
            return "documentation"
        if any(seg in fp for seg in ("api/", "routes/", "router", "endpoint")):
            return "api"
        if any(seg in fp for seg in ("ui/", "component", "view", "page")):
            return "ui"
        if any(seg in fp for seg in ("script", "bin/", "cli")):
            return "script"
        if "model" in fp:
            return "model"
        return "internal"

    @staticmethod
    def _lang_label(file_path: str, language: str = "") -> str:
        """Human-readable language label from path or language field."""
        if language and language != "unknown":
            return language.capitalize()
        ext_map = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".tsx": "TypeScript React", ".jsx": "JavaScript React",
            ".rs": "Rust", ".go": "Go", ".rb": "Ruby", ".java": "Java",
            ".swift": "Swift", ".md": "Markdown", ".json": "JSON",
            ".toml": "TOML", ".yaml": "YAML", ".yml": "YAML",
            ".css": "CSS", ".scss": "SCSS", ".html": "HTML",
            ".sh": "Shell", ".sql": "SQL",
        }
        for ext, label in ext_map.items():
            if file_path.endswith(ext):
                return label
        return "source"

    def _synthetic_entry(
        self,
        node: Dict[str, Any],
        file_hashes: Dict[str, str],
        reason: str = "llm_failure",
    ) -> AugmentationEntry:
        """Create a synthetic augmentation entry from file metadata.

        The summary is derived from the file path structure rather than
        an LLM call.  This guarantees every traced node gets an entry
        in trace_augmented.jsonl with a non-empty summary.
        """
        file_path = node.get("file_path", "")
        language = node.get("language", "")
        lang_label = self._lang_label(file_path, language)
        role = self._infer_role_from_path(file_path)
        kind = node.get("kind", "file")

        if kind == "symbol":
            name = node.get("name", os.path.basename(file_path))
            sym_type = node.get("metadata", {}).get("symbol_type", "symbol")
            summary = f"{lang_label} {sym_type} '{name}' in {file_path}"
        else:
            summary = f"{lang_label} {role} file at {file_path}"

        return AugmentationEntry(
            node_id=node["id"],
            summary=summary,
            role=role,
            confidence=0.1,  # low confidence signals synthetic origin
            augmented_at=datetime.now(timezone.utc).isoformat(),
            model=f"synthetic:{reason}",
            file_hash=file_hashes.get(file_path),
        )

    def _llm_generate_with_retry(
        self,
        prompt: str,
        system: Optional[str] = None,
        num_predict: int = 2048,
        max_retries: int = 2,
        label: str = "",
    ) -> Tuple[str, int]:
        """Call LLM with retry on transient failures.

        Retries up to ``max_retries`` times with exponential back-off
        (1s, 2s).  Returns (text, tokens) on success or raises the
        last exception.
        """
        last_err: Optional[Exception] = None
        for attempt in range(1 + max_retries):
            try:
                return self.llm.generate(prompt, system=system, num_predict=num_predict)
            except Exception as e:
                last_err = e
                if attempt < max_retries:
                    wait = (attempt + 1)  # 1s, 2s
                    logger.info(
                        "LLM retry %d/%d for %s after error: %s (waiting %ds)",
                        attempt + 1, max_retries, label, e, wait,
                    )
                    time.sleep(wait)
        raise last_err  # type: ignore[misc]

    def augment_symbol(
        self,
        node: Dict[str, Any],
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
        file_hashes: Dict[str, str],
    ) -> Optional[AugmentationEntry]:
        """Augment a single symbol node with LLM summary."""
        file_path = node.get("file_path", "")
        span = node.get("span")
        source = self._read_source_snippet(file_path, span)
        if not source:
            logger.debug("Empty source for symbol %s — using synthetic entry", node.get("name"))
            return self._synthetic_entry(node, file_hashes, reason="empty_source")

        imports = self._get_file_imports(file_path, edges, nodes_by_id)
        symbol_type = node.get("metadata", {}).get("symbol_type", "function")
        role_hint = "utility"  # default hint
        if "test" in file_path.lower() or "test" in node.get("name", "").lower():
            role_hint = "test"

        prompt = SYMBOL_SUMMARY_PROMPT.format(
            name=node.get("name", ""),
            symbol_type=symbol_type,
            file_path=file_path,
            start_line=span.get("start_line", 0) if span else 0,
            end_line=span.get("end_line", 0) if span else 0,
            source_code=source,
            imports=imports or "(none)",
            role_hint=role_hint,
        )

        try:
            text, tokens = self._llm_generate_with_retry(
                prompt, system=SYMBOL_SUMMARY_SYSTEM,
                label=node.get("name", "?"),
            )
        except Exception as e:
            logger.warning("LLM call failed for %s after retries: %s", node.get("name"), e)
            return self._synthetic_entry(node, file_hashes, reason="llm_failure")

        parsed = _parse_json_response(text)
        if parsed is None:
            logger.warning("Failed to parse LLM response for %s — raw: %.200s", node.get("name"), text)
            return self._synthetic_entry(node, file_hashes, reason="parse_failure")

        role = parsed.get("role", "internal")
        if role not in VALID_ROLES:
            role = "internal"

        confidence = _parse_confidence(parsed.get("confidence"), 0.5)

        summary = str(parsed.get("summary", "")).strip()[:500]
        if not summary:
            # LLM returned valid JSON but empty summary — derive from metadata
            name = node.get("name", os.path.basename(file_path))
            sym_type = node.get("metadata", {}).get("symbol_type", "symbol")
            summary = f"{sym_type.capitalize()} '{name}' in {file_path}"

        return AugmentationEntry(
            node_id=node["id"],
            summary=summary,
            role=role,
            confidence=confidence,
            augmented_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model,
            file_hash=file_hashes.get(file_path),
        )

    # Paths containing these segments are build output / not worth augmenting
    _SKIP_PATH_SEGMENTS = frozenset({
        "node_modules", ".next", "out/_next", "dist/", "build/",
        "__pycache__", ".tox", ".eggs", "vendor/bundle",
    })

    def _should_skip_file(self, file_path: str) -> bool:
        """Return True if this file is likely build output or minified."""
        fp_lower = file_path.lower()
        for seg in self._SKIP_PATH_SEGMENTS:
            if seg in fp_lower:
                return True
        # Skip minified JS/CSS (very long lines, no useful structure)
        if fp_lower.endswith((".min.js", ".min.css")):
            return True
        # Heuristic: filenames with content hashes (e.g. chunk-abc123.js)
        base = os.path.basename(fp_lower)
        if base.count("-") >= 1 and base.endswith(".js") and len(base) > 20:
            return True
        return False

    def _get_section_nodes_for_file(
        self,
        node_id: str,
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Get section nodes contained by a file node."""
        sections = []
        for e in edges:
            if e.get("source") == node_id and e.get("kind") == "contains":
                target = nodes_by_id.get(e["target"])
                if target and target.get("kind") == "section":
                    sections.append(target)
        return sections

    def _get_reference_targets(
        self,
        node_id: str,
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        """Get file paths referenced by this node via 'references' edges."""
        targets = []
        for e in edges:
            if e.get("source") == node_id and e.get("kind") == "references":
                target = nodes_by_id.get(e["target"])
                if target:
                    targets.append(target.get("file_path", e["target"]))
        return targets

    def _get_link_targets(
        self,
        node_id: str,
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        """Get file paths linked by this node via 'links_to' edges."""
        targets = []
        for e in edges:
            if e.get("source") == node_id and e.get("kind") == "links_to":
                target = nodes_by_id.get(e["target"])
                if target:
                    targets.append(target.get("file_path", e["target"]))
        return targets

    def augment_file(
        self,
        node: Dict[str, Any],
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
        file_hashes: Dict[str, str],
    ) -> Optional[AugmentationEntry]:
        """Augment a file node with LLM role classification.

        For markdown files: uses doc-specific prompt with strategic excerpts
        (head + top-ranked sections by ref_count).
        For code files: uses standard prompt with file head.
        """
        file_path = node.get("file_path", "")
        if self._should_skip_file(file_path):
            # Skip build output files entirely
            logger.debug("Skipping build output file %s", file_path)
            return None

        is_markdown = node.get("language") == "markdown" or file_path.endswith((".md", ".markdown"))

        if is_markdown:
            return self._augment_markdown_file(node, edges, nodes_by_id, file_hashes)
        else:
            return self._augment_code_file(node, edges, nodes_by_id, file_hashes)

    def _augment_code_file(
        self,
        node: Dict[str, Any],
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
        file_hashes: Dict[str, str],
    ) -> Optional[AugmentationEntry]:
        """Augment a code file node with LLM role classification."""
        file_path = node.get("file_path", "")
        head = self._get_file_head(file_path)
        if not head:
            # Skip empty files (e.g. __init__.py) entirely to avoid noise
            logger.debug("Empty file head for %s — skipping augmentation", file_path)
            return None

        # Find symbols in this file
        symbol_names = []
        for e in edges:
            if e.get("source") == node["id"] and e.get("kind") == "contains":
                target = nodes_by_id.get(e["target"])
                if target and target.get("kind") == "symbol":
                    symbol_names.append(target.get("name", ""))

        imports = self._get_file_imports(file_path, edges, nodes_by_id)

        prompt = FILE_ROLE_PROMPT.format(
            file_path=file_path,
            symbol_names=", ".join(symbol_names[:30]) or "(none)",
            imports=imports or "(none)",
            content_label="First 30 lines",
            head=head,
        )

        try:
            text, tokens = self._llm_generate_with_retry(
                prompt, system=FILE_ROLE_SYSTEM,
                label=file_path,
            )
        except Exception as e:
            logger.warning("LLM call failed for file %s after retries: %s", file_path, e)
            return self._synthetic_entry(node, file_hashes, reason="llm_failure")

        parsed = _parse_json_response(text)
        if parsed is None:
            logger.warning("Failed to parse LLM response for file %s — raw: %.200s", file_path, text)
            return self._synthetic_entry(node, file_hashes, reason="parse_failure")

        role = parsed.get("role", "utility")
        if role not in VALID_ROLES:
            role = "utility"

        confidence = _parse_confidence(parsed.get("confidence"), 0.5)

        related = parsed.get("related_files")
        if isinstance(related, list):
            related = [str(r) for r in related[:5]]
        else:
            related = None

        summary = str(parsed.get("summary", "")).strip()[:500]
        if not summary:
            summary = f"Source file at {file_path}"

        return AugmentationEntry(
            node_id=node["id"],
            summary=summary,
            role=role,
            confidence=confidence,
            augmented_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model,
            file_hash=file_hashes.get(file_path),
            related_files=related,
        )

    def _augment_markdown_file(
        self,
        node: Dict[str, Any],
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
        file_hashes: Dict[str, str],
    ) -> Optional[AugmentationEntry]:
        """Augment a markdown file with doc-specific prompt and strategic excerpts."""
        file_path = node.get("file_path", "")
        node_id = node["id"]

        # Get section nodes for strategic excerpt ranking
        section_nodes = self._get_section_nodes_for_file(node_id, edges, nodes_by_id)
        section_names = [s.get("name", "") for s in section_nodes]

        # Get Rust-extracted cross-references
        file_refs = self._get_reference_targets(node_id, edges, nodes_by_id)
        link_targets = self._get_link_targets(node_id, edges, nodes_by_id)

        # Strategic excerpt: head + top-ranked sections
        if section_nodes:
            content = self._get_strategic_excerpt(file_path, section_nodes)
            content_label = f"Strategic excerpt ({node.get('metadata', {}).get('line_count', '?')} total lines)"
        else:
            content = self._get_file_head(file_path, max_lines=100)
            content_label = "First 100 lines"

        if not content:
            # Skip empty docs entirely
            logger.debug("Empty content for doc %s — skipping augmentation", file_path)
            return None

        prompt = DOC_ROLE_PROMPT.format(
            file_path=file_path,
            section_names=", ".join(section_names[:20]) or "(none)",
            file_refs=", ".join(file_refs[:15]) or "(none)",
            link_targets=", ".join(link_targets[:15]) or "(none)",
            content_label=content_label,
            content=content,
        )

        try:
            text, tokens = self._llm_generate_with_retry(
                prompt, system=DOC_ROLE_SYSTEM,
                label=file_path,
            )
        except Exception as e:
            logger.warning("LLM call failed for doc %s after retries: %s", file_path, e)
            return self._synthetic_entry(node, file_hashes, reason="llm_failure")

        parsed = _parse_json_response(text)
        if parsed is None:
            logger.warning("Failed to parse LLM response for doc %s — raw: %.200s", file_path, text)
            return self._synthetic_entry(node, file_hashes, reason="parse_failure")

        role = parsed.get("role", "documentation")
        if role not in VALID_ROLES:
            role = "documentation"

        confidence = _parse_confidence(parsed.get("confidence"), 0.5)

        doc_type = parsed.get("doc_type")
        if doc_type not in VALID_DOC_TYPES:
            doc_type = None

        doc_status = parsed.get("doc_status")
        if doc_status not in VALID_DOC_STATUSES:
            doc_status = None

        related = parsed.get("related_files")
        if isinstance(related, list):
            related = [str(r) for r in related[:5]]
        else:
            related = None

        summary = str(parsed.get("summary", "")).strip()[:500]
        if not summary:
            summary = f"Documentation file at {file_path}"

        return AugmentationEntry(
            node_id=node["id"],
            summary=summary,
            role=role,
            confidence=confidence,
            augmented_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model,
            file_hash=file_hashes.get(file_path),
            related_files=related,
            doc_type=doc_type,
            doc_status=doc_status,
        )

    def _augment_files_batched(
        self,
        file_nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
        file_hashes: Dict[str, str],
        augmented: Dict[str, "AugmentationEntry"],
        result: "AugmentResult",
        done: int,
        total_work: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> int:
        """Process file nodes in batches using batched prompts.

        Returns the updated 'done' counter.
        """
        from .batch_profiles import BatchStage
        from .batch_prompts import (
            BATCHED_FILE_SYSTEM,
            BATCHED_DOC_SYSTEM,
            build_batched_file_prompt,
            build_batched_doc_prompt,
            get_structured_schema,
        )
        from .batch_strategy import BatchedResponseParser

        batch_size = self._batch_profile.batch_size(BatchStage.CATALOGUE_FILE)
        logger.info(
            "Batched file augmentation: %d files, batch_size=%d (%s profile)",
            len(file_nodes), batch_size, self._batch_profile.name.value,
        )

        file_schema = get_structured_schema("catalogue_file")
        doc_schema = get_structured_schema("epistemic_doc") # doc aug matches epistemic doc shape closely enough

        # Split into code files and doc files
        code_files = []
        doc_files = []
        for node in file_nodes:
            fp = node.get("file_path", "")
            lang = node.get("language", "")
            is_md = lang == "markdown" or fp.endswith((".md", ".markdown"))
            if is_md:
                doc_files.append(node)
            else:
                code_files.append(node)

        # Process code files in batches (concurrent batch dispatch for cloud APIs)
        _BYOK_CONCURRENCY = 3  # Max concurrent batched API calls

        # Pre-build all code batch payloads
        code_batches = []
        for batch_start in range(0, len(code_files), batch_size):
            batch = code_files[batch_start:batch_start + batch_size]
            items = []
            for node in batch:
                fp = node.get("file_path", "")
                nid = node["id"]
                symbol_names = ", ".join(
                    n.get("name", "")
                    for n in nodes_by_id.values()
                    if n.get("kind") == "symbol"
                    and n.get("file_path") == fp
                )[:500]
                imports = self._get_file_imports(fp, edges, nodes_by_id)
                head = self._get_file_head(fp, max_lines=30)
                items.append({
                    "file_path": fp,
                    "symbol_names": symbol_names,
                    "imports": imports,
                    "content_label": "First 30 lines",
                    "head": head,
                    "_node": node,
                    "_node_id": nid,
                })
            code_batches.append(items)

        def _call_code_batch(items):
            prompt = build_batched_file_prompt(items)
            try:
                text, tokens = self.llm.generate(
                    prompt, system=BATCHED_FILE_SYSTEM, num_predict=batch_size * 200,
                    response_schema=file_schema,
                )
                return BatchedResponseParser.parse(text, expected_count=len(items))
            except Exception as e:
                logger.warning("Batched file augmentation failed for batch of %d: %s", len(items), e)
                return []

        # Dispatch batches concurrently
        with ThreadPoolExecutor(max_workers=min(_BYOK_CONCURRENCY, len(code_batches) or 1)) as pool:
            future_to_items = {
                pool.submit(_call_code_batch, items): items
                for items in code_batches
            }
            for future in as_completed(future_to_items):
                items = future_to_items[future]
                try:
                    results_list = future.result()
                except Exception as e:
                    logger.warning("Code batch future failed: %s", e)
                    results_list = []

                for idx, item in enumerate(items):
                    node = item["_node"]
                    nid = item["_node_id"]
                    fp = item["file_path"]
                    parsed = results_list[idx] if idx < len(results_list) else None

                    if parsed:
                        entry = AugmentationEntry(
                            node_id=nid,
                            summary=str(parsed.get("summary", ""))[:500],
                            role=parsed.get("role", self._infer_role_from_path(fp)),
                            confidence=_parse_confidence(parsed.get("confidence"), 0.7),
                            augmented_at=datetime.now(timezone.utc).isoformat(),
                            model=self.llm.model,
                            file_hash=file_hashes.get(fp),
                            related_files=parsed.get("related_files", [])[:5],
                        )
                        augmented[nid] = entry
                        result.augmented += 1
                    else:
                        entry = self._synthetic_entry(node, nodes_by_id, edges, file_hashes)
                        if entry:
                            augmented[nid] = entry
                            result.synthetic += 1
                        else:
                            result.failed += 1
                    done += 1

                if progress_callback:
                    progress_callback("augment_files", done, total_work)

                logger.info(
                    "Batched file augmentation: %d/%d done (batch of %d → %d parsed)",
                    done, total_work, len(items), len(results_list),
                )

        # Process doc files in batches (smaller batch size, concurrent dispatch)
        doc_batch_size = max(1, batch_size // 5)  # Docs are bigger

        doc_batches = []
        for batch_start in range(0, len(doc_files), doc_batch_size):
            batch = doc_files[batch_start:batch_start + doc_batch_size]
            items = []
            for node in batch:
                fp = node.get("file_path", "")
                nid = node["id"]
                section_nodes = [
                    nodes_by_id[e["target"]]
                    for e in edges
                    if e.get("source") == nid
                    and e.get("kind") == "contains"
                    and e.get("target", "") in nodes_by_id
                    and nodes_by_id[e["target"]].get("kind") == "section"
                ]
                section_names = [s.get("name", "") for s in section_nodes]
                content = self._get_strategic_excerpt(fp, section_nodes)
                file_refs = ", ".join(
                    e.get("target", "").replace("file:", "")
                    for e in edges
                    if e.get("source") == nid and e.get("kind") == "references"
                )[:300]
                link_targets = ", ".join(
                    e.get("target", "").replace("file:", "")
                    for e in edges
                    if e.get("source") == nid and e.get("kind") == "links_to"
                )[:300]
                items.append({
                    "file_path": fp,
                    "section_names": ", ".join(section_names[:20]) or "(none)",
                    "file_refs": file_refs or "(none)",
                    "link_targets": link_targets or "(none)",
                    "content_label": "Content excerpt",
                    "content": content,
                    "_node": node,
                    "_node_id": nid,
                })
            doc_batches.append(items)

        def _call_doc_batch(items):
            prompt = build_batched_doc_prompt(items)
            try:
                text, tokens = self.llm.generate(
                    prompt, system=BATCHED_DOC_SYSTEM, num_predict=len(items) * 200,
                    response_schema=doc_schema,
                )
                return BatchedResponseParser.parse(text, expected_count=len(items))
            except Exception as e:
                logger.warning("Batched doc augmentation failed for batch of %d: %s", len(items), e)
                return []

        with ThreadPoolExecutor(max_workers=min(_BYOK_CONCURRENCY, len(doc_batches) or 1)) as pool:
            future_to_items = {
                pool.submit(_call_doc_batch, items): items
                for items in doc_batches
            }
            for future in as_completed(future_to_items):
                items = future_to_items[future]
                try:
                    results_list = future.result()
                except Exception as e:
                    logger.warning("Doc batch future failed: %s", e)
                    results_list = []

                for idx, item in enumerate(items):
                    node = item["_node"]
                    nid = item["_node_id"]
                    fp = item["file_path"]
                    parsed = results_list[idx] if idx < len(results_list) else None

                    if parsed:
                        entry = AugmentationEntry(
                            node_id=nid,
                            summary=str(parsed.get("summary", ""))[:500],
                            role="documentation",
                            confidence=_parse_confidence(parsed.get("confidence"), 0.7),
                            augmented_at=datetime.now(timezone.utc).isoformat(),
                            model=self.llm.model,
                            file_hash=file_hashes.get(fp),
                            related_files=parsed.get("related_files", [])[:5],
                            doc_type=parsed.get("doc_type"),
                            doc_status=parsed.get("doc_status"),
                        )
                        augmented[nid] = entry
                        result.augmented += 1
                    else:
                        entry = self._synthetic_entry(node, nodes_by_id, edges, file_hashes)
                        if entry:
                            augmented[nid] = entry
                            result.synthetic += 1
                        else:
                            result.failed += 1
                    done += 1

                if progress_callback:
                    progress_callback("augment_files", done, total_work)

        return done

    def run(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        max_items: Optional[int] = None,
        cancel_token: Optional[Any] = None,
    ) -> AugmentResult:
        """
        Run augmentation on all trace nodes that need it.

        Steps:
        1. Load static trace + existing augmentations.
        2. Identify nodes needing augmentation (new or stale).
        3. Augment symbol nodes first, then file nodes.
        4. Write overlay atomically.
        """
        start = time.monotonic()
        result = AugmentResult()

        nodes = self.load_trace_nodes()
        edges = self.load_trace_edges()
        file_hashes = self.load_file_hashes()
        existing = self.load_existing()

        if not nodes:
            logger.info("No trace nodes found, skipping augmentation")
            return result

        nodes_by_id = {n["id"]: n for n in nodes}
        result.total_nodes = len(nodes)

        # Separate symbol and file nodes
        symbol_nodes = [n for n in nodes if n.get("kind") == "symbol"]
        file_nodes = [n for n in nodes if n.get("kind") == "file"]

        # Filter to nodes needing augmentation
        to_augment_symbols = [n for n in symbol_nodes if self._needs_augmentation(n, existing, file_hashes)]
        to_augment_files = [n for n in file_nodes if self._needs_augmentation(n, existing, file_hashes)]

        total_work = len(to_augment_symbols) + len(to_augment_files)
        if max_items and total_work > max_items:
            to_augment_symbols = to_augment_symbols[:max_items]
            remaining = max_items - len(to_augment_symbols)
            to_augment_files = to_augment_files[:max(0, remaining)]
            total_work = len(to_augment_symbols) + len(to_augment_files)

        logger.info(
            "Augmentation: %d symbols + %d files to process (%d existing, %d total nodes)",
            len(to_augment_symbols), len(to_augment_files), len(existing), len(nodes),
        )
        logger.info(
            "LLM: model=%s endpoint=%s provider=%s timeout=%.0fs",
            self.llm.model, self.llm.endpoint_url, self.llm.provider, self.llm.timeout,
        )

        # Pre-flight: test LLM with a tiny prompt to catch model-loading
        # issues or missing models before committing to 2000+ sequential calls.
        logger.info("Pre-flight LLM test...")
        try:
            preflight_start = time.monotonic()
            test_text, _ = self.llm.generate('Respond with: {"ok":true}', num_predict=20)
            preflight_elapsed = time.monotonic() - preflight_start
            logger.info("Pre-flight OK (%.1fs): %.100s", preflight_elapsed, test_text.strip())
        except Exception as e:
            logger.error("Pre-flight LLM test FAILED: %s", e)
            raise RuntimeError(
                f"LLM pre-flight failed — model '{self.llm.model}' at {self.llm.endpoint_url} "
                f"is not responding. Check that the model is pulled and Ollama is running. Error: {e}"
            ) from e

        # Read checkpoint interval from global settings (once per run)
        checkpoint_interval = _get_checkpoint_interval()

        # Start with existing entries (will be updated/overwritten)
        augmented = dict(existing)
        done = 0
        pass_start = time.monotonic()

        # Pass 1: Symbol augmentation
        concurrency = _get_llm_concurrency("fast")
        if to_augment_symbols:
            logger.info("Pass 1: augmenting %d symbols (concurrency=%d)...", len(to_augment_symbols), concurrency)

        if concurrency <= 1 or not to_augment_symbols:
            # Sequential symbol augmentation
            for node in to_augment_symbols:
                # Cooperative cancellation check
                if cancel_token and cancel_token.is_cancelled:
                    logger.info("Augmentation paused/cancelled at %d/%d — flushing partial results", done, total_work)
                    self._write_augmentations(augmented)
                    cancel_token.raise_if_cancelled()

                if progress_callback:
                    progress_callback("augment_symbols", done, total_work)

                item_start = time.monotonic()
                entry = self.augment_symbol(node, edges, nodes_by_id, file_hashes)
                item_elapsed = time.monotonic() - item_start
                if entry:
                    augmented[entry.node_id] = entry
                    if entry.model.startswith("synthetic:"):
                        result.synthetic += 1
                    else:
                        result.augmented += 1
                else:
                    result.failed += 1
                done += 1

                if done == 1:
                    logger.info(
                        "First LLM call %s (%.1fs) — node: %s",
                        "succeeded" if entry else "FAILED", item_elapsed, node.get("id", "?"),
                    )
                elif done % 25 == 0:
                    elapsed = time.monotonic() - pass_start
                    avg = elapsed / done if done else 0
                    eta = avg * (total_work - done)
                    logger.info(
                        "Augmentation progress: %d/%d (%.0f%%) — avg %.1fs/item, ETA %.0fs",
                        done, total_work, done / total_work * 100, avg, eta,
                    )

                # Periodic checkpoint to avoid losing progress on crash
                if done % checkpoint_interval == 0:
                    self._write_augmentations(augmented)
                    logger.info("Checkpoint saved at %d/%d items", done, total_work)
        else:
            # Concurrent symbol augmentation via thread pool
            lock = threading.Lock()
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = {
                    pool.submit(self.augment_symbol, node, edges, nodes_by_id, file_hashes): node
                    for node in to_augment_symbols
                }
                for future in as_completed(futures):
                    try:
                        entry = future.result()
                    except Exception as e:
                        logger.warning("Symbol augmentation thread failed: %s", e)
                        entry = None
                    with lock:
                        if entry:
                            augmented[entry.node_id] = entry
                            if entry.model.startswith("synthetic:"):
                                result.synthetic += 1
                            else:
                                result.augmented += 1
                        else:
                            result.failed += 1
                        done += 1
                        if progress_callback:
                            progress_callback("augment_symbols", done, total_work)
                        if done % checkpoint_interval == 0:
                            self._write_augmentations(augmented)
                            logger.info("Checkpoint saved at %d/%d items", done, total_work)
                        if done % 25 == 0:
                            elapsed = time.monotonic() - pass_start
                            avg = elapsed / done if done else 0
                            eta = avg * (total_work - done)
                            logger.info(
                                "Augmentation progress: %d/%d (%.0f%%) — avg %.1fs/item, ETA %.0fs",
                                done, total_work, done / total_work * 100, avg, eta,
                            )

        # Pass 2: File augmentation
        # Use batched path for BYOK models with batch_size > 1
        use_batching = (
            self._batch_profile is not None
            and self._batch_profile.name.value != "off"
        )

        if use_batching and to_augment_files:
            logger.info("Pass 2: BATCHED file augmentation (%d files, profile=%s)",
                        len(to_augment_files), self._batch_profile.name.value)
            done = self._augment_files_batched(
                to_augment_files, edges, nodes_by_id, file_hashes,
                augmented, result, done, total_work, progress_callback,
            )
        elif to_augment_files:
            # Individual file augmentation (local models / batching off)
            concurrency = _get_llm_concurrency("fast")
            logger.info("Pass 2: augmenting %d files (concurrency=%d)...", len(to_augment_files), concurrency)

            if concurrency <= 1:
                # Sequential (default)
                for node in to_augment_files:
                    # Cooperative cancellation check
                    if cancel_token and cancel_token.is_cancelled:
                        logger.info("Augmentation paused/cancelled at %d/%d — flushing partial results", done, total_work)
                        self._write_augmentations(augmented)
                        cancel_token.raise_if_cancelled()

                    if progress_callback:
                        progress_callback("augment_files", done, total_work)

                    item_start = time.monotonic()
                    entry = self.augment_file(node, edges, nodes_by_id, file_hashes)
                    item_elapsed = time.monotonic() - item_start
                    if entry:
                        augmented[entry.node_id] = entry
                        if entry.model.startswith("synthetic:"):
                            result.synthetic += 1
                        else:
                            result.augmented += 1
                    else:
                        result.failed += 1
                    done += 1

                    if done % 25 == 0:
                        elapsed = time.monotonic() - pass_start
                        avg = elapsed / done if done else 0
                        eta = avg * (total_work - done)
                        logger.info(
                            "Augmentation progress: %d/%d (%.0f%%) — avg %.1fs/item, ETA %.0fs",
                            done, total_work, done / total_work * 100, avg, eta,
                        )

                    # Periodic checkpoint to avoid losing progress on crash
                    if done % checkpoint_interval == 0:
                        self._write_augmentations(augmented)
                        logger.info("Checkpoint saved at %d/%d items", done, total_work)
            else:
                # Concurrent LLM calls via thread pool
                lock = threading.Lock()
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    futures = {
                        pool.submit(self.augment_file, node, edges, nodes_by_id, file_hashes): node
                        for node in to_augment_files
                    }
                    for future in as_completed(futures):
                        entry = future.result()
                        with lock:
                            if entry:
                                augmented[entry.node_id] = entry
                                if entry.model.startswith("synthetic:"):
                                    result.synthetic += 1
                                else:
                                    result.augmented += 1
                            else:
                                result.failed += 1
                            done += 1
                            if progress_callback:
                                progress_callback("augment_files", done, total_work)
                            # Periodic checkpoint to avoid losing progress on crash
                            if done % checkpoint_interval == 0:
                                self._write_augmentations(augmented)
                                logger.info("Checkpoint saved at %d/%d items", done, total_work)
                            if done % 25 == 0:
                                elapsed = time.monotonic() - pass_start
                                avg = elapsed / done if done else 0
                                eta = avg * (total_work - done)
                                logger.info(
                                    "Augmentation progress: %d/%d (%.0f%%) — avg %.1fs/item, ETA %.0fs",
                                    done, total_work, done / total_work * 100, avg, eta,
                                )

        result.skipped = result.total_nodes - total_work

        # Write atomically
        self._write_augmentations(augmented)
        self._write_manifest(result, augmented)

        result.duration_ms = (time.monotonic() - start) * 1000

        if progress_callback:
            progress_callback("augment_complete", total_work, total_work)

        logger.info(
            "Augmentation complete: %d augmented, %d synthetic, %d skipped, %d failed in %.1fs",
            result.augmented, result.synthetic, result.skipped, result.failed,
            result.duration_ms / 1000,
        )
        return result

    def run_pass_05(
        self,
        trace_handle: Any = None,
    ) -> Dict[str, Any]:
        """Pass 0.5: Extract related_files from augmentations, validate via Rust.

        Reads trace_augmented.jsonl, collects all related_files hypotheses,
        and feeds them to the Rust engine's incorporate_inferred_edges()
        for validation. Writes trace_inferred_edges.jsonl.

        Args:
            trace_handle: A codrag_engine.TraceHandle (Rust trace graph).
                          If None, attempts to import and load from index_dir.

        Returns:
            Dict with validation stats (accepted, rejected_*, boosted).
        """
        if trace_handle is None:
            try:
                import codrag_engine
                trace_handle = codrag_engine.load_trace(str(self.index_dir))
            except Exception as e:
                logger.warning("Cannot load Rust trace for Pass 0.5: %s", e)
                return {"error": str(e)}

        # Load augmentations
        existing = self.load_existing()
        if not existing:
            logger.info("No augmentations found, skipping Pass 0.5")
            return {"skipped": True, "reason": "no_augmentations"}

        # Collect hypotheses from related_files
        hypotheses: List[Dict[str, Any]] = []
        for entry in existing.values():
            if not entry.related_files:
                continue
            for rel_path in entry.related_files:
                rel_path = rel_path.strip()
                if not rel_path:
                    continue
                hypotheses.append({
                    "source_node_id": entry.node_id,
                    "target_file_path": rel_path,
                    "relationship": "related",
                    "confidence": entry.confidence,  # use augmentation confidence as edge confidence
                })

        if not hypotheses:
            logger.info("No related_files hypotheses found, skipping Pass 0.5")
            return {"skipped": True, "reason": "no_hypotheses"}

        logger.info("Pass 0.5: validating %d relationship hypotheses", len(hypotheses))

        # Call Rust validation
        result = trace_handle.incorporate_inferred_edges(hypotheses, min_confidence=0.7)

        # Write inferred edges to file
        inferred_count = trace_handle.write_inferred_edges(str(self.index_dir))

        stats = dict(result)
        stats["total_hypotheses"] = len(hypotheses)
        stats["inferred_edges_written"] = inferred_count

        logger.info(
            "Pass 0.5 complete: %d accepted, %d rejected (missing_src=%d, missing_tgt=%d, low_conf=%d, dup=%d), %d boosted",
            stats.get("accepted", 0),
            stats.get("rejected_missing_source", 0) + stats.get("rejected_missing_target", 0)
            + stats.get("rejected_low_confidence", 0) + stats.get("rejected_duplicate", 0),
            stats.get("rejected_missing_source", 0),
            stats.get("rejected_missing_target", 0),
            stats.get("rejected_low_confidence", 0),
            stats.get("rejected_duplicate", 0),
            stats.get("boosted", 0),
        )

        return stats

    def _write_augmentations(self, entries: Dict[str, AugmentationEntry]) -> None:
        """Write augmentations atomically."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        sorted_entries = sorted(entries.values(), key=lambda e: e.node_id)

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", dir=self.index_dir, delete=False, encoding="utf-8",
        )
        try:
            for entry in sorted_entries:
                tmp.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, self.augmented_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    def _write_manifest(self, result: AugmentResult, entries: Dict[str, AugmentationEntry]) -> None:
        """Write augmentation manifest."""
        # Exclude synthetic entries from avg confidence — they have 0.1 confidence
        # and artificially drag down the average (e.g. 61% instead of ~85%).
        real_confidences = [e.confidence for e in entries.values() if not e.model.startswith("synthetic:")]
        all_confidences = [e.confidence for e in entries.values()]
        avg_conf = sum(real_confidences) / len(real_confidences) if real_confidences else 0.0
        low_conf = sum(1 for e in entries.values() if e.confidence < 0.5 and not e.model.startswith("synthetic:"))
        validated = sum(1 for e in entries.values() if e.validated)

        # Augmentable nodes = total minus skipped (external_module nodes can't be augmented)
        augmentable_nodes = result.total_nodes - result.skipped

        manifest = {
            "version": AUGMENT_FORMAT_VERSION,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "model": self.llm.model,
            "counts": {
                "total_nodes": augmentable_nodes,
                "augmented": len(entries),
                "validated": validated,
                "low_confidence": low_conf,
                "skipped_external": result.skipped,
            },
            "stats": {
                "avg_confidence": round(avg_conf, 3),
                "tokens_used": result.tokens_used,
                "duration_ms": round(result.duration_ms, 1),
                "augmented_this_run": result.augmented,
                "synthetic_this_run": result.synthetic,
                "failed_this_run": result.failed,
                "skipped_this_run": result.skipped,
            },
        }

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", dir=self.index_dir, delete=False, encoding="utf-8",
        )
        try:
            json.dump(manifest, tmp, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, self.augment_manifest_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    def status(self) -> Dict[str, Any]:
        """Return augmentation status summary."""
        if not self.augment_manifest_path.exists():
            return {
                "enabled": False,
                "total_nodes": 0,
                "augmented_nodes": 0,
                "validated_nodes": 0,
                "avg_confidence": 0.0,
                "low_confidence_count": 0,
            }

        try:
            with open(self.augment_manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            counts = manifest.get("counts", {})
            stats = manifest.get("stats", {})
            return {
                "enabled": True,
                "total_nodes": counts.get("total_nodes", 0),
                "augmented_nodes": counts.get("augmented", 0),
                "validated_nodes": counts.get("validated", 0),
                "avg_confidence": stats.get("avg_confidence", 0.0),
                "low_confidence_count": counts.get("low_confidence", 0),
                "last_augment_at": manifest.get("built_at"),
                "model": manifest.get("model"),
            }
        except Exception:
            return {
                "enabled": False,
                "total_nodes": 0,
                "augmented_nodes": 0,
                "validated_nodes": 0,
                "avg_confidence": 0.0,
                "low_confidence_count": 0,
            }
