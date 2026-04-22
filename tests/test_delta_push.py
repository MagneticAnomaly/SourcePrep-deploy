"""Tests for push_significant_delta on PushEngine."""
from unittest.mock import MagicMock

import pytest

from prep.adapters.push_engine import PushEngine
from prep.services.collaboration.snapshots import StructuralDelta


def test_empty_delta_pushes_nothing():
    adapter = MagicMock()
    engine = PushEngine(adapter)
    delta = StructuralDelta(since=0, until=1000)
    count = engine.push_significant_delta(delta, "proj-1")
    assert count == 0
    adapter.create_issue.assert_not_called()


def test_rank_change_only_pushes_nothing():
    adapter = MagicMock()
    engine = PushEngine(adapter)
    delta = StructuralDelta(
        since=0, until=1000,
        hub_changes=[{"path": "src/foo.py", "change": "rank_changed", "old_rank": 3, "new_rank": 1}],
    )
    count = engine.push_significant_delta(delta, "proj-1")
    assert count == 0


def test_new_hub_creates_issue():
    adapter = MagicMock()
    adapter.find_issue_by_prep_address.return_value = None
    engine = PushEngine(adapter)
    delta = StructuralDelta(
        since=0, until=1000,
        hub_changes=[{"path": "src/gateway.py", "change": "new", "dependents_count": 14, "rank": 2}],
    )
    count = engine.push_significant_delta(delta, "proj-1")
    assert count == 1
    adapter.create_issue.assert_called_once()
    issue = adapter.create_issue.call_args[0][0]
    assert "src/gateway.py" in issue.title
    assert "new hub" in issue.title.lower() or "New hub" in issue.description


def test_dedup_same_delta_twice():
    adapter = MagicMock()
    adapter.find_issue_by_prep_address.return_value = "existing-id"
    engine = PushEngine(adapter)
    delta = StructuralDelta(
        since=0, until=1000,
        hub_changes=[{"path": "src/gateway.py", "change": "new", "dependents_count": 14, "rank": 2}],
    )
    count = engine.push_significant_delta(delta, "proj-1")
    assert count == 0
    adapter.create_issue.assert_not_called()


def test_mixed_delta_creates_multiple_issues():
    adapter = MagicMock()
    adapter.find_issue_by_prep_address.return_value = None
    engine = PushEngine(adapter)
    delta = StructuralDelta(
        since=0, until=1000,
        hub_changes=[{"path": "src/gw.py", "change": "new", "dependents_count": 10, "rank": 3}],
        module_changes=[{"name": "auth_v2", "change": "new", "file_count": 8}],
    )
    count = engine.push_significant_delta(delta, "proj-1")
    assert count == 2
    assert adapter.create_issue.call_count == 2
