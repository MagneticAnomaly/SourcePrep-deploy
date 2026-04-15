"""Atlas decoration tests: hub labeling + hot zones + flag fallback."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from codrag.core.atlas.generator import (
    _build_hot_zones_line,
    _format_hubs_with_labels,
)


def test_format_hubs_with_labels_groups_by_label():
    hubs = [("typing", 223), ("pathlib", 168), ("backend_config.py", 55)]
    classifier = MagicMock(side_effect=lambda p: {
        "typing": "stable",
        "pathlib": "stable",
        "backend_config.py": "evolving",
    }.get(p, "unknown"))

    line = _format_hubs_with_labels(hubs, classifier)

    assert "stable" in line
    assert "evolving" in line
    assert "typing" in line
    assert "backend_config.py" in line
    # No raw numbers in the labeled form
    assert "223" not in line
    assert "168" not in line


def test_format_hubs_with_labels_falls_back_on_all_unknown():
    """When no evidence, emit today's format (raw edge counts)."""
    hubs = [("typing", 223), ("pathlib", 168)]
    classifier = MagicMock(return_value="unknown")

    line = _format_hubs_with_labels(hubs, classifier)
    # Fallback reproduces the classic "<name> (<n> edges)" shape
    assert "typing" in line
    assert "223 edges" in line


def test_hot_zones_line_empty_when_no_zones():
    assert _build_hot_zones_line([]) == ""


def test_hot_zones_line_formats_paths_as_codespan():
    zones = ["src/foo/", "src/bar/", "src/baz/"]
    line = _build_hot_zones_line(zones)
    assert line.startswith("Active zones")
    assert "src/foo/" in line
    assert "src/bar/" in line
    assert "src/baz/" in line


def test_hub_str_with_evidence_returns_baseline_when_flag_off(monkeypatch):
    """With decoration disabled, _hub_str_with_evidence returns the classic
    `<name> (<n> edges)` format regardless of evidence availability.

    Pins acceptance gate 9 (byte-for-byte baseline parity when flag off).
    """
    # Patch where the symbol is imported INTO the method — inside git_evidence module.
    monkeypatch.setattr(
        "codrag.core.git_evidence.atlas_decoration_enabled",
        lambda: False,
        raising=False,
    )

    from codrag.core.atlas.generator import CodebaseAtlas

    # Build a minimal instance that exposes just the method we need.
    atlas = MagicMock(spec=CodebaseAtlas)
    atlas.project_root = Path("/nonexistent")
    # Bind the real method to the mock instance
    atlas._hub_str_with_evidence = CodebaseAtlas._hub_str_with_evidence.__get__(
        atlas, CodebaseAtlas,
    )

    hubs = [("typing", 223), ("pathlib", 168)]
    result = atlas._hub_str_with_evidence(hubs)
    assert result == "typing (223 edges), pathlib (168 edges)"
