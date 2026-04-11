import pytest
from codrag.services.antibody_store import AntibodyStore
from codrag.core.antibodies import Antibody, Trigger, TriggerType, Response, ResponseType, Severity


@pytest.fixture
def store(tmp_path):
    s = AntibodyStore()
    s.init(tmp_path / "test_antibodies.db")
    yield s
    s.close()


def _make_antibody(id="ab-1", name="Guard: Zero LLM", status="testing"):
    return Antibody(
        id=id, name=name, source_concept_id="c-1",
        trigger=Trigger(type=TriggerType.IMPORT_ADDED, target="src/pi.py", pattern="openai"),
        response=Response(type=ResponseType.AMBIENT_INJECT, message="LLM violation"),
        severity=Severity.REVIEW, status=status,
    )


def test_save_and_retrieve(store):
    ab = _make_antibody()
    store.save("proj-1", ab)
    retrieved = store.get(ab.id)
    assert retrieved is not None
    assert retrieved.name == "Guard: Zero LLM"
    assert retrieved.trigger.pattern == "openai"


def test_list_antibodies(store):
    store.save("proj-1", _make_antibody("ab-1"))
    store.save("proj-1", _make_antibody("ab-2", "Guard: B"))
    store.save("proj-2", _make_antibody("ab-3", "Other project"))
    results = store.list_antibodies("proj-1")
    assert len(results) == 2


def test_list_by_status(store):
    store.save("proj-1", _make_antibody("ab-1", status="testing"))
    store.save("proj-1", _make_antibody("ab-2", "Active", status="active"))
    results = store.list_antibodies("proj-1", status="active")
    assert len(results) == 1
    assert results[0].status == "active"


def test_update_status(store):
    store.save("proj-1", _make_antibody())
    store.update_status("ab-1", "active")
    ab = store.get("ab-1")
    assert ab.status == "active"


def test_record_trigger(store):
    store.save("proj-1", _make_antibody())
    store.record_trigger("ab-1")
    store.record_trigger("ab-1")
    ab = store.get("ab-1")
    assert ab.trigger_count == 2
    assert ab.last_triggered is not None


def test_record_dismiss(store):
    store.save("proj-1", _make_antibody())
    store.record_dismiss("ab-1")
    ab = store.get("ab-1")
    assert ab.dismiss_count == 1


def test_delete(store):
    store.save("proj-1", _make_antibody())
    store.delete("ab-1")
    assert store.get("ab-1") is None


def test_save_many_persists_all(store):
    abs_ = [_make_antibody(f"ab-{i}", f"Guard {i}") for i in range(5)]
    saved = store.save_many("proj-1", abs_)
    assert saved == 5
    assert len(store.list_antibodies("proj-1")) == 5


def test_save_many_empty_returns_zero(store):
    assert store.save_many("proj-1", []) == 0


def test_save_many_uses_one_commit(store):
    abs_ = [_make_antibody(f"ab-{i}", f"Guard {i}") for i in range(5)]
    statements: list[str] = []
    store._conn.set_trace_callback(lambda sql: statements.append(sql))
    try:
        store.save_many("proj-1", abs_)
    finally:
        store._conn.set_trace_callback(None)
    commit_count = sum(1 for s in statements if s.strip().upper() == "COMMIT")
    assert commit_count == 1, f"Expected 1 COMMIT, got {commit_count}: {statements}"


def test_busy_timeout_is_30s(store):
    timeout_ms = store._conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert timeout_ms == 30000
