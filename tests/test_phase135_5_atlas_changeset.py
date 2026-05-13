"""Phase 135.5 — stage 11 (atlas) consults the Changeset.

CodebaseAtlas inherits Worker; is_stale() consults self.changeset
instead of computing per-module fingerprints / per-file hashes.
The fingerprint field is gone from AtlasDocument and the per-segment
models.
"""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from prep.core.atlas.generator import CodebaseAtlas
from prep.core.atlas import models as atlas_models
from prep.services.pipeline.changeset import Changeset


@pytest.fixture
def atlas(tmp_path: Path) -> CodebaseAtlas:
    return CodebaseAtlas(tmp_path)


def test_atlas_inherits_worker(atlas: CodebaseAtlas) -> None:
    from prep.services.pipeline.workers.base import Worker
    assert isinstance(atlas, Worker)


def test_atlas_has_changeset_attribute(atlas: CodebaseAtlas) -> None:
    assert atlas.changeset is None


def test_compute_fingerprint_method_deleted() -> None:
    assert not hasattr(CodebaseAtlas, "_compute_fingerprint")


def test_compute_hub_hashes_deleted_if_unused() -> None:
    """If _compute_hub_hashes was only called from the old is_stale
    triggers, it should be gone."""
    assert not hasattr(CodebaseAtlas, "_compute_hub_hashes"), (
        "_compute_hub_hashes survived. Verify nothing else calls it; "
        "if something does, this assertion can be relaxed."
    )


def test_is_stale_no_atlas_yet(atlas: CodebaseAtlas) -> None:
    """No on-disk atlas → always stale (need to generate)."""
    assert not atlas.exists()
    assert atlas.is_stale() is True


def test_is_stale_no_changeset(atlas: CodebaseAtlas, tmp_path: Path) -> None:
    """Atlas exists but no changeset injected → defensive True."""
    # Stub on-disk atlas
    atlas.atlas_path.write_text('{"content": "stub"}')
    assert atlas.exists()
    assert atlas.changeset is None
    assert atlas.is_stale() is True


def test_is_stale_unchanged_changeset(atlas: CodebaseAtlas, tmp_path: Path) -> None:
    """Atlas exists AND changeset has no added/modified/deleted → fresh."""
    atlas.atlas_path.write_text('{"content": "stub"}')
    atlas.changeset = Changeset(
        added=frozenset(),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset({"foo.py", "bar.py"}),
        run_id="r1",
        base_run_id=None,
    )
    assert atlas.is_stale() is False


def test_is_stale_any_churn_marks_stale(atlas: CodebaseAtlas, tmp_path: Path) -> None:
    """Atlas exists, but changeset has SOME churn → stale."""
    atlas.atlas_path.write_text('{"content": "stub"}')
    for partition in ("added", "modified", "deleted"):
        atlas.changeset = Changeset(
            added=frozenset({"x.py"} if partition == "added" else set()),
            modified=frozenset({"x.py"} if partition == "modified" else set()),
            deleted=frozenset({"x.py"} if partition == "deleted" else set()),
            unchanged=frozenset(),
            run_id="r1",
            base_run_id=None,
        )
        assert atlas.is_stale() is True, f"Atlas should be stale when {partition} is non-empty"


def test_fingerprint_field_removed_from_models() -> None:
    """All three atlas dataclasses lost the fingerprint field."""
    # Identify the three classes — look for any dataclass in atlas_models
    # with a 'fingerprint' field. Should be zero.
    candidates = [
        getattr(atlas_models, name) for name in dir(atlas_models)
        if not name.startswith("_")
    ]
    offenders: list[str] = []
    for cls in candidates:
        if hasattr(cls, "__dataclass_fields__"):
            if "fingerprint" in cls.__dataclass_fields__:
                offenders.append(cls.__name__)
    assert not offenders, f"Dataclasses still carrying fingerprint: {offenders}"
