import pytest
from codrag.core.immune_watcher import evaluate_changes
from codrag.core.alert_queue import alert_queue
from codrag.services.antibody_store import AntibodyStore
from codrag.core.antibodies import Antibody, Trigger, TriggerType, Response, ResponseType, Severity


@pytest.fixture
def store(tmp_path):
    s = AntibodyStore()
    s.init(tmp_path / "test_antibodies.db")
    yield s
    s.close()


@pytest.fixture(autouse=True)
def clean_queue():
    alert_queue._queue.clear()
    alert_queue._seen_this_session.clear()
    yield
    alert_queue._queue.clear()
    alert_queue._seen_this_session.clear()


def test_evaluate_fires_on_matching_file(store):
    ab = Antibody(
        id="ab-1", name="Guard", source_concept_id="c-1",
        trigger=Trigger(type=TriggerType.FILE_MODIFIED, target="src/server.py"),
        response=Response(type=ResponseType.AMBIENT_INJECT, message="Server changed"),
        severity=Severity.WARN, status="active",
    )
    store.save("proj-1", ab)
    count = evaluate_changes("proj-1", ["src/server.py"], antibody_store=store)
    assert count == 1
    alerts = alert_queue.drain()
    assert len(alerts) == 1
    assert alerts[0].message == "Server changed"


def test_evaluate_skips_testing_antibodies(store):
    ab = Antibody(
        id="ab-1", name="Guard", source_concept_id="c-1",
        trigger=Trigger(type=TriggerType.FILE_MODIFIED, target="src/server.py"),
        response=Response(type=ResponseType.AMBIENT_INJECT, message="test"),
        severity=Severity.WARN, status="testing",
    )
    store.save("proj-1", ab)
    count = evaluate_changes("proj-1", ["src/server.py"], antibody_store=store)
    assert count == 0


def test_evaluate_no_match(store):
    ab = Antibody(
        id="ab-1", name="Guard", source_concept_id="c-1",
        trigger=Trigger(type=TriggerType.FILE_MODIFIED, target="src/other.py"),
        response=Response(type=ResponseType.AMBIENT_INJECT, message="test"),
        severity=Severity.WARN, status="active",
    )
    store.save("proj-1", ab)
    count = evaluate_changes("proj-1", ["src/server.py"], antibody_store=store)
    assert count == 0
