"""
CoDRAG Inferred Edges — LLM-powered edge discovery (Stage 1.5)
==============================================================

Reads trace_nodes.jsonl + source code and uses an LLM to infer edges
that static parsing (tree-sitter / regex) cannot detect:

  - **Cross-language calls**: Python calling a REST endpoint defined in TS
  - **Dynamic dispatch**: getattr(), eval(), reflection patterns
  - **Interface satisfaction**: which struct/class implements an interface
  - **Implicit dependencies**: config files referencing code paths, env vars

Outputs: trace_inferred_edges.jsonl  (same schema as trace_edges.jsonl)

These edges are loaded by TraceIndex and available to all downstream
stages (catalogue, validation, epistemic, clustering).

**VRAM note**: Uses the small_model slot.  The pipeline orchestrator
handles load/unload transitions so this stage and catalogue share the
same model without redundant VRAM swaps.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── Prompt templates ─────────────────────────────────────────────────

INFERRED_EDGES_SYSTEM = """You are a code analyst specializing in cross-file dependency detection.
You identify relationships between code files that static parsing misses:
cross-language API calls, dynamic dispatch, interface implementations, and implicit dependencies.
You MUST respond with valid JSON only. No markdown, no explanation outside the JSON."""

INFERRED_EDGES_PROMPT = """Analyze this source file and identify relationships to OTHER files in the codebase that static import analysis would miss.

File: {file_path}
Language: {language}

Known files in the codebase (potential targets):
{known_files}

Existing static edges for this file:
{existing_edges}

Source code:
```
{source_code}
```

Identify edges that static import/require analysis CANNOT detect. Look for:
1. HTTP/REST/RPC calls to endpoints defined in other files (e.g. fetch("/api/users") → routes/users.py)
2. Dynamic dispatch: getattr(), eval(), importlib, require() with variables, reflection
3. Interface/protocol satisfaction: classes implementing interfaces defined elsewhere
4. Config references: file paths in strings, env var names referencing other modules
5. Event emitters/listeners: publish/subscribe patterns connecting files

Respond with this exact JSON format:
{{"edges": [{{"target_file": "path/to/target.py", "kind": "calls", "evidence": "fetch('/api/users') matches route in target", "confidence": 0.8}}]}}

Where kind is one of: calls, implements, configures, listens_to, dispatches
confidence: 0.0-1.0 (how certain you are this edge exists)

Rules:
- ONLY emit edges to files in the known_files list. Do not invent file paths.
- ONLY emit edges that are NOT already in existing_edges.
- Maximum 10 edges per file. Prefer high-confidence edges.
- If no inferred edges are found, return {{"edges": []}}

