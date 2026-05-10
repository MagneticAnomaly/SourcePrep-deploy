"""
Tests for the FIX-16-3 follow-up: migrating legacy `#N` suffixes in
already-synthesized module names.

Modules in `trace_modules.jsonl` from before FIX-16-3 carry "Foo (Packages) #2"
style names. The new dedup logic emits "Foo (Packages) [<idx>]" instead.
The migration helpers let callers rewrite legacy names without forcing a
full pipeline rerun.
"""
from __future__ import annotations

import re

from prep.core.cluster import (
    ModuleEntry,
    strip_legacy_pound_n_suffix,
    strip_legacy_pound_n_suffixes,
)


def _mod(module_id: str, name: str) -> ModuleEntry:
    return ModuleEntry(
        module_id=module_id,
        name=name,
        summary="",
        member_files=[],
        domain_tags=[],
        architecture_layers=[],
        component_status="complete",
    )


# --- single-name helper ---------------------------------------------------------

def test_strip_pound_n_simple():
    assert strip_legacy_pound_n_suffix(
        "UI Library (Packages) #2", "cluster:packages:42",
    ) == "UI Library (Packages) [42]"


def test_strip_pound_n_with_trailing_space():
    assert strip_legacy_pound_n_suffix(
        "Foo #3 ", "cluster:foo:7",
    ) == "Foo [7]"


def test_strip_pound_n_multi_digit():
    assert strip_legacy_pound_n_suffix(
        "Bar #12", "cluster:bar:99",
    ) == "Bar [99]"


def test_strip_pound_n_no_match_passes_through():
    assert strip_legacy_pound_n_suffix(
        "Foo (Packages)", "cluster:packages:1",
    ) == "Foo (Packages)"


def test_strip_pound_n_does_not_strip_mid_string():
    """A # in the middle of a name is not a suffix and must be preserved."""
    assert strip_legacy_pound_n_suffix(
        "Issue #42 Tracker", "cluster:tracker:1",
    ) == "Issue #42 Tracker"


def test_strip_pound_n_handles_already_migrated():
    """Names already migrated to `[idx]` form pass through unchanged."""
    assert strip_legacy_pound_n_suffix(
        "Foo (Packages) [42]", "cluster:packages:42",
    ) == "Foo (Packages) [42]"


def test_strip_pound_n_falls_back_to_base_when_no_module_id():
    assert strip_legacy_pound_n_suffix("Foo #2", "") == "Foo"


def test_strip_pound_n_empty_inputs():
    assert strip_legacy_pound_n_suffix("", "cluster:x:1") == ""
    # None passes through as None — keep semantics simple, callers handle.
    assert strip_legacy_pound_n_suffix(None, "cluster:x:1") is None  # type: ignore[arg-type]


# --- batch helper ---------------------------------------------------------------

def test_batch_migrates_all_pound_n_names():
    mods = {
        "cluster:a:1": _mod("cluster:a:1", "Auth Service"),  # no change
        "cluster:b:2": _mod("cluster:b:2", "UI Library #2"),
        "cluster:c:3": _mod("cluster:c:3", "Data Layer #3"),
    }
    rewritten = strip_legacy_pound_n_suffixes(mods)
    assert rewritten == 2
    assert mods["cluster:a:1"].name == "Auth Service"
    assert mods["cluster:b:2"].name == "UI Library [2]"
    assert mods["cluster:c:3"].name == "Data Layer [3]"
    # No `#N` survives
    for mod in mods.values():
        assert not re.search(r"#\d+\s*$", mod.name)


def test_batch_idempotent():
    """Running migration twice on the same dict is a no-op the second time."""
    mods = {
        "cluster:b:2": _mod("cluster:b:2", "UI Library #2"),
    }
    first = strip_legacy_pound_n_suffixes(mods)
    second = strip_legacy_pound_n_suffixes(mods)
    assert first == 1
    assert second == 0
    assert mods["cluster:b:2"].name == "UI Library [2]"


def test_batch_returns_zero_for_clean_dict():
    mods = {"cluster:a:1": _mod("cluster:a:1", "Auth Service")}
    assert strip_legacy_pound_n_suffixes(mods) == 0
