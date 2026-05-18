"""Phase 136 Part 13b regression — cluster reuse must survive small
membership shifts.

Pre-Phase-136 the reuse path keyed on ``frozenset(member_files)``,
so adding/removing even one file from a cluster invalidated the
cached ModuleEntry.  On an incremental rebuild this cascaded across
most modules → "Module Synthesis: rebuilding" behavior even though
only a few files changed.  Parallel to Part 12's fix for
group_reasoning.
"""
from __future__ import annotations

from prep.core.cluster import (
    ModuleEntry,
    _CLUSTER_REUSE_JACCARD_THRESHOLD,
    _find_overlapping_module,
)


def _module(module_id: str, *files: str) -> ModuleEntry:
    return ModuleEntry(
        module_id=module_id,
        name=module_id,
        summary="cached",
        member_files=list(files),
        domain_tags=[],
        architecture_layers=[],
        component_status="healthy",
    )


def _files(*names: str) -> list[str]:
    return [f"src/prep/core/{n}.py" for n in names]


class TestFindOverlappingModule:
    def test_exact_match_returns_module(self):
        m = _module("a", *_files("a", "b", "c", "d", "e"))
        existing = {"a": m}
        result = _find_overlapping_module(_files("a", "b", "c", "d", "e"), existing)
        assert result is m

    def test_peripheral_add_within_threshold_matches(self):
        # 5-file cluster + 1 new = 5/6 = 83% > 70%
        m = _module("a", *_files("a", "b", "c", "d", "e"))
        existing = {"a": m}
        result = _find_overlapping_module(
            _files("a", "b", "c", "d", "e", "z"), existing,
        )
        assert result is m, (
            "1-file growth on a 5-file cluster must match the cached entry"
        )

    def test_realistic_incremental_shift_matches(self):
        # 10-file cluster + 2 new = 10/12 = 83% > 70%
        m = _module("a", *_files(*"abcdefghij"))
        existing = {"a": m}
        result = _find_overlapping_module(
            _files(*"abcdefghij") + ["docs/X.md", "tests/test_z.py"],
            existing,
        )
        assert result is m

    def test_below_threshold_returns_none(self):
        # 1/5 = 20% — way below
        m = _module("a", *_files("a", "b", "c", "d", "e"))
        existing = {"a": m}
        result = _find_overlapping_module(_files("a", "w", "x", "y", "z"), existing)
        assert result is None

    def test_empty_input_returns_none(self):
        m = _module("a", *_files("a", "b", "c"))
        existing = {"a": m}
        assert _find_overlapping_module([], existing) is None

    def test_empty_existing_returns_none(self):
        assert _find_overlapping_module(_files("a", "b"), {}) is None

    def test_asymmetric_overlap_rejects_subset_match(self):
        # Big cached module (20 files); new cluster is a 5-file subset.
        # Forward overlap is 5/5=100% but reverse is 5/20=25% < 70%.
        # Must NOT match.
        big = _module("big", *_files(*"abcdefghijklmnopqrst"))
        existing = {"big": big}
        result = _find_overlapping_module(_files("a", "b", "c", "d", "e"), existing)
        assert result is None

    def test_picks_best_match_among_candidates(self):
        # Two candidates: one 90%, one 75%.  Pick the 90% one.
        tight = _module("tight", *_files(*"abcdefghij"))     # 10 files
        loose = _module("loose", *_files(*"abcdefghi", "x", "y"))  # 9+2 = 11 files
        existing = {"tight": tight, "loose": loose}
        # New cluster = tight's 10 + 1 extra → 10/11 vs tight, 9/12 vs loose
        new = _files(*"abcdefghij") + ["docs/N.md"]
        result = _find_overlapping_module(new, existing)
        assert result is tight

    def test_threshold_constant_is_sensible(self):
        # Smoke check: the threshold should be in (0.5, 1.0).  0.7 is
        # the chosen default; the test guards against accidental
        # changes that would either match too aggressively (≤0.5)
        # or never match (≥1.0).
        assert 0.5 < _CLUSTER_REUSE_JACCARD_THRESHOLD < 1.0
