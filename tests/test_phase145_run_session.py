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
    _md_cell,
    _resolve_evidence_paths,
    cancel_and_quiesce,
    daemon_healthy,
    is_completed,
    parse_iter_result,
    persist_manifest,
    project_pipeline_ready,
    render_scorecard,
    wait_for_pipeline_idle,
)

from tools.playwright_smoke import _advance_scheduled_actions


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
    def test_returns_quiesced_false_and_detail_when_daemon_down(self):
        # Best-effort by design: cancel post errors, wait_for_idle times
        # out, helper returns False with both facts in the detail string.
        quiesced, detail = cancel_and_quiesce(
            "http://127.0.0.1:1", "any-pid", max_seconds=0.2,
        )
        assert quiesced is False
        assert "cancel post failed" in detail
        assert "still busy" in detail


class TestWaitForPipelineIdleFailure:
    def test_returns_false_when_daemon_unreachable(self):
        assert wait_for_pipeline_idle(
            "http://127.0.0.1:1", "any-pid", max_seconds=0.2,
        ) is False
