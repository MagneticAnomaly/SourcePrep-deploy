# Phase 136 Part 09 Step 2 — Chunked synthesis implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When concept-synthesis input exceeds the LLM's effective consolidation budget, split successful worker results into batches of ~200, synthesize each batch, then synthesize-the-syntheses. Preserve the existing single-call path for runs that don't need chunking. Add diagnostic telemetry distinguishing four chunked failure modes from the four single-call failure modes.

**Architecture:** `SwarmOrchestrator._synthesize` becomes a thin dispatcher splitting to `_synthesize_single` (existing body, renamed) or `_synthesize_chunked` (new). All paths return a 5-tuple `(parsed, tokens, raw_text, prompt_chars, meta_failed)`. `SwarmResult` gains `synthesis_chunk_count: int = 1` and `synthesis_meta_failed: bool = False`. Concept_seeder's diagnostic helper learns `chunked_all_failed` and `chunked_meta_failed`; a new `concepts_chunked_meta_failed` telemetry event fires for the recovery-success path.

**Tech Stack:** Python 3.11, dataclasses, pytest, unittest.mock.patch. No new dependencies.

**Spec:** `docs/Phase136_Dogfood-fixes/Part09_SynthesizerWallTimeRegression/STEP2_CHUNKED_SYNTHESIS_DESIGN.md`

**Branch:** `phase-136-part09`. Step 1 ships as commit `7a338adb`; spec at `c1f57177` + `367f2210`. This plan lands additional commits on top.

**Merge gate:** Do NOT merge to `main` until Step 1 telemetry from a live rebuild produces a `concepts_synthesis_failed` event with `failure_mode = "parsed_but_empty"` AND `synthesis_prompt_chars > 1_500_000`. If telemetry says otherwise, the branch stays for reference and Step 3 (Path B) takes priority.

---

## File map

| File | Action | Responsibility |
|---|---|---|
| `src/prep/core/swarm_orchestrator.py` | Modify | `SwarmResult` gains 2 fields; `_synthesize` widens to 5-tuple and splits into dispatcher + `_synthesize_single` + `_synthesize_chunked`; `__init__` reads env config; `execute()` plumbs `synthesis_meta_failed` into `SwarmResult`. |
| `src/prep/core/concept_seeder.py` | Modify | `_synthesis_diagnostic_fields` gains 2 `failure_mode` branches; `seed_concepts_swarm` gains a new `record_event("concepts_chunked_meta_failed", ...)` call. |
| `tests/test_synthesis_diagnostic.py` | Modify | Step 1 tests that unpack `_synthesize`'s return get widened to 5-tuple (`*_, _ = ...` or explicit 5-name unpack). No new assertions, no behavioral changes. |
| `tests/test_synthesis_chunked.py` | Create | 19 new tests covering chunked dispatch, per-chunk failure handling, meta failure with deduped union, soft-hold pause propagation, env config, reproducibility, and the new telemetry event. |

No changes to cluster.py / atlas/generator.py / group_reasoning.py — they call `execute()`, not `_synthesize`, and `SwarmResult`'s new fields have backward-compat defaults.

---

## Task 1: Widen `SwarmResult` with chunked-synthesis fields

**Files:**
- Modify: `src/prep/core/swarm_orchestrator.py` (the `SwarmResult` dataclass, currently around lines 94-122)
- Create: `tests/test_synthesis_chunked.py`

- [ ] **Step 1.1: Create the test file with the two field-default tests**

```python
# tests/test_synthesis_chunked.py
"""Phase 136 Part 09 Step 2 — chunked synthesis.

Tests the new chunked path in SwarmOrchestrator + the corresponding
telemetry surface in concept_seeder.

Spec: docs/Phase136_Dogfood-fixes/Part09_SynthesizerWallTimeRegression/STEP2_CHUNKED_SYNTHESIS_DESIGN.md
"""
from __future__ import annotations

import json
import os
from dataclasses import is_dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

from prep.core.swarm_orchestrator import (
    SwarmOrchestrator,
    SwarmResult,
    WorkerResult,
)


# ── SwarmResult contract ───────────────────────────────────────────


def test_swarm_result_synthesis_chunk_count_default_is_1():
    """Backward compat: existing callers see chunk_count == 1."""
    r = SwarmResult()
    assert hasattr(r, "synthesis_chunk_count"), (
        "SwarmResult must carry synthesis_chunk_count so concept_seeder's "
        "diagnostic classifier can distinguish chunked from single-call paths"
    )
    assert r.synthesis_chunk_count == 1


def test_swarm_result_synthesis_meta_failed_default_is_false():
    """Backward compat: existing callers see meta_failed is False."""
    r = SwarmResult()
    assert hasattr(r, "synthesis_meta_failed"), (
        "SwarmResult must expose synthesis_meta_failed so the diagnostic "
        "classifier can fire chunked_meta_failed without re-deriving"
    )
    assert r.synthesis_meta_failed is False
```

- [ ] **Step 1.2: Run the tests to verify they fail**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/.claude/worktrees/phase-136-part09
.venv/bin/pytest tests/test_synthesis_chunked.py -v
```

Expected: 2 FAIL with `AssertionError: SwarmResult must carry synthesis_chunk_count ...` and `... must expose synthesis_meta_failed ...`.

Note: the worktree shares the parent repo's `.venv`. Use `/Volumes/4TB-BAD/HumanAI/CoDRAG/.venv/bin/pytest` if running from a non-worktree cwd.

- [ ] **Step 1.3: Add the two fields to `SwarmResult`**

Locate the `SwarmResult` dataclass in `src/prep/core/swarm_orchestrator.py`. Step 1 already added `raw_synthesis_text` and `synthesis_prompt_chars` at the end of the class. Append two more fields immediately after them:

```python
    # Phase 136 Part 09 Step 2: chunked-synthesis surface.
    # synthesis_chunk_count == 1 means single-call path (or chunking was
    # eligible but only one chunk's worth of workers).  N > 1 means N
    # chunks + 1 meta call.  synthesis_meta_failed is True ONLY when the
    # chunked path ran AND chunks succeeded AND meta failed AND we
    # returned a manually-deduped union of survivors as result.synthesis.
    # The diagnostic classifier reads these to distinguish
    # chunked_meta_failed and chunked_all_failed from the four single-
    # call failure modes (no_workers / no_text / parse_failed /
    # parsed_but_empty).
    synthesis_chunk_count: int = 1
    synthesis_meta_failed: bool = False
```

- [ ] **Step 1.4: Run the tests to verify they pass**

```bash
.venv/bin/pytest tests/test_synthesis_chunked.py::test_swarm_result_synthesis_chunk_count_default_is_1 tests/test_synthesis_chunked.py::test_swarm_result_synthesis_meta_failed_default_is_false -v
```

Expected: 2 PASS.

- [ ] **Step 1.5: Commit**

```bash
git add src/prep/core/swarm_orchestrator.py tests/test_synthesis_chunked.py
git commit -m "feat(phase136 part09 step2): SwarmResult gains chunk_count + meta_failed fields

Backward-compatible groundwork for the chunked-synthesis path.  Both
fields default to single-call-path values (1 and False) so existing
callers and tests stay green.

Tests (+2):
- synthesis_chunk_count defaults to 1 (single-call semantics).
- synthesis_meta_failed defaults to False (no chunked recovery happened).

