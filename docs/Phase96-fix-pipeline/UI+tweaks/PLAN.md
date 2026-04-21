# Pipeline 3x5 Reorganization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the pipeline from 11 sequential stages (2 groups) into 15 stages (3 groups of 5): Sync, Enrich, Finalize — promoting existing post-pipeline tools into first-class stages.

**Architecture:** Move Atlas from Deep Enrichment to a new Finalize group. Wrap existing post-flight code (rules generation, concept seeding, audit, antibody derivation) as pipeline workers with standard progress reporting. The Finalize group uses wave-based dispatch: Atlas first, then Rules+Concepts+Audit in parallel, then Antibodies. Frontend gets a third group section with the same auto/manual toggle pattern.

**Tech Stack:** Python (FastAPI, Pydantic), TypeScript/React (Tailwind, Lucide icons), pytest

**Spec:** `docs/Phase96-fix-pipeline/UI+tweaks/PIPELINE_15_STAGE_REORGANIZATION.md`

---

## File Map

### Backend — Modified
| File | Responsibility |
|------|---------------|
| `src/prep/services/pipeline/stages.py` | Stage enum, group constants, all mapping dicts |
| `src/prep/services/pipeline/workers.py` | Worker factory + worker functions (add 4 new workers) |
| `src/prep/services/build_orchestrator.py` | BuildType enum (add 4 new types) |
| `src/prep/services/pipeline/orchestrator.py` | 3-group state machine, wave-based Finalize dispatch, chaining |
| `src/prep/services/pipeline/post_flight.py` | Remove logic now handled by Finalize stages |
| `src/prep/api/routers/pipeline.py` | API endpoints for 3-group model, status response |

### Frontend — Modified
| File | Responsibility |
|------|---------------|
| `packages/ui/src/types.ts` | New status interfaces, 3-group PipelineStatus |
| `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` | Third group section, parallel indicator |

### Tests — Modified
| File | Responsibility |
|------|---------------|
| `tests/test_pipeline_state_machine.py` | Update stage counts, add finalize group tests |
| `tests/test_pipeline_orchestrator.py` | Update stage counts, imports, add finalize tests |

---

## Task 1: Update Stage Definitions and Group Constants

**Files:**
- Modify: `src/prep/services/pipeline/stages.py:12-57` (StageId enum, group lists)
- Modify: `src/prep/services/build_orchestrator.py:59-71` (BuildType enum)
- Test: `tests/test_pipeline_orchestrator.py:60-74`

- [ ] **Step 1: Write failing tests for the new 3-group model**

In `tests/test_pipeline_orchestrator.py`, update the existing stage count tests and add a finalize test:

```python
# Replace test_fast_sync_has_5_stages (line 60-63) — keep as-is, no change

# Replace test_deep_enrichment_has_6_stages (line 66-69) with:
def test_enrich_has_5_stages():
    assert len(ENRICH_STAGES) == 5
    assert ENRICH_STAGES[0] == StageId.ENRICHMENT
    assert ENRICH_STAGES[-1] == StageId.DEEP_KNOWLEDGE

# Add new test:
def test_finalize_has_5_stages():
    assert len(FINALIZE_STAGES) == 5
    assert FINALIZE_STAGES[0] == StageId.ATLAS
    assert FINALIZE_STAGES[-1] == StageId.ANTIBODIES

def test_all_15_stages_have_build_type_mapping():
    for stage in list(StageId):
        assert stage in STAGE_BUILD_TYPE, f"Missing build type for {stage}"
    assert len(StageId) == 15
```

Also update the imports at line 22-28 — replace `DEEP_ENRICHMENT_STAGES` with `ENRICH_STAGES` and add `FINALIZE_STAGES`:

```python
from prep.services.pipeline_orchestrator import (
    ENRICH_STAGES,
    FAST_SYNC_STAGES,
    FINALIZE_STAGES,
    STAGE_BUILD_TYPE,
    PipelineOrchestrator,
    PipelineRunPhase,
    StageId,
)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_pipeline_orchestrator.py::test_enrich_has_5_stages tests/test_pipeline_orchestrator.py::test_finalize_has_5_stages tests/test_pipeline_orchestrator.py::test_all_15_stages_have_build_type_mapping -v`

Expected: ImportError — `ENRICH_STAGES` and `FINALIZE_STAGES` don't exist yet.

- [ ] **Step 3: Add new BuildType variants**

In `src/prep/services/build_orchestrator.py`, add 4 new members to the `BuildType` enum (after line 71):

```python
class BuildType(str, enum.Enum):
    """All build types managed by the orchestrator."""
    INDEX = "index"
    TRACE = "trace"
    INFERRED_EDGES = "inferred_edges"
    AUGMENT = "augment"
    VALIDATE = "validate"
    KNOWLEDGE = "knowledge"
    EPISTEMIC = "epistemic"
    CLUSTER = "cluster"
    GROUP_REASONING = "group_reasoning"
    ATLAS = "atlas"
    DEEPENING = "deepening"
    # Finalize group (Phase 96)
    RULES = "rules"
    CONCEPTS = "concepts"
    AUDIT = "audit"
    ANTIBODIES = "antibodies"
```

- [ ] **Step 4: Update StageId enum and group constants**

In `src/prep/services/pipeline/stages.py`, update the `StageId` enum (lines 12-24). Keep all existing members, add 4 new ones, and reorder so Atlas is in the Finalize group:

