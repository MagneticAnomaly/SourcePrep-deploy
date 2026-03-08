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
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from codrag.core.context_config import PipelineTask, compute_optimal_settings
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .llm_client import _get_llm_concurrency, _parse_confidence

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

_MIN_CONFIDENCE_DEFAULT = 0.5  # Discard edges below this threshold


def _get_min_confidence() -> float:
    """Read min_edge_confidence from global advanced_config, with fallback."""
    try:
        from codrag.services.settings_store import settings
        adv = settings.get("advanced_config")
        if adv and isinstance(adv, dict):
            return float(adv.get("min_edge_confidence", _MIN_CONFIDENCE_DEFAULT))
    except Exception:
        pass
    return _MIN_CONFIDENCE_DEFAULT


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
        cancel_token: Optional[Any] = None,
    ) -> InferredEdgesResult:
        """Run the inferred edges analysis.

        Incremental: skips files whose content hash matches the manifest.

        If *cancel_token* is provided, the loop checks it periodically and
        flushes partial results before raising.
        """
        start = time.time()
        min_confidence = _get_min_confidence()

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
            _BYOK_CONCURRENCY = 3  # Max concurrent batched API calls

            # Pre-build all batch payloads
            all_batches = []
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
                if items:
                    all_batches.append(items)

            def _call_edge_batch(items):
                prompt = build_batched_inferred_edges_prompt(items, known_text)
                prompt_tokens = len(prompt) // 4
                num_predict, num_ctx, warnings = compute_optimal_settings(
                    task=PipelineTask.AUGMENT,  # Treat similar to augment
                    prompt_tokens=prompt_tokens,
                    model=self.llm.model,
                    think=False,
                )

                try:
                    text, tokens = self.llm.generate(
                        prompt, system=BATCHED_INFERRED_EDGES_SYSTEM,
                        num_predict=num_predict, num_ctx=num_ctx,
                        response_schema=schema,
                    )
                    return BatchedResponseParser.parse(text, expected_count=len(items))
                except Exception as e:
                    logger.warning("Batched inferred edges failed for %d items: %s", len(items), e)
                    return None  # Distinguish from empty parse

            # Dispatch batches concurrently
            done_batches = 0
            with ThreadPoolExecutor(max_workers=min(_BYOK_CONCURRENCY, len(all_batches) or 1)) as pool:
                future_to_items = {
                    pool.submit(_call_edge_batch, items): items
                    for items in all_batches
                }
                for future in as_completed(future_to_items):
                    items = future_to_items[future]
                    try:
                        results_list = future.result()
                    except Exception as e:
                        logger.warning("Edge batch future failed: %s", e)
                        results_list = None

                    if results_list is None:
                        failed += len(items)
                        done_batches += 1
                        continue

                    for idx, item in enumerate(items):
                        fp = item["file_path"]
                        parsed = results_list[idx] if idx < len(results_list) else None
                        if parsed:
                            raw_edges = parsed.get("edges", [])
                            for re_item in raw_edges:
                                edges_found += 1
                                conf = _parse_confidence(re_item.get("confidence"), 0.0)
                                if conf < min_confidence:
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

                            if item["_content_hash"]:
                                new_manifest[fp] = item["_content_hash"]
                        else:
                            failed += 1

                    done_batches += 1
                    if progress_callback:
                        progress_callback("Inferring edges", min(done_batches * batch_size, total), total)

        else:
            # Local model: sequential or concurrent
            concurrency = _get_llm_concurrency("code")
            logger.info("Inferred edges: %d files, concurrency=%d", total, concurrency)

            if concurrency <= 1:
                # Sequential: one file at a time
                for i, (node, content_hash) in enumerate(to_analyze):
                    # Cooperative cancellation check
                    if cancel_token and cancel_token.is_cancelled:
                        logger.info("Inferred edges paused/cancelled at %d/%d — flushing partial results", i, total)
                        self._write_edges(new_edges)
                        self._save_manifest(new_manifest)
                        cancel_token.raise_if_cancelled()

                    fp = node.get("file_path", "")
                    if progress_callback:
                        progress_callback("Inferring edges", i, total)

                    try:
                        file_edges = self._analyze_file(
                            node, all_file_paths, edge_targets, inferred_targets
                        )
                        for edge in file_edges:
                            edges_found += 1
                            if edge.confidence < min_confidence:
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
            else:
                # Concurrent LLM calls via thread pool
                lock = threading.Lock()
                done_count = 0
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    futures = {
                        pool.submit(
                            self._analyze_file, node, all_file_paths, edge_targets, inferred_targets
                        ): (node, content_hash)
                        for node, content_hash in to_analyze
                    }
                    for future in as_completed(futures):
                        node, content_hash = futures[future]
                        fp = node.get("file_path", "")
                        try:
                            file_edges = future.result()
                            with lock:
                                for edge in file_edges:
                                    edges_found += 1
                                    if edge.confidence < min_confidence:
                                        skipped_low += 1
                                        continue
                                    existing = edge_targets.get(edge.source_file, set())
                                    already_inferred = inferred_targets.get(edge.source_file, set())
                                    if edge.target_file in existing or edge.target_file in already_inferred:
                                        skipped_dup += 1
                                        continue
                                    new_edges.append(edge)
                                    edges_written += 1
                                    inferred_targets.setdefault(edge.source_file, set()).add(edge.target_file)
                                if content_hash:
                                    new_manifest[fp] = content_hash
                                done_count += 1
                                if progress_callback:
                                    progress_callback("Inferring edges", done_count, total)
                        except Exception as e:
                            logger.warning("Inferred edges failed for %s: %s", fp, e)
                            with lock:
                                failed += 1
                                done_count += 1

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

        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.AUGMENT,  # Treat similar to augment
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        text, tokens = self.llm.generate(
            prompt,
            system=INFERRED_EDGES_SYSTEM,
            num_predict=num_predict,
            num_ctx=num_ctx,
            temperature=0.1,
        )

        return self._parse_response(fp, text)

    def _parse_response(self, source_file: str, text: str) -> List[InferredEdge]:
        """Parse LLM response into InferredEdge objects."""
        from .llm_client import _parse_json_response
        parsed = _parse_json_response(text)
        if parsed is None:
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
            confidence = _parse_confidence(item.get("confidence"), 0.5)
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