No behavior change."
```

---

## Task 2: Widen `_synthesize` return to 5-tuple (backward-compat, no behavior change)

**Files:**
- Modify: `src/prep/core/swarm_orchestrator.py` — `_synthesize` return type signature, all 4 return statements, the single caller in `execute()`
- Modify: `tests/test_synthesis_diagnostic.py` — 4 tests that unpack the return tuple

- [ ] **Step 2.1: Update Step 1 tests to unpack 5-tuple (write the failing change first)**

Open `tests/test_synthesis_diagnostic.py`. Four tests unpack `_synthesize`'s return:

- `test_synthesize_returns_raw_text_on_success`
- `test_synthesize_returns_raw_text_on_parse_failure`
- `test_synthesize_returns_none_text_on_llm_timeout`
- `test_synthesize_returns_zero_prompt_chars_when_no_workers`

In each test, find the unpacking line (`parsed, tokens, raw_text, prompt_chars = orch._synthesize(...)`) and change it to:

```python
parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
    workers,
    synthesis_prompt="prefix {worker_outputs} suffix",
    event_log=None,
)
```

For `test_synthesize_returns_raw_text_on_success` ONLY, also assert:

```python
assert meta_failed is False, (
    "_synthesize_single never has a meta phase — meta_failed must be False"
)
```

Repeat that assertion at the end of each of the four tests (so all 4 confirm meta_failed is False on the single-call path).

Also update `test_synthesize_returns_raw_text_on_success`'s tuple-length assertion:

```python
assert len(out) == 5, (
    f"_synthesize must return (parsed, tokens, raw_text, prompt_chars, "
    f"meta_failed); got tuple of length {len(out)}"
)
```

(Update the existing `assert len(out) == 4` to `== 5`.)

- [ ] **Step 2.2: Run the updated tests to verify they fail**

```bash
.venv/bin/pytest tests/test_synthesis_diagnostic.py -v
```

Expected: 4 FAIL with `ValueError: not enough values to unpack (expected 5, got 4)` and the success test fails the tuple-length assertion.

- [ ] **Step 2.3: Update `_synthesize` to return 5-tuple**

In `src/prep/core/swarm_orchestrator.py`, find `_synthesize`. Update the return type annotation:

```python
def _synthesize(
    self,
    worker_results: List[WorkerResult],
    synthesis_prompt: str,
    event_log: Optional[SwarmEventLogger] = None,
) -> Tuple[Optional[Dict[str, Any]], int, Optional[str], int, bool]:
    """Single LLM call to aggregate successful worker results.

    Returns ``(parsed_result, token_count, raw_text, prompt_chars,
    meta_failed)``.

    - ``parsed_result`` is ``None`` on failure, timeout, or if no
      workers succeeded.
    - ``raw_text`` is the LLM response captured even on parse failure
      so callers (currently concept_seeder) can include head/tail in
      the diagnostic.  ``None`` when no LLM call was made or it timed
      out.
    - ``prompt_chars`` is the consolidation prompt size; ``0`` when no
      LLM call was made.
    - ``meta_failed`` is reserved for the chunked path (Step 2);
      single-call path always returns ``False``.

    Callers should fall back to merging raw worker outputs when
    ``parsed_result`` is ``None``.
    """
```

Then update each of the 4 return statements in `_synthesize` to include `False` as the trailing element. Specifically:

```python
# At "no successful workers" branch:
return None, 0, None, 0, False

# At "LLM timeout (text is None)" branch:
return None, tokens, None, prompt_chars, False

# At "parse failed" branch:
return None, tokens, text, prompt_chars, False

# At "success" branch:
return parsed, tokens, text, prompt_chars, False
```

- [ ] **Step 2.4: Update the single caller in `execute()`**

Find the call site in `execute()` (currently around line 957):

```python
(
    synthesis, synthesis_tokens,
    raw_synthesis_text, synthesis_prompt_chars,
) = self._synthesize(
    worker_results, synthesis_prompt, event_log=event_log,
)
```

Widen the unpack and add the captured flag:

```python
(
    synthesis, synthesis_tokens,
    raw_synthesis_text, synthesis_prompt_chars,
    synthesis_meta_failed,
) = self._synthesize(
    worker_results, synthesis_prompt, event_log=event_log,
)
```

Also add the variable initialization near the top of the try block (alongside `raw_synthesis_text: Optional[str] = None`):

```python
synthesis_meta_failed = False
```

And add the field when constructing `SwarmResult`:

```python
result = SwarmResult(
    worker_results=worker_results,
    synthesis=synthesis,
    coordinator_plan=plan,
    stats=stats,
    event_log_path=str(event_log.path) if event_log and event_log.path else None,
    paused=paused,
    pause_info=pause_info,
    raw_synthesis_text=raw_synthesis_text,
    synthesis_prompt_chars=synthesis_prompt_chars,
    synthesis_meta_failed=synthesis_meta_failed,
)
```

(`synthesis_chunk_count` defaults to 1 — we'll set it explicitly in Task 5 when chunking actually runs.)

- [ ] **Step 2.5: Run the updated tests to verify they pass**

```bash
.venv/bin/pytest tests/test_synthesis_diagnostic.py tests/test_synthesis_chunked.py -v
```

Expected: 16 PASS (14 from Step 1 + 2 from Task 1).

- [ ] **Step 2.6: Commit**

```bash
git add src/prep/core/swarm_orchestrator.py tests/test_synthesis_diagnostic.py
git commit -m "refactor(phase136 part09 step2): widen _synthesize return to 5-tuple

Backward-compatible groundwork for the chunked path.  _synthesize now
returns (parsed, tokens, raw_text, prompt_chars, meta_failed) on every
exit branch.  The new meta_failed flag is always False on the single-
call path — it carries meaning only when the chunked path runs and
the meta synthesis fails after at least one chunk succeeded.

Updates:
- _synthesize return type widened; all 4 return sites add trailing False.
- execute() updated to unpack the 5-tuple and pass synthesis_meta_failed
  into SwarmResult.
- Step 1 tests (test_synthesize_returns_raw_text_on_success and 3 others)
  updated to unpack the new shape; success-path tests additionally
  assert meta_failed is False.

No behavior change.  Chunked dispatcher lands in Task 3."
```

---

## Task 3: Rename `_synthesize` body to `_synthesize_single` + add dispatcher

**Files:**
- Modify: `src/prep/core/swarm_orchestrator.py` — rename method, add new dispatcher
- Modify: `tests/test_synthesis_diagnostic.py` — Step 1 tests that call `orch._synthesize(...)` need to keep working (they will, because the dispatcher has the same signature)

- [ ] **Step 3.1: Rename `_synthesize` to `_synthesize_single`**

In `src/prep/core/swarm_orchestrator.py`, find the `_synthesize` method (the one we just widened to 5-tuple). Rename `_synthesize` → `_synthesize_single` on the method definition only:

```python
def _synthesize_single(
    self,
    worker_results: List[WorkerResult],
    synthesis_prompt: str,
    event_log: Optional[SwarmEventLogger] = None,
) -> Tuple[Optional[Dict[str, Any]], int, Optional[str], int, bool]:
    """Single LLM call to aggregate successful worker results.
    ...
```

Update the docstring's opening line to:

```python
    """Single LLM call to aggregate successful worker results.

    This is the existing single-prompt synthesis path.  The chunked path
    (`_synthesize_chunked`) calls this method once per chunk plus once
    for the meta synthesis.

    Returns ...
    """
```

- [ ] **Step 3.2: Add the dispatcher `_synthesize`**

Insert a new method named `_synthesize` ABOVE `_synthesize_single`:

```python
    def _synthesize(
        self,
        worker_results: List[WorkerResult],
        synthesis_prompt: str,
        event_log: Optional[SwarmEventLogger] = None,
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str], int, bool]:
        """Phase 136 Part 09 Step 2: dispatch to single-call or chunked
        synthesis based on worker count.

        When the number of successful workers exceeds
        ``self.synthesis_chunk_max_workers``, split into chunks and run
        synthesis + meta-synthesis.  Otherwise run the existing single-
        call path unchanged.

        Same return shape as ``_synthesize_single``:
        ``(parsed, tokens, raw_text, prompt_chars, meta_failed)``.
        """
        # Phase 136 Part 09 step 2: dispatch decision lives here so all
        # callers (currently only execute()) see one entry point.
        # Task 5 wires this to _synthesize_chunked once the chunked path
        # is implemented.  Until then, always delegate to single-call.
        return self._synthesize_single(
            worker_results, synthesis_prompt, event_log=event_log,
        )
```

- [ ] **Step 3.3: Update Step 1 tests if they call the renamed method directly**

Open `tests/test_synthesis_diagnostic.py`. Search for any call to `orch._synthesize_single(` — should be zero. Search for calls to `orch._synthesize(` — these now hit the dispatcher, which still delegates to single-call, so behavior is unchanged.

No test edits needed in this step.

- [ ] **Step 3.4: Run all touched tests**

```bash
.venv/bin/pytest tests/test_synthesis_diagnostic.py tests/test_synthesis_chunked.py -v
```

Expected: 16 PASS. The Step 1 tests now exercise the dispatcher → single-call delegation; no observable change.

- [ ] **Step 3.5: Commit**

```bash
git add src/prep/core/swarm_orchestrator.py
git commit -m "refactor(phase136 part09 step2): split _synthesize into dispatcher + _synthesize_single

The existing _synthesize body is renamed _synthesize_single (the
single-prompt synthesis path).  A new _synthesize method becomes the
dispatcher — for now it unconditionally delegates to _synthesize_single
so behavior is unchanged.  Task 5 wires the dispatcher to the chunked
path once chunking is implemented.

No behavior change.  Step 1 tests pass unchanged (they exercise the
dispatcher → single-call delegation now)."
```

---

## Task 4: Add `synthesis_chunk_max_workers` config to `__init__`

**Files:**
- Modify: `src/prep/core/swarm_orchestrator.py` — `SwarmOrchestrator.__init__` reads env var, stores attr
- Modify: `tests/test_synthesis_chunked.py` — test the env-var override behavior

- [ ] **Step 4.1: Write the env-var override test**

Append to `tests/test_synthesis_chunked.py`:

```python
# ── Config ─────────────────────────────────────────────────────────


def test_env_var_overrides_default_threshold(monkeypatch):
    """PREP_SYNTHESIS_CHUNK_MAX_WORKERS env var sets the threshold at
    init time.  Tests use a small value (e.g. 10) so they don't need
    to construct 200+ fake workers.
    """
    monkeypatch.setenv("PREP_SYNTHESIS_CHUNK_MAX_WORKERS", "10")

    # Build a fresh orchestrator AFTER the env is set (env is read in
    # __init__).  Bypass __init__'s LLM-client requirement by passing
    # a sentinel coordinator/worker pair that satisfies the type but
    # is never called in this test.
    class _StubLLM:
        model = "stub"
        def _resolve_scheduler_node_id(self):
            return ""

    stub = _StubLLM()
    orch = SwarmOrchestrator(
        coordinator_llm=stub,
        worker_llm=stub,
        concurrency=1,
    )
    assert orch.synthesis_chunk_max_workers == 10


def test_default_chunk_max_workers_is_200_when_env_unset(monkeypatch):
    """Default threshold matches the work-order's '~200 workers' guidance."""
    monkeypatch.delenv("PREP_SYNTHESIS_CHUNK_MAX_WORKERS", raising=False)

    class _StubLLM:
        model = "stub"
        def _resolve_scheduler_node_id(self):
            return ""

    stub = _StubLLM()
    orch = SwarmOrchestrator(
        coordinator_llm=stub,
        worker_llm=stub,
        concurrency=1,
    )
    assert orch.synthesis_chunk_max_workers == 200