```python
class StageId(str, enum.Enum):
    """The 15 pipeline stages in 3 groups of 5."""
    # ── Sync (1-5) ──
    STRUCTURAL = "structural"
    INFERRED_EDGES = "inferred_edges"
    CATALOGUE = "catalogue"
    VALIDATION = "validation"
    KNOWLEDGE = "knowledge"
    # ── Enrich (6-10) ──
    ENRICHMENT = "enrichment"
    GROUP_REASONING = "group_reasoning"
    CLUSTERING = "clustering"
    DEEPENING = "deepening"
    DEEP_KNOWLEDGE = "deep_knowledge"
    # ── Finalize (11-15) ──
    ATLAS = "atlas"
    RULES = "rules"
    CONCEPTS = "concepts"
    AUDIT = "audit"
    ANTIBODIES = "antibodies"
```

Replace the group constants (lines 42-57):

```python
FAST_SYNC_STAGES: List[StageId] = [
    StageId.STRUCTURAL,
    StageId.INFERRED_EDGES,
    StageId.CATALOGUE,
    StageId.VALIDATION,
    StageId.KNOWLEDGE,
]
# Backward-compat alias
SYNC_STAGES = FAST_SYNC_STAGES

ENRICH_STAGES: List[StageId] = [
    StageId.ENRICHMENT,
    StageId.GROUP_REASONING,
    StageId.CLUSTERING,
    StageId.DEEPENING,
    StageId.DEEP_KNOWLEDGE,
]
# Backward-compat alias
DEEP_ENRICHMENT_STAGES = ENRICH_STAGES

FINALIZE_STAGES: List[StageId] = [
    StageId.ATLAS,
    StageId.RULES,
    StageId.CONCEPTS,
    StageId.AUDIT,
    StageId.ANTIBODIES,
]
```

- [ ] **Step 5: Update all stage mapping dicts**

In `stages.py`, extend every `Dict[StageId, ...]` to include the 4 new stages. The key changes:

**STAGE_BUILD_TYPE** (lines 28-40) — add:
```python
    StageId.RULES:          BuildType.RULES,
    StageId.CONCEPTS:       BuildType.CONCEPTS,
    StageId.AUDIT:          BuildType.AUDIT,
    StageId.ANTIBODIES:     BuildType.ANTIBODIES,
```

**STAGE_INPUT_FILES** (lines 64-76) — add:
```python
    StageId.ATLAS:           ["trace_modules.jsonl"],      # unchanged, stays here
    StageId.RULES:           [],   # reads atlas.json directly, not a pipeline JSONL
    StageId.CONCEPTS:        [],   # reads atlas.json + modules + audit
    StageId.AUDIT:           ["trace_nodes.jsonl", "trace_edges.jsonl", "trace_epistemic.jsonl"],
    StageId.ANTIBODIES:      [],   # derives from concept store, not pipeline files
```

**STAGE_IS_DETERMINISTIC** (lines 79-91) — add:
```python
    StageId.RULES:           True,   # CPU template generation
    StageId.CONCEPTS:        False,  # LLM
    StageId.AUDIT:           False,  # LLM (Tier 2 synthesis built in)
    StageId.ANTIBODIES:      True,   # CPU derivation from concepts
```

**STAGE_TASK_ID** (lines 98-110) — add:
```python
    StageId.RULES:           None,          # CPU only
    StageId.CONCEPTS:        "concepts",    # uses large model
    StageId.AUDIT:           "audit",       # uses large model for Tier 2
    StageId.ANTIBODIES:      None,          # CPU only
```

**STAGE_QUEUE_TYPE** (lines 130-142) — add:
```python
    StageId.RULES:           QueueType.RUST,       # CPU only, instant
    StageId.CONCEPTS:        QueueType.LLM,        # LLM call
    StageId.AUDIT:           QueueType.LLM,        # LLM for Tier 2
    StageId.ANTIBODIES:      QueueType.RUST,       # CPU only
```

**STAGE_MANIFEST_FILE** (lines 150-162) — add:
```python
    StageId.RULES:           "rules_manifest.json",
    StageId.CONCEPTS:        "concepts_manifest.json",
    StageId.AUDIT:           "audit_manifest.json",
    StageId.ANTIBODIES:      "antibodies_manifest.json",
```

**STAGE_OUTPUT_FILE** (lines 168-180) — add:
```python
    StageId.RULES:           None,    # writes IDE files, not JSONL
    StageId.CONCEPTS:        None,    # writes to ConceptStore, not JSONL
    StageId.AUDIT:           None,    # writes audit_findings.json
    StageId.ANTIBODIES:      None,    # writes to AntibodyStore
```

**STAGE_CONFIDENCE_FIELD** (lines 185-197) — add:
```python
    StageId.RULES:           None,
    StageId.CONCEPTS:        None,
    StageId.AUDIT:           None,
    StageId.ANTIBODIES:      None,
```

**STAGE_MODEL_SLOT** (lines 199-211) — add:
```python
    StageId.RULES:           None,
    StageId.CONCEPTS:        "large",
    StageId.AUDIT:           "large",
    StageId.ANTIBODIES:      None,
```

- [ ] **Step 6: Add wave-based parallel group constant**

At the end of `stages.py`, add:

```python
# ── Finalize Wave Groups (Phase 96) ──────────────────────────────
# Stages in the same wave can run concurrently.
# Wave 0 runs first, then wave 1, then wave 2.
FINALIZE_WAVES: List[List[StageId]] = [
    [StageId.ATLAS],                                        # Wave 0: root dependency
    [StageId.RULES, StageId.CONCEPTS, StageId.AUDIT],       # Wave 1: parallel
    [StageId.ANTIBODIES],                                   # Wave 2: after concepts
]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_pipeline_orchestrator.py::test_enrich_has_5_stages tests/test_pipeline_orchestrator.py::test_finalize_has_5_stages tests/test_pipeline_orchestrator.py::test_all_15_stages_have_build_type_mapping -v`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/prep/services/pipeline/stages.py src/prep/services/build_orchestrator.py tests/test_pipeline_orchestrator.py
git commit -m "feat(P96): add 3x5 stage definitions — Sync, Enrich, Finalize

