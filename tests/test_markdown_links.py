"""Tests for prep.core.atlas.markdown_links (Phase 124 T2).

Covers the deterministic path-extraction + validation contract.
Per project convention: at least one test exercises the real
filesystem walk + validation seam (no mocks on the parser).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prep.core.atlas.markdown_links import (
    MarkdownLinkResult,
    _extract_candidates,
    aggregate_for_segments,
    docs_for_module,
    extract,
    extract_excerpt,
    load,
    reverse_index,
    save,
)


# ──────────────────────────────────────────────────────────────────────
# Pure extractor (no I/O)
# ──────────────────────────────────────────────────────────────────────

def test_extract_bare_path_mention():
    text = "Look at src/prep/core/atlas/routing.py for the segmentation logic."
    assert "src/prep/core/atlas/routing.py" in _extract_candidates(text)


def test_extract_markdown_link_target():
    text = "See the [routing module](src/prep/core/atlas/routing.py)."
    assert "src/prep/core/atlas/routing.py" in _extract_candidates(text)


def test_extract_inline_code_span():
    text = "The function lives in `src/prep/core/audit/runner.py`."
    assert "src/prep/core/audit/runner.py" in _extract_candidates(text)


def test_external_urls_ignored():
    text = "[docs](https://example.com/path/file.py) and [foo](http://x.io/y.ts)"
    cands = _extract_candidates(text)
    # URLs themselves drop; only the file extensions in slugs survive
    # — but the leading "https://" is filtered upstream.
    assert not any(c.startswith("http") for c in cands)


def test_anchor_fragments_stripped():
    text = "see [link](src/prep/foo.py#L42)"
    assert "src/prep/foo.py" in _extract_candidates(text)


def test_bare_filename_without_directory_filtered():
    # Bare names like "package.json" or "README.md" are too noisy.
    text = "Edit package.json and README.md"
    cands = _extract_candidates(text)
    assert "package.json" not in cands
    assert "README.md" not in cands


def test_dot_slash_prefix_normalized():
    text = "Check `./src/prep/foo.py`"
    cands = _extract_candidates(text)
    assert "src/prep/foo.py" in cands
    assert "./src/prep/foo.py" not in cands


# ──────────────────────────────────────────────────────────────────────
# Filesystem-validated extract
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def tiny_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "real.py").write_text("# real\n")
    (tmp_path / "src" / "other.py").write_text("# other\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "design.md").write_text(
        "Design doc.\n\n"
        "The implementation is in `src/real.py`.\n"
        "It depends on [other](src/other.py).\n"
        "We tried src/missing.py but it didn't work.\n"
    )
    (docs / "self_ref.md").write_text("This is `docs/self_ref.md` itself.\n")
    return tmp_path


def test_extract_validates_against_filesystem(tiny_repo: Path):
    result = extract(tiny_repo)
    assert result.md_count == 1  # only design.md has valid links
    files = result.md_to_files["docs/design.md"]
    assert "src/real.py" in files
    assert "src/other.py" in files
    assert "src/missing.py" not in files  # filesystem validation drops it


def test_self_reference_filtered(tiny_repo: Path):
    result = extract(tiny_repo)
    assert "docs/self_ref.md" not in result.md_to_files


def test_extract_validates_against_indexed_set(tiny_repo: Path):
    # Pretend only src/real.py is indexed; src/other.py exists on
    # disk but isn't in the trace graph.
    indexed = {"src/real.py"}
    result = extract(tiny_repo, indexed_files=indexed)
    files = result.md_to_files["docs/design.md"]
    assert files == ["src/real.py"]


def test_extract_handles_missing_root(tmp_path: Path):
    result = extract(tmp_path / "does_not_exist")
    assert result.md_count == 0
    assert result.md_to_files == {}


def test_walk_excludes_noise_dirs(tmp_path: Path):
    # .claude/worktrees and node_modules shouldn't be walked.
    for noise in (".claude", "node_modules", ".git", ".venv"):
        (tmp_path / noise).mkdir()
        (tmp_path / noise / "leak.md").write_text("`src/foo.py`\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("")
    (tmp_path / "real.md").write_text("`src/foo.py`\n")
    result = extract(tmp_path)
    assert "real.md" in result.md_to_files
    for noise in (".claude", "node_modules", ".git", ".venv"):
        assert f"{noise}/leak.md" not in result.md_to_files


# ──────────────────────────────────────────────────────────────────────
# Persistence round-trip
# ──────────────────────────────────────────────────────────────────────

def test_save_load_roundtrip(tmp_path: Path):
    result = MarkdownLinkResult(
        md_to_files={"docs/a.md": ["src/x.py", "src/y.py"]},
        extracted_at="2026-05-01T00:00:00Z",
        project_root=str(tmp_path),
        md_count=1,
        valid_link_count=2,
        raw_mention_count=5,
    )
    out_path = save(result, tmp_path)
    assert out_path.is_file()
    data = json.loads(out_path.read_text())
    assert data["schema_version"] == 1
    loaded = load(tmp_path)
    assert loaded is not None
    assert loaded.md_to_files == result.md_to_files
    assert loaded.md_count == 1


def test_load_returns_none_when_missing(tmp_path: Path):
    assert load(tmp_path) is None


# ──────────────────────────────────────────────────────────────────────
# Consumer helpers
# ──────────────────────────────────────────────────────────────────────

def test_reverse_index_groups_by_code_file():
    result = MarkdownLinkResult(
        md_to_files={
            "docs/a.md": ["src/x.py", "src/y.py"],
            "docs/b.md": ["src/x.py"],
        },
    )
    rev = reverse_index(result)
    assert rev["src/x.py"] == ["docs/a.md", "docs/b.md"]
    assert rev["src/y.py"] == ["docs/a.md"]


def test_docs_for_module_ranks_by_overlap():
    result = MarkdownLinkResult(
        md_to_files={
            "docs/most.md":  ["src/a.py", "src/b.py", "src/c.py"],
            "docs/some.md":  ["src/a.py", "src/b.py"],
            "docs/one.md":   ["src/a.py"],
            "docs/none.md":  ["src/d.py"],
        },
    )
    out = docs_for_module(result, member_files={"src/a.py", "src/b.py", "src/c.py"})
    assert out == ["docs/most.md", "docs/some.md", "docs/one.md"]
    assert "docs/none.md" not in out


def test_docs_for_module_cap_respected():
    result = MarkdownLinkResult(
        md_to_files={
            f"docs/{i}.md": ["src/a.py"] for i in range(10)
        },
    )
    assert len(docs_for_module(result, ["src/a.py"], cap=3)) == 3


def test_docs_for_module_empty_members_returns_empty():
    result = MarkdownLinkResult(
        md_to_files={"docs/a.md": ["src/x.py"]},
    )
    assert docs_for_module(result, member_files=[]) == []


# ──────────────────────────────────────────────────────────────────────
# Excerpt extractor
# ──────────────────────────────────────────────────────────────────────

def test_extract_excerpt_returns_window_around_mention(tmp_path: Path):
    md = tmp_path / "doc.md"
    md.write_text(
        "Header\n\n"
        "Some unrelated paragraph one.\n"
        "Some unrelated paragraph two.\n"
        "The bug is in src/foo.py — see line 42.\n"
        "Cause is the cache invalidation.\n"
        "Resolution: clear the cache.\n"
        "More unrelated text.\n"
    )
    excerpt = extract_excerpt(md, ["src/foo.py"], window_lines=2, max_chars=500)
    assert "src/foo.py" in excerpt
    assert "cache invalidation" in excerpt
    assert "Header" not in excerpt  # outside the window


def test_extract_excerpt_empty_when_no_mention(tmp_path: Path):
    md = tmp_path / "doc.md"
    md.write_text("Nothing relevant here.\n")
    assert extract_excerpt(md, ["src/foo.py"]) == ""


def test_extract_excerpt_empty_when_file_missing(tmp_path: Path):
    assert extract_excerpt(tmp_path / "no_such.md", ["src/foo.py"]) == ""


def test_extract_excerpt_truncates_to_max_chars(tmp_path: Path):
    md = tmp_path / "doc.md"
    body = "src/foo.py is mentioned here.\n" + ("filler line\n" * 100)
    md.write_text(body)
    out = extract_excerpt(md, ["src/foo.py"], window_lines=50, max_chars=200)
    assert len(out) <= 250  # max + truncation marker tolerance
    assert out.endswith("…")


# ──────────────────────────────────────────────────────────────────────
# Segment aggregator (Phase 124 T3)
# ──────────────────────────────────────────────────────────────────────

def test_aggregate_for_segments_basic():
    md = MarkdownLinkResult(
        md_to_files={
            "docs/ui.md":   ["packages/ui/Card.tsx", "packages/ui/Button.tsx"],
            "docs/dash.md": ["src/prep/dashboard/App.tsx"],
            "docs/none.md": ["unindexed/missing.py"],
        },
    )
    manifest = [
        {"id": "ui",   "file_paths": ["packages/ui/Card.tsx", "packages/ui/Button.tsx"]},
        {"id": "dash", "file_paths": ["src/prep/dashboard/App.tsx"]},
    ]
    out = aggregate_for_segments(md, manifest, cap=5)
    assert "ui" in out and "dash" in out
    assert out["ui"][0]["path"] == "docs/ui.md"
    assert out["ui"][0]["mention_count"] == 2
    assert out["dash"][0]["path"] == "docs/dash.md"


def test_aggregate_for_segments_caps_results():
    md = MarkdownLinkResult(
        md_to_files={
            f"docs/d{i}.md": ["src/x.py"]
            for i in range(20)
        },
    )
    manifest = [{"id": "s", "file_paths": ["src/x.py"]}]
    out = aggregate_for_segments(md, manifest, cap=3)
    assert len(out["s"]) == 3


def test_aggregate_for_segments_handles_missing_or_malformed():
    md = MarkdownLinkResult(md_to_files={"docs/a.md": ["src/x.py"]})
    # Empty manifest
    assert aggregate_for_segments(md, []) == {}
    # Segment with no file_paths
    assert aggregate_for_segments(md, [{"id": "empty"}]) == {"empty": []}
    # Segment with no id
    assert aggregate_for_segments(md, [{"file_paths": ["src/x.py"]}]) == {}


def test_aggregate_for_segments_ranks_by_overlap():
    md = MarkdownLinkResult(
        md_to_files={
            "docs/most.md":  ["src/a.py", "src/b.py", "src/c.py"],
            "docs/some.md":  ["src/a.py", "src/b.py"],
            "docs/one.md":   ["src/a.py"],
        },
    )
    manifest = [
        {"id": "s", "file_paths": ["src/a.py", "src/b.py", "src/c.py"]},
    ]
    out = aggregate_for_segments(md, manifest)
    paths = [d["path"] for d in out["s"]]
    assert paths == ["docs/most.md", "docs/some.md", "docs/one.md"]


def test_aggregate_for_segments_supports_segment_id_alias():
    """Manifest may use either ``id`` or ``segment_id`` — both must work."""
    md = MarkdownLinkResult(md_to_files={"docs/a.md": ["src/x.py"]})
    out = aggregate_for_segments(
        md,
        [{"segment_id": "alt", "file_paths": ["src/x.py"]}],
    )
    assert "alt" in out
    assert out["alt"][0]["path"] == "docs/a.md"


def test_extract_excerpt_merges_overlapping_windows(tmp_path: Path):
    md = tmp_path / "doc.md"
    md.write_text(
        "Pre-context\n"
        "src/foo.py first mention\n"
        "Middle context line one\n"
        "Middle context line two\n"
        "src/foo.py second mention\n"
        "Tail line\n"
    )
    out = extract_excerpt(
        md, ["src/foo.py"],
        window_lines=2, max_chars=1000, section_aware=False,
    )
    # Both mentions captured; no separator because windows overlap
    assert "first mention" in out
    assert "second mention" in out
    assert "…\n" not in out  # merged, no ellipsis between


# ──────────────────────────────────────────────────────────────────────
# Section-aware excerpt extractor (Phase 124 T10)
# ──────────────────────────────────────────────────────────────────────

def test_extract_excerpt_section_aware_picks_enclosing_section(tmp_path: Path):
    md = tmp_path / "doc.md"
    md.write_text(
        "# Top header\n\n"
        "Intro text not relevant.\n\n"
        "## Section A\n\n"
        "Some prose about A. The implementation is in src/foo.py.\n"
        "More A prose.\n\n"
        "## Section B\n\n"
        "Other prose unrelated.\n"
    )
    out = extract_excerpt(md, ["src/foo.py"], max_chars=2000)
    # Section A surfaces fully; Section B excluded
    assert "Section A" in out
    assert "Some prose about A" in out
    assert "More A prose" in out
    assert "Section B" not in out
    assert "Other prose unrelated" not in out


def test_extract_excerpt_section_aware_merges_adjacent_sections(tmp_path: Path):
    md = tmp_path / "doc.md"
    md.write_text(
        "## A\n\nMention 1: src/foo.py\n\n"
        "## B\n\nMention 2: src/foo.py\n\n"
        "## C\n\nUnrelated tail.\n"
    )
    out = extract_excerpt(md, ["src/foo.py"], max_chars=2000)
    # Both A and B surface; C excluded
    assert "Mention 1" in out
    assert "Mention 2" in out
    assert "Unrelated tail" not in out


def test_extract_excerpt_section_aware_falls_back_when_no_headers(tmp_path: Path):
    md = tmp_path / "doc.md"
    md.write_text(
        "Line 1\nLine 2\nMention src/foo.py here\nLine 4\nLine 5\n"
    )
    out = extract_excerpt(md, ["src/foo.py"], window_lines=1, max_chars=2000)
    # Falls back to line-window when no headers present
    assert "Mention src/foo.py here" in out
    # Window is ±1 so we get Line 2 + hit + Line 4 (Line 1 / Line 5 outside)
    assert "Line 2" in out
    assert "Line 4" in out


def test_extract_excerpt_section_aware_truncates_at_line_boundary(tmp_path: Path):
    md = tmp_path / "doc.md"
    section = "padding line\n" * 60
    md.write_text(
        f"## Big section\n\nsrc/foo.py mentioned here.\n{section}\n"
    )
    out = extract_excerpt(md, ["src/foo.py"], max_chars=200)
    assert len(out) <= 250  # max + truncation marker
    assert out.endswith("…")
    assert "src/foo.py mentioned here" in out


def test_extract_excerpt_explicit_line_window_mode(tmp_path: Path):
    """Callers can opt out of section-aware extraction."""
    md = tmp_path / "doc.md"
    md.write_text(
        "## Big section header\n\n"
        "Line A\nLine B\nMention src/foo.py here\nLine D\nLine E\n"
        + ("trailing line\n" * 50)
    )
    out_section = extract_excerpt(md, ["src/foo.py"], max_chars=2000, section_aware=True)
    out_window = extract_excerpt(md, ["src/foo.py"], window_lines=1, max_chars=2000, section_aware=False)
    # Section mode includes more context; window mode is tighter
    assert len(out_section) > len(out_window)
    assert "trailing line" in out_section  # included in big section
    assert "trailing line" not in out_window  # outside ±1 window