```

- [ ] **Step 4.2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/test_synthesis_chunked.py::test_env_var_overrides_default_threshold tests/test_synthesis_chunked.py::test_default_chunk_max_workers_is_200_when_env_unset -v
```

Expected: 2 FAIL with `AttributeError: 'SwarmOrchestrator' object has no attribute 'synthesis_chunk_max_workers'`.

- [ ] **Step 4.3: Add the config read to `__init__`**

In `src/prep/core/swarm_orchestrator.py`, find `SwarmOrchestrator.__init__`. Locate where other timeout attributes are set (e.g., `self.synthesis_timeout_s = ...`). Append after the timeout block:

```python
        # Phase 136 Part 09 Step 2: threshold above which synthesis
        # splits into chunks of ~chunk_max_workers each.  Read at
        # __init__ so tests can monkeypatch the env before constructing
        # the orchestrator.  Default 200 matches the Part 09 work order.
        # Same value doubles as the per-chunk batch size (`chunk_max_workers`
        # workers per chunk; last chunk may be smaller).
        try:
            self.synthesis_chunk_max_workers = int(
                os.environ.get("PREP_SYNTHESIS_CHUNK_MAX_WORKERS", "200")
            )
        except ValueError:
            self.synthesis_chunk_max_workers = 200
        if self.synthesis_chunk_max_workers < 1:
            self.synthesis_chunk_max_workers = 200
```

Verify `import os` is already at the top of the file. If not, add it.

- [ ] **Step 4.4: Run the test to verify it passes**

```bash
.venv/bin/pytest tests/test_synthesis_chunked.py::test_env_var_overrides_default_threshold tests/test_synthesis_chunked.py::test_default_chunk_max_workers_is_200_when_env_unset -v
```

Expected: 2 PASS.

- [ ] **Step 4.5: Run the full test surface to confirm nothing else broke**

```bash
.venv/bin/pytest tests/test_synthesis_diagnostic.py tests/test_synthesis_chunked.py tests/test_soft_hold_primitive.py --no-header -q
```

Expected: all PASS, no regressions from adding the new attribute.

- [ ] **Step 4.6: Commit**

```bash
git add src/prep/core/swarm_orchestrator.py tests/test_synthesis_chunked.py
git commit -m "feat(phase136 part09 step2): SwarmOrchestrator config — synthesis_chunk_max_workers

PREP_SYNTHESIS_CHUNK_MAX_WORKERS env var (default 200) controls the
threshold above which _synthesize splits into chunks.  The same value
doubles as the chunk size (workers per chunk in the chunked path).

Read at __init__ so tests can monkeypatch the env before constructing
the orchestrator.  Defensive: bad values (non-int, <1) fall back to 200.

Tests (+2):
- Env-var override sets the attribute (uses threshold 10 so tests don't
  need 200+ fake workers).
- Default is 200 when env is unset.

No behavior change in the dispatcher yet — Task 5 wires it in."
```

---

## Task 5: Implement `_synthesize_chunked` — success path (chunks + meta success)

**Files:**
- Modify: `src/prep/core/swarm_orchestrator.py` — add `_synthesize_chunked` method; dispatcher routes to it above threshold; `execute()` reads `synthesis_chunk_count` from the chunked path
- Modify: `tests/test_synthesis_chunked.py` — add tests 1-4, 15-17

- [ ] **Step 5.1: Write the success-path tests**

Append to `tests/test_synthesis_chunked.py`:

```python
# ── Helpers ────────────────────────────────────────────────────────


def _make_orch(chunk_max: int = 200) -> SwarmOrchestrator:
    """Construct an orchestrator suitable for unit-testing _synthesize_chunked.
    Bypasses __init__'s LLM-client setup; sets only the attributes the
    code paths under test touch.
    """
    orch = SwarmOrchestrator.__new__(SwarmOrchestrator)
    orch.synthesis_timeout_s = 60.0
    orch.coordinator_llm = None
    orch.worker_llm = None
    orch.project_id = None
    orch.synthesis_chunk_max_workers = chunk_max
    return orch


def _ok_worker(item_id: str = "m1", concept_title: str = "T") -> WorkerResult:
    """Worker result with parsed JSON — enough to feed _synthesize."""
    return WorkerResult(
        item_id=item_id,
        raw_output="ignored",
        parsed={"concepts": [{"title": concept_title}], "questions": []},
        success=True,
    )


def _many_ok_workers(n: int, prefix: str = "m") -> List[WorkerResult]:
    """Generate N workers with distinct item_ids for chunk-count tests."""
    return [_ok_worker(item_id=f"{prefix}{i:03d}", concept_title=f"T-{i}")
            for i in range(n)]


# ── Dispatcher: below/above threshold ──────────────────────────────


def test_below_threshold_uses_single_call():
    """At exactly the threshold (200 with default config), the dispatcher
    must NOT chunk — single-call runs once.
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(200)
    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 100)) as mock_llm:
        out = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    # _llm_call_with_timeout called exactly once → single-call path.
    assert mock_llm.call_count == 1, (
        f"At threshold (200 == 200), dispatcher must use single-call; "
        f"got {mock_llm.call_count} LLM calls (would indicate chunking)"
    )
    parsed, tokens, raw_text, prompt_chars, meta_failed = out
    assert parsed == {"concepts": [{"title": "OK"}], "questions": []}
    assert meta_failed is False


def test_above_threshold_dispatches_correct_chunk_count():
    """At 798 workers, threshold 200, the chunked path must split into
    chunks of 200 + 200 + 200 + 198 and dispatch 4 + 1 = 5 LLM calls
    (4 per-chunk + 1 meta).
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(798)
    # Every per-chunk call AND the meta call returns the same valid JSON;
    # we count call_count to assert chunk math.
    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 50)) as mock_llm:
        out = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    # 4 chunks (200+200+200+198) + 1 meta = 5 LLM dispatches.
    assert mock_llm.call_count == 5, (
        f"798 workers at threshold 200 → 4 chunks + 1 meta = 5 LLM calls; "
        f"got {mock_llm.call_count}"
    )

    # Each chunk's prompt is one of the LLM call's positional args.
    # Verify the per-chunk prompts together contain all 798 workers'
    # item_ids (sanity check that chunking actually split the workload).
    prompts_sent = []
    for call in mock_llm.call_args_list[:4]:  # first 4 are per-chunk
        # _llm_call_with_timeout(prompt=..., system=..., ...)
        prompts_sent.append(call.kwargs.get("prompt", ""))

    for i in range(798):
        item_id = f"m{i:03d}"
        assert any(item_id in p for p in prompts_sent), (
            f"Worker {item_id} should appear in exactly one chunk prompt"
        )


def test_chunked_full_success_has_meta_dict_and_no_meta_failed():
    """All 4 chunks + meta succeed: result.synthesis is the meta dict,
    synthesis_meta_failed is False, synthesis_chunk_count == 4.
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(798)
    fake_text = '{"concepts": [{"title": "MetaConsolidated"}], "questions": []}'

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 100)):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert parsed == {"concepts": [{"title": "MetaConsolidated"}], "questions": []}
    assert meta_failed is False, (
        "Full chunked success must NOT set meta_failed"
    )


def test_chunked_synthesis_tokens_sum_across_chunks_and_meta():
    """Total tokens returned is the sum of per-chunk LLM tokens plus
    meta tokens.
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(600)  # 3 chunks of 200
    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'

    # Each LLM call returns a different token count so the sum is
    # distinguishable from "took the last call's count".
    token_seq = iter([100, 200, 300, 400])  # 3 chunks + 1 meta
    def _fake_call(**kwargs):
        return fake_text, next(token_seq)

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       side_effect=_fake_call):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert tokens == 100 + 200 + 300 + 400, (
        f"tokens must be sum of per-chunk + meta calls; got {tokens}"
    )


def test_chunked_synthesis_prompt_chars_is_max_single_prompt_size():
    """synthesis_prompt_chars is the LARGEST single prompt sent
    (per-chunk or meta), not the sum.  Operators read it as 'worst-case
    prompt the LLM saw'.
    """
    orch = _make_orch(chunk_max=200)

    # Build workers whose parsed content has varying sizes so the
    # per-chunk prompts differ.
    small = WorkerResult(item_id="m000", raw_output="r",
                         parsed={"concepts": [{"title": "x"}]}, success=True)
    large = WorkerResult(item_id="m001", raw_output="r",
                         parsed={"concepts": [{"title": "X" * 10_000}]},
                         success=True)
    # 201 workers → 2 chunks.  Put the large worker in chunk 1 (it sorts
    # to item_id "m001" → chunk starting at m000).
    workers = [small, large] + _many_ok_workers(199, prefix="m")
    # Re-sort by item_id since the chunked path sorts before splitting.
    # m000, m001, m000..m198 — duplicate m000 is fine for this test.

    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'
    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 10)):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    # The chunk containing the 10K-char worker produces a much larger
    # prompt than the meta call (which only has 2 small partial syntheses).
    # prompt_chars must reflect the largest single prompt.
    assert prompt_chars >= 10_000, (
        f"prompt_chars must be the MAX single prompt size; got {prompt_chars} "
        f"which is smaller than the large worker's content (10K chars)"
    )
```

