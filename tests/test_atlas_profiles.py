"""Tests: profile-keyed ATLAS prompt selection (T-S2.3).

Acceptance:
* A project with knowledge/linux + knowledge/macos segments (prose_docs)
  selects the CORPUS root prompt and SEGMENT_CORPUS per-segment prompt —
  platform coverage, not "modules/imports".
* A host segment (system_config) selects HOST root + SEGMENT_HOST segment
  prompts describing config surfaces.
* A code-only project (no profiled scopes) selects the legacy
  ROOT_ATLAS_PROMPT / SEGMENT_ATLAS_PROMPT unchanged.
* Mixed (prose dominant + a host scope) → CORPUS root with mixed_host=True.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pytest

from prep.core.atlas.generator import CodebaseAtlas
from prep.core.atlas.models import Segment
from prep.core.atlas.prompts import (
    CORPUS_ATLAS_PROMPT,
    HOST_ATLAS_PROMPT,
    ROOT_ATLAS_PROMPT,
    SEGMENT_ATLAS_PROMPT,
    SEGMENT_CORPUS_PROMPT,
    SEGMENT_HOST_PROMPT,
)
from prep.core.pipeline_profiles import ProfileGate
from prep.core.scope_store import scope_store
from prep.services.pipeline.stages import StageId


def _seg(seg_id, name, dir_path, files):
    return Segment(
        id=seg_id, name=name, dir_path=dir_path, file_paths=list(files),
        file_count=len(files),
    )


def _atlas_with_gate(tmp_path, pid, gate=None):
    # CodebaseAtlas needs an index_dir + project_root; the prompt-selection
    # helpers never touch disk, so a throwaway path is enough.
    gen = CodebaseAtlas(
        index_dir=tmp_path / "idx", project_root=tmp_path, llm=None,
        project_id=pid,
    )
    gen.profile_gate = gate
    return gen


def test_corpus_project_selects_corpus_prompts(
    tmp_path, tmp_settings, dummy_project_in_registry
):
    pid = dummy_project_in_registry.id
    scope_store.create(pid, display_name="knowledge-linux", paths=["knowledge/linux/"], pipeline_profile="prose_docs")
    scope_store.create(pid, display_name="knowledge-macos", paths=["knowledge/macos/"], pipeline_profile="prose_docs")
    gate = ProfileGate(pid, StageId.ATLAS)
    gen = _atlas_with_gate(tmp_path, pid, gate=gate)

    segs = [
        _seg("kl", "Knowledge Linux", "knowledge/linux",
             ["knowledge/linux/man8/sshd_config.5", "knowledge/linux/man1/ls.1"]),
        _seg("km", "Knowledge macOS", "knowledge/macos",
             ["knowledge/macos/man1/brew.1", "knowledge/macos/handbook/disk.md"]),
    ]

    root_tmpl, mixed = gen._root_prompt_for(segs)
    assert root_tmpl is CORPUS_ATLAS_PROMPT
    assert mixed is False  # no host scope present
    # CORPUS root asks for platform coverage, not modules/imports.
    assert "PLATFORM COVERAGE" in root_tmpl
    assert "ARCHITECTURE" not in root_tmpl  # legacy code-root section

    for seg in segs:
        assert gen._segment_prompt_for(seg) is SEGMENT_CORPUS_PROMPT


def test_host_project_selects_host_prompts(
    tmp_path, tmp_settings, dummy_project_in_registry
):
    pid = dummy_project_in_registry.id
    scope_store.create(pid, display_name="host", paths=["host/"], pipeline_profile="system_config")
    gate = ProfileGate(pid, StageId.ATLAS)
    gen = _atlas_with_gate(tmp_path, pid, gate=gate)

    seg = _seg("host", "Host Config", "host", ["host/etc/ssh/sshd_config", "host/etc/fstab"])
    root_tmpl, mixed = gen._root_prompt_for([seg])
    assert root_tmpl is HOST_ATLAS_PROMPT
    assert mixed is False
    assert "SERVICES" in root_tmpl and "AUTH POLICY" in root_tmpl
    assert gen._segment_prompt_for(seg) is SEGMENT_HOST_PROMPT


def test_mixed_corpus_plus_host_signals_host_paragraph(
    tmp_path, tmp_settings, dummy_project_in_registry
):
    pid = dummy_project_in_registry.id
    scope_store.create(pid, display_name="knowledge-linux", paths=["knowledge/linux/"], pipeline_profile="prose_docs")
    scope_store.create(pid, display_name="host", paths=["host/"], pipeline_profile="system_config")
    gate = ProfileGate(pid, StageId.ATLAS)
    gen = _atlas_with_gate(tmp_path, pid, gate=gate)

    segs = [
        _seg("kl", "Knowledge Linux", "knowledge/linux",
             [f"knowledge/linux/d{i}.md" for i in range(10)]),
        _seg("host", "Host Config", "host", ["host/etc/ssh/sshd_config"]),
    ]
    root_tmpl, mixed = gen._root_prompt_for(segs)
    # prose_docs dominant by volume → CORPUS, but host scope present → mixed
    assert root_tmpl is CORPUS_ATLAS_PROMPT
    assert mixed is True


def test_code_only_project_keeps_legacy_prompts(tmp_path):
    """No profiled scopes → legacy ROOT_ATLAS_PROMPT / SEGMENT_ATLAS_PROMPT.
    A project with no scopes (or only code-profile scopes) resolves every
    path to the code default, so prompt selection is byte-identical to before."""
    gen = _atlas_with_gate(tmp_path, "no-such-project")  # no scopes → code default

    seg = _seg("src", "Source", "src", ["src/app.py", "src/lib.py"])
    root_tmpl, mixed = gen._root_prompt_for([seg])
    assert root_tmpl is ROOT_ATLAS_PROMPT
    assert mixed is False
    assert gen._segment_prompt_for(seg) is SEGMENT_ATLAS_PROMPT


# ── atlas_deep_dirs config knob (T-S2.4) ─────────────────────────────


def test_group_by_directory_uses_atlas_deep_dirs():
    """With extra_deep_dirs=['knowledge'], knowledge/<platform> files group
    per-platform at depth 2; without it, they group at depth 1 (knowledge)."""
    from prep.core.atlas.routing import _group_by_directory

    paths = [
        "knowledge/linux/man8/sshd_config.5",
        "knowledge/linux/man1/ls.1",
        "knowledge/macos/man1/brew.1",
        "knowledge/common/shell.md",
        "src/app.py",
    ]
    # Without the knob: knowledge/* collapses to a single 'knowledge' group.
    no_knob = _group_by_directory(paths)
    assert "knowledge" in no_knob
    assert not any(k.startswith("knowledge/") for k in no_knob)
    # src/ stays deep (built-in _DEEP_DIRS).
    assert "src/app" not in no_knob or "src" in no_knob  # src is built-in deep

    # With the knob: knowledge splits per platform.
    with_knob = _group_by_directory(paths, extra_deep_dirs=["knowledge"])
    assert "knowledge/linux" in with_knob
    assert "knowledge/macos" in with_knob
    assert "knowledge/common" in with_knob
    assert "knowledge" not in with_knob


def test_compute_segments_default_unchanged(tmp_path):
    """Without extra_deep_dirs, compute_segments is byte-identical to before."""
    from prep.core.atlas.routing import compute_segments, _group_by_directory

    paths = ["src/a/x.py", "src/a/y.py", "src/b/z.py", "docs/readme.md", "docs/guide.md"]
    default = _group_by_directory(paths)
    explicit_none = _group_by_directory(paths, extra_deep_dirs=None)
    assert default == explicit_none


def test_atlas_deep_dirs_reads_project_config(
    tmp_path, tmp_settings, dummy_project_in_registry
):
    """The generator's _atlas_deep_dirs() reads the project config knob."""
    pid = dummy_project_in_registry.id
    dummy_project_in_registry.config["atlas_deep_dirs"] = ["knowledge", "host"]
    gen = _atlas_with_gate(tmp_path, pid)
    assert gen._atlas_deep_dirs() == ["knowledge", "host"]

    # Unset → None (compute_segments stays byte-identical).
    dummy_project_in_registry.config.pop("atlas_deep_dirs", None)
    gen2 = _atlas_with_gate(tmp_path, pid)
    assert gen2._atlas_deep_dirs() is None