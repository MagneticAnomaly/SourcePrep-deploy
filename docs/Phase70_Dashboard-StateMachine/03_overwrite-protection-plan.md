# Pipeline Overwrite Protection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent the pipeline from ever destroying data it already built. If a stage would produce fewer records than already exist, halt instead of overwriting.

**Architecture:** Extend the existing IntegrityGuard (Phase 60A) with a blocking write guard. The guard intercepts at two points in the orchestrator: (1) before a stage starts, check if its outputs are already up-to-date (skip if so), and (2) after a stage completes, compare new vs old record counts and block advancement if data shrank. No changes to individual worker write logic — the guard operates at the orchestrator level.

**Tech Stack:** Python, existing IntegrityGuard, PipelineOrchestrator

---

## File Structure

| File | Purpose | Action |
|------|---------|--------|
| `src/codrag/services/pipeline_integrity.py` | IntegrityGuard — add blocking write guard methods | **Modify** |
| `src/codrag/services/pipeline/orchestrator.py` | Wire write guard into stage lifecycle | **Modify** |
| `src/codrag/services/pipeline/stages.py` | Add stage dependency map for freshness checks | **Modify** |
| `tests/test_write_guard.py` | Unit tests for write guard logic | **Create** |

---

### Task 1: Add WriteGuard to IntegrityGuard

Add two new methods to IntegrityGuard that can block pipeline advancement when data loss is detected.

**Files:**
- Modify: `src/codrag/services/pipeline_integrity.py`
- Create: `tests/test_write_guard.py`

- [ ] **Step 1: Write failing test for `should_block_stage_completion`**

```python
# tests/test_write_guard.py
import pytest
from pathlib import Path
from codrag.services.pipeline_integrity import IntegrityGuard, FileSnapshot, StageSnapshot

def test_block_when_records_shrank():
    """Stage produced fewer records than existed — must block."""
    guard = IntegrityGuard()
    
    # Simulate pre-flight: 800 records existed
    pre = StageSnapshot(project_id="test", stage_id="enrichment")
    pre.files["trace_epistemic.jsonl"] = FileSnapshot(
        path="/tmp/trace_epistemic.jsonl",
        exists=True,
        size_bytes=1_000_000,
        record_count=800,
    )
    guard._snapshots[("test", "enrichment")] = pre
    
    # Simulate post-flight: only 50 records produced
    post_files = {
        "trace_epistemic.jsonl": FileSnapshot(
            path="/tmp/trace_epistemic.jsonl",
            exists=True,
            size_bytes=50_000,
            record_count=50,
        )
    }
    
    blocked, reason = guard.should_block_stage_completion(
        "test", "enrichment", post_files
    )
    assert blocked is True
    assert "800" in reason  # should mention original count
    assert "50" in reason   # should mention new count


def test_allow_when_records_grew():
    """Stage produced more records — allow."""
    guard = IntegrityGuard()
    
    pre = StageSnapshot(project_id="test", stage_id="enrichment")
    pre.files["trace_epistemic.jsonl"] = FileSnapshot(
        path="/tmp/trace_epistemic.jsonl",
        exists=True,
        size_bytes=1_000_000,
        record_count=800,
    )
    guard._snapshots[("test", "enrichment")] = pre
    
    post_files = {
        "trace_epistemic.jsonl": FileSnapshot(
            path="/tmp/trace_epistemic.jsonl",
            exists=True,
            size_bytes=1_100_000,
            record_count=850,
        )
    }
    
    blocked, reason = guard.should_block_stage_completion(
        "test", "enrichment", post_files
    )
    assert blocked is False


def test_allow_first_run():
    """No pre-flight data existed — always allow."""
    guard = IntegrityGuard()
    
    pre = StageSnapshot(project_id="test", stage_id="enrichment")
    pre.files["trace_epistemic.jsonl"] = FileSnapshot(
        path="/tmp/trace_epistemic.jsonl",
        exists=False,
    )
    guard._snapshots[("test", "enrichment")] = pre
    
    post_files = {
        "trace_epistemic.jsonl": FileSnapshot(
            path="/tmp/trace_epistemic.jsonl",
            exists=True,
            size_bytes=50_000,
            record_count=50,
        )
    }
    
    blocked, reason = guard.should_block_stage_completion(
        "test", "enrichment", post_files
    )
    assert blocked is False


def test_allow_equal_records():
    """Same record count (re-run with no changes) — allow."""
    guard = IntegrityGuard()
    
    pre = StageSnapshot(project_id="test", stage_id="enrichment")
    pre.files["trace_epistemic.jsonl"] = FileSnapshot(
        path="/tmp/trace_epistemic.jsonl",
        exists=True,
        size_bytes=1_000_000,
        record_count=800,
    )
    guard._snapshots[("test", "enrichment")] = pre
    
    post_files = {
        "trace_epistemic.jsonl": FileSnapshot(
            path="/tmp/trace_epistemic.jsonl",
            exists=True,
            size_bytes=1_000_000,
            record_count=800,
        )
    }
    
    blocked, reason = guard.should_block_stage_completion(
        "test", "enrichment", post_files
    )
    assert blocked is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_write_guard.py -v`