- [ ] **Step 5.2: Run the failing tests**

```bash
.venv/bin/pytest tests/test_synthesis_chunked.py -v -k "below_threshold or above_threshold or chunked_full_success or chunked_synthesis_tokens or chunked_synthesis_prompt_chars"
```

Expected: 5 FAIL — `test_below_threshold_uses_single_call` may pass (single-call works today), others fail because chunked dispatch doesn't exist.

If `below_threshold` passes already, that's fine — it documents the existing single-call behavior at the threshold boundary.

- [ ] **Step 5.3: Implement `_synthesize_chunked` and wire the dispatcher**

In `src/prep/core/swarm_orchestrator.py`, add the `_synthesize_chunked` method ABOVE `_synthesize_single` and BELOW the new dispatcher `_synthesize`:

```python
    def _synthesize_chunked(
        self,
        successful: List[WorkerResult],
        synthesis_prompt: str,
        event_log: Optional[SwarmEventLogger] = None,
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str], int, bool]:
        """Phase 136 Part 09 Step 2: split synthesis into chunks of
        ``self.synthesis_chunk_max_workers`` and run a meta-synthesis
        over the chunk results.

        Path:
          1. Sort ``successful`` by ``item_id`` for reproducibility.
          2. Slice into batches of up to ``chunk_max_workers``.
          3. For each chunk, run ``_synthesize_single`` (drops the
             chunk on parse_failed / timeout / no_text).  Soft-hold
             check fires AFTER each chunk completes.
          4. If 0 chunks succeeded → return (None, ..., None, max_prompt, False).
             The existing concept_seeder fallback runs against raw
             worker outputs.
          5. Otherwise call ``_synthesize_single`` once more with the
             chunk parsed results as the ``{worker_outputs}`` payload
             (each chunk parsed dict serialized as JSON, joined the
             same way the original prompt joins workers).  Item id for
             each chunk is ``chunk-N``.
             - Meta succeeds → return (meta_parsed, sum_tokens + meta_tokens,
               meta_text, max(per_chunk_prompts, meta_prompt), False).
             - Meta fails → return (manually_deduped_union, ...,
               max(per_chunk_prompts, meta_prompt), True).
               Dedup mirrors concept_seeder.py:889-909 (skip empty
               titles, skip questions with empty text, lowercase-strip
               for dedup keys).

        Tokens are summed across chunks + meta.  prompt_chars is the
        MAX single prompt sent so the diagnostic question "was the
        prompt size too large for the model's output cap?" stays
        meaningful.
        """
        # Step 5a-d: chunk splitting + per-chunk dispatch.
        # Sort by item_id for reproducibility — production debugging and
        # test fixtures both rely on chunk boundaries being deterministic.
        sorted_workers = sorted(successful, key=lambda w: w.item_id)
        chunk_size = self.synthesis_chunk_max_workers
        chunks: List[List[WorkerResult]] = [
            sorted_workers[i:i + chunk_size]
            for i in range(0, len(sorted_workers), chunk_size)
        ]

        logger.info(
            "[Swarm/Chunked] Synthesis: %d workers split into %d chunks of "
            "up to %d each",
            len(sorted_workers), len(chunks), chunk_size,
        )

        # Per-chunk results: list of parsed dicts (successes only).
        chunk_parsed_dicts: List[Dict[str, Any]] = []
        sum_chunk_tokens = 0
        max_chunk_prompt_chars = 0

        for chunk_idx, chunk_workers in enumerate(chunks):
            logger.info(
                "[Swarm/Chunked] Chunk %d/%d: synthesizing %d workers",
                chunk_idx + 1, len(chunks), len(chunk_workers),
            )
            chunk_parsed, chunk_tokens, chunk_text, chunk_prompt_chars, _ = (
                self._synthesize_single(
                    chunk_workers, synthesis_prompt, event_log=event_log,
                )
            )
            sum_chunk_tokens += chunk_tokens
            if chunk_prompt_chars > max_chunk_prompt_chars:
                max_chunk_prompt_chars = chunk_prompt_chars

            if chunk_parsed is not None:
                chunk_parsed_dicts.append(chunk_parsed)
                logger.info(
                    "[Swarm/Chunked] Chunk %d/%d: success (%d tokens)",
                    chunk_idx + 1, len(chunks), chunk_tokens,
                )
            else:
                logger.info(
                    "[Swarm/Chunked] Chunk %d/%d: failed (no parsed output)",
                    chunk_idx + 1, len(chunks),
                )

            # Soft-hold check AFTER each chunk completes (= before next).
            # The first chunk doesn't need this because execute() already
            # checked at the fanout→synth boundary; subsequent chunks need
            # the check to honor a hold that landed mid-synthesis.
            if chunk_idx < len(chunks) - 1 and self._hold_paused():
                self._raise_hold_paused()

        # All chunks failed → return None, existing fallback runs.
        if not chunk_parsed_dicts:
            logger.warning(
                "[Swarm/Chunked] All %d chunks failed — returning None",
                len(chunks),
            )
            return None, sum_chunk_tokens, None, max_chunk_prompt_chars, False

        # Soft-hold check before meta dispatch.
        if self._hold_paused():
            self._raise_hold_paused()

        # Build meta synthesis input — same format as worker output joining.
        meta_workers: List[WorkerResult] = [
            WorkerResult(
                item_id=f"chunk-{i+1}",
                raw_output="",
                parsed=chunk_dict,
                success=True,
            )
            for i, chunk_dict in enumerate(chunk_parsed_dicts)
        ]
        logger.info(
            "[Swarm/Chunked] Meta-synthesis: %d/%d chunks succeeded, "
            "dispatching meta over %d partial syntheses",
            len(chunk_parsed_dicts), len(chunks), len(meta_workers),
        )
        meta_parsed, meta_tokens, meta_text, meta_prompt_chars, _ = (
            self._synthesize_single(
                meta_workers, synthesis_prompt, event_log=event_log,
            )
        )
        total_tokens = sum_chunk_tokens + meta_tokens
        max_prompt = max(max_chunk_prompt_chars, meta_prompt_chars)

        if meta_parsed is not None:
            logger.info(
                "[Swarm/Chunked] Meta-synthesis: success (%d tokens)",
                meta_tokens,
            )
            return meta_parsed, total_tokens, meta_text, max_prompt, False

        # Meta failed but chunks survived → return manually-deduped union.
        logger.warning(
            "[Swarm/Chunked] Meta-synthesis: failed; returning manually-"
            "deduped union of %d chunks",
            len(chunk_parsed_dicts),
        )
        union = self._dedup_chunk_union(chunk_parsed_dicts)
        return union, total_tokens, meta_text, max_prompt, True

    @staticmethod
    def _dedup_chunk_union(
        chunk_parsed_dicts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Union the chunk parsed dicts with the same defensiveness as
        concept_seeder.py:889-909's fallback dedup:

          - Concepts deduped by ``title.lower().strip()``.
          - Questions deduped by ``(text.lower().strip(),
            target_module.lower().strip())``.
          - Empty/missing titles → entry dropped.
          - Empty/missing question text → entry dropped.

        This keeps the chunked_meta_failed shape comparable to the
        single-call empty-synthesis fallback so downstream consumers
        don't need to learn a new path.
        """
        seen_titles: set = set()
        seen_questions: set = set()
        out_concepts: List[Dict[str, Any]] = []
        out_questions: List[Dict[str, Any]] = []

        for chunk_dict in chunk_parsed_dicts:
            for c in chunk_dict.get("concepts", []) or []:
                title = (c.get("title") or "").strip().lower()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    out_concepts.append(c)
            for q in chunk_dict.get("questions", []) or []:
                qtext = (q.get("question") or "").strip().lower()
                qmod = (q.get("target_module") or "").strip().lower()
                key = (qtext, qmod)
                if qtext and key not in seen_questions:
                    seen_questions.add(key)
                    out_questions.append(q)

        return {"concepts": out_concepts, "questions": out_questions}
```

