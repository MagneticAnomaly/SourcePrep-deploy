"""Regression test: /pipeline/rebuild/stop must not drop the shared
embedder if another project is still using it.

2026-06-08 incident: stopping deep-live-cam appeared to also stop
SourcePrep. close_shared_embedders is process-wide; even when only
one project is in-flight on the embedder, dropping the singleton
invalidates any in-flight ONNX session for any other project."""
from __future__ import annotations

from unittest.mock import patch

from prep.services.embedder_factory import (
    _SHARED_EMBEDDERS,
    close_shared_embedders,
)


def test_close_with_no_active_embedding_releases():
    _SHARED_EMBEDDERS.clear()
    _SHARED_EMBEDDERS[("native", "x")] = object()
    with patch(
        "prep.services.embedder_factory._is_other_project_embedding",
        return_value=False,
    ):
        n = close_shared_embedders(active_project_id="pid_a")
    assert n == 1
    assert not _SHARED_EMBEDDERS


def test_close_with_other_project_embedding_skips():
    _SHARED_EMBEDDERS.clear()
    _SHARED_EMBEDDERS[("native", "x")] = object()
    with patch(
        "prep.services.embedder_factory._is_other_project_embedding",
        return_value=True,
    ):
        n = close_shared_embedders(active_project_id="pid_a")
    assert n == 0
    assert _SHARED_EMBEDDERS  # not cleared


def test_close_with_no_caller_id_force_releases():
    """Graceful daemon shutdown calls with active_project_id=None to
    force the release regardless of in-flight state — there is no
    other project to protect once the daemon is shutting down."""
    _SHARED_EMBEDDERS.clear()
    _SHARED_EMBEDDERS[("native", "x")] = object()
    # Even if _is_other_project_embedding would return True (it won't
    # be consulted when active_project_id is None), the release proceeds.
    with patch(
        "prep.services.embedder_factory._is_other_project_embedding",
        return_value=True,
    ):
        n = close_shared_embedders(active_project_id=None)
    assert n == 1
    assert not _SHARED_EMBEDDERS


def test_is_other_project_embedding_inspects_scheduler():
    """Internal helper consults the scheduler's __embedding__ slot
    and returns True iff any project OTHER than the caller has an
    active stage there."""
    from prep.services.embedder_factory import _is_other_project_embedding

    fake_status = {
        "nodes": {
            "__embedding__": {
                "active": {"pid_a": "knowledge", "pid_b": "deep_knowledge"},
            },
        },
    }
    with patch(
        "prep.services.pipeline.scheduler.pipeline_scheduler.status",
        return_value=fake_status,
    ):
        # pid_a is the caller — pid_b is the "other project"
        assert _is_other_project_embedding("pid_a") is True
        # pid_b is the caller — pid_a is the "other project"
        assert _is_other_project_embedding("pid_b") is True
        # pid_c is the caller — both pid_a and pid_b are others
        assert _is_other_project_embedding("pid_c") is True


def test_is_other_project_embedding_returns_false_when_only_caller_active():
    """When the embedding slot has only the caller's project (or is
    empty), the close should proceed."""
    from prep.services.embedder_factory import _is_other_project_embedding

    fake_status_solo = {
        "nodes": {
            "__embedding__": {"active": {"pid_a": "knowledge"}},
        },
    }
    with patch(
        "prep.services.pipeline.scheduler.pipeline_scheduler.status",
        return_value=fake_status_solo,
    ):
        assert _is_other_project_embedding("pid_a") is False

    fake_status_empty = {"nodes": {"__embedding__": {"active": {}}}}
    with patch(
        "prep.services.pipeline.scheduler.pipeline_scheduler.status",
        return_value=fake_status_empty,
    ):
        assert _is_other_project_embedding("pid_a") is False
