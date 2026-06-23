"""Phase 145 T3 — pytest coverage for tools.phase145_uat.run_session.

Covers:
    - parse_iter_result over real fixture files (no I/O mocking — per
      feedback_test_full_import_chain.md, the seam under test (filesystem
      read) is exercised real).
    - render_scorecard over synthetic manifests (pass-only, mixed, empty).
    - SessionManifest JSON round-trip.
    - is_completed pre/post-condition.
    - daemon_healthy failure path (no daemon needed; we hit a guaranteed
      unreachable URL).
    - persist_manifest atomic write semantics.

NOT covered here (deferred to integration runs against HomeColab):
    - run_one_iter subprocess invocation — needs a real playwright_smoke
      install + a live daemon. Smoke-tested via the end-to-end session
      run that produces SCORECARD_uat_baseline_*.md per T4.
    - The new playwright_smoke --refresh-at-secs / --update-at-secs flags
      end-to-end. Argparse smoke-test below catches the obvious mis-wires.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.phase145_uat.run_session import (
    INV_TO_FINDING,
    OPERATIONS,
    OP_BY_ID,
    SHIPPED_INVARIANTS,
    IterResult,
    SessionManifest,
    _CANCELLABLE_PHASES,
    _NOTES_MAX_LEN,
    _TERMINAL_PHASES,
    _clip_notes,
    _md_cell,
    _resolve_evidence_paths,
    _summarise_event_kind,
    cancel_and_quiesce,
    daemon_healthy,
    is_completed,
    parse_iter_result,
    persist_manifest,
    project_pipeline_ready,
    render_scorecard,
    wait_for_pipeline_idle,
)

from tools.playwright_smoke import (
    _NON_RUNNING_PHASES,
    _VERDICT_ELIGIBLE_PHASES,
    _advance_scheduled_actions,
    is_any_running,
)
from tools.phase145_uat.invariants import ACTIVE_PIPELINE_PHASES, GROUPS


# ── Fixture builders ──────────────────────────────────────────────


def _write_smoke_output(
    base: Path,
    *,
    mode: str,
    summary: dict,
    events: list[dict],
) -> Path:
    """Mimic playwright_smoke's per-iteration output tree on disk.

    Returns the `run_<ts>` dir that parse_iter_result expects to receive.
    """
    run_dir = base / "run_20260622T120000Z"
    mode_dir = run_dir / mode
    mode_dir.mkdir(parents=True, exist_ok=True)
    (mode_dir / "summary.json").write_text(json.dumps(summary))
    with (mode_dir / "events.jsonl").open("w") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")
    return run_dir


def _op(op_id: str):
    return OP_BY_ID[op_id]


# ── parse_iter_result ─────────────────────────────────────────────


class TestParseIterResult:
    def test_clean_pass_marks_every_invariant_passing(self, tmp_path):
        op = _op("Op-1")
        run_dir = _write_smoke_output(
            tmp_path,
            mode=op.smoke_mode,
            summary={"mode": "rebuild", "pass": True,
                     "started_at": 1_750_000_000.0, "ended_at": 1_750_000_300.0,
                     "desync_count": 0, "anomaly_count": 0,
                     "invariant_failure_count": 0, "error_count": 0,
                     "stages_seen": ["structural"], "trigger_reason": "",
                     "notes": []},
            events=[
                {"ts": 1_750_000_010.0, "kind": "stage-start", "stage": "structural"},
            ],
        )
        r = parse_iter_result(op, 1, run_dir)
        assert r.status == "pass"
        assert r.invariants == {k: True for k in SHIPPED_INVARIANTS}
        assert r.failures == []
        assert r.started_at.startswith("2025-06-15")  # UTC ISO from epoch
        assert r.ended_at  # populated

    def test_invariant_failure_flips_specific_inv_to_false(self, tmp_path):
        op = _op("Op-3")
        run_dir = _write_smoke_output(
            tmp_path,
            mode=op.smoke_mode,
            summary={"mode": "rebuild", "pass": False,
                     "started_at": 1_750_000_000.0, "ended_at": 1_750_000_300.0,
                     "desync_count": 0, "anomaly_count": 0,
                     "invariant_failure_count": 1, "error_count": 0,
                     "stages_seen": ["enrichment"], "trigger_reason": "",
                     "notes": []},
            events=[
                {"ts": 1_750_000_040.0, "kind": "invariant_failure",
                 "invariant_id": "I13", "label": "current-stage decoration",
                 "evidence": {"group": "deep_enrichment", "marked_count": 0}},
            ],
        )
        r = parse_iter_result(op, 2, run_dir)
        assert r.status == "fail"
        assert r.invariants["I13"] is False
        assert r.invariants["I1"] is True
        assert r.invariants["I2"] is True
        assert r.invariants["I3"] is True
        assert len(r.failures) == 1
        assert r.failures[0]["invariant_id"] == "I13"
        assert r.failures[0]["count"] == 1
        assert r.failures[0]["first_evidence"]["group"] == "deep_enrichment"

    def test_multiple_failures_for_same_invariant_counted(self, tmp_path):
        op = _op("Op-4")
        run_dir = _write_smoke_output(
            tmp_path,
            mode=op.smoke_mode,
            summary={"mode": "rebuild", "pass": False,
                     "started_at": 1_750_000_000.0, "ended_at": 1_750_000_400.0,
                     "desync_count": 0, "anomaly_count": 0,
                     "invariant_failure_count": 3, "error_count": 0,
                     "stages_seen": [], "trigger_reason": "", "notes": []},
            events=[
                {"ts": 1, "kind": "invariant_failure", "invariant_id": "I3",
                 "label": "downstream not complete", "evidence": {"k": 1}},
                {"ts": 2, "kind": "invariant_failure", "invariant_id": "I3",
                 "label": "downstream not complete", "evidence": {"k": 2}},
                {"ts": 3, "kind": "invariant_failure", "invariant_id": "I1",
                 "label": "one running row per group", "evidence": {"k": 3}},
            ],
        )
        r = parse_iter_result(op, 1, run_dir)
        assert r.invariants["I3"] is False
        assert r.invariants["I1"] is False
        assert r.invariants["I2"] is True
        assert r.invariants["I13"] is True
        # Sorted alphabetically by invariant_id ⇒ I1 first.
        assert [f["invariant_id"] for f in r.failures] == ["I1", "I3"]
        # First evidence is the EARLIEST event for that invariant
        # (preserves chronological insight, e.g. "this is the moment it
        # first broke" rather than "this is the latest re-observation").
        i3 = next(f for f in r.failures if f["invariant_id"] == "I3")
        assert i3["count"] == 2
        assert i3["first_evidence"] == {"k": 1}

    def test_missing_summary_returns_error_status(self, tmp_path):
        op = _op("Op-1")
        # Create the mode dir but no summary.json.
        (tmp_path / "run_x" / op.smoke_mode).mkdir(parents=True)
        r = parse_iter_result(op, 1, tmp_path / "run_x")
        assert r.status == "error"
        assert "missing summary" in r.notes
        # Invariants default to all-True so the row is not misread as a
        # silent invariant failure ("error" status carries the signal).
        assert r.invariants == {k: True for k in SHIPPED_INVARIANTS}

    def test_malformed_summary_returns_error_status(self, tmp_path):
        op = _op("Op-1")
        run_dir = tmp_path / "run_y"
        (run_dir / op.smoke_mode).mkdir(parents=True)
        (run_dir / op.smoke_mode / "summary.json").write_text("{not json")
        r = parse_iter_result(op, 1, run_dir)
        assert r.status == "error"
        assert "parse error" in r.notes

    def test_malformed_event_line_is_skipped_not_fatal(self, tmp_path):
        op = _op("Op-2")
        mode_dir = tmp_path / "run_z" / op.smoke_mode
        mode_dir.mkdir(parents=True)
        (mode_dir / "summary.json").write_text(json.dumps({
            "mode": "incremental", "pass": True,
            "started_at": 1.0, "ended_at": 2.0,
            "desync_count": 0, "anomaly_count": 0,
            "invariant_failure_count": 0, "error_count": 0,
            "stages_seen": [], "trigger_reason": "", "notes": [],
        }))
        (mode_dir / "events.jsonl").write_text(
            "not json\n"
            "\n"  # blank line
            + json.dumps({"kind": "note"}) + "\n"
            + json.dumps({"kind": "invariant_failure", "invariant_id": "I1",
                          "evidence": {"x": 1}}) + "\n"
        )
        r = parse_iter_result(op, 1, tmp_path / "run_z")
        # Malformed line ignored; valid invariant_failure picked up; pass
        # flipped to fail due to invariant failure event.
        assert r.status == "fail"
        assert r.invariants["I1"] is False

    def test_invariant_failure_event_with_missing_id_is_skipped(self, tmp_path):
        op = _op("Op-1")
        run_dir = _write_smoke_output(
            tmp_path,
            mode=op.smoke_mode,
            summary={"mode": "rebuild", "pass": True,
                     "started_at": 1.0, "ended_at": 2.0,
                     "desync_count": 0, "anomaly_count": 0,
                     "invariant_failure_count": 0, "error_count": 0,
                     "stages_seen": [], "trigger_reason": "", "notes": []},
            events=[
                {"kind": "invariant_failure", "evidence": {}},  # no invariant_id
            ],
        )
        r = parse_iter_result(op, 1, run_dir)
        assert r.failures == []
        assert all(r.invariants.values())


# ── parse_iter_result — error/desync evidence in notes (§9.3 #17) ─


class TestParseIterResultSurfacesErrorEvidence:
    """§9.3 #17 reframe — bare-fail rows in the post-I3-fix SCORECARD looked
    like `status=FAIL, I1/I2/I3/I13 ✓✓✓✓, notes='cancel-quiesce: already
    idle'`. Reading the original starter prompt suggested rc-vs-summary
    mismatch; the actual evidence (events.jsonl walk) showed THREE distinct
    real failures hiding in plain sight:

      - Op-1 iter 1: 3 desync events (no matching invariant in shipped set)
      - Op-2 iter 3: 1 error event "409 Conflict" on /pipeline/all
      - Op-3/Op-4 (6 iters): 1 error event "timed out" on api.rebuild()

    parse_iter_result previously walked only kind="invariant_failure" so all
    three classes rendered as bare-fail. The fix surfaces error+desync event
    evidence in IterResult.notes so the SCORECARD Notes column carries
    enough signal for a reviewer to triage without opening any jsonl file.
    """

    def test_error_event_surfaced_in_notes(self, tmp_path):
        op = _op("Op-3")
        run_dir = _write_smoke_output(
            tmp_path,
            mode=op.smoke_mode,
            summary={"mode": op.smoke_mode, "started_at": 1.0, "ended_at": 2.0,
                     "pass": False, "desync_count": 0, "anomaly_count": 0,
                     "invariant_failure_count": 0, "error_count": 1,
                     "stages_seen": [], "trigger_reason": "", "notes": []},
            events=[
                {"ts": 1.5, "where": "rebuild", "detail": "timed out", "kind": "error"},
            ],
        )
        r = parse_iter_result(op, 1, run_dir)
        assert r.status == "fail"
        # All shipped invariants pass (none of them caught this) — the
        # signal must come from notes.
        assert all(r.invariants.values())
        assert "error" in r.notes.lower()
        assert "timed out" in r.notes

    def test_desync_events_surfaced_in_notes(self, tmp_path):
        op = _op("Op-1")
        run_dir = _write_smoke_output(
            tmp_path,
            mode=op.smoke_mode,
            summary={"mode": op.smoke_mode, "started_at": 1.0, "ended_at": 100.0,
                     "pass": False, "desync_count": 3, "anomaly_count": 0,
                     "invariant_failure_count": 0, "error_count": 0,
                     "stages_seen": [], "trigger_reason": "", "notes": []},
            events=[
                {"ts": 10.0, "kind": "desync", "stage": "structural",
                 "subtype": "progress_gap"},
                {"ts": 20.0, "kind": "desync", "stage": "catalogue",
                 "subtype": "progress_gap"},
                {"ts": 30.0, "kind": "desync", "stage": "knowledge",
                 "subtype": "api_running_dom_not_running"},
            ],
        )
        r = parse_iter_result(op, 1, run_dir)
        assert r.status == "fail"
        assert all(r.invariants.values())
        assert "desync" in r.notes.lower()
        # Count surfaced so the reviewer sees magnitude, not just kind.
        assert "3" in r.notes

    def test_combines_errors_and_desyncs_in_notes(self, tmp_path):
        op = _op("Op-4")
        run_dir = _write_smoke_output(
            tmp_path,
            mode=op.smoke_mode,
            summary={"mode": op.smoke_mode, "started_at": 1.0, "ended_at": 30.0,
                     "pass": False, "desync_count": 2, "anomaly_count": 0,
                     "invariant_failure_count": 0, "error_count": 1,
                     "stages_seen": [], "trigger_reason": "", "notes": []},
            events=[
                {"ts": 5.0, "kind": "desync", "stage": "structural",
                 "subtype": "progress_gap"},
                {"ts": 10.0, "kind": "desync", "stage": "catalogue",
                 "subtype": "progress_gap"},
                {"ts": 20.0, "where": "rebuild", "detail": "timed out",
                 "kind": "error"},
            ],
        )
        r = parse_iter_result(op, 1, run_dir)
        assert r.status == "fail"
        assert "error" in r.notes.lower()
        assert "desync" in r.notes.lower()

    def test_does_not_surface_evidence_when_pass_is_true(self, tmp_path):
        """A passing iter's notes must stay clean. We only walk error/desync
        events when the smoke flagged failure — otherwise warning events
        from defensive code paths would pollute clean rows.
        """
        op = _op("Op-1")
        run_dir = _write_smoke_output(
            tmp_path,
            mode=op.smoke_mode,
            summary={"mode": op.smoke_mode, "started_at": 1.0, "ended_at": 100.0,
                     "pass": True, "desync_count": 0, "anomaly_count": 0,
                     "invariant_failure_count": 0, "error_count": 0,
                     "stages_seen": [], "trigger_reason": "", "notes": []},
            events=[
                # Stray error event from a non-fatal snapshot failure that
                # the smoke chose to keep `pass=True` despite. Don't
                # surface it.
                {"ts": 5.0, "where": "snap", "detail": "screenshot failed",
                 "kind": "error"},
            ],
        )
        r = parse_iter_result(op, 1, run_dir)
        assert r.status == "pass"
        assert "error" not in (r.notes or "").lower()

    def test_long_error_detail_truncated_in_notes(self, tmp_path):
        """Tracebacks and HTTPStatusError messages can be 500+ chars and
        would blow out the markdown table width. Cap the surfaced detail.
        """
        op = _op("Op-2")
        long_detail = "HTTPStatusError(" + "x" * 600 + ")"
        run_dir = _write_smoke_output(
            tmp_path,
            mode=op.smoke_mode,
            summary={"mode": op.smoke_mode, "started_at": 1.0, "ended_at": 2.0,
                     "pass": False, "desync_count": 0, "anomaly_count": 0,
                     "invariant_failure_count": 0, "error_count": 1,
                     "stages_seen": [], "trigger_reason": "", "notes": []},
            events=[
                {"ts": 1.5, "where": "mode_runner", "detail": long_detail,
                 "kind": "error"},
            ],
        )
        r = parse_iter_result(op, 1, run_dir)
        # Detail surfaced but bounded — the test guards against the full
        # 600-char dump landing in the SCORECARD table cell.
        assert len(r.notes) <= 200

    def test_invariant_failures_take_priority_over_error_notes(self, tmp_path):
        """When a real invariant fires, the failures list already populates
        the Notes column. Don't double-up by also writing the raw error/
        desync evidence — the invariant evidence is the authoritative
        signal and the failures list is what gets summarized.
        """
        op = _op("Op-1")
        run_dir = _write_smoke_output(
            tmp_path,
            mode=op.smoke_mode,
            summary={"mode": op.smoke_mode, "started_at": 1.0, "ended_at": 100.0,
                     "pass": False, "desync_count": 1, "anomaly_count": 0,
                     "invariant_failure_count": 1, "error_count": 0,
                     "stages_seen": [], "trigger_reason": "", "notes": []},
            events=[
                {"ts": 5.0, "kind": "desync", "stage": "structural",
                 "subtype": "progress_gap"},
                {"ts": 10.0, "kind": "invariant_failure", "invariant_id": "I3",
                 "label": "intra-group stale-leak",
                 "evidence": {"stage": "atlas"}},
            ],
        )
        r = parse_iter_result(op, 1, run_dir)
        assert r.invariants["I3"] is False
        # failures list populated — the SCORECARD renderer uses
        # _summarise_failures for the Notes cell when notes is empty, so
        # leaving notes empty is the right behavior.
        assert any(f["invariant_id"] == "I3" for f in r.failures)
        # No need to also dump the raw desync into notes — the invariant
        # surface is authoritative.
        assert r.notes == "" or "desync" not in r.notes.lower()


# ── render_scorecard ──────────────────────────────────────────────


def _manifest_with(results: list[IterResult]) -> SessionManifest:
    m = SessionManifest(
        session_id="2026-06-22T120000Z",
        project_id="proj-uuid",
        iterations=3,
        operations=[op.id for op in OPERATIONS],
        api_url="http://localhost:8400",
        dashboard_url="http://localhost:5174",
        out_root="tests/eval/ui_smoke",
    )
    m.completed = results
    return m


class TestRenderScorecard:
    def test_header_and_table_columns_present_on_empty_run(self):
        m = _manifest_with([])
        md = render_scorecard(m, today="2026-06-22")
        assert "# Phase 145 UAT Scorecard — 2026-06-22" in md
        assert "**Project:** `proj-uuid`" in md
        assert "**Iterations per op:** 3" in md
        assert "**Iterations recorded:** 0/12 (partial)" in md
        assert "NOTE: partial session" in md
        assert "Status legend:" in md
        assert "| Op | Iter | Status | I1 | I2 | I3 | I13 | Notes |" in md
        # No iterations recorded ⇒ explicit "none yet" fallback.
        assert "No iterations recorded yet" in md

    def test_pass_row_renders_with_checkmarks(self):
        m = _manifest_with([
            IterResult(op_id="Op-1", iter_num=1, run_dir="/tmp/run_a",
                       status="pass", invariants={k: True for k in SHIPPED_INVARIANTS}),
        ])
        md = render_scorecard(m, today="2026-06-22")
        assert "| Op-1 Rebuild All clean | 1 | pass | ✓ | ✓ | ✓ | ✓ | clean |" in md

    def test_fail_row_renders_with_x_and_failure_summary(self):
        m = _manifest_with([
            IterResult(
                op_id="Op-3", iter_num=2, run_dir="/tmp/run_b",
                status="fail",
                invariants={"I1": True, "I2": True, "I3": True, "I13": False},
                failures=[{"invariant_id": "I13", "count": 4,
                           "first_evidence": {"group": "deep_enrichment"}}],
            ),
        ])
        md = render_scorecard(m, today="2026-06-22")
        assert "| Op-3 Mid-rebuild refresh | 2 | FAIL |" in md
        assert "✓ | ✓ | ✓ | ✗" in md
        assert "I13 ×4" in md
        # Mapped-to-findings row also emitted.
        assert "Op-3 iter 2 I13" in md
        assert INV_TO_FINDING["I13"] in md

    def test_trends_emit_per_op_per_invariant_failure_rate(self):
        m = _manifest_with([
            IterResult(op_id="Op-4", iter_num=1, run_dir="/r1", status="fail",
                       invariants={"I1": False, "I2": True, "I3": True, "I13": True}),
            IterResult(op_id="Op-4", iter_num=2, run_dir="/r2", status="fail",
                       invariants={"I1": False, "I2": True, "I3": True, "I13": True}),
            IterResult(op_id="Op-4", iter_num=3, run_dir="/r3", status="pass",
                       invariants={"I1": True, "I2": True, "I3": True, "I13": True}),
        ])
        md = render_scorecard(m, today="2026-06-22")
        assert "Op-4 I1" in md
        assert "2/3 (66.7%)" in md

    def test_skipped_and_errored_iters_surface_in_trends(self):
        m = _manifest_with([
            IterResult(op_id="Op-1", iter_num=1, run_dir="", status="skipped",
                       invariants={k: True for k in SHIPPED_INVARIANTS},
                       notes="daemon down"),
            IterResult(op_id="Op-1", iter_num=2, run_dir="", status="error",
                       invariants={k: True for k in SHIPPED_INVARIANTS},
                       notes="subprocess timeout"),
        ])
        md = render_scorecard(m, today="2026-06-22")
        # Trend denominator is PLANNED iters (3), not observed (2),
        # so a partial session doesn't silently understate severity.
        assert "1/3 iter(s) skipped" in md
        assert "1/3 iter(s) errored" in md

    def test_rows_sorted_by_op_then_iter(self):
        m = _manifest_with([
            IterResult(op_id="Op-4", iter_num=2, run_dir="/r", status="pass",
                       invariants={k: True for k in SHIPPED_INVARIANTS}),
            IterResult(op_id="Op-1", iter_num=3, run_dir="/r", status="pass",
                       invariants={k: True for k in SHIPPED_INVARIANTS}),
            IterResult(op_id="Op-1", iter_num=1, run_dir="/r", status="pass",
                       invariants={k: True for k in SHIPPED_INVARIANTS}),
        ])
        md = render_scorecard(m, today="2026-06-22")
        # Find the row lines in order; Op-1/1 < Op-1/3 < Op-4/2.
        op1_iter1 = md.index("| Op-1 Rebuild All clean | 1 |")
        op1_iter3 = md.index("| Op-1 Rebuild All clean | 3 |")
        op4_iter2 = md.index("| Op-4 Update during Rebuild | 2 |")
        assert op1_iter1 < op1_iter3 < op4_iter2


# ── SessionManifest round-trip ────────────────────────────────────


class TestSessionManifest:
    def test_to_json_then_from_json_preserves_completed(self):
        m = SessionManifest(
            session_id="sid",
            project_id="pid",
            iterations=3,
            operations=["Op-1", "Op-2"],
            api_url="u",
            dashboard_url="d",
            out_root="o",
            completed=[
                IterResult(op_id="Op-1", iter_num=1, run_dir="/r",
                           status="pass",
                           invariants={"I1": True, "I2": True, "I3": True, "I13": True},
                           failures=[],
                           started_at="2026-06-22T12:00:00+00:00",
                           ended_at="2026-06-22T12:05:00+00:00"),
                IterResult(op_id="Op-2", iter_num=1, run_dir="/r2",
                           status="fail",
                           invariants={"I1": False, "I2": True, "I3": True, "I13": True},
                           failures=[{"invariant_id": "I1", "count": 1,
                                      "first_evidence": {"x": 1}}]),
            ],
        )
        roundtrip = SessionManifest.from_json(json.loads(json.dumps(m.to_json())))
        assert roundtrip.session_id == "sid"
        assert roundtrip.iterations == 3
        assert roundtrip.operations == ["Op-1", "Op-2"]
        assert len(roundtrip.completed) == 2
        assert roundtrip.completed[1].failures[0]["first_evidence"] == {"x": 1}


# ── is_completed ─────────────────────────────────────────────────


class TestIsCompleted:
    def test_returns_true_for_any_terminal_status(self):
        m = _manifest_with([
            IterResult(op_id="Op-1", iter_num=1, run_dir="", status="pass",
                       invariants={k: True for k in SHIPPED_INVARIANTS}),
            IterResult(op_id="Op-1", iter_num=2, run_dir="", status="fail",
                       invariants={k: True for k in SHIPPED_INVARIANTS}),
            IterResult(op_id="Op-1", iter_num=3, run_dir="", status="skipped",
                       invariants={k: True for k in SHIPPED_INVARIANTS}),
            IterResult(op_id="Op-1", iter_num=4, run_dir="", status="error",
                       invariants={k: True for k in SHIPPED_INVARIANTS}),
        ])
        for n in (1, 2, 3, 4):
            assert is_completed(m, "Op-1", n) is True
        assert is_completed(m, "Op-1", 5) is False
        assert is_completed(m, "Op-2", 1) is False


# ── persist_manifest ─────────────────────────────────────────────


class TestPersistManifest:
    def test_writes_via_tmpfile_then_rename(self, tmp_path):
        m = _manifest_with([])
        target = tmp_path / "session.json"
        persist_manifest(m, target)
        assert target.is_file()
        loaded = json.loads(target.read_text())
        assert loaded["session_id"] == "2026-06-22T120000Z"
        # No leftover tmp.
        assert not (tmp_path / "session.json.tmp").exists()

    def test_overwrites_existing_atomically(self, tmp_path):
        m1 = _manifest_with([
            IterResult(op_id="Op-1", iter_num=1, run_dir="/r", status="pass",
                       invariants={k: True for k in SHIPPED_INVARIANTS}),
        ])
        target = tmp_path / "session.json"
        persist_manifest(m1, target)
        m1.completed.append(IterResult(
            op_id="Op-1", iter_num=2, run_dir="/r", status="fail",
            invariants={k: True for k in SHIPPED_INVARIANTS},
        ))
        persist_manifest(m1, target)
        loaded = json.loads(target.read_text())
        assert len(loaded["completed"]) == 2


# ── daemon_healthy failure path ──────────────────────────────────


class TestDaemonHealthyFailure:
    def test_returns_false_for_unreachable_url(self):
        # Port 0 is documented to be reserved; httpx surfaces this as
        # a connection error, which the helper coerces to False.
        assert daemon_healthy("http://127.0.0.1:1", timeout=0.5) is False

    def test_returns_false_on_garbage_url(self):
        assert daemon_healthy("http://not-a-real-host.invalid", timeout=0.5) is False


# ── playwright_smoke CLI smoke (argparse only — no daemon) ───────


class TestPlaywrightSmokeFlagsParse:
    def test_help_lists_new_flags(self):
        r = subprocess.run(
            [sys.executable, "-m", "tools.playwright_smoke", "--help"],
            capture_output=True, text=True, check=True,
        )
        assert "--refresh-at-secs" in r.stdout
        assert "--update-at-secs" in r.stdout

    def test_unknown_mode_returns_2_without_invoking_browser(self):
        # Catches an accidental break of the mode-allowlist when the
        # new T3 flags were threaded through.
        r = subprocess.run(
            [sys.executable, "-m", "tools.playwright_smoke",
             "--project-id", "x", "--modes", "bogus"],
            capture_output=True, text=True,
        )
        assert r.returncode == 2
        assert "unknown modes" in r.stderr

    def test_refresh_flag_with_non_rebuild_mode_is_fatal(self):
        # T3 Lens C #6 (in-drop fix): scheduled-action flags with a mode
        # that doesn't honour them are a hard error, not a silent skip.
        # Use --api-url at a guaranteed-down port so this test is
        # deterministic regardless of whether the user has a daemon
        # running on :8400 (Lens D #2 fix).
        r = subprocess.run(
            [sys.executable, "-m", "tools.playwright_smoke",
             "--project-id", "00000000-0000-0000-0000-000000000000",
             "--api-url", "http://127.0.0.1:1",
             "--modes", "incremental",
             "--refresh-at-secs", "5"],
            capture_output=True, text=True,
            timeout=10,
        )
        assert r.returncode == 2
        assert "only fire during `rebuild`" in r.stderr


# ── _advance_scheduled_actions (playwright_smoke pure helper) ────


class TestAdvanceScheduledActions:
    def test_no_action_when_both_at_secs_none(self):
        new_r, new_u, actions = _advance_scheduled_actions(
            elapsed=100.0,
            refresh_at_secs=None, update_at_secs=None,
            refresh_fired=False, update_fired=False,
        )
        assert (new_r, new_u, actions) == (False, False, [])

    def test_no_action_before_at_secs(self):
        new_r, new_u, actions = _advance_scheduled_actions(
            elapsed=5.0,
            refresh_at_secs=30.0, update_at_secs=10.0,
            refresh_fired=False, update_fired=False,
        )
        assert (new_r, new_u, actions) == (False, False, [])

    def test_fires_at_threshold(self):
        new_r, new_u, actions = _advance_scheduled_actions(
            elapsed=30.0,
            refresh_at_secs=30.0, update_at_secs=None,
            refresh_fired=False, update_fired=False,
        )
        assert (new_r, new_u, actions) == (True, False, ["refresh"])

    def test_does_not_refire_after_emitted(self):
        new_r, new_u, actions = _advance_scheduled_actions(
            elapsed=60.0,
            refresh_at_secs=30.0, update_at_secs=None,
            refresh_fired=True, update_fired=False,
        )
        assert (new_r, new_u, actions) == (True, False, [])

    def test_same_tick_fires_refresh_before_update(self):
        new_r, new_u, actions = _advance_scheduled_actions(
            elapsed=20.0,
            refresh_at_secs=10.0, update_at_secs=15.0,
            refresh_fired=False, update_fired=False,
        )
        # Both eligible on this tick; refresh first so the next page
        # operations land on the reloaded DOM, not the pre-reload one.
        assert actions == ["refresh", "update"]
        assert (new_r, new_u) == (True, True)

    def test_independent_eligibility(self):
        # refresh already done, update due now
        new_r, new_u, actions = _advance_scheduled_actions(
            elapsed=25.0,
            refresh_at_secs=10.0, update_at_secs=20.0,
            refresh_fired=True, update_fired=False,
        )
        assert actions == ["update"]
        assert (new_r, new_u) == (True, True)


# ── _md_cell escape ─────────────────────────────────────────────


class TestMdCellEscape:
    def test_none_returns_empty_string(self):
        assert _md_cell(None) == ""

    def test_non_string_coerced(self):
        assert _md_cell(42) == "42"

    def test_pipe_is_escaped(self):
        assert _md_cell("a | b") == "a \\| b"

    def test_newline_collapses(self):
        # Python tracebacks always include \n; stripping them is the
        # whole point of the helper (Lens B Tier-1).
        cell = _md_cell("Traceback (most recent call last):\n  File ...")
        assert "\n" not in cell
        assert " · " in cell

    def test_carriage_return_stripped(self):
        assert "\r" not in _md_cell("a\r\nb")

    def test_no_change_for_normal_text(self):
        assert _md_cell("clean cell") == "clean cell"


class TestMdCellInScorecard:
    def test_newline_in_notes_does_not_break_table(self):
        # Real-world reproduction: subprocess stderr tail from a Python
        # traceback. Before _md_cell, this would terminate the row and
        # corrupt every subsequent table line.
        m = _manifest_with([
            IterResult(
                op_id="Op-1", iter_num=1, run_dir="", status="error",
                invariants={k: True for k in SHIPPED_INVARIANTS},
                notes="rc=124: TIMEOUT after 900s\nstderr tail: stuck in stage_start",
            ),
            IterResult(
                op_id="Op-1", iter_num=2, run_dir="", status="pass",
                invariants={k: True for k in SHIPPED_INVARIANTS},
            ),
        ])
        md = render_scorecard(m, today="2026-06-22")
        # Every row in the Results section should be on a single line.
        results_section = md.split("## Results")[1].split("## Rolled-up trends")[0]
        row_lines = [line for line in results_section.splitlines() if line.startswith("| Op-")]
        assert len(row_lines) == 2  # iter 1 and iter 2 both present
        assert all("\n" not in line for line in row_lines)
        # The escaped newline shows up as ` · `.
        assert any(" · " in line for line in row_lines)

    def test_pipe_in_notes_does_not_split_cell(self):
        m = _manifest_with([
            IterResult(
                op_id="Op-1", iter_num=1, run_dir="", status="error",
                invariants={k: True for k in SHIPPED_INVARIANTS},
                notes="stderr: cmd|grep failed",
            ),
        ])
        md = render_scorecard(m, today="2026-06-22")
        row = [line for line in md.splitlines() if line.startswith("| Op-1")][0]
        # Eight columns means seven separators after the leading `|`.
        # Escaping the embedded `|` is what keeps the count right.
        # Counts include leading and trailing `|` so 7 separators + 2 = 9 segments.
        assert row.count("|") - row.count("\\|") == 9


# ── Partial-session banner + bare-fail trend (Lens A #4, B #2) ───


class TestPartialSessionRendering:
    def test_partial_banner_appears_when_some_iters_missing(self):
        m = _manifest_with([
            IterResult(op_id="Op-1", iter_num=1, run_dir="/r", status="pass",
                       invariants={k: True for k in SHIPPED_INVARIANTS}),
        ])
        md = render_scorecard(m, today="2026-06-22")
        # 1 of 12 planned (3 iters × 4 ops)
        assert "**Iterations recorded:** 1/12 (partial)" in md
        assert "NOTE: partial session" in md

    def test_complete_session_marker_when_all_iters_recorded(self):
        results = []
        for op in OPERATIONS:
            for n in range(1, 4):  # 3 iters per op = 12 total
                results.append(IterResult(
                    op_id=op.id, iter_num=n, run_dir=f"/r/{op.id}/{n}",
                    status="pass",
                    invariants={k: True for k in SHIPPED_INVARIANTS},
                ))
        m = _manifest_with(results)
        md = render_scorecard(m, today="2026-06-22")
        assert "**Iterations recorded:** 12/12 (complete)" in md
        assert "NOTE: partial session" not in md

    def test_trends_use_planned_denominator_on_partial(self):
        m = _manifest_with([
            # Only 1 of 3 iters for Op-1 recorded; that one failed I3.
            IterResult(op_id="Op-1", iter_num=1, run_dir="/r", status="fail",
                       invariants={"I1": True, "I2": True, "I3": False, "I13": True}),
        ])
        md = render_scorecard(m, today="2026-06-22")
        # Denominator must be 3 (planned), not 1 (observed).
        assert "1/3" in md
        # Suffix names the actual sample size so the reader knows the trend
        # has only one data point.
        assert "observed 1/3" in md


class TestBareFailNoFailuresTrend:
    def test_status_fail_with_empty_failures_surfaces_in_trends(self):
        # An iter where smoke returned pass=False but no invariant_failure
        # event was logged (e.g. settle-timeout). Without Lens B #2 fix,
        # the trends section would say "All recorded iterations passed
        # every invariant" while the Results table shows FAIL.
        m = _manifest_with([
            IterResult(op_id="Op-2", iter_num=1, run_dir="/r", status="fail",
                       invariants={k: True for k in SHIPPED_INVARIANTS},
                       failures=[],  # critically: no per-invariant evidence
                       notes="watch_until_idle timeout"),
        ])
        md = render_scorecard(m, today="2026-06-22")
        assert "1/3 iter(s) failed without invariant evidence" in md
        assert "All recorded iterations passed every invariant" not in md


# ── Evidence path resolution (Lens B #4) ─────────────────────────


class TestResolveEvidencePaths:
    def test_returns_concrete_files_when_present(self, tmp_path):
        mode_dir = tmp_path / "rebuild"
        mode_dir.mkdir()
        (mode_dir / "003_invariant_I13_FAIL.png").write_bytes(b"\x89PNG")
        (mode_dir / "008_invariant_I13_FAIL.png").write_bytes(b"\x89PNG")
        (mode_dir / "005_invariant_I1_FAIL.png").write_bytes(b"\x89PNG")
        paths = _resolve_evidence_paths(str(tmp_path), "rebuild", "I13")
        assert len(paths) == 2
        # Sorted means deterministic doc output.
        assert paths[0].name == "003_invariant_I13_FAIL.png"

    def test_returns_empty_when_run_dir_missing(self, tmp_path):
        # run_dir from an iter that errored before snap fired.
        assert _resolve_evidence_paths(str(tmp_path / "ghost"), "rebuild", "I1") == []

    def test_returns_empty_when_no_matching_screenshots(self, tmp_path):
        (tmp_path / "rebuild").mkdir()
        assert _resolve_evidence_paths(str(tmp_path), "rebuild", "I3") == []

    def test_render_falls_back_to_pattern_when_no_files(self, tmp_path):
        m = _manifest_with([
            IterResult(
                op_id="Op-3", iter_num=1, run_dir=str(tmp_path / "ghost"),
                status="fail",
                invariants={"I1": True, "I2": True, "I3": True, "I13": False},
                failures=[{"invariant_id": "I13", "count": 1,
                           "first_evidence": {}}],
            ),
        ])
        md = render_scorecard(m, today="2026-06-22")
        assert "_(pattern; no files on disk)_" in md


# ── Health probe failure paths ──────────────────────────────────


class TestProjectPipelineReadyFailure:
    def test_returns_false_for_unreachable_url(self):
        assert project_pipeline_ready("http://127.0.0.1:1", "any-pid", timeout=0.5) is False


# ── cancel + quiesce (Lens A #1 Tier-1) ─────────────────────────


class TestCancelAndQuiesce:
    def test_returns_false_and_detail_when_daemon_down(self):
        # Daemon unreachable → _pipeline_snapshot returns all-empty →
        # targets is [] → wait_for_pipeline_idle times out → False
        # with "no active groups visible; still not idle" detail.
        # (Pre-fix: detail said "cancel post failed" because the helper
        # tried to post regardless of state; now it short-circuits when
        # snapshot has no active phases.)
        quiesced, detail = cancel_and_quiesce(
            "http://127.0.0.1:1", "any-pid", max_seconds=0.2,
        )
        assert quiesced is False
        assert "no active groups visible" in detail
        assert "still not idle" in detail

    def test_posts_correct_body_for_each_running_group(self, monkeypatch):
        """Body-shape regression test for PROPOSAL §9.1 cancel-quiesce
        empty-body false-negative.

        The bug: original cancel_and_quiesce posted with no body, hitting
        `/pipeline/cancel`'s `CancelRequest` validator and returning a
        silent 400. Pipeline kept running; harness moved on; next iter
        409'd on /rebuild and read ERR. This test verifies the post body
        is now `{group, reason}` for every group identified as running.
        """
        import tools.phase145_uat.run_session as rs

        captured: list[dict] = []
        snapshot_calls: list[int] = [0]

        class FakeResp:
            def __init__(self, code: int = 200, body: dict | None = None):
                self.status_code = code
                self._body = body if body is not None else {"data": {}}
            def json(self):
                return self._body

        def fake_get(url, *, timeout=None, **kw):  # noqa: ARG001
            assert "/pipeline/status" in url
            snapshot_calls[0] += 1
            if snapshot_calls[0] == 1:
                # Initial snapshot: deep_enrichment running, fast_sync
                # completed, finalize null. Cancel target list = [
                # "deep_enrichment"].
                return FakeResp(200, {"data": {
                    "fast_sync": {"phase": "completed"},
                    "deep_enrichment": {"phase": "running"},
                    "finalize": None,
                }})
            # Subsequent polls (from wait_for_pipeline_idle): idle.
            return FakeResp(200, {"data": {
                "fast_sync": {"phase": "completed"},
                "deep_enrichment": {"phase": "cancelled"},
                "finalize": None,
            }})

        def fake_post(url, *, json=None, timeout=None, **kw):  # noqa: ARG001
            captured.append({"url": url, "json": json})
            return FakeResp(200)

        monkeypatch.setattr(rs.httpx, "get", fake_get)
        monkeypatch.setattr(rs.httpx, "post", fake_post)

        quiesced, detail = rs.cancel_and_quiesce("http://x", "pid", max_seconds=1.0)

        assert quiesced is True
        assert len(captured) == 1
        assert captured[0]["url"].endswith("/projects/pid/pipeline/cancel")
        assert captured[0]["json"] == {
            "group": "deep_enrichment",
            "reason": "uat_session_cleanup",
        }
        assert "deep_enrichment:cancelled" in detail

    def test_treats_409_not_running_as_already_stopped(self, monkeypatch):
        """409 NOT_RUNNING is a fine outcome (group quiesced between our
        snapshot read and our cancel post). It must NOT be classified as
        a cancel error — the runner needs to know "already-stopped" so it
        can continue without flagging the iter as failed-cleanup.
        """
        import tools.phase145_uat.run_session as rs

        class FakeResp:
            def __init__(self, code: int = 200, body: dict | None = None):
                self.status_code = code
                self._body = body if body is not None else {"data": {}}
            def json(self):
                return self._body

        def fake_get(url, *, timeout=None, **kw):  # noqa: ARG001
            return FakeResp(200, {"data": {
                "fast_sync": {"phase": "running"},
                "deep_enrichment": None,
                "finalize": None,
            }})

        def fake_post(url, *, json=None, timeout=None, **kw):  # noqa: ARG001
            return FakeResp(409, {"error": {"code": "NOT_RUNNING"}})

        monkeypatch.setattr(rs.httpx, "get", fake_get)
        monkeypatch.setattr(rs.httpx, "post", fake_post)

        # Patch wait_for_pipeline_idle to return True instantly so we
        # don't burn budget on a fake-still-running snapshot.
        monkeypatch.setattr(rs, "wait_for_pipeline_idle", lambda *a, **k: True)

        quiesced, detail = rs.cancel_and_quiesce("http://x", "pid", max_seconds=0.5)
        assert quiesced is True
        assert "fast_sync:already-stopped" in detail
        assert "cancel-err" not in detail

    def test_cancels_every_active_group_in_snapshot(self, monkeypatch):
        """If multiple groups are simultaneously active (e.g. fast_sync
        running + deep_enrichment queued), every one of them needs a
        cancel post. Verifies the loop visits all targets rather than
        bailing after the first.
        """
        import tools.phase145_uat.run_session as rs

        class FakeResp:
            def __init__(self, code: int = 200, body: dict | None = None):
                self.status_code = code
                self._body = body if body is not None else {"data": {}}
            def json(self):
                return self._body

        def fake_get(url, *, timeout=None, **kw):  # noqa: ARG001
            return FakeResp(200, {"data": {
                "fast_sync": {"phase": "running"},
                "deep_enrichment": {"phase": "queued"},
                "finalize": {"phase": "queued"},
            }})

        captured_groups: list[str] = []
        def fake_post(url, *, json=None, timeout=None, **kw):  # noqa: ARG001
            captured_groups.append(json["group"])
            return FakeResp(200)

        monkeypatch.setattr(rs.httpx, "get", fake_get)
        monkeypatch.setattr(rs.httpx, "post", fake_post)
        monkeypatch.setattr(rs, "wait_for_pipeline_idle", lambda *a, **k: True)

        rs.cancel_and_quiesce("http://x", "pid", max_seconds=0.5)
        assert sorted(captured_groups) == ["deep_enrichment", "fast_sync", "finalize"]


class TestWaitForPipelineIdleFailure:
    def test_returns_false_when_daemon_unreachable(self):
        assert wait_for_pipeline_idle(
            "http://127.0.0.1:1", "any-pid", max_seconds=0.2,
        ) is False


class TestWaitForPipelineIdleStrictness:
    """§9.3 #17 root cause — wait_for_pipeline_idle previously only checked
    `phase == "running"`, so a daemon mid-transition reported as idle. The
    next iter fired POST /pipeline/rebuild or /pipeline/all while the daemon
    was still in `queued`, `pausing`, `recovering`, or `cancelling`, which
    either 409'd (still-running) or http-timed-out (>30s daemon hold).

    Per state_machine.py:94-200, terminal phases are `idle`, `completed`,
    `cancelled`, `failed`. Anything else is "still busy" and the poll must
    continue until terminal or the budget runs out.

    These tests are direct: mock /pipeline/status with each non-terminal
    phase in turn and assert the helper does NOT short-circuit to True.
    Each test uses a 0.3s budget so a buggy implementation that returns
    True instantly is visibly wrong (passes too fast), and a buggy
    implementation that loops forever is bounded by pytest's per-test
    budget.
    """

    @staticmethod
    def _mk_fake_get(phase_map):
        """Return a fake httpx.get that always responds with the given
        per-group phase dict wrapped in the canonical envelope."""
        class FakeResp:
            def __init__(self, body):
                self.status_code = 200
                self._body = body
            def json(self):
                return self._body

        def fake_get(url, *, timeout=None, **kw):  # noqa: ARG001
            return FakeResp({"data": {g: {"phase": p} for g, p in phase_map.items()}})

        return fake_get

    def test_terminal_idle_returns_true(self, monkeypatch):
        import tools.phase145_uat.run_session as rs
        monkeypatch.setattr(rs.httpx, "get", self._mk_fake_get({
            "fast_sync": "idle", "deep_enrichment": "idle", "finalize": "idle",
        }))
        assert wait_for_pipeline_idle("http://x", "pid", max_seconds=0.3) is True

    def test_terminal_completed_returns_true(self, monkeypatch):
        import tools.phase145_uat.run_session as rs
        monkeypatch.setattr(rs.httpx, "get", self._mk_fake_get({
            "fast_sync": "completed", "deep_enrichment": "completed",
            "finalize": "completed",
        }))
        assert wait_for_pipeline_idle("http://x", "pid", max_seconds=0.3) is True

    def test_terminal_cancelled_returns_true(self, monkeypatch):
        import tools.phase145_uat.run_session as rs
        monkeypatch.setattr(rs.httpx, "get", self._mk_fake_get({
            "fast_sync": "cancelled", "deep_enrichment": "cancelled",
            "finalize": "cancelled",
        }))
        assert wait_for_pipeline_idle("http://x", "pid", max_seconds=0.3) is True

    def test_terminal_failed_returns_true(self, monkeypatch):
        import tools.phase145_uat.run_session as rs
        monkeypatch.setattr(rs.httpx, "get", self._mk_fake_get({
            "fast_sync": "failed", "deep_enrichment": "failed",
            "finalize": "failed",
        }))
        assert wait_for_pipeline_idle("http://x", "pid", max_seconds=0.3) is True

    def test_queued_treated_as_busy(self, monkeypatch):
        """Pre-fix bug: queued reported as idle. This is the cascade root
        for Op-2 iter 3 in the 2026-06-22 SCORECARD."""
        import tools.phase145_uat.run_session as rs
        monkeypatch.setattr(rs.httpx, "get", self._mk_fake_get({
            "fast_sync": "completed", "deep_enrichment": "queued",
            "finalize": "idle",
        }))
        assert wait_for_pipeline_idle("http://x", "pid", max_seconds=0.3) is False

    def test_pausing_treated_as_busy(self, monkeypatch):
        import tools.phase145_uat.run_session as rs
        monkeypatch.setattr(rs.httpx, "get", self._mk_fake_get({
            "fast_sync": "pausing", "deep_enrichment": "completed",
            "finalize": "idle",
        }))
        assert wait_for_pipeline_idle("http://x", "pid", max_seconds=0.3) is False

    def test_recovering_treated_as_busy(self, monkeypatch):
        """recovering means daemon-restart mid-stage; the run is still in
        flight and the next /pipeline/rebuild WILL conflict if we proceed.
        """
        import tools.phase145_uat.run_session as rs
        monkeypatch.setattr(rs.httpx, "get", self._mk_fake_get({
            "fast_sync": "completed", "deep_enrichment": "recovering",
            "finalize": "idle",
        }))
        assert wait_for_pipeline_idle("http://x", "pid", max_seconds=0.3) is False

    def test_cancelling_treated_as_busy(self, monkeypatch):
        """We just posted cancel; daemon is acknowledging. Waiting through
        cancelling → cancelled is the WHOLE POINT of the helper.
        """
        import tools.phase145_uat.run_session as rs
        monkeypatch.setattr(rs.httpx, "get", self._mk_fake_get({
            "fast_sync": "cancelling", "deep_enrichment": "completed",
            "finalize": "idle",
        }))
        assert wait_for_pipeline_idle("http://x", "pid", max_seconds=0.3) is False

    def test_running_still_treated_as_busy(self, monkeypatch):
        """Regression: don't break the original primary case while
        tightening the others."""
        import tools.phase145_uat.run_session as rs
        monkeypatch.setattr(rs.httpx, "get", self._mk_fake_get({
            "fast_sync": "running", "deep_enrichment": "idle",
            "finalize": "idle",
        }))
        assert wait_for_pipeline_idle("http://x", "pid", max_seconds=0.3) is False

    def test_mixed_terminal_and_busy_returns_false(self, monkeypatch):
        """Three groups, only one busy — still must wait."""
        import tools.phase145_uat.run_session as rs
        monkeypatch.setattr(rs.httpx, "get", self._mk_fake_get({
            "fast_sync": "completed", "deep_enrichment": "completed",
            "finalize": "queued",
        }))
        assert wait_for_pipeline_idle("http://x", "pid", max_seconds=0.3) is False


# ── playwright_smoke.Api — extended timeout for rebuild (§9.3 #17) ─


class TestApiRebuildTimeout:
    """§9.3 #17 fix C — api.rebuild() / api.run_all() can take >30s to
    respond when the daemon is doing post-iter cleanup work
    (manifest writes, indexing, audit). The default Api httpx timeout was
    30s; we override per-call to give these heavy endpoints headroom while
    keeping the default short for fast endpoints (status, cancel).
    """

    def test_rebuild_uses_extended_timeout(self):
        import tools.playwright_smoke as ps

        captured = {}

        class FakeResp:
            status_code = 200
            def json(self):
                return {"success": True, "data": {}}
            def raise_for_status(self):
                pass

        class FakeHttp:
            def post(self, url, *, timeout=None, **kw):
                captured["url"] = url
                captured["timeout"] = timeout
                return FakeResp()

        api = ps.Api("http://x")
        api.http = FakeHttp()
        api.rebuild("pid")
        assert captured["url"].endswith("/projects/pid/pipeline/rebuild")
        # 30s is too tight; expect at least 90s to absorb daemon cleanup.
        assert captured["timeout"] is not None
        assert captured["timeout"] >= 90

    def test_run_all_uses_extended_timeout(self):
        """/pipeline/all is the incremental-rebuild trigger; same daemon
        cleanup characteristics as /pipeline/rebuild."""
        import tools.playwright_smoke as ps

        captured = {}

        class FakeResp:
            status_code = 200
            def json(self):
                return {"success": True, "data": {}}
            def raise_for_status(self):
                pass

        class FakeHttp:
            def post(self, url, *, timeout=None, **kw):
                captured["url"] = url
                captured["timeout"] = timeout
                return FakeResp()

        api = ps.Api("http://x")
        api.http = FakeHttp()
        api.run_all("pid")
        assert captured["url"].endswith("/projects/pid/pipeline/all")
        assert captured["timeout"] is not None
        assert captured["timeout"] >= 90


# ── §9.3 #17 scrutiny fixes — pin the post-merge gaps ──────────────


class TestHarnessPhaseSetsMatchCanonical:
    """SOT enforcement: the harness's `_TERMINAL_PHASES` and
    `_CANCELLABLE_PHASES` together must be a true partition of the
    canonical `PipelineState` enum at src/prep/services/pipeline/
    state_machine.py (Phase 25B). If the state machine adds, renames, or
    removes a phase, these tests fail loudly — preventing the silent
    drift that motivated PROPOSAL_state-machine-re-centering-v1.md.

    The harness's `_TERMINAL_PHASES` is an INTENTIONAL superset of
    canonical `TERMINAL_STATES` (it adds `idle`, which is canonically a
    starting/reset state but is "ready for next run" from the harness's
    perspective). See run_session.py docstring for the rationale.
    """

    def test_union_is_a_true_partition_of_canonical_pipeline_state(self):
        from src.prep.services.pipeline.state_machine import PipelineState

        canonical = {p.value for p in PipelineState}
        harness = _TERMINAL_PHASES | _CANCELLABLE_PHASES
        missing_from_harness = canonical - harness
        extra_in_harness = harness - canonical
        assert not missing_from_harness, (
            f"Canonical PipelineState has values the harness does not cover: "
            f"{missing_from_harness}. Add them to _TERMINAL_PHASES or "
            f"_CANCELLABLE_PHASES in tools/phase145_uat/run_session.py."
        )
        assert not extra_in_harness, (
            f"Harness has phase strings the canonical PipelineState no longer "
            f"defines: {extra_in_harness}. Remove from run_session.py."
        )

    def test_terminal_and_cancellable_are_disjoint(self):
        """The two sets must NOT overlap; if they did, the cancel-quiesce
        helper would treat a phase as both 'still active' and 'ready for
        next run', breaking the wait/cancel decision."""
        overlap = _TERMINAL_PHASES & _CANCELLABLE_PHASES
        assert not overlap, (
            f"_TERMINAL_PHASES and _CANCELLABLE_PHASES overlap on: {overlap}. "
            f"Each canonical phase must classify as exactly one of the two."
        )

    def test_canonical_terminal_states_are_subset_of_harness_terminal(self):
        """Pre-fix the comment claimed `_TERMINAL_PHASES` mirrored canonical
        TERMINAL_STATES; in fact the harness intentionally adds `idle`. Pin
        the relationship explicitly so a future "cleanup" doesn't drop the
        harness-only members back to the canonical 3.
        """
        from src.prep.services.pipeline.state_machine import TERMINAL_STATES

        canonical_terminal = {s.value for s in TERMINAL_STATES}
        assert canonical_terminal <= _TERMINAL_PHASES, (
            f"Canonical TERMINAL_STATES {canonical_terminal} must all be in "
            f"harness _TERMINAL_PHASES {_TERMINAL_PHASES}."
        )
        # Harness-only addition is `idle`, by current design. If this changes,
        # update the rationale comment in run_session.py and adjust this
        # test to match.
        harness_only = _TERMINAL_PHASES - canonical_terminal
        assert harness_only == {"idle"}, (
            f"Harness adds {harness_only} on top of canonical TERMINAL_STATES; "
            f"expected just {{'idle'}}. Update the comment or this test."
        )