Now wire the dispatcher. Update the `_synthesize` method body:

```python
    def _synthesize(
        self,
        worker_results: List[WorkerResult],
        synthesis_prompt: str,
        event_log: Optional[SwarmEventLogger] = None,
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str], int, bool]:
        """Phase 136 Part 09 Step 2: dispatch to single-call or chunked
        synthesis based on worker count.

        When the number of successful workers exceeds
        ``self.synthesis_chunk_max_workers``, split into chunks and run
        synthesis + meta-synthesis.  Otherwise run the existing single-
        call path unchanged.

        Same return shape as ``_synthesize_single``:
        ``(parsed, tokens, raw_text, prompt_chars, meta_failed)``.
        """
        successful = [r for r in worker_results if r.success and r.parsed]
        if not successful:
            # Identical to _synthesize_single's no-workers branch —
            # return early without inspecting threshold.  Important:
            # avoids dispatching an empty chunked run.
            logger.warning(
                "[Swarm] No successful workers with parsed output — "
                "skipping synthesis"
            )
            if event_log is not None:
                event_log.event("phase_skipped", phase="synthesis",
                                reason="no_successful_workers")
            return None, 0, None, 0, False

        if len(successful) > self.synthesis_chunk_max_workers:
            return self._synthesize_chunked(
                successful, synthesis_prompt, event_log=event_log,
            )
        return self._synthesize_single(
            successful, synthesis_prompt, event_log=event_log,
        )
```

Update `execute()` to capture `synthesis_chunk_count`. Find the call site (the place where `synthesis, synthesis_tokens, ...` is unpacked from `_synthesize`). Before it, calculate the count post-hoc — easier: add it directly to the `SwarmResult` construction:

```python
# Right before the SwarmResult(...) construction in execute(), compute:
n_successful = sum(1 for r in worker_results if r.success and r.parsed)
if n_successful > self.synthesis_chunk_max_workers:
    chunk_count = (
        (n_successful + self.synthesis_chunk_max_workers - 1)
        // self.synthesis_chunk_max_workers
    )
else:
    chunk_count = 1
```

And use it:

```python
result = SwarmResult(
    worker_results=worker_results,
    synthesis=synthesis,
    coordinator_plan=plan,
    stats=stats,
    event_log_path=str(event_log.path) if event_log and event_log.path else None,
    paused=paused,
    pause_info=pause_info,
    raw_synthesis_text=raw_synthesis_text,
    synthesis_prompt_chars=synthesis_prompt_chars,
    synthesis_meta_failed=synthesis_meta_failed,
    synthesis_chunk_count=chunk_count,
)
```

- [ ] **Step 5.4: Run the success-path tests to verify they pass**

```bash
.venv/bin/pytest tests/test_synthesis_chunked.py -v -k "below_threshold or above_threshold or chunked_full_success or chunked_synthesis_tokens or chunked_synthesis_prompt_chars"
```

Expected: 5 PASS.

- [ ] **Step 5.5: Run the broader test suite to confirm no regressions**

```bash
.venv/bin/pytest tests/test_synthesis_diagnostic.py tests/test_synthesis_chunked.py tests/test_soft_hold_primitive.py tests/test_cluster_parallel_batched.py --no-header -q
```

Expected: all PASS (16 from prior tasks + 5 new = 21 in the chunked + diagnostic files, plus existing soft-hold and cluster tests).

- [ ] **Step 5.6: Commit**

```bash
git add src/prep/core/swarm_orchestrator.py tests/test_synthesis_chunked.py
git commit -m "feat(phase136 part09 step2): chunked synthesis happy path

_synthesize_chunked splits successful workers into batches of
synthesis_chunk_max_workers (default 200, env-configurable), runs
_synthesize_single per chunk, then runs _synthesize_single once more
over the chunk parsed dicts as a meta-synthesis.

Dispatcher routes via len(successful) > threshold.  At threshold (200
== 200) → single-call; 201+ → chunked.  Sorting by item_id makes
chunk boundaries deterministic for production debugging + test fixtures.

Wiring:
- _synthesize is now the dispatcher; identical no-workers branch
  short-circuits before threshold check.
- _synthesize_chunked covers success + meta-success paths.
- _dedup_chunk_union is the meta-failed survivor dedup (used in Task 6).
- execute() computes synthesis_chunk_count from n_successful_workers
  and passes it to SwarmResult.

Tests (+5):
- Below-threshold (200 workers, threshold 200): single LLM call.
- Above-threshold (798 workers, threshold 200): 4 chunks + 1 meta = 5
  calls; verified by call_count + that every worker's item_id appears
  in exactly one chunk prompt.
- Full success: meta dict returned, meta_failed is False.
- Tokens summed across chunks + meta (100+200+300+400 = 1000).
- prompt_chars is MAX single prompt (verified with one 10K-char worker
  whose chunk's prompt dominates).

Per-chunk failure handling and meta-failed union dedup land in Task 6.
Soft-hold checks land in Task 7."
```

---

## Task 6: Per-chunk failure + meta-failed union dedup

**Files:**
- Modify: `tests/test_synthesis_chunked.py` — add tests 5, 6, 7, 19

- [ ] **Step 6.1: Write the failure-path tests**

Append to `tests/test_synthesis_chunked.py`:

```python
# ── Per-chunk + meta failure handling ──────────────────────────────


def test_chunked_some_chunks_fail_meta_gets_survivors():
    """2 of 4 chunks parse-fail.  Meta is called with the 2 survivors;
    result.synthesis is the meta dict; meta_failed is False.
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(798)  # 4 chunks

    # 4 chunk calls return alternating success/failure; 5th call (meta)
    # returns success.  Failure shape = unparseable text.
    chunk_returns = iter([
        ('{"concepts": [{"title": "C1"}], "questions": []}', 50),   # chunk 1 OK
        ("not-json-reasoning-blob",                          30),    # chunk 2 fail
        ('{"concepts": [{"title": "C3"}], "questions": []}', 50),   # chunk 3 OK
        ("more-reasoning-blob",                              30),    # chunk 4 fail
        ('{"concepts": [{"title": "MetaConsolidated"}], "questions": []}', 100),  # meta
    ])
    def _fake_call(**kwargs):
        return next(chunk_returns)

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       side_effect=_fake_call) as mock_llm:
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert mock_llm.call_count == 5, (
        f"Even with 2 chunks failing, meta call still fires; "
        f"expected 5 LLM calls, got {mock_llm.call_count}"
    )

    # Meta input prompt should contain C1 and C3 (survivors) but NOT
    # any of the failure blobs.
    meta_call_prompt = mock_llm.call_args_list[-1].kwargs.get("prompt", "")
    assert "C1" in meta_call_prompt, "Meta must receive surviving chunk 1's parsed JSON"
    assert "C3" in meta_call_prompt, "Meta must receive surviving chunk 3's parsed JSON"

    # Meta succeeded → use its output, meta_failed False.
    assert parsed == {"concepts": [{"title": "MetaConsolidated"}], "questions": []}
    assert meta_failed is False


def test_chunked_all_chunks_fail_returns_none():
    """All 4 chunks fail to parse; meta is NOT called; result is
    (None, sum_tokens, None, max_prompt_chars, False).
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(798)  # 4 chunks

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=("garbage non-json", 25)) as mock_llm:
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    # Only the 4 per-chunk calls — meta is skipped.
    assert mock_llm.call_count == 4, (
        f"All-chunks-fail must skip meta; expected 4 LLM calls, got "
        f"{mock_llm.call_count}"
    )
    assert parsed is None
    assert raw_text is None, (
        "Per-chunk raw text is NOT bubbled to SwarmResult on the "
        "chunked_all_failed path; operators consult the swarm event log "
        "for per-chunk evidence"
    )
    assert tokens == 4 * 25, "Tokens summed across all 4 chunk calls"
    assert meta_failed is False, (
        "All chunks failed → meta never ran → meta_failed remains False"
    )


def test_chunked_meta_fails_returns_deduped_union():
    """Chunks succeed; meta fails; result.synthesis is the deduped
    union of chunk parsed results; meta_failed is True.
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(400)  # 2 chunks

    # Chunk 1 and chunk 2 each return concepts with overlapping titles.
    chunk_returns = iter([
        ('{"concepts": [{"title": "Shared"}, {"title": "OnlyInChunk1"}], "questions": []}', 50),
        ('{"concepts": [{"title": "Shared"}, {"title": "OnlyInChunk2"}], "questions": []}', 50),
        ("unparseable-meta-failure", 75),
    ])
    def _fake_call(**kwargs):
        return next(chunk_returns)

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       side_effect=_fake_call):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert meta_failed is True, (
        "Meta failure after chunk successes must set meta_failed=True"
    )
    assert parsed is not None and "concepts" in parsed
    titles = {c["title"] for c in parsed["concepts"]}
    assert titles == {"Shared", "OnlyInChunk1", "OnlyInChunk2"}, (
        f"Union must dedupe 'Shared' but keep 'OnlyInChunk1' and "
        f"'OnlyInChunk2'; got {titles}"
    )
    # raw_synthesis_text carries the meta response text — operators see
    # what the failed meta call actually produced.
    assert raw_text == "unparseable-meta-failure"


def test_chunked_meta_fail_union_skips_entries_with_empty_titles():
    """The manual dedup mirrors concept_seeder.py:889-909 defensiveness:
    entries with empty/missing titles are skipped; questions with empty
    text are skipped.
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(400)  # 2 chunks

    chunk_returns = iter([
        (json.dumps({
            "concepts": [
                {"title": "Real"},
                {"title": ""},  # empty title — must be dropped
                {"title": "  "},  # whitespace only — must be dropped
                {"description": "missing title field"},  # missing — must be dropped
            ],
            "questions": [
                {"question": "Real q", "target_module": "m"},
                {"question": "", "target_module": "m"},  # empty — dropped
                {"target_module": "m"},  # missing question — dropped
            ],
        }), 50),
        (json.dumps({"concepts": [{"title": "Another"}], "questions": []}), 50),
        ("unparseable-meta", 75),
    ])
    def _fake_call(**kwargs):
        return next(chunk_returns)

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       side_effect=_fake_call):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert meta_failed is True
    titles = {c["title"] for c in parsed["concepts"]}
    assert titles == {"Real", "Another"}, (
        f"Empty/missing-title entries must be skipped; got {titles}"
    )
    q_texts = {q["question"] for q in parsed["questions"]}
    assert q_texts == {"Real q"}, (
        f"Empty/missing-question entries must be skipped; got {q_texts}"
    )
```

