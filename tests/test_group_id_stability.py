"""Phase 136 Part 12 regression — incremental group_reasoning carries
forward cached entries when membership shifts by ≤ 30%, so adding a
peripheral file to an existing group doesn't force full re-analysis.

The group_id itself remains a hash of the full sorted member set
(format-compatible with existing on-disk entries).  Stability comes
from `_find_overlapping_entry`, a Jaccard-overlap fallback used when
the exact-gid lookup misses.

Pre-Phase-136 dogfooding 2026-05-18: 54 added files caused 98 of 109
groups to re-analyze (90% cache miss) on what should have been a
near-no-op incremental run, because adding even ONE member changed
the gid hash and invalidated the cached entry.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from prep.core.group_reasoning import (
    GroupReasoningEntry,
    _find_overlapping_entry,
    _stable_group_id,
)


def _members(*names: str) -> list[str]:
    return [f"file:src/prep/core/{n}.py" for n in names]


def _entry(members: list[str]) -> GroupReasoningEntry:
    """Minimal GroupReasoningEntry for fixture use."""
    return GroupReasoningEntry(
        group_id=_stable_group_id(members),
        member_node_ids=list(members),
        pattern="test",
        data_flow="cached analysis",
        coupling_risks=[],
        blast_radius=[],
        architectural_insight="",
        confidence=0.9,
    )


class TestStableGroupIdFormat:
    """The id remains a hash of the FULL sorted member set — this is
    the legacy formula and the on-disk format depends on it."""

    def test_id_format_prefix(self):
        gid = _stable_group_id(_members("a", "b", "c"))
        assert gid.startswith("group:")
        assert len(gid) == len("group:") + 10

    def test_id_changes_with_any_membership_change(self):
        # Document the intentional behavior: the id itself is NOT
        # stable across membership changes; stability comes from the
        # overlap fallback in _find_overlapping_entry.
        before = _stable_group_id(_members("a", "b", "c"))
        after = _stable_group_id(_members("a", "b", "c", "z"))
        assert before != after

    def test_id_stable_for_input_permutations(self):
        # Sorted inside the helper — caller-side order doesn't matter.
        a = _stable_group_id(["file:a.py", "file:b.py", "file:c.py"])
        b = _stable_group_id(["file:c.py", "file:a.py", "file:b.py"])
        assert a == b


class TestFindOverlappingEntry:
    """The fallback that lets incremental runs reuse cached entries
    when membership shifted slightly."""

    def test_exact_match_returns_entry(self):
        core = _members("a", "b", "c", "d", "e")
        existing = {_stable_group_id(core): _entry(core)}
        gid, ex = _find_overlapping_entry(core, existing)
        assert ex is not None
        assert ex.member_node_ids == core

    def test_peripheral_add_within_threshold_matches(self):
        # 5-member group + 1 new member = 5/6 overlap = 83% ≥ 70%
        core = _members("a", "b", "c", "d", "e")
        existing = {_stable_group_id(core): _entry(core)}
        # Add a file that sorts BEFORE the existing anchors (the
        # failure mode that broke the anchor-N approach)
        new_members = ["file:docs/X.md"] + core
        gid, ex = _find_overlapping_entry(new_members, existing)
        assert ex is not None, (
            "Adding 1 file to a 5-member group must still match the "
            "cached entry (83% overlap > 70% threshold)"
        )

    def test_realistic_incremental_shift_matches(self):
        # 10-member group + 2 new members = 10/12 overlap = 83% ≥ 70%
        core = _members(*"abcdefghij")
        existing = {_stable_group_id(core): _entry(core)}
        new_members = core + [
            "file:docs/A.md",
            "file:tests/test_z.py",
        ]
        gid, ex = _find_overlapping_entry(new_members, existing)
        assert ex is not None

    def test_large_shift_below_threshold_does_not_match(self):
        # 5-member group, 4 of which are different = 1/5 overlap = 20%
        core = _members("a", "b", "c", "d", "e")
        existing = {_stable_group_id(core): _entry(core)}
        new_members = _members("a", "x", "y", "z", "w")  # only "a" shared
        gid, ex = _find_overlapping_entry(new_members, existing)
        assert ex is None, (
            "20% overlap must not match — groups have fundamentally "
            "different membership"
        )

    def test_empty_input_returns_none(self):
        existing = {_stable_group_id(_members("a", "b", "c")): _entry(_members("a", "b", "c"))}
        gid, ex = _find_overlapping_entry([], existing)
        assert ex is None

    def test_empty_existing_returns_none(self):
        gid, ex = _find_overlapping_entry(_members("a", "b", "c"), {})
        assert ex is None

    def test_picks_best_match_among_multiple_candidates(self):
        # Two cached groups: one 90% overlap, one 75% overlap → pick the 90%.
        ten = _members(*"abcdefghij")  # 10 members
        nine = _members(*"abcdefghi")   # 9 shared, 1 missing
        existing = {
            _stable_group_id(ten): _entry(ten),
            _stable_group_id(nine + ["file:src/prep/core/x.py"]): _entry(nine + ["file:src/prep/core/x.py"]),
        }
        # New group = the 10-member set + 1 add = 10/11 overlap with ten,
        # 9/11 overlap with the second.  Should pick ten.
        new = ten + ["file:docs/Y.md"]
        gid, ex = _find_overlapping_entry(new, existing)
        assert ex is not None
        assert set(ex.member_node_ids) == set(ten)

    def test_asymmetric_overlap_rejects_subset_match(self):
        # Big cached group with 20 members; new group is a 5-member subset.
        # Forward overlap is 5/5=100% (subset contained), but reverse is
        # 5/20=25% < threshold.  Must NOT match (different group).
        big = _members(*"abcdefghijklmnopqrst")  # 20 members
        existing = {_stable_group_id(big): _entry(big)}
        small = _members("a", "b", "c", "d", "e")
        gid, ex = _find_overlapping_entry(small, existing)
        assert ex is None, (
            "Subset overlap must not match the parent — symmetric "
            "Jaccard prevents tiny groups from absorbing big ones"
        )