class TestClipNotes:
    """Scrutiny fix #1 — pre-fix cap was inside parse_iter_result only, so
    the cancel-quiesce annotation appended in main() could push notes past
    the SCORECARD cell width budget. `_clip_notes` is the helper that
    closes the gap; main() now wraps the append.
    """

    def test_short_string_passes_through_unchanged(self):
        s = "error×1 'timed out'"
        assert _clip_notes(s) is s or _clip_notes(s) == s

    def test_empty_string_passes_through(self):
        assert _clip_notes("") == ""

    def test_truncates_to_max_len_with_ellipsis(self):
        s = "x" * (_NOTES_MAX_LEN + 50)
        clipped = _clip_notes(s)
        assert len(clipped) == _NOTES_MAX_LEN
        assert clipped.endswith("...")

    def test_idempotent_on_already_clipped(self):
        s = "x" * (_NOTES_MAX_LEN + 50)
        once = _clip_notes(s)
        twice = _clip_notes(once)
        assert once == twice


class TestSummariseEventKind:
    """Scrutiny fix #3 — pre-fix kept only events[0] detail, collapsing
    mixed-cause clusters. Now renders up to 3 distinct values with a
    `(+N more)` suffix when truncated.
    """

    def test_single_event_renders_count_and_detail(self):
        events = [{"detail": "timed out"}]
        out = _summarise_event_kind(events, "error", "detail")
        assert "error×1" in out
        assert "'timed out'" in out

    def test_multiple_events_same_detail_dedupes(self):
        events = [{"detail": "timed out"} for _ in range(4)]
        out = _summarise_event_kind(events, "error", "detail")
        assert "error×4" in out
        # 4 identical → 1 distinct → no "(+N more)" tail
        assert "more" not in out

    def test_multiple_distinct_details_rendered_with_separator(self):
        events = [
            {"detail": "timed out"},
            {"detail": "409 Conflict"},
            {"detail": "ConnectionRefused"},
        ]
        out = _summarise_event_kind(events, "error", "detail")
        assert "error×3" in out
        assert "'timed out'" in out
        assert "'409 Conflict'" in out
        assert "'ConnectionRefused'" in out

    def test_more_than_max_distinct_shows_plus_n_more(self):
        events = [
            {"detail": f"err-{i}"} for i in range(5)
        ]
        out = _summarise_event_kind(events, "error", "detail", max_distinct=3)
        assert "error×5" in out
        assert "'err-0'" in out
        assert "'err-1'" in out
        assert "'err-2'" in out
        # err-3 and err-4 not rendered but counted
        assert "(+2 more)" in out

    def test_per_detail_truncation(self):
        events = [{"detail": "X" * 200}]
        out = _summarise_event_kind(events, "error", "detail", per_detail_max_chars=20)
        # Detail should be truncated; full 200-char string shouldn't appear.
        assert "X" * 200 not in out

    def test_works_with_desync_subtype(self):
        events = [
            {"subtype": "progress_gap"},
            {"subtype": "progress_gap"},
            {"subtype": "api_running_dom_not_running"},
        ]
        out = _summarise_event_kind(events, "desync", "subtype")
        assert "desync×3" in out
        assert "'progress_gap'" in out
        assert "'api_running_dom_not_running'" in out