- [ ] **Step 6.2: Run the tests to verify they pass**

The implementation already landed in Task 5 (`_dedup_chunk_union` plus the meta-failure branch in `_synthesize_chunked`).

```bash
.venv/bin/pytest tests/test_synthesis_chunked.py -v -k "some_chunks_fail or all_chunks_fail or meta_fails_returns_deduped or meta_fail_union_skips"
```

Expected: 4 PASS.

If any fail, the dedup logic or the per-chunk failure branch may need a fix. The dedup is the static method `_dedup_chunk_union` and the per-chunk failure handling is `if chunk_parsed is not None: chunk_parsed_dicts.append(chunk_parsed)`.

- [ ] **Step 6.3: Commit**

```bash
git add tests/test_synthesis_chunked.py
git commit -m "test(phase136 part09 step2): per-chunk failure + meta-failed union dedup

Pins the chunked-synthesis failure-path behavior that was implemented
in Task 5:

  - Some chunks fail (2 of 4): meta is still called with the 2 survivors.
    Meta input prompt contains surviving chunks' parsed JSON but NOT
    the failed chunks' raw responses.
  - All chunks fail: meta is NOT called; returns (None, ..., False).
    Operators consult swarm event log for per-chunk parse_failure
    records.
  - Meta fails after chunk successes: returns manually-deduped union;
    meta_failed=True.  Union dedupes overlapping concept titles
    (verified with 'Shared' appearing in both chunks → kept once).
  - Dedup defensiveness mirrors concept_seeder.py:889-909: empty /
    whitespace-only / missing-key titles and questions are dropped.

Tests (+4).  No code changes — Task 5's _synthesize_chunked +
_dedup_chunk_union already implemented this behavior; these tests pin
it against future regression."
```

---

## Task 7: Soft-hold checks between chunks + before meta

**Files:**
- Modify: `tests/test_synthesis_chunked.py` — add tests 8 + 9

- [ ] **Step 7.1: Write the soft-hold tests**

Append to `tests/test_synthesis_chunked.py`:

```python
# ── Soft-hold (HoldPausedError) propagation ────────────────────────


def test_chunked_pause_between_chunks_propagates_hold_paused():
    """Mock _hold_paused to return True after chunk 1 completes; the
    chunked path must raise HoldPausedError; chunks 2-4 and meta must
    NOT dispatch.
    """
    from prep.services.pipeline.holds import HoldPausedError

    orch = _make_orch(chunk_max=200)
    orch.project_id = "proj-test"
    workers = _many_ok_workers(798)  # 4 chunks

    # Each chunk call returns valid JSON; meta would too if reached.
    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'

    # _hold_paused returns False on first poll (during chunk 1 dispatch),
    # then True after chunk 1 completes (between-chunks check fires).
    hold_returns = iter([False, True])
    def _fake_hold():
        return next(hold_returns)

    # _raise_hold_paused must raise — patch with the real-ish behavior.
    def _fake_raise():
        raise HoldPausedError(
            project_id="proj-test", endpoint_id="cloud:test",
        )

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 50)) as mock_llm:
        with patch.object(SwarmOrchestrator, "_hold_paused",
                           side_effect=_fake_hold):
            with patch.object(SwarmOrchestrator, "_raise_hold_paused",
                               side_effect=_fake_raise):
                with pytest.raises(HoldPausedError):
                    orch._synthesize(
                        workers,
                        synthesis_prompt="prefix {worker_outputs} suffix",
                        event_log=None,
                    )

    # Only chunk 1 dispatched before the pause was raised.
    assert mock_llm.call_count == 1, (
        f"Pause between chunks must stop dispatch; expected 1 LLM call, "
        f"got {mock_llm.call_count}"
    )


def test_chunked_pause_before_meta_propagates_hold_paused():
    """All chunks succeed; _hold_paused returns True at the pre-meta
    check; HoldPausedError raises; meta does NOT dispatch.
    """
    from prep.services.pipeline.holds import HoldPausedError

    orch = _make_orch(chunk_max=200)
    orch.project_id = "proj-test"
    workers = _many_ok_workers(400)  # 2 chunks

    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'

    # _hold_paused: False after chunk 1 (between-chunks check), True
    # before meta dispatch.
    hold_returns = iter([False, True])
    def _fake_hold():
        return next(hold_returns)

    def _fake_raise():
        raise HoldPausedError(
            project_id="proj-test", endpoint_id="cloud:test",
        )

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 50)) as mock_llm:
        with patch.object(SwarmOrchestrator, "_hold_paused",
                           side_effect=_fake_hold):
            with patch.object(SwarmOrchestrator, "_raise_hold_paused",
                               side_effect=_fake_raise):
                with pytest.raises(HoldPausedError):
                    orch._synthesize(
                        workers,
                        synthesis_prompt="prefix {worker_outputs} suffix",
                        event_log=None,
                    )

    # Both chunks dispatched; meta did NOT.
    assert mock_llm.call_count == 2, (
        f"Both chunks must dispatch before the pre-meta hold check "
        f"fires; meta must NOT dispatch; expected 2 LLM calls, got "
        f"{mock_llm.call_count}"
    )
```

- [ ] **Step 7.2: Run the soft-hold tests**

Task 5's implementation already includes the soft-hold checks (`if chunk_idx < len(chunks) - 1 and self._hold_paused(): self._raise_hold_paused()` after each chunk; `if self._hold_paused(): self._raise_hold_paused()` before meta).

```bash
.venv/bin/pytest tests/test_synthesis_chunked.py -v -k "pause_between or pause_before_meta"
```

Expected: 2 PASS.

- [ ] **Step 7.3: Commit**

```bash
git add tests/test_synthesis_chunked.py
git commit -m "test(phase136 part09 step2): soft-hold pause propagation in chunked path

Pins the HoldPausedError propagation behavior implemented in Task 5:

  - Pause AFTER chunk 1 completes (between-chunks check): chunks 2-4
    and meta do NOT dispatch; HoldPausedError raises with the held
    project_id/endpoint_id.
  - Pause AFTER all chunks succeed but BEFORE meta: meta does NOT
    dispatch; HoldPausedError raises.

The first chunk doesn't need an explicit check (execute()'s
fanout→synth boundary check already ran).  HoldPausedError propagates
up through _synthesize_chunked into execute()'s existing except
clause, which sets paused=True on the SwarmResult.

Tests (+2).  No code changes."
```