Expected: FAIL — `should_block_stage_completion` doesn't exist yet

- [ ] **Step 3: Implement `should_block_stage_completion` on IntegrityGuard**

Add to `src/codrag/services/pipeline_integrity.py`, after the `check_after_stage` method:

```python
    def should_block_stage_completion(
        self,
        project_id: str,
        stage_id: str,
        post_files: Dict[str, FileSnapshot],
    ) -> tuple[bool, str]:
        """Check if a stage's output would destroy existing data.

        Compares post-stage file state against the pre-flight snapshot.
        Returns (should_block, reason). If should_block is True, the
        pipeline should NOT advance — the stage's output would reduce
        the data below what already existed.

        This is the blocking counterpart to check_after_stage(), which
        only logs.  Called from the orchestrator's completion handler.
        """
        key = (project_id, stage_id)
        pre = self._snapshots.get(key)
        if pre is None:
            return False, "no pre-flight snapshot"

        for fname, pre_fs in pre.files.items():
            if not pre_fs.exists or pre_fs.record_count == 0:
                continue  # first run or empty file — nothing to protect

            post_fs = post_files.get(fname)
            if post_fs is None or not post_fs.exists:
                return True, (
                    f"Stage {stage_id} would delete {fname} "
                    f"({pre_fs.record_count} records existed)"
                )

            if post_fs.record_count < pre_fs.record_count:
                return True, (
                    f"Stage {stage_id} would shrink {fname} from "
                    f"{pre_fs.record_count} to {post_fs.record_count} records "
                    f"({post_fs.record_count / pre_fs.record_count:.0%} of original)"
                )

        return False, "ok"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_write_guard.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/pipeline_integrity.py tests/test_write_guard.py
git commit -m "feat(integrity): add blocking write guard to IntegrityGuard

should_block_stage_completion() compares post-stage output against
pre-flight snapshot and returns True if data would shrink. This is
the blocking counterpart to check_after_stage() which only logs."
```

---

### Task 2: Wire write guard into orchestrator's completion handler

When a stage completes, check if its output would destroy data. If so, log a CRITICAL error and fail the stage instead of advancing.

**Files:**
- Modify: `src/codrag/services/pipeline/orchestrator.py:1540-1570`

- [ ] **Step 1: Add write guard check after stage completion**

In `_on_build_transition` (around line 1547), after `_write_stage_manifest_and_update_run` and before `_integrity_check_after_stage`, add the blocking check:

```python
                    # Phase 70B: Write guard — block if data would shrink
                    try:
                        from codrag.services.pipeline_integrity import integrity_guard, STAGE_DATA_FILES
                        from codrag.core.project_registry import project_index_dir
                        from codrag.services.project_helpers import require_project
                        
                        project = require_project(project_id)
                        idx_dir = Path(project_index_dir(project))
                        data_files = STAGE_DATA_FILES.get(stage.value, [])
                        
                        post_files = {}
                        for fname in data_files:
                            fpath = idx_dir / fname
                            post_files[fname] = integrity_guard._snapshot_file(fpath)
                        
                        blocked, reason = integrity_guard.should_block_stage_completion(
                            project_id, stage.value, post_files,
                        )
                        
                        if blocked:
                            logger.critical(
                                "WRITE GUARD BLOCKED stage %s for %s: %s",
                                stage.value, project_id, reason,
                            )
                            if pfl:
                                pfl.log(stage.value, f"WRITE GUARD BLOCKED: {reason}")
                            # Fail this stage — do NOT advance to next stage
                            raise RuntimeError(f"Write guard blocked: {reason}")
                    except RuntimeError:
                        raise  # re-raise the write guard block
                    except Exception:
                        logger.debug(
                            "Write guard check failed (non-fatal) for %s/%s",
                            project_id, stage.value, exc_info=True,
                        )
```

