"""
Tests for FIX-16-3: replace `#N` numbered-clone fallback in
`_deduplicate_module_names` with a module_id discriminator
(see docs/Phase82_MCP-Dogfooding/17_Followup_2026-05-08.md).

The original second-pass fallback emitted "Foo #2", "Foo #3" when the
first-pass parenthetical distinguisher (majority dir / layer / domain tag)
collided. The `#N` suffix reads as a synthesizer giveaway in the atlas.
This pass replaces that fallback with a module_id-derived discriminator
so duplicates are still distinguishable but no longer signal failure.
"""
from __future__ import annotations

import re

from prep.core.cluster import ModuleEntry, _deduplicate_module_names


def _mod(
    module_id: str,
    name: str,
    member_files: list[str] | None = None,
    layers: list[str] | None = None,
    tags: list[str] | None = None,
) -> ModuleEntry:
    return ModuleEntry(
        module_id=module_id,
        name=name,
        summary="",
        member_files=member_files or [],
        domain_tags=tags or [],
        architecture_layers=layers or [],
        component_status="complete",
    )


def test_no_collision_no_change():
    """Distinct names pass through unchanged."""
    mods = {
        "a": _mod("cluster:a:1", "Auth Service"),
        "b": _mod("cluster:b:1", "Marketing Engine"),
    }
    _deduplicate_module_names(mods)
    assert mods["a"].name == "Auth Service"
    assert mods["b"].name == "Marketing Engine"


def test_first_pass_distinguishes_by_directory():
    """When duplicates have different majority directories, first pass
    distinguishes them with parenthetical suffixes — pre-existing behavior."""
    mods = {
        "a": _mod("cluster:a:1", "UI Layer", member_files=["packages/ui/x.tsx"]),
        "b": _mod("cluster:b:1", "UI Layer", member_files=["src/dashboard/y.tsx"]),
    }
    _deduplicate_module_names(mods)
    assert mods["a"].name != mods["b"].name
    # Both should carry parenthetical distinguishers from their top dir
    assert "(" in mods["a"].name
    assert "(" in mods["b"].name


def test_no_pound_n_suffix_when_first_pass_collides():
    """When two modules collide AND first-pass distinguishers collide too,
    the fallback must NOT emit `#2`/`#3`. The output should still be unique
    but use a module_id-derived discriminator instead."""
    # Both modules: same name, both in the same top dir → first-pass suffix
    # for both will be "Packages", producing a residual collision.
    mods = {
        "cluster:packages:1": _mod(
            "cluster:packages:1", "UI Library",
            member_files=["packages/ui/Button.tsx", "packages/ui/Card.tsx"],
        ),
        "cluster:packages:2": _mod(
            "cluster:packages:2", "UI Library",
            member_files=["packages/ui/Modal.tsx", "packages/ui/Drawer.tsx"],
        ),
    }
    _deduplicate_module_names(mods)
    name_a = mods["cluster:packages:1"].name
    name_b = mods["cluster:packages:2"].name
    # Names must be distinct
    assert name_a != name_b
    # Neither name may end with `#N`
    assert not re.search(r"#\d+\s*$", name_a), f"name_a={name_a!r} still has #N"
    assert not re.search(r"#\d+\s*$", name_b), f"name_b={name_b!r} still has #N"
    # Both should still start with the original name root
    assert "UI Library" in name_a
    assert "UI Library" in name_b


def test_three_way_collision_produces_three_distinct_names_no_pound_n():
    mods = {
        "cluster:packages:1": _mod(
            "cluster:packages:1", "Atlas Module",
            member_files=["packages/atlas/a.ts"],
        ),
        "cluster:packages:2": _mod(
            "cluster:packages:2", "Atlas Module",
            member_files=["packages/atlas/b.ts"],
        ),
        "cluster:packages:3": _mod(
            "cluster:packages:3", "Atlas Module",
            member_files=["packages/atlas/c.ts"],
        ),
    }
    _deduplicate_module_names(mods)
    names = {m.name for m in mods.values()}
    assert len(names) == 3, f"expected 3 distinct names, got {names}"
    for n in names:
        assert not re.search(r"#\d+\s*$", n), f"{n!r} still has #N"


def test_singletons_unaffected_when_others_collide():
    """A unique-named module in the same dict should be left alone even if
    other modules collide."""
    mods = {
        "cluster:packages:1": _mod(
            "cluster:packages:1", "UI Library",
            member_files=["packages/ui/x.tsx"],
        ),
        "cluster:packages:2": _mod(
            "cluster:packages:2", "UI Library",
            member_files=["packages/ui/y.tsx"],
        ),
        "cluster:other:1": _mod(
            "cluster:other:1", "Auth Service",
            member_files=["src/auth/token.py"],
        ),
    }
    _deduplicate_module_names(mods)
    assert mods["cluster:other:1"].name == "Auth Service"
