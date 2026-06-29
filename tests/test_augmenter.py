"""Tests for TraceAugmenter and DeepAnalysisOrchestrator."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from prep.core.augmenter import (
    AugmentationEntry,
    AugmentResult,
    TraceAugmenter,
    VALID_ROLES,
)
from prep.core.llm_client import LLMClient, _parse_json_response
from prep.core.deep_analysis import (
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
        self.provider = "ollama"
        self.timeout = 30.0
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

    def test_truncated_mid_key(self):
        """Truncation mid-key name (e.g. "related_f" cut off) — exact pattern from dashboard logs."""
        text = '{"summary": "Displays download options.", "role": "ui", "confidence": 0.95, "key_exports": [], "related_f'
        result = _parse_json_response(text)
        assert result is not None
        assert result["summary"] == "Displays download options."
        assert result["role"] == "ui"
        assert result["confidence"] == 0.95
        assert result["key_exports"] == []

    def test_truncated_mid_array_string(self):
        """Truncation inside a string within an array (e.g. related_files list)."""
        text = '{"summary": "Test.", "role": "ui", "confidence": 0.95, "key_exports": [], "related_files": ["path/to/file.tsx", "path/to/ano'
        result = _parse_json_response(text)
        assert result is not None
        assert result["summary"] == "Test."
        # Should recover at least the first array element or drop the incomplete array
        assert "role" in result

    def test_truncated_after_complete_array_element(self):
        """Truncation after a complete string in an array but before closing bracket."""
        text = '{"summary": "Test.", "role": "ui", "confidence": 0.95, "related_files": ["path/to/file.tsx"'
        result = _parse_json_response(text)
        assert result is not None
        assert result["summary"] == "Test."

    def test_truncated_mid_value_string(self):
        """Truncation mid-value in a string field."""
        text = '{"summary": "This is a very long summary that gets tru'
        result = _parse_json_response(text)
        assert result is not None
        assert "summary" in result

    def test_truncated_with_brace_inside_string(self):
        """A } exists inside a string value but isn't structural — should still repair."""
        text = '{"summary": "Returns {value} from config", "role": "utility", "confidence": 0.9, "related_fi'
        result = _parse_json_response(text)
        assert result is not None
        assert result["role"] == "utility"

    def test_truncated_complete_except_closing_brace(self):
        """All fields present but missing the final }."""
        text = '{"summary": "Test.", "role": "ui", "confidence": 0.95'
        result = _parse_json_response(text)
        assert result is not None
        assert result["confidence"] == 0.95


# ── Tests: AugmentationEntry ──────────────────────────────────


