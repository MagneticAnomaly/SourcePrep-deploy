"""Regression test: POST /settings/pipeline-config must not dispatch
pipeline runs across projects.

See docs/superpowers/plans/2026-06-08-pipeline-reliability-ux-fixes.md
for the 2026-06-08 incident that motivated this guard.
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from prep.server import app


def test_pipeline_config_auto_flip_does_not_trigger_runs():
    """Flipping deep_enrichment_mode to 'auto' globally must not call
    pipeline_orchestrator.run_deep_enrichment for any project.

    Before the 2026-06-08 fix, the global endpoint spawned a background
    thread that iterated every active trace-enabled project and called
    run_deep_enrichment / run_fast_sync for each. After the fix, no
    thread is spawned and the orchestrator is never called from this
    endpoint, regardless of the global state. The assertions below
    pin that contract.
    """
    client = TestClient(app)
    with patch(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator.run_deep_enrichment"
    ) as run_deep, patch(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator.run_fast_sync"
    ) as run_fast:
        response = client.post(
            "/settings/pipeline-config",
            json={"deep_enrichment_mode": "auto", "fast_sync_auto": True},
        )

    assert response.status_code == 200
    assert run_deep.call_count == 0, (
        f"Global config flip dispatched run_deep_enrichment "
        f"{run_deep.call_count} times across projects — regression of "
        f"the 2026-06-08 fan-out bug."
    )
    assert run_fast.call_count == 0, (
        f"Global config flip dispatched run_fast_sync "
        f"{run_fast.call_count} times across projects — regression of "
        f"the 2026-06-08 fan-out bug."
    )