Insert this block AFTER line 1552 (`_write_stage_manifest_and_update_run`) and BEFORE line 1561 (`_integrity_check_after_stage`).

- [ ] **Step 2: Verify the orchestrator still imports cleanly**

Run: `.venv/bin/python -c "from codrag.services.pipeline.orchestrator import PipelineOrchestrator; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/codrag/services/pipeline/orchestrator.py
git commit -m "feat(pipeline): wire write guard into stage completion handler

After a stage completes, compare output record counts against
pre-flight snapshot. If data would shrink, raise RuntimeError
to fail the stage and prevent pipeline advancement. The pipeline
should only grow the graph, never shrink it."
```

---

### Task 3: Add input freshness check to skip already-current stages

Before running a stage, check if its output files are already newer than its input files. If so, skip the stage with "Already current" instead of re-running and risking data loss.

**Files:**
- Modify: `src/codrag/services/pipeline/stages.py` (add dependency map)
- Modify: `src/codrag/services/pipeline_integrity.py` (add freshness check)
- Modify: `src/codrag/services/pipeline/orchestrator.py:1440-1455` (wire check before stage start)
- Create: `tests/test_input_freshness.py`

- [ ] **Step 1: Add stage dependency map to stages.py**

Add after the existing `STAGE_OUTPUT_FILE` definitions:

```python
# Which output files each stage depends on (its inputs).
# If ALL input files are OLDER than ALL output files, the stage is already current.
STAGE_INPUT_FILES: Dict[str, list[str]] = {
    "structural":      [],  # depends on source files, not pipeline files
    "inferred_edges":  ["trace_augmented.jsonl"],
    "catalogue":       ["trace_nodes.jsonl"],
    "validation":      ["trace_edges.jsonl", "trace_inferred_edges.jsonl"],
    "knowledge":       ["trace_augmented.jsonl"],
    "enrichment":      ["trace_augmented.jsonl"],
    "group_reasoning": ["trace_epistemic.jsonl"],
    "clustering":      ["trace_epistemic.jsonl"],
    "atlas":           ["trace_modules.jsonl"],
    "deepening":       ["trace_epistemic.jsonl", "trace_modules.jsonl"],
    "deep_knowledge":  ["trace_epistemic.jsonl", "trace_modules.jsonl"],
}
```

- [ ] **Step 2: Write failing test for freshness check**

```python
# tests/test_input_freshness.py
import pytest
import tempfile
import time
from pathlib import Path
from codrag.services.pipeline_integrity import IntegrityGuard

def test_skip_when_outputs_newer_than_inputs(tmp_path):
    """Stage outputs are newer than inputs — should skip."""
    guard = IntegrityGuard()
    
    # Create input file (older)
    input_file = tmp_path / "trace_augmented.jsonl"
    input_file.write_text('{"id": "1"}\n')
    
    time.sleep(0.05)  # ensure mtime difference
    
    # Create output file (newer)
    output_file = tmp_path / "trace_epistemic.jsonl"
    output_file.write_text('{"id": "1", "confidence": 0.9}\n')
    
    should_skip, reason = guard.check_stage_freshness(
        tmp_path,
        input_files=["trace_augmented.jsonl"],
        output_files=["trace_epistemic.jsonl"],
    )
    assert should_skip is True
    assert "current" in reason.lower()


def test_run_when_inputs_newer_than_outputs(tmp_path):
    """Input was rebuilt after output — stage needs to run."""
    guard = IntegrityGuard()
    
    # Create output file (older)
    output_file = tmp_path / "trace_epistemic.jsonl"
    output_file.write_text('{"id": "1", "confidence": 0.9}\n')
    
    time.sleep(0.05)
    
    # Create input file (newer)
    input_file = tmp_path / "trace_augmented.jsonl"
    input_file.write_text('{"id": "1"}\n{"id": "2"}\n')
    
    should_skip, reason = guard.check_stage_freshness(
        tmp_path,
        input_files=["trace_augmented.jsonl"],
        output_files=["trace_epistemic.jsonl"],
    )
    assert should_skip is False


def test_run_when_output_missing(tmp_path):
    """Output doesn't exist — stage must run."""
    guard = IntegrityGuard()
    
    input_file = tmp_path / "trace_augmented.jsonl"
    input_file.write_text('{"id": "1"}\n')
    
    should_skip, reason = guard.check_stage_freshness(
        tmp_path,
        input_files=["trace_augmented.jsonl"],
        output_files=["trace_epistemic.jsonl"],
    )
    assert should_skip is False


def test_run_when_no_inputs(tmp_path):
    """Stage has no pipeline inputs (e.g. structural) — always run."""
    guard = IntegrityGuard()
    
    should_skip, reason = guard.check_stage_freshness(
        tmp_path,
        input_files=[],
        output_files=["trace_nodes.jsonl"],
    )
    assert should_skip is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_input_freshness.py -v`