class TestAugmentationEntry:
    def test_round_trip(self):
        # Phase 134: file_hash field deleted — entry no longer carries it.
        entry = AugmentationEntry(
            node_id="node-1",
            summary="Does something",
            role="utility",
            confidence=0.85,
            augmented_at="2025-02-11T00:00:00Z",
            model="test",
        )
        d = entry.to_dict()
        restored = AugmentationEntry.from_dict(d)
        assert restored.node_id == "node-1"
        assert restored.summary == "Does something"
        assert restored.confidence == 0.85
        # Verify old JSON with a hash key loads cleanly (key silently ignored).
        legacy_dict = {**d, "file_hash": "legacy_abc123"}
        restored_legacy = AugmentationEntry.from_dict(legacy_dict)
        assert restored_legacy.node_id == "node-1"

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
        # Batched mode requires an explicit batch_profile; without it
        # `use_batching=False` at augmenter.py:1818 routes to the legacy
        # non-batched paths that don't hit the narrative branch at all.
        from prep.core.batch_profiles import PROFILE_CLOUD_SMALL
        aug = TraceAugmenter(
            tmp_index, tmp_repo, client, batch_profile=PROFILE_CLOUD_SMALL,
        )
        aug.run()
        assert (tmp_index / "trace_augmented.jsonl").exists()
        assert (tmp_index / "trace_augment_manifest.json").exists()

    def test_incremental_skips_unchanged(self, tmp_index, tmp_repo):
        """Phase 134: incremental skipping is now changeset-driven, not
        hash-driven. When the injected changeset marks all files unchanged,
        nodes with existing entries are skipped."""
        from prep.services.pipeline.changeset import Changeset

        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)

        # First run: no changeset (process-all mode) — augments everything
        r1 = aug.run()
        assert r1.augmented > 0

        # Second run: changeset says all files are unchanged → all nodes skipped.
        client.calls.clear()
        aug2 = TraceAugmenter(tmp_index, tmp_repo, client)
        # Mark all files as unchanged — no new, no modified
        all_paths = {n.get("file_path", "") for n in SAMPLE_NODES if n.get("file_path")}
        aug2.changeset = Changeset(
            added=frozenset(),
            modified=frozenset(),
            deleted=frozenset(),
            unchanged=frozenset(all_paths),
            run_id="r2",
            base_run_id="r1",
        )
        r2 = aug2.run()
        assert r2.skipped > 0
        # Only the pre-flight LLM check fires — no augmentation calls
        assert len(client.calls) <= 1

    def test_max_items_limit(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        result = aug.run(max_items=1)
        assert result.augmented <= 1

    def test_handles_llm_failure(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES[:3], SAMPLE_EDGES[:2])

        class FailingClient(FakeLLMClient):
            """Passes pre-flight but fails on actual augmentation calls."""
            def __init__(self):
                super().__init__()
                self._call_count = 0

            def generate(self, prompt, system=None, **kwargs):
                self._call_count += 1
                if self._call_count == 1:  # pre-flight
                    return '{"ok":true}', 10
                raise ConnectionError("LLM down")

        client = FailingClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        result = aug.run()
        # LLM failures now produce synthetic entries instead of counting as "failed"
        assert result.augmented == 0
        assert (result.failed + result.synthetic) > 0

    def test_handles_bad_json_response(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES[:3], SAMPLE_EDGES[:2])

        class BadJsonClient(FakeLLMClient):
            """Passes pre-flight but returns bad JSON for augmentation calls."""
            def __init__(self):
                super().__init__()
                self._call_count = 0

            def generate(self, prompt, system=None, **kwargs):
                self._call_count += 1
                if self._call_count == 1:  # pre-flight
                    return '{"ok":true}', 10
                return "I don't know how to respond in JSON", 50

        client = BadJsonClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        result = aug.run()
        # Bad JSON responses now produce synthetic fallback entries
        assert (result.failed + result.synthetic) > 0

    def test_status_no_augmentation(self, tmp_index, tmp_repo):
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        s = aug.status()
        assert s["enabled"] is False
        assert s["augmented_nodes"] == 0

    def test_status_after_run(self, tmp_index, tmp_repo):
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        client = FakeLLMClient()
        # Batched mode requires an explicit batch_profile; without it
        # `use_batching=False` at augmenter.py:1818 routes to the legacy
        # non-batched paths that don't hit the narrative branch at all.
        from prep.core.batch_profiles import PROFILE_CLOUD_SMALL
        aug = TraceAugmenter(
            tmp_index, tmp_repo, client, batch_profile=PROFILE_CLOUD_SMALL,
        )
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

    # ── §9.3 #32 regression — PR-P fix ────────────────────────
    # The 7812/142 → 5501% production case was caused by the v1 manifest
    # writer using two different denominators: `counts.total_nodes` was
    # `result.total_nodes - result.skipped` (which by substitution equals
    # `total_work` — this-run scope), while `counts.augmented` was
    # `len(entries)` (cumulative project-wide from `load_existing()`).
    # PR-P adds `AugmentResult.project_augmentable_count` set in `run()`
    # to `len(symbol_nodes) + len(file_nodes)` and uses it as the manifest
    # denominator so numerator and denominator share project-wide scope.
    # See FINDING_catalogue-augmented-vs-total-semantic-mismatch.md.

    def test_run_sets_project_augmentable_count(self, tmp_index, tmp_repo):
        """run() must populate result.project_augmentable_count with the
        project-wide count of augmentable-kind nodes (symbol + file)."""
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)
        result = aug.run()
        expected = sum(
            1 for n in SAMPLE_NODES if n.get("kind") in ("symbol", "file")
        )
        assert result.project_augmentable_count == expected

    def test_manifest_total_nodes_never_smaller_than_augmented_count(
        self, tmp_index, tmp_repo,
    ):
        """§9.3 #32 invariant: counts.augmented MUST NOT exceed
        counts.total_nodes in the v1 manifest. Direct repro of the
        incremental-no-op + cumulative-entries scenario that produced
        the 5501% chip in production.
        """
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)

        augmentable = [
            n for n in SAMPLE_NODES if n.get("kind") in ("symbol", "file")
        ]
        # Simulate the no-op-incremental result: all nodes already
        # processed this run (so result.skipped == result.total_nodes,
        # making the old `total_nodes - skipped` formula collapse to 0).
        result = AugmentResult()
        result.total_nodes = len(SAMPLE_NODES)
        result.skipped = result.total_nodes
        result.project_augmentable_count = len(augmentable)

        # Cumulative entries: current augmentable PLUS orphan entries from
        # prior runs (typical cause: files renamed/deleted but their old
        # entries still live in trace_augmented.jsonl, since the augmenter
        # never reaps orphans).
        entries = {}
        for n in augmentable:
            entries[n["id"]] = AugmentationEntry(
                node_id=n["id"], summary="x", role="utility",
                confidence=0.9, augmented_at="2025-01-01", model="m",
            )
        for i in range(50):
            entries[f"orphan-symbol-{i}"] = AugmentationEntry(
                node_id=f"orphan-symbol-{i}", summary="x", role="utility",
                confidence=0.9, augmented_at="2025-01-01", model="m",
            )

        # PR-P run() passes set(nodes_by_id.keys()) as valid_node_ids so
        # orphan entries don't inflate the numerator past the denominator.
        valid_ids = {n["id"] for n in SAMPLE_NODES}
        aug._write_manifest(result, entries, valid_node_ids=valid_ids)
        s = aug.status()

        # The §9.3 #32 invariant: numerator cannot exceed denominator.
        # Pre-PR-P this assertion failed with augmented_nodes=55 and
        # total_nodes=0 (the 5501% chip class — formally undefined but
        # rendering as the unclamped ratio).
        assert s["enabled"] is True
        assert s["augmented_nodes"] <= s["total_nodes"], (
            f"§9.3 #32: augmented_nodes ({s['augmented_nodes']}) > "
            f"total_nodes ({s['total_nodes']}) — the 5501% chip bug "
            f"class is back. _write_manifest must use "
            f"result.project_augmentable_count "
            f"({len(augmentable)}) as the denominator AND must filter "
            f"entries against valid_node_ids."
        )
        # Denominator must be project-wide augmentable count.
        assert s["total_nodes"] == len(augmentable)
        # Numerator must exclude orphans (50 of 55 entries are orphans).
        assert s["augmented_nodes"] == len(augmentable)

    def test_manifest_falls_back_to_old_denominator_when_field_unset(
        self, tmp_index, tmp_repo,
    ):
        """Backwards-compat: callers constructing AugmentResult outside
        run() (e.g. older tests, dataclass(**dict) restoration) leave
        project_augmentable_count at its default 0. _write_manifest must
        fall back to the pre-PR-P denominator formula in that case so
        existing callers don't see surprise zero-denominator manifests.
        PR-P-fixup: also asserts the warning fires so a future regression
        that drops project_augmentable_count from run() leaves a log trail."""
        import logging
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)

        # Old-style AugmentResult: project_augmentable_count left at 0.
        result = AugmentResult()
        result.total_nodes = 10
        result.skipped = 3  # → augmentable_nodes = 10 - 3 = 7
        # (project_augmentable_count defaults to 0 → fallback path)

        with self._captured_logs("prep.core.augmenter", logging.WARNING) as caplog:
            aug._write_manifest(result, {})
        s = aug.status()
        # Old formula: total_nodes - skipped = 7
        assert s["total_nodes"] == 7
        # Fallback warning fired so a regression that drops field-population
        # from run() leaves a visible trail in daemon logs.
        assert any("§9.3 #32 fallback" in r.getMessage() for r in caplog), (
            "PR-P-fixup: fallback path must log a warning when "
            "project_augmentable_count is 0 with total_nodes > 0"
        )

    @staticmethod
    def _captured_logs(logger_name: str, level: int):
        """Tiny inline context manager replacement for pytest's caplog —
        keeps test code self-contained without adding new fixtures."""
        import logging
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            records: list[logging.LogRecord] = []
            handler = logging.Handler(level=level)
            handler.emit = records.append  # type: ignore[assignment]
            logger = logging.getLogger(logger_name)
            prev_level = logger.level
            logger.addHandler(handler)
            logger.setLevel(level)
            try:
                yield records
            finally:
                logger.removeHandler(handler)
                logger.setLevel(prev_level)

        return _ctx()

    def test_manifest_v2_write_preserves_v1_counts_for_pipeline_mode(
        self, tmp_index, tmp_repo,
    ):
        """§9.3 #32 INTEGRATION (PR-P-fixup, addresses scrutiny XPR-005 +
        SCR-PRP-001): the orchestrator's v2 manifest write at
        `_write_stage_manifest_and_update_run` goes through
        `ManifestStore.write_provenance` and targets the SAME file as
        TraceAugmenter._write_manifest. Pre-fixup that write was a plain
        atomic overwrite for non-STRUCTURAL stages, so PR-P's v1
        counts/stats block was clobbered milliseconds after being written
        and `augmenter.status()` fell back to v2's quality block (which
        has different semantics — per-jsonl-line counts that round to
        ~100%). The chip's 5501% protection lived ONLY in PR-D's
        rendering-side Math.min clamp.

        PR-P-fixup extends the STRUCTURAL merge pattern to CATALOGUE so
        the v1 counts/stats survive the v2 write. This test simulates
        the pipeline-driven sequence (augmenter writes v1, orchestrator
        writes v2) and asserts the §9.3 #32 invariant survives.
        """
        from prep.services.pipeline.manifest_store import ManifestStore
        from prep.services.pipeline.stages import StageId

        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)

        # Step 1 — augmenter writes v1 manifest with PR-P's coherent
        # counts (total_nodes = project augmentable count, augmented =
        # orphan-filtered cumulative count).
        aug.run()
        pre = json.loads((tmp_index / "trace_augment_manifest.json").read_text())
        assert "counts" in pre, "augmenter must write v1 counts block"
        pre_total = pre["counts"]["total_nodes"]
        pre_augmented = pre["counts"]["augmented"]
        assert pre_total > 0
        assert pre_augmented <= pre_total, (
            "PR-P precondition: v1 manifest must already satisfy the §9.3 "
            "#32 invariant before the v2 write."
        )

        # Step 2 — simulate the orchestrator's v2 write. Mirrors what
        # `_write_stage_manifest_and_update_run` does at
        # orchestrator.py:4535+ for the catalogue stage — a stage manifest
        # blob with quality / output_files / model / timing but NO counts
        # / stats keys.
        #
        # PR-P-fixup-r2 (scrutiny PRP-INT-001): make the v2 quality block
        # DELIBERATELY DIVERGENT (processed > total_items, mirroring the
        # §9.3 #32 ratio inversion). Pre-fixup, status() would fall back
        # to this block and return augmented_nodes=200 against
        # total_nodes=2 → invariant FAILS. The original equal-values
        # block produced a coherent ratio under the bug, making the
        # invariant assertion non-load-bearing; with this divergent block
        # the integration assertion at Step 4 now actually bites.
        store = ManifestStore(tmp_index)
        v2_blob: Dict[str, Any] = {
            "stage_id": "catalogue",
            "run_id": "test-pipeline-run-1",
            "project_id": "test-project",
            "started_at": "2026-06-25T00:00:00Z",
            "finished_at": "2026-06-25T00:00:01Z",
            "elapsed_seconds": 1.0,
            "model": {"provider": "ollama", "model_name": "test-model"},
            "quality": {
                # Divergent on purpose: processed dwarfs total_items —
                # the §9.3 #32 inversion the augmenter's v1 numerator
                # used to produce. If the CATALOGUE merge is reverted,
                # status() falls back to v2 and returns the inverted
                # ratio (200 augmented / 2 total) → invariant FAILS.
                "total_items": 2,
                "processed": 200,
                "skipped": 0,
                "failed": 0,
                "success_rate": 1.0,
                "avg_confidence": 0.85,
            },
            "output_files": {"trace_augmented.jsonl": {"size_bytes": 1024}},
        }
        store.write_provenance(StageId.CATALOGUE, v2_blob)

        # Step 3 — pre-fixup, the v1 counts would be GONE here. PR-P-fixup
        # preserves them via the merge pattern from STRUCTURAL.
        post = json.loads((tmp_index / "trace_augment_manifest.json").read_text())
        assert "counts" in post, (
            "PR-P-fixup regression: v2 write clobbered v1 counts block. "
            "ManifestStore.write_provenance(StageId.CATALOGUE, ...) must "
            "preserve the v1 counts/stats keys (matches STRUCTURAL pattern)."
        )
        assert post["counts"]["total_nodes"] == pre_total
        assert post["counts"]["augmented"] == pre_augmented
        # v2 fields also present.
        assert "quality" in post
        assert "stage_id" in post

        # Step 4 — augmenter.status() reads v1 first (line 2211 check on
        # counts.total_nodes / counts.augmented). With the merge, v1 wins
        # → §9.3 #32 invariant holds.
        s = aug.status()
        assert s["enabled"] is True
        assert s["augmented_nodes"] <= s["total_nodes"], (
            f"§9.3 #32 integration regression: augmented_nodes "
            f"({s['augmented_nodes']}) > total_nodes ({s['total_nodes']}) "
            "after the v2 manifest write. The merge-preservation in "
            "ManifestStore.write_provenance must keep v1 counts/stats so "
            "PR-P's fix survives the pipeline write sequence."
        )
        assert s["total_nodes"] == pre_total
        assert s["augmented_nodes"] == pre_augmented

    def test_stage_manifest_to_dict_never_emits_v1_keys(self):
        """PR-P-fixup-r2 (scrutiny PRP-INT-003 + PRP-FXP-001): the
        ManifestStore CATALOGUE merge depends on the orchestrator's v2
        blob (constructed via StageManifest.to_dict()) NEVER emitting
        `counts`, `stats`, or `version` — because if it did, the merge
        contract `if key in existing and key not in data` would let the
        v2 blob's empty/default counts overwrite the augmenter's v1
        counts and the §9.3 #32 fix would silently revert.

        This guard pins the StageManifest contract so a future refactor
        that adds a `counts` / `stats` / `version` field to StageManifest
        (or its to_dict()) trips this test before reaching production.
        """
        from prep.core.stage_manifest import create_stage_manifest

        manifest = create_stage_manifest(
            stage_id="catalogue",
            run_id="r1",
            project_id="p1",
        )
        d = manifest.to_dict()

        # The actual v2 schema uses `format_version`, not `version`.
        # The merge preserves the v1 `version` key from the augmenter's
        # writer — that key must not collide with anything v2 emits.
        forbidden = {"counts", "stats", "version"}
        present = forbidden & set(d.keys())
        assert not present, (
            f"§9.3 #32 contract regression: StageManifest.to_dict() "
            f"emitted keys {present} which collide with the v1 manifest "
            "keys the ManifestStore CATALOGUE merge preserves. The merge "
            "would now let v2's value overwrite v1's, re-introducing the "
            "5501% chip class. Either remove those fields from "
            "StageManifest, or update preserved_keys in manifest_store.py "
            "to drop the colliding name."
        )

    def test_manifest_v2_write_via_real_stagemanifest_preserves_v1_counts(
        self, tmp_index, tmp_repo,
    ):
        """PR-P-fixup-r2 (scrutiny PRP-FXP-001): the existing pipeline
        integration test hand-rolls a v2_blob dict. This sibling test
        uses the REAL `create_stage_manifest().to_dict()` output that
        the orchestrator actually writes via
        `_write_stage_manifest_and_update_run`. Catches structural
        drift in StageManifest that the hand-rolled blob misses (e.g.
        future fields named in a way that collides with v1).
        """
        from prep.core.stage_manifest import create_stage_manifest
        from prep.services.pipeline.manifest_store import ManifestStore
        from prep.services.pipeline.stages import StageId

        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)

        # v1 first.
        aug.run()
        pre = json.loads((tmp_index / "trace_augment_manifest.json").read_text())
        pre_total = pre["counts"]["total_nodes"]
        pre_augmented = pre["counts"]["augmented"]

        # v2 via the real factory.
        manifest = create_stage_manifest(
            stage_id="catalogue", run_id="r1", project_id="p1",
        )
        manifest.quality = {
            # Deliberately divergent — see test_manifest_v2_write_...
            "total_items": 2,
            "processed": 200,
            "skipped": 0,
            "failed": 0,
            "success_rate": 1.0,
            "avg_confidence": 0.85,
        }
        manifest.output_files = {"trace_augmented.jsonl": {"size_bytes": 1024}}
        v2_blob = manifest.to_dict()

        store = ManifestStore(tmp_index)
        store.write_provenance(StageId.CATALOGUE, v2_blob)

        # v1 counts must survive the real-shape v2 write.
        post = json.loads((tmp_index / "trace_augment_manifest.json").read_text())
        assert "counts" in post
        assert post["counts"]["total_nodes"] == pre_total
        assert post["counts"]["augmented"] == pre_augmented
        # v2 fields also present.
        assert post.get("format_version") == "2.0"
        assert post.get("stage_id") == "catalogue"

        # status() resolves to v1's coherent counts, not v2's inverted ratio.
        s = aug.status()
        assert s["enabled"] is True
        assert s["augmented_nodes"] <= s["total_nodes"]
        assert s["total_nodes"] == pre_total
        assert s["augmented_nodes"] == pre_augmented
        # PR-P-fixup-r2 (PRP-FIX-001): built_at + model also survive the
        # v2 merge — last_augment_at no longer silently nulled.
        assert s["last_augment_at"] is not None, (
            "PRP-FIX-001 regression: built_at must be in preserved_keys "
            "so status()['last_augment_at'] survives the v2 write."
        )

    def test_orphan_filter_excludes_non_augmentable_kind_entries(
        self, tmp_index, tmp_repo,
    ):
        """PR-P-fixup-r2 (scrutiny R-AUG-003 + retro SCR-PRP-004):
        SAMPLE_NODES contains only symbol/file kinds; pre-fixup,
        valid_node_ids was `set(nodes_by_id.keys())` so this test could
        not have detected a regression in the kind-filter tightening.
        This test adds an external_module trace node + an on-disk
        AugmentationEntry whose node_id matches it, then runs the
        augmenter and asserts:
          (a) counts.augmented EXCLUDES the external_module entry
              (orphan filter uses {symbol, file} only, not all kinds),
          (b) counts.total_nodes is the symbol+file count, not the
              all-kinds total_nodes from trace.
        If someone reverts run()'s call-site to pass `set(nodes_by_id.
        keys())` (the pre-fixup form), the external_module entry would
        pass the filter and counts.augmented would equal pre+1.
        """
        # Add an external_module node to SAMPLE_NODES for this test.
        nodes_with_ext = list(SAMPLE_NODES) + [
            {
                "id": "ext:os",
                "kind": "external_module",
                "name": "os",
                "file_path": None,
                "span": None,
                "language": "python",
                "metadata": {},
            },
        ]
        _write_trace(tmp_index, nodes_with_ext, SAMPLE_EDGES)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)

        # Seed an existing augmentation for the external_module node so
        # the on-disk JSONL has an entry whose id matches a node but
        # whose kind is NOT augmentable. This is the SCR-PRP-004 attack
        # shape: an entry that would survive the unfiltered orphan
        # filter `set(nodes_by_id.keys())` but must be rejected by the
        # tightened `augmentable_ids` filter.
        seed_entry = AugmentationEntry(
            node_id="ext:os", summary="x", role="utility",
            confidence=0.9, augmented_at="2025-01-01", model="m",
        )
        with open(tmp_index / "trace_augmented.jsonl", "w") as f:
            f.write(json.dumps(seed_entry.to_dict()) + "\n")

        aug.run()
        s = aug.status()

        # Denominator must be the kind-filtered project augmentable count
        # (symbol + file kinds only, NOT the all-kinds trace node count).
        augmentable_count = sum(
            1 for n in nodes_with_ext if n.get("kind") in ("symbol", "file")
        )
        assert s["total_nodes"] == augmentable_count, (
            f"§9.3 #32 denominator regression: total_nodes "
            f"({s['total_nodes']}) should be the project augmentable "
            f"count ({augmentable_count}), not the all-kinds trace total."
        )

        # Numerator must exclude the external_module entry — and must
        # not exceed the denominator regardless.
        assert s["augmented_nodes"] <= s["total_nodes"], (
            "SCR-PRP-004 regression: orphan filter let a non-augmentable-"
            "kind entry through, inflating counts.augmented past "
            "counts.total_nodes. run() must pass valid_node_ids filtered "
            "to {symbol, file} kinds — NOT set(nodes_by_id.keys())."
        )

    def test_manifest_production_like_scenario_5501_class(
        self, tmp_index, tmp_repo,
    ):
        """§9.3 #32 (PR-P-fixup, addresses scrutiny SCR-PRP-005): mirror
        the actual 7812/142 production ratio rather than the degenerate
        ÷0 case the original PR-P test used. Many cumulative entries
        (mostly orphans) against a small this-run scope reproduces the
        ratio that hit the dashboard in real life.
        """
        _write_trace(tmp_index, SAMPLE_NODES, SAMPLE_EDGES)
        client = FakeLLMClient()
        aug = TraceAugmenter(tmp_index, tmp_repo, client)

        augmentable = [
            n for n in SAMPLE_NODES if n.get("kind") in ("symbol", "file")
        ]
        n_augmentable = len(augmentable)

        # 100 entries on disk — close mix of valid + orphan, similar
        # ratio to the 7812/142 production case where most cumulative
        # entries point at past-project state. 5 valid (one per current
        # augmentable node) + 95 orphans → pre-PR-P ratio would have
        # been ~100/142 against a small this-run skipped scope.
        entries = {}
        for n in augmentable:
            entries[n["id"]] = AugmentationEntry(
                node_id=n["id"], summary="x", role="utility",
                confidence=0.9, augmented_at="2025-01-01", model="m",
            )
        for i in range(95):
            entries[f"deleted-orphan-{i}"] = AugmentationEntry(
                node_id=f"deleted-orphan-{i}", summary="x", role="utility",
                confidence=0.9, augmented_at="2025-01-01", model="m",
            )

        # Production-like result shape: incremental run with small
        # this-run scope. PR-P's run() would set
        # project_augmentable_count = n_augmentable for this scenario.
        result = AugmentResult()
        result.total_nodes = len(SAMPLE_NODES)
        # Small this-run work (mimics 142-style narrow scope): only 1
        # node needed re-augmentation in this incremental.
        total_work = 1
        result.skipped = result.total_nodes - total_work
        result.project_augmentable_count = n_augmentable

        # Pre-PR-P formula reconstruction (for comparison only):
        pre_pr_p_total = result.total_nodes - result.skipped  # == total_work == 1
        pre_pr_p_augmented = len(entries)  # == 100
        pre_pr_p_ratio_pct = (pre_pr_p_augmented / pre_pr_p_total) * 100
        assert pre_pr_p_ratio_pct >= 1000, (
            "Sanity: the pre-PR-P formula must reproduce a chip ratio "
            "well above 100% on this fixture so the regression test "
            "genuinely models the 5501% class. Got "
            f"{pre_pr_p_ratio_pct:.0f}%."
        )

        valid_ids = {n["id"] for n in augmentable}
        aug._write_manifest(result, entries, valid_node_ids=valid_ids)
        s = aug.status()

        # The PR-P invariant must hold under the production-like ratio.
        assert s["augmented_nodes"] <= s["total_nodes"], (
            f"§9.3 #32 production-class regression: augmented_nodes "
            f"({s['augmented_nodes']}) > total_nodes ({s['total_nodes']}). "
            f"Pre-fix this fixture would have produced "
            f"{pre_pr_p_ratio_pct:.0f}% — the 5501% bug class."
        )
        # Numerator drops orphans (95 of 100 entries are orphans).
        assert s["augmented_nodes"] == n_augmentable
        # Denominator is project-wide, not this-run scope.
        assert s["total_nodes"] == n_augmentable


