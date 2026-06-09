"""Regression test: POST /settings/pipeline-config must not dispatch
pipeline runs across projects.

See docs/superpowers/plans/2026-06-08-pipeline-reliability-ux-fixes.md
for the 2026-06-08 incident that motivated this guard.
"""
from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from prep.server import app


def _make_fake_registry(project_ids: list[str]):
    """Return a mock registry whose list_projects() yields trace-enabled projects."""
    fake_projects = [
        SimpleNamespace(
            id=pid,
            config={"trace": {"enabled": True}},
        )
        for pid in project_ids
    ]
    registry = MagicMock()
    registry.list_projects.return_value = fake_projects
    return registry


def test_pipeline_config_auto_flip_does_not_trigger_runs():
    """Flipping deep_enrichment_mode to 'auto' globally must not call
    pipeline_orchestrator.run_deep_enrichment for any project.

    The fake registry exposes two trace-enabled projects so that the old
    fan-out code would have dispatched two run_deep_enrichment calls.
    After the fix, call_count must remain zero.
    """
    client = TestClient(app)
    fake_registry = _make_fake_registry(["proj-aaa", "proj-bbb"])

    with patch(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator.run_deep_enrichment"
    ) as run_deep, patch(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator.run_fast_sync"
    ) as run_fast, patch(
        # This is the import path used inside the background thread
        "prep.services.project_helpers.get_registry",
        return_value=fake_registry,
    ), patch(
        # Always return "active" so activity check passes
        "prep.services.project_helpers.get_project_activity_status",
        return_value="active",
    ):
        response = client.post(
            "/settings/pipeline-config",
            json={"deep_enrichment_mode": "auto", "fast_sync_auto": True},
        )
        # Give background thread (if any) time to fire before we check counts.
        time.sleep(0.3)

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
