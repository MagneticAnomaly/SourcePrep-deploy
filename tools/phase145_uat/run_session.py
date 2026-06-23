"""Phase 145 UAT session runner — drives tools.playwright_smoke through the
PROPOSAL §4 operation matrix N times each, emits a SCORECARD markdown doc.

See docs/Phase145_Pipeline-UI-Reliability/PROPOSAL_playwright-uat-harness-v1.md
§5 T3 for the goal + acceptance criterion (≥12 rows of 4 ops × 3 iters +
trends rollup).

Usage:
    .venv/bin/python -m tools.phase145_uat.run_session \\
        --project-id <homecolab-id> \\
        --iterations 3 \\
        --output docs/Phase145_Pipeline-UI-Reliability/SCORECARD_uat_$(date +%Y-%m-%d).md

The runner is RESUMABLE — every completed iteration is journaled to
`<output>.manifest.json` immediately. Re-running with `--resume <manifest>`
skips iterations already in the manifest, so a crash / interrupt does
not lose prior work (PROPOSAL §7 RU8).

A daemon health probe runs before every iteration; if the daemon is
unreachable, the iter is recorded as `skipped` and the runner moves on
to the next (PROPOSAL §7 RU6).

Each operation runs as a separate `python -m tools.playwright_smoke`
subprocess — process isolation means an OOM / browser hang in one
iteration cannot corrupt the runner's state.

Operation matrix (one-to-one with PROPOSAL §4):
    Op-1  Rebuild All clean       → playwright_smoke --modes rebuild
    Op-2  Incremental Update      → playwright_smoke --modes incremental
    Op-3  Mid-rebuild refresh     → --modes rebuild --refresh-at-secs 30
    Op-4  Update during Rebuild   → --modes rebuild --update-at-secs 10
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx


# ── Operation matrix (PROPOSAL §4) ────────────────────────────────


@dataclass(frozen=True)
class Operation:
    id: str
    label: str
    smoke_mode: str
    extra_args: tuple[str, ...] = ()


OPERATIONS: tuple[Operation, ...] = (
    Operation("Op-1", "Rebuild All clean",      "rebuild",     ()),
    Operation("Op-2", "Incremental Update",     "incremental", ()),
    Operation("Op-3", "Mid-rebuild refresh",    "rebuild",     ("--refresh-at-secs", "30")),
    # Op-4 fires the scheduled update at 20s (not 10s as originally drafted).
    # Rationale: watch_until_idle's startup_grace_seconds defaults to 15s
    # and the invariant 2-tick persistence gate adds ~4s before a first
    # emit is possible — anything fired before 19s lands in a deaf
    # detector. 20s gives one safety tick after grace expires.
    Operation("Op-4", "Update during Rebuild",  "rebuild",     ("--update-at-secs", "20")),
)

OP_BY_ID: dict[str, Operation] = {op.id: op for op in OPERATIONS}

# Maps every shipped invariant to the §-letter finding it primarily targets.
# Mirrors the docstrings on the invariant functions + PROPOSAL §3 table.
# Used for the SCORECARD "Mapped to findings" section so the doc stays
# self-explanatory without forcing the reader back to the proposal.
INV_TO_FINDING: dict[str, str] = {
    "I1":  "§2r (intra-group)",
    "I2":  "defensive (no §2r evidence today)",
    "I3":  "§2r (intra-group); cross-group leak NOT covered — see §9.1",
    "I13": "§2u §6.2",
}

SHIPPED_INVARIANTS: tuple[str, ...] = ("I1", "I2", "I3", "I13")


# ── Daemon health pre-check (PROPOSAL §7 RU6) ─────────────────────


def daemon_healthy(api_url: str, timeout: float = 2.0) -> bool:
    """Return True iff GET <api_url>/health returns 200 within `timeout`.

    Cheap liveness probe — used as the FIRST gate before the deeper
    project-level check. The shallow /health endpoint returns 200 even
    for a daemon that hasn't finished hydrating the registry or
    re-opened the SQLite stores, so callers should ALSO call
    `project_pipeline_ready` before treating an iter as runnable.

    Errors (timeout, connection refused, malformed response) all map to
    False — the caller treats False as "skip this iteration" and keeps
    going, so this MUST NOT raise.
    """
    try:
        r = httpx.get(f"{api_url.rstrip('/')}/health", timeout=timeout)
    except Exception:
        return False
    return r.status_code == 200


def project_pipeline_ready(api_url: str, project_id: str, timeout: float = 5.0) -> bool:
    """Return True iff the project's /pipeline/status endpoint answers 200.

    Catches the partial-startup case daemon_healthy can't (Lens A #3):
    /health returns 200 from a daemon whose registry is still hydrating
    or whose SQLite store is in read-only fallback, but
    /projects/{id}/pipeline/status will 500 or 404 because the project
    isn't loaded yet.

    Also used to detect "already running" between iters — a daemon mid-
    rebuild from a prior crashed-out iter responds normally to /health
    but its pipeline router will reject the next /pipeline/all with
    409. This probe doesn't return that signal directly, but pairing it
    with `wait_for_pipeline_idle` does.

    Errors map to False. MUST NOT raise.
    """
    try:
        r = httpx.get(
            f"{api_url.rstrip('/')}/projects/{project_id}/pipeline/status",
            timeout=timeout,
        )
    except Exception:
        return False
    return r.status_code == 200


# Phases that mean the daemon's run is genuinely done — POST
# /pipeline/rebuild or /pipeline/all will accept work immediately. Per
# state_machine.py:94-200 these are the four terminal states reachable
# from any group lifecycle.
_TERMINAL_PHASES: frozenset[str] = frozenset({
    "idle", "completed", "cancelled", "failed",
})


def wait_for_pipeline_idle(
    api_url: str,
    project_id: str,
    *,
    max_seconds: float = 30.0,
    poll_interval: float = 1.0,
) -> bool:
    """Poll /pipeline/status until every group is in a terminal phase, or
    timeout.

    Used by the cancel-quiesce path after a subprocess crash so the next
    iter doesn't immediately 409 because the daemon is still finishing
    work the killed subprocess left behind. Returns True iff the pipeline
    quiesced within `max_seconds`. Returns False on timeout or repeated
    API errors — caller treats False as "next iter is at risk; record but
    keep going" rather than abort.

    §9.3 #17 fix — the original code only treated `phase == "running"` as
    busy. A daemon mid-transition (queued / pausing / recovering /
    cancelling) reported as idle and the next iter cascade-failed (Op-2
    iter 3 → 409; Op-3/Op-4 → httpx 30s timeout). Now any phase OUTSIDE
    `_TERMINAL_PHASES` is treated as still-busy and the poll continues.
    Missing groups (null in payload) are treated as terminal — a group
    that never ran is by definition idle for our purposes.
    """
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        try:
            r = httpx.get(
                f"{api_url.rstrip('/')}/projects/{project_id}/pipeline/status",
                timeout=3.0,
            )
            if r.status_code == 200:
                body = r.json()
                payload = body.get("data") if isinstance(body, dict) and "data" in body else body
                if isinstance(payload, dict):
                    busy = False
                    for g in ("fast_sync", "deep_enrichment", "finalize"):
                        grp = payload.get(g)
                        if not isinstance(grp, dict):
                            continue
                        phase = grp.get("phase")
                        if isinstance(phase, str) and phase not in _TERMINAL_PHASES:
                            busy = True
                            break
                    if not busy:
                        return True
        except Exception:
            pass
        time.sleep(poll_interval)
    return False


# Phases a /pipeline/cancel post is meaningful for. Idle/completed/
# cancelled/failed are terminal. `queued` is pre-active but the
# orchestrator accepts cancels for queued groups (removes them from the
# queue). Anything else is a no-op we don't want to bother the daemon
# with.
_CANCELLABLE_PHASES: frozenset[str] = frozenset({
    "running", "pausing", "paused", "recovering", "cancelling", "queued",
})


def _pipeline_snapshot(api_url: str, project_id: str) -> dict[str, str]:
    """Return `{group_name: phase}` for the three top-level pipeline groups.

    Empty string for missing/unreachable groups so callers can do plain
    `phase in _CANCELLABLE_PHASES` checks without `None` handling.
    MUST NOT raise — daemon-down maps to all-empty.
    """
    snapshot: dict[str, str] = {g: "" for g in ("fast_sync", "deep_enrichment", "finalize")}
    try:
        r = httpx.get(
            f"{api_url.rstrip('/')}/projects/{project_id}/pipeline/status",
            timeout=3.0,
        )
        if r.status_code != 200:
            return snapshot
        body = r.json()
        payload = body.get("data") if isinstance(body, dict) and "data" in body else body
        if not isinstance(payload, dict):
            return snapshot
        for g in snapshot:
            grp = payload.get(g)
            if isinstance(grp, dict):
                phase = grp.get("phase")
                if isinstance(phase, str):
                    snapshot[g] = phase
    except Exception:
        pass
    return snapshot


def cancel_and_quiesce(
    api_url: str,
    project_id: str,
    *,
    max_seconds: float = 30.0,
) -> tuple[bool, str]:
    """Best-effort cancel of every active group, then wait for idle.

    `/pipeline/cancel` takes ONE group at a time and requires a JSON body
    of `{group, reason}` (see `src/prep/api/routers/pipeline.py`
    `CancelRequest`). An empty-body POST returns 400 silently because
    `httpx` does not raise on non-2xx — that exact bug burned the first
    T4 dry run and is documented in PROPOSAL §9.1 (cancel-quiesce-
    empty-body false-negative).

    We snapshot `/pipeline/status`, post cancel for every group whose
    phase is in `_CANCELLABLE_PHASES`, then `wait_for_pipeline_idle` for
    the remainder of `max_seconds`. 409 NOT_RUNNING is treated as
    already-stopped (group quiesced between snapshot and cancel post).
    Other non-2xx codes are surfaced in the notes string but do not
    block the quiesce wait.

    Returns `(quiesced, detail)`; detail is surfaced verbatim in the
    scorecard so a reviewer can see what the runner did.
    """
    snapshot = _pipeline_snapshot(api_url, project_id)
    targets = [g for g, phase in snapshot.items() if phase in _CANCELLABLE_PHASES]

    if not targets:
        # No active groups visible. Either pipeline is already idle, or
        # the daemon is unreachable. Run the idle probe anyway: if
        # status answered 200 with all terminal phases, this returns
        # True fast. Daemon-down returns False after the budget.
        quiesced = wait_for_pipeline_idle(api_url, project_id, max_seconds=max_seconds)
        detail = (
            "already idle (nothing to cancel)" if quiesced
            else f"no active groups visible; still not idle after {max_seconds}s"
        )
        return quiesced, detail

    notes: list[str] = []
    for group in targets:
        try:
            r = httpx.post(
                f"{api_url.rstrip('/')}/projects/{project_id}/pipeline/cancel",
                json={"group": group, "reason": "uat_session_cleanup"},
                timeout=5.0,
            )
            if r.status_code == 200:
                notes.append(f"{group}:cancelled")
            elif r.status_code == 409:
                notes.append(f"{group}:already-stopped")
            else:
                notes.append(f"{group}:cancel-{r.status_code}")
        except Exception as e:
            notes.append(f"{group}:cancel-err-{type(e).__name__}")

    quiesced = wait_for_pipeline_idle(api_url, project_id, max_seconds=max_seconds)
    state = "quiesced" if quiesced else f"still busy after {max_seconds}s"
    return quiesced, f"{', '.join(notes)}; {state}"


# ── Result + manifest dataclasses ─────────────────────────────────


@dataclass
class IterResult:
    op_id: str
    iter_num: int
    run_dir: str
    status: str            # "pass" | "fail" | "skipped" | "error"
    invariants: dict[str, bool] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = ""
    ended_at: str = ""
    notes: str = ""

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "IterResult":
        return cls(**data)


@dataclass
class SessionManifest:
    session_id: str
    project_id: str
    iterations: int
    operations: list[str]
    api_url: str
    dashboard_url: str
    out_root: str
    completed: list[IterResult] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "iterations": self.iterations,
            "operations": list(self.operations),
            "api_url": self.api_url,
            "dashboard_url": self.dashboard_url,
            "out_root": self.out_root,
            "completed": [asdict(r) for r in self.completed],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "SessionManifest":
        raw_completed = data.get("completed") or []
        return cls(
            session_id=data["session_id"],
            project_id=data["project_id"],
            iterations=int(data["iterations"]),
            operations=list(data.get("operations") or []),
            api_url=data["api_url"],
            dashboard_url=data["dashboard_url"],
            out_root=data["out_root"],
            completed=[IterResult.from_json(r) for r in raw_completed],
        )


def is_completed(manifest: SessionManifest, op_id: str, iter_num: int) -> bool:
    """True iff the (op_id, iter_num) pair already has a recorded result.

    Any terminal status — pass, fail, error, skipped — counts as completed.
    Re-running a failed/errored iter requires manually removing it from
    the manifest. This is intentional: resume-after-crash should pick up
    where we left off, not silently redo work the caller might be
    inspecting.
    """
    return any(r.op_id == op_id and r.iter_num == iter_num for r in manifest.completed)


# ── playwright_smoke output parsing ───────────────────────────────


def _ts_from_epoch(v: Any) -> str:
    """Convert epoch seconds → UTC ISO-8601 string. Empty string if v is
    missing or non-positive (treats 0.0 as "never set", matching
    playwright_smoke's ModeSummary.ended_at sentinel).
    """
    if isinstance(v, (int, float)) and v > 0:
        return datetime.fromtimestamp(v, tz=timezone.utc).isoformat()
    return ""


def parse_iter_result(op: Operation, iter_num: int, run_dir: Path) -> IterResult:
    """Read playwright_smoke's per-mode summary + events into an IterResult.

    playwright_smoke writes:
        <run_dir>/<mode>/summary.json         — ModeSummary.to_json
        <run_dir>/<mode>/events.jsonl         — one JSON object per line

    We pull pass/fail from summary, and walk events.jsonl for
    `kind == "invariant_failure"` to compute per-invariant pass/fail.
    Any invariant that did NOT appear in a failure event during the iter
    is considered passing — playwright_smoke deliberately only logs
    failures (passing invariants would produce ~7k useless lines/hour).
    """
    mode_dir = run_dir / op.smoke_mode
    summary_path = mode_dir / "summary.json"
    events_path = mode_dir / "events.jsonl"

    if not summary_path.is_file():
        return IterResult(
            op_id=op.id,
            iter_num=iter_num,
            run_dir=str(run_dir),
            status="error",
            invariants={k: True for k in SHIPPED_INVARIANTS},
            notes=f"missing summary.json at {summary_path}",
        )

    try:
        summary = json.loads(summary_path.read_text())
    except json.JSONDecodeError as e:
        return IterResult(
            op_id=op.id,
            iter_num=iter_num,
            run_dir=str(run_dir),
            status="error",
            invariants={k: True for k in SHIPPED_INVARIANTS},
            notes=f"summary.json parse error: {e}",
        )

    invariants_seen: dict[str, list[dict[str, Any]]] = {}
    # §9.3 #17 — surface raw error/desync evidence in IterResult.notes when
    # the smoke flagged failure but no shipped invariant fired. Without this
    # the SCORECARD renders ✓✓✓✓ + FAIL with empty notes, hiding the
    # actual signal (Op-1 iter 1's desyncs, Op-3/Op-4's "timed out", etc.)
    # in the events.jsonl that reviewers don't open.
    error_events: list[dict[str, Any]] = []
    desync_events: list[dict[str, Any]] = []
    if events_path.is_file():
        with events_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = ev.get("kind")
                if kind == "invariant_failure":
                    inv_id = ev.get("invariant_id")
                    if not inv_id:
                        continue
                    invariants_seen.setdefault(inv_id, []).append({
                        "label": ev.get("label", ""),
                        "evidence": ev.get("evidence", {}),
                        "ts": ev.get("ts"),
                    })
                elif kind == "error":
                    error_events.append(ev)
                elif kind == "desync":
                    desync_events.append(ev)

    inv_status = {
        inv_id: (inv_id not in invariants_seen)
        for inv_id in SHIPPED_INVARIANTS
    }
    failures = [
        {
            "invariant_id": inv_id,
            "count": len(events),
            "first_evidence": events[0].get("evidence", {}) if events else {},
        }
        for inv_id, events in sorted(invariants_seen.items())
    ]

    base_status = "pass" if summary.get("pass") else "fail"
    # An invariant_failure event means pass=False already on the smoke side
    # (watch_until_idle flips `ok` to False), but be defensive in case the
    # smoke pass flag and the events log ever drift.
    if failures and base_status == "pass":
        base_status = "fail"

    # §9.3 #17 — only surface raw evidence on actual failures, only when no
    # invariant matched (failures list is the authoritative summary when
    # present; double-reporting would noise up the Notes column).
    raw_evidence_note = ""
    if base_status == "fail" and not failures:
        parts: list[str] = []
        if error_events:
            first_detail = str(error_events[0].get("detail", ""))[:80]
            parts.append(f"error×{len(error_events)} '{first_detail}'")
        if desync_events:
            first_subtype = str(desync_events[0].get("subtype", ""))[:40]
            parts.append(f"desync×{len(desync_events)} '{first_subtype}'")
        if parts:
            raw_evidence_note = "; ".join(parts)
            # Hard cap so a pathological many-events case still fits a
            # markdown table cell.
            if len(raw_evidence_note) > 180:
                raw_evidence_note = raw_evidence_note[:177] + "..."

    return IterResult(
        op_id=op.id,
        iter_num=iter_num,
        run_dir=str(run_dir),
        status=base_status,
        invariants=inv_status,
        failures=failures,
        started_at=_ts_from_epoch(summary.get("started_at")),
        ended_at=_ts_from_epoch(summary.get("ended_at")),
        notes=raw_evidence_note,
    )


# ── Scorecard rendering ───────────────────────────────────────────


def _summarise_failures(failures: list[dict[str, Any]]) -> str:
    if not failures:
        return ""
    return "; ".join(f"{f['invariant_id']} ×{f['count']}" for f in failures)


def _inv_glyph(passed: bool) -> str:
    return "✓" if passed else "✗"


def _status_label(status: str) -> str:
    return {
        "pass":    "pass",
        "fail":    "FAIL",
        "error":   "ERR",
        "skipped": "skip",
    }.get(status, status)


def _md_cell(s: Any) -> str:
    """Escape a value for safe inclusion in a markdown table cell.

    Markdown table rows terminate on `\\n`; a literal `|` splits cells.
    parse_iter_result builds notes from subprocess stderr tails and
    json.JSONDecodeError messages — both can contain newlines (Python
    tracebacks always do). Without escaping, an errored iter silently
    corrupts every row beneath it in the Results table and the doc is
    unreadable. Lens B Tier-1 (review 2026-06-22).

    We also strip carriage returns and collapse internal whitespace runs
    so the cell stays single-line and visually narrow.
    """
    if s is None:
        return ""
    text = str(s).replace("\r", "")
    # Newline → ` · ` (compact + visually obvious it was multi-line).
    text = text.replace("\n", " · ")
    # Pipe → `\|` (markdown escape).
    text = text.replace("|", "\\|")
    return text


def _resolve_evidence_paths(run_dir: str, mode: str, inv_id: str) -> list[Path]:
    """Glob the actual on-disk screenshot files for an invariant failure.

    playwright_smoke names screenshots `{seq:03d}_invariant_{inv_id}_FAIL.png`
    (tools/playwright_smoke.py RunContext.snap). Lens B #4 surfaced that
    rendering a literal glob in the scorecard makes the reviewer
    copy-paste-glob to find evidence; resolving at render time and
    emitting concrete paths is one extra Path.glob per failure.

    Returns sorted file paths so the doc is stable across renders.
    Empty list when run_dir does not exist (e.g. error iter that never
    created its output dir) — caller falls back to the pattern string.
    """
    base = Path(run_dir) / mode
    if not base.is_dir():
        return []
    try:
        return sorted(base.glob(f"*_invariant_{inv_id}_FAIL.png"))
    except OSError:
        return []


def render_scorecard(manifest: SessionManifest, *, today: Optional[str] = None) -> str:
    """Render the SCORECARD markdown document from a SessionManifest.

    Format per PROPOSAL §5 T3 (with Status column added in T3 — see §5):
        - Header: project, iterations, session start, partial-session banner
        - Status legend (4-line glossary so the reader doesn't have to
          re-derive what "skip" vs "ERR" means)
        - Results table: one row per (op, iter), columns for each invariant
        - Rolled-up trends: per-op per-invariant failure rates over PLANNED
          iters (manifest.iterations × #ops), not just over completed
          iters — a partial session reports `1/3` not `1/1` for an op
          that has only one iter recorded (Lens A #4)
        - Mapped to findings: failure → §-letter + resolved evidence files

    Cells run through _md_cell so newlines / pipes in stderr-derived
    notes don't break the markdown table (Lens B Tier-1).

    `today` overrides the date in the H1 header (test hook so the doc is
    deterministic in pytest; defaults to ISO date of the session_id).
    """
    if today is None:
        today = manifest.session_id.split("T")[0]

    op_order = {op.id: i for i, op in enumerate(OPERATIONS)}
    planned_op_ids = list(manifest.operations) or [op.id for op in OPERATIONS]
    planned_total = manifest.iterations * len(planned_op_ids)
    completed_total = len(manifest.completed)
    is_partial = completed_total < planned_total

    lines: list[str] = [
        f"# Phase 145 UAT Scorecard — {today}",
        "",
        f"**Project:** `{manifest.project_id}`",
        f"**Iterations per op:** {manifest.iterations}",
        f"**Operations:** {', '.join(planned_op_ids)}",
        f"**Session id:** {manifest.session_id}",
        f"**Out root:** `{manifest.out_root}`",
        f"**Iterations recorded:** {completed_total}/{planned_total}"
        + (" (partial)" if is_partial else " (complete)"),
        "",
    ]
    if is_partial:
        lines += [
            "> **NOTE: partial session.** "
            f"{completed_total} of {planned_total} planned iterations are recorded. "
            "Trend percentages below are over PLANNED iterations, with the "
            "observed sample size in parens so a 0%-recorded op is not "
            "silently misread as 0%-failing.",
            "",
        ]
    lines += [
        "**Status legend:** `pass` = all invariants held; `FAIL` = at least "
        "one invariant fired OR smoke exited non-zero; `ERR` = subprocess "
        "crash / missing summary; `skip` = daemon /health unreachable.",
        "",
        "## Results",
        "",
        "| Op | Iter | Status | I1 | I2 | I3 | I13 | Notes |",
        "|---|---:|:--:|:--:|:--:|:--:|:--:|---|",
    ]

    sorted_results = sorted(
        manifest.completed,
        key=lambda r: (op_order.get(r.op_id, 999), r.iter_num),
    )
    for r in sorted_results:
        op_label = OP_BY_ID.get(r.op_id).label if r.op_id in OP_BY_ID else r.op_id
        inv_cols = " | ".join(
            _inv_glyph(r.invariants.get(k, True)) for k in SHIPPED_INVARIANTS
        )
        notes_raw = r.notes or _summarise_failures(r.failures) or (
            "clean" if r.status == "pass" else ""
        )
        lines.append(
            f"| {_md_cell(r.op_id)} {_md_cell(op_label)} | {r.iter_num} | "
            f"{_status_label(r.status)} | {inv_cols} | {_md_cell(notes_raw)} |"
        )

    lines += ["", "## Rolled-up trends", ""]
    by_op: dict[str, list[IterResult]] = {}
    for r in manifest.completed:
        by_op.setdefault(r.op_id, []).append(r)

    any_trend = False
    for op_id in planned_op_ids:
        op_def = OP_BY_ID.get(op_id)
        if op_def is None:
            continue
        rs = by_op.get(op_id, [])
        observed = len(rs)
        planned = manifest.iterations
        denom = planned if planned > 0 else max(observed, 1)
        for inv_id in SHIPPED_INVARIANTS:
            fails = sum(1 for r in rs if not r.invariants.get(inv_id, True))
            if fails:
                pct = round(100 * fails / denom, 1)
                suffix = f"observed {observed}/{planned}" if observed < planned else ""
                trail = f" ({suffix})" if suffix else ""
                lines.append(
                    f"- **{op_id} {inv_id}** failure rate **{fails}/{denom} ({pct}%)** — {op_def.label}{trail}"
                )
                any_trend = True
        # Lens B #2: surface status=fail with no per-invariant signal so the
        # trends section can't read "clean" while the Results table shows FAIL.
        bare_fails = sum(1 for r in rs if r.status == "fail" and not r.failures)
        if bare_fails:
            lines.append(
                f"- {op_id}: {bare_fails}/{denom} iter(s) failed without invariant evidence — see Notes column"
            )
            any_trend = True
        skipped = sum(1 for r in rs if r.status == "skipped")
        errored = sum(1 for r in rs if r.status == "error")
        if skipped:
            lines.append(f"- {op_id}: {skipped}/{denom} iter(s) skipped (daemon health)")
            any_trend = True
        if errored:
            lines.append(f"- {op_id}: {errored}/{denom} iter(s) errored (subprocess fault)")
            any_trend = True
    if not any_trend:
        if completed_total == 0:
            lines.append("- No iterations recorded yet.")
        else:
            lines.append("- All recorded iterations passed every invariant. No trends to report.")

    lines += [
        "",
        "## Mapped to findings",
        "",
        "| Failure | Maps to | Evidence file(s) |",
        "|---|---|---|",
    ]
    mapped_rows = 0
    for r in sorted_results:
        for f in r.failures:
            inv_id = f["invariant_id"]
            mode = OP_BY_ID.get(r.op_id).smoke_mode if r.op_id in OP_BY_ID else "?"
            paths = _resolve_evidence_paths(r.run_dir, mode, inv_id)
            if paths:
                evid_text = "; ".join(f"`{p}`" for p in paths)
            else:
                evid_text = f"`{r.run_dir}/{mode}/*_invariant_{inv_id}_FAIL.png` _(pattern; no files on disk)_"
            lines.append(
                f"| {r.op_id} iter {r.iter_num} {inv_id} | "
                f"{INV_TO_FINDING.get(inv_id, '?')} | {_md_cell(evid_text)} |"
            )
            mapped_rows += 1
    if mapped_rows == 0:
        lines.append("| _(no failures)_ | _(n/a)_ | _(n/a)_ |")

    lines.append("")
    return "\n".join(lines)


# ── Subprocess invocation ─────────────────────────────────────────


def run_one_iter(
    op: Operation,
    project_id: str,
    api_url: str,
    dashboard_url: str,
    out_root: Path,
    per_iter_timeout: int,
) -> tuple[Optional[Path], int, str]:
    """Invoke playwright_smoke as a subprocess for ONE op iteration.

    Snapshots `out_root` before/after so we can identify the new
    `run_<ts>` directory the subprocess created. Returns
    `(run_dir, returncode, stderr)`. `run_dir` is None when the
    subprocess timed out or crashed before creating its output dir.
    """
    cmd = [
        sys.executable, "-m", "tools.playwright_smoke",
        "--project-id", project_id,
        "--modes", op.smoke_mode,
        "--iterations", "1",
        "--api-url", api_url,
        "--dashboard-url", dashboard_url,
        "--out-root", str(out_root),
        *op.extra_args,
    ]
    print(f"  $ {' '.join(cmd)}", flush=True)

    pre = set(out_root.glob("run_*")) if out_root.is_dir() else set()
    # Lens D #3: capture_output=True buffers stdout + stderr in RAM until
    # exit. playwright_smoke defaults --verbose=True and prints ~5
    # events/poll; a 15-minute iter ≈ tens of MB held by the parent we
    # never read. Drop stdout to /dev/null (we only ever use the stderr
    # tail) and keep stderr piped at a bounded tail length.
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=per_iter_timeout,
        )
        rc = result.returncode
        stderr_tail = (result.stderr or "")[-400:]
    except subprocess.TimeoutExpired as e:
        # TimeoutExpired exposes captured-so-far stderr; surface its tail
        # so the manifest can hint at where the subprocess was when it
        # hung (e.g. last `stage-start` it logged).
        partial_stderr = (getattr(e, "stderr", None) or "")
        if isinstance(partial_stderr, bytes):
            partial_stderr = partial_stderr.decode("utf-8", errors="replace")
        return None, 124, f"TIMEOUT after {per_iter_timeout}s; stderr tail: {partial_stderr[-200:]}"
    except FileNotFoundError as e:
        return None, 127, f"subprocess spawn failed: {e}"

    post = set(out_root.glob("run_*"))
    new_dirs = sorted(post - pre, key=lambda p: p.stat().st_mtime)
    if new_dirs:
        return new_dirs[-1], rc, stderr_tail
    return None, rc, stderr_tail or "no new run_* directory created"


# ── Manifest persistence ──────────────────────────────────────────


def persist_manifest(manifest: SessionManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a sibling tempfile then rename so a crash mid-write
    # cannot leave the manifest half-flushed (resume must be safe).
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(manifest.to_json(), indent=2, default=str))
    tmp.replace(path)


# ── CLI entry point ───────────────────────────────────────────────


def _new_session_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Phase 145 UAT session runner — drives playwright_smoke "
                    "through the §4 operation matrix N times each."
    )
    ap.add_argument("--project-id", required=True,
                    help="Target project UUID. HomeColab is the canonical UAT subject.")
    ap.add_argument("--iterations", type=int, default=3,
                    help="Iterations per operation (default: 3). 4 ops × 3 = 12 rows.")
    ap.add_argument("--operations",
                    default=",".join(op.id for op in OPERATIONS),
                    help="Comma-separated op IDs to run (default: all four).")
    ap.add_argument("--output", required=True,
                    help="Path to write the SCORECARD markdown document.")
    ap.add_argument("--out-root", default="tests/eval/ui_smoke",
                    help="playwright_smoke output root (default: tests/eval/ui_smoke).")
    ap.add_argument("--api-url", default="http://localhost:8400")
    ap.add_argument("--dashboard-url", default="http://localhost:5174")
    ap.add_argument("--per-iter-timeout", type=int, default=15 * 60,
                    help="Wall-clock budget per iter, seconds (default: 900 = 15m).")
    ap.add_argument("--inter-iter-pause", type=int, default=10,
                    help="Pause between iterations, seconds (default: 10).")
    ap.add_argument("--resume",
                    help="Path to a previous session manifest JSON to resume.")
    args = ap.parse_args(argv)

    req_ops = [s.strip() for s in args.operations.split(",") if s.strip()]
    unknown_ops = [op for op in req_ops if op not in OP_BY_ID]
    if unknown_ops:
        print(f"ERROR: unknown operations: {unknown_ops}", file=sys.stderr)
        return 2
    selected = [OP_BY_ID[op_id] for op_id in req_ops]

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output)
    manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")

    if args.resume:
        resume_path = Path(args.resume)
        if not resume_path.is_file():
            print(f"ERROR: resume manifest not found: {resume_path}", file=sys.stderr)
            return 2
        manifest = SessionManifest.from_json(json.loads(resume_path.read_text()))
        manifest_path = resume_path
        print(
            f"Resuming session {manifest.session_id} — "
            f"{len(manifest.completed)} iteration(s) already recorded.",
            flush=True,
        )
    else:
        manifest = SessionManifest(
            session_id=_new_session_id(),
            project_id=args.project_id,
            iterations=args.iterations,
            operations=[op.id for op in selected],
            api_url=args.api_url,
            dashboard_url=args.dashboard_url,
            out_root=str(out_root),
        )
        print(f"New session {manifest.session_id}", flush=True)
        print(f"manifest → {manifest_path}", flush=True)

    # Initial daemon health probe — fail fast if the daemon isn't even up
    # or its project registry hasn't hydrated. Per-iter probes still run.
    if not daemon_healthy(args.api_url):
        print(
            f"ERROR: daemon at {args.api_url} did not respond to /health. "
            "Run scripts/dev.sh first.",
            file=sys.stderr,
        )
        return 3
    if not project_pipeline_ready(args.api_url, args.project_id):
        print(
            f"ERROR: daemon /health is up but /projects/{args.project_id}/pipeline/status "
            "is not answering. Project may not be registered, daemon may be "
            "mid-hydration, or the project UUID is wrong.",
            file=sys.stderr,
        )
        return 3

    for op in selected:
        for iter_num in range(1, args.iterations + 1):
            if is_completed(manifest, op.id, iter_num):
                print(f"\n[{op.id} iter {iter_num}/{args.iterations}] skipped (already in manifest)",
                      flush=True)
                continue

            print(f"\n[{op.id} iter {iter_num}/{args.iterations}] {op.label}", flush=True)

            # Lens A #3 + RU6: two-step health probe (liveness +
            # project-readiness) catches partial-startup daemons that
            # /health alone misses.
            if not daemon_healthy(args.api_url) or not project_pipeline_ready(args.api_url, args.project_id):
                print("  daemon / project pipeline not ready → recording as skipped", flush=True)
                manifest.completed.append(IterResult(
                    op_id=op.id,
                    iter_num=iter_num,
                    run_dir="",
                    status="skipped",
                    invariants={k: True for k in SHIPPED_INVARIANTS},
                    notes="daemon health or project /pipeline/status unreachable at iter start",
                ))
                persist_manifest(manifest, manifest_path)
                continue

            run_dir, rc, stderr_tail = run_one_iter(
                op,
                args.project_id,
                args.api_url,
                args.dashboard_url,
                out_root,
                args.per_iter_timeout,
            )

            if run_dir is None:
                result = IterResult(
                    op_id=op.id,
                    iter_num=iter_num,
                    run_dir="",
                    status="error",
                    invariants={k: True for k in SHIPPED_INVARIANTS},
                    notes=f"subprocess rc={rc}: {stderr_tail[:200]}",
                )
            else:
                result = parse_iter_result(op, iter_num, run_dir)
                if rc != 0 and result.status == "pass":
                    result.status = "fail"
                    result.notes = (result.notes or "") + f" (smoke rc={rc})"

            manifest.completed.append(result)
            persist_manifest(manifest, manifest_path)
            inv_summary = " ".join(
                f"{k}={_inv_glyph(result.invariants.get(k, True))}"
                for k in SHIPPED_INVARIANTS
            )
            print(f"  → {result.status}, invariants: {inv_summary}", flush=True)

            # Lens A #1 (Tier-1): if the iter timed out or otherwise errored,
            # the playwright_smoke subprocess was killed but the daemon-side
            # pipeline is almost certainly still running. The next iter
            # would then 409 from /pipeline/rebuild and cascade-fail the
            # rest of the session. Cancel + wait for idle before moving on.
            if result.status in ("error", "fail") or rc != 0:
                quiesced, detail = cancel_and_quiesce(args.api_url, args.project_id)
                print(f"  cancel-quiesce: {detail}", flush=True)
                # Annotate the iter notes so the scorecard reader sees
                # what the runner did about the stall.
                result.notes = (result.notes + " · " if result.notes else "") + f"cancel-quiesce: {detail}"
                persist_manifest(manifest, manifest_path)

            time.sleep(args.inter_iter_pause)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_scorecard(manifest))
    print(f"\nSCORECARD → {output_path}", flush=True)
    print(f"manifest  → {manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
