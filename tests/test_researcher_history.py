"""Tests for Researcher history persistence."""
import json
from pathlib import Path

import pytest

from prep.agents.researcher.history import ResearchHistory
from prep.agents.shared.models import ResearchPlan, ResearchTopic


@pytest.fixture
def history(tmp_path: Path) -> ResearchHistory:
    return ResearchHistory(tmp_path)


def _sample_topic() -> ResearchTopic:
    return ResearchTopic(
        finding_id="f1", title="Fix circular deps",
        description="core <-> api cycle",
        affected_files=["a.py"], priority="P1",
    )


def _sample_plan() -> ResearchPlan:
    return ResearchPlan(
        topic_id="f1", title="Fix circular deps",
        root_cause="Bidirectional import",
        fix_steps=["Extract shared types", "Update imports"],
        effort="medium", risk="low",
        testing_strategy="Run import checker",
    )


class TestResearchHistory:
    def test_save_and_load_run(self, history: ResearchHistory) -> None:
        run_id = history.save_run(
            topics=[_sample_topic()], plans=[_sample_plan()],
        )
        assert run_id
        loaded = history.get_run(run_id)
        assert loaded is not None
        assert len(loaded["topics"]) == 1
        assert len(loaded["plans"]) == 1
        assert loaded["topics"][0]["title"] == "Fix circular deps"

    def test_list_runs(self, history: ResearchHistory) -> None:
        history.save_run(topics=[_sample_topic()], plans=[_sample_plan()])
        history.save_run(topics=[_sample_topic()], plans=[_sample_plan()])
        runs = history.list_runs()
        assert len(runs) == 2

    def test_empty_history(self, history: ResearchHistory) -> None:
        assert history.list_runs() == []
        assert history.get_run("nonexistent") is None

    def test_run_has_timestamp(self, history: ResearchHistory) -> None:
        run_id = history.save_run(topics=[], plans=[])
        loaded = history.get_run(run_id)
        assert "timestamp" in loaded

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        h1 = ResearchHistory(tmp_path)
        run_id = h1.save_run(topics=[_sample_topic()], plans=[_sample_plan()])
        h2 = ResearchHistory(tmp_path)
        assert h2.get_run(run_id) is not None

    def test_latest_run(self, history: ResearchHistory) -> None:
        history.save_run(topics=[], plans=[])
        run_id2 = history.save_run(
            topics=[_sample_topic()], plans=[_sample_plan()],
        )
        latest = history.get_latest()
        assert latest is not None
        assert latest["run_id"] == run_id2
