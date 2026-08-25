"""Tests: profile-keyed CATALOGUE prompts (T-S2.1).

Acceptance from IMPLEMENTATION-PLAN-SOURCEPREP-TEMPLATE-2026-08-24.md:

* A man page fixture under a prose_docs scope → REFDOC prompt selected,
  doc_type="man_page", no doc_status field.
* An sshd_config fixture under a system_config scope → CONFIG prompt
  selected, a config-role summary.
* A code-profile markdown file (no profiled scope) → legacy DOC prompt
  unchanged (doc_type/doc_status from the project-doc taxonomy).
"""
from __future__ import annotations

import json
from typing import Any, Optional, Tuple

import pytest

from prep.core.augmenter import (
    CONFIG_ROLE_SYSTEM,
    DOC_ROLE_SYSTEM,
    REFDOC_ROLE_SYSTEM,
    TraceAugmenter,
)
from prep.core.pipeline_profiles import ProfileGate
from prep.core.scope_store import scope_store
from prep.services.pipeline.stages import StageId


class _CapturingLLM:
    """Records the system prompt used and returns a canned JSON response."""

    model = "test-model"
    provider = "ollama"
    endpoint_url = "http://localhost"
    timeout = 1.0

    def __init__(self, response: str) -> None:
        self.response = response
        self.last_system: Optional[str] = None
        self.last_prompt: str = ""

    def generate(self, prompt: str, system: Optional[str] = None, **kw: Any) -> Tuple[str, int]:
        self.last_system = system
        self.last_prompt = prompt
        return self.response, 10

    def is_available(self) -> bool:
        return True


def _file_node(fp: str, language: str = "") -> dict:
    return {
        "id": f"file:{fp}",
        "kind": "file",
        "file_path": fp,
        "language": language,
        "metadata": {"line_count": 10},
    }


def _make_augmenter(tmp_path, llm, gate=None, project_id=None):
    aug = TraceAugmenter(tmp_path / "idx", tmp_path, llm, project_id=project_id)
    aug.profile_gate = gate
    # Stub the on-disk excerpt helpers so no files need to exist.
    aug._get_file_head = lambda fp, max_lines=100: "stubbed file content"
    aug._get_strategic_excerpt = lambda fp, sections: "stubbed strategic excerpt"
    return aug


def test_prose_docs_man_page_uses_refdoc_prompt(
    tmp_path, tmp_settings, dummy_project_in_registry
):
    pid = dummy_project_in_registry.id
    scope_store.create(
        pid, display_name="knowledge-linux", paths=["knowledge/linux/"], pipeline_profile="prose_docs"
    )
    llm = _CapturingLLM(json.dumps({
        "summary": "sshd_config man page — every sshd directive with accepted values and defaults.",
        "role": "documentation",
        "confidence": 0.9,
        "doc_type": "man_page",
        "related_files": ["sshd.8"],
    }))
    gate = ProfileGate(pid, StageId.CATALOGUE)
    aug = _make_augmenter(tmp_path, llm, gate=gate, project_id=pid)

    node = _file_node("knowledge/linux/man8/sshd_config.5", language="markdown")
    entry = aug.augment_file(node, [], {})

    assert entry is not None
    assert llm.last_system == REFDOC_ROLE_SYSTEM
    assert entry.role == "documentation"
    assert entry.doc_type == "man_page"
    # REFDOC entries carry no lifecycle status.
    assert entry.doc_status is None
    assert entry.related_files == ["sshd.8"]


def test_system_config_sshd_uses_config_prompt(
    tmp_path, tmp_settings, dummy_project_in_registry
):
    pid = dummy_project_in_registry.id
    scope_store.create(
        pid, display_name="host", paths=["host/"], pipeline_profile="system_config"
    )
    llm = _CapturingLLM(json.dumps({
        "summary": "Configures sshd: sets Port, PermitRootLogin=no, password auth policy; risk: auth.",
        "role": "config",
        "confidence": 0.9,
        "related_files": ["host/etc/ssh/sshd_config.d/00-shared.conf"],
    }))
    gate = ProfileGate(pid, StageId.CATALOGUE)
    aug = _make_augmenter(tmp_path, llm, gate=gate, project_id=pid)

    node = _file_node("host/etc/ssh/sshd_config")
    entry = aug.augment_file(node, [], {})

    assert entry is not None
    assert llm.last_system == CONFIG_ROLE_SYSTEM
    assert entry.role == "config"
    assert "sshd" in entry.summary
    # Config entries set no doc_type/doc_status.
    assert entry.doc_type is None
    assert entry.doc_status is None


def test_code_profile_markdown_unchanged_legacy_doc_prompt(tmp_path):
    """No profile gate → markdown routes to the legacy DOC_ROLE_PROMPT with
    the project-doc taxonomy (doc_type ∈ research/design_spec/…, doc_status)."""
    llm = _CapturingLLM(json.dumps({
        "summary": "Project README.",
        "role": "documentation",
        "confidence": 0.8,
        "doc_type": "readme",
        "doc_status": "active",
        "related_files": [],
    }))
    aug = _make_augmenter(tmp_path, llm)  # no gate → code default
    assert aug.profile_gate is None

    node = _file_node("README.md", language="markdown")
    entry = aug.augment_file(node, [], {})

    assert entry is not None
    assert llm.last_system == DOC_ROLE_SYSTEM
    assert entry.doc_type == "readme"
    assert entry.doc_status == "active"  # legacy docs keep doc_status