Move Atlas from Enrich to Finalize group. Add RULES, CONCEPTS,
AUDIT, ANTIBODIES as new StageId members with all mapping dicts.
Add FINALIZE_WAVES for parallel dispatch within Finalize group."
```

---

## Task 2: Create Finalize Workers

**Files:**
- Modify: `src/prep/services/pipeline/workers.py:106-147` (factory dispatch), append new worker methods
- Reference (read-only): `src/prep/services/pipeline/post_flight.py:126-178, 300-344`
- Reference (read-only): `src/prep/core/concept_seeder.py:34`
- Reference (read-only): `src/prep/core/audit/runner.py:80`
- Reference (read-only): `src/prep/core/antibody_derivation.py:115`

- [ ] **Step 1: Add Rules worker**

Append to `workers.py` after the `_deepening_worker` method (after line ~792):

```python
    @staticmethod
    def _rules_worker(project_id: str):
        """Generate/update IDE rules files (AGENTS.md, .cursor/, etc.)."""
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from prep.core.atlas import CodebaseAtlas
            from prep.core.project_registry import project_index_dir
            from prep.core.rules_generator import write_rules_file
            from prep.services.project_helpers import require_project
            from prep.services.manifest_store import ManifestStore
            from pathlib import Path

            project = require_project(project_id)
            idx_dir = project_index_dir(project)
            log_cb = WorkerFactory._logged_progress("Rules", progress_cb, project.name)

            _t0 = time.time()
            log_cb("Loading atlas", 0, 3)

            atlas = CodebaseAtlas(idx_dir)
            doc = atlas.load()

            if not doc or not doc.content:
                log_cb("No atlas available — writing structural rules", 1, 3)
                # Fall back to structural-only rules
                write_rules_file(
                    project_path=Path(project.path),
                    project_name=project.name or project_id,
                    atlas_content=None,
                    is_preliminary=True,
                    ide="auto",
                    project_id=project_id,
                )
                return {"stage": "rules", "skipped": False, "mode": "structural",
                        "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0}}

            log_cb("Generating rules files", 1, 3)
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

            log_cb("Writing atlas signal", 2, 3)
            from prep.services.pipeline.post_flight import PostFlightActions
            PostFlightActions.write_atlas_signal(idx_dir)

            log_cb("Done", 3, 3)
            return {
                "stage": "rules",
                "skipped": False,
                "mode": doc.mode,
                "atlas_chars": doc.char_count,
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
        return worker
```

- [ ] **Step 2: Add Concepts worker**

```python
    @staticmethod
    def _concepts_worker(project_id: str):
        """Seed concepts from atlas + modules + audit data."""
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from prep.core.concept_seeder import seed_concepts
            from prep.services.concept_store import concept_store

            log_cb = WorkerFactory._logged_progress("Concepts", progress_cb, "")
            _t0 = time.time()

            # Check if concepts already exist
            stats = concept_store.get_stats(project_id)
            if stats["total"] > 0:
                log_cb(f"{stats['total']} concepts already exist — skipping", 1, 1)
                return {
                    "stage": "concepts",
                    "skipped": True,
                    "existing_count": stats["total"],
                    "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
                }

            log_cb("Seeding concepts from pipeline data", 0, 1)
            result = seed_concepts(project_id)
            concepts_created = result.get("concepts_created", 0)
            questions_created = result.get("questions_created", 0)
            log_cb(f"{concepts_created} concepts, {questions_created} questions", 1, 1)

            llm_client = None
            try:
                llm_client = WorkerFactory._get_llm_client_for_task("concepts")
            except RuntimeError:
                pass

            return {
                "stage": "concepts",
                "skipped": False,
                "status": result.get("status"),
                "concepts_created": concepts_created,
                "questions_created": questions_created,
                "_model_info": _capture_model_info(llm_client) if llm_client else {},
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
        return worker
```

- [ ] **Step 3: Add Audit worker**

```python
    @staticmethod
    def _audit_worker(project_id: str):
        """Run structural audit analyzers + LLM synthesis."""
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from prep.core.audit.runner import run_audit
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
            from pathlib import Path

            project = require_project(project_id)
            idx_dir = project_index_dir(project)
            log_cb = WorkerFactory._logged_progress("Audit", progress_cb, project.name)

            _t0 = time.time()
            log_cb("Running structural analyzers", 0, 2)

            # Tier 1: structural analysis
            result = run_audit(
                index_dir=Path(idx_dir),
                project_root=Path(project.path),
                progress_callback=lambda phase, cur, tot: log_cb(phase, cur, tot),
            )

            finding_count = len(result.findings) if result.findings else 0
            log_cb(f"Tier 1 complete — {finding_count} findings", 1, 2)

            # Tier 2: LLM synthesis (built in by default per user decision)
            tier2_ok = False
            try:
                from prep.core.audit.synthesizer import AuditSynthesizer
                llm_client = WorkerFactory._get_llm_client_for_task("audit")
                synth = AuditSynthesizer(llm_client)
                log_cb("Running LLM synthesis", 1, 2)
                synth.synthesize(result, Path(idx_dir))
                tier2_ok = True
            except Exception as e:
                logger.info("[Audit] Tier 2 synthesis skipped: %s", e)

            log_cb("Done", 2, 2)
            return {
                "stage": "audit",
                "skipped": False,
                "finding_count": finding_count,
                "tier2": tier2_ok,
                "errors": result.errors if result.errors else [],
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
        return worker
```

- [ ] **Step 4: Add Antibodies worker**

```python
    @staticmethod
    def _antibodies_worker(project_id: str):
        """Derive immune system antibodies from concepts."""
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from prep.core.antibody_derivation import derive_antibodies_for_project
            from prep.services.antibody_store import antibody_store
            from prep.services.concept_store import concept_store

            log_cb = WorkerFactory._logged_progress("Antibodies", progress_cb, "")
            _t0 = time.time()

            log_cb("Loading concepts", 0, 2)
            concepts = concept_store.list_concepts(project_id)

            if not concepts:
                log_cb("No concepts to derive from — skipping", 1, 1)
                return {
                    "stage": "antibodies",
                    "skipped": True,
                    "reason": "no_concepts",
                    "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
                }

            log_cb("Deriving antibodies", 1, 2)
            antibodies = derive_antibodies_for_project(concepts)

            saved = 0
            for ab in antibodies:
                try:
                    antibody_store.save(project_id, ab)
                    saved += 1
                except Exception as e:
                    logger.debug("Failed to save antibody: %s", e)

            log_cb(f"{saved} antibodies derived", 2, 2)
            return {
                "stage": "antibodies",
                "skipped": False,
                "derived": len(antibodies),
                "saved": saved,
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
        return worker
```

- [ ] **Step 5: Update the worker factory dispatch**

In `workers.py` `create_worker()` (lines 117-140), add dispatch for the 4 new stages. Insert before the `else: raise ValueError` at line 139:

```python
        elif stage == StageId.RULES:
            base_worker = WorkerFactory._rules_worker(project_id)
        elif stage == StageId.CONCEPTS:
            base_worker = WorkerFactory._concepts_worker(project_id)
        elif stage == StageId.AUDIT:
            base_worker = WorkerFactory._audit_worker(project_id)
        elif stage == StageId.ANTIBODIES:
            base_worker = WorkerFactory._antibodies_worker(project_id)
```

- [ ] **Step 6: Run existing tests to verify no regressions**

Run: `.venv/bin/pytest tests/test_pipeline_orchestrator.py tests/test_pipeline_state_machine.py -v`

Expected: Existing tests pass (new stages don't break old ones).

- [ ] **Step 7: Commit**

```bash
git add src/prep/services/pipeline/workers.py
git commit -m "feat(P96): add Finalize workers — Rules, Concepts, Audit, Antibodies

Each worker wraps existing logic (rules_generator, concept_seeder,
audit/runner, antibody_derivation) with standard progress reporting.
Audit includes Tier 2 LLM synthesis by default."
```

---

## Task 3: Update Orchestrator for 3-Group Model

**Files:**
- Modify: `src/prep/services/pipeline/orchestrator.py` (multiple locations)
- Modify: `src/prep/services/pipeline/post_flight.py:126-178, 300-344`
- Test: `tests/test_pipeline_orchestrator.py`

This is the largest task. It touches the orchestrator's group management, chaining logic, and post-flight cleanup.

- [ ] **Step 1: Write failing test for `run_finalize()`**

Add to `tests/test_pipeline_orchestrator.py`:

```python
class TestFinalize:
    """Finalize group (stages 11-15) lifecycle tests."""

    def test_run_finalize_starts_atlas(self, pipeline, orchestrator):
        """Finalize group should start with Atlas stage."""
        with patch.multiple(
            "prep.services.pipeline.orchestrator",
            WorkerFactory=MagicMock(create_worker=MagicMock(return_value=_instant_worker)),
        ), patch("prep.services.pipeline.orchestrator.PipelineOrchestrator._detect_resume_point", return_value=0):
            started = pipeline.run_finalize("test-proj")
            assert started

    def test_finalize_has_correct_stages(self):
        """Finalize group should have exactly 5 stages in correct order."""
        assert FINALIZE_STAGES == [
            StageId.ATLAS,
            StageId.RULES,
            StageId.CONCEPTS,
            StageId.AUDIT,
            StageId.ANTIBODIES,
        ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_pipeline_orchestrator.py::TestFinalize -v`

Expected: `AttributeError: 'PipelineOrchestrator' object has no attribute 'run_finalize'`

- [ ] **Step 3: Add `run_finalize()` method to orchestrator**

In `orchestrator.py`, after the `run_deep_enrichment()` method (after line ~697), add:

```python
    def run_finalize(self, project_id: str, force_from_start: bool = False) -> bool:
        """Start the Finalize group (stages 11-15).

        Runs Atlas, then Rules+Concepts+Audit in parallel, then Antibodies.
        Auto-detects resume point from disk state.
        """
        # Don't start finalize while enrich is active
        with self._lock:
            enrich_run = self._runs.get((project_id, "deep_enrichment"))
            if enrich_run and enrich_run.is_active:
                logger.info(
                    "[%s] Skipping finalize — enrich is still active (stage=%s)",
                    project_id, enrich_run.current_stage,
                )
                return False

        resume = 0 if force_from_start else self._detect_resume_point(
            project_id, FINALIZE_STAGES, skip_mtime_cascade=True,
        )
        if resume >= len(FINALIZE_STAGES):
            logger.info("All finalize stages complete for %s — nothing to do", project_id)
            return False

        if resume > 0:
            logger.info(
                "Resuming finalize for %s from stage %d/%d (%s)",
                project_id, resume, len(FINALIZE_STAGES),
                FINALIZE_STAGES[resume].value,
            )
        return self._start_group(project_id, "finalize", FINALIZE_STAGES, resume_from=resume)
```

Import `FINALIZE_STAGES` at the top of orchestrator.py where `FAST_SYNC_STAGES` and `DEEP_ENRICHMENT_STAGES` are imported.

- [ ] **Step 4: Update `run_all()` to chain through finalize**

In `orchestrator.py`, update `run_all()` (lines 816-844). Add a `_chain_finalize` dict alongside `_chain_deep`:

At class init (near line 92 where `_chain_deep` is defined):
```python
self._chain_finalize: Dict[str, bool] = {}
```

In `run_all()`, set both chain flags:
```python
    def run_all(self, project_id: str, force_from_start: bool = False) -> bool:
        with self._lock:
            key = (project_id, "fast_sync")
            run = self._runs.get(key)
            if run and run.is_active:
                return False
            self._chain_deep[project_id] = True
            self._chain_finalize[project_id] = True
        # ... rest unchanged
```

- [ ] **Step 5: Update chaining in `_advance_pipeline()`**

In `_advance_pipeline()`, find the section where `run.group == "fast_sync"` chains to deep (lines 1448-1509). After this block, add a similar block for enrich → finalize chaining:

```python
            # Chain finalize after enrich if configured or explicitly requested
            if run.group == "deep_enrichment":
                should_chain_fin = False
                # 1. Explicit chain from run_all()
                if self._chain_finalize.pop(run.project_id, False):
                    should_chain_fin = True
                # 2. Auto-chain: check persisted pipeline config
                if not should_chain_fin:
                    is_auto = self._is_finalize_auto(run.project_id)
                    if is_auto:
                        should_chain_fin = True
                if should_chain_fin:
                    logger.info(
                        "Chaining finalize for %s after enrich completed",
                        run.project_id,
                    )
                    try:
                        self.run_finalize(run.project_id)
                    except Exception:
                        logger.debug(
                            "Finalize chain failed for %s (non-fatal)",
                            run.project_id, exc_info=True,
                        )
```

Add the auto-check method (alongside `_is_deep_enrichment_auto`, near line 1193):

```python
    @staticmethod
    def _is_finalize_auto(project_id: str) -> bool:
        """Check if finalize should auto-chain after enrich."""
        try:
            from prep.services.settings_store import settings
            config = settings.get("pipeline_config") or {}
            fin_mode = (config.get("finalize") or {}).get("mode", "manual")
            # Also auto-chain if enrich is auto (user expects full pipeline)
            enrich_mode = (config.get("deep_enrichment") or {}).get("mode", "manual")
            return fin_mode == "auto" or enrich_mode == "auto"
        except Exception:
            return False
```

- [ ] **Step 6: Update post-flight to remove rules regen and concept seeding**

In `orchestrator.py`, in `_on_build_transition()` (lines 1787-1792), remove the Atlas-specific rules regeneration:

Change lines 1791-1792 from:
```python
                elif stage == StageId.ATLAS:
                    self._regenerate_rules_with_full_atlas(project_id)
```
to:
```python
                # Atlas rules regen is now handled by the Rules stage (12) in Finalize
```

In `_advance_pipeline()`, in the `run.group == "deep_enrichment"` section (lines 1439-1446), remove the concept seeding trigger:

Change lines 1441-1442 from:
```python
                self._trigger_code_index_build(run.project_id, pfl)
                # Phase 74: Auto-seed concepts from pipeline data
                PostFlightActions.trigger_concept_seeding(run.project_id, pfl)
```
to:
```python
                self._trigger_code_index_build(run.project_id, pfl)
                # Concept seeding is now handled by the Concepts stage (13) in Finalize
```

Keep `_trigger_code_index_build` and `_maybe_retrigger_deepening` — these remain as post-Enrich actions.

- [ ] **Step 7: Update group name references**

Throughout `orchestrator.py`, update group name handling to accept "finalize" alongside "fast_sync" and "deep_enrichment". Key locations:

In `_start_group()` (line ~1222), the cross-group conflict check currently only checks fast_sync vs deep_enrichment. Add finalize:

The cross-group check logic should prevent finalize from running while enrich is active (already handled in `run_finalize()` above, but the guard in `_start_group` provides defense-in-depth).

In `_on_pipeline_group_completed()` (lines 1417-1446), add finalize completion handling:
```python
            # After finalize completes, no downstream chaining needed
            if run.group == "finalize":
                logger.info("Finalize complete for %s", run.project_id)
```

- [ ] **Step 8: Run tests**

Run: `.venv/bin/pytest tests/test_pipeline_orchestrator.py -v`

Expected: All tests pass including new TestFinalize.

- [ ] **Step 9: Commit**

```bash
git add src/prep/services/pipeline/orchestrator.py src/prep/services/pipeline/post_flight.py tests/test_pipeline_orchestrator.py
git commit -m "feat(P96): wire Finalize group into orchestrator

Add run_finalize() with enrich→finalize chaining. Remove post-flight
rules regen and concept seeding — now handled as Finalize stages.
Keep CodeIndex rebuild and deepening retrigger as post-Enrich actions."
```

---

## Task 4: Update Pipeline API for 3-Group Model

**Files:**
- Modify: `src/prep/api/routers/pipeline.py:46-70` (request models), status endpoint
- Test: manual API test (curl)

- [ ] **Step 1: Update request models to accept "finalize"**

In `pipeline.py` (lines 46-70), update the group field comments and defaults:

```python
class CancelRequest(BaseModel):
    group: str = "fast_sync"  # "fast_sync", "deep_enrichment", or "finalize"

class PauseRequest(BaseModel):
    group: str = "fast_sync"  # "fast_sync", "deep_enrichment", or "finalize"

class ResumeGroupRequest(BaseModel):
    group: str = "fast_sync"  # "fast_sync", "deep_enrichment", or "finalize"

class SwapModelRequest(BaseModel):
    group: str = "deep_enrichment"  # "fast_sync", "deep_enrichment", or "finalize"
```

- [ ] **Step 2: Add finalize endpoint**

After the existing `/pipeline/deep` endpoint, add:

```python
@router.post("/projects/{project_id}/pipeline/finalize")
async def run_finalize(project_id: str):
    """Run Finalize group (stages 11-15): Atlas, Rules, Concepts, Audit, Antibodies."""
    from prep.services.pipeline_orchestrator import pipeline_orchestrator
    started = pipeline_orchestrator.run_finalize(project_id)
    return ok({"started": started})
```

- [ ] **Step 3: Update status endpoint for 3-group response**

In the status endpoint response builder (line ~475), add the finalize group:

```python
return ok({
    "fast_sync": ...,
    "deep_enrichment": ...,
    "finalize": _serialize_group_run(orchestrator, project_id, "finalize"),
    "stages": { ... },  # all 15 stages
    "any_running": ...,
    ...
})
```

Add status data for the 4 new stages in the `stages` dict. These are simpler than the existing stages — just check if their output exists:

```python
# Rules status
rules_status = {
    "generated": bool(rules_files_exist),
    "stale": False,  # TODO: compare mtime
}

# Concepts status
try:
    from prep.services.concept_store import concept_store
    concept_stats = concept_store.get_stats(project_id)
    concepts_status = {"seeded": concept_stats["total"] > 0, "count": concept_stats["total"]}
except Exception:
    concepts_status = {"seeded": False, "count": 0}

# Audit status
audit_path = Path(idx_dir) / "audit_findings.json"
audit_status = {"exists": audit_path.exists(), "finding_count": 0}
if audit_path.exists():
    try:
        data = json.loads(audit_path.read_text())
        audit_status["finding_count"] = len(data.get("findings", []))
    except Exception:
        pass

# Antibodies status
try:
    from prep.services.antibody_store import antibody_store
    ab_list = antibody_store.list_antibodies(project_id)
    antibodies_status = {"count": len(ab_list)}
except Exception:
    antibodies_status = {"count": 0}
```

- [ ] **Step 4: Update `run_all` endpoint to include finalize**

The `/pipeline/all` endpoint should already chain through via orchestrator's `run_all()` which now sets `_chain_finalize`. No endpoint change needed — just verify.

- [ ] **Step 5: Commit**

```bash
git add src/prep/api/routers/pipeline.py
git commit -m "feat(P96): extend pipeline API for 3-group model

Add /pipeline/finalize endpoint. Update status response with finalize
group and new stage status fields. Accept 'finalize' in cancel/pause/resume."
```

---

## Task 5: Update Frontend Types

**Files:**
- Modify: `packages/ui/src/types.ts` (add new status interfaces, update PipelineStatus)

- [ ] **Step 1: Add new status interfaces**

In `types.ts`, after the existing `AtlasStatus` interface (line ~449), add:

```typescript
/** Stage 12: Rules file generation status */
export interface RulesStatus {
  generated: boolean;
  stale: boolean;
  mode?: string;
  atlas_chars?: number;
}

/** Stage 13: Concept seeding status */
export interface ConceptsStatus {
  seeded: boolean;
  count: number;
  questions?: number;
}

/** Stage 14: Structural audit status */
export interface AuditPipelineStatus {
  exists: boolean;
  finding_count: number;
  tier2: boolean;
}

/** Stage 15: Antibody derivation status */
export interface AntibodiesStatus {
  count: number;
  firing?: number;
}
```

- [ ] **Step 2: Update PipelineStatus to include finalize group**

In the `PipelineStatus` interface (line ~990), add:

```typescript
interface PipelineStatus {
  fast_sync: PipelineGroupRun | null;
  deep_enrichment: PipelineGroupRun | null;
  finalize: PipelineGroupRun | null;     // NEW
  stages: { [stage_id: string]: any };
  any_running: boolean;
  crashed_runs?: CrashedPipelineRun[];
  scheduler?: SchedulerStatus | null;
  agent?: AgentStatus | null;
  branch?: string | null;
  branch_snapshots?: any[];
  branch_state?: any | null;
}
```

- [ ] **Step 3: Update EnrichmentAutoConfig**

Find `EnrichmentAutoConfig` and add finalize mode:

```typescript
export interface EnrichmentAutoConfig {
  fastSync: boolean;
  deepEnrichment: 'manual' | 'auto' | 'scheduled' | 'threshold';
  finalize: 'manual' | 'auto';  // NEW
}
```

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/types.ts
git commit -m "feat(P96): add frontend types for Finalize group

Add RulesStatus, ConceptsStatus, AuditPipelineStatus, AntibodiesStatus
interfaces. Extend PipelineStatus with finalize group."
```

---

## Task 6: Update Frontend Pipeline Component

**Files:**
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`

- [ ] **Step 1: Update EnrichmentStageId type**

At line 22, update to include the 4 new stages:

```typescript
export type EnrichmentStageId =
  | 'structural' | 'inferred_edges' | 'catalogue' | 'validation' | 'knowledge'
  | 'enrichment' | 'group_reasoning' | 'clustering' | 'deepening' | 'deep_knowledge'
  | 'atlas' | 'rules' | 'concepts' | 'audit' | 'antibodies';
```

- [ ] **Step 2: Move Atlas from deepStages to finalizeStages**

In the stage array construction (lines 961-1010), remove the `atlas` entry from `deepStages`. Then remove the `deep_knowledge` entry too (it stays in `deepStages` but at the end — verify it's the last one after atlas removal).

After `deepStages`, add a `finalizeStages` array:

```typescript
  const finalizeStages: EnrichmentStage[] = [
    { id: 'atlas', label: 'Atlas Building', icon: Map, modelTag: 'Thinking', state: atlasState, stats: atlasStats },
    { id: 'rules', label: 'Rules Generation', icon: FileText, modelTag: 'CPU',
      state: rulesStatus?.generated ? 'complete' : 'not_built',
      stats: rulesStatus?.generated ? `${rulesStatus.mode ?? 'generated'}` : 'Not generated',
    },
    { id: 'concepts', label: 'Concept Seeding', icon: Lightbulb, modelTag: 'Thinking',
      state: conceptsStatus?.seeded ? 'complete' : 'not_built',
      stats: conceptsStatus?.seeded ? `${conceptsStatus.count} concepts` : 'Not seeded',
    },
    { id: 'audit', label: 'Structural Audit', icon: ClipboardCheck, modelTag: 'LLM',
      state: auditPipelineStatus?.exists ? 'complete' : 'not_built',
      stats: auditPipelineStatus?.exists ? `${auditPipelineStatus.finding_count} findings` : 'Not run',
    },
    { id: 'antibodies', label: 'Immune System', icon: Shield, modelTag: 'CPU',
      state: antibodiesStatus?.count ? 'complete' : 'not_built',
      stats: antibodiesStatus?.count ? `${antibodiesStatus.count} antibodies` : 'Not derived',
    },
  ];
```

Add the required icon imports at the top of the file:
```typescript
import { FileText, Lightbulb, ClipboardCheck, Shield } from 'lucide-react';
```

- [ ] **Step 3: Add props for finalize status data**

In the component props interface (lines 34-103), add props for the new stage statuses and finalize controls:

```typescript
  // Finalize status
  rulesStatus?: RulesStatus;
  conceptsStatus?: ConceptsStatus;
  auditPipelineStatus?: AuditPipelineStatus;
  antibodiesStatus?: AntibodiesStatus;
  // Finalize controls
  onRunFinalize?: () => void;
  finalizePaused?: boolean;
  finalizePausedStage?: string;
```

- [ ] **Step 4: Add provenance injection for finalize stages**

Update the provenance loop (line 1013) to include finalize:

```typescript
  for (const stage of [...fastStages, ...deepStages, ...finalizeStages]) {
    stage.provenance = lookupProvenance(stage.id, provenance);
  }
```

- [ ] **Step 5: Update group classification**

Update the group lookup (line 566-568) to include finalize:

```typescript
  const group = ['structural', 'inferred_edges', 'catalogue', 'validation', 'knowledge'].includes(stage.id)
    ? 'fast_sync'
    : ['enrichment', 'group_reasoning', 'clustering', 'deepening', 'deep_knowledge'].includes(stage.id)
    ? 'deep_enrichment'
    : 'finalize';
```

- [ ] **Step 6: Add Finalize group section to JSX**

After the Deep Enrichment section in the JSX (after line ~1200), add a divider and the Finalize group:

```tsx
      {/* Divider between groups */}
      <div className="border-t border-border" />

      {/* ── Finalize Group ──────────────────────────── */}
      <div className="flex items-center justify-between py-1.5 px-1">
        <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">Finalize</span>
        <div className="flex items-center gap-2">
          {finalizePaused && onResumePipeline && (
            <button
              onClick={() => onResumePipeline('finalize')}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
              title="Resume from where it paused"
            >
              <Play className="w-3.5 h-3.5" />
              Resume
            </button>
          )}
          {onRunFinalize && !finalizePaused && (
            <button
              onClick={inactive ? undefined : onRunFinalize}
              disabled={finalizeRunning || limitReached || inactive}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
                (finalizeRunning || limitReached || inactive)
                  ? "border-border bg-surface text-text-subtle cursor-not-allowed"
                  : "border-success/40 bg-success/10 text-success hover:bg-success/20"
              )}
            >
              <Play className="w-3.5 h-3.5" />
              {finalizeRunning ? 'Running...' : 'Run'}
            </button>
          )}
          <SlidingSwitch2
            value={cfg.finalize === 'auto'}
            onChange={onAutoConfigChange ? (v) => onAutoConfigChange({ ...cfg, finalize: v ? 'auto' : 'manual' }) : undefined}
            disabled={inactive}
            disabledReason={inactive ? "Project is inactive" : undefined}
          />
        </div>
      </div>
      <div className="flex flex-col gap-0.5 ml-1">
        {finalizeStages.map((stage) => (
          <StageRow
            key={stage.id}
            stage={stage}
            isPaused={!!(finalizePaused && stage.id === finalizePausedStage)}
            showDetails={showDetails}
          />
        ))}
      </div>
```

Add the running check:
```typescript
  const finalizeRunning = finalizeStages.some(s => s.state === 'running');
```

- [ ] **Step 7: Commit**

```bash
git add packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx
git commit -m "feat(P96): render Finalize group in pipeline UI

Add third group section with Atlas, Rules, Concepts, Audit, Antibodies
stages. Same auto/manual toggle pattern as Sync and Enrich groups."
```

---

## Task 7: Update Tests and Verify

**Files:**
- Modify: `tests/test_pipeline_state_machine.py`
- Modify: `tests/test_pipeline_orchestrator.py`

- [ ] **Step 1: Update state machine tests**

In `tests/test_pipeline_state_machine.py`, add a helper and test for finalize group:

```python
def make_finalize_sm():
    return make_sm(
        stages=["atlas", "rules", "concepts", "audit", "antibodies"],
        group="finalize",
    )

class TestFinalizeGroup:
    """Test finalize group state machine behavior."""

    def test_finalize_sm_has_5_stages(self):
        sm = make_finalize_sm()
        assert len(sm.stages) == 5

    def test_finalize_lifecycle(self):
        sm = make_finalize_sm()
        sm.transition(Event.START)
        assert sm.state == PipelineState.RUNNING
        # Complete all 5 stages
        for _ in range(5):
            sm.transition(Event.STAGE_COMPLETED)
        sm.transition(Event.ALL_STAGES_DONE)
        assert sm.state == PipelineState.COMPLETED
```

- [ ] **Step 2: Update orchestrator tests for backward compat**

In `tests/test_pipeline_orchestrator.py`, verify the backward-compat alias works:

```python
def test_backward_compat_aliases():
    """DEEP_ENRICHMENT_STAGES alias still works."""
    from prep.services.pipeline.stages import DEEP_ENRICHMENT_STAGES, ENRICH_STAGES
    assert DEEP_ENRICHMENT_STAGES is ENRICH_STAGES
```

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/pytest tests/test_pipeline_state_machine.py tests/test_pipeline_orchestrator.py tests/test_pipeline_orchestrator_transitions.py -v`

Expected: All tests pass.

- [ ] **Step 4: Run frontend typecheck**

Run: `cd packages/ui && npm run typecheck`

Expected: No type errors from the new interfaces and component changes.

- [ ] **Step 5: Commit**

```bash
git add tests/test_pipeline_state_machine.py tests/test_pipeline_orchestrator.py
git commit -m "test(P96): add finalize group tests, verify backward compat

State machine lifecycle test for finalize group. Verify
DEEP_ENRICHMENT_STAGES alias still works."
```

---

## Task 8: Wire Dashboard to Finalize API

**Files:**
- Modify: `src/prep/dashboard/src/App.tsx` or wherever the dashboard calls pipeline APIs and passes status to the GraphEnrichmentPipeline component

This task connects the plumbing: the dashboard fetches the finalize group status from the API and passes it as props to the pipeline component.

- [ ] **Step 1: Find where PipelineStatus is consumed in the dashboard**

Search the dashboard source for where `pipeline/status` is fetched and where `GraphEnrichmentPipeline` is rendered with props. The key is adding:
- `finalize` group from the status response → to the component
- `rulesStatus`, `conceptsStatus`, `auditPipelineStatus`, `antibodiesStatus` from `stages` → to the component
- `onRunFinalize` callback → calls `POST /pipeline/finalize`

- [ ] **Step 2: Add the finalize API call**

In the dashboard's API layer, add:
```typescript
const runFinalize = async (projectId: string) => {
  await fetch(`/api/projects/${projectId}/pipeline/finalize`, { method: 'POST' });
};
```

- [ ] **Step 3: Extract finalize stage statuses from API response**

When the status polling returns, extract the new fields:
```typescript
const rulesStatus = status?.stages?.rules;
const conceptsStatus = status?.stages?.concepts;
const auditPipelineStatus = status?.stages?.audit;
const antibodiesStatus = status?.stages?.antibodies;
```

- [ ] **Step 4: Pass props to GraphEnrichmentPipeline**

```tsx
<GraphEnrichmentPipeline
  // ... existing props
  rulesStatus={rulesStatus}
  conceptsStatus={conceptsStatus}
  auditPipelineStatus={auditPipelineStatus}
  antibodiesStatus={antibodiesStatus}
  onRunFinalize={() => runFinalize(projectId)}
  finalizePaused={status?.finalize?.phase === 'paused'}
  finalizePausedStage={status?.finalize?.current_stage}
/>
```

- [ ] **Step 5: Commit**

```bash
git add src/prep/dashboard/
git commit -m "feat(P96): wire dashboard to Finalize pipeline API

Pass finalize status and controls to GraphEnrichmentPipeline component."
```

---

## Summary

| Task | What | Files | Est. Complexity |
|------|------|-------|-----------------|
| 1 | Stage definitions + group constants | stages.py, build_orchestrator.py | Low — enum additions |
| 2 | Create 4 Finalize workers | workers.py | Medium — wrapping existing code |
| 3 | Orchestrator 3-group model | orchestrator.py, post_flight.py | High — state machine + chaining |
| 4 | Pipeline API endpoints | pipeline.py | Medium — endpoint additions |
| 5 | Frontend types | types.ts | Low — interface additions |
| 6 | Frontend component | GraphEnrichmentPipeline.tsx | Medium — third group section |
| 7 | Tests | test_pipeline_*.py | Low — verify correctness |
| 8 | Dashboard wiring | dashboard App.tsx | Low — prop plumbing |

**Note on parallel dispatch:** This plan implements the Finalize group as sequential stages (same as Sync and Enrich). Wave-based parallel dispatch within Finalize is architecturally designed (see `FINALIZE_WAVES` in Task 1 Step 6) but the orchestrator's `_advance_pipeline()` currently advances one stage at a time. Implementing actual parallel dispatch is a separate, more complex change to the state machine that can be done as a follow-up — the sequential version works correctly and the parallelism is an optimization, not a correctness requirement.
