"""Atlas decoration tests: hub labeling + hot zones + flag fallback."""
from __future__ import annotations

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
