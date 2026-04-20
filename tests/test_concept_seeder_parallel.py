"""Task 2: verify non-swarm concept seeding fans out across modules via llm_pool."""
from __future__ import annotations

import json
import threading
import time
from unittest.mock import MagicMock, patch


class _FakeConceptLLM:
    """Fake LLMClient for concept seeding. Records concurrent in-flight calls."""

    def __init__(self, latency: float = 0.1) -> None:
        self.model = "fake/concept-model"
        self.provider = "fake"
        self._latency = latency
        self._in_flight = 0
        self._peak = 0
        self._lock = threading.Lock()
        self.calls = 0

    def generate(self, prompt=None, **_kw):
        with self._lock:
            self._in_flight += 1
            if self._in_flight > self._peak:
                self._peak = self._in_flight
            self.calls += 1
        try:
            time.sleep(self._latency)
            return (
                json.dumps({
                    "concepts": [
                        {
                            "title": f"Concept-{self.calls}",
                            "content": "why this matters",
                            "category": "architecture",
                            "confidence": 0.8,
                            "anchors": [],
                            "tags": [],
                        }
                    ]
                }),
                {"in": 10, "out": 10},
            )
        finally:
            with self._lock:
                self._in_flight -= 1


def _fake_modules(n: int) -> list[dict]:
    return [
        {
            "module_id": f"mod{i}",
            "name": f"Module {i}",
            "member_files": [f"path/mod{i}/file{j}.py" for j in range(6)],
            "summary": f"module {i} summary",
        }
        for i in range(n)
    ]


def test_concept_seeding_parallel_fans_out_per_module(tmp_path, monkeypatch):
    """With 6 modules and prefer_swarm=False, the non-swarm path should
    submit 6 per-module LLM calls concurrently via llm_pool."""
    from codrag.core import concept_seeder

    fake_llm = _FakeConceptLLM(latency=0.25)

    fake_project = MagicMock()
    fake_project.name = "FakeProj"
    fake_project.path = str(tmp_path)

    saves: list[dict] = []

    with patch("codrag.services.project_helpers.require_project", return_value=fake_project), \
         patch("codrag.core.project_registry.project_index_dir", return_value=tmp_path), \
         patch.object(concept_seeder, "_get_seeder_llm", return_value=fake_llm), \
         patch.object(concept_seeder, "_load_modules_for_swarm",
                      return_value=_fake_modules(6)), \
         patch("codrag.services.concept_store.concept_store", create=True) as cs_mock:

        cs_mock.save = MagicMock(side_effect=lambda **kw: saves.append(kw))
        cs_mock.save_question = MagicMock()

        result = concept_seeder.seed_concepts("proj-1", prefer_swarm=False)

    assert fake_llm.calls == 6, f"expected 6 per-module calls, got {fake_llm.calls}"
    assert fake_llm._peak >= 2, (
        f"expected peak in-flight >=2 (fan-out working); got {fake_llm._peak}"
    )
    assert result["status"] == "success"
    assert result["concepts_created"] == len(saves)
    assert result["mode"] == "parallel"


def test_concept_seeding_falls_back_to_single_call_for_tiny_project(tmp_path):
    """Projects with <2 modules should still work via the single-call path."""
    from codrag.core import concept_seeder

    fake_llm = _FakeConceptLLM(latency=0.05)
    fake_project = MagicMock()
    fake_project.name = "Tiny"
    fake_project.path = str(tmp_path)

    with patch("codrag.services.project_helpers.require_project", return_value=fake_project), \
         patch("codrag.core.project_registry.project_index_dir", return_value=tmp_path), \
         patch.object(concept_seeder, "_get_seeder_llm", return_value=fake_llm), \
         patch.object(concept_seeder, "_load_modules_for_swarm", return_value=[]), \
         patch.object(concept_seeder, "_assemble_seeding_context",
                      return_value="x" * 500), \
         patch.object(concept_seeder, "_call_llm_for_concepts",
                      return_value='{"concepts": [], "questions": []}'), \
         patch("codrag.services.concept_store.concept_store", create=True) as cs_mock:

        cs_mock.save = MagicMock()
        cs_mock.save_question = MagicMock()

        result = concept_seeder.seed_concepts("proj-tiny", prefer_swarm=False)

    assert result["status"] == "success"
    assert result["mode"] == "single_call"
