"""
PostFlightActions — Actions that run after pipeline stages complete.

Phase 72 Stage 3: Extracted from orchestrator.py. These are callbacks
triggered by stage completion events, not core orchestration logic.

- Atlas generation (preliminary after structural, full after atlas stage)
- IDE rules file regeneration
- CodeIndex build triggering
- Deepening convergence retrigger
- MCP atlas signal writing
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .manifest_store import ManifestStore

logger = logging.getLogger(__name__)

# Deepening convergence thresholds
DEEPENING_CONVERGE_TARGET = 0.70
DEEPENING_RETRIGGER_DELAY = 30.0  # seconds


class PostFlightActions:
    """Actions triggered after pipeline stages complete.

    All methods are static — no instance state. The orchestrator calls
    these as post-completion hooks from _on_build_transition and
    _advance_pipeline.
    """

    @staticmethod
    def write_atlas_signal(idx_dir: Path) -> None:
        """Write a timestamp signal so the MCP server detects atlas changes."""
        try:
            signal_path = Path(str(idx_dir)) / "atlas_updated.signal"
            signal_path.write_text(str(time.time()), encoding="utf-8")
        except Exception:
            pass  # Non-fatal

    @staticmethod
    def generate_preliminary_atlas_and_rules(project_id: str) -> None:
        """Generate a structural-only atlas and write/update IDE rules files.

        Called after Stage 1 (STRUCTURAL) completes. Takes ~100ms (no LLM).
        Non-fatal — never blocks the pipeline.
        """
        try:
            from prep.core.atlas import CodebaseAtlas
            from prep.core.project_registry import project_index_dir
            from prep.core.rules_generator import write_rules_file
            from prep.services.project_helpers import require_project

            project = require_project(project_id)
            idx_dir = project_index_dir(project)

            nodes_path = idx_dir / "trace_nodes.jsonl"
            if not nodes_path.exists() or nodes_path.stat().st_size == 0:
                logger.debug("trace_nodes.jsonl missing after Stage 1 — skipping preliminary atlas")
                return

            atlas = CodebaseAtlas(idx_dir, llm=None, project_root=Path(project.path))

            # If a full LLM atlas already exists, reuse it instead of downgrading
            existing_doc = atlas.load()
            if existing_doc and existing_doc.mode == "llm" and existing_doc.content:
                logger.info(
                    "Phase 50: Existing LLM atlas found for %s — reusing for rules file",
                    project_id,
                )
                doc = existing_doc
            else:
                doc = atlas.generate_structural()

            if not doc or not doc.content:
                logger.debug("Structural atlas empty for %s — writing rules without atlas", project_id)

            store = ManifestStore(Path(idx_dir))
            stats = store.read_graph_stats()
            if doc and doc.file_count:
                stats.setdefault("node_count", doc.file_count)

            pcfg = project.config or {}
            included_paths = pcfg.get("included_paths") or []
            is_prelim = not (existing_doc and existing_doc.mode == "llm")

            write_rules_file(
                project_path=Path(project.path),
                project_name=project.name or project_id,
                atlas_content=doc.content if doc else "",
                included_paths=included_paths if included_paths else None,
                is_preliminary=is_prelim,
                stats=stats,
                ide="auto",
                project_id=project_id,
            )
            PostFlightActions.write_atlas_signal(idx_dir)

            # Cache role sub-atlases from structural data
            try:
                role_cache = atlas.cache_role_atlases()
                logger.info("Phase 64A: Preliminary role atlases cached — %d roles", len(role_cache))
            except Exception:
                logger.debug("Phase 64A: Preliminary role atlas caching failed (non-fatal)", exc_info=True)

            logger.info(
                "Phase 50: Preliminary atlas + rules file written for %s (%d chars)",
                project_id,
                doc.char_count if doc else 0,
            )
        except Exception:
            logger.debug(
                "Phase 50: Preliminary atlas generation failed for %s (non-fatal)",
                project_id,
                exc_info=True,
            )

    @staticmethod
    def regenerate_rules_with_full_atlas(project_id: str) -> None:
        """Regenerate IDE rules files with the full LLM-generated atlas.

        Called after Stage 9 (ATLAS) completes. Non-fatal.
        """
        try:
            from prep.core.atlas import CodebaseAtlas
            from prep.core.project_registry import project_index_dir
            from prep.core.rules_generator import write_rules_file
            from prep.services.project_helpers import require_project

            project = require_project(project_id)
            idx_dir = project_index_dir(project)

            atlas = CodebaseAtlas(idx_dir)
            doc = atlas.load()

            if not doc or not doc.content:
                logger.debug("No atlas.json found after Stage 9 for %s — skipping rules regen", project_id)
                return

            store = ManifestStore(Path(idx_dir))
            stats = store.read_graph_stats()
            if doc.file_count:
                stats.setdefault("node_count", doc.file_count)

            pcfg = project.config or {}
            included_paths = pcfg.get("included_paths") or []

            write_rules_file(
                project_path=Path(project.path),
                project_name=project.name or project_id,
                atlas_content=doc.content,
                included_paths=included_paths if included_paths else None,
                is_preliminary=False,
                stats=stats,
                ide="auto",
                project_id=project_id,
            )
            PostFlightActions.write_atlas_signal(idx_dir)

            logger.info(
                "Phase 50: Rules file updated with full LLM atlas for %s (%d chars, mode=%s)",
                project_id,
                doc.char_count,
                doc.mode,
            )
        except Exception:
            logger.debug(
                "Phase 50: Rules file regen failed for %s (non-fatal)",
                project_id,
                exc_info=True,
            )

    @staticmethod
    def trigger_code_index_build(project_id: str, pfl: Any = None) -> None:
        """Trigger a CodeIndex build after deep enrichment completes."""
        try:
            from prep.services.project_helpers import get_project_activity_status

            if get_project_activity_status(project_id) != "active":
                logger.info("Skipping CodeIndex build for %s — project not active", project_id)
                return
        except Exception:
            pass

        try:
            from prep.services.build_manager import build_manager
            from prep.services.project_helpers import compute_index_membership, require_project

            project = require_project(project_id)
            cfg = project.config or {}
            include_globs = cfg.get("include_globs") or None
            exclude_globs = cfg.get("exclude_globs") or None
            max_file_bytes = int(cfg.get("max_file_bytes") or 500_000)
            hard_limit_bytes = int(cfg.get("hard_limit_bytes") or 100_000_000)
            included_paths = sorted(compute_index_membership(project_id)) or None

            started = build_manager.start_project_build(
                project,
                None,
                include_globs,
                exclude_globs,
                max_file_bytes,
                hard_limit_bytes,
                included_paths=included_paths,
            )
            logger.info("CodeIndex build triggered for %s after pipeline: started=%s", project_id, started)
            if pfl:
                pfl.log("code_index", f"CodeIndex build triggered: started={started}")
        except Exception as e:
            logger.warning("Failed to trigger CodeIndex build for %s: %s", project_id, e)
            if pfl:
                pfl.log("code_index", f"CodeIndex build FAILED: {e}")

    @staticmethod
    def maybe_retrigger_deepening(
        project_id: str,
        is_deep_auto_fn: Callable[[str], bool],
        run_deepening_fn: Callable[[str], bool],
        pfl: Any = None,
    ) -> None:
        """Re-trigger deep enrichment if auto mode is on and deepening hasn't converged."""
        if not is_deep_auto_fn(project_id):
            return

        try:
            from prep.core import EpistemicEnricher, LLMClient
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project

            project = require_project(project_id)
            idx_dir = project_index_dir(project)

            modules_path = idx_dir / "trace_modules.jsonl"
            if not modules_path.exists() or modules_path.stat().st_size == 0:
                return

            enricher = EpistemicEnricher(
                llm=LLMClient("http://localhost:11434", "none"),
                repo_root=Path(project.path),
                index_dir=idx_dir,
            )
            scores = enricher.compute_all_scores()
            if not scores:
                return
            composites = [s.composite for s in scores.values()]
            settled_count = sum(1 for c in composites if c >= 0.60)
            settled = settled_count / len(composites) if composites else 0.0
        except Exception:
            logger.debug("Could not compute settled_ratio for %s — skipping retrigger", project_id, exc_info=True)
            return

        if settled >= DEEPENING_CONVERGE_TARGET:
            logger.info(
                "Deepening converged for %s (%.1f%% >= %.1f%%) — no retrigger",
                project_id,
                settled * 100,
                DEEPENING_CONVERGE_TARGET * 100,
            )
            if pfl:
                pfl.log("deepening", f"Converged: {settled*100:.1f}%")
            return

        try:
            from prep.services.pipeline_budget import budget as _budget

            if not _budget.check_allowed(project_id):
                logger.info("Budget exhausted for %s — deferring retrigger", project_id)
                return
        except Exception:
            pass

        logger.info(
            "Scheduling deepening retrigger for %s in %.0fs (settled=%.1f%%)",
            project_id,
            DEEPENING_RETRIGGER_DELAY,
            settled * 100,
        )
        if pfl:
            pfl.log("deepening", f"Re-trigger in {DEEPENING_RETRIGGER_DELAY:.0f}s (settled={settled*100:.1f}%)")

        def _retrigger():
            try:
                started = run_deepening_fn(project_id)
                logger.info("Deepening retrigger for %s: started=%s", project_id, started)
            except Exception as e:
                logger.warning("Deepening retrigger failed for %s: %s", project_id, e)

        timer = threading.Timer(DEEPENING_RETRIGGER_DELAY, _retrigger)
        timer.daemon = True
        timer.start()

    # Phase 96E: trigger_concept_seeding removed — the CONCEPTS stage
    # (stage 13) in the Finalize group now handles concept seeding
    # synchronously as a proper pipeline stage.  Concept workers are
    # defined in workers.py:_concepts_worker.