class TestCancelQuiesceBudget:
    """Scrutiny fix #2 — pre-fix default was 30s, too short for daemons
    in `recovering` (60-90s normal post-crash hydrate). Main loop now
    passes max_seconds=90 explicitly.
    """

    def test_main_loop_cancel_call_uses_extended_budget(self):
        """Scan run_session.py main() source for the cancel_and_quiesce
        call to verify it doesn't fall back to the 30s default. This is
        a contract test, not a runtime test, because the alternative
        (mocking the whole main loop) would be more brittle than a
        source-level pin.
        """
        import re
        from pathlib import Path
        src = Path(__file__).resolve().parent.parent / "tools/phase145_uat/run_session.py"
        text = src.read_text()
        # Match cancel_and_quiesce(...args.api_url...max_seconds=NN...)
        # across line breaks. DOTALL so `.` spans newlines; non-greedy so
        # we stop at the first matching close-paren chain.
        pattern = re.compile(
            r"cancel_and_quiesce\s*\(\s*args\.api_url\b[^()]*?max_seconds\s*=\s*([\d.]+)",
            re.DOTALL,
        )
        m = pattern.search(text)
        assert m, (
            "main() does not call cancel_and_quiesce(args.api_url, ...) with "
            "an explicit max_seconds keyword. Pre-fix it inherited the 30s "
            "default which is too tight for daemons in `recovering`."
        )
        budget = float(m.group(1))
        assert budget >= 60.0, (
            f"main()'s cancel_and_quiesce budget is {budget}s; recovering "
            f"daemons need ≥60s. Bump it in tools/phase145_uat/run_session.py."
        )


