"""Integration tests for the full Digital Custodian pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import pytest

from prep.agents.custodian import CustodianEngine, ArchiveManifest
from prep.agents.shared.models import CleanupPlan


def _fake_llm(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    if "safe to delete" in prompt.lower() or "reviewing a code file" in prompt.lower():
        return json.dumps({
            "classification": "SAFE_TO_DELETE",
            "reason": "Confirmed dead — no dynamic imports or config refs",
        }), 40
    return "ok", 10


def _findings():
    return [
        {"id": "ARCH-17", "title": "Orphaned fixture",
         "category": "dead_code", "priority": "P2",
         "affected_files": ["tests/old_fixture.py"],
         "description": "0 dependents"},
        {"id": "ARCH-22", "title": "Unused helpers",
         "category": "dead_code", "priority": "P2",
         "affected_files": ["src/utils/old.py"],
         "description": "Never imported"},
        {"id": "QUAL-5", "title": "Deprecated module",
         "category": "deprecated", "priority": "P3",
         "affected_files": ["src/legacy/auth_v1.py"],
         "description": "Replaced by auth_v2"},
        {"id": "SEC-1", "title": "Secret leak",
         "category": "security", "priority": "P0",
         "affected_files": ["config.py"],
         "description": "Not dead code"},
    ]


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    (tmp_path / "codebase_atlas.md").write_text("# Test")
    (tmp_path / "trace_modules.jsonl").write_text("")
    return tmp_path


class TestCustodianEndToEnd:
    def test_full_dry_run_pipeline(self, index_dir: Path) -> None:
        engine = CustodianEngine(index_dir=index_dir, project_id="test")

        plan = engine.run(findings=_findings(), llm_fn=_fake_llm)

        assert isinstance(plan, CleanupPlan)
        assert plan.dry_run is True
        # Should find 3 dead code files (not SEC-1)
        assert len(plan.candidates) == 3
        for c in plan.candidates:
            assert c.classification == "safe_to_delete"

    def test_push_packaging_end_to_end(self, index_dir: Path) -> None:
        engine = CustodianEngine(index_dir=index_dir, project_id="test")
        plan = engine.run(findings=_findings(), llm_fn=_fake_llm)

        project, _, issues = engine.package_for_push(plan)
        assert "Cleanup" in project.name
        assert len(issues) == 3

    def test_stage_by_stage(self, index_dir: Path) -> None:
        engine = CustodianEngine(index_dir=index_dir, project_id="test")

        # Stage 1: Discover
        candidates = engine.discover(_findings())
        assert len(candidates) == 3

        # Stage 2: Verify
        verified = engine.verify_candidates(candidates, _fake_llm)
        assert all(c.classification == "safe_to_delete" for c in verified)

        # Stage 3: Plan
        plan = engine.plan_cleanup(verified)
        assert len(plan.candidates) == 3
        assert plan.dry_run is True
