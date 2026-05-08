"""
Tests for the FIX-16-1 module-list cap and first-sentence summary truncation
in `_format_module_tiers` (see docs/Phase82_MCP-Dogfooding/17_Followup_2026-05-08.md).

Before this fix, every "significant" module (file_count >= module_min_files_significant)
was emitted with its full multi-sentence summary, producing a ~35K-char firehose on
prep() no-arg calls. The fix adds:

  - A per-tier `module_max_significant` cap on how many modules render in the
    significant tier.
  - First-sentence truncation of each module's summary by default.
  - A `verbose=True` opt-out that restores the original unbounded behavior.
  - Footnote of the omitted-significant count so the agent knows to re-call
    with `verbose=True` if it needs the full list.
"""
from __future__ import annotations

from prep.api.routers.projects.search import _format_module_tiers
from prep.core.context_tier import ContextTier


def _module(name: str, file_count: int, summary: str = "Short summary.") -> dict:
    return {
        "name": name,
        "module_id": f"mod:{name.lower()}",
        "summary": summary,
        "file_count": file_count,
        "member_files": [f"src/{name.lower()}/file{i}.py" for i in range(file_count)],
        "domain_tags": [],
        "dependencies": [],
    }


# --- module_max_significant cap -------------------------------------------------

def test_significant_list_capped_to_tier_max_by_default():
    """Tier 1 caps the significant tier at 12 modules; the rest fold into a footnote."""
    modules = [_module(f"M{i:02d}", 50) for i in range(20)]
    out = _format_module_tiers(modules, context_tier=ContextTier.TIER_1, role=None)
    # Top 12 appear by name
    for i in range(12):
        assert f"M{i:02d}" in out, f"M{i:02d} should be in capped output"
    # The 13th onward should not appear as named entries
    assert "**M12**" not in out
    assert "**M19**" not in out
    # Footnote should disclose the omitted count
    assert "8 more" in out or "omitted" in out or "additional" in out


def test_tier_2_cap_is_8():
    modules = [_module(f"M{i:02d}", 50) for i in range(15)]
    out = _format_module_tiers(modules, context_tier=ContextTier.TIER_2, role=None)
    for i in range(8):
        assert f"**M{i:02d}**" in out
    assert "**M08**" not in out
    assert "**M14**" not in out


def test_tier_2_5_cap_is_6():
    modules = [_module(f"M{i:02d}", 50) for i in range(10)]
    out = _format_module_tiers(modules, context_tier=ContextTier.TIER_2_5, role=None)
    for i in range(6):
        assert f"**M{i:02d}**" in out
    assert "**M06**" not in out


def test_under_cap_emits_all_no_footnote():
    """When fewer significant modules exist than the cap, no omission footnote."""
    modules = [_module(f"M{i}", 50) for i in range(5)]
    out = _format_module_tiers(modules, context_tier=ContextTier.TIER_1, role=None)
    for i in range(5):
        assert f"**M{i}**" in out
    # Don't suggest there are more significant modules to see
    assert "more significant" not in out
    assert "additional significant" not in out


def test_verbose_true_lifts_cap():
    """verbose=True restores the original unbounded behavior."""
    modules = [_module(f"M{i:02d}", 50) for i in range(20)]
    out = _format_module_tiers(
        modules, context_tier=ContextTier.TIER_1, role=None, verbose=True,
    )
    # All 20 appear by name
    for i in range(20):
        assert f"**M{i:02d}**" in out


# --- first-sentence summary truncation -----------------------------------------

def test_summary_truncated_to_first_sentence_by_default():
    """Multi-sentence summaries get truncated to the first sentence."""
    long_summary = (
        "Provides end-to-end project management capabilities. "
        "Bridges enterprise policy enforcement with consumer-grade privacy. "
        "Currently in active transition with critical gaps."
    )
    modules = [_module("PM", 50, summary=long_summary)]
    out = _format_module_tiers(modules, context_tier=ContextTier.TIER_1, role=None)
    assert "Provides end-to-end project management capabilities." in out
    # Subsequent sentences should be dropped
    assert "Bridges enterprise policy enforcement" not in out
    assert "Currently in active transition" not in out


def test_verbose_true_keeps_full_summary():
    long_summary = (
        "Provides end-to-end project management capabilities. "
        "Bridges enterprise policy enforcement with consumer-grade privacy."
    )
    modules = [_module("PM", 50, summary=long_summary)]
    out = _format_module_tiers(
        modules, context_tier=ContextTier.TIER_1, role=None, verbose=True,
    )
    assert "Provides end-to-end project management capabilities." in out
    assert "Bridges enterprise policy enforcement" in out


def test_summary_without_period_passes_through():
    """A summary that doesn't end in a period is emitted as-is (not truncated)."""
    modules = [_module("X", 50, summary="No terminal period here")]
    out = _format_module_tiers(modules, context_tier=ContextTier.TIER_1, role=None)
    assert "No terminal period here" in out


def test_empty_summary_does_not_crash():
    modules = [_module("X", 50, summary="")]
    out = _format_module_tiers(modules, context_tier=ContextTier.TIER_1, role=None)
    assert "**X**" in out


# --- ContextTier exposes the cap ------------------------------------------------

def test_tier_1_has_module_max_significant_property():
    assert ContextTier.TIER_1.module_max_significant == 12


def test_tier_2_has_module_max_significant_property():
    assert ContextTier.TIER_2.module_max_significant == 8


def test_tier_2_5_has_module_max_significant_property():
    assert ContextTier.TIER_2_5.module_max_significant == 6