JSON response:"""


# ── Data types ───────────────────────────────────────────────────────

VALID_EDGE_KINDS = {"calls", "implements", "configures", "listens_to", "dispatches"}

MIN_CONFIDENCE = 0.5  # Discard edges below this threshold


@dataclass
class InferredEdge:
    """A single LLM-inferred edge."""
    source_file: str  # repo-relative path
    target_file: str  # repo-relative path
    kind: str         # calls | implements | configures | listens_to | dispatches
    evidence: str     # LLM's reasoning for this edge
    confidence: float # 0.0–1.0
    model: str        # LLM model that produced this edge

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": f"inferred:{self.kind}:{self.source_file}->{self.target_file}",
            "kind": self.kind,
            "source": f"file:{self.source_file}",
            "target": f"file:{self.target_file}",
            "metadata": {
                "inferred": True,
                "evidence": self.evidence,
                "confidence": self.confidence,
                "model": self.model,
            },
        }


@dataclass
class InferredEdgesResult:
    """Result of the inferred edges stage."""
    files_analyzed: int
    edges_found: int
    edges_written: int
    skipped_low_confidence: int
    skipped_duplicate: int
    failed: int
    duration_ms: int


# ── Analyzer ─────────────────────────────────────────────────────────

class InferredEdgesAnalyzer:
    """Analyzes source files to discover edges that static parsing misses.

    Architecture:
    - Reads trace_nodes.jsonl for the list of files and their metadata.
    - Reads trace_edges.jsonl for existing static edges (to avoid duplicates).
    - For each code file, sends source + context to the LLM.
    - Writes trace_inferred_edges.jsonl (append-safe, deduped).
    - Supports incremental runs via a manifest of already-analyzed files.
    """

    # Files larger than this are skipped (too much context for the LLM)
    MAX_SOURCE_CHARS = 4000
    # Maximum known_files context to include in prompt
    MAX_KNOWN_FILES = 100

    def __init__(
        self,
        index_dir: str | Path,
        repo_root: str | Path,
        llm_client: Any,  # LLMClient from augmenter.py
        batch_profile: Optional[Any] = None,
    ):
        self.index_dir = Path(index_dir).resolve()
        self.repo_root = Path(repo_root).resolve()
        self.llm = llm_client
        self._batch_profile = batch_profile

        self.inferred_path = self.index_dir / "trace_inferred_edges.jsonl"
        self.manifest_path = self.index_dir / "trace_inferred_manifest.json"

    # ── Public API ────────────────────────────────────────────────

    def run(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        max_items: Optional[int] = None,
    ) -> InferredEdgesResult:
        """Run the inferred edges analysis.

        Incremental: skips files whose content hash matches the manifest.
        """
        start = time.time()

        nodes = self._load_nodes()
        existing_edges = self._load_existing_edges()
        existing_inferred = self._load_existing_inferred()
        manifest = self._load_manifest()

        # Filter to code files only (skip markdown, external_module nodes)
        code_files = [
            n for n in nodes
            if n.get("kind") == "file"
            and n.get("language") not in (None, "markdown")
        ]

        # Build known-files set for the prompt (all file nodes)
        all_file_paths = sorted(set(
            n.get("file_path", "")
            for n in nodes
            if n.get("kind") == "file" and n.get("file_path")
        ))

        # Build existing-edge lookup: source_file → set of target_files
        edge_targets: Dict[str, Set[str]] = {}
        for e in existing_edges:
            src = e.get("source", "").replace("file:", "", 1)
            tgt = e.get("target", "").replace("file:", "", 1)
            edge_targets.setdefault(src, set()).add(tgt)

        # Also include already-inferred edges in the duplicate check
        inferred_targets: Dict[str, Set[str]] = {}
        for e in existing_inferred:
            src = e.get("source", "").replace("file:", "", 1)
            tgt = e.get("target", "").replace("file:", "", 1)
            inferred_targets.setdefault(src, set()).add(tgt)

        # Determine which files need analysis
        to_analyze = []
        for node in code_files:
            fp = node.get("file_path", "")
            content_hash = self._file_hash(fp)
            if content_hash and manifest.get(fp) == content_hash:
                continue  # Already analyzed with same content
            to_analyze.append((node, content_hash))

        if max_items:
            to_analyze = to_analyze[:max_items]

        total = len(to_analyze)
        edges_found = 0
        edges_written = 0
        skipped_low = 0
        skipped_dup = 0
        failed = 0

        new_edges: List[InferredEdge] = []
        new_manifest = dict(manifest)

        # Decide: batched (BYOK) or sequential (local)
        use_batching = (
            self._batch_profile is not None
            and self._batch_profile.name.value != "off"
        )

        if use_batching:
            from .batch_profiles import BatchStage
            from .batch_prompts import (
                BATCHED_INFERRED_EDGES_SYSTEM,
                build_batched_inferred_edges_prompt,
                get_structured_schema,
            )
            from .batch_strategy import BatchedResponseParser

            batch_size = self._batch_profile.batch_size(BatchStage.INFERRED_EDGES)
            known_text = "\n".join(f"- {f}" for f in all_file_paths[:self.MAX_KNOWN_FILES])
            logger.info(
                "BATCHED inferred edges: %d files, batch_size=%d (%s profile)",
                total, batch_size, self._batch_profile.name.value,
            )

            schema = get_structured_schema("inferred_edges")

            for batch_start in range(0, total, batch_size):
                batch = to_analyze[batch_start:batch_start + batch_size]
                items = []
                for node, content_hash in batch:
                    fp = node.get("file_path", "")
                    source = self._read_source(fp)
                    if not source:
                        failed += 1
                        if content_hash:
                            new_manifest[fp] = content_hash
                        continue
                    existing_set = edge_targets.get(fp, set()) | inferred_targets.get(fp, set())
                    existing_text = "\n".join(f"- {fp} → {t}" for t in sorted(existing_set)[:20]) if existing_set else "(none)"
                    items.append({
                        "file_path": fp,
                        "language": node.get("language", "unknown"),
                        "source_code": source[:self.MAX_SOURCE_CHARS],
                        "existing_edges": existing_text,
                        "_node": node,
                        "_content_hash": content_hash,
                    })

                if not items:
                    continue

                prompt = build_batched_inferred_edges_prompt(items, known_text)
                try:
                    text, tokens = self.llm.generate(
                        prompt, system=BATCHED_INFERRED_EDGES_SYSTEM,
                        num_predict=len(items) * 300,
                        response_schema=schema,
                    )
                    results_list = BatchedResponseParser.parse(text, expected_count=len(items))
                except Exception as e:
                    logger.warning("Batched inferred edges failed for %d items: %s", len(items), e)
                    results_list = []
                    failed += len(items)
                    # We do NOT update new_manifest here so failed files are retried next time
                    continue

                for idx, item in enumerate(items):
                    fp = item["file_path"]
                    parsed = results_list[idx] if idx < len(results_list) else None
                    if parsed:
                        raw_edges = parsed.get("edges", [])
                        for re_item in raw_edges:
                            edges_found += 1
                            conf = float(re_item.get("confidence", 0.0))
                            if conf < MIN_CONFIDENCE:
                                skipped_low += 1
                                continue
                            target = re_item.get("target_file", "")
                            existing_set = edge_targets.get(fp, set()) | inferred_targets.get(fp, set())
                            if target in existing_set:
                                skipped_dup += 1
                                continue
                            edge = InferredEdge(
                                source_file=fp,
                                target_file=target,
                                kind=re_item.get("kind", "calls"),
                                evidence=re_item.get("evidence", ""),
                                confidence=conf,
                            )
                            new_edges.append(edge)
                            edges_written += 1
                            inferred_targets.setdefault(fp, set()).add(target)

                        # Only update manifest if we successfully parsed the result
                        if item["_content_hash"]:
                            new_manifest[fp] = item["_content_hash"]
                    else:
                        failed += 1

                if progress_callback:
                    progress_callback("Inferring edges", min(batch_start + batch_size, total), total)

        else:
            # Sequential: one file at a time (local model)
            for i, (node, content_hash) in enumerate(to_analyze):
                fp = node.get("file_path", "")
                if progress_callback:
                    progress_callback("Inferring edges", i, total)

                try:
                    file_edges = self._analyze_file(
                        node, all_file_paths, edge_targets, inferred_targets
                    )
                    for edge in file_edges:
                        edges_found += 1
                        if edge.confidence < MIN_CONFIDENCE:
                            skipped_low += 1
                            continue
                        # Check duplicate against both static and already-inferred
                        existing = edge_targets.get(edge.source_file, set())
                        already_inferred = inferred_targets.get(edge.source_file, set())
                        if edge.target_file in existing or edge.target_file in already_inferred:
                            skipped_dup += 1
                            continue
                        new_edges.append(edge)
                        edges_written += 1
                        # Track for dedup within this run
                        inferred_targets.setdefault(edge.source_file, set()).add(edge.target_file)

                    if content_hash:
                        new_manifest[fp] = content_hash
                except Exception as e:
                    logger.warning("Inferred edges failed for %s: %s", fp, e)
                    failed += 1

        if progress_callback:
            progress_callback("Writing inferred edges", total, total)

        # Append new edges to the inferred edges file
        self._write_edges(new_edges)
        self._save_manifest(new_manifest)

        duration_ms = int((time.time() - start) * 1000)

        logger.info(
            "Inferred edges: analyzed=%d found=%d written=%d "
            "low_conf=%d dup=%d failed=%d (%dms)",
            total, edges_found, edges_written,
            skipped_low, skipped_dup, failed, duration_ms,
        )

        return InferredEdgesResult(
            files_analyzed=total,
            edges_found=edges_found,
            edges_written=edges_written,
            skipped_low_confidence=skipped_low,
            skipped_duplicate=skipped_dup,
            failed=failed,
            duration_ms=duration_ms,
        )

    # ── File analysis ─────────────────────────────────────────────

    def _analyze_file(
        self,
        node: Dict[str, Any],
        all_file_paths: List[str],
        edge_targets: Dict[str, Set[str]],
        inferred_targets: Dict[str, Set[str]],
    ) -> List[InferredEdge]:
        """Analyze a single file for inferred edges."""
        fp = node.get("file_path", "")
        language = node.get("language", "unknown")

        # Read source
        source = self._read_source(fp)
        if not source:
            return []

        # Build known-files context (exclude self)
        known = [f for f in all_file_paths if f != fp][:self.MAX_KNOWN_FILES]
        known_text = "\n".join(f"- {f}" for f in known)

        # Build existing edges context
        existing = edge_targets.get(fp, set()) | inferred_targets.get(fp, set())
        if existing:
            existing_text = "\n".join(f"- {fp} → {t}" for t in sorted(existing)[:20])
        else:
            existing_text = "(none)"

        prompt = INFERRED_EDGES_PROMPT.format(
            file_path=fp,
            language=language,
            known_files=known_text,
            existing_edges=existing_text,
            source_code=source[:self.MAX_SOURCE_CHARS],
        )

        text, tokens = self.llm.generate(
            prompt,
            system=INFERRED_EDGES_SYSTEM,
            num_predict=1024,
            temperature=0.1,
        )

        return self._parse_response(fp, text)

    def _parse_response(self, source_file: str, text: str) -> List[InferredEdge]:
        """Parse LLM response into InferredEdge objects."""
        from .augmenter import _parse_json_response
        parsed = _parse_json_response(text)
        if not parsed:
            logger.warning("Failed to parse inferred edges response for %s", source_file)
            return []

        raw_edges = parsed.get("edges", [])
        if not isinstance(raw_edges, list):
            return []

        edges: List[InferredEdge] = []
        for item in raw_edges[:10]:  # Hard cap at 10
            if not isinstance(item, dict):
                continue
            target = item.get("target_file", "")
            kind = item.get("kind", "calls")
            if kind not in VALID_EDGE_KINDS:
                kind = "calls"
            confidence = float(item.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
            evidence = str(item.get("evidence", ""))[:300]

            if not target:
                continue

            edges.append(InferredEdge(
                source_file=source_file,
                target_file=target,
                kind=kind,
                evidence=evidence,
                confidence=confidence,
                model=self.llm.model,
            ))

        return edges

    # ── I/O helpers ───────────────────────────────────────────────

    def _load_nodes(self) -> List[Dict[str, Any]]:
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

    def _load_existing_edges(self) -> List[Dict[str, Any]]:
        """Load static trace edges."""
        edges_path = self.index_dir / "trace_edges.jsonl"
        edges: List[Dict[str, Any]] = []
        if edges_path.exists():
            with open(edges_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        edges.append(json.loads(line))
        return edges

    def _load_existing_inferred(self) -> List[Dict[str, Any]]:
        """Load previously inferred edges."""
        edges: List[Dict[str, Any]] = []
        if self.inferred_path.exists():
            with open(self.inferred_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        edges.append(json.loads(line))
        return edges

    def _load_manifest(self) -> Dict[str, str]:
        """Load manifest of already-analyzed file hashes."""
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_manifest(self, manifest: Dict[str, str]) -> None:
        """Save manifest of analyzed file hashes."""
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

    def _write_edges(self, edges: List[InferredEdge]) -> None:
        """Append new inferred edges to the output file."""
        if not edges:
            return
        with open(self.inferred_path, "a", encoding="utf-8") as f:
            for edge in edges:
                f.write(json.dumps(edge.to_dict()) + "\n")

    def _read_source(self, file_path: str) -> Optional[str]:
        """Read source code for a file."""
        full_path = self.repo_root / file_path
        if not full_path.exists() or not full_path.is_file():
            return None
        try:
            return full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

    def _file_hash(self, file_path: str) -> Optional[str]:
        """Compute a content hash for incremental detection."""
        full_path = self.repo_root / file_path
        if not full_path.exists():
            return None
        try:
            content = full_path.read_bytes()
            return hashlib.sha256(content).hexdigest()[:16]
        except Exception:
            return None
