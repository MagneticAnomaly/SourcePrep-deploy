"""Tests: profile-keyed ENRICHMENT prompts (T-S2.2).

Acceptance:
* An sshd_config fixture under a system_config scope → CONFIG epistemic
  prompt selected; output describes controlled resources, not code-role
  architecture.
* A code-profile file (no profiled scope) → legacy EPISTEMIC_CODE_PROMPT
  unchanged.
* A reference-doc fixture under a prose_docs scope → REFDOC epistemic
  prompt (ships dormant in v1; the matrix turns enrichment off, but the
  prompt + dispatch path are exercised here directly).
"""
from __future__ import annotations

import json
from typing import Any, Optional, Tuple

import pytest

from prep.core.epistemic_enrichment import (
    EPISTEMIC_CONFIG_PROMPT,
    EPISTEMIC_CODE_PROMPT,
    EPISTEMIC_REFDOC_PROMPT,
    EpistemicEnricher,
)
from prep.core.pipeline_profiles import ProfileGate
from prep.core.scope_store import scope_store
from prep.services.pipeline.stages import StageId


class _CapturingLLM:
    model = "test-model"
    provider = "ollama"
    endpoint_url = "http://localhost"
    timeout = 1.0

    def __init__(self, response: str) -> None:
        self.response = response
        self.last_prompt: str = ""

    def generate(self, prompt: str, system: Optional[str] = None, **kw: Any) -> Tuple[str, int]:
        self.last_prompt = prompt
        return self.response, 10

    def is_available(self) -> bool:
        return True


def _make_enricher(tmp_path, llm, gate=None, project_id=None):
    enr = EpistemicEnricher(llm, tmp_path, tmp_path / "idx", project_id=project_id)
    enr.profile_gate = gate
    # Stub on-disk helpers so no files need to exist.
    enr._get_file_excerpt = lambda fp, max_lines=150: "stubbed content"
    enr._get_neighbor_context = lambda *a, **k: "(none)"
    enr._get_section_names = lambda *a, **k: []
    enr._get_reference_paths = lambda *a, **k: ([], [])
    return enr


def _file_node(fp: str, language: str = "") -> dict:
    return {"id": f"file:{fp}", "kind": "file", "file_path": fp, "language": language}


def test_system_config_uses_config_prompt(
    tmp_path, tmp_settings, dummy_project_in_registry
):
    pid = dummy_project_in_registry.id
    scope_store.create(
        pid, display_name="host", paths=["host/"], pipeline_profile="system_config"
    )
    llm = _CapturingLLM(json.dumps({
        "extended_summary": "Configures sshd: controls Port, PermitRootLogin, password auth. Resource: remote-login service.",
        "domain_tags": ["auth", "config:network"],
        "architecture_layer": "configuration",
        "subsystem": "sshd",
        "cross_references": [{"target": "host/etc/ssh/sshd_config.d/00.conf", "relationship": "overrides", "context": "drop-in"}],
        "tech_debt": [{"item": "PermitRootLogin default", "severity": "high", "context": "auth sensitivity"}],
        "staleness_risk": "low",
        "epistemic_confidence": 0.9,
    }))
    gate = ProfileGate(pid, StageId.ENRICHMENT)
    enr = _make_enricher(tmp_path, llm, gate=gate, project_id=pid)

    node = _file_node("host/etc/ssh/sshd_config")
    entry = enr.enrich_node(node, [], {}, {"file:host/etc/ssh/sshd_config": {"summary": "x", "role": "config"}}, {})

    assert entry is not None
    # The CONFIG prompt header is present in the captured prompt.
    assert "system configuration file" in llm.last_prompt.lower()
    assert entry.architecture_layer == "configuration"
    assert entry.doc_type is None  # config carries no doc_type
    # Controlled-resources output, not code-role (no design_patterns/subsystem
    # like "business_logic").
    assert "sshd" in entry.extended_summary


def test_code_profile_uses_code_prompt_unchanged(tmp_path):
    llm = _CapturingLLM(json.dumps({
        "extended_summary": "App entry point.",
        "domain_tags": ["core"],
        "architecture_layer": "business_logic",
        "epistemic_confidence": 0.8,
    }))
    enr = _make_enricher(tmp_path, llm)  # no gate → code default
    assert enr.profile_gate is None

    node = _file_node("src/app.py", language="python")
    entry = enr.enrich_node(node, [], {}, {"file:src/app.py": {"summary": "x", "role": "entry_point"}}, {})

    assert entry is not None
    assert "this code file" in llm.last_prompt  # EPISTEMIC_CODE_PROMPT header
    assert entry.architecture_layer == "business_logic"


def test_prose_docs_uses_refdoc_prompt(
    tmp_path, tmp_settings, dummy_project_in_registry
):
    pid = dummy_project_in_registry.id
    scope_store.create(
        pid, display_name="knowledge-linux", paths=["knowledge/linux/"], pipeline_profile="prose_docs"
    )
    llm = _CapturingLLM(json.dumps({
        "extended_summary": "Reference for sshd_config directives; platform linux.",
        "domain_tags": ["auth", "platform:linux"],
        "architecture_layer": "documentation",
        "doc_type": "man_page",
        "epistemic_confidence": 0.85,
    }))
    gate = ProfileGate(pid, StageId.ENRICHMENT)
    enr = _make_enricher(tmp_path, llm, gate=gate, project_id=pid)

    node = _file_node("knowledge/linux/man8/sshd_config.5", language="markdown")
    entry = enr.enrich_node(node, [], {}, {"file:knowledge/linux/man8/sshd_config.5": {"summary": "x", "doc_type": "man_page"}}, {})

    assert entry is not None
    assert "this reference document" in llm.last_prompt  # EPISTEMIC_REFDOC_PROMPT header
    assert entry.doc_type == "man_page"
    # REFDOC carries no decision_chains / doc_status.
    assert entry.decision_chains is None
    assert entry.doc_status is None
    assert "platform:linux" in entry.domain_tags