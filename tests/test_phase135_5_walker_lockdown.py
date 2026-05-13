"""Phase 135.5 lockdown — no file outside prep.core.walker may import
prep_engine for walking. If you re-introduce a direct prep_engine
import or walk_repo call, this test fails — by design.

Exempt:
- src/prep/core/walker.py — the sanctioned wrapper.
- src/prep/core/trace/builder.py — uses prep_engine.hash_content (NOT
  walk_repo). Hash primitives are not in scope for Phase 135.5; the
  walker-only lockdown allows other prep_engine surfaces.
- test files (not in SRC).
"""
from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "prep"


def test_no_direct_walk_repo_calls_outside_walker_module() -> None:
    """prep_engine.walk_repo may only be called from prep.core.walker."""
    walker = SRC / "core" / "walker.py"
    offenders: list[str] = []
    for py in SRC.rglob("*.py"):
        if py.resolve() == walker.resolve():
            continue
        body = py.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(body.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Only flag actual code calls (not comments, not inside string literals)
            if "prep_engine.walk_repo(" in stripped or "_prep_engine.walk_repo(" in stripped:
                offenders.append(f"{py.relative_to(SRC.parents[1])}:{i}: {stripped}")
    assert not offenders, (
        "Direct prep_engine.walk_repo calls outside prep.core.walker are "
        "banned by Phase 135.5. Offenders:\n  " + "\n  ".join(offenders)
    )


def test_walker_module_is_the_walker_module() -> None:
    """Smoke check: prep.core.walker DOES import prep_engine and calls walk_repo."""
    walker = SRC / "core" / "walker.py"
    assert walker.exists(), "Expected sanctioned walker module not found"
    body = walker.read_text(encoding="utf-8")
    assert "import prep_engine" in body, "walker.py must import prep_engine"
    assert "walk_repo" in body, "walker.py must call walk_repo somewhere"


def test_no_walk_repo_imports_via_from_syntax() -> None:
    """Belt-and-suspenders: no `from prep_engine import walk_repo` form anywhere."""
    walker = SRC / "core" / "walker.py"
    offenders: list[str] = []
    for py in SRC.rglob("*.py"):
        if py.resolve() == walker.resolve():
            continue
        body = py.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(body.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith("from prep_engine") and "walk_repo" in stripped:
                offenders.append(f"{py.relative_to(SRC.parents[1])}:{i}: {stripped}")
    assert not offenders, (
        "`from prep_engine import walk_repo` is also banned. Offenders:\n  "
        + "\n  ".join(offenders)
    )