---

## Task 8: Deterministic chunking by item_id

**Files:**
- Modify: `tests/test_synthesis_chunked.py` — add test 3

- [ ] **Step 8.1: Write the determinism test**

Append to `tests/test_synthesis_chunked.py`:

```python
# ── Reproducibility ────────────────────────────────────────────────


def test_chunk_results_deterministic_by_item_id():
    """Workers passed in shuffled order produce the same chunk
    boundaries as sorted-by-item_id workers.  Critical for production
    debugging — a chunk's contents must be reproducible from the input
    list.
    """
    import random

    orch = _make_orch(chunk_max=100)
    sorted_workers = _many_ok_workers(250)  # 3 chunks of 100, 100, 50
    shuffled = sorted_workers.copy()
    random.Random(42).shuffle(shuffled)

    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'

    sorted_prompts = []
    shuffled_prompts = []

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 10)) as mock_llm:
        orch._synthesize(
            sorted_workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )
        # First 3 calls = per-chunk; 4th = meta.
        for call in mock_llm.call_args_list[:3]:
            sorted_prompts.append(call.kwargs.get("prompt", ""))

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 10)) as mock_llm:
        orch._synthesize(
            shuffled,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )
        for call in mock_llm.call_args_list[:3]:
            shuffled_prompts.append(call.kwargs.get("prompt", ""))

    assert sorted_prompts == shuffled_prompts, (
        "Chunk boundaries (and therefore per-chunk prompts) must be "
        "identical regardless of input worker order — _synthesize_chunked "
        "sorts by item_id before slicing"
    )
```

- [ ] **Step 8.2: Run the test**

Task 5's `_synthesize_chunked` sorts by item_id at the top. This test should already pass.

```bash
.venv/bin/pytest tests/test_synthesis_chunked.py::test_chunk_results_deterministic_by_item_id -v
```

Expected: PASS.

- [ ] **Step 8.3: Commit**

```bash
git add tests/test_synthesis_chunked.py
git commit -m "test(phase136 part09 step2): chunk boundaries are deterministic

Pins the item_id-sorted chunking behavior implemented in Task 5.
Workers passed in shuffled order produce byte-identical per-chunk
prompts as workers passed sorted.

This makes production debugging tractable: an operator can reproduce
the contents of a specific failing chunk from the list of successful
worker item_ids without needing to know the original fanout return
order.

Tests (+1).  No code changes."
```

---

## Task 9: Extend `_synthesis_diagnostic_fields` with chunked failure modes

**Files:**
- Modify: `src/prep/core/concept_seeder.py` — extend the classifier in `_synthesis_diagnostic_fields`
- Modify: `tests/test_synthesis_chunked.py` — add tests 11, 12

- [ ] **Step 9.1: Write the classifier tests**

Append to `tests/test_synthesis_chunked.py`:

```python
# ── Diagnostic classifier — chunked failure modes ──────────────────


from prep.core.concept_seeder import _synthesis_diagnostic_fields


def test_diagnostic_failure_mode_chunked_all_failed():
    """SwarmResult with synthesis_chunk_count > 1, synthesis=None,
    raw_text=None, prompt_chars>0 → failure_mode = chunked_all_failed.
    """
    r = SwarmResult(
        worker_results=[
            WorkerResult(item_id=f"m{i}", raw_output="", parsed=None,
                          success=False)
            for i in range(5)
        ],
        synthesis=None,
        raw_synthesis_text=None,
        synthesis_prompt_chars=500_000,  # non-zero — chunks were dispatched
        synthesis_chunk_count=4,
        synthesis_meta_failed=False,
    )

    out = _synthesis_diagnostic_fields(r)

    assert out["failure_mode"] == "chunked_all_failed"
    assert out["raw_synthesis_chars"] == 0


def test_diagnostic_failure_mode_chunked_meta_failed():
    """SwarmResult with synthesis_chunk_count > 1, synthesis (non-empty
    union), synthesis_meta_failed=True → failure_mode = chunked_meta_failed.
    """
    survivors_union = {
        "concepts": [{"title": "C1"}, {"title": "C2"}],
        "questions": [],
    }
    r = SwarmResult(
        worker_results=[
            WorkerResult(item_id=f"m{i}", raw_output="r",
                          parsed={"concepts": [{"title": "x"}]},
                          success=True)
            for i in range(5)
        ],
        synthesis=survivors_union,
        raw_synthesis_text="meta call failed with this response text",
        synthesis_prompt_chars=400_000,
        synthesis_chunk_count=4,
        synthesis_meta_failed=True,
    )

    out = _synthesis_diagnostic_fields(r)

    assert out["failure_mode"] == "chunked_meta_failed"
```

- [ ] **Step 9.2: Run the tests to verify they fail**

```bash
.venv/bin/pytest tests/test_synthesis_chunked.py::test_diagnostic_failure_mode_chunked_all_failed tests/test_synthesis_chunked.py::test_diagnostic_failure_mode_chunked_meta_failed -v
```

Expected: 2 FAIL — the current classifier doesn't know about chunked modes.

- [ ] **Step 9.3: Extend the classifier**

In `src/prep/core/concept_seeder.py`, find `_synthesis_diagnostic_fields`. Replace the failure-mode classification block (currently a 5-line if/elif/else chain after `raw_text = getattr(...)`) with the chunked-aware version:

```python
    raw_text = getattr(result, "raw_synthesis_text", None)
    prompt_chars = getattr(result, "synthesis_prompt_chars", 0)
    synthesis = getattr(result, "synthesis", None)
    chunk_count = getattr(result, "synthesis_chunk_count", 1)
    meta_failed = getattr(result, "synthesis_meta_failed", False)

    if raw_text is None:
        if prompt_chars == 0:
            failure_mode = "no_workers"
        elif chunk_count > 1:
            # Chunks were dispatched (prompt_chars > 0 → at least one
            # chunk's prompt was sent) but none returned parseable text
            # and meta was skipped → chunked_all_failed.  Per-chunk
            # raw responses are not bubbled here; see swarm event log
            # for per-chunk parse_failure records.
            failure_mode = "chunked_all_failed"
        else:
            failure_mode = "no_text"
    elif synthesis is None:
        failure_mode = "parse_failed"
    elif chunk_count > 1 and meta_failed:
        # Chunks succeeded, meta failed; we returned a manually-deduped
        # union of chunk survivors as result.synthesis.  This is the
        # chunked path's recovery-success — partial-quality output kept.
        failure_mode = "chunked_meta_failed"
    else:
        failure_mode = "parsed_but_empty"
```

- [ ] **Step 9.4: Run the tests to verify they pass**

```bash
.venv/bin/pytest tests/test_synthesis_chunked.py::test_diagnostic_failure_mode_chunked_all_failed tests/test_synthesis_chunked.py::test_diagnostic_failure_mode_chunked_meta_failed tests/test_synthesis_diagnostic.py -v --no-header -q
```

Expected: all PASS (existing 4 failure-mode tests in test_synthesis_diagnostic.py still pass because the single-call branches are unchanged).

- [ ] **Step 9.5: Commit**

```bash
git add src/prep/core/concept_seeder.py tests/test_synthesis_chunked.py
git commit -m "feat(phase136 part09 step2): diagnostic classifier learns chunked failure modes

_synthesis_diagnostic_fields gains two new failure_mode values:

  - chunked_all_failed: chunk_count > 1 AND no successful chunks
    (raw_text=None AND prompt_chars > 0).  Meta was never dispatched.
    Per-chunk raw responses are NOT bubbled to telemetry; operators
    use the swarm event log for chunk-level evidence.

  - chunked_meta_failed: chunk_count > 1 AND meta_failed=True.
    Chunks succeeded; meta failed; result.synthesis carries the
    manually-deduped union of survivors.  This is the recovery-success
    path — partial quality kept.

The existing four single-call modes (no_workers, no_text, parse_failed,
parsed_but_empty) classify identically.

Tests (+2).  Existing test_synthesis_diagnostic.py classifier tests
still pass (single-call branches unchanged)."
```

---

## Task 10: Emit `concepts_chunked_meta_failed` telemetry event

**Files:**
- Modify: `src/prep/core/concept_seeder.py` — add new `record_event` call in `seed_concepts_swarm`, after the existing `concepts_synthesis_failed` block
- Modify: `tests/test_synthesis_chunked.py` — add test 18

- [ ] **Step 10.1: Write the event-emission test**

Append to `tests/test_synthesis_chunked.py`:

