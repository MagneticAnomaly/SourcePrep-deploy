"""
Tests for the atlas_endpoints helpers — Phase 104.

Covers:
- _serialize_segments: empty when atlas has no segments; populated otherwise.
- _build_atlas_response: includes segments key in all cases; stale_override
  bypasses is_stale(); role branch attaches role_atlas when projection succeeds
  and role_atlas_error when it fails.
"""
from __future__ import annotations

from dataclasses import dataclass

from codrag.api.routers.projects import atlas_endpoints as atlas_endpoints_module
from codrag.api.routers.projects.atlas_endpoints import (
    _build_atlas_response,
    _serialize_segments,
)

# ── Fakes ────────────────────────────────────────────────────────────


@dataclass
class _FakeSegment:
    segment_id: str
    segment_name: str
    dir_path: str
    file_count: int
    char_count: int
    mode: str = "structural"
    generated_at: str = "2026-04-14T00:00:00Z"


@dataclass
class _FakeDoc:
    content: str = "root atlas content"
    mode: str = "structural"
    model: str = "structural"
    generated_at: str = "2026-04-14T00:00:00Z"
    file_count: int = 100
    module_count: int = 5
    char_count: int = 1024


class _FakeAtlas:
    """Minimal stand-in for CodebaseAtlas exposing only what the helpers call."""

    def __init__(
        self,
        segments: list[_FakeSegment] | None = None,
        stale: bool = False,
        display: tuple | None = None,
        role_atlas: str | None = None,
        role_error: Exception | None = None,
    ):
        self._segments = segments or []
        self._stale = stale
        self._display = display or ("full display content", 2048)
        self._role_atlas = role_atlas
        self._role_error = role_error

    def has_segments(self) -> bool:
        return bool(self._segments)

    def is_stale(self) -> bool:
        return self._stale

    def load_segments(self) -> list[_FakeSegment]:
        return self._segments

    def get_display_content(self):
        return self._display

    def get_role_atlas(self, role: str, *, overrides=None, pinned_concepts=None) -> str:
        # Phase 104: accept (and ignore for the fake) the override kwargs
        # so helper tests don't need to re-create role_overrides_store.
        if self._role_error:
            raise self._role_error
        return self._role_atlas or ""


# ── _serialize_segments ──────────────────────────────────────────────


def test_serialize_segments_empty_when_no_segments():
    atlas = _FakeAtlas(segments=[])
    assert _serialize_segments(atlas) == []


def test_serialize_segments_returns_expected_fields():
    atlas = _FakeAtlas(
        segments=[
            _FakeSegment(
                segment_id="seg_src_codrag",
                segment_name="src/codrag",
                dir_path="src/codrag",
                file_count=47,
                char_count=2100,
            ),
            _FakeSegment(
                segment_id="seg_packages_ui",
                segment_name="packages/ui",
                dir_path="packages/ui",
                file_count=291,
                char_count=1800,
            ),
        ],
        stale=False,
    )
    out = _serialize_segments(atlas)
    assert len(out) == 2
    assert out[0] == {
        "segment_id": "seg_src_codrag",
        "segment_name": "src/codrag",
        "dir_path": "src/codrag",
        "file_count": 47,
        "char_count": 2100,
        "mode": "structural",
        "generated_at": "2026-04-14T00:00:00Z",
        "stale": False,
    }


def test_serialize_segments_inherits_atlas_level_staleness():
    atlas = _FakeAtlas(
        segments=[
            _FakeSegment("s1", "s1", "s1", 1, 10),
            _FakeSegment("s2", "s2", "s2", 2, 20),
        ],
        stale=True,
    )
    out = _serialize_segments(atlas)
    assert all(s["stale"] is True for s in out)


# ── _build_atlas_response ────────────────────────────────────────────


def test_build_response_always_includes_segments_key():
    atlas = _FakeAtlas(segments=[], stale=False)
    doc = _FakeDoc()
    resp = _build_atlas_response(atlas, doc)
    assert "segments" in resp
    assert resp["segments"] == []
    assert resp["segmented"] is False
    assert resp["exists"] is True


def test_build_response_populates_segments_when_present():
    atlas = _FakeAtlas(
        segments=[_FakeSegment("a", "A", "a", 10, 100)],
        stale=False,
    )
    doc = _FakeDoc()
    resp = _build_atlas_response(atlas, doc)
    assert resp["segmented"] is True
    assert len(resp["segments"]) == 1
    assert resp["segments"][0]["segment_id"] == "a"


