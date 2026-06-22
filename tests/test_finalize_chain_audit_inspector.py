"""Smoke test for tools/finalize_chain_audit.py render_events_summary.

This is the canonical operator tool for evaluating the Step 2 merge
gate — it must surface ALL events, not just historical phase=124 ones.

Phase 136 Part 09 Step 2 Follow-up A: regression guard against the
``latest_run_events(idx_dir, phase="124")`` filter, which silently
returned 0 events once pipeline_telemetry stopped persisting the
``phase`` field. Without the filter, both T2-era events and the new
chunked-synthesis Step-2 events must appear in the formatted output.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

from prep.services.pipeline_telemetry import record_event


_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOL_PATH = _REPO_ROOT / "tools" / "finalize_chain_audit.py"


def _load_tool_module():
    """Import tools/finalize_chain_audit.py as a module.

    The file lives outside the ``prep`` package — load it by path so
    the test does not depend on tool packaging.
    """
    spec = importlib.util.spec_from_file_location(
        "finalize_chain_audit_under_test", _TOOL_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_render_events_summary_lists_t2_and_step2_events(tmp_path: Path):
    """Operator runs the inspector — both T2 and Step-2 events appear.

    Reproduces the merge-gate scenario: a telemetry log written by
    today's pipeline (no ``phase`` field) contains an md_links_extracted
    event (T2) AND a concepts_synthesis_failed event (Step 2 chunked
    fallback signal). The formatted summary must mention both event
    names.
    """
    # Seed a telemetry log with two events that share a run_id so
    # latest_run_events groups them into a single run.
    run_id = "test-run-001"
    record_event(
        tmp_path,
        "md_links_extracted",
        {"run_id": run_id, "links": 12},
        stage="atlas",
    )
    record_event(
        tmp_path,
        "concepts_synthesis_failed",
        {"run_id": run_id, "reason": "chunk_meta_short_circuit"},
        stage="concepts",
    )

    mod = _load_tool_module()
    out = mod.render_events_summary(tmp_path)

    # Both event names appear in the rendered summary.
    assert "md_links_extracted" in out, out
    assert "concepts_synthesis_failed" in out, out
    # And the inspector did not silently report "no events".
    assert "no" not in out.lower() or "NOT FIRED" in out, out