```python
# ── concepts_chunked_meta_failed event emission ────────────────────


def test_chunked_meta_failed_event_fires_alongside_no_concepts_synthesis_failed(
    monkeypatch,
):
    """When SwarmResult has synthesis_meta_failed=True AND non-empty
    synthesis.concepts, concept_seeder must emit
    concepts_chunked_meta_failed event AND NOT emit
    concepts_synthesis_failed.

    We exercise the emission helper directly by simulating the gating
    logic concept_seeder uses: if meta_failed → fire the new event;
    if final_concepts empty → fire the existing event.  This is a
    contract test for the new emission site behavior.
    """
    # Test fixture: build the result + call the helper that emits.
    # Since seed_concepts_swarm is a 700-LoC function with heavy fixtures,
    # we factor out the emission helper as `_emit_chunked_meta_failed_event`
    # and test it directly (implementation step adds the helper).
    from prep.core.concept_seeder import _emit_chunked_meta_failed_event

    survivors_union = {
        "concepts": [{"title": "C1"}, {"title": "C2"}],
        "questions": [{"question": "Q1"}],
    }
    r = SwarmResult(
        worker_results=[
            WorkerResult(item_id=f"m{i}", raw_output="r",
                          parsed={"concepts": [{"title": "x"}]},
                          success=True)
            for i in range(5)
        ],
        synthesis=survivors_union,
        raw_synthesis_text="meta call failed",
        synthesis_prompt_chars=400_000,
        synthesis_chunk_count=4,
        synthesis_meta_failed=True,
    )

    captured: List[Dict[str, Any]] = []

    def _capture(index_dir, event_name, payload, **kwargs):
        captured.append({
            "event_name": event_name,
            "payload": payload,
            "kwargs": kwargs,
        })

    # Patch record_event at its import site within concept_seeder.
    import prep.services.pipeline_telemetry as telemetry_mod
    monkeypatch.setattr(telemetry_mod, "record_event", _capture)

    _emit_chunked_meta_failed_event(
        result=r,
        index_dir="/tmp/fake-index",
        project_id="proj-test",
        final_concepts=survivors_union["concepts"],
        final_questions=survivors_union["questions"],
    )

    assert len(captured) == 1
    assert captured[0]["event_name"] == "concepts_chunked_meta_failed"
    payload = captured[0]["payload"]
    # New event carries the diagnostic-fields surface PLUS the success
    # counters (concepts_returned + questions_returned).
    assert payload["failure_mode"] == "chunked_meta_failed"
    assert payload["concepts_returned"] == 2
    assert payload["questions_returned"] == 1
    assert payload["worker_count"] == 5
    assert payload["raw_synthesis_chars"] == len("meta call failed")
```

- [ ] **Step 10.2: Run the test to verify it fails**

```bash
.venv/bin/pytest tests/test_synthesis_chunked.py::test_chunked_meta_failed_event_fires_alongside_no_concepts_synthesis_failed -v
```

Expected: FAIL with `ImportError: cannot import name '_emit_chunked_meta_failed_event' from 'prep.core.concept_seeder'`.

- [ ] **Step 10.3: Add the emission helper to concept_seeder.py**

In `src/prep/core/concept_seeder.py`, find `_synthesis_diagnostic_fields`. Insert a new helper RIGHT AFTER it:

```python
def _emit_chunked_meta_failed_event(
    result: Any,
    index_dir: Any,
    project_id: Optional[str],
    final_concepts: list,
    final_questions: list,
) -> None:
    """Phase 136 Part 09 Step 2 — emit ``concepts_chunked_meta_failed``
    telemetry event when the chunked synthesis's meta call failed but
    chunk survivors were preserved as ``result.synthesis``.

    Distinct from ``concepts_synthesis_failed`` (which fires when
    synthesis returned no usable concepts at all and raw-worker
    fallback ran): this event signals the chunked path's recovery-
    success — partial-quality output kept, no fallback needed.

    Best-effort: telemetry write failures are silently ignored so a
    bad data_dir cannot fail the run.
    """
    try:
        from prep.services.pipeline_telemetry import record_event
        record_event(
            index_dir, "concepts_chunked_meta_failed",
            {
                "concepts_returned": len(final_concepts),
                "questions_returned": len(final_questions),
                "worker_count": len(getattr(result, "worker_results", []) or []),
                "successful_workers": sum(
                    1 for wr in (getattr(result, "worker_results", []) or [])
                    if wr.success
                ),
                **_synthesis_diagnostic_fields(result),
            },
            stage="concepts", project_id=project_id,
        )
    except Exception:
        pass
```

- [ ] **Step 10.4: Wire the helper into `seed_concepts_swarm`**

Find the block in `seed_concepts_swarm` that emits `concepts_synthesis_failed` (the existing block that runs when `synthesis_was_empty and result.worker_results`). After that block (i.e., after its closing brace on the dict + `stage="concepts", project_id=project_id,`), add the parallel block:

```python
    # Phase 136 Part 09 Step 2: chunked path's meta safety-net fired —
    # synthesis_was_empty is False (we returned the survivors' union as
    # result.synthesis), so the block above did NOT run.  Emit a
    # distinct event so operators can see the recovery happened.
    elif getattr(result, "synthesis_meta_failed", False):
        _emit_chunked_meta_failed_event(
            result=result,
            index_dir=index_dir,
            project_id=project_id,
            final_concepts=final_concepts,
            final_questions=final_questions,
        )
```

Note the `elif` — the existing block uses `if synthesis_was_empty and result.worker_results:`. The `elif` here means: ONLY emit `concepts_chunked_meta_failed` when the fallback above did NOT fire. This avoids double-emission.

- [ ] **Step 10.5: Run the test to verify it passes**

```bash
.venv/bin/pytest tests/test_synthesis_chunked.py::test_chunked_meta_failed_event_fires_alongside_no_concepts_synthesis_failed -v
```

Expected: PASS.

- [ ] **Step 10.6: Commit**

```bash
git add src/prep/core/concept_seeder.py tests/test_synthesis_chunked.py
git commit -m "feat(phase136 part09 step2): concepts_chunked_meta_failed telemetry event

The existing concepts_synthesis_failed event is gated on
synthesis_was_empty=True (raw-worker fallback path).  On the chunked
recovery-success path we return a non-empty deduped union as
result.synthesis, so synthesis_was_empty is False and the existing
event does not fire.  Without this commit the chunked_meta_failed
failure_mode classification would be dead code.

Implementation:
- New helper _emit_chunked_meta_failed_event(result, ...) builds the
  same diagnostic-fields surface as concepts_synthesis_failed but
  with a distinct event name + concepts_returned/questions_returned
  counters (success-shape, not fallback-shape).
- seed_concepts_swarm gains an elif branch that calls the helper when
  the fallback above did NOT fire AND result.synthesis_meta_failed is
  True.

Operators get two distinct signals:
  - concepts_synthesis_failed: raw-worker fallback ran (quality cliff)
  - concepts_chunked_meta_failed: chunked path's safety-net kicked in
    (partial quality kept)

Test (+1).  No regression in existing test_synthesis_diagnostic.py."
```

---

## Task 11: Full regression sweep + plan-level acceptance check

**Files:** None modified.

- [ ] **Step 11.1: Run the full Lane-C-adjacent test surface**

```bash
.venv/bin/pytest \
  tests/test_synthesis_diagnostic.py \
  tests/test_synthesis_chunked.py \
  tests/test_soft_hold_primitive.py \
  tests/test_cluster_parallel_batched.py \
  tests/test_llm_direct_sites_hold_guarded.py \
  tests/test_stale_hold_sweep.py \
  tests/test_augmenter.py \
  tests/test_epistemic_enrichment.py \
  --no-header -q
```

Expected: all PASS, including 19 tests in test_synthesis_chunked.py.

- [ ] **Step 11.2: Verify pre-existing failures are unchanged**

```bash
.venv/bin/pytest tests/test_concept_seeder_swarm.py::TestSeedConceptsRouting -v --no-header -q
```

Expected: 2 FAILED (same as pre-existing on main per Lane C closeout doc), 2 PASSED. The 2 failures are pre-existing, not introduced by Step 2.

- [ ] **Step 11.3: Verify the spec's acceptance criteria are met**

Walk the spec's "Acceptance criteria" section. Confirm:

- All 19 tests in test_synthesis_chunked.py pass. ✓
- Step 1's 14 tests in test_synthesis_diagnostic.py still pass. ✓
- test_soft_hold_primitive.py still passes (HoldPausedError propagation unchanged). ✓
- test_cluster_parallel_batched.py still passes (small-N callers stay on single-call path). ✓
- Merge gate not yet met (Step 1 telemetry from a live rebuild has not yet shown failure_mode=parsed_but_empty AND synthesis_prompt_chars > 1.5M). Branch stays unmerged.

- [ ] **Step 11.4: No commit needed in this task**

This task is a verification gate, not a code change.

If any regressions surfaced, return to the relevant earlier task and fix. If everything is green, Step 2 implementation is complete on `phase-136-part09`. The branch sits waiting for the merge-gate telemetry signal before integrating to `main`.