class TestIsAnyRunningStrictness:
    """Scrutiny fix #5 — playwright_smoke.is_any_running pre-fix checked
    only `phase == 'running'`, missing pausing/recovering/cancelling/
    queued/paused. The watch loop would declare 'settled' mid-transition
    and the next iter would race the unfinished work. Now matches the
    same predicate as run_session.wait_for_pipeline_idle.
    """

    def _wrap(self, phase: str) -> dict:
        return {"fast_sync": {"phase": phase}, "deep_enrichment": {}, "finalize": {}}

    def test_running_is_running(self):
        assert is_any_running(self._wrap("running")) is True

    def test_queued_is_running(self):
        """Pre-fix bug: queued passed as not-running."""
        assert is_any_running(self._wrap("queued")) is True

    def test_pausing_is_running(self):
        assert is_any_running(self._wrap("pausing")) is True

    def test_paused_is_running(self):
        """Harness POV: a paused run still holds a stage row; treat as
        in-flight so watch_until_idle keeps polling."""
        assert is_any_running(self._wrap("paused")) is True

    def test_recovering_is_running(self):
        assert is_any_running(self._wrap("recovering")) is True

    def test_cancelling_is_running(self):
        assert is_any_running(self._wrap("cancelling")) is True

    def test_idle_is_not_running(self):
        assert is_any_running(self._wrap("idle")) is False

    def test_completed_is_not_running(self):
        assert is_any_running(self._wrap("completed")) is False

    def test_cancelled_is_not_running(self):
        assert is_any_running(self._wrap("cancelled")) is False

    def test_failed_is_not_running(self):
        assert is_any_running(self._wrap("failed")) is False

    def test_empty_status_is_not_running(self):
        assert is_any_running({}) is False


