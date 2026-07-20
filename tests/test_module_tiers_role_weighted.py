"""
Tests for role-weighted module ranking in the ambient context module list.

Closes the 2026-05-02 dogfood finding (issue #2 / Task #4) — see the
2026-05-05 epistemic-audit pass notes.
A prep(role="security") call previously listed marketing modules above
security modules in the "Modules in scope" section because the role lens
only filtered the trailing files block; the module emission ignored role.
"""
from __future__ import annotations

from prep.api.routers.projects.search import _format_module_tiers
from prep.core.atlas.role_resolver import resolve_role
from prep.core.context_tier import ContextTier


def _module(name: str, file_count: int, domain_tags: list[str]) -> dict:
    return {
        "name": name,
        "module_id": f"mod:{name.lower()}",
        "summary": f"{name} module summary.",
        "file_count": file_count,
        "member_files": [f"src/{name.lower()}/file{i}.py" for i in range(file_count)],
        "domain_tags": domain_tags,
        "dependencies": [],
    }


def test_no_role_preserves_file_count_ordering():
    """Without role, modules sort by file_count descending — unchanged behavior."""
    modules = [
        _module("Marketing", 50, ["marketing", "content"]),
        _module("Auth", 30, ["security", "auth"]),
        _module("Bigger Marketing", 100, ["marketing"]),
    ]
    out = _format_module_tiers(modules, context_tier=ContextTier.TIER_2, role=None)
    # Header is plain "Modules in scope" — no role label
    assert "## Modules in scope\n" in out
    assert "(role:" not in out
    # Largest module comes first (Bigger Marketing — 100 files)
    bigger_idx = out.index("Bigger Marketing")
    auth_idx = out.index("Auth")
    assert bigger_idx < auth_idx


def test_security_role_promotes_security_modules():
    """With role='security', security-tagged modules float above marketing
    modules even when the marketing module has more files."""
    modules = [
        _module("Marketing Engine", 100, ["marketing", "content", "branding"]),
        _module("Auth Service", 30, ["security", "auth", "token"]),
        _module("Community Outreach", 50, ["marketing", "social"]),
    ]
    role = resolve_role("security")
    out = _format_module_tiers(
        modules, context_tier=ContextTier.TIER_2, role=role,
    )
    # Header now carries the role label
    assert "## Modules in scope (role:" in out

    auth_idx = out.index("Auth Service")
    marketing_idx = out.index("Marketing Engine")
    community_idx = out.index("Community Outreach")

    # Auth (security match) ranks above marketing modules even with fewer files
    assert auth_idx < marketing_idx, (
        "security role should promote auth module above marketing"
    )
    assert auth_idx < community_idx


def test_role_label_uses_display_name():
    """The role label should use the role's human-readable display_name."""
    modules = [_module("Auth", 30, ["security"])]
    role = resolve_role("security")
    out = _format_module_tiers(
        modules, context_tier=ContextTier.TIER_2, role=role,
    )
    # display_name is something like "Security Engineer" — assert it's present
    assert role.display_name in out


def test_unknown_role_falls_back_silently():
    """A RoleVector with empty domain_affinity should not crash, just
    fall back to file-count ordering."""
    from prep.core.atlas.role_vectors import RoleVector

    blank_role = RoleVector(
        role_id="custom",
        display_name="Custom",
        domain_affinity=[],  # no keywords
    )
    modules = [
        _module("Marketing", 100, ["marketing"]),
        _module("Auth", 30, ["security"]),
    ]
    out = _format_module_tiers(
        modules, context_tier=ContextTier.TIER_2, role=blank_role,
    )
    # Marketing ranks first (file_count) since affinity provides no signal
    marketing_idx = out.index("Marketing")
    auth_idx = out.index("Auth")
    assert marketing_idx < auth_idx
    # Header should NOT include role label when affinity is empty
    # (we only label when re-ranking actually happened)
    assert "(role:" not in out


def test_small_and_tiny_tiers_not_reordered():
    """Role re-ranking only touches the significant tier; smaller tiers
    are still rolled into the count-only summary."""
    modules = (
        [_module(f"BigSec{i}", 30, ["security"]) for i in range(2)]
        + [_module(f"BigMkt{i}", 25, ["marketing"]) for i in range(2)]
        + [_module(f"Small{i}", 3, ["random"]) for i in range(5)]
        + [_module(f"Tiny{i}", 1, ["random"]) for i in range(7)]
    )
    role = resolve_role("security")
    out = _format_module_tiers(
        modules, context_tier=ContextTier.TIER_2, role=role,
    )
    # Significant tier: security ranks above marketing
    big_sec_idx = out.index("BigSec0")
    big_mkt_idx = out.index("BigMkt0")
    assert big_sec_idx < big_mkt_idx
    # Small/tiny still emitted as count-only rollups (one-line summaries)
    assert "smaller modules" in out or "single-file modules" in out


def test_role_does_not_drop_marketing_modules():
    """Conservative re-rank: even with role='security', marketing modules
    must still appear in the output (just at the bottom of the tier).
    Don't filter — the user might still need them for context."""
    modules = [
        _module("Auth", 30, ["security"]),
        _module("Marketing", 50, ["marketing"]),
    ]
    role = resolve_role("security")
    out = _format_module_tiers(
        modules, context_tier=ContextTier.TIER_2, role=role,
    )
    # Both modules appear in the output
    assert "Auth" in out
    assert "Marketing" in out