class TestNarrativeConcurrency:
    """2026-05-17 regression. Narrative-file augmentation used to be a
    plain `for item in narrative_items:` loop (1x sequential) while the
    structured-code and structured-docs paths fan out at `_concurrency`
    (10x typical). On SourcePrep this stage is 7000+ narrative files
    and the sequential loop dominates Fast Catalogue's wall time. The
    fix mirrors the code-batch ThreadPoolExecutor pattern."""

    def _make_narrative_repo(self, tmp_repo: Path, count: int) -> List[Dict]:
        nodes = []
        for i in range(count):
            rel = f"notes/note_{i:02d}.md"
            (tmp_repo / "notes").mkdir(exist_ok=True)
            # Pure prose (no frontmatter, no fenced code) — classified
            # as UNSTRUCTURED_NARRATIVE by classify_nodes.
            (tmp_repo / rel).write_text(
                f"# Note {i}\n\nThis is a paragraph of plain prose about "
                f"topic number {i}. It contains no code blocks and no "
                f"frontmatter, so the classifier routes it to the "
                f"narrative branch.\n"
            )
            nodes.append({
                "id": f"node-narr-{i}",
                "kind": "file",
                "name": f"note_{i:02d}.md",
                "file_path": rel,
                "span": None,
                "language": "markdown",
                "metadata": {},
            })
        return nodes

    def test_narrative_path_uses_thread_pool_when_concurrency_gt_1(
        self, tmp_index, tmp_repo, monkeypatch,
    ):
        """When `_concurrency > 1` and `narrative_items > 1`, the
        narrative branch must dispatch via ThreadPoolExecutor. Before
        the fix this assertion failed because the branch was a plain
        for-loop."""
        from concurrent.futures import ThreadPoolExecutor as _RealTPE

        nodes = self._make_narrative_repo(tmp_repo, count=4)
        _write_trace(tmp_index, nodes, [])

        # Pin batch concurrency at 10 — bypass scheduler probing.
        # The augmenter imports get_batch_concurrency inside the run()
        # function via `from .batch_profiles import get_batch_concurrency`,
        # so the patch target is the source module.
        monkeypatch.setattr(
            "prep.core.batch_profiles.get_batch_concurrency",
            lambda provider, **kw: 10,
        )

        instantiations: List[int] = []

        class _SpyTPE(_RealTPE):
            def __init__(self, max_workers=None, *a, **kw):
                instantiations.append(max_workers or 0)
                super().__init__(max_workers=max_workers, *a, **kw)

        monkeypatch.setattr("prep.core.augmenter.ThreadPoolExecutor", _SpyTPE)

        client = FakeLLMClient()
        # Batched mode requires an explicit batch_profile; without it
        # `use_batching=False` at augmenter.py:1818 routes to the legacy
        # non-batched paths that don't hit the narrative branch at all.
        from prep.core.batch_profiles import PROFILE_CLOUD_SMALL
        aug = TraceAugmenter(
            tmp_index, tmp_repo, client, batch_profile=PROFILE_CLOUD_SMALL,
        )
        aug.run()

        # The narrative path must have spawned a ThreadPoolExecutor with
        # max_workers == min(_concurrency, len(narrative_items)) == 4.
        # (Symbol and code/doc paths may also spawn pools — we just need
        # to confirm at least one pool was sized for the narrative items.)
        assert 4 in instantiations, (
            "narrative branch must use ThreadPoolExecutor when "
            f"narrative_items > 1 and _concurrency > 1; saw max_workers "
            f"instantiations={instantiations}"
        )

    def test_narrative_path_stays_sequential_for_single_item(
        self, tmp_index, tmp_repo, monkeypatch,
    ):
        """Single narrative item should NOT spawn a ThreadPoolExecutor
        for the narrative branch (overhead avoidance — matches the
        code-batch fast-path at augmenter.py:1402)."""
        from concurrent.futures import ThreadPoolExecutor as _RealTPE

        nodes = self._make_narrative_repo(tmp_repo, count=1)
        _write_trace(tmp_index, nodes, [])

        # The augmenter imports get_batch_concurrency inside the run()
        # function via `from .batch_profiles import get_batch_concurrency`,
        # so the patch target is the source module.
        monkeypatch.setattr(
            "prep.core.batch_profiles.get_batch_concurrency",
            lambda provider, **kw: 10,
        )

        narrative_sized_pools: List[int] = []

        class _SpyTPE(_RealTPE):
            def __init__(self, max_workers=None, *a, **kw):
                # We only care about the narrative-sized pool here.
                if max_workers == 1:
                    narrative_sized_pools.append(max_workers)
                super().__init__(max_workers=max_workers, *a, **kw)

        monkeypatch.setattr("prep.core.augmenter.ThreadPoolExecutor", _SpyTPE)

        client = FakeLLMClient()
        # Batched mode requires an explicit batch_profile; without it
        # `use_batching=False` at augmenter.py:1818 routes to the legacy
        # non-batched paths that don't hit the narrative branch at all.
        from prep.core.batch_profiles import PROFILE_CLOUD_SMALL
        aug = TraceAugmenter(
            tmp_index, tmp_repo, client, batch_profile=PROFILE_CLOUD_SMALL,
        )
        aug.run()

        assert not narrative_sized_pools, (
            "single narrative item must take the sequential fast-path, "
            f"not spawn a 1-worker pool; saw {narrative_sized_pools}"
        )


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
