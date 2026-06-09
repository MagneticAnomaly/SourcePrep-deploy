"""Regression test: PUT /global/config must not 500 because of a broken
import. The handler at src/prep/api/routers/system.py:update_global_config_v2
imports several names at request time. If any of them have been moved out
of prep.server, the ImportError bubbles up as a hard 500 (and the dashboard
silently breaks because it saves theme/layout state on load).

The 2026-06-09 UI hang traced back to ``_deep_merge`` having been moved
out of prep.server into prep.services.config_manager (commit f3dbd219).
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from prep.server import app


def test_put_global_config_does_not_500_on_import():
    """Empty-body PUT must return a non-500 status. The previous failure
    mode was ImportError → 500 INTERNAL_ERROR, before any validation or
    save logic ran."""
    client = TestClient(app)
    # Patch the IO-bound bits so we don't actually touch the UI config
    # store, but leave the import path real — that's what we're testing.
    with patch(
        "prep.server._load_ui_config", return_value={}
    ), patch(
        "prep.server._save_ui_config", return_value=None
    ):
        r = client.put("/global/config", json={})
    # Anything but 500 means the imports resolved cleanly. The handler
    # itself may still validate, merge, etc., but it doesn't crash at
    # the import line.
    assert r.status_code != 500, (
        f"PUT /global/config returned 500 — likely a broken import in "
        f"src/prep/api/routers/system.py:update_global_config_v2. "
        f"Response body: {r.text}"
    )


def test_deep_merge_import_path_is_valid():
    """The handler imports deep_merge as _deep_merge from
    prep.services.config_manager. Pin that path so future moves of the
    helper fire a CI failure here instead of silently 500ing in prod."""
    from prep.services.config_manager import deep_merge as _deep_merge
    out = _deep_merge({"a": 1, "b": {"c": 2}}, {"b": {"d": 3}})
    assert out == {"a": 1, "b": {"c": 2, "d": 3}}