Expected: FAIL — `check_stage_freshness` doesn't exist

- [ ] **Step 4: Implement `check_stage_freshness` on IntegrityGuard**

Add to `src/codrag/services/pipeline_integrity.py`:

```python
    def check_stage_freshness(
        self,
        index_dir: Path,
        input_files: list[str],
        output_files: list[str],
    ) -> tuple[bool, str]:
        """Check if a stage's outputs are already up-to-date.

        Compares modification times of input files vs output files.
        If ALL output files exist and are NEWER than ALL input files,
        the stage is already current and can be skipped.

        Returns (should_skip, reason).
        """
        if not input_files:
            return False, "no pipeline inputs — stage must run"

        # Get newest input mtime
        newest_input_mtime = 0.0
        for fname in input_files:
            fpath = index_dir / fname
            if not fpath.exists():
                return False, f"input {fname} missing — stage must run"
            newest_input_mtime = max(newest_input_mtime, fpath.stat().st_mtime)

        # Get oldest output mtime
        for fname in output_files:
            fpath = index_dir / fname
            if not fpath.exists():
                return False, f"output {fname} missing — stage must run"
            if fpath.stat().st_mtime < newest_input_mtime:
                return False, (
                    f"output {fname} is older than inputs — stage must run"
                )

        return True, "all outputs are newer than inputs — already current"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_input_freshness.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Wire freshness check into orchestrator before stage start**

In `src/codrag/services/pipeline/orchestrator.py`, before line 1450 (the pre-flight snapshot), add:

```python
        # Phase 70B: Input freshness check — skip if outputs already current
        try:
            from codrag.services.pipeline_integrity import integrity_guard
            from codrag.services.pipeline.stages import STAGE_INPUT_FILES
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project
            
            project = require_project(run.project_id)
            idx_dir = Path(project_index_dir(project))
            input_files = STAGE_INPUT_FILES.get(stage.value, [])
            output_files = STAGE_DATA_FILES.get(stage.value, [])
            
            if input_files:  # structural has no pipeline inputs
                should_skip, reason = integrity_guard.check_stage_freshness(
                    idx_dir, input_files, output_files,
                )
                if should_skip:
                    logger.info(
                        "Stage %s skipped for %s: %s",
                        stage.value, run.project_id, reason,
                    )
                    pfl = self._get_file_logger(run.project_id)
                    if pfl:
                        pfl.log(stage.value, f"SKIPPED (freshness): {reason}")
                    # Mark stage as completed without running it
                    run.stage_results[stage.value] = "skipped"
                    run.advance()
                    return  # don't start the worker
        except Exception:
            logger.debug(
                "Freshness check failed (non-fatal) for %s/%s",
                run.project_id, stage.value, exc_info=True,
            )
```

Note: `STAGE_DATA_FILES` needs to be imported — add it to the existing import from `pipeline_integrity` or import directly from `stages`.

- [ ] **Step 7: Run full test suite**

Run: `.venv/bin/pytest tests/test_write_guard.py tests/test_input_freshness.py -v`
Expected: All 8 tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/codrag/services/pipeline/stages.py \
        src/codrag/services/pipeline_integrity.py \
        src/codrag/services/pipeline/orchestrator.py \
        tests/test_input_freshness.py
git commit -m "feat(pipeline): add input freshness check to skip already-current stages

Before running a stage, compare input file mtimes to output file
mtimes. If all outputs are newer than all inputs, skip the stage
with 'Already current'. This prevents unnecessary re-runs that
could overwrite good data with smaller results.

Includes STAGE_INPUT_FILES dependency map in stages.py."
```

---

## Summary

| Guardrail | Where | What It Does |
|-----------|-------|-------------|
| **Write guard** (Task 1-2) | After stage completion, before pipeline advances | Blocks if output has fewer records than pre-flight snapshot |
| **Freshness check** (Task 3) | Before stage starts | Skips stage entirely if outputs are newer than inputs |

Together these ensure the pipeline only grows the graph. A stage that would shrink data is blocked. A stage whose outputs are already current is skipped. No data is ever destroyed during normal pipeline operation.