def test_build_response_stale_override_wins_over_is_stale():
    atlas = _FakeAtlas(segments=[], stale=True)
    doc = _FakeDoc()
    # stale_override=False (simulating post-regenerate) beats is_stale()==True.
    resp = _build_atlas_response(atlas, doc, stale_override=False)
    assert resp["stale"] is False


def test_build_response_role_attaches_role_atlas():
    atlas = _FakeAtlas(
        segments=[],
        role_atlas="[Software Engineer View]\nmodules...",
    )
    doc = _FakeDoc()
    resp = _build_atlas_response(atlas, doc, role="engineering")
    assert resp["role"] == "engineering"
    assert resp["role_atlas"].startswith("[Software Engineer View]")
    assert resp["role_atlas_chars"] == len(resp["role_atlas"])
    assert "role_atlas_error" not in resp


def test_build_response_role_failure_returns_error_not_projection():
    atlas = _FakeAtlas(
        segments=[],
        role_error=RuntimeError("no enrichment data"),
    )
    doc = _FakeDoc()
    resp = _build_atlas_response(atlas, doc, role="engineering")
    assert resp["role_atlas_error"] == "no enrichment data"
    assert "role_atlas" not in resp


def test_build_response_uses_display_content_when_available():
    atlas = _FakeAtlas(display=("concatenated display", 999))
    doc = _FakeDoc(content="root only", char_count=50)
    resp = _build_atlas_response(atlas, doc)
    assert resp["content"] == "concatenated display"
    assert resp["char_count"] == 999


def test_build_response_falls_back_to_doc_content_when_no_display():
    atlas = _FakeAtlas(display=("", 0))
    doc = _FakeDoc(content="root only", char_count=50)
    resp = _build_atlas_response(atlas, doc)
    assert resp["content"] == "root only"
    assert resp["char_count"] == 50


# ── Route-level smoke tests ──────────────────────────────────────────


def test_get_atlas_route_when_no_atlas_returns_exists_false_with_empty_segments(monkeypatch):
    """The doc-is-None branch of the GET route is not covered by helper tests.

    Ensures the route returns the short payload shape (exists/content/stale/
    segments) rather than calling the helper when there is no cached atlas.
    """
    class _NullAtlas:
        def __init__(self, *args, **kwargs):
            pass

        def load(self):
            return None

    # Fake the required service pieces — route only needs _require_project
    # to succeed and a CodebaseAtlas that returns None from load().
    class _FakeProject:
        path = "/tmp/fake"

    class _FakeSrv:
        def _require_project(self, pid):
            return _FakeProject()

    monkeypatch.setattr(atlas_endpoints_module, "_srv", lambda: _FakeSrv())
    monkeypatch.setattr(atlas_endpoints_module, "project_index_dir", lambda _p: "/tmp/idx")

    # The function imports CodebaseAtlas lazily inside the handler — patch the
    # symbol that the import resolves to.
    import codrag.core.atlas as atlas_pkg
    monkeypatch.setattr(atlas_pkg, "CodebaseAtlas", _NullAtlas)

    body = atlas_endpoints_module.get_atlas("proj-id", role=None)
    # ok() wraps under {"success": True, "data": ...}
    data = body["data"] if "data" in body else body
    assert data["exists"] is False
    assert data["content"] is None
    assert data["stale"] is True
    assert data["segments"] == []


def test_get_atlas_route_when_atlas_exists_returns_full_payload(monkeypatch):
    """Happy path — route calls the helper, response has segments key."""
    loaded_doc = _FakeDoc()
    fake = _FakeAtlas(
        segments=[_FakeSegment("s1", "S1", "s1", 10, 100)],
        stale=False,
    )

    class _AtlasFactory:
        def __init__(self, *args, **kwargs):
            self._inner = fake

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def load(self):
            return loaded_doc

    class _FakeProject:
        path = "/tmp/fake"

    class _FakeSrv:
        def _require_project(self, pid):
            return _FakeProject()

    monkeypatch.setattr(atlas_endpoints_module, "_srv", lambda: _FakeSrv())
    monkeypatch.setattr(atlas_endpoints_module, "project_index_dir", lambda _p: "/tmp/idx")

    import codrag.core.atlas as atlas_pkg
    monkeypatch.setattr(atlas_pkg, "CodebaseAtlas", _AtlasFactory)

    body = atlas_endpoints_module.get_atlas("proj-id", role=None)
    data = body["data"] if "data" in body else body
    assert data["exists"] is True
    assert data["segmented"] is True
    assert len(data["segments"]) == 1
    assert data["segments"][0]["segment_id"] == "s1"