# ── Directory Proximity Edges (TG-8) ────────────────────────────────

# Non-code extensions that should be excluded from co_located edges
_NON_CODE_EXTENSIONS = {
    ".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".conf", ".lock", ".sum", ".csv", ".xml", ".html", ".css",
    ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".map", ".min.js", ".min.css", ".LICENSE", "",
}


def generate_directory_proximity_edges(
    index_dir: Path,
    max_dir_size: int = 20,
    min_confidence: float = 0.3,
) -> int:
    """Generate co_located edges between code files in the same directory.

    Provides baseline connectivity for repos where import resolution fails.
    Files in the same directory are assumed to be related with a confidence
    that decays with directory size (large directories are less informative).

    Args:
        index_dir: Path to .codrag index directory.
        max_dir_size: Skip directories with more files than this (too noisy).
        min_confidence: Minimum confidence threshold for emitted edges.

    Returns:
        Number of edges written.
    """
    nodes_path = index_dir / "trace_nodes.jsonl"
    if not nodes_path.exists():
        return 0

    # Load file nodes
    file_paths: List[str] = []
    with open(nodes_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                node = json.loads(line)
                if node.get("kind") == "file":
                    fp = node.get("file_path", "")
                    if fp:
                        file_paths.append(fp)
            except json.JSONDecodeError:
                continue

    if len(file_paths) < 2:
        return 0

    # Filter to code files only
    import os.path as osp
    code_files = [
        fp for fp in file_paths
        if osp.splitext(fp)[1].lower() not in _NON_CODE_EXTENSIONS
    ]

    # Group by parent directory
    dir_groups: Dict[str, List[str]] = {}
    for fp in code_files:
        parent = osp.dirname(fp) or "."
        dir_groups.setdefault(parent, []).append(fp)

    # Load existing edges to avoid duplicates
    existing_pairs: Set[Tuple[str, str]] = set()
    for edge_file in ("trace_edges.jsonl", "trace_inferred_edges.jsonl"):
        edge_path = index_dir / edge_file
        if not edge_path.exists():
            continue
        try:
            with open(edge_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                        src = e.get("source", "").replace("file:", "", 1)
                        tgt = e.get("target", "").replace("file:", "", 1)
                        if src and tgt:
                            existing_pairs.add((src, tgt))
                            existing_pairs.add((tgt, src))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue

    # Generate co_located edges
    edges_written = 0
    inferred_path = index_dir / "trace_inferred_edges.jsonl"

    with open(inferred_path, "a", encoding="utf-8") as out:
        for dir_path, members in dir_groups.items():
            if len(members) < 2 or len(members) > max_dir_size:
                continue

            # Confidence decays with directory size: 2 files = 0.6, 10 files = 0.3
            confidence = round(max(min_confidence, 0.7 - (len(members) * 0.04)), 2)

            for i, src in enumerate(members):
                for tgt in members[i + 1:]:
                    if (src, tgt) in existing_pairs:
                        continue
                    existing_pairs.add((src, tgt))
                    existing_pairs.add((tgt, src))

                    edge = {
                        "id": f"proximity:{src}->{tgt}",
                        "kind": "co_located",
                        "source": f"file:{src}",
                        "target": f"file:{tgt}",
                        "metadata": {
                            "inferred": True,
                            "method": "directory_proximity",
                            "confidence": confidence,
                            "directory": dir_path,
                        },
                    }
                    out.write(json.dumps(edge) + "\n")
                    edges_written += 1

    if edges_written > 0:
        logger.info("TG-8: Generated %d directory proximity edges", edges_written)

    return edges_written


# ── Git Co-Change Edges (TG-2) ──────────────────────────────────────

def generate_git_cochange_edges(
    index_dir: Path,
    repo_root: Path,
    min_commits: int = 3,
    min_jaccard: float = 0.25,
    max_commits: int = 500,
    recency_halflife: int = 90,
) -> int:
    """Generate co_changes edges from git commit history.

    Files that frequently change together in commits have an implicit
    dependency even when no import edge exists. Uses Jaccard similarity
    with exponential recency weighting.

    Args:
        index_dir: Path to .codrag index directory.
        repo_root: Path to the git repository root.
        min_commits: Minimum co-occurrence count to consider a pair.
        min_jaccard: Minimum Jaccard similarity threshold.
        max_commits: Maximum recent commits to analyze.
        recency_halflife: Days for exponential decay half-life.

    Returns:
        Number of edges written.
    """
    import subprocess
    import math
    from datetime import datetime, timezone
    from itertools import combinations

    nodes_path = index_dir / "trace_nodes.jsonl"
    if not nodes_path.exists():
        return 0

    # Collect known file paths from trace
    known_files: Set[str] = set()
    with open(nodes_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                node = json.loads(line)
                if node.get("kind") == "file":
                    fp = node.get("file_path", "")
                    if fp:
                        known_files.add(fp)
            except json.JSONDecodeError:
                continue

    if len(known_files) < 2:
        return 0

    # Parse git log for commit → files mapping
    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={max_commits}",
             "--name-only", "--pretty=format:COMMIT:%H:%at"],
            capture_output=True, text=True, cwd=str(repo_root),
            timeout=30,
        )
        if result.returncode != 0:
            logger.debug("TG-2: git log failed: %s", result.stderr[:200])
            return 0
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.debug("TG-2: git unavailable: %s", e)
        return 0

    now_ts = datetime.now(timezone.utc).timestamp()
    decay_rate = math.log(2) / (recency_halflife * 86400)  # per-second decay

    # Parse commits
    commits: List[Tuple[float, List[str]]] = []  # (weight, [files])
    current_weight = 1.0
    current_files: List[str] = []

    for raw_line in result.stdout.split("\n"):
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        if raw_line.startswith("COMMIT:"):
            # Save previous commit
            if current_files:
                commits.append((current_weight, current_files))
            parts = raw_line.split(":")
            commit_ts = float(parts[2]) if len(parts) >= 3 else now_ts
            age_s = max(0, now_ts - commit_ts)
            current_weight = math.exp(-decay_rate * age_s)
            current_files = []
        else:
            # File path line
            if raw_line in known_files:
                current_files.append(raw_line)
    if current_files:
        commits.append((current_weight, current_files))

    if not commits:
        return 0

    # Compute weighted co-occurrence and individual occurrence
    cooccur: Dict[Tuple[str, str], float] = {}
    occur: Dict[str, float] = {}

    for weight, files in commits:
        # Only consider commits with 2-30 files (skip merges and single-file changes)
        if len(files) < 2 or len(files) > 30:
            continue
        for fp in files:
            occur[fp] = occur.get(fp, 0.0) + weight
        for a, b in combinations(sorted(files), 2):
            pair = (a, b)
            cooccur[pair] = cooccur.get(pair, 0.0) + weight

    # Load existing edges to avoid duplicates
    existing_pairs: Set[Tuple[str, str]] = set()
    for edge_file in ("trace_edges.jsonl", "trace_inferred_edges.jsonl"):
        edge_path = index_dir / edge_file
        if not edge_path.exists():
            continue
        try:
            with open(edge_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                        if e.get("kind") == "co_changes":
                            src = e.get("source", "").replace("file:", "", 1)
                            tgt = e.get("target", "").replace("file:", "", 1)
                            if src and tgt:
                                existing_pairs.add((min(src, tgt), max(src, tgt)))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue

    # Emit co_changes edges
    edges_written = 0
    inferred_path = index_dir / "trace_inferred_edges.jsonl"

    with open(inferred_path, "a", encoding="utf-8") as out:
        for (a, b), co_weight in cooccur.items():
            if co_weight < min_commits * 0.5:  # weighted threshold
                continue
            pair_key = (min(a, b), max(a, b))
            if pair_key in existing_pairs:
                continue

            union_weight = occur.get(a, 0.0) + occur.get(b, 0.0) - co_weight
            if union_weight <= 0:
                continue
            jaccard = co_weight / union_weight

            if jaccard < min_jaccard:
                continue

            existing_pairs.add(pair_key)
            edge = {
                "id": f"cochange:{a}->{b}",
                "kind": "co_changes",
                "source": f"file:{a}",
                "target": f"file:{b}",
                "metadata": {
                    "inferred": True,
                    "method": "git_cochange",
                    "confidence": round(min(0.95, jaccard), 2),
                    "jaccard": round(jaccard, 3),
                    "co_occurrence_weight": round(co_weight, 2),
                },
            }
            out.write(json.dumps(edge) + "\n")
            edges_written += 1

    if edges_written > 0:
        logger.info("TG-2: Generated %d git co-change edges", edges_written)

    return edges_written
