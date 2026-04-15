"""
CodebaseAtlas — the main atlas generator class.

Generates and caches single-document or segmented architectural overviews.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from codrag.core.context_config import PipelineTask, compute_module_cap, compute_optimal_settings
from codrag.core.llm_client import TASK_MAX_CHARS, _is_cloud_endpoint
from codrag.core.swarm_orchestrator import (
    SwarmOrchestrator,
    SwarmResult,
    WorkerAssignment,
    WorkItem,
)
from codrag.core.swarm_registry import get_min_groups_threshold, get_swarm_tier

from .models import AtlasDocument, Segment, SegmentDescriptor, SegmentDocument
from .prompts import (
    ATLAS_PROMPT,
    ATLAS_SYSTEM,
    ROOT_ATLAS_PROMPT,
    ROOT_ATLAS_SYSTEM,
    SEGMENT_ATLAS_PROMPT,
    SEGMENT_ATLAS_SYSTEM,
)
from .routing import (
    MAX_ATLAS_CHARS,
    MIN_ATLAS_CHARS,
    MIN_FILES_FOR_ATLAS,
    MIN_FILES_FOR_ROUTING,
    MIN_MODULES_FOR_ROUTING,
    ROOT_ATLAS_MAX_CHARS,
    ROOT_ATLAS_MIN_CHARS,
    ROUTING_SEGMENT_BOOST,
    SEGMENT_ATLAS_MAX_CHARS,
    SEGMENT_ATLAS_MIN_CHARS,
    build_routing_descriptors,
    compute_atlas_budget,
    compute_root_atlas_budget,
    compute_segments,
)

logger = logging.getLogger(__name__)


# ── Phase 105: evidence-aware formatting helpers ─────────────────────


def _format_hubs_with_labels(
    hubs: list[tuple[str, int]],
    classifier: Callable[[str], str],
) -> str:
    """Return a one-line hub description grouped by label, or fallback to
    the raw `<name> (<n> edges)` format if all hubs classify as 'unknown'
    (meaning no evidence available).

    Labels only — no raw numbers emitted in the grouped form.
    """
    labeled: dict[str, list[str]] = {
        "stable": [], "evolving": [], "fragile": [], "unknown": [],
    }
    for path, _edges in hubs:
        label = classifier(path)
        if label not in labeled:
            label = "unknown"
        labeled[label].append(path)

    # All-unknown → emit today's format so no-evidence behavior is
    # byte-identical to pre-phase-105 output
    if len(labeled["unknown"]) == len(hubs):
        return ", ".join(f"{p} ({d} edges)" for p, d in hubs)

    parts: list[str] = []
    for label in ("stable", "evolving", "fragile"):
        names = labeled[label]
        if names:
            parts.append(f"{', '.join(names)} ({label})")
    if labeled["unknown"]:
        parts.append(", ".join(labeled["unknown"]))
    return ", ".join(parts)


def _build_hot_zones_line(zones: list[str]) -> str:
    """Return the 'Active zones' line for cross_parts, or '' if no zones."""
    if not zones:
        return ""
    return "Active zones: " + ", ".join(f"`{z}`" for z in zones)


# ── Atlas Generator ──────────────────────────────────────────────────

class CodebaseAtlas:
    """Generates and caches a single-document codebase map.

    Usage::

        atlas = CodebaseAtlas(index_dir, llm_client)

        # Generate (or regenerate) the atlas
        doc = atlas.generate()

        # Load cached atlas from disk
        doc = atlas.load()

        # Check if regeneration needed
        if atlas.is_stale():
            doc = atlas.generate()

        # Structural-only fallback (no LLM)
        doc = atlas.generate_structural()
    """

    def __init__(
        self,
        index_dir: Path,
        llm: Optional[Any] = None,  # LLMClient from augmenter.py
        project_root: Optional[Path] = None,
    ):
        self.index_dir = Path(index_dir)
        self.llm = llm
        self.project_root = Path(project_root) if project_root else None
        self.atlas_path = self.index_dir / "atlas.json"
        self.atlas_prev_path = self.index_dir / "atlas_prev.json"
        self.segments_dir = self.index_dir / "atlas_segments"

    def _get_swarm_enabled(self) -> bool:
        """Check if swarm is enabled in pipeline settings."""
        try:
            from codrag.services.settings_store import settings
            return bool(settings.get("swarm_enabled", True))
        except Exception:
            return True

    # ── Public API ─────────────────────────────────────────────

    def generate(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> AtlasDocument:
        """Generate the Atlas via reasoning LLM.

        Reads pre-computed enrichment data (modules, epistemic, graph stats),
        formats a prompt, and makes one LLM call. Falls back to structural
        Atlas if LLM is unavailable.

        Returns:
            AtlasDocument with the generated content.
        """
        start = time.monotonic()

        if progress_callback:
            progress_callback("atlas_generation", 0, 3)

        full_modules = self._load_modules()
        modules = full_modules  # capped-for-prompt view; fingerprint uses full

        if self.llm:
            from codrag.core.context_config import detect_available_vram_gb
            vram = detect_available_vram_gb()
            cap = compute_module_cap(len(modules), available_vram_gb=vram, model=self.llm.model)
            if cap < len(modules):
                # Sort by file count descending and take top N
                modules = sorted(modules, key=lambda x: -x.get("file_count", 0))[:cap]
                logger.info("Capped atlas modules at %d (from %d) due to VRAM", cap, len(modules))

        epistemic = self._load_epistemic_summary()
        graph_stats = self._load_graph_stats()
        hub_files = self._identify_hubs(graph_stats)

        if progress_callback:
            progress_callback("atlas_generation", 1, 3)

        if not modules:
            logger.info("No modules found — generating structural atlas")
            return self.generate_structural()

        if self.llm is None:
            logger.info("No LLM configured — generating structural atlas")
            return self.generate_structural()

        # Compute budget-aware char targets
        file_count = graph_stats.get("file_count", 0)
        budget = compute_atlas_budget(file_count)
        target_chars = max(MIN_ATLAS_CHARS, budget)
        max_chars = int(target_chars * 1.3)  # allow 30% overflow before hard truncation

        # Format prompt inputs
        module_text = self._format_modules(modules)
        layer_text = self._format_layers(epistemic)
        stats_text = self._format_graph_stats(graph_stats)
        hub_text = self._format_hubs(hub_files)

        system = ATLAS_SYSTEM.format(
            target_chars=target_chars,
            max_chars=max_chars,
        )
        prompt = ATLAS_PROMPT.format(
            module_summaries=module_text,
            architecture_layers=layer_text,
            graph_stats=stats_text,
            hub_files=hub_text,
            target_chars=target_chars,
            max_chars=max_chars,
        )

        if progress_callback:
            progress_callback("atlas_generation", 2, 3)

        # One reasoning LLM call — free-form prose, not JSON.
        # Disable thinking mode: qwen3/deepseek reasoning models stream their
        # internal deliberation as plain text when think=None, corrupting the
        # stored atlas.  We want only the final answer.
        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.ATLAS,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        try:
            text, tokens = self.llm.generate(
                prompt, system=system, num_predict=num_predict, num_ctx=num_ctx,
                json_mode=False, temperature=0.3, think=False,
            )
            content = self._postprocess(text, max_chars)
        except Exception as e:
            logger.warning("Atlas LLM generation failed: %s — falling back to structural", e)
            return self.generate_structural()

        # Quality gate: reject extremely short output
        if len(content) < MIN_ATLAS_CHARS // 2:
            logger.warning(
                "Atlas output too short (%d chars, min %d) — falling back to structural",
                len(content), MIN_ATLAS_CHARS // 2,
            )
            return self.generate_structural()

        # Compute fingerprint for staleness detection — MUST use the full
        # module set (not the VRAM-capped prompt view) so is_stale() can
        # reproduce the same value by reading modules fresh from disk.
        fp = self._compute_fingerprint(full_modules, graph_stats)
        hub_hashes = self._compute_hub_hashes(hub_files, graph_stats)

        doc = AtlasDocument(
            content=content,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model if self.llm else "unknown",
            fingerprint=fp,
            file_count=graph_stats.get("file_count", 0),
            module_count=len(full_modules),
            char_count=len(content),
            mode="llm",
            hub_file_hashes=hub_hashes,
            segment_ids=self._current_segment_ids(),
        )

        self._save(doc)

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "Atlas generated: %d chars, %d modules, %.1fs",
            len(content), len(full_modules), duration_ms / 1000,
        )

        if progress_callback:
            progress_callback("atlas_complete", 3, 3)

        return doc

    def generate_structural(self) -> AtlasDocument:
        """Generate a structural-only Atlas from graph stats (no LLM).

        Available to all tiers. Provides basic orientation: languages,
        file counts, hub files, module domains.
        """
        graph_stats = self._load_graph_stats()
        full_modules = self._load_modules()
        modules = full_modules  # capped-for-prompt view; fingerprint uses full

        if self.llm:
            from codrag.core.context_config import detect_available_vram_gb
            vram = detect_available_vram_gb()
            cap = compute_module_cap(len(modules), available_vram_gb=vram, model=self.llm.model)
            if cap < len(modules):
                # Sort by file count descending and take top N
                modules = sorted(modules, key=lambda x: -x.get("file_count", 0))[:cap]
                logger.info("Capped atlas modules at %d (from %d) due to VRAM", cap, len(modules))

        epistemic = self._load_epistemic_summary()
        hub_files = self._identify_hubs(graph_stats)

        file_count = graph_stats.get("file_count", 0)
        if file_count < MIN_FILES_FOR_ATLAS:
            content = ""
        else:
            content = self._build_structural_content(
                graph_stats, modules, epistemic, hub_files,
            )

        fp = self._compute_fingerprint(full_modules, graph_stats)
        hub_hashes = self._compute_hub_hashes(hub_files, graph_stats)

        doc = AtlasDocument(
            content=content,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model="structural",
            fingerprint=fp,
            file_count=file_count,
            module_count=len(full_modules),
            char_count=len(content),
            mode="structural",
            hub_file_hashes=hub_hashes,
            segment_ids=self._current_segment_ids(),
        )

        self._save(doc)
        return doc

    # ── Segmented Atlas ───────────────────────────────────────────

    def generate_segmented(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[AtlasDocument, List[SegmentDocument]]:
        """Generate hierarchical atlas: root + per-segment atlases.

        Discovers segments from directory structure, generates a short root
        atlas for global orientation, then generates per-segment atlases for
        subsystem depth.

        Returns:
            (root_doc, [segment_docs]) tuple.
        """
        start = time.monotonic()

        # Discover segments
        segments = compute_segments(self.index_dir, self.project_root)
        if not segments or len(segments) < 2:
            logger.info("Too few segments (%d) — falling back to single atlas", len(segments))
            doc = self.generate(progress_callback=progress_callback)
            return doc, []

        total_steps = 1 + len(segments)  # root + each segment
        if progress_callback:
            progress_callback("atlas_segmented", 0, total_steps)

        # Load shared data
        modules = self._load_modules()

        if self.llm:
            from codrag.core.context_config import detect_available_vram_gb
            vram = detect_available_vram_gb()
            cap = compute_module_cap(len(modules), available_vram_gb=vram, model=self.llm.model)
            if cap < len(modules):
                # Sort by file count descending and take top N
                modules = sorted(modules, key=lambda x: -x.get("file_count", 0))[:cap]
                logger.info("Capped atlas modules at %d (from %d) due to VRAM", cap, len(modules))

        epistemic = self._load_epistemic_summary()
        graph_stats = self._load_graph_stats()
        hub_files = self._identify_hubs(graph_stats)

        if self.llm is None:
            logger.info("No LLM — falling back to single structural atlas")
            doc = self.generate_structural()
            return doc, []

        # Generate root atlas
        root_doc = self._generate_root_atlas(segments, graph_stats, modules)
        if progress_callback:
            progress_callback("atlas_segmented", 1, total_steps)

        # Phase 79: Swarm-orchestrated segment generation
        # Use swarm when: model supports it, swarm is enabled, and enough segments
        swarm_tier = get_swarm_tier(self.llm.provider, self.llm.model)
        swarm_threshold = get_min_groups_threshold()
        use_swarm = (
            swarm_tier.can_coordinate
            and self._get_swarm_enabled()
            and len(segments) >= swarm_threshold
        )
        if use_swarm:
            logger.info(
                "[Swarm] Atlas swarm activated: %d segments, tier=%s",
                len(segments), swarm_tier,
            )
            swarm_docs, swarm_result = self._run_swarm(
                segments, modules, epistemic, graph_stats, hub_files,
                progress_callback=progress_callback,
            )
            if swarm_docs:
                if swarm_result and swarm_result.synthesis:
                    self._write_atlas_synthesis(swarm_result)
                duration_s = time.monotonic() - start
                logger.info(
                    "Segmented atlas (swarm): root + %d segments in %.1fs",
                    len(swarm_docs), duration_s,
                )
                if progress_callback:
                    progress_callback("atlas_complete", total_steps, total_steps)
                return root_doc, swarm_docs
            logger.warning("[Swarm] Atlas swarm returned empty results — falling back to standard path")

        # Generate per-segment atlases
        # Phase 72: Use the scheduler's batch concurrency budget to
        # process multiple segments in parallel when using cloud endpoints.
        try:
            from codrag.core.batch_profiles import get_batch_concurrency
            concurrency = get_batch_concurrency(self.llm.provider, model=self.llm.model)
        except Exception as exc:
            logger.warning("get_batch_concurrency failed for atlas, falling back to sequential: %s", exc)
            concurrency = 1

        logger.info(
            "Segmented atlas: generating %d segment atlases with concurrency=%d",
            len(segments), concurrency,
        )

        segment_docs: List[SegmentDocument] = []

        if concurrency > 1 and len(segments) > 1:
            import threading
            from concurrent.futures import ThreadPoolExecutor, as_completed

            lock = threading.Lock()
            done_count = 0

            def _gen_segment(seg):
                return self._generate_segment_atlas(
                    seg, modules, epistemic, graph_stats, hub_files, segments,
                )

            with ThreadPoolExecutor(max_workers=min(concurrency, len(segments))) as pool:
                futures = {
                    pool.submit(_gen_segment, seg): seg
                    for seg in segments
                }
                for future in as_completed(futures):
                    seg = futures[future]
                    try:
                        seg_doc = future.result()
                        with lock:
                            segment_docs.append(seg_doc)
                    except Exception as e:
                        logger.warning("Failed to generate segment atlas for %s: %s", seg.id, e)

                    with lock:
                        done_count += 1
                        if progress_callback:
                            progress_callback("atlas_segmented", 1 + done_count, total_steps)
        else:
            for i, segment in enumerate(segments):
                try:
                    seg_doc = self._generate_segment_atlas(
                        segment, modules, epistemic, graph_stats, hub_files, segments,
                    )
                    segment_docs.append(seg_doc)
                except Exception as e:
                    logger.warning("Failed to generate segment atlas for %s: %s", segment.id, e)

                if progress_callback:
                    progress_callback("atlas_segmented", 2 + i, total_steps)

        duration_s = time.monotonic() - start
        logger.info(
            "Segmented atlas: root + %d segments in %.1fs (concurrency=%d)",
            len(segment_docs), duration_s, concurrency,
        )

        if progress_callback:
            progress_callback("atlas_complete", total_steps, total_steps)

        return root_doc, segment_docs

    def _generate_root_atlas(
        self,
        segments: List[Segment],
        graph_stats: Dict[str, Any],
        modules: List[Dict[str, Any]],
    ) -> AtlasDocument:
        """Generate the root atlas — global orientation header.

        Budget scales with project size (55% of full atlas budget,
        clamped 1200-2500) so it's useful on its own in the dashboard.
        """
        file_count = graph_stats.get("file_count", 0)
        target_chars = compute_root_atlas_budget(file_count)
        max_chars = int(target_chars * 1.3)

        # Format segment map
        seg_lines: List[str] = []
        for seg in segments:
            tags_str = ", ".join(seg.domain_tags[:5]) if seg.domain_tags else "(no tags)"
            seg_lines.append(f"- {seg.name} ({seg.dir_path}, {seg.file_count} files): {tags_str}")
        segment_map = "\n".join(seg_lines)

        # Format graph stats
        stats_text = self._format_graph_stats(graph_stats)

        # Cross-cutting: extract hub files and shared domain tags across segments
        hub_files = self._identify_hubs(graph_stats)
        cross_parts: List[str] = []
        if hub_files:
            # Phase 105: decorate with evidence labels when available
            hub_str = self._hub_str_with_evidence(hub_files[:5])
            cross_parts.append(f"Hub files: {hub_str}")

            # Phase 105: append Active zones line when evidence qualifies
            zones_line = self._hot_zones_line()
            if zones_line:
                cross_parts.append(zones_line)

        # Find domain tags shared across multiple segments
        tag_segments: Dict[str, int] = defaultdict(int)
        for seg in segments:
            for tag in seg.domain_tags[:5]:
                tag_segments[tag] += 1
        shared_tags = [t for t, c in sorted(tag_segments.items(), key=lambda x: -x[1]) if c >= 2]
        if shared_tags:
            cross_parts.append(f"Shared domains: {', '.join(shared_tags[:8])}")

        cross_cutting = "\n".join(cross_parts) if cross_parts else "(insufficient data)"

        system = ROOT_ATLAS_SYSTEM.format(target_chars=target_chars, max_chars=max_chars)
        prompt = ROOT_ATLAS_PROMPT.format(
            segment_map=segment_map,
            graph_stats=stats_text,
            cross_cutting=cross_cutting,
            target_chars=target_chars,
            max_chars=max_chars,
        )

        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.ATLAS,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        try:
            text, tokens = self.llm.generate(
                prompt, system=system, num_predict=num_predict, num_ctx=num_ctx,
                json_mode=False, temperature=0.3, think=False,
            )
            content = self._postprocess(text, max_chars)
        except Exception as e:
            logger.warning("Root atlas LLM failed: %s — using structural", e)
            content = ""

        # Quality gate: thinking models may produce only <think> tokens which
        # _postprocess strips, leaving empty content.  Fall back to structural.
        if len(content) < MIN_ATLAS_CHARS // 2:
            if content:
                logger.warning(
                    "Root atlas LLM output too short (%d chars) — using structural",
                    len(content),
                )
            else:
                logger.warning("Root atlas LLM output empty after postprocess — using structural")
            content = self._build_structural_content(
                graph_stats, modules, self._load_epistemic_summary(),
                self._identify_hubs(graph_stats),
            )

        # Fingerprint must be computed from the FULL module list, not the
        # VRAM-capped subset used for prompting. Otherwise is_stale() —
        # which always reads the full set — will never match the saved
        # fingerprint and the atlas reports stale immediately after a
        # successful regen. (Observed on DebateHaus, 586 files, after
        # force-regen with kimi-k2.5 LLM.)
        full_modules = self._load_modules()
        fp = self._compute_fingerprint(full_modules, graph_stats)
        hub_hashes = self._compute_hub_hashes(self._identify_hubs(graph_stats), graph_stats)

        doc = AtlasDocument(
            content=content,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model if self.llm else "structural",
            fingerprint=fp,
            file_count=graph_stats.get("file_count", 0),
            module_count=len(full_modules),
            char_count=len(content),
            mode="llm" if self.llm else "structural",
            hub_file_hashes=hub_hashes,
            segment_ids=self._current_segment_ids(),
        )

        self._save(doc)
        # Save segment manifest alongside root atlas
        self._save_segment_manifest(segments)
        return doc

    def _generate_segment_atlas(
        self,
        segment: Segment,
        all_modules: List[Dict[str, Any]],
        epistemic: Dict[str, Any],
        graph_stats: Dict[str, Any],
        hub_files: List[Tuple[str, int]],
        all_segments: List[Segment],
    ) -> SegmentDocument:
        """Generate atlas for one segment."""
        # Compute adaptive budget for this segment
        target_chars = min(
            SEGMENT_ATLAS_MAX_CHARS,
            max(SEGMENT_ATLAS_MIN_CHARS, int(segment.file_count * 8)),
        )
        max_chars = int(target_chars * 1.3)

        # Filter modules to those within this segment
        seg_file_set = set(segment.file_paths)
        seg_modules = [
            m for m in all_modules
            if any(fp in seg_file_set for fp in m.get("member_files", []))
        ]

        # Filter hub files to those within this segment
        seg_hubs = [(p, d) for p, d in hub_files if p in seg_file_set]

        # Build external dependency info: edges from this segment to others
        seg_to_other = self._compute_external_deps(segment, all_segments)

        # Format prompt data
        module_text = self._format_modules(seg_modules) if seg_modules else "(no module data for this segment)"

        # Segment-specific layer distribution
        seg_layers: Counter = Counter()
        epi_path = self.index_dir / "trace_epistemic.jsonl"
        if epi_path.exists():
            try:
                with open(epi_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                            nid = d.get("node_id", "")
                            fp = nid.replace("file:", "", 1) if nid.startswith("file:") else ""
                            if fp in seg_file_set:
                                layer = d.get("architecture_layer", "unknown")
                                seg_layers[layer] += 1
                        except json.JSONDecodeError:
                            continue
            except OSError:
                pass
        layer_text = ", ".join(f"{l}: {c}" for l, c in seg_layers.most_common(5)) if seg_layers else "(no layer data)"

        hub_text = self._format_hubs(seg_hubs) if seg_hubs else "(no hub data for this segment)"

        ext_deps_text = seg_to_other if seg_to_other else "(no cross-segment dependencies detected)"

        # Build file listing — show all files (capped at 50 to avoid prompt bloat)
        file_lines = segment.file_paths[:50]
        if len(segment.file_paths) > 50:
            file_lines.append(f"... +{len(segment.file_paths) - 50} more files")
        file_listing = "\n".join(file_lines) if file_lines else "(no files)"

        system = SEGMENT_ATLAS_SYSTEM.format(target_chars=target_chars, max_chars=max_chars)
        prompt = SEGMENT_ATLAS_PROMPT.format(
            segment_name=segment.name,
            segment_dir=segment.dir_path,
            segment_file_count=segment.file_count,
            module_summaries=module_text,
            architecture_layers=layer_text,
            hub_files=hub_text,
            file_listing=file_listing,
            external_deps=ext_deps_text,
            target_chars=target_chars,
            max_chars=max_chars,
        )

        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.ATLAS,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        try:
            text, tokens = self.llm.generate(
                prompt, system=system, num_predict=num_predict, num_ctx=num_ctx,
                json_mode=False, temperature=0.3, think=False,
            )
            content = self._postprocess(text, max_chars)
        except Exception as e:
            logger.warning("Segment atlas LLM failed for %s: %s — using structural", segment.name, e)
            content = ""

        # Quality gate: fall back to structural summary for this segment
        if len(content) < SEGMENT_ATLAS_MIN_CHARS // 2:
            logger.warning(
                "Segment atlas %s: LLM output too short (%d chars) — using structural",
                segment.name, len(content),
            )
            parts = [f"SEGMENT: {segment.name} ({segment.dir_path}, {segment.file_count} files)"]
            if seg_modules:
                mod_names = [m.get("name", "?") for m in seg_modules[:10]]
                parts.append(f"Modules: {', '.join(mod_names)}")
            if seg_hubs:
                hub_str = ", ".join(f"{p} ({d} edges)" for p, d in seg_hubs[:5])
                parts.append(f"Key files: {hub_str}")
            top_files = segment.file_paths[:15]
            parts.append(f"Files: {', '.join(top_files)}")
            content = ". ".join(parts)

        # Compute segment fingerprint
        fp = self._compute_segment_fingerprint(segment, seg_modules)

        seg_doc = SegmentDocument(
            content=content,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model,
            fingerprint=fp,
            segment_id=segment.id,
            segment_name=segment.name,
            dir_path=segment.dir_path,
            file_count=segment.file_count,
            char_count=len(content),
            mode="llm",
        )

        self._save_segment(seg_doc)
        return seg_doc

    def _generate_segment_atlas_with_angle(
        self,
        segment: Segment,
        all_modules: List[Dict[str, Any]],
        epistemic: Dict[str, Any],
        graph_stats: Dict[str, Any],
        hub_files: List[Tuple[str, int]],
        all_segments: List[Segment],
        analysis_focus: str,
        cross_segment_hints: List[str],
    ) -> SegmentDocument:
        """Generate atlas for one segment with coordinator-assigned analysis angle.

        Extends _generate_segment_atlas by appending coordinator guidance to
        the prompt before the LLM call. Used by the atlas swarm fan-out phase.
        """
        # Compute adaptive budget for this segment
        target_chars = min(
            SEGMENT_ATLAS_MAX_CHARS,
            max(SEGMENT_ATLAS_MIN_CHARS, int(segment.file_count * 8)),
        )
        max_chars = int(target_chars * 1.3)

        # Filter modules to those within this segment
        seg_file_set = set(segment.file_paths)
        seg_modules = [
            m for m in all_modules
            if any(fp in seg_file_set for fp in m.get("member_files", []))
        ]

        # Filter hub files to those within this segment
        seg_hubs = [(p, d) for p, d in hub_files if p in seg_file_set]

        # Build external dependency info
        seg_to_other = self._compute_external_deps(segment, all_segments)

        # Format prompt data
        module_text = self._format_modules(seg_modules) if seg_modules else "(no module data for this segment)"

        # Segment-specific layer distribution
        seg_layers: Counter = Counter()
        epi_path = self.index_dir / "trace_epistemic.jsonl"
        if epi_path.exists():
            try:
                with open(epi_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                            nid = d.get("node_id", "")
                            fp = nid.replace("file:", "", 1) if nid.startswith("file:") else ""
                            if fp in seg_file_set:
                                layer = d.get("architecture_layer", "unknown")
                                seg_layers[layer] += 1
                        except json.JSONDecodeError:
                            continue
            except OSError:
                pass
        layer_text = ", ".join(f"{l}: {c}" for l, c in seg_layers.most_common(5)) if seg_layers else "(no layer data)"

        hub_text = self._format_hubs(seg_hubs) if seg_hubs else "(no hub data for this segment)"
        ext_deps_text = seg_to_other if seg_to_other else "(no cross-segment dependencies detected)"

        # Build file listing
        file_lines = segment.file_paths[:50]
        if len(segment.file_paths) > 50:
            file_lines.append(f"... +{len(segment.file_paths) - 50} more files")
        file_listing = "\n".join(file_lines) if file_lines else "(no files)"

        system = SEGMENT_ATLAS_SYSTEM.format(target_chars=target_chars, max_chars=max_chars)
        prompt = SEGMENT_ATLAS_PROMPT.format(
            segment_name=segment.name,
            segment_dir=segment.dir_path,
            segment_file_count=segment.file_count,
            module_summaries=module_text,
            architecture_layers=layer_text,
            hub_files=hub_text,
            file_listing=file_listing,
            external_deps=ext_deps_text,
            target_chars=target_chars,
            max_chars=max_chars,
        )

        # Append coordinator guidance
        if cross_segment_hints:
            hints_text = "\n".join(f"- {h}" for h in cross_segment_hints)
        else:
            hints_text = "- (none identified)"
        prompt += (
            "\n\n## Coordinator Guidance\n"
            f"Analysis focus: {analysis_focus}\n"
            "Cross-segment connections to highlight:\n"
            f"{hints_text}\n"
        )

        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.ATLAS,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        try:
            text, tokens = self.llm.generate(
                prompt, system=system, num_predict=num_predict, num_ctx=num_ctx,
                json_mode=False, temperature=0.3, think=False,
            )
            content = self._postprocess(text, max_chars)
        except Exception as e:
            logger.warning(
                "Segment atlas (swarm) LLM failed for %s: %s — using structural",
                segment.name, e,
            )
            content = ""

        # Quality gate: fall back to structural summary for this segment
        if len(content) < SEGMENT_ATLAS_MIN_CHARS // 2:
            logger.warning(
                "Segment atlas (swarm) %s: LLM output too short (%d chars) — using structural",
                segment.name, len(content),
            )
            parts = [f"SEGMENT: {segment.name} ({segment.dir_path}, {segment.file_count} files)"]
            if seg_modules:
                mod_names = [m.get("name", "?") for m in seg_modules[:10]]
                parts.append(f"Modules: {', '.join(mod_names)}")
            if seg_hubs:
                hub_str = ", ".join(f"{p} ({d} edges)" for p, d in seg_hubs[:5])
                parts.append(f"Key files: {hub_str}")
            top_files = segment.file_paths[:15]
            parts.append(f"Files: {', '.join(top_files)}")
            content = ". ".join(parts)

        fp = self._compute_segment_fingerprint(segment, seg_modules)

        seg_doc = SegmentDocument(
            content=content,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model,
            fingerprint=fp,
            segment_id=segment.id,
            segment_name=segment.name,
            dir_path=segment.dir_path,
            file_count=segment.file_count,
            char_count=len(content),
            mode="llm",
        )

        self._save_segment(seg_doc)
        return seg_doc

    def _run_swarm(
        self,
        segments: List[Segment],
        all_modules: List[Dict[str, Any]],
        epistemic: Dict[str, Any],
        graph_stats: Dict[str, Any],
        hub_files: List[Tuple[str, int]],
        progress_callback: Optional[Callable[..., None]] = None,
    ) -> Tuple[List[SegmentDocument], Optional[SwarmResult]]:
        """Run swarm-orchestrated segment atlas generation.

        Returns (segment_docs, swarm_result).
        Empty list signals the caller to fall back to standard path.
        """
        # Phase 79: Swarm stages bypass the scheduler's fair-share division
        # to get the full concurrency budget. The stage still waits its turn
        # in the queue — only the worker parallelism is maximized.
        # TODO(Phase79-DualModel): pass coordinator_model and worker_model separately
        concurrency = 1
        try:
            from codrag.services.pipeline.scheduler import pipeline_scheduler
            full = pipeline_scheduler.full_budget_for_swarm(
                self.llm.provider, self.llm.model,
            )
            if full is not None:
                concurrency = full
        except (ImportError, Exception) as exc:
            logger.debug("Swarm full budget unavailable, trying batch concurrency: %s", exc)
        if concurrency <= 1:
            try:
                from codrag.core.batch_profiles import get_batch_concurrency
                concurrency = get_batch_concurrency(self.llm.provider, model=self.llm.model)
            except Exception:
                concurrency = 1
        # F-59 rework: cap concurrency for cloud-proxied models (same as
        # group_reasoning and concept_seeder).
        is_cloud = _is_cloud_endpoint(self.llm)
        if is_cloud and concurrency > 3:
            logger.info("[Swarm/Atlas] Capping concurrency %d → 3 for cloud model %s",
                        concurrency, self.llm.model)
            concurrency = 3
        logger.info("[Swarm] Atlas using concurrency=%d for fan-out", concurrency)

        # F-59 rework: set per-worker and wall-time caps to prevent
        # apparent hangs on sequential cloud endpoints.
        orch = SwarmOrchestrator(
            llm=self.llm,
            concurrency=concurrency,
            coordinator_timeout_s=10.0 if is_cloud else 90.0,
            synthesis_timeout_s=120.0,
            worker_timeout_s=120.0 if is_cloud else 300.0,
            max_wall_time_s=600.0 if is_cloud else 1800.0,
        )

        # Build WorkItems from segments
        items: List[WorkItem] = []
        seg_map: Dict[str, Segment] = {}
        for seg in segments:
            seg_map[seg.id] = seg
            summary = (
                f"{seg.dir_path} ({seg.file_count} files); "
                f"domains: {', '.join(seg.domain_tags[:5]) if seg.domain_tags else 'unknown'}"
            )
            full_context = json.dumps({
                "segment_id": seg.id,
                "name": seg.name,
                "dir_path": seg.dir_path,
                "file_count": seg.file_count,
                "file_paths": seg.file_paths[:20],
                "module_ids": seg.module_ids[:10],
                "domain_tags": seg.domain_tags,
            })
            items.append(WorkItem(id=seg.id, summary=summary, full_context=full_context))

        coordinator_prompt = (
            "You are coordinating parallel architectural analysis of {n} codebase segments.\n"
            "Each segment is a directory-based subsystem.\n\n"
            "Segments:\n{{group_summaries}}\n\n"
            "For EACH segment, assign a specific analysis_angle (architectural focus area)\n"
            "and priority_concerns (cross-segment dependencies or risks to highlight).\n\n"
            "Respond with JSON:\n"
            '{{"assignments": [{{"item_id": "seg:...", "analysis_angle": "...", '
            '"priority_concerns": ["..."]}}]}}'
        ).format(n=len(items))

        synthesis_prompt = (
            "Below are the atlas results from {n} parallel segment analyses.\n\n"
            "{{worker_outputs}}\n\n"
            "Synthesize cross-segment patterns:\n"
            '{{"cross_segment_data_flows": ["..."], '
            '"shared_dependencies": ["..."], '
            '"architectural_coherence": "high|medium|low", '
            '"key_insight": "..."}}'
        ).format(n=len(items))

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
            seg = seg_map.get(item.id)
            if seg is None:
                return None
            try:
                seg_doc = self._generate_segment_atlas_with_angle(
                    seg, all_modules, epistemic, graph_stats, hub_files, segments,
                    analysis_focus=assignment.analysis_angle,
                    cross_segment_hints=assignment.priority_concerns,
                )
                return json.dumps({
                    "segment_id": seg_doc.segment_id,
                    "dir_path": seg_doc.dir_path,
                    "content": seg_doc.content,
                    "file_count": seg_doc.file_count,
                })
            except Exception as exc:
                logger.warning("[Swarm] Worker failed for segment %s: %s", item.id, exc)
                return None

        def progress_fn(done: int, total: int) -> None:
            if progress_callback:
                progress_callback("atlas_segmented", 1 + done, 1 + total)

        result = orch.execute(
            items=items,
            coordinator_prompt=coordinator_prompt,
            worker_fn=worker_fn,
            synthesis_prompt=synthesis_prompt,
            progress_fn=progress_fn,
        )

        if result is None:
            return [], None

        # Convert worker results back to SegmentDocument objects
        seg_docs: List[SegmentDocument] = []
        for wr in result.worker_results:
            if wr.success and wr.parsed:
                try:
                    seg = seg_map.get(wr.item_id)
                    if seg is None:
                        continue
                    content = wr.parsed.get("content", "")
                    seg_file_set = set(seg.file_paths)
                    seg_modules = [
                        m for m in all_modules
                        if any(mfp in seg_file_set for mfp in m.get("member_files", []))
                    ]
                    fingerprint = self._compute_segment_fingerprint(seg, seg_modules)
                    seg_doc = SegmentDocument(
                        content=content,
                        generated_at=datetime.now(timezone.utc).isoformat(),
                        model=self.llm.model,
                        fingerprint=fingerprint,
                        segment_id=seg.id,
                        segment_name=seg.name,
                        dir_path=seg.dir_path,
                        file_count=seg.file_count,
                        char_count=len(content),
                        mode="llm",
                    )
                    seg_docs.append(seg_doc)
                except (KeyError, ValueError) as exc:
                    logger.warning("[Swarm] Failed to reconstruct SegmentDocument for %s: %s", wr.item_id, exc)

        return seg_docs, result

    def _write_atlas_synthesis(self, result: SwarmResult) -> None:
        """Write swarm atlas synthesis artifact to disk."""
        artifact = {
            "stage": "atlas_swarm_synthesis",
            "model": self.llm.model if self.llm else "unknown",
            "segments_analyzed": result.stats.total_items,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "synthesis": result.synthesis,
            "stats": {
                "workers_succeeded": result.stats.workers_succeeded,
                "workers_failed": result.stats.workers_failed,
                "wall_clock_seconds": round(result.stats.wall_clock_seconds, 1),
            },
        }
        path = self.index_dir / "atlas_swarm_synthesis.json"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2)
        logger.info("[Swarm] Atlas synthesis written to %s", path)

    def _compute_external_deps(
        self,
        segment: Segment,
        all_segments: List[Segment],
    ) -> str:
        """Compute edges from this segment's files to other segments."""
        seg_file_set = set(segment.file_paths)
        # Build reverse index: file_path → segment_name
        file_to_seg: Dict[str, str] = {}
        for s in all_segments:
            if s.id == segment.id:
                continue
            for fp in s.file_paths:
                file_to_seg[fp] = s.name

        # Count edges to other segments
        dep_counts: Counter = Counter()
        for edge_file in ("trace_edges.jsonl", "trace_inferred_edges.jsonl"):
            edge_path = self.index_dir / edge_file
            if not edge_path.exists():
                continue
            try:
                with open(edge_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                            src = d.get("source", "").replace("file:", "", 1)
                            tgt = d.get("target", "").replace("file:", "", 1)
                            if src in seg_file_set and tgt in file_to_seg:
                                dep_counts[file_to_seg[tgt]] += 1
                            elif tgt in seg_file_set and src in file_to_seg:
                                dep_counts[file_to_seg[src]] += 1
                        except json.JSONDecodeError:
                            continue
            except OSError:
                pass

        if not dep_counts:
            return ""
        parts = [f"{name}: {count} edges" for name, count in dep_counts.most_common(5)]
        return "\n".join(parts)

    def _compute_segment_fingerprint(
        self,
        segment: Segment,
        modules: List[Dict[str, Any]],
    ) -> str:
        """Compute fingerprint for one segment."""
        parts: List[str] = [f"seg:{segment.id}:files:{segment.file_count}"]
        for m in sorted(modules, key=lambda x: x.get("module_id", "")):
            s_hash = hashlib.sha256(
                m.get("summary", "").encode("utf-8")
            ).hexdigest()[:8]
            parts.append(f"{m.get('module_id', '')}:{s_hash}")
        return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:24]

    # ── Segment Selection (Query-Time) ────────────────────────────

    def build_file_to_segment_index(self) -> Dict[str, str]:
        """Build a mapping of source_path → segment_id for query-time routing.

        Loads the segment manifest from the root atlas and maps each file
        to its segment. Returns empty dict if no segments exist.
        """
        manifest = self._load_segment_manifest()
        if not manifest:
            return {}

        index: Dict[str, str] = {}
        for seg_info in manifest:
            seg_id = seg_info.get("id", "")
            for fp in seg_info.get("file_paths", []):
                index[fp] = seg_id
        return index

    def select_segments(
        self,
        source_paths: List[str],
        max_segments: int = 3,
    ) -> List[SegmentDocument]:
        """Select relevant segment atlases based on search result file paths.

        Maps source_paths to segment IDs, ranks by hit count, returns
        top segments as loaded SegmentDocument objects.
        """
        file_index = self.build_file_to_segment_index()
        if not file_index:
            return []

        # Count hits per segment
        seg_hits: Counter = Counter()
        for path in source_paths:
            seg_id = file_index.get(path)
            if seg_id:
                seg_hits[seg_id] += 1
            else:
                # Try prefix matching for paths that don't exact-match
                for fp, sid in file_index.items():
                    if path.startswith(fp.rsplit("/", 1)[0] + "/") if "/" in fp else False:
                        seg_hits[sid] += 1
                        break

        # Load and return top segments
        result: List[SegmentDocument] = []
        for seg_id, _count in seg_hits.most_common(max_segments):
            doc = self._load_segment(seg_id)
            if doc and doc.content:
                result.append(doc)
        return result

    # ── Routing (Pre-Retrieval Segment Selection) ─────────────────

    def generate_routing(
        self,
        embedder: Any,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[SegmentDescriptor]:
        """Build routing descriptors from pipeline data and embed them.

        1. Discovers segments via compute_segments()
        2. Builds structural descriptors (no LLM) via build_routing_descriptors()
        3. Embeds each descriptor's COVERS text using the project embedder
        4. Saves descriptors + embeddings to disk

        Returns list of SegmentDescriptor objects (empty if below threshold).
        """
        import numpy as np

        segments = compute_segments(self.index_dir, self.project_root)
        if not segments or len(segments) < 2:
            logger.info("Too few segments (%d) for routing", len(segments))
            return []

        # Check activation threshold
        graph_stats = self._load_graph_stats()
        file_count = graph_stats.get("file_count", 0)
        modules = self._load_modules()
        if file_count < MIN_FILES_FOR_ROUTING and len(modules) < MIN_MODULES_FOR_ROUTING:
            logger.info(
                "Below routing threshold (files=%d, modules=%d)",
                file_count, len(modules),
            )
            return []

        if progress_callback:
            progress_callback("atlas_routing", 0, len(segments) + 1)

        descriptors = build_routing_descriptors(segments, self.index_dir)
        if not descriptors:
            return []

        if progress_callback:
            progress_callback("atlas_routing", 1, len(segments) + 1)

        # Embed each descriptor's COVERS text
        embed_fn = getattr(embedder, "embed", None)
        if embed_fn is None:
            logger.warning("Embedder has no embed() method — skipping routing embeddings")
            return descriptors

        vectors: List[List[float]] = []
        for i, desc in enumerate(descriptors):
            try:
                result = embed_fn(desc.covers)
                vectors.append(result.vector)
            except Exception as e:
                logger.warning("Failed to embed descriptor %s: %s", desc.segment_id, e)
                vectors.append([])

            if progress_callback:
                progress_callback("atlas_routing", 2 + i, len(segments) + 1)

        # Filter out failed embeddings
        valid_descs: List[SegmentDescriptor] = []
        valid_vecs: List[List[float]] = []
        for desc, vec in zip(descriptors, vectors):
            if vec:
                valid_descs.append(desc)
                valid_vecs.append(vec)

        if not valid_vecs:
            logger.warning("No valid descriptor embeddings produced")
            return []

        embeddings = np.array(valid_vecs, dtype=np.float32)

        # Persist
        self._save_routing(valid_descs, embeddings, getattr(embedder, 'model_name', 'unknown'))

        logger.info(
            "Routing: %d descriptors embedded and saved",
            len(valid_descs),
        )
        return valid_descs

    def load_routing(self) -> Tuple[List[SegmentDescriptor], Optional[Any]]:
        """Load cached routing descriptors and embeddings from disk.

        Returns (descriptors, embeddings_ndarray) or ([], None) if not found.
        """
        routing_path = self.index_dir / "atlas_routing.json"
        embeddings_path = self.index_dir / "atlas_routing_embeddings.npy"

        if not routing_path.exists() or not embeddings_path.exists():
            return [], None

        try:
            with open(routing_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            descriptors = [
                SegmentDescriptor.from_dict(d)
                for d in data.get("descriptors", [])
            ]
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning("Failed to load routing descriptors: %s", e)
            return [], None

        try:
            import numpy as np
            embeddings = np.load(str(embeddings_path))
        except Exception as e:
            logger.warning("Failed to load routing embeddings: %s", e)
            return descriptors, None

        if embeddings.shape[0] != len(descriptors):
            logger.warning(
                "Routing data mismatch: %d descriptors vs %d embeddings",
                len(descriptors), embeddings.shape[0],
            )
            return [], None

        return descriptors, embeddings

    def has_routing(self) -> bool:
        """Check if routing data (descriptors + embeddings) exists on disk."""
        return (
            (self.index_dir / "atlas_routing.json").exists()
            and (self.index_dir / "atlas_routing_embeddings.npy").exists()
        )

    def get_routed_file_paths(
        self,
        selected: List[Tuple[SegmentDescriptor, float]],
    ) -> Set[str]:
        """Extract the set of all file paths from selected segments."""
        paths: Set[str] = set()
        for desc, _score in selected:
            paths.update(desc.file_paths)
        return paths

    def _save_routing(
        self,
        descriptors: List[SegmentDescriptor],
        embeddings: Any,
        embedding_model: str,
    ) -> None:
        """Save routing descriptors and embeddings atomically."""
        import numpy as np

        self.index_dir.mkdir(parents=True, exist_ok=True)
        routing_path = self.index_dir / "atlas_routing.json"
        embeddings_path = self.index_dir / "atlas_routing_embeddings.npy"

        # Save descriptors JSON
        data = {
            "version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "embedding_model": embedding_model,
            "descriptor_count": len(descriptors),
            "descriptors": [d.to_dict() for d in descriptors],
        }
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", dir=self.index_dir,
            delete=False, encoding="utf-8",
        )
        try:
            json.dump(data, tmp, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, routing_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

        # Save embeddings numpy array
        tmp_npy = tempfile.NamedTemporaryFile(
            suffix=".npy", dir=self.index_dir, delete=False,
        )
        try:
            np.save(tmp_npy, embeddings)
            tmp_npy.flush()
            os.fsync(tmp_npy.fileno())
            tmp_npy.close()
            os.rename(tmp_npy.name, embeddings_path)
        except Exception:
            try:
                os.unlink(tmp_npy.name)
            except OSError:
                pass
            raise

    def get_display_content(self) -> Tuple[str, int]:
        """Get full atlas content for dashboard display.

        Concatenates root atlas + all segment atlases into a single string
        so the frontend can render it in one card. Returns (content, char_count).

        If no segments exist, returns the root atlas content alone.
        """
        doc = self.load()
        if doc is None or not doc.content:
            return "", 0

        if not self.has_segments():
            return doc.content, len(doc.content)

        # Build: root + each segment separated by blank lines
        blocks: List[str] = [doc.content]
        seg_docs = self.load_segments()
        for seg_doc in seg_docs:
            if seg_doc.content:
                blocks.append(f"[{seg_doc.segment_name.upper()}] ({seg_doc.dir_path})\n{seg_doc.content}")

        full = "\n\n".join(blocks)
        return full, len(full)

    # ── Post-processing ─────────────────────────────────────────

    @staticmethod
    def _postprocess(text: str, max_chars: int) -> str:
        """Clean LLM output: strip markdown artifacts, normalize whitespace, truncate.

        Models often sneak in markdown despite prompt instructions. This ensures
        the stored atlas is clean plain text.
        """
        import re

        content = text.strip()

        # Strip LLM thinking tokens (e.g. <think>...</think> from reasoning models)
        content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL)
        # Also handle unclosed <think> tags (model started thinking but didn't close)
        content = re.sub(r'<think>.*', '', content, flags=re.DOTALL)
        content = content.strip()

        # Strip markdown bold/italic markers
        content = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', content)
        # Strip markdown headers (## Header → Header)
        content = re.sub(r'^#{1,4}\s+', '', content, flags=re.MULTILINE)
        # Strip markdown bullet chars (- item → item, * item → item)
        content = re.sub(r'^[\-\*]\s+', '', content, flags=re.MULTILINE)
        # Collapse triple+ newlines to double
        content = re.sub(r'\n{3,}', '\n\n', content)
        # Strip leading/trailing whitespace per line
        content = '\n'.join(line.rstrip() for line in content.split('\n'))
        content = content.strip()

        # Hard truncate at sentence boundary if over max_chars
        if len(content) > max_chars:
            truncated = content[:max_chars]
            # Try to break at last sentence end
            last_period = truncated.rfind('.')
            last_newline = truncated.rfind('\n')
            break_at = max(last_period, last_newline)
            if break_at > max_chars * 0.7:  # only if we keep >70%
                content = truncated[:break_at + 1].rstrip()
            else:
                content = truncated.rstrip()

        return content

    def load(self) -> Optional[AtlasDocument]:
        """Load cached Atlas from disk. Returns None if not found."""
        if not self.atlas_path.exists():
            return None
        try:
            with open(self.atlas_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AtlasDocument.from_dict(data)
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning("Failed to load atlas: %s", e)
            return None

    def is_stale(self) -> bool:
        """Check if the cached Atlas needs regeneration.

        Three staleness triggers:
        1. Module fingerprint changed (clusters resynthesized)
        2. Hub file content changed (core infrastructure modified)
        3. File count changed >20% (significant growth/shrinkage)
        """
        cached = self.load()
        if cached is None:
            return True

        modules = self._load_modules()
        graph_stats = self._load_graph_stats()

        if not cached.content:
            # Empty content is intentional for repos below the file threshold —
            # don't mark as stale or the pipeline will regenerate endlessly.
            if graph_stats.get("file_count", 0) >= MIN_FILES_FOR_ATLAS:
                return True
            # Below threshold: content is expected to be empty, check fingerprint
            # to detect if the repo grew past the threshold.

        # 1. Module fingerprint check
        current_fp = self._compute_fingerprint(modules, graph_stats)
        if current_fp != cached.fingerprint:
            logger.debug("Atlas stale: fingerprint changed")
            return True

        # 2. Hub file hash check
        hub_files = self._identify_hubs(graph_stats)
        current_hub_hashes = self._compute_hub_hashes(hub_files, graph_stats)
        if current_hub_hashes != cached.hub_file_hashes:
            logger.debug("Atlas stale: hub file hashes changed")
            return True

        # 3. File count growth/shrinkage >20%
        current_count = graph_stats.get("file_count", 0)
        if cached.file_count > 0:
            ratio = abs(current_count - cached.file_count) / cached.file_count
            if ratio > 0.20:
                logger.debug(
                    "Atlas stale: file count changed %.0f%% (%d → %d)",
                    ratio * 100, cached.file_count, current_count,
                )
                return True

        # 4. Segment drift check — new directories appeared or disappeared
        # Only recompute segments if trace_nodes.jsonl changed since atlas was generated
        # (compute_segments reads trace_nodes.jsonl which is O(n) for large projects)
        if cached.segment_ids:
            nodes_path = self.index_dir / "trace_nodes.jsonl"
            atlas_mtime = self.atlas_path.stat().st_mtime if self.atlas_path.exists() else 0
            if nodes_path.exists() and nodes_path.stat().st_mtime > atlas_mtime:
                current_ids = sorted(self._current_segment_ids())
                cached_ids = sorted(cached.segment_ids)
                if current_ids != cached_ids:
                    new_segments = set(current_ids) - set(cached_ids)
                    removed_segments = set(cached_ids) - set(current_ids)
                    logger.debug(
                        "Atlas stale: segment drift detected. New: %s, Removed: %s",
                        new_segments or "none", removed_segments or "none",
                    )
                    return True

        return False

    def _current_segment_ids(self) -> List[str]:
        """Compute current segment IDs from the trace graph."""
        try:
            segments = compute_segments(
                self.index_dir,
                project_root=Path(self.project_root) if self.project_root else None,
            )
            return [s.id for s in segments]
        except Exception:
            return []

    def exists(self) -> bool:
        """Check if a cached Atlas exists on disk."""
        return self.atlas_path.exists()

    # ── Fingerprinting ─────────────────────────────────────────

    def _compute_fingerprint(
        self,
        modules: List[Dict[str, Any]],
        graph_stats: Dict[str, Any],
    ) -> str:
        """Compute a stable fingerprint from module membership + file count."""
        parts: List[str] = []
        for m in sorted(modules, key=lambda x: x.get("module_id", "")):
            mid = m.get("module_id", "")
            fc = m.get("file_count", 0)
            # Include summary hash to detect re-synthesis with different content
            s_hash = hashlib.sha256(
                m.get("summary", "").encode("utf-8")
            ).hexdigest()[:8]
            parts.append(f"{mid}:{fc}:{s_hash}")
        parts.append(f"files:{graph_stats.get('file_count', 0)}")
        combined = "\n".join(parts)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:24]

    def _compute_hub_hashes(
        self,
        hub_files: List[Tuple[str, int]],
        graph_stats: Dict[str, Any],
    ) -> Dict[str, str]:
        """Get content hashes for hub files from the trace manifest."""
        manifest_hashes = graph_stats.get("file_hashes", {})
        result: Dict[str, str] = {}
        for path, _degree in hub_files[:10]:
            h = manifest_hashes.get(path)
            if h:
                result[path] = h
        return result

    # ── Data Loading ───────────────────────────────────────────

    def _load_modules(self) -> List[Dict[str, Any]]:
        """Load module entries from trace_modules.jsonl."""
        modules: List[Dict[str, Any]] = []
        path = self.index_dir / "trace_modules.jsonl"
        if not path.exists():
            return modules
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        modules.append(json.loads(line))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load modules: %s", e)
        return modules

    def _load_epistemic_summary(self) -> Dict[str, Any]:
        """Load aggregate stats from trace_epistemic.jsonl.

        Returns a summary dict with layer counts, domain tag counts,
        and average confidence — not individual entries.
        """
        layers: Counter = Counter()
        domains: Counter = Counter()
        total_conf = 0.0
        count = 0

        path = self.index_dir / "trace_epistemic.jsonl"
        if not path.exists():
            return {"layers": {}, "domains": {}, "avg_confidence": 0.0, "count": 0}

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        layer = d.get("architecture_layer", "unknown")
                        layers[layer] += 1
                        for tag in (d.get("domain_tags") or []):
                            domains[tag] += 1
                        total_conf += float(d.get("epistemic_confidence", 0.0))
                        count += 1
                    except (json.JSONDecodeError, ValueError):
                        continue
        except OSError as e:
            logger.warning("Failed to load epistemic entries: %s", e)

        return {
            "layers": dict(layers.most_common(20)),
            "domains": dict(domains.most_common(30)),
            "avg_confidence": round(total_conf / count, 3) if count else 0.0,
            "count": count,
        }

    def _load_graph_stats(self) -> Dict[str, Any]:
        """Load graph topology stats from trace manifest and node/edge files."""
        stats: Dict[str, Any] = {
            "file_count": 0,
            "node_count": 0,
            "edge_count": 0,
            "languages": {},
            "file_hashes": {},
            "node_degrees": {},  # path → in-degree
        }

        # Manifest
        manifest_path = self.index_dir / "trace_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                # Try counts.files_parsed (current format), then stats.files_indexed (legacy)
                counts = manifest.get("counts", {})
                stats["file_count"] = (
                    counts.get("files_parsed", 0)
                    or manifest.get("stats", {}).get("files_indexed", 0)
                )
                stats["file_hashes"] = manifest.get("file_hashes", {})
                # Also use file_hashes length as file_count if counts missing
                if not stats["file_count"] and stats["file_hashes"]:
                    stats["file_count"] = len(stats["file_hashes"])
            except (OSError, json.JSONDecodeError):
                pass

        # Count unique files and detect languages from extensions
        # trace_nodes.jsonl has multiple nodes per file — deduplicate
        lang_counter: Counter = Counter()
        seen_files: Set[str] = set()
        node_count = 0
        nodes_path = self.index_dir / "trace_nodes.jsonl"
        if nodes_path.exists():
            try:
                with open(nodes_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                            node_count += 1
                            fp = d.get("file_path", "")
                            if fp and fp not in seen_files:
                                seen_files.add(fp)
                                ext = Path(fp).suffix.lower()
                                if ext:
                                    lang_counter[ext] += 1
                        except json.JSONDecodeError:
                            continue
            except OSError:
                pass
        stats["node_count"] = node_count
        stats["languages"] = dict(lang_counter.most_common(15))
        # If manifest didn't provide file_count, use deduped count from nodes
        if not stats["file_count"]:
            stats["file_count"] = len(seen_files)

        # Count edges, compute in-degree, edge kinds, dir deps, cycles
        edge_count = 0
        in_degree: Counter = Counter()
        out_degree: Counter = Counter()
        edge_kind_counter: Counter = Counter()
        # OPP-S1: Track source_dir -> target_dir edges for inter-subsystem deps
        dir_edge_pairs: set = set()  # (src_dir, tgt_dir)
        # OPP-E4: Track file-level edges for cycle detection
        file_edges: Dict[str, set] = defaultdict(set)

        for edge_file in ("trace_edges.jsonl", "trace_inferred_edges.jsonl"):
            edge_path = self.index_dir / edge_file
            if not edge_path.exists():
                continue
            try:
                with open(edge_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                            edge_count += 1
                            source = d.get("source", "")
                            target = d.get("target", "")
                            kind = d.get("kind", d.get("edge_kind", "unknown"))
                            edge_kind_counter[kind] += 1

                            src_path = source.replace("file:", "", 1) if source.startswith("file:") else source
                            tgt_path = target.replace("file:", "", 1) if target.startswith("file:") else target

                            if tgt_path:
                                in_degree[tgt_path] += 1
                            if src_path:
                                out_degree[src_path] += 1

                            # Dir-level dependency tracking (OPP-S1)
                            src_dir = src_path.split("/")[0] if "/" in src_path else ""
                            tgt_dir = tgt_path.split("/")[0] if "/" in tgt_path else ""
                            if src_dir and tgt_dir and src_dir != tgt_dir:
                                dir_edge_pairs.add((src_dir, tgt_dir))

                            # File-level edges for cycle detection (OPP-E4)
                            if src_path and tgt_path:
                                file_edges[src_path].add(tgt_path)
                        except json.JSONDecodeError:
                            continue
            except OSError:
                pass
        stats["edge_count"] = edge_count
        stats["node_degrees"] = dict(in_degree.most_common(50))
        stats["edge_kinds"] = dict(edge_kind_counter.most_common(10))

        # OPP-S1: Build dir_dependencies map {src_dir: [tgt_dir1, tgt_dir2, ...]}
        dir_deps: Dict[str, List[str]] = defaultdict(list)
        for src, tgt in dir_edge_pairs:
            if tgt not in dir_deps[src]:
                dir_deps[src].append(tgt)
        stats["dir_dependencies"] = dict(dir_deps)

        # OPP-S2: Entry point detection
        _ENTRY_NAMES = {
            "main.py", "app.py", "server.py", "cli.py", "__main__.py",
            "index.ts", "index.js", "main.ts", "main.rs", "lib.rs",
            "main.go", "cmd/main.go", "manage.py", "wsgi.py", "asgi.py",
        }
        entry_points: List[str] = []
        # Files matching common entry point names
        for fp in seen_files:
            basename = fp.rsplit("/", 1)[-1] if "/" in fp else fp
            if basename in _ENTRY_NAMES:
                entry_points.append(fp)
        # Files with 0 in-degree but high out-degree (they import but aren't imported)
        if not entry_points:
            zero_in = [fp for fp in seen_files if fp not in in_degree and out_degree.get(fp, 0) >= 3]
            entry_points.extend(sorted(zero_in, key=lambda x: -out_degree.get(x, 0))[:3])
        stats["entry_points"] = entry_points[:5]

        # OPP-S4: Test directory detection
        test_dir_counter: Counter = Counter()
        _TEST_PATTERNS = {"tests", "test", "__tests__", "spec", "specs", "test_"}
        for fp in seen_files:
            parts = fp.split("/")
            for part in parts:
                if part.lower() in _TEST_PATTERNS or part.lower().startswith("test"):
                    test_dir_counter[part] += 1
                    break
        stats["test_dirs"] = dict(test_dir_counter.most_common(5))

        # OPP-E4: Simple cycle detection (file-level bidirectional edges)
        cycles: List[Tuple[str, str]] = []
        checked: set = set()
        for src, targets in file_edges.items():
            for tgt in targets:
                pair = tuple(sorted([src, tgt]))
                if pair not in checked and src in file_edges.get(tgt, set()):
                    cycles.append((src, tgt))
                    checked.add(pair)
        stats["cycle_count"] = len(cycles)
        stats["cycles"] = cycles[:5]

        # OPP-W4: Call chain visualization -- find longest import paths.
        # Uses greedy DFS (always follow highest-out-degree neighbor) to
        # avoid combinatorial explosion. O(depth * starts) worst case.
        _MAX_CHAIN_DEPTH = 8
        call_chains: List[List[str]] = []
        chain_starts = entry_points[:3] if entry_points else [
            fp for fp, _ in sorted(out_degree.items(), key=lambda x: -x[1])[:3]
        ]
        for start in chain_starts:
            if start not in file_edges:
                continue
            # Greedy DFS: at each step, follow the neighbor with highest out-degree
            chain: List[str] = [start]
            visited: set = {start}
            current = start
            for _ in range(_MAX_CHAIN_DEPTH):
                neighbors = [n for n in file_edges.get(current, set()) if n not in visited]
                if not neighbors:
                    break
                # Pick neighbor with highest out-degree (most likely to continue the chain)
                nxt = max(neighbors, key=lambda n: out_degree.get(n, 0))
                chain.append(nxt)
                visited.add(nxt)
                current = nxt
            if len(chain) >= 3:
                call_chains.append(chain)
        call_chains.sort(key=len, reverse=True)
        stats["call_chains"] = call_chains[:5]

        # Use file_count from manifest; fall back to counting file: nodes
        if stats["file_count"] == 0:
            stats["file_count"] = node_count

        return stats

    def _identify_hubs(
        self, graph_stats: Dict[str, Any], top_n: int = 10,
    ) -> List[Tuple[str, int]]:
        """Identify hub files (highest in-degree) from graph stats."""
        degrees = graph_stats.get("node_degrees", {})
        if not degrees:
            return []
        sorted_items = sorted(degrees.items(), key=lambda x: -x[1])
        return sorted_items[:top_n]

    def _hub_str_with_evidence(
        self, hubs: List[Tuple[str, int]],
    ) -> str:
        """Produce the hub-file one-liner, optionally labeled by churn."""
        from codrag.core.git_evidence import atlas_decoration_enabled
        if not atlas_decoration_enabled() or self.project_root is None:
            return ", ".join(f"{p} ({d} edges)" for p, d in hubs)

        try:
            from codrag.services.git_evidence_service import get_git_evidence
            evidence = get_git_evidence(self.project_root)
        except Exception:
            evidence = None
        if evidence is None:
            return ", ".join(f"{p} ({d} edges)" for p, d in hubs)

        def _classify(p: str) -> str:
            try:
                return evidence.classify_hub(p)
            except Exception:
                return "unknown"

        return _format_hubs_with_labels(hubs, _classify)

    def _hot_zones_line(self) -> str:
        """Produce the 'Active zones' line, or empty string."""
        from codrag.core.git_evidence import atlas_decoration_enabled
        if not atlas_decoration_enabled() or self.project_root is None:
            return ""

        try:
            from codrag.services.git_evidence_service import get_git_evidence
            evidence = get_git_evidence(self.project_root)
        except Exception:
            return ""
        if evidence is None:
            return ""

        try:
            zones = evidence.hot_zones(top_n=5, min_commits=10, depth=3)
        except Exception:
            return ""
        return _build_hot_zones_line(zones)

    # ── Prompt Formatting ──────────────────────────────────────

    def _format_modules(self, modules: List[Dict[str, Any]]) -> str:
        """Format module summaries for the LLM prompt."""
        if not modules:
            return "(no modules)"
        parts: List[str] = []
        for m in sorted(modules, key=lambda x: -x.get("file_count", 0)):
            mid = m.get("module_id", "?")
            name = m.get("name", mid)
            summary = m.get("summary", "(no summary)")
            fc = m.get("file_count", 0)
            status = m.get("component_status", "unknown")
            tags = ", ".join(m.get("domain_tags", [])[:5])
            deps = ", ".join(m.get("dependencies", [])[:5]) if m.get("dependencies") else ""
            debt = m.get("tech_debt_summary", "")

            line = f"- {name} ({fc} files, {status}): {summary}"
            if tags:
                line += f" Tags: [{tags}]."
            if deps:
                line += f" Depends on: [{deps}]."
            if debt:
                line += f" Tech debt: {debt}"
            parts.append(line)
        return "\n".join(parts)

    def _format_layers(self, epistemic: Dict[str, Any]) -> str:
        """Format architecture layer distribution."""
        layers = epistemic.get("layers", {})
        if not layers:
            return "(no layer data)"
        parts = [f"{layer}: {count} files" for layer, count in
                 sorted(layers.items(), key=lambda x: -x[1])]
        return ", ".join(parts)

    def _format_graph_stats(self, stats: Dict[str, Any]) -> str:
        """Format graph statistics for LLM atlas prompt.

        Phase 50: Enhanced with edge kinds, entry points, test dirs,
        cycle info, and dir dependencies for OPP-E1..E5.
        """
        parts: List[str] = [
            f"Files: {stats.get('file_count', 0)}",
            f"Graph nodes: {stats.get('node_count', 0)}",
            f"Graph edges: {stats.get('edge_count', 0)}",
        ]
        langs = stats.get("languages", {})
        if langs:
            lang_parts = [f"{ext}: {count}" for ext, count in
                         sorted(langs.items(), key=lambda x: -x[1])[:8]]
            parts.append(f"Languages: {', '.join(lang_parts)}")
        # OPP-E3: Edge kind breakdown
        edge_kinds = stats.get("edge_kinds", {})
        if edge_kinds:
            kind_parts = [f"{k}: {v}" for k, v in sorted(edge_kinds.items(), key=lambda x: -x[1])[:5]]
            parts.append(f"Edge types: {', '.join(kind_parts)}")
        # OPP-S2: Entry points
        entry_points = stats.get("entry_points", [])
        if entry_points:
            parts.append(f"Entry points: {', '.join(entry_points[:5])}")
        # OPP-S4: Test directories
        test_dirs = stats.get("test_dirs", {})
        if test_dirs:
            td_parts = [f"{d}/ ({c} files)" for d, c in sorted(test_dirs.items(), key=lambda x: -x[1])[:3]]
            parts.append(f"Test dirs: {', '.join(td_parts)}")
        # OPP-E4: Cycles
        cycle_count = stats.get("cycle_count", 0)
        if cycle_count > 0:
            parts.append(f"Import cycles: {cycle_count}")
        # OPP-S1/E5: Dir-level dependencies
        dir_deps = stats.get("dir_dependencies", {})
        if dir_deps:
            dep_parts = []
            for src, targets in sorted(dir_deps.items())[:6]:
                dep_parts.append(f"{src} -> {', '.join(targets[:3])}")
            parts.append(f"Directory dependencies: {'; '.join(dep_parts)}")
        # OPP-W4: Call chains
        call_chains = stats.get("call_chains", [])
        if call_chains:
            chain_strs = [" -> ".join(c) for c in call_chains[:3]]
            parts.append(f"Longest import chains: {'; '.join(chain_strs)}")
        return ". ".join(parts)

    def _format_hubs(self, hub_files: List[Tuple[str, int]]) -> str:
        """Format hub files list."""
        if not hub_files:
            return "(no hub data)"
        parts = [f"{path} ({degree} incoming edges)" for path, degree in hub_files[:10]]
        return "\n".join(parts)

    # ── Structural Content Builder ─────────────────────────────

    def _build_structural_content(
        self,
        graph_stats: Dict[str, Any],
        modules: List[Dict[str, Any]],
        epistemic: Dict[str, Any],
        hub_files: List[Tuple[str, int]],
    ) -> str:
        """Build structural-only Atlas content (no LLM).

        Uses the same section format as the LLM-generated atlas (IDENTITY,
        STACK, SUBSYSTEMS, HUB FILES) so that when the LLM atlas replaces
        this preliminary version, the AI sees richer content in the same
        familiar structure.

        Phase 50 OPP-S1..S4: Enhanced with inter-subsystem dependency
        arrows, entry point detection, language percentages, and test
        directory detection. See ATLAS_OPPORTUNITIES.md for research basis.
        """
        sections: List[str] = []

        file_count = graph_stats.get("file_count", 0)
        node_count = graph_stats.get("node_count", 0)
        edge_count = graph_stats.get("edge_count", 0)

        # IDENTITY: Project name (from project_root dir name if available)
        if self.project_root:
            sections.append(f"IDENTITY: {self.project_root.name}")

        # OPP-S3: STACK with language percentages instead of raw counts
        langs = graph_stats.get("languages", {})
        if langs:
            top_langs = sorted(langs.items(), key=lambda x: -x[1])[:8]
            total_files = sum(c for _, c in top_langs) or 1
            lang_parts = []
            for ext, count in top_langs:
                pct = round(100 * count / total_files)
                lang_parts.append(f"{ext} {pct}%")
            sections.append(f"STACK: {', '.join(lang_parts)}")

        # STRUCTURE: Graph topology
        sections.append(f"STRUCTURE: {file_count} files, {node_count} nodes, {edge_count} edges")

        # OPP-E3: Edge kind summary (available from Stage 1)
        edge_kinds = graph_stats.get("edge_kinds", {})
        if edge_kinds:
            kind_parts = [f"{k}: {v}" for k, v in sorted(edge_kinds.items(), key=lambda x: -x[1])[:5]]
            sections.append(f"EDGE TYPES: {', '.join(kind_parts)}")

        # OPP-E4: Circular dependency warnings
        cycle_count = graph_stats.get("cycle_count", 0)
        if cycle_count > 0:
            cycles = graph_stats.get("cycles", [])
            if cycles:
                cycle_str = "; ".join(f"{a} <-> {b}" for a, b in cycles[:3])
                sections.append(f"CIRCULAR DEPS ({cycle_count}): {cycle_str}")
            else:
                sections.append(f"CIRCULAR DEPS: {cycle_count} import cycles detected")

        # OPP-S2: Entry points (files with 0 in-degree that import many things,
        # or files matching common entry point names)
        entry_points = graph_stats.get("entry_points", [])
        if entry_points:
            ep_str = ", ".join(entry_points[:5])
            sections.append(f"ENTRY POINTS: {ep_str}")

        # SUBSYSTEMS: Directory-based segments (available from Stage 1 data)
        # If modules exist (Stage 8+), use those. Otherwise fall back to
        # compute_segments() which groups files by directory from trace_nodes.
        subsystem_dirs: List[str] = []  # collected for OPP-S1
        if modules:
            mod_lines = []
            for m in sorted(modules, key=lambda x: -x.get("file_count", 0))[:10]:
                name = m.get("name", m.get("module_id", "?"))
                fc = m.get("file_count", 0)
                summary = m.get("summary", "")
                tags = ", ".join(m.get("domain_tags", [])[:3])
                line = f"  {name} ({fc} files)"
                if summary:
                    line += f" -- {summary[:80]}"
                elif tags:
                    line += f" -- {tags}"
                mod_lines.append(line)
                subsystem_dirs.append(name)
            if mod_lines:
                sections.append("SUBSYSTEMS:\n" + "\n".join(mod_lines))
        else:
            # No modules yet -- use directory-based segment detection
            try:
                segments = compute_segments(self.index_dir, self.project_root)
                if segments:
                    seg_lines = []
                    for seg in segments[:10]:
                        seg_lines.append(f"  {seg.dir_path}/ ({seg.file_count} files)")
                        subsystem_dirs.append(seg.dir_path)
                    sections.append("SUBSYSTEMS:\n" + "\n".join(seg_lines))
            except Exception:
                logger.debug("compute_segments failed in structural atlas (non-fatal)", exc_info=True)

        # OPP-S1: Inter-subsystem dependency arrows from trace_edges.jsonl
        dir_deps = graph_stats.get("dir_dependencies", {})
        if dir_deps and subsystem_dirs:
            dep_lines = []
            for src_dir in subsystem_dirs[:8]:
                targets = dir_deps.get(src_dir, [])
                if targets:
                    # Only show targets that are also known subsystems
                    known = [t for t in targets if t in subsystem_dirs and t != src_dir]
                    if known:
                        dep_lines.append(f"  {src_dir} -> {', '.join(known[:4])}")
            if dep_lines:
                sections.append("DEPENDENCIES:\n" + "\n".join(dep_lines))

        # OPP-S4: Test directory detection
        test_dirs = graph_stats.get("test_dirs", {})
        if test_dirs:
            test_parts = [f"{d}/ ({c} files)" for d, c in
                         sorted(test_dirs.items(), key=lambda x: -x[1])[:3]]
            sections.append(f"TESTS: {', '.join(test_parts)}")

        # Architecture layers (from epistemic data, Stage 6+)
        layers = epistemic.get("layers", {})
        if layers:
            top_layers = sorted(layers.items(), key=lambda x: -x[1])[:5]
            layer_str = ", ".join(f"{layer}: {count}" for layer, count in top_layers)
            sections.append(f"LAYERS: {layer_str}")

        # HUB FILES: Highest connectivity (available from Stage 1)
        if hub_files:
            # Phase 105: decorate with evidence labels when available (parity with LLM path)
            hub_str = self._hub_str_with_evidence(hub_files[:5])
            sections.append(f"HUB FILES: {hub_str}")

        # OPP-W4: Call chain visualization (longest import paths)
        call_chains = graph_stats.get("call_chains", [])
        if call_chains:
            chain_lines = []
            for chain in call_chains[:3]:
                chain_lines.append("  " + " -> ".join(chain))
            sections.append("CALL CHAINS:\n" + "\n".join(chain_lines))

        # OPP-E6: Confidence/quality indicators (from epistemic data, Stage 6+)
        avg_conf = epistemic.get("avg_confidence", 0.0)
        ep_count = epistemic.get("count", 0)
        if avg_conf > 0 and ep_count > 0:
            sections.append(f"CONFIDENCE: {avg_conf:.2f} avg across {ep_count} files")

        # Domain tags (from epistemic data, Stage 6+)
        domains = epistemic.get("domains", {})
        if domains:
            top_domains = sorted(domains.items(), key=lambda x: -x[1])[:8]
            domain_str = ", ".join(f"{tag}" for tag, _ in top_domains)
            sections.append(f"DOMAINS: {domain_str}")

        return "\n".join(sections)

    # ── Persistence ────────────────────────────────────────────

    def _save(self, doc: AtlasDocument) -> None:
        """Save Atlas atomically, preserving previous version."""
        self.index_dir.mkdir(parents=True, exist_ok=True)

        # Rotate: current → prev
        if self.atlas_path.exists():
            try:
                os.replace(str(self.atlas_path), str(self.atlas_prev_path))
            except OSError:
                pass

        # Write new atlas atomically
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", dir=self.index_dir,
            delete=False, encoding="utf-8",
        )
        try:
            json.dump(doc.to_dict(), tmp, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, self.atlas_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    def load_previous(self) -> Optional[AtlasDocument]:
        """Load previous Atlas version (for diff detection)."""
        if not self.atlas_prev_path.exists():
            return None
        try:
            with open(self.atlas_prev_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AtlasDocument.from_dict(data)
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    # ── Segment Persistence ────────────────────────────────────

    def _save_segment(self, doc: SegmentDocument) -> None:
        """Save a segment atlas atomically."""
        self.segments_dir.mkdir(parents=True, exist_ok=True)
        target = self.segments_dir / f"seg_{doc.segment_id}.json"

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", dir=self.segments_dir,
            delete=False, encoding="utf-8",
        )
        try:
            json.dump(doc.to_dict(), tmp, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, target)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    def _load_segment(self, segment_id: str) -> Optional[SegmentDocument]:
        """Load a cached segment atlas."""
        path = self.segments_dir / f"seg_{segment_id}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SegmentDocument.from_dict(data)
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning("Failed to load segment %s: %s", segment_id, e)
            return None

    def load_segments(self) -> List[SegmentDocument]:
        """Load all cached segment atlases."""
        if not self.segments_dir.exists():
            return []
        docs: List[SegmentDocument] = []
        for path in sorted(self.segments_dir.glob("seg_*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                docs.append(SegmentDocument.from_dict(data))
            except (json.JSONDecodeError, KeyError, OSError):
                continue
        return docs

    def _save_segment_manifest(self, segments: List[Segment]) -> None:
        """Save the segment manifest as a companion file to atlas.json."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.index_dir / "atlas_segments_manifest.json"
        manifest = [s.to_dict() for s in segments]

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", dir=self.index_dir,
            delete=False, encoding="utf-8",
        )
        try:
            json.dump(manifest, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, manifest_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    def _load_segment_manifest(self) -> List[Dict[str, Any]]:
        """Load the segment manifest."""
        manifest_path = self.index_dir / "atlas_segments_manifest.json"
        if not manifest_path.exists():
            return []
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def has_segments(self) -> bool:
        """Check if segmented atlases exist."""
        manifest_path = self.index_dir / "atlas_segments_manifest.json"
        return manifest_path.exists() and self.segments_dir.exists()

    def get_role_atlas(
        self,
        role: str,
        *,
        overrides: Optional[Any] = None,
        pinned_concepts: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Return a role-filtered sub-atlas.

        When no overrides or pinned concepts are supplied, the cached
        copy (``atlas_roles/{role_id}.txt``) is returned if present.
        Any override forces a live projection since the cache represents
        the default RoleVector shape.

        Args:
            role: Free-form role name (e.g. "CEO", "design engineer",
                  "Senior QA Lead", "security").
            overrides: Optional ``RoleOverride`` layered on top of the
                built-in RoleVector (Phase 104). ``None`` → use defaults.
            pinned_concepts: Optional list of ``{"title", "content"}``
                concept dicts rendered as a preamble before the projection.

        Returns:
            A role-appropriate sub-atlas string, compressed to the
            role's character budget.
        """
        # Cache is only valid for the default role vector — any override
        # or pin necessarily invalidates it.
        if not overrides and not pinned_concepts:
            cached = self.load_cached_role_atlas(role)
            if cached:
                return cached

        # Live generation
        from .role_projection import project_atlas_for_role
        from .role_resolver import resolve_role

        role_vector = resolve_role(role)
        doc = self.load()
        base_content = doc.content if doc else ""
        return project_atlas_for_role(
            role_vector,
            self.index_dir,
            base_content,
            overrides=overrides,
            pinned_concepts=pinned_concepts,
        )

    def cache_role_atlases(self) -> Dict[str, int]:
        """Pre-generate and cache role sub-atlases for all built-in roles.

        Writes to index_dir/atlas_roles/{role_id}.txt.
        Called after atlas generation (Stage 9) and after structural
        atlas generation (Stage 1) for the fast-path fallback.

        Returns:
            Mapping of role_id → char_count for each cached atlas.
        """
        from .role_projection import project_atlas_for_role
        from .role_resolver import resolve_role
        from .role_vectors import BUILT_IN_ROLES

        roles_dir = self.index_dir / "atlas_roles"
        roles_dir.mkdir(parents=True, exist_ok=True)

        doc = self.load()
        base_content = doc.content if doc else ""

        results: Dict[str, int] = {}
        for role_id in BUILT_IN_ROLES:
            try:
                role_vector = resolve_role(role_id)
                content = project_atlas_for_role(
                    role_vector, self.index_dir, base_content,
                )
                # Write atomically
                role_path = roles_dir / f"{role_id}.txt"
                tmp_path = role_path.with_suffix(".tmp")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(content)
                tmp_path.replace(role_path)
                results[role_id] = len(content)
            except Exception as e:
                logger.debug("Failed to cache role atlas for %s: %s", role_id, e)

        logger.info(
            "Cached %d role sub-atlases in %s",
            len(results), roles_dir,
        )
        return results

    def load_cached_role_atlas(self, role: str) -> Optional[str]:
        """Load a cached role sub-atlas from disk.

        Args:
            role: Free-form role name (resolved to find cache key).

        Returns:
            Cached atlas content, or None if not cached or stale.
        """
        from .role_resolver import resolve_role

        role_vector = resolve_role(role)
        role_id = role_vector.role_id

        role_path = self.index_dir / "atlas_roles" / f"{role_id}.txt"
        if not role_path.exists():
            return None

        # Staleness check: if the base atlas is newer than this cache,
        # the cache is stale.
        if self.atlas_path.exists():
            atlas_mtime = self.atlas_path.stat().st_mtime
            cache_mtime = role_path.stat().st_mtime
            if atlas_mtime > cache_mtime:
                logger.debug(
                    "Role atlas cache stale for %s (atlas: %.0f > cache: %.0f)",
                    role_id, atlas_mtime, cache_mtime,
                )
                return None

        try:
            return role_path.read_text(encoding="utf-8")
        except OSError:
            return None

    def clear_role_cache(self) -> int:
        """Remove all cached role sub-atlases.

        Returns:
            Number of cache files removed.
        """
        roles_dir = self.index_dir / "atlas_roles"
        if not roles_dir.exists():
            return 0

        removed = 0
        for f in roles_dir.glob("*.txt"):
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
        return removed

