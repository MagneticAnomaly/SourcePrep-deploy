"""Tests for TraceAugmenter and DeepAnalysisOrchestrator."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from codrag.core.augmenter import (
    AugmentationEntry,
    AugmentResult,
    LLMClient,
    TraceAugmenter,
    _parse_json_response,
    VALID_ROLES,
)
from codrag.core.deep_analysis import (
    DeepAnalysisOrchestrator,
    DeepAnalysisResult,
    DeepAnalysisSchedule,
    ValidationItem,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def tmp_index(tmp_path: Path) -> Path:
    """Create a temp index dir with trace data."""
    idx = tmp_path / "index"
    idx.mkdir()
    return idx


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a temp repo with sample files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        'def hello():\n    """Say hello."""\n    print("hello")\n\ndef add(a, b):\n    return a + b\n'
    )
    (repo / "utils.py").write_text(
        'import os\n\ndef read_file(path):\n    """Read a file."""\n    return open(path).read()\n'
    )
    return repo


def _write_trace(idx: Path, nodes: List[Dict], edges: List[Dict], file_hashes: Optional[Dict] = None):
    """Write trace files to index dir."""
    with open(idx / "trace_nodes.jsonl", "w") as f:
        for n in nodes:
            f.write(json.dumps(n) + "\n")
    with open(idx / "trace_edges.jsonl", "w") as f:
        for e in edges:
            f.write(json.dumps(e) + "\n")
    manifest = {
        "version": "1.0",
        "built_at": "2025-02-11T00:00:00Z",
        "counts": {"nodes": len(nodes), "edges": len(edges)},
    }
    if file_hashes:
        manifest["file_hashes"] = file_hashes
    with open(idx / "trace_manifest.json", "w") as f:
        json.dump(manifest, f)


SAMPLE_NODES = [
    {"id": "node-file-1", "kind": "file", "name": "main.py", "file_path": "main.py", "span": None, "language": "python", "metadata": {}},
    {"id": "node-sym-1", "kind": "symbol", "name": "hello", "file_path": "main.py", "span": {"start_line": 1, "end_line": 3}, "language": "python", "metadata": {"symbol_type": "function"}},
    {"id": "node-sym-2", "kind": "symbol", "name": "add", "file_path": "main.py", "span": {"start_line": 5, "end_line": 6}, "language": "python", "metadata": {"symbol_type": "function"}},
    {"id": "node-file-2", "kind": "file", "name": "utils.py", "file_path": "utils.py", "span": None, "language": "python", "metadata": {}},
    {"id": "node-sym-3", "kind": "symbol", "name": "read_file", "file_path": "utils.py", "span": {"start_line": 3, "end_line": 5}, "language": "python", "metadata": {"symbol_type": "function"}},
]

SAMPLE_EDGES = [
    {"id": "edge-1", "kind": "contains", "source": "node-file-1", "target": "node-sym-1", "metadata": {}},
    {"id": "edge-2", "kind": "contains", "source": "node-file-1", "target": "node-sym-2", "metadata": {}},
    {"id": "edge-3", "kind": "contains", "source": "node-file-2", "target": "node-sym-3", "metadata": {}},
    {"id": "edge-4", "kind": "imports", "source": "node-file-2", "target": "node-ext-os", "metadata": {"import": "import os"}},
]


class FakeLLMClient:
    """Fake LLM client for testing."""

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        self.endpoint_url = "http://localhost:11434"
        self.model = "test-model"
        self.calls: List[str] = []
        self.responses = responses or {}
        self._default_response = json.dumps({
            "summary": "Test summary",
            "role": "utility",
            "confidence": 0.85,
        })

    def generate(self, prompt: str, system: Optional[str] = None, **kwargs: Any) -> Tuple[str, int]:
        self.calls.append(prompt)
        # Check if any key in responses matches a substring of the prompt
        for key, resp in self.responses.items():
            if key in prompt:
                return resp, 100
        return self._default_response, 100

    def is_available(self) -> bool:
        return True


# ── Tests: _parse_json_response ───────────────────────────────


class TestParseJsonResponse:
    def test_direct_json(self):
        result = _parse_json_response('{"summary": "test", "confidence": 0.9}')
        assert result is not None
        assert result["summary"] == "test"

    def test_json_in_markdown_block(self):
        text = '```json\n{"summary": "test", "confidence": 0.9}\n```'
        result = _parse_json_response(text)
        assert result is not None
        assert result["summary"] == "test"

    def test_json_with_surrounding_text(self):
        text = 'Here is the result: {"summary": "test", "confidence": 0.9} done.'
        result = _parse_json_response(text)
        assert result is not None
        assert result["summary"] == "test"

    def test_invalid_json(self):
        assert _parse_json_response("not json at all") is None

    def test_empty_string(self):
        assert _parse_json_response("") is None


# ── Tests: AugmentationEntry ──────────────────────────────────


class TestAugmentationEntry:
    def test_round_trip(self):
        entry = AugmentationEntry(
            node_id="node-1",
            summary="Does something",
            role="utility",
            confidence=0.85,
            augmented_at="2025-02-11T00:00:00Z",
            model="test",
            file_hash="abc123",
        )
        d = entry.to_dict()
        restored = AugmentationEntry.from_dict(d)
        assert restored.node_id == "node-1"
        assert restored.summary == "Does something"
        assert restored.confidence == 0.85
        assert restored.file_hash == "abc123"

    def test_validated_fields(self):
        entry = AugmentationEntry(
            node_id="node-1",
            summary="Test",
            role="utility",
            confidence=0.9,
            augmented_at="2025-02-11T00:00:00Z",
            model="test",
            validated=True,
            validated_at="2025-02-12T00:00:00Z",
            validated_by="large-model",
        )
        d = entry.to_dict()
        assert d["validated"] is True
        assert d["validated_at"] == "2025-02-12T00:00:00Z"


# ── Tests: TraceAugmenter ─────────────────────────────────────


class TestTraceAugmenter:
    def test_load_existing_empty(self, tmp_index, tmp_repo):
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        assert aug.load_existing() == {}

    def test_load_existing_with_data(self, tmp_index, tmp_repo):
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        # Write some augmentations
        entry = AugmentationEntry(
            node_id="node-1", summary="test", role="utility",
            confidence=0.8, augmented_at="2025-01-01", model="m",
        )
        with open(tmp_index / "trace_augmented.jsonl", "w") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
        existing = aug.load_existing()
        assert "node-1" in existing
        assert existing["node-1"].summary == "test"

    def test_run_augments_symbols(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        result = aug.run()
        assert result.augmented > 0
        assert result.total_nodes == len(SAMPLE_NODES)
        # Should have called LLM for symbols + files
        assert len(client.calls) > 0

    def test_run_writes_augmented_file(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        aug.run()
        assert (tmp_index / "trace_augmented.jsonl").exists()
        assert (tmp_index / "trace_augment_manifest.json").exists()

    def test_incremental_skips_unchanged(self, tmp_index, tmp_repo):
        hashes = {"main.py": "hash1", "utils.py": "hash2"}
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES, file_hashes=hashes)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)

        # First run augments everything
        r1 = aug.run()
        assert r1.augmented > 0
        calls_first = len(client.calls)

        # Second run should skip (hashes unchanged)
        client.calls.clear()
        r2 = aug.run()
        assert r2.skipped > 0
        assert len(client.calls) == 0  # No LLM calls needed

    def test_max_items_limit(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        result = aug.run(max_items=1)
        assert result.augmented <= 1

    def test_handles_llm_failure(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES[:3], SAMPLE_EDGES[:2])

        class FailingClient(FakeLLMClient):
            def generate(self, prompt, system=None, **kwargs):
                raise ConnectionError("LLM down")

        client = FailingClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        result = aug.run()
        assert result.failed > 0
        assert result.augmented == 0

    def test_handles_bad_json_response(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES[:3], SAMPLE_EDGES[:2])

        class BadJsonClient(FakeLLMClient):
            def generate(self, prompt, system=None, **kwargs):
                return "I don't know how to respond in JSON", 50

        client = BadJsonClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        result = aug.run()
        assert result.failed > 0

    def test_status_no_augmentation(self, tmp_index, tmp_repo):
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        s = aug.status()
        assert s["enabled"] is False
        assert s["augmented_nodes"] == 0

    def test_status_after_run(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        aug.run()
        s = aug.status()
        assert s["enabled"] is True
        assert s["augmented_nodes"] > 0
        assert 0.0 <= s["avg_confidence"] <= 1.0

    def test_confidence_clamped(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES[:3], SAMPLE_EDGES[:2])
        client = FakeLLMClient(responses={
            "hello": json.dumps({"summary": "test", "role": "utility", "confidence": 1.5}),
            "add": json.dumps({"summary": "test", "role": "utility", "confidence": -0.5}),
        })
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        aug.run()
        entries = aug.load_existing()
        for entry in entries.values():
            assert 0.0 <= entry.confidence <= 1.0

    def test_invalid_role_defaults_to_internal(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES[:3], SAMPLE_EDGES[:2])
        client = FakeLLMClient(responses={
            "hello": json.dumps({"summary": "test", "role": "invalid_role", "confidence": 0.8}),
        })
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        aug.run()
        entries = aug.load_existing()
        for entry in entries.values():
            assert entry.role in VALID_ROLES


# ── Tests: DeepAnalysisOrchestrator ───────────────────────────


class TestDeepAnalysisOrchestrator:
    def test_empty_queue_when_no_augmentations(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        orchestrator = DeepAnalysisOrchestrator(tmp_index, tmp_repo)
        queue = orchestrator.build_validation_queue()
        assert len(queue) == 0

    def test_queue_from_unvalidated_augmentations(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        # Write augmentations with varying confidence
        entries = [
            AugmentationEntry("node-sym-1", "high conf", "utility", 0.95, "2025-01-01", "m"),
            AugmentationEntry("node-sym-2", "low conf", "utility", 0.3, "2025-01-01", "m"),
            AugmentationEntry("node-sym-3", "med conf", "utility", 0.6, "2025-01-01", "m"),
        ]
        with open(tmp_index / "trace_augmented.jsonl", "w") as f:
            for e in entries:
                f.write(json.dumps(e.to_dict()) + "\n")

        orchestrator = DeepAnalysisOrchestrator(tmp_index, tmp_repo)
        queue = orchestrator.build_validation_queue()
        assert len(queue) == 3
        # Lowest confidence should be first (highest priority)
        assert queue[0].current_confidence == 0.3

    def test_queue_skips_validated(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        entries = [
            AugmentationEntry("node-sym-1", "validated", "utility", 0.95, "2025-01-01", "m", validated=True),
            AugmentationEntry("node-sym-2", "not validated", "utility", 0.3, "2025-01-01", "m"),
        ]
        with open(tmp_index / "trace_augmented.jsonl", "w") as f:
            for e in entries:
                f.write(json.dumps(e.to_dict()) + "\n")

        orchestrator = DeepAnalysisOrchestrator(tmp_index, tmp_repo)
        queue = orchestrator.build_validation_queue()
        assert len(queue) == 1
        assert queue[0].node_id == "node-sym-2"

    def test_run_validates_items(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        entries = [
            AugmentationEntry("node-sym-1", "says hello", "utility", 0.4, "2025-01-01", "m"),
            AugmentationEntry("node-sym-2", "adds numbers", "utility", 0.3, "2025-01-01", "m"),
        ]
        with open(tmp_index / "trace_augmented.jsonl", "w") as f:
            for e in entries:
                f.write(json.dumps(e.to_dict()) + "\n")

        client = FakeLLMClient(responses={
            "hello": json.dumps({"verdict": "confirmed", "summary": "says hello", "confidence": 0.92, "reasoning": "correct"}),
            "add": json.dumps({"verdict": "corrected", "summary": "adds two numbers together", "confidence": 0.88, "reasoning": "more specific"}),
        })

        schedule = DeepAnalysisSchedule(budget_max_items=10)
        orchestrator = DeepAnalysisOrchestrator(tmp_index, tmp_repo, schedule)
        result = orchestrator.run(llm_client=client)

        assert result.items_validated == 2
        assert result.items_confirmed >= 1
        assert result.items_corrected >= 0

    def test_budget_limits_items(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        entries = [
            AugmentationEntry("node-sym-1", "a", "utility", 0.3, "2025-01-01", "m"),
            AugmentationEntry("node-sym-2", "b", "utility", 0.4, "2025-01-01", "m"),
            AugmentationEntry("node-sym-3", "c", "utility", 0.5, "2025-01-01", "m"),
        ]
        with open(tmp_index / "trace_augmented.jsonl", "w") as f:
            for e in entries:
                f.write(json.dumps(e.to_dict()) + "\n")

        client = FakeLLMClient()
        schedule = DeepAnalysisSchedule(budget_max_items=1)
        orchestrator = DeepAnalysisOrchestrator(tmp_index, tmp_repo, schedule)
        result = orchestrator.run(llm_client=client)
        assert result.items_validated <= 1

    def test_status_empty(self, tmp_index, tmp_repo):
        orchestrator = DeepAnalysisOrchestrator(tmp_index, tmp_repo)
        s = orchestrator.status()
        assert s["queue_size"] == 0
        assert s["running"] is False

    def test_schedule_round_trip(self):
        s = DeepAnalysisSchedule(
            mode="scheduled",
            frequency="weekly",
            day_of_week=3,
            hour=14,
            budget_max_tokens=100_000,
        )
        d = s.to_dict()
        restored = DeepAnalysisSchedule.from_dict(d)
        assert restored.mode == "scheduled"
        assert restored.frequency == "weekly"
        assert restored.day_of_week == 3
        assert restored.hour == 14
        assert restored.budget_max_tokens == 100_000

    def test_connectivity_priority(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        entries = [
            AugmentationEntry("node-sym-1", "a", "utility", 0.8, "2025-01-01", "m"),
            AugmentationEntry("node-sym-2", "b", "utility", 0.3, "2025-01-01", "m"),
        ]
        with open(tmp_index / "trace_augmented.jsonl", "w") as f:
            for e in entries:
                f.write(json.dumps(e.to_dict()) + "\n")

        schedule = DeepAnalysisSchedule(priority="highest_connectivity")
        orchestrator = DeepAnalysisOrchestrator(tmp_index, tmp_repo, schedule)
        queue = orchestrator.build_validation_queue()
        # With connectivity priority, order depends on edge count not confidence
        assert len(queue) == 2


# ── Tests: LLMClient ──────────────────────────────────────────


class TestLLMClient:
    def test_is_available_offline(self):
        client = LLMClient("http://localhost:99999", "test")
        assert client.is_available() is False
