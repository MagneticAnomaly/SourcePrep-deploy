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
import time
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
            confidence=float(d.get("confidence", 0.0)),
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
    tokens_used: int = 0
    duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)


class LLMClient:
    """
    Minimal LLM client for augmentation calls.
    Wraps Ollama-compatible /api/generate endpoint.
    """

    def __init__(
        self,
        endpoint_url: str,
        model: str,
        provider: str = "ollama",
        api_key: Optional[str] = None,
        timeout: float = 60.0
    ):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.model = model
        self.provider = provider
        self.api_key = api_key
        self.timeout = timeout

    def generate(self, prompt: str, system: Optional[str] = None, num_predict: int = 1024) -> Tuple[str, int]:
        """
        Call the LLM and return (response_text, tokens_used).
        Raises on network/parse errors.
        """
        import requests

        if self.provider == "ollama":
            payload: Dict[str, Any] = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1, "num_predict": num_predict},
            }
            if system:
                payload["system"] = system

            url = f"{self.endpoint_url}/api/generate"
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            text = data.get("response", "")
            tokens = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)
            return text, tokens

        elif self.provider in ("openai", "openai-compatible"):
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.1,
                # "response_format": {"type": "json_object"}, # Not all OpenAI-compat models support this, so rely on prompt
            }
            
            headers = {
                "Content-Type": "application/json",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Assume endpoint_url is base URL (e.g. https://api.openai.com/v1)
            # Some users might put /chat/completions in the URL, try to handle gracefully?
            # Standard convention: endpoint_url is base, we append /chat/completions
            url = f"{self.endpoint_url}/chat/completions"
            
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            
            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})
            tokens = usage.get("total_tokens", 0)
            return text, tokens
        
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def is_available(self) -> bool:
        """Check if the endpoint is reachable."""
        import requests
        try:
            if self.provider == "ollama":
                resp = requests.get(f"{self.endpoint_url}/api/tags", timeout=5)
                return resp.status_code == 200
            elif self.provider in ("openai", "openai-compatible"):
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                # Try listing models
                resp = requests.get(f"{self.endpoint_url}/models", headers=headers, timeout=5)
                return resp.status_code == 200
            return False
        except Exception:
            return False


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


