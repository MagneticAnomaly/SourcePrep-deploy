"""Test that POST /projects/{id}/pipeline/cancel accepts a reason
field so the X-button heuristic can distinguish user-initiated
cancels from infrastructure-initiated ones (drain timeout, watchdog,
etc.)."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from prep.server import app


def test_cancel_endpoint_accepts_reason_field():
    """The endpoint must accept reason in the request body. Reason
    defaults to 'user_action' so older clients omit it harmlessly."""
    client = TestClient(app)
    with patch(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator.cancel_fast_sync",
        return_value=True,
    ):
        # New-style call with explicit reason
        r1 = client.post(
            "/projects/fake-pid/pipeline/cancel",
            json={"group": "fast_sync", "reason": "user_action"},
        )
        # Old-style call without reason (must not break)
        r2 = client.post(
            "/projects/fake-pid/pipeline/cancel",
            json={"group": "fast_sync"},
        )
    assert r1.status_code in (200, 404, 409), r1.text
    assert r2.status_code in (200, 404, 409), r2.text


def test_cancel_endpoint_does_not_crash_on_unknown_group():
    """Defensive: an unknown group name must not crash the endpoint.
    The existing behavior is to route through ProgressManager, which
    returns 409 NOT_RUNNING if nothing of that name is active. Reason
    should pass through harmlessly regardless of the routing outcome."""
    client = TestClient(app)
    r = client.post(
        "/projects/fake-pid/pipeline/cancel",
        json={"group": "not_a_real_group", "reason": "user_action"},
    )
    # Either 200 with cancelled=False or 409 NOT_RUNNING — both acceptable.
    assert r.status_code in (200, 404, 409), r.text