class TestApiHeavyTimeoutAcrossEndpoints:
    """Scrutiny fix #4 — pre-fix only run_all + rebuild used the 120s
    per-call timeout. The other 5 daemon-side heavy endpoints
    (destroy + run_fast + run_deep + enrichment_full_reset +
    finalize_full_reset) still used the 30s class default and would
    reproduce the Op-3/Op-4 timeout cascade for --modes initial /
    rebuild-sync / rebuild-enrichment / reset-* paths.
    """

    def _mk_api(self, captured):
        import tools.playwright_smoke as ps

        class FakeResp:
            status_code = 200
            def json(self):
                return {"success": True, "data": {}}
            def raise_for_status(self):
                pass

        class FakeHttp:
            def post(self, url, *, timeout=None, **kw):
                captured.append(("post", url, timeout))
                return FakeResp()
            def delete(self, url, *, timeout=None, **kw):
                captured.append(("delete", url, timeout))
                return FakeResp()

        api = ps.Api("http://x")
        api.http = FakeHttp()
        return api

    def test_destroy_uses_heavy_timeout(self):
        captured = []
        api = self._mk_api(captured)
        api.destroy("pid")
        assert captured[-1][2] is not None and captured[-1][2] >= 90

    def test_run_fast_uses_heavy_timeout(self):
        captured = []
        api = self._mk_api(captured)
        api.run_fast("pid")
        assert captured[-1][2] is not None and captured[-1][2] >= 90

    def test_run_deep_uses_heavy_timeout(self):
        captured = []
        api = self._mk_api(captured)
        api.run_deep("pid")
        assert captured[-1][2] is not None and captured[-1][2] >= 90

    def test_enrichment_full_reset_uses_heavy_timeout(self):
        captured = []
        api = self._mk_api(captured)
        api.enrichment_full_reset("pid")
        assert captured[-1][2] is not None and captured[-1][2] >= 90

    def test_finalize_full_reset_uses_heavy_timeout(self):
        captured = []
        api = self._mk_api(captured)
        api.finalize_full_reset("pid")
        assert captured[-1][2] is not None and captured[-1][2] >= 90


# ── §9.3 second-pass audit — phase-vocabulary SOT pins ──────────────


class TestActivePipelinePhasesPinnedToCanonical:
    """Second-pass scrutiny caught that ACTIVE_PIPELINE_PHASES in
    invariants.py was UNPINNED — the first scrutiny's SOT scorecard
    claimed it was, but no test existed. Pin it now.

    Per state_machine.py:202-208, canonical `ACTIVE_STATES` is
    {QUEUED, RUNNING, PAUSING, CANCELLING, RECOVERING}. The harness's
    `ACTIVE_PIPELINE_PHASES` INTENTIONALLY diverges by:
      - EXCLUDING `queued` (no current_stage to anchor against)
      - INCLUDING `paused` (still holds a stage row, observable)
    See invariants.py docstring lines 82-103 for the full rationale.
    """

    def test_active_pipeline_phases_matches_documented_set(self):
        # Pin the exact 5-phase set. If invariants.py is edited, this
        # forces the editor to also update the rationale comment.
        assert ACTIVE_PIPELINE_PHASES == frozenset({
            "running", "pausing", "paused", "recovering", "cancelling",
        }), (
            f"ACTIVE_PIPELINE_PHASES drifted from documented set. "
            f"Current: {ACTIVE_PIPELINE_PHASES}. If this is intentional, "
            f"update invariants.py docstring AND this test together."
        )

    def test_active_diverges_from_canonical_active_states_by_swap(self):
        """The divergence vs canonical ACTIVE_STATES is deliberate:
        drop `queued` (no current_stage), add `paused` (stable snapshot).
        If a future state machine change makes one of these wrong, this
        test fires.
        """
        from src.prep.services.pipeline.state_machine import ACTIVE_STATES

        canonical_active = {s.value for s in ACTIVE_STATES}
        # In canonical but excluded from harness:
        harness_excludes_from_canonical = canonical_active - ACTIVE_PIPELINE_PHASES
        # In harness but not in canonical active:
        harness_adds_beyond_canonical = ACTIVE_PIPELINE_PHASES - canonical_active

        assert harness_excludes_from_canonical == {"queued"}, (
            f"Expected harness to exclude exactly {{'queued'}} from "
            f"canonical ACTIVE_STATES; actually excludes "
            f"{harness_excludes_from_canonical}."
        )
        assert harness_adds_beyond_canonical == {"paused"}, (
            f"Expected harness to add exactly {{'paused'}} on top of "
            f"canonical ACTIVE_STATES; actually adds "
            f"{harness_adds_beyond_canonical}."
        )


class TestNonRunningPhasesPinnedToCanonical:
    """Second-pass scrutiny caught that playwright_smoke._NON_RUNNING_PHASES
    was UNPINNED. Pin it now — must equal canonical TERMINAL_STATES plus
    `idle` (same divergence rationale as run_session._TERMINAL_PHASES).
    """

    def test_non_running_phases_match_canonical_plus_idle(self):
        from src.prep.services.pipeline.state_machine import TERMINAL_STATES

        canonical_terminal = {s.value for s in TERMINAL_STATES}
        expected = canonical_terminal | {"idle"}
        assert _NON_RUNNING_PHASES == expected, (
            f"_NON_RUNNING_PHASES drifted. Expected canonical "
            f"TERMINAL_STATES + {{'idle'}} = {expected}; got "
            f"{_NON_RUNNING_PHASES}."
        )


class TestVerdictEligiblePhases:
    """Second-pass scrutiny added _VERDICT_ELIGIBLE_PHASES so per-stage
    desync detection works during `paused` (was silently blind pre-fix).

    The set is INTENTIONALLY narrow — only `running` and `paused` have a
    stable `current_stage`. `pausing`/`cancelling`/`recovering` are
    EXCLUDED because their `current_stage` is mid-transition and emitting
    verdicts against it would produce false positives.
    """

    def test_verdict_eligible_is_exactly_running_and_paused(self):
        assert _VERDICT_ELIGIBLE_PHASES == frozenset({"running", "paused"})

    def test_verdict_eligible_is_subset_of_active(self):
        """A phase that's verdict-eligible must also be in
        ACTIVE_PIPELINE_PHASES (you can only have a verdict when there's
        an active stage). If a future change adds a verdict-eligible
        phase that's NOT active, this test catches the inconsistency.
        """
        assert _VERDICT_ELIGIBLE_PHASES <= ACTIVE_PIPELINE_PHASES, (
            f"_VERDICT_ELIGIBLE_PHASES must be a subset of "
            f"ACTIVE_PIPELINE_PHASES. Diff: "
            f"{_VERDICT_ELIGIBLE_PHASES - ACTIVE_PIPELINE_PHASES}"
        )

    def test_pausing_cancelling_recovering_intentionally_excluded(self):
        """Document the exclusion rationale via a test. If a future
        refactor adds these phases, this test fails — forcing the
        author to revisit the false-positive concern.
        """
        for transitional in ("pausing", "cancelling", "recovering"):
            assert transitional not in _VERDICT_ELIGIBLE_PHASES, (
                f"{transitional!r} has a TRANSITIONAL current_stage; "
                f"emitting verdicts would produce false positives. "
                f"See api_stage_verdict docstring."
            )


class TestGroupsConstantSingleSource:
    """Second-pass scrutiny found 4 hard-coded copies of the 3-group tuple
    across playwright_smoke.py + run_session.py. All now import from
    invariants.GROUPS. Pin the canonical set so a rename hits one place.
    """

    def test_groups_is_the_three_pipeline_top_level_groups(self):
        assert GROUPS == ("fast_sync", "deep_enrichment", "finalize")

    def test_groups_has_three_entries(self):
        # State machine has one PipelineGroupStateMachine per group;
        # changing this count requires a state-machine-side change too.
        assert len(GROUPS) == 3


class TestStageOrderPinnedToCanonical:
    """Second-pass scrutiny: the 15 pipeline stages are hand-mirrored at
    least 3 times — `src/prep/services/pipeline/stages.py` (canonical,
    Phase 25B `StageId` enum), `tools/phase145_uat/constants.py
    STAGE_ORDER`, and `packages/ui/src/components/trace/freezeGreen.ts`
    FAST_STAGE_ORDER + DEEP_STAGE_ORDER + FINALIZE_STAGE_ORDER. The TS
    side cannot import from Python; a single Python-side pin test
    catches drift in all three at once.

    Pinning the active vocabulary leaves the `augment → catalogue` alias
    (`freezeGreen.normalizeFastStage`) in place — that alias defends
    against backends that pre-date the StageId enum; documented as cruft
    in PROPOSAL §9.3 follow-up.
    """

    def test_constants_stage_order_matches_canonical_stages_py(self):
        from src.prep.services.pipeline.stages import (
            DEEP_ENRICHMENT_STAGES,
            FAST_SYNC_STAGES,
            FINALIZE_STAGES,
        )
        from tools.phase145_uat.constants import STAGE_ORDER

        canonical_ids = [
            s.value for s in (FAST_SYNC_STAGES + DEEP_ENRICHMENT_STAGES + FINALIZE_STAGES)
        ]
        harness_ids = [stage_id for stage_id, _group in STAGE_ORDER]
        assert harness_ids == canonical_ids, (
            f"tools/phase145_uat/constants.py STAGE_ORDER drifted from "
            f"canonical src/prep/services/pipeline/stages.py. "
            f"In canonical but not harness: "
            f"{set(canonical_ids) - set(harness_ids)}. "
            f"In harness but not canonical: "
            f"{set(harness_ids) - set(canonical_ids)}."
        )

    def test_freezegreen_ts_arrays_match_canonical_stages_py(self):
        """Parse the TypeScript arrays from freezeGreen.ts and assert
        they equal the canonical Python lists. Catches drift in the
        TS mirror without requiring vitest invocation from pytest.
        """
        import re
        from pathlib import Path

        from src.prep.services.pipeline.stages import (
            DEEP_ENRICHMENT_STAGES,
            FAST_SYNC_STAGES,
            FINALIZE_STAGES,
        )

        ts_path = (
            Path(__file__).resolve().parent.parent
            / "packages/ui/src/components/trace/freezeGreen.ts"
        )
        text = ts_path.read_text()

        def _parse_array(name: str) -> list[str]:
            # Match `export const NAME: ReadonlyArray<string> = [ 'a', 'b', ... ];`
            # across multiple lines. Captures the single-quoted string contents.
            pattern = re.compile(
                rf"export\s+const\s+{name}\s*:\s*ReadonlyArray<string>\s*=\s*\[(.*?)\];",
                re.DOTALL,
            )
            m = pattern.search(text)
            assert m, f"Could not find {name} export in {ts_path}"
            body = m.group(1)
            return re.findall(r"'([^']+)'", body)

        ts_fast = _parse_array("FAST_STAGE_ORDER")
        ts_deep = _parse_array("DEEP_STAGE_ORDER")
        ts_finalize = _parse_array("FINALIZE_STAGE_ORDER")

        canonical_fast = [s.value for s in FAST_SYNC_STAGES]
        canonical_deep = [s.value for s in DEEP_ENRICHMENT_STAGES]
        canonical_finalize = [s.value for s in FINALIZE_STAGES]

        assert ts_fast == canonical_fast, (
            f"freezeGreen.FAST_STAGE_ORDER drifted from canonical "
            f"FAST_SYNC_STAGES. TS: {ts_fast}. Canonical: {canonical_fast}."
        )
        assert ts_deep == canonical_deep, (
            f"freezeGreen.DEEP_STAGE_ORDER drifted from canonical "
            f"DEEP_ENRICHMENT_STAGES. TS: {ts_deep}. Canonical: {canonical_deep}."
        )
        assert ts_finalize == canonical_finalize, (
            f"freezeGreen.FINALIZE_STAGE_ORDER drifted from canonical "
            f"FINALIZE_STAGES. TS: {ts_finalize}. Canonical: {canonical_finalize}."
        )


