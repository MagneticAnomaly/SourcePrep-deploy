"""Tests for the per-swarm-execution JSONL event logger.

Phase 119 verbose-logging feature: every ``SwarmOrchestrator.execute()``
writes one JSONL file under ``<data_dir>/logs/swarm/`` so the user can
inspect after-the-fact what each swarm did.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from prep.core.swarm_event_logger import SwarmEventLogger
from prep.core.swarm_orchestrator import (
    SwarmOrchestrator,
    WorkItem,
)


# ---------------------------------------------------------------------------
# SwarmEventLogger unit tests
# ---------------------------------------------------------------------------


class TestSwarmEventLoggerUnit:
    def test_creates_jsonl_file_with_session_start(self, tmp_path: Path) -> None:
        log = SwarmEventLogger(
            run_id="abc12345xxxx",
            stage="concept_seeding",
            project_id="proj-1",
            log_dir=tmp_path / "swarm",
        )

        assert log.path is not None
        assert log.path.exists()
        # Filename embeds stage + short run_id so a directory listing
        # is identifiable without parsing the file contents.
        assert "concept_seeding" in log.path.name
        assert "abc12345" in log.path.name
        assert log.path.suffix == ".jsonl"

        records = _read_jsonl(log.path)
        assert len(records) == 1
        assert records[0]["kind"] == "session_start"
        assert records[0]["stage"] == "concept_seeding"
        assert records[0]["project_id"] == "proj-1"
        assert records[0]["run_id"] == "abc12345xxxx"

    def test_event_appends_with_elapsed_and_kind(self, tmp_path: Path) -> None:
        log = SwarmEventLogger(
            run_id="r0", stage="s0", project_id="p0",
            log_dir=tmp_path / "swarm",
        )
        log.event("custom_event", foo="bar", n=3)

        records = _read_jsonl(log.path)
        assert len(records) == 2
        assert records[1]["kind"] == "custom_event"
        assert records[1]["foo"] == "bar"
        assert records[1]["n"] == 3
        assert "ts" in records[1]
        assert "elapsed_s" in records[1]

    def test_phase_helpers_emit_expected_payload(self, tmp_path: Path) -> None:
        log = SwarmEventLogger(
            run_id="r1", stage="audit", project_id="p1",
            log_dir=tmp_path / "swarm",
        )
        log.phase_start("coordinator", model="kimi-k2.5:cloud", n_items=4)
        log.phase_end("coordinator", success=True, duration_s=1.234, tokens=987)
        log.worker_dispatch("w-0", "module:foo", "qwen3:14b", prompt_chars=512)
        log.worker_complete("w-0", success=True, duration_s=2.5,
                            response_chars=1024, parse_ok=True)
        log.parse_failure(where="worker:module:bar", raw_chars=200,
                          reason="json_parse_failed")
        log.session_end(success=True, summary={"workers_succeeded": 4})

        records = _read_jsonl(log.path)
        kinds = [r["kind"] for r in records]
        # Required event kinds called out in the spec
        expected_kinds = {
            "session_start",
            "phase_start",
            "phase_end",
            "worker_dispatch",
            "worker_complete",
            "parse_failure",
            "session_end",
        }
        assert expected_kinds.issubset(set(kinds))

        # phase_start/end carry phase + model
        ps = next(r for r in records if r["kind"] == "phase_start")
        assert ps["phase"] == "coordinator"
        assert ps["model"] == "kimi-k2.5:cloud"
        assert ps["n_items"] == 4

        # worker_complete carries parse_ok and duration
        wc = next(r for r in records if r["kind"] == "worker_complete")
        assert wc["parse_ok"] is True
        assert wc["duration_s"] == 2.5
        assert wc["response_chars"] == 1024

        # session_end carries the summary block
        se = next(r for r in records if r["kind"] == "session_end")
        assert se["success"] is True
        assert se["summary"]["workers_succeeded"] == 4

    def test_jsonl_file_is_well_formed(self, tmp_path: Path) -> None:
        """Every line must independently parse as JSON (file integrity)."""
        log = SwarmEventLogger(
            run_id="r2", stage="s2", project_id="p2",
            log_dir=tmp_path / "swarm",
        )
        for i in range(20):
            log.event("tick", i=i)

        text = log.path.read_text()
        lines = [line for line in text.splitlines() if line.strip()]
        for line in lines:
            obj = json.loads(line)  # raises if any line is malformed
            assert "kind" in obj
            assert "ts" in obj

    def test_write_failure_does_not_raise(self, tmp_path: Path) -> None:
        """A read-only or vanished log_dir must not crash the swarm."""
        log = SwarmEventLogger(
            run_id="r3", stage="s3", project_id="p3",
            log_dir=tmp_path / "swarm",
        )
        # Delete the file under the logger's feet, then make the dir
        # read-only so the next append fails.
        log.path.unlink()
        # We don't chmod — instead, monkey-patch _path to a definitely-bad
        # location to simulate a write error path.
        log._path = tmp_path / "does" / "not" / "exist" / "x.jsonl"
        # Should not raise
        log.event("after_failure", note="shouldn't crash")


# ---------------------------------------------------------------------------
# SwarmOrchestrator integration: end-to-end JSONL emission
# ---------------------------------------------------------------------------


class TestSwarmOrchestratorEventLogging:
    def test_simulated_swarm_emits_all_event_kinds(self, tmp_path: Path) -> None:
        """A mocked swarm execution writes a JSONL with every required kind."""
        items = [
            WorkItem(id=f"item-{i}", summary=f"sum-{i}", full_context=f"ctx-{i}")
            for i in range(3)
        ]

        coord_response = json.dumps({
            "assignments": [
                {"item_id": it.id,
                 "analysis_angle": "test angle",
                 "priority_concerns": ["a", "b"]}
                for it in items
            ]
        })
        synth_response = json.dumps({"summary": "ok"})

        # Coordinator + synthesis share the same LLM in this test.
        llm = MagicMock()
        llm.model = "test-model"
        # Sequence: 1 coordinator call, then 1 synthesis call.
        llm.generate.side_effect = [
            (coord_response, 100),
            (synth_response, 50),
        ]

        orch = SwarmOrchestrator(llm=llm, concurrency=2)

        def worker_fn(item, assignment):
            # First worker returns malformed JSON to exercise parse_failure.
            if item.id == "item-0":
                return "not json at all"
            return json.dumps({"ok": True, "id": item.id})

        log_dir = tmp_path / "swarm-logs"
        result = orch.execute(
            items=items,
            coordinator_prompt="Plan: {group_summaries}",
            worker_fn=worker_fn,
            synthesis_prompt="Synth: {worker_outputs}",
            run_id="run-abcdef123456",
            stage="concept_seeding",
            project_id="proj-xyz",
            log_dir=log_dir,
        )

        assert result is not None
        assert result.event_log_path is not None
        log_path = Path(result.event_log_path)
        assert log_path.exists()

        records = _read_jsonl(log_path)
        kinds = [r["kind"] for r in records]
        # All six required event kinds must be present:
        required = {
            "session_start",
            "phase_start",
            "phase_end",
            "worker_dispatch",
            "worker_complete",
            "parse_failure",   # item-0 returned non-JSON
            "session_end",
        }
        missing = required - set(kinds)
        assert not missing, (
            f"missing event kinds {missing} (got {sorted(set(kinds))})"
        )

        # session_end always last
        assert records[-1]["kind"] == "session_end"
        assert records[-1]["summary"]["total_items"] == 3

    def test_filename_layout(self, tmp_path: Path) -> None:
        """File name must encode timestamp + stage + short run_id."""
        items = [WorkItem(id="x", summary="s", full_context="c")]
        llm = MagicMock()
        llm.model = "m"
        llm.generate.side_effect = [
            (json.dumps({"assignments": []}), 10),  # coordinator
            (json.dumps({"ok": True}), 10),          # synthesis
        ]
        orch = SwarmOrchestrator(llm=llm)

        result = orch.execute(
            items=items,
            coordinator_prompt="{group_summaries}",
            worker_fn=lambda it, a: json.dumps({"ok": True}),
            synthesis_prompt="{worker_outputs}",
            run_id="deadbeefcafe",
            stage="audit_swarm",
            project_id="p",
            log_dir=tmp_path / "logs",
        )

        assert result is not None
        assert result.event_log_path is not None
        name = Path(result.event_log_path).name
        assert "audit_swarm" in name
        assert "deadbeef" in name  # short run_id (first 8 chars)
        assert name.endswith(".jsonl")

    def test_disable_event_log(self, tmp_path: Path) -> None:
        """enable_event_log=False produces no file and no event_log_path."""
        items = [WorkItem(id="x", summary="s", full_context="c")]
        llm = MagicMock()
        llm.model = "m"
        llm.generate.side_effect = [
            (json.dumps({"assignments": []}), 1),
            (json.dumps({"ok": True}), 1),
        ]
        orch = SwarmOrchestrator(llm=llm)

        result = orch.execute(
            items=items,
            coordinator_prompt="{group_summaries}",
            worker_fn=lambda it, a: json.dumps({"ok": True}),
            synthesis_prompt="{worker_outputs}",
            log_dir=tmp_path / "logs",
            enable_event_log=False,
        )

        assert result is not None
        assert result.event_log_path is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# Allow `pytest -k swarm_event` to pick this file up explicitly.
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