def test_code_profile_code_file_unchanged_file_prompt(tmp_path):
    """A code file with no profiled scope → FILE_ROLE prompt (unchanged)."""
    from prep.core.augmenter import FILE_ROLE_SYSTEM

    llm = _CapturingLLM(json.dumps({
        "summary": "App entry point.",
        "role": "entry_point",
        "confidence": 0.85,
        "related_files": [],
    }))
    aug = _make_augmenter(tmp_path, llm)
    node = _file_node("src/app.py", language="python")
    entry = aug.augment_file(node, [], {})

    assert entry is not None
    assert llm.last_system == FILE_ROLE_SYSTEM
    assert entry.role == "entry_point"


def test_refdoc_invalid_doc_type_falls_back_to_none(
    tmp_path, tmp_settings, dummy_project_in_registry
):
    pid = dummy_project_in_registry.id
    scope_store.create(
        pid, display_name="knowledge-linux", paths=["knowledge/linux/"], pipeline_profile="prose_docs"
    )
    llm = _CapturingLLM(json.dumps({
        "summary": "some doc", "role": "documentation", "confidence": 0.7,
        "doc_type": "nonsense_type",  # not in VALID_REFDOC_TYPES
    }))
    gate = ProfileGate(pid, StageId.CATALOGUE)
    aug = _make_augmenter(tmp_path, llm, gate=gate, project_id=pid)
    node = _file_node("knowledge/linux/x.md", language="markdown")
    entry = aug.augment_file(node, [], {})
    assert entry is not None
    assert entry.doc_type is None  # rejected, not stored


# ── Fixture-driven end-to-end (real file content, not stubbed) ──────

_FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures" / "sourceprep_profiles"


def _real_augmenter(tmp_path, llm, gate, project_id):
    """TraceAugmenter that reads real fixture content (no excerpt stubs)."""
    aug = TraceAugmenter(tmp_path / "idx", tmp_path, llm, project_id=project_id)
    aug.profile_gate = gate
    return aug


def test_man_page_fixture_reads_real_content(
    tmp_path, tmp_settings, dummy_project_in_registry
):
    """A real sshd_config man-page fixture under a prose_docs scope flows
    through _augment_refdoc_file reading the actual file (excerpt + SEE ALSO
    parsing), and the LLM receives the file's real section content."""
    pid = dummy_project_in_registry.id
    scope_store.create(
        pid, display_name="knowledge-linux", paths=["knowledge/linux/"], pipeline_profile="prose_docs"
    )
    fixture = _FIXTURES / "sshd_config.5"
    assert fixture.exists()

    llm = _CapturingLLM(json.dumps({
        "summary": "sshd_config man page — every sshd directive with accepted values and defaults.",
        "role": "documentation", "confidence": 0.9,
        "doc_type": "man_page", "related_files": ["sshd.8", "ssh_config.5"],
    }))
    gate = ProfileGate(pid, StageId.CATALOGUE)
    aug = _real_augmenter(tmp_path, llm, gate, pid)

    node = _file_node("knowledge/linux/man8/sshd_config.5", language="markdown")
    # Make the excerpt helper read the real fixture.
    aug._get_strategic_excerpt = lambda fp, sections: fixture.read_text()
    aug._get_file_head = lambda fp, max_lines=100: fixture.read_text()

    entry = aug.augment_file(node, [], {})
    assert entry is not None
    assert llm.last_system == REFDOC_ROLE_SYSTEM
    assert entry.doc_type == "man_page"
    # The real man-page content reached the prompt.
    assert "sshd_config" in llm.last_prompt


def test_sshd_config_fixture_reads_real_content(
    tmp_path, tmp_settings, dummy_project_in_registry
):
    """A real sshd_config fixture under a system_config scope flows through
    _augment_config_file reading the actual file content."""
    pid = dummy_project_in_registry.id
    scope_store.create(
        pid, display_name="host", paths=["host/"], pipeline_profile="system_config"
    )
    fixture = _FIXTURES / "sshd_config"
    assert fixture.exists()

    llm = _CapturingLLM(json.dumps({
        "summary": "Configures sshd: sets Port 22, PermitRootLogin=no, password auth policy; risk: auth.",
        "role": "config", "confidence": 0.9,
        "related_files": ["host/etc/ssh/sshd_config.d/00.conf"],
    }))
    gate = ProfileGate(pid, StageId.CATALOGUE)
    aug = _real_augmenter(tmp_path, llm, gate, pid)

    node = _file_node("host/etc/ssh/sshd_config")
    aug._get_file_head = lambda fp, max_lines=120: fixture.read_text()

    entry = aug.augment_file(node, [], {})
    assert entry is not None
    assert llm.last_system == CONFIG_ROLE_SYSTEM
    assert entry.role == "config"
    assert "PermitRootLogin" in llm.last_prompt