def _parse_json_response(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON extraction from LLM response."""
    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting JSON from markdown code block
    if "```" in text:
        for block in text.split("```"):
            block = block.strip()
            if block.startswith("json"):
                block = block[4:].strip()
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue
    # Try finding first { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    # Truncated JSON repair: we have '{' but no '}' (LLM output was cut off)
    if start >= 0 and (end < 0 or end <= start):
        fragment = text[start:]
        repaired = _repair_truncated_json(fragment)
        if repaired is not None:
            return repaired
    return None


def _repair_truncated_json(fragment: str) -> Optional[Dict[str, Any]]:
    """Try to recover a dict from a truncated JSON fragment.

    Strategy: progressively strip trailing incomplete content and try
    closing the string / object.
    """
    # Try closing with various suffixes (handles mid-string truncation)
    for suffix in ('"}', '" }', '}', '"}}', '0}', 'null}'):
        try:
            return json.loads(fragment + suffix)
        except json.JSONDecodeError:
            continue

    # More aggressive: strip back to the last complete key-value comma boundary
    # e.g. {"verdict":"corrected","summary":"long text that got tru
    #  → try to cut at the last comma before the truncation
    last_comma = fragment.rfind(",")
    if last_comma > 0:
        truncated = fragment[:last_comma]
        for suffix in ("}", '"}'):
            try:
                return json.loads(truncated + suffix)
            except json.JSONDecodeError:
                continue

    return None


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
    ):
        self.index_dir = Path(index_dir).resolve()
        self.repo_root = Path(repo_root).resolve()
        self.llm = llm_client

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
        head_lines: int = 100,
        section_lines: int = 30,
        max_total: int = 300,
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
            return None

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
            text, tokens = self.llm.generate(prompt, system=SYMBOL_SUMMARY_SYSTEM)
        except Exception as e:
            logger.warning("LLM call failed for %s: %s", node.get("name"), e)
            return None

        parsed = _parse_json_response(text)
        if not parsed:
            logger.warning("Failed to parse LLM response for %s — raw: %.200s", node.get("name"), text)
            return None

        role = parsed.get("role", "internal")
        if role not in VALID_ROLES:
            role = "internal"

        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return AugmentationEntry(
            node_id=node["id"],
            summary=str(parsed.get("summary", ""))[:500],
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
            logger.debug("Skipping build output file: %s", file_path)
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
            text, tokens = self.llm.generate(prompt, system=FILE_ROLE_SYSTEM)
        except Exception as e:
            logger.warning("LLM call failed for file %s: %s", file_path, e)
            return None

        parsed = _parse_json_response(text)
        if not parsed:
            logger.warning("Failed to parse LLM response for file %s — raw: %.200s", file_path, text)
            return None

        role = parsed.get("role", "utility")
        if role not in VALID_ROLES:
            role = "utility"

        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        related = parsed.get("related_files")
        if isinstance(related, list):
            related = [str(r) for r in related[:5]]
        else:
            related = None

        return AugmentationEntry(
            node_id=node["id"],
            summary=str(parsed.get("summary", ""))[:500],
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
            text, tokens = self.llm.generate(prompt, system=DOC_ROLE_SYSTEM)
        except Exception as e:
            logger.warning("LLM call failed for doc %s: %s", file_path, e)
            return None

        parsed = _parse_json_response(text)
        if not parsed:
            logger.warning("Failed to parse LLM response for doc %s — raw: %.200s", file_path, text)
            return None

        role = parsed.get("role", "documentation")
        if role not in VALID_ROLES:
            role = "documentation"

        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

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

        return AugmentationEntry(
            node_id=node["id"],
            summary=str(parsed.get("summary", ""))[:500],
            role=role,
            confidence=confidence,
            augmented_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model,
            file_hash=file_hashes.get(file_path),
            related_files=related,
            doc_type=doc_type,
            doc_status=doc_status,
        )

    def run(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        max_items: Optional[int] = None,
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

        # Start with existing entries (will be updated/overwritten)
        augmented = dict(existing)
        done = 0

        # Pass 1: Symbol augmentation
        for node in to_augment_symbols:
            if progress_callback:
                progress_callback("augment_symbols", done, total_work)

            entry = self.augment_symbol(node, edges, nodes_by_id, file_hashes)
            if entry:
                augmented[entry.node_id] = entry
                result.augmented += 1
            else:
                result.failed += 1
            done += 1

        # Pass 2: File augmentation
        for node in to_augment_files:
            if progress_callback:
                progress_callback("augment_files", done, total_work)

            entry = self.augment_file(node, edges, nodes_by_id, file_hashes)
            if entry:
                augmented[entry.node_id] = entry
                result.augmented += 1
            else:
                result.failed += 1
            done += 1

        result.skipped = result.total_nodes - total_work

        # Write atomically
        self._write_augmentations(augmented)
        self._write_manifest(result, augmented)

        result.duration_ms = (time.monotonic() - start) * 1000

        if progress_callback:
            progress_callback("augment_complete", total_work, total_work)

        logger.info(
            "Augmentation complete: %d augmented, %d skipped, %d failed in %.1fs",
            result.augmented, result.skipped, result.failed, result.duration_ms / 1000,
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
        confidences = [e.confidence for e in entries.values()]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        low_conf = sum(1 for c in confidences if c < 0.5)
        validated = sum(1 for e in entries.values() if e.validated)

        manifest = {
            "version": AUGMENT_FORMAT_VERSION,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "model": self.llm.model,
            "counts": {
                "total_nodes": result.total_nodes,
                "augmented": len(entries),
                "validated": validated,
                "low_confidence": low_conf,
            },
            "stats": {
                "avg_confidence": round(avg_conf, 3),
                "tokens_used": result.tokens_used,
                "duration_ms": round(result.duration_ms, 1),
                "augmented_this_run": result.augmented,
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
