"""P127-F5 regression: DeepeningLoop end-to-end pause-on-hold.

The audit-fix-A2 work (commit d6234e5b) added HoldPausedError catches
in deepening.py at the sequential dispatch (line 493), the threaded
future.result() (line 539), and the iteration-level boundary
(line 559).  But until this test, no integration test exercised the
full DeepeningLoop.run() with a mid-batch pause.

This test plugs a fake EpistemicEnricher into the loop, makes
``enrich_node`` raise HoldPausedError after the first node, and asserts:

  1. loop.run() returns a DeepeningResult without raising.
  2. result.iterations == 1 (we paused mid-iteration-1, not at boundary).
  3. _write_epistemic was called — the partial work was checkpointed.
  4. The "deepening_complete" progress beacon was NOT emitted; the
     dashboard must not flip the stage to "done" on a paused run.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from prep.core.deepening import DeepeningLoop, DeepeningResult
from prep.core.epistemic_score import EpistemicScore, EpistemicEntry
from prep.services.pipeline.holds import HoldPausedError


def _make_score(node_id: str, composite: float) -> EpistemicScore:
    return EpistemicScore(
        node_id=node_id,
        composite=composite,
        summary_confidence=0.5,
        validation_status=0.0,
        neighbor_coverage=0.5,
        cross_reference_density=0.0,
        enrichment_depth=0.5,
    )


def _make_entry(node_id: str) -> EpistemicEntry:
    """Construct a minimal EpistemicEntry the loop can checkpoint."""
    return EpistemicEntry(
        node_id=node_id,
        extended_summary="paused-test enrichment",
        domain_tags=[],
        architecture_layer="core",
        epistemic_confidence=0.5,
        pass_number=2,
        model="fake-test-model",
        enriched_at="2026-05-27T00:00:00Z",
    )


class _FakePausingEnricher:
    """EpistemicEnricher-shaped fake that raises HoldPausedError on the
    Nth enrich_node call.

    Each call records the requested node id.  ``_write_epistemic`` records
    the dict it was handed so the test can assert the partial checkpoint
    survived the pause.
    """

    def __init__(self, raise_on_call: int = 2) -> None:
        # Two below-threshold nodes so the queue produces a batch with >1
        # entry — guarantees the pause happens mid-batch, not at the
        # outer iteration boundary.
        self._scores: Dict[str, EpistemicScore] = {
            "n1": _make_score("n1", 0.1),
            "n2": _make_score("n2", 0.2),
        }
        self._nodes: List[Dict[str, Any]] = [
            {"id": "n1", "path": "a.py"}, {"id": "n2", "path": "b.py"},
        ]
        self._raise_on_call = raise_on_call
        self.call_count = 0
        self.enriched_ids: List[str] = []
        self.write_calls: List[Dict[str, EpistemicEntry]] = []

    # ── Loaders ────────────────────────────────────────────────────
    def compute_all_scores(self) -> Dict[str, EpistemicScore]:
        return dict(self._scores)

    def load_augmentations(self) -> Dict[str, Any]:
        return {}

    def load_trace_edges(self) -> List[Dict[str, Any]]:
        return []

    def load_trace_nodes(self) -> List[Dict[str, Any]]:
        return list(self._nodes)

    def load_existing(self) -> Dict[str, EpistemicEntry]:
        # Empty — every queued node is a fresh enrichment (pass 2).
        return {}

    # ── The under-test method ─────────────────────────────────────
    def enrich_node(
        self,
        node: Dict[str, Any],
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
        augmentations: Dict[str, Any],
        existing_epistemic: Dict[str, EpistemicEntry],
    ) -> Optional[EpistemicEntry]:
        self.call_count += 1
        nid = node["id"]
        if self.call_count == self._raise_on_call:
            raise HoldPausedError(project_id="proj-test", endpoint_id="cloud:test")
        self.enriched_ids.append(nid)
        return _make_entry(nid)

    # ── Checkpoint writer ─────────────────────────────────────────
    def _write_epistemic(self, existing: Dict[str, EpistemicEntry]) -> None:
        # Capture a snapshot — the loop hands us the live dict, so we
        # copy to preserve the state at write time.
        self.write_calls.append(dict(existing))


def _progress_recorder() -> tuple[Callable[[str, int, int], None], List[tuple]]:
    """Return a progress-callback + the list it appends each call into."""
    events: List[tuple] = []

    def cb(label: str, current: int, total: int) -> None:
        events.append((label, current, total))

    return cb, events


def test_deepening_loop_pauses_mid_batch_returns_paused_result(monkeypatch, tmp_path) -> None:
    """End-to-end: HoldPausedError raised on the 2nd enrich_node call
    inside iteration 1 must produce a DeepeningResult with partial
    work checkpointed, no exception, and no completion beacon.
    """
    # Force sequential path so the pause sequencing is deterministic.
    monkeypatch.setattr("prep.core.deepening._get_llm_concurrency", lambda _stage: 1)

    enricher = _FakePausingEnricher(raise_on_call=2)
    loop = DeepeningLoop(
        enricher=enricher,
        index_dir=tmp_path,
        max_iterations=5,
        batch_size=10,
        # Both fake scores are below 0.6, so they both enqueue.
        settled_threshold=0.6,
        residual_threshold=0.01,
        project_id="proj-test",
    )

    cb, events = _progress_recorder()

    # The contract: NO exception bubbles out of run().
    result = loop.run(progress_callback=cb)

    # ── Shape: returned a DeepeningResult, not raised ─────────────
    assert isinstance(result, DeepeningResult)

    # ── Partial iterations recorded ───────────────────────────────
    # We paused inside iteration 1 — the loop should record iterations=1
    # (the iteration in which the pause occurred) and NOT continue to 5.
    assert result.iterations == 1, (
        f"expected iterations=1 (paused mid-iteration-1), got {result.iterations}"
    )

    # ── Pre-pause work was preserved ──────────────────────────────
    # First call succeeded, second raised — so one node enriched.
    assert enricher.call_count == 2, f"expected 2 enrich_node calls, got {enricher.call_count}"
    assert len(enricher.enriched_ids) == 1, (
        f"expected exactly 1 successful enrichment before pause, got {enricher.enriched_ids}"
    )
    assert result.total_enriched == 1, (
        f"expected total_enriched=1, got {result.total_enriched}"
    )

    # ── Checkpoint persisted ──────────────────────────────────────
    # _write_epistemic must be invoked even when the iteration ended
    # via pause — that is the "checkpoint flushed" guarantee.
    assert enricher.write_calls, "expected _write_epistemic to be called for the checkpoint"
    last_write = enricher.write_calls[-1]
    enriched_node = enricher.enriched_ids[0]
    assert enriched_node in last_write, (
        f"expected partial enrichment for {enriched_node} in checkpoint, got keys {list(last_write)}"
    )

    # ── No "complete" beacon on a paused run ──────────────────────
    # The dashboard must not flip the stage UI to "done"; the
    # _deepening_worker caller relies on the absence of this beacon.
    complete_events = [e for e in events if e[0] == "deepening_complete"]
    assert not complete_events, (
        f"deepening_complete beacon must not fire on a paused run, got {complete_events}"
    )


def test_deepening_loop_pause_signals_via_progress_iteration_label(
    monkeypatch, tmp_path
) -> None:
    """The 'deepening_iteration' beacon should still fire for the paused
    iteration — operators need to see that work began before the pause.
    """
    monkeypatch.setattr("prep.core.deepening._get_llm_concurrency", lambda _stage: 1)

    enricher = _FakePausingEnricher(raise_on_call=1)  # pause immediately
    loop = DeepeningLoop(
        enricher=enricher,
        index_dir=tmp_path,
        max_iterations=3,
        batch_size=10,
        project_id="proj-test",
    )
    cb, events = _progress_recorder()
    loop.run(progress_callback=cb)

    iter_events = [e for e in events if e[0] == "deepening_iteration"]
    assert iter_events, "expected at least one deepening_iteration progress event"
    # The iteration beacon fires BEFORE work, so it goes through even
    # when iteration-1 pauses immediately.
    assert iter_events[0][1] == 0  # zero-indexed iteration counter


def test_deepening_loop_threaded_branch_pauses_cleanly(
    monkeypatch, tmp_path
) -> None:
    """Threaded branch: concurrency > 1 → enrich_node runs on llm_pool;
    HoldPausedError raised inside a future must bubble out of
    future.result() and be caught at the iteration-level boundary
    (deepening.py:559), the iteration cancels pending futures, and
    loop.run() returns a paused-aware result without raising.
    """
    # Force the threaded path.
    monkeypatch.setattr("prep.core.deepening._get_llm_concurrency", lambda _stage: 4)

    enricher = _FakePausingEnricher(raise_on_call=1)
    loop = DeepeningLoop(
        enricher=enricher,
        index_dir=tmp_path,
        max_iterations=3,
        batch_size=10,
        project_id="proj-test",
    )
    cb, events = _progress_recorder()
    result = loop.run(progress_callback=cb)

    assert isinstance(result, DeepeningResult)
    # We paused inside iteration 1 — the loop records iterations=1 and
    # does not progress to the convergence-check phase that bumps it
    # further.
    assert result.iterations == 1, (
        f"expected iterations=1 (paused mid-iteration-1), got {result.iterations}"
    )
    # Checkpoint persisted even on the threaded branch — the iteration
    # falls through to _write_epistemic and the pause-break block.
    assert enricher.write_calls, "expected _write_epistemic to be called on threaded pause"
    # No "deepening_complete" beacon on a paused run.
    complete_events = [e for e in events if e[0] == "deepening_complete"]
    assert not complete_events, (
        f"deepening_complete must not fire on paused run, got {complete_events}"
    )
