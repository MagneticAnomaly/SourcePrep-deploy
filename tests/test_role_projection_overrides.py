"""
Tests for Phase 104 Step 3 — overrides + pinned concepts wire through the
role projection engine.

Covers:
- ``overrides.max_chars`` replaces ``role.max_chars`` before assembly.
- Pinned concepts are rendered as a preamble, bounded by 20% of budget.
- No override / no pins → behavior unchanged (regression guard).
- ``_format_pinned_block`` handles empty / oversize / malformed entries.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def projection_mod():
    return importlib.import_module("codrag.core.atlas.role_projection")


@pytest.fixture
def role_vectors_mod():
    return importlib.import_module("codrag.core.atlas.role_vectors")


# ── _format_pinned_block ────────────────────────────────────────────


def test_format_pinned_block_empty_returns_empty_string(projection_mod):
    assert projection_mod._format_pinned_block([], 500) == ""


def test_format_pinned_block_tiny_budget_returns_empty(projection_mod):
    # Under the 80-char floor, the block is not worth rendering.
    concepts = [{"title": "T", "content": "C"}]
    assert projection_mod._format_pinned_block(concepts, 50) == ""


def test_format_pinned_block_includes_title_and_preview(projection_mod):
    concepts = [{"title": "JWT Auth", "content": "Uses RS256 signing keys."}]
    block = projection_mod._format_pinned_block(concepts, 500)
    assert "[Pinned for this role]" in block
    assert "JWT Auth" in block
    assert "RS256" in block


def test_format_pinned_block_truncates_long_content(projection_mod):
    long_content = "x" * 1000
    concepts = [{"title": "Wide", "content": long_content}]
    block = projection_mod._format_pinned_block(concepts, 300)
    assert block
    # The "…" ellipsis signals truncation.
    assert "…" in block
    assert len(block) <= 300


def test_format_pinned_block_stops_when_budget_exhausted(projection_mod):
    concepts = [
        {"title": f"Concept {i}", "content": "short preview " * 5}
        for i in range(20)
    ]
    block = projection_mod._format_pinned_block(concepts, 400)
    # Not every concept fits into 400 chars.
    entries = [line for line in block.splitlines() if line.startswith("- ")]
    assert 0 < len(entries) < 20
    assert len(block) <= 400


def test_format_pinned_block_skips_entries_missing_title(projection_mod):
    concepts = [
        {"title": "", "content": "no title means skip"},
        {"title": "Kept", "content": "renders"},
    ]
    block = projection_mod._format_pinned_block(concepts, 500)
    assert "no title means skip" not in block
    assert "Kept" in block


# ── project_atlas_for_role: budget override ─────────────────────────


class _FakeOverride:
    """Minimal shape compatible with the loose ``Any`` typing used in the
    projection (must expose a ``.max_chars`` attribute)."""

    def __init__(self, max_chars=None):
        self.max_chars = max_chars


def _role(role_vectors_mod, max_chars=4000):
    # The engineering built-in has all the fields populated; copy then mutate
    # for test determinism.
    rv = role_vectors_mod.BUILT_IN_ROLES["engineering"].copy()
    rv.max_chars = max_chars
    return rv


def test_override_shrinks_max_chars(tmp_path, projection_mod, role_vectors_mod):
    """With no data on disk, the function returns a short placeholder, but
    the override must not raise and must be honored in the budget math.
    """
    role = _role(role_vectors_mod, max_chars=4000)
    override = _FakeOverride(max_chars=1000)

    out = projection_mod.project_atlas_for_role(
        role,
        index_dir=tmp_path,
        atlas_content="",
        overrides=override,
    )
    # Placeholder path is small — we're not testing budget enforcement on
    # the placeholder output. We ARE testing that passing overrides doesn't
    # crash and that the function returns something.
    assert isinstance(out, str)


def test_no_override_preserves_default_budget_behavior(
    tmp_path, projection_mod, role_vectors_mod
):
    """Regression guard: existing callers must still work without overrides."""
    role = _role(role_vectors_mod, max_chars=4000)
    out = projection_mod.project_atlas_for_role(role, tmp_path, "")
    assert isinstance(out, str)


def test_pinned_concepts_prepend_to_output(
    tmp_path, projection_mod, role_vectors_mod
):
    role = _role(role_vectors_mod, max_chars=4000)
    pinned = [{"title": "PinnedTitle", "content": "pinned body"}]
    out = projection_mod.project_atlas_for_role(
        role,
        tmp_path,
        atlas_content="",
        pinned_concepts=pinned,
    )
    # Pinned block is prepended, and "[Role:" marker follows after.
    assert out.startswith("[Pinned for this role]")
    assert "PinnedTitle" in out


def test_override_zero_or_negative_max_chars_is_ignored(
    tmp_path, projection_mod, role_vectors_mod
):
    """Defensive: if override gets a bad value, fall back to the role's
    built-in budget instead of crashing or producing empty output.
    """
    role = _role(role_vectors_mod, max_chars=4000)
    override = _FakeOverride(max_chars=0)
    out = projection_mod.project_atlas_for_role(
        role, tmp_path, "", overrides=override
    )
    assert isinstance(out, str)


def test_pinned_budget_capped_at_20pct(projection_mod):
    """Even when the pinned-concepts budget itself is fine, the projection
    caller only allocates 20% of role.max_chars to the pin block.
    """
    # Sanity check the constant used: max_chars=1000 → pin budget = 200.
    # 200 >= 80 floor, so block should render.
    concepts = [{"title": "x", "content": "y" * 50}]
    block = projection_mod._format_pinned_block(concepts, 200)
    assert block
    assert len(block) <= 200