class TestApiPhaseToCanonDeleted:
    """Second-pass scrutiny deleted the dead `API_PHASE_TO_CANON` map
    from playwright_smoke.py — it had zero call sites and documented a
    stale 7-phase vocabulary (canonical PipelineState has 10). Pin the
    deletion so it can't be silently resurrected as authoritative.
    """

    def test_api_phase_to_canon_not_importable(self):
        import tools.playwright_smoke as ps
        assert not hasattr(ps, "API_PHASE_TO_CANON"), (
            "API_PHASE_TO_CANON was deleted in §9.3 second-pass audit "
            "(zero call sites, missing 3 canonical phases). If you need "
            "a phase→canon map, base it on the full PipelineState enum, "
            "not this stale 7-entry dict."
        )


# ── §9.3 #22 PR-B coverage (subprocess + timing hardening) ────────


class TestSubprocessLifecycle:
    """B1 — run_one_iter must use Popen with start_new_session=True and
    SIGKILL the entire process group on TimeoutExpired. Two timeouts on
    a 7-iter run was leaving ~4 orphan headless chromiums (~1 GB RSS)
    surviving until reboot.
    """

    @pytest.fixture(autouse=True)
    def _snapshot_pending_pgids(self):
        """§9.3 #24 B1-RACE — several tests in this class inject fake pgids
        (77777/88888/99999/2**30) into rs._PENDING_CHILD_PGIDS. If a test
        crashes between mock setup and the production `finally` block, the
        fake pgid leaks into module-global state. At pytest exit
        `_atexit_kill_pending_children` would then call
        `os.killpg(<fake_pgid>, SIGKILL)` — `_kill_pgid_safely` swallows
        `ProcessLookupError` in the common case, but under unlikely PID
        reuse this could SIGKILL an unrelated process group.

        Snapshot + restore around every test in this class so a fixture
        teardown ALWAYS clears any leaked pgids regardless of test outcome.
        """
        import tools.phase145_uat.run_session as rs
        before = set(rs._PENDING_CHILD_PGIDS)
        try:
            yield
        finally:
            rs._PENDING_CHILD_PGIDS.clear()
            rs._PENDING_CHILD_PGIDS.update(before)

    def test_pending_pgid_set_is_module_level(self):
        import tools.phase145_uat.run_session as rs
        assert hasattr(rs, "_PENDING_CHILD_PGIDS")
        assert isinstance(rs._PENDING_CHILD_PGIDS, set)

    def test_atexit_handler_is_registered(self):
        """atexit cleanup function must be registered at import time so an
        OOM / segfault in pure-Python land still kills children. We can't
        easily inspect atexit's registry across Python versions, but we
        can assert the symbol exists + is callable + tolerates an empty
        pending set (the most common case at exit).
        """
        import tools.phase145_uat.run_session as rs
        assert callable(rs._atexit_kill_pending_children)
        # Should be a no-op when the set is empty — must not raise.
        rs._PENDING_CHILD_PGIDS.clear()
        rs._atexit_kill_pending_children()

    def test_kill_pgid_safely_swallows_process_lookup(self):
        """A pgid that already exited must not raise — kill happens during
        cleanup paths where re-raising would mask the original error.
        """
        import tools.phase145_uat.run_session as rs
        # PID 1 is init/launchd; trying to killpg it with SIGKILL fails
        # with PermissionError (or on macOS with whatever pgid 1 holds).
        # Either way, must not raise out.
        rs._kill_pgid_safely(1)
        # Bogus pgid → ProcessLookupError, also swallowed.
        rs._kill_pgid_safely(2**30)

    def test_run_one_iter_invokes_popen_with_start_new_session(self, monkeypatch, tmp_path):
        """B1 contract: Popen must be invoked with start_new_session=True
        so killpg() on TimeoutExpired reaches grandchild chromium.
        """
        import tools.phase145_uat.run_session as rs

        captured: dict[str, object] = {}

        class FakeProc:
            pid = 99999
            returncode = 0

            def communicate(self, timeout=None):  # noqa: ARG002
                return ("", "")

        def fake_popen(cmd, **kwargs):  # noqa: ARG001
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs
            return FakeProc()

        def fake_getpgid(pid):
            return pid

        monkeypatch.setattr(rs.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(rs.os, "getpgid", fake_getpgid)

        op = OP_BY_ID["Op-1"]
        out_root = tmp_path / "out"
        out_root.mkdir()
        rs.run_one_iter(
            op,
            project_id="pid",
            api_url="http://x",
            dashboard_url="http://y",
            out_root=out_root,
            per_iter_timeout=90,  # §9.3 #23 minimum
        )

        assert captured["kwargs"].get("start_new_session") is True, (
            "Popen must be invoked with start_new_session=True so the "
            "child's grandchildren (chromium) can be reaped via killpg "
            "on TimeoutExpired. Without it, parent SIGKILL only takes "
            "the immediate child and the browser orphans."
        )
        # pgid must be discarded from the pending set after a clean run.
        assert 99999 not in rs._PENDING_CHILD_PGIDS

    def test_pgid_present_in_pending_set_during_call(self, monkeypatch, tmp_path):
        """B1-PGID-TRACK: existing `not in _PENDING_CHILD_PGIDS` post-call
        assertions cannot distinguish 'add+discard both ran' from
        'neither ran' ─ deleting both would silently disable the atexit
        safety net. Capture set membership DURING the call so an
        empty-add regression fails loudly.
        """
        import tools.phase145_uat.run_session as rs

        observed_during_call: list[set[int]] = []

        class FakeProc:
            pid = 77777
            returncode = 0
            def communicate(self, timeout=None):  # noqa: ARG002
                observed_during_call.append(set(rs._PENDING_CHILD_PGIDS))
                return ("", "")

        monkeypatch.setattr(rs.subprocess, "Popen", lambda cmd, **kw: FakeProc())
        monkeypatch.setattr(rs.os, "getpgid", lambda pid: pid)

        op = OP_BY_ID["Op-1"]
        out_root = tmp_path / "out"
        out_root.mkdir()
        rs.run_one_iter(
            op, project_id="pid", api_url="http://x", dashboard_url="http://y",
            out_root=out_root, per_iter_timeout=90,  # §9.3 #23 minimum
        )

        assert observed_during_call == [{77777}], (
            "B1-PGID-TRACK: 77777 must be in _PENDING_CHILD_PGIDS while "
            "communicate() runs, so atexit can reach it if the parent "
            "dies mid-call. Empty observation = the `add` line was "
            "deleted and the safety net is silently disabled."
        )
        assert 77777 not in rs._PENDING_CHILD_PGIDS

    def test_run_one_iter_killpg_on_timeout(self, monkeypatch, tmp_path):
        """B1 contract: on subprocess.TimeoutExpired, the pgid is SIGKILLed
        via _kill_pgid_safely. Without this the child's chromium orphans.
        """
        import tools.phase145_uat.run_session as rs

        killed: list[int] = []

        class FakeProc:
            pid = 88888
            returncode = -9

            def __init__(self):
                self._call = 0

            def communicate(self, timeout=None):  # noqa: ARG002
                self._call += 1
                if self._call == 1:
                    raise rs.subprocess.TimeoutExpired(cmd="fake", timeout=timeout)
                return ("", "stderr after kill")

            def kill(self):
                pass

        def fake_popen(cmd, **kwargs):  # noqa: ARG001
            return FakeProc()

        def fake_getpgid(pid):
            return pid

        monkeypatch.setattr(rs.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(rs.os, "getpgid", fake_getpgid)
        monkeypatch.setattr(rs, "_kill_pgid_safely", lambda pgid: killed.append(pgid))

        op = OP_BY_ID["Op-1"]
        out_root = tmp_path / "out"
        out_root.mkdir()
        run_dir, rc, stderr = rs.run_one_iter(
            op,
            project_id="pid",
            api_url="http://x",
            dashboard_url="http://y",
            out_root=out_root,
            per_iter_timeout=90,  # §9.3 #23 minimum; FakeProc raises TimeoutExpired regardless
        )

        assert run_dir is None
        assert rc == 124
        assert "TIMEOUT" in stderr
        assert killed == [88888], (
            "TimeoutExpired path must SIGKILL the whole process group via "
            "_kill_pgid_safely, not just the immediate child. Otherwise "
            "chromium grandchildren orphan."
        )
        # pgid must be removed from the pending set even on timeout path.
        assert 88888 not in rs._PENDING_CHILD_PGIDS

    # ── §9.3 #25 B1-COVERAGE — three recovery branches in run_one_iter ──

    def test_run_one_iter_returns_127_on_popen_filenotfound(self, monkeypatch, tmp_path):
        """B1-COVERAGE — when subprocess.Popen raises FileNotFoundError
        (e.g. broken sys.executable, missing playwright_smoke module),
        run_one_iter must return (None, 127, "subprocess spawn failed: …")
        rather than propagating the exception (which would crash the entire
        UAT session and lose all prior iter results).
        """
        import tools.phase145_uat.run_session as rs

        def fake_popen(cmd, **kwargs):  # noqa: ARG001
            raise FileNotFoundError("No such file or directory: 'python'")

        monkeypatch.setattr(rs.subprocess, "Popen", fake_popen)

        op = OP_BY_ID["Op-1"]
        out_root = tmp_path / "out"
        out_root.mkdir()
        run_dir, rc, stderr = rs.run_one_iter(
            op, project_id="pid", api_url="http://x", dashboard_url="http://y",
            out_root=out_root, per_iter_timeout=900,
        )

        assert run_dir is None
        assert rc == 127, "Conventional 'command not found' exit code"
        assert "subprocess spawn failed" in stderr

    def test_run_one_iter_falls_back_to_proc_pid_when_getpgid_lookups_fail(
        self, monkeypatch, tmp_path
    ):
        """B1-COVERAGE — if the child crashes between Popen and getpgid
        (rare; instant segfault before fork returns), os.getpgid raises
        ProcessLookupError. run_one_iter must fall back to proc.pid for
        kill-target purposes so the pending set still has SOME pgid to
        feed atexit.
        """
        import tools.phase145_uat.run_session as rs

        observed_during_call: list[set[int]] = []

        class FakeProc:
            pid = 42424
            returncode = 0
            def communicate(self, timeout=None):  # noqa: ARG002
                observed_during_call.append(set(rs._PENDING_CHILD_PGIDS))
                return ("", "")

        def fake_popen(cmd, **kwargs):  # noqa: ARG001
            return FakeProc()

        def fake_getpgid(pid):  # noqa: ARG001
            raise ProcessLookupError(f"no process: {pid}")

        monkeypatch.setattr(rs.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(rs.os, "getpgid", fake_getpgid)

        op = OP_BY_ID["Op-1"]
        out_root = tmp_path / "out"
        out_root.mkdir()
        rs.run_one_iter(
            op, project_id="pid", api_url="http://x", dashboard_url="http://y",
            out_root=out_root, per_iter_timeout=900,
        )

        assert observed_during_call == [{42424}], (
            "When os.getpgid raises ProcessLookupError, run_one_iter must "
            "fall back to proc.pid (42424) and add it to _PENDING_CHILD_PGIDS "
            "so the atexit handler still has a kill target."
        )

    def test_run_one_iter_kills_again_when_post_kill_communicate_also_timeouts(
        self, monkeypatch, tmp_path
    ):
        """B1-COVERAGE / B1-FALLBACK — extremely rare path: parent's
        proc.communicate raises TimeoutExpired, we SIGKILL the group, try
        to drain stderr with a 5 s budget, and THAT also TimeoutExpires
        (would require the kernel to block reaping after SIGKILL). The
        contract is to call _kill_pgid_safely a SECOND time (idempotent
        group kill) rather than fall back to proc.kill() — proc.kill
        only re-SIGKILLs the already-dead immediate child and leaves
        the chromium grandchildren alive.
        """
        import tools.phase145_uat.run_session as rs

        killed: list[int] = []

        class FakeProc:
            pid = 88889
            returncode = -9
            def __init__(self):
                self._call = 0
            def communicate(self, timeout=None):
                self._call += 1
                # Both calls (initial full timeout AND post-kill 5 s drain)
                # raise TimeoutExpired to exercise the inner-except branch.
                raise rs.subprocess.TimeoutExpired(cmd="fake", timeout=timeout)
            def kill(self):
                # If production code ever falls back to proc.kill() this
                # would be observed but the killed list (group-kill) would
                # be short by one entry — the assertion below catches it.
                pass

        def fake_popen(cmd, **kwargs):  # noqa: ARG001
            return FakeProc()

        monkeypatch.setattr(rs.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(rs.os, "getpgid", lambda pid: pid)
        monkeypatch.setattr(rs, "_kill_pgid_safely", lambda pgid: killed.append(pgid))

        op = OP_BY_ID["Op-1"]
        out_root = tmp_path / "out"
        out_root.mkdir()
        run_dir, rc, stderr = rs.run_one_iter(
            op, project_id="pid", api_url="http://x", dashboard_url="http://y",
            out_root=out_root, per_iter_timeout=900,
        )

        assert run_dir is None
        assert rc == 124, "TimeoutExpired still surfaces as 124 even when drain also times out"
        assert "TIMEOUT" in stderr
        assert killed == [88889, 88889], (
            "When the post-kill communicate also TimeoutExpires, "
            "_kill_pgid_safely must be invoked a SECOND time (idempotent "
            f"group kill). Got killed={killed!r}."
        )
        # pgid must STILL be removed from the pending set even after the
        # double-timeout path (the production `finally` block must run).
        assert 88889 not in rs._PENDING_CHILD_PGIDS


class TestChildWatchBudgetClamp:
    """B2 — playwright_smoke's per-mode max_seconds (60m default) must be
    clamped by the parent's --max-watch-secs flag so the child has time
    to ctx.snap(page, "timeout") and flush stderr before the parent
    SIGKILLs. Without the clamp every parent-timeout iter loses its DOM
    evidence — exactly the data §9.3 #20 needed.
    """

    def test_capped_max_seconds_is_identity_when_cap_unset(self, monkeypatch):
        import tools.playwright_smoke as ps
        monkeypatch.setattr(ps, "_MAX_WATCH_SECS_CAP", None)
        assert ps._capped_max_seconds(60 * 60) == 60 * 60
        assert ps._capped_max_seconds(30) == 30

    def test_capped_max_seconds_clamps_downward_only(self, monkeypatch):
        """If a mode requests 60s and the cap is 600s, the mode keeps its
        tighter budget. Caps are ceilings, not floors — a shorter
        intentional budget (e.g. run_reset_scoped_ui's 60s) must survive.
        """
        import tools.playwright_smoke as ps
        monkeypatch.setattr(ps, "_MAX_WATCH_SECS_CAP", 600)
        assert ps._capped_max_seconds(60 * 60) == 600  # 3600 → 600
        assert ps._capped_max_seconds(60) == 60        # 60 → 60 (unchanged)
        assert ps._capped_max_seconds(600) == 600      # equal → equal

    @pytest.mark.parametrize("bad_value", ["0", "-1", "-3600"])
    def test_max_watch_secs_cli_flag_rejects_non_positive(self, capsys, bad_value):
        """§9.3 #26 B2-CLI — production check is `if args.max_watch_secs
        <= 0`. The 0 path was already covered; negative values share the
        same branch but were unexercised. Parametrize so a future drift
        like `if args.max_watch_secs == 0` (off-by-one strictness) would
        let -1 silently pass the validation and produce a no-cap regression.
        """
        import tools.playwright_smoke as ps
        ap_args = ["--project-id", "x", "--max-watch-secs", bad_value]
        rc = ps.main(ap_args)
        assert rc == 2
        captured = capsys.readouterr()
        assert "--max-watch-secs must be > 0" in captured.err

    def test_max_watch_secs_cli_flag_sets_module_cap_on_positive(self, monkeypatch):
        """§9.3 #26 B2-CLI — *behavioral* check that a valid value actually
        installs the module-global `_MAX_WATCH_SECS_CAP`. The production
        code uses `globals()["_MAX_WATCH_SECS_CAP"] = args.max_watch_secs`,
        an indirect assignment that a refactor could silently revert to a
        plain local (which would silently disable the cap and reintroduce
        the §9.3 #22 data-loss class).

        Intercept the very next external call after cap install
        (Api.project) with a sentinel exception so we exit main()
        deterministically without requiring a live daemon. Then assert
        the cap WAS set despite the early bail.
        """
        import tools.playwright_smoke as ps

        # Reset cap to a known sentinel so we can detect the assignment.
        monkeypatch.setattr(ps, "_MAX_WATCH_SECS_CAP", None)

        class _StopAfterCap(Exception):
            pass

        def fake_project(self, project_id):  # noqa: ARG001
            # Cap is installed earlier in main(); raise here to bypass
            # the rest of main() without needing a real daemon.
            raise _StopAfterCap("stopping after cap install")

        monkeypatch.setattr(ps.Api, "project", fake_project)

        ap_args = [
            "--project-id", "x",
            "--modes", "initial",
            "--max-watch-secs", "600",
        ]
        with pytest.raises(_StopAfterCap):
            ps.main(ap_args)

        assert ps._MAX_WATCH_SECS_CAP == 600, (
            "After main() processes --max-watch-secs 600, the module-global "
            "_MAX_WATCH_SECS_CAP must equal 600 so _capped_max_seconds() "
            "actually clamps every mode's watch budget. A regression where "
            "the assignment becomes local instead of global would silently "
            "disable §9.3 #22 B2 — this behavioral pin catches that."
        )

    def test_run_one_iter_passes_max_watch_secs_to_child(self, monkeypatch, tmp_path):
        """Child cmd must include --max-watch-secs <per_iter_timeout - 30>
        so the global cap installs before any watch starts."""
        import tools.phase145_uat.run_session as rs

        captured_cmd: list[str] = []

        class FakeProc:
            pid = 1
            returncode = 0
            def communicate(self, timeout=None):  # noqa: ARG002
                return ("", "")

        def fake_popen(cmd, **kwargs):  # noqa: ARG001
            captured_cmd.extend(cmd)
            return FakeProc()

        monkeypatch.setattr(rs.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(rs.os, "getpgid", lambda pid: pid)

        op = OP_BY_ID["Op-1"]
        out_root = tmp_path / "out"
        out_root.mkdir()
        rs.run_one_iter(
            op, project_id="pid", api_url="http://x", dashboard_url="http://y",
            out_root=out_root, per_iter_timeout=900,
        )

        assert "--max-watch-secs" in captured_cmd
        idx = captured_cmd.index("--max-watch-secs")
        # 900 - 30 = 870
        assert captured_cmd[idx + 1] == "870", (
            f"Child watch cap must be per_iter_timeout - 30 = 870. "
            f"Got: {captured_cmd[idx + 1]}"
        )

    def test_per_iter_timeout_below_90_raises_value_error(self, tmp_path):
        """§9.3 #23 B2-FLOOR — historical behavior was
        `max(60, per_iter_timeout - 30)` which inverts the parent/child
        SIGKILL relationship when `per_iter_timeout < 90` (parent kills
        the group at e.g. 10 s while the child still believes it has 60 s
        to snapshot). The corrected contract: raise ValueError loudly so
        the operator fixes their config rather than silently losing
        timeout-snapshot evidence.
        """
        import tools.phase145_uat.run_session as rs

        op = OP_BY_ID["Op-1"]
        out_root = tmp_path / "out"
        out_root.mkdir()
        # Exhaustively cover the inversion range plus a value just below
        # the threshold. 89 must also fail — the boundary is strict (>=).
        for bad_timeout in (10, 30, 60, 89):
            with pytest.raises(ValueError, match="per_iter_timeout"):
                rs.run_one_iter(
                    op, project_id="pid", api_url="http://x", dashboard_url="http://y",
                    out_root=out_root, per_iter_timeout=bad_timeout,
                )

    def test_child_watch_cap_at_per_iter_timeout_90_is_60s(self, monkeypatch, tmp_path):
        """§9.3 #23 B2-FLOOR boundary — 90 s is the minimum supported value
        and produces a 60 s child cap (90 - 30 = 60). Pins the boundary so
        a future drift like `if per_iter_timeout <= 90:` (off-by-one) is
        caught by this test rather than silently shrinking the floor.
        """
        import tools.phase145_uat.run_session as rs

        captured_cmd: list[str] = []

        class FakeProc:
            pid = 1
            returncode = 0
            def communicate(self, timeout=None):  # noqa: ARG002
                return ("", "")

        def fake_popen(cmd, **kwargs):  # noqa: ARG001
            captured_cmd.extend(cmd)
            return FakeProc()

        monkeypatch.setattr(rs.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(rs.os, "getpgid", lambda pid: pid)

        op = OP_BY_ID["Op-1"]
        out_root = tmp_path / "out"
        out_root.mkdir()
        rs.run_one_iter(
            op, project_id="pid", api_url="http://x", dashboard_url="http://y",
            out_root=out_root, per_iter_timeout=90,
        )

        idx = captured_cmd.index("--max-watch-secs")
        assert captured_cmd[idx + 1] == "60", (
            "At the per_iter_timeout=90 boundary, child cap must be 60 "
            "(= 90 - 30). Got: " + captured_cmd[idx + 1]
        )

    # ── §9.3 #33 PR-F F6 — argparse-level --per-iter-timeout validation ──

    @pytest.mark.parametrize("bad_value", ["10", "30", "60", "89"])
    def test_main_rejects_per_iter_timeout_below_90_at_argparse(self, capsys, bad_value):
        """§9.3 #33 PR-F F6 — PR-E's ValueError in run_one_iter was
        unhandled by main(): an operator passing --per-iter-timeout 60
        would crash the entire UAT session with an unhandled traceback
        AFTER the daemon health probe. Move the floor check to argparse
        so the failure is a clean SystemExit(2) BEFORE any work begins.
        """
        import tools.phase145_uat.run_session as rs

        with pytest.raises(SystemExit) as exc_info:
            rs.main([
                "--project-id", "x",
                "--operations", "Op-1",
                "--iterations", "1",
                "--output", "/tmp/scorecard.md",
                "--per-iter-timeout", bad_value,
            ])
        assert exc_info.value.code == 2, (
            f"argparse rejection must exit 2, not propagate ValueError. "
            f"Got code={exc_info.value.code}"
        )
        captured = capsys.readouterr()
        assert "--per-iter-timeout" in captured.err
        assert "≥ 90" in captured.err or "90s" in captured.err, (
            "Error message must mention the 90s minimum so the operator knows "
            "what to change."
        )

    def test_main_rejects_non_integer_per_iter_timeout(self, capsys):
        """§9.3 #33 PR-F F6 — argparse type fn must also handle non-integer
        input (e.g. operator typo). int() raising surfaces a confusing
        builtin error; the custom type fn wraps it cleanly.
        """
        import tools.phase145_uat.run_session as rs

        with pytest.raises(SystemExit) as exc_info:
            rs.main([
                "--project-id", "x",
                "--operations", "Op-1",
                "--iterations", "1",
                "--output", "/tmp/scorecard.md",
                "--per-iter-timeout", "ninety",
            ])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "--per-iter-timeout" in captured.err
        assert "integer" in captured.err.lower()


class TestMonotonicClock:
    """B3 — watch_until_idle elapsed math must use time.monotonic(), not
    time.time(). Laptop sleep mid-iter (lid closed) or NTP step causes
    wall-clock jumps that fire false timeouts and mis-schedule
    --refresh-at-secs / --update-at-secs. Source-level pin: assert the
    function references time.monotonic() and the elapsed math uses the
    monotonic variant rather than wall.
    """

    def test_watch_until_idle_uses_monotonic_for_t0(self):
        import inspect
        import tools.playwright_smoke as ps
        src = inspect.getsource(ps.watch_until_idle)
        assert "t0_mono = time.monotonic()" in src, (
            "B3 regression: watch_until_idle must initialise t0 from "
            "time.monotonic(), not time.time(). Wall-clock breaks under "
            "laptop sleep / NTP step."
        )

    def test_watch_until_idle_separates_now_mono_from_now_wall(self):
        """now_mono drives elapsed math + next_poll; now_wall drives the
        Event timestamp so log readers can still correlate with daemon
        wall-clock logs. Both must be present.
        """
        import inspect
        import tools.playwright_smoke as ps
        src = inspect.getsource(ps.watch_until_idle)
        assert "now_mono = time.monotonic()" in src
        assert "now_wall = time.time()" in src
        # elapsed math now uses the monotonic snapshot.
        assert "elapsed = now_mono - t0_mono" in src

    def test_idle_since_and_next_poll_are_monotonic(self):
        """B3 strengthened pin: the PR claim 'next_poll / idle_since both
        monotonic' must actually hold ─ otherwise a partial revert that
        left t0_mono in place but switched next_poll back to wall would
        silently re-introduce sleep-jump bugs. Pin the specific call
        sites, not just the symbol presence.
        """
        import inspect
        import re
        import tools.playwright_smoke as ps
        src = inspect.getsource(ps.watch_until_idle)
        # next_poll must compare against and assign from now_mono.
        assert re.search(r"if\s+now_mono\s*>=\s*next_poll", src), (
            "B3 regression: `if now >= next_poll` must use now_mono. "
            "Wall-clock would mis-schedule polls under sleep/NTP."
        )
        assert re.search(r"next_poll\s*=\s*now_mono\s*\+\s*poll_interval", src), (
            "B3 regression: `next_poll = now + poll_interval` must use "
            "now_mono so the schedule advances linearly across sleep."
        )
        # idle_since assignment + compare both use now_mono.
        assert "idle_since = now_mono" in src, (
            "B3 regression: `idle_since = now` must use now_mono so the "
            "settle-window math survives wall-clock jumps."
        )
        assert "now_mono - idle_since" in src, (
            "B3 regression: `(now - idle_since) >= settle_seconds` must "
            "use now_mono - idle_since for the settle comparison."
        )

    def test_event_timestamps_in_watch_loop_use_now_wall(self):
        """B3 strengthened pin: Event(...) calls inside the watch loop
        should use now_wall (so timestamps remain correlatable to wall-
        clock daemon logs). Catch a partial revert where someone re-
        introduced Event(now, ...) and `now` is monotonic.
        """
        import inspect
        import re
        import tools.playwright_smoke as ps
        src = inspect.getsource(ps.watch_until_idle)
        # No stray `Event(now,` (must be now_wall or time.time() refetch).
        # We use a negative lookahead so `now_wall` / `now_mono` still match
        # explicitly when expected.
        stray = re.findall(r"Event\(now\s*,", src)
        assert stray == [], (
            f"B3 regression: found {len(stray)} `Event(now, ...)` calls "
            f"in watch_until_idle. Each must be `Event(now_wall, ...)` "
            f"(wall) or `Event(time.time(), ...)` (refetch). Stray usage "
            f"would produce monotonic-seconds Event timestamps that "
            f"cannot be correlated with daemon logs."
        )


class TestOp4HttpxTeardown:
    """B4 — httpx.TimeoutException / HTTPError raised by api.run_all in
    the scheduled_update path (§9.3 #20 daemon-side rebuild stall
    surfacing through Op-4) must be downgraded to a note event, not an
    error. Pre-fix this crashed scheduled_update → bubbled through
    watch_until_idle → tripped Playwright teardown → Op-4 status=ERR
    with the §9.3 #21 contextlib.py:158 traceback.
    """

    def test_scheduled_update_downgrades_httpx_timeout_to_note(self):
        """Source-level pin: the scheduled_update except block must call
        isinstance(e, (httpx.TimeoutException, httpx.HTTPError)) and
        route to a `note` event when True.
        """
        import inspect
        import tools.playwright_smoke as ps
        src = inspect.getsource(ps.watch_until_idle)
        assert "isinstance(" in src
        assert "httpx.TimeoutException" in src
        assert "httpx.HTTPError" in src
        # The new branch must produce a note, not an error_count++.
        assert "scheduled_update_transport_error" in src

    def test_main_closes_api_http_in_finally(self):
        """main() must close api.http via try/finally so a pending socket
        does not race sync_playwright()'s teardown.
        """
        import inspect
        import tools.playwright_smoke as ps
        src = inspect.getsource(ps.main)
        assert "api.http.close()" in src, (
            "B4 regression: api.http must be closed in main()'s finally "
            "block. Letting it gc during sync_playwright teardown "
            "produces §9.3 #21's contextlib.py:158 traceback."
        )
        # Must be in a finally block (not just in the happy path).
        assert "finally:" in src

    def test_httpx_downgrade_branch_does_not_increment_error_count(self):
        """B4 strengthened pin: a regression like
            elif is_httpx_transport_error:
                ctx.log(Event(..., "error", ...))
                ctx.summary.error_count += 1
        would still satisfy the original substring assertions while
        re-breaking §9.3 #20/#21. Pin the structural shape: the
        is_httpx_transport_error branch must produce a `note` event AND
        must NOT increment error_count.
        """
        import inspect
        import re
        import tools.playwright_smoke as ps
        src = inspect.getsource(ps.watch_until_idle)

        # Find the `elif is_httpx_transport_error:` block and capture
        # only lines INDENTED MORE DEEPLY than the elif itself ─ i.e.
        # the branch body, stopping at the sibling `else:` (which sits
        # at the same indent as the elif). A naive `(.*\n){1,N}` would
        # straddle into the else: branch and falsely match its
        # error_count++ usage.
        elif_match = re.search(
            r"^( *)elif\s+is_httpx_transport_error\s*:\s*\n", src, re.MULTILINE,
        )
        assert elif_match is not None, (
            "B4 regression: `elif is_httpx_transport_error:` branch "
            "missing from scheduled_update except block. The transport-"
            "error path would fall through to `else: error_count += 1` "
            "and resurrect §9.3 #21."
        )
        elif_indent = len(elif_match.group(1))
        body_lines: list[str] = []
        for line in src[elif_match.end():].splitlines():
            stripped = line.lstrip(" ")
            if not stripped:
                body_lines.append(line)
                continue
            line_indent = len(line) - len(stripped)
            if line_indent <= elif_indent:
                break
            body_lines.append(line)
        branch_body = "\n".join(body_lines)
        assert '"note"' in branch_body or "'note'" in branch_body, (
            f"B4 regression: httpx transport-error branch must log a "
            f"`note` event, not an `error`. Branch body:\n{branch_body}"
        )
        assert "error_count" not in branch_body, (
            f"B4 regression: httpx transport-error branch must NOT "
            f"increment error_count ─ that would turn a known daemon "
            f"stall into a smoke FAIL. Branch body:\n{branch_body}"
        )


# ── §9.3 #22 B5 — cancel_and_quiesce partial-failure tests ───────


class TestCancelQuiescePartialFailure:
    """B5 — per-group cancel outcomes must all surface in the notes
    string. Pre-PR-B the loop visits every target (good), but the
    notes assembly was never tested under a mixed 200/500 outcome —
    a future refactor could regress it to bail-on-first-failure
    without anyone noticing until a real partial-failure showed up
    in production.
    """

    def test_partial_failure_surfaces_per_group_status(self, monkeypatch):
        """fast_sync POST returns 200 (cancelled), deep_enrichment
        returns 500 (cancel-500). Both outcomes must appear in detail
        so a reviewer sees the partial state, not just the first event.
        """
        import tools.phase145_uat.run_session as rs

        class FakeResp:
            def __init__(self, code: int = 200, body: dict | None = None):
                self.status_code = code
                self._body = body if body is not None else {"data": {}}
            def json(self):
                return self._body

        def fake_get(url, *, timeout=None, **kw):  # noqa: ARG001
            return FakeResp(200, {"data": {
                "fast_sync": {"phase": "running"},
                "deep_enrichment": {"phase": "running"},
                "finalize": None,
            }})

        post_calls: list[str] = []
        def fake_post(url, *, json=None, timeout=None, **kw):  # noqa: ARG001
            grp = json["group"]
            post_calls.append(grp)
            if grp == "fast_sync":
                return FakeResp(200)
            return FakeResp(500, {"error": "Internal Server Error"})

        monkeypatch.setattr(rs.httpx, "get", fake_get)
        monkeypatch.setattr(rs.httpx, "post", fake_post)
        monkeypatch.setattr(rs, "wait_for_pipeline_idle", lambda *a, **k: False)

        quiesced, detail = rs.cancel_and_quiesce("http://x", "pid", max_seconds=0.5)

        # Both groups visited even though deep_enrichment 500'd.
        assert sorted(post_calls) == ["deep_enrichment", "fast_sync"]
        # Per-group outcome surfaced so the reviewer sees both.
        assert "fast_sync:cancelled" in detail
        assert "deep_enrichment:cancel-500" in detail
        # wait_for_pipeline_idle returned False → still-busy detail.
        assert quiesced is False
        assert "still busy" in detail

    def test_2xx_classification_is_status_code_only(self, monkeypatch):
        """§9.3 #27 B5-NAMING — production code branches on `r.status_code`
        and NEVER inspects the body. Old test name overpromised by
        suggesting we tolerate "unexpected schemas"; tighten by making
        the FakeResp body raise loudly if ever parsed — that way a future
        body-parsing regression like `if r.json().get("status") ==
        "cancelled":` fails this test instead of silently mis-classifying.
        """
        import tools.phase145_uat.run_session as rs

        class FakeResp:
            def __init__(self, code: int = 200):
                self.status_code = code
            def json(self):
                # §9.3 #27 B5-NAMING — if production parses the cancel
                # response body, fail loudly so the regression is visible.
                raise AssertionError(
                    "FakeResp.json() called: production cancel-classification "
                    "must rely on status_code only. If a future change inspects "
                    "the body, update both this test AND its docstring."
                )

        class FakeStatusResp:
            """Distinct response shape for the /pipeline/status GET path —
            wait_for_pipeline_idle is monkey-patched anyway, but the inline
            status-check in cancel_and_quiesce reads .json() to learn which
            groups are still active. Provide a real body here.
            """
            status_code = 200
            def json(self):
                return {"data": {
                    "fast_sync": {"phase": "running"},
                    "deep_enrichment": None,
                    "finalize": None,
                }}

        def fake_get(url, *, timeout=None, **kw):  # noqa: ARG001
            return FakeStatusResp()

        def fake_post(url, *, json=None, timeout=None, **kw):  # noqa: ARG001
            # 200 OK; body would raise AssertionError if production parsed it.
            return FakeResp(200)

        monkeypatch.setattr(rs.httpx, "get", fake_get)
        monkeypatch.setattr(rs.httpx, "post", fake_post)
        monkeypatch.setattr(rs, "wait_for_pipeline_idle", lambda *a, **k: True)

        quiesced, detail = rs.cancel_and_quiesce("http://x", "pid", max_seconds=0.5)
        assert quiesced is True
        assert "fast_sync:cancelled" in detail
        # No "cancel-err" or "cancel-200" parse error leaked through.
        assert "cancel-err" not in detail

    def test_first_group_failure_does_not_short_circuit_remaining_groups(self, monkeypatch):
        """B5-BAIL: the partial-failure test above fails the LAST group;
        a bail-on-first-failure regression (`if r.status_code != 200:
        return notes, ...`) would still pass it. Pin the opposite case:
        fast_sync (FIRST iterated) returns 500, deep_enrichment must
        still get POSTed AND its outcome must appear in detail.
        """
        import tools.phase145_uat.run_session as rs

        class FakeResp:
            def __init__(self, code: int = 200, body: dict | None = None):
                self.status_code = code
                self._body = body if body is not None else {"data": {}}
            def json(self):
                return self._body

        def fake_get(url, *, timeout=None, **kw):  # noqa: ARG001
            return FakeResp(200, {"data": {
                "fast_sync": {"phase": "running"},
                "deep_enrichment": {"phase": "running"},
                "finalize": None,
            }})

        post_calls: list[str] = []
        def fake_post(url, *, json=None, timeout=None, **kw):  # noqa: ARG001
            grp = json["group"]
            post_calls.append(grp)
            if grp == "fast_sync":
                # FIRST iterated group returns 500.
                return FakeResp(500, {"error": "Internal Server Error"})
            return FakeResp(200)

        monkeypatch.setattr(rs.httpx, "get", fake_get)
        monkeypatch.setattr(rs.httpx, "post", fake_post)
        monkeypatch.setattr(rs, "wait_for_pipeline_idle", lambda *a, **k: True)

        quiesced, detail = rs.cancel_and_quiesce("http://x", "pid", max_seconds=0.5)

        # Both targets visited despite fast_sync 500'ing first.
        assert sorted(post_calls) == ["deep_enrichment", "fast_sync"], (
            f"B5-BAIL: bail-on-first-failure regression would leave "
            f"deep_enrichment unvisited. Got post_calls={post_calls}."
        )
        assert "fast_sync:cancel-500" in detail
        assert "deep_enrichment:cancelled" in detail


# ── §9.3 #22 B6 — parse_iter_result empty-events.jsonl regression ─


class TestParseIterResultEmptyEvents:
    """B6 — pin the §9.3 #17 "bare-fail empty-notes" row class so a
    future refactor can't silently regress to fabricating notes from
    missing data or crashing on an empty events.jsonl.
    """

    def test_pass_true_with_empty_events_jsonl_produces_pass_row(self, tmp_path):
        """summary.pass=True + zero events ⇒ clean pass, empty notes.
        This is the happy-path baseline that any "surface evidence on
        fail" code path must not pollute.
        """
        op = _op("Op-1")
        run_dir = _write_smoke_output(
            tmp_path,
            mode=op.smoke_mode,
            summary={"mode": op.smoke_mode, "started_at": 1.0, "ended_at": 2.0,
                     "pass": True, "desync_count": 0, "anomaly_count": 0,
                     "invariant_failure_count": 0, "error_count": 0,
                     "stages_seen": [], "trigger_reason": "", "notes": []},
            events=[],
        )
        r = parse_iter_result(op, 1, run_dir)
        assert r.status == "pass"
        assert r.notes == ""
        assert all(r.invariants.values())

    def test_pass_false_with_empty_events_jsonl_is_bare_fail(self, tmp_path):
        """summary.pass=False + zero events ⇒ status=fail with empty
        notes. This is the §9.3 #17 row class: smoke marked it failed
        but produced no error/desync/invariant evidence to surface.
        The renderer's bare-fail trend depends on this row staying
        empty-notes so a count of "fail with no evidence" stays
        accurate. Past refactors have tried to fabricate notes here;
        this test pins the empty-string contract.
        """
        op = _op("Op-1")
        run_dir = _write_smoke_output(
            tmp_path,
            mode=op.smoke_mode,
            summary={"mode": op.smoke_mode, "started_at": 1.0, "ended_at": 2.0,
                     "pass": False, "desync_count": 0, "anomaly_count": 0,
                     "invariant_failure_count": 0, "error_count": 0,
                     "stages_seen": [], "trigger_reason": "", "notes": []},
            events=[],
        )
        r = parse_iter_result(op, 1, run_dir)
        assert r.status == "fail"
        assert r.notes == "", (
            "B6: bare-fail rows (pass=False with no error/desync/invariant "
            "events) must render with empty notes, not a fabricated string. "
            "The §9.3 #17 trend counter depends on this contract."
        )
        # Failures list also empty because no invariant_failure event.
        assert r.failures == []

    def test_pass_false_with_missing_events_file_does_not_crash(self, tmp_path):
        """A subprocess that crashed before writing events.jsonl (rare
        but observed) must not raise from parse_iter_result. Status =
        fail, notes empty (same contract as empty events.jsonl).
        """
        op = _op("Op-1")
        run_dir = tmp_path / "run_x"
        mode_dir = run_dir / op.smoke_mode
        mode_dir.mkdir(parents=True)
        (mode_dir / "summary.json").write_text(json.dumps({
            "mode": op.smoke_mode, "started_at": 1.0, "ended_at": 2.0,
            "pass": False, "desync_count": 0, "anomaly_count": 0,
            "invariant_failure_count": 0, "error_count": 0,
            "stages_seen": [], "trigger_reason": "", "notes": [],
        }))
        # No events.jsonl on disk.
        r = parse_iter_result(op, 1, run_dir)
        assert r.status == "fail"
        assert r.notes == ""


# ── §9.3 #22 B7 — _summarise_event_kind + _md_cell integration ────


class TestSummariseEventKindMdCellIntegration:
    """B7 — parse_iter_result builds the raw notes via
    `_summarise_event_kind` (+ `_clip_notes`); render_scorecard later
    wraps every cell through `_md_cell` at the markdown emit boundary.
    If a detail string contains a pipe or newline, the row must stay on
    a single line with the pipe escaped. The two helpers were
    individually tested; this pins the integration contract: notes
    survive the parse_iter_result → render_scorecard `_md_cell` wrap.
    """

    def test_pipe_in_event_detail_escaped_at_md_cell_boundary(self):
        """An error detail containing `|` (e.g. "cmd|grep failed") must
        not split the SCORECARD row. _summarise_event_kind formats it
        with surrounding quotes; _md_cell escapes the `|`. Together the
        result is a single-cell value with the pipe preserved + escaped.
        """
        from tools.phase145_uat.run_session import _md_cell, _summarise_event_kind
        events = [{"detail": "cmd|grep failed"}]
        summary = _summarise_event_kind(events, "error", "detail")
        cell = _md_cell(summary)
        # Pipe escaped (markdown-safe).
        assert "\\|" in cell
        # Bare pipe must not appear (would split the cell).
        assert "|" not in cell.replace("\\|", "")
        # Detail content preserved aside from the escape.
        assert "cmd" in cell and "grep" in cell

    def test_newline_in_event_detail_collapsed_at_md_cell_boundary(self):
        """An error detail with a newline (e.g. a Python traceback
        fragment) must collapse to ` · ` per _md_cell, not split the
        markdown row.
        """
        from tools.phase145_uat.run_session import _md_cell, _summarise_event_kind
        events = [{"detail": "Traceback\nFile foo.py line 1"}]
        summary = _summarise_event_kind(events, "error", "detail")
        cell = _md_cell(summary)
        assert "\n" not in cell
        assert " · " in cell

    def test_multiple_events_with_mixed_metacharacters(self):
        """Combined: error+desync events, mixed pipes/newlines, run
        through the full pipeline (parse_iter_result-style assembly).
        Result must be single-line + pipe-escaped + clipped to
        _NOTES_MAX_LEN.
        """
        from tools.phase145_uat.run_session import (
            _clip_notes,
            _md_cell,
            _summarise_event_kind,
        )
        error_events = [
            {"detail": "rebuild failed|bad config"},
            {"detail": "TIMEOUT\nstderr tail: stuck"},
        ]
        desync_events = [
            {"subtype": "progress_gap|api>>dom"},
        ]
        # Mirror the parse_iter_result assembly verbatim.
        parts = [
            _summarise_event_kind(error_events, "error", "detail"),
            _summarise_event_kind(desync_events, "desync", "subtype"),
        ]
        clipped = _clip_notes("; ".join(parts))
        cell = _md_cell(clipped)
        # Single-line.
        assert "\n" not in cell
        # Pipes escaped.
        assert "|" not in cell.replace("\\|", "")
        # Within the notes cap (md_cell does not change length materially).
        assert len(cell) <= _NOTES_MAX_LEN + 10  # +10 slack for `\|` escapes
