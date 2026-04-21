import pytest
from prep.core.alert_queue import Alert, AlertQueue


def test_push_and_drain():
    q = AlertQueue(max_per_drain=3)
    q.push(Alert(antibody_id="ab1", antibody_name="Guard", severity="warn", message="test", file_path="a.py"))
    alerts = q.drain()
    assert len(alerts) == 1
    assert alerts[0].antibody_id == "ab1"


def test_drain_max():
    q = AlertQueue(max_per_drain=2)
    for i in range(5):
        q.push(Alert(antibody_id=f"ab{i}", antibody_name="G", severity="inform", message="m", file_path=f"f{i}.py"))
    alerts = q.drain()
    assert len(alerts) == 2


def test_drain_priority_order():
    q = AlertQueue(max_per_drain=3)
    q.push(Alert(antibody_id="a1", antibody_name="G", severity="inform", message="low", file_path="a.py"))
    q.push(Alert(antibody_id="a2", antibody_name="G", severity="review", message="high", file_path="b.py"))
    q.push(Alert(antibody_id="a3", antibody_name="G", severity="warn", message="mid", file_path="c.py"))
    alerts = q.drain()
    assert alerts[0].severity == "review"
    assert alerts[1].severity == "warn"
    assert alerts[2].severity == "inform"


def test_dedup_same_session():
    q = AlertQueue()
    q.push(Alert(antibody_id="ab1", antibody_name="G", severity="warn", message="m", file_path="a.py"))
    added = q.push(Alert(antibody_id="ab1", antibody_name="G", severity="warn", message="m", file_path="a.py"))
    assert added is False
    assert q.pending_count() == 1


def test_dedup_different_files():
    q = AlertQueue()
    q.push(Alert(antibody_id="ab1", antibody_name="G", severity="warn", message="m", file_path="a.py"))
    added = q.push(Alert(antibody_id="ab1", antibody_name="G", severity="warn", message="m", file_path="b.py"))
    assert added is True
    assert q.pending_count() == 2


def test_reset_session():
    q = AlertQueue()
    q.push(Alert(antibody_id="ab1", antibody_name="G", severity="warn", message="m", file_path="a.py"))
    q.drain()
    q.reset_session()
    added = q.push(Alert(antibody_id="ab1", antibody_name="G", severity="warn", message="m", file_path="a.py"))
    assert added is True


def test_drain_empty():
    q = AlertQueue()
    assert q.drain() == []
