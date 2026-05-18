"""Phase 136 Part 11 regression — atlas reports Stale immediately after
rebuild because is_stale() never checked whether the changeset had
already been consumed.  See docs/Phase136_Dogfood-fixes/Part11_*.

Failure mode: 2026-05-17 dashboard screenshot showed all 10 sub-atlases
as Stale 90s after a successful rebuild.  Root cause was that the
churn check (`bool(cs.added) or bool(cs.modified) or bool(cs.deleted)`)
trips on every non-empty build because the initial-scan changeset has
1971 files in `added`.
"""
from __future__ import annotations

import json
from pathlib import Path

from prep.core.atlas.generator import CodebaseAtlas
from prep.core.atlas.models import AtlasDocument
from prep.services.pipeline.changeset import Changeset


def _write_atlas(idx_dir: Path, consumed_run_id: str) -> None:
    """Write a minimal AtlasDocument JSON with the given consumed run_id."""
    doc = AtlasDocument(
        content="test",
        generated_at="2026-05-17T20:13:00Z",
        model="structural",
        file_count=10,
        module_count=2,
        char_count=4,
        mode="structural",
        consumed_changeset_run_id=consumed_run_id,
    )
    (idx_dir / "atlas.json").write_text(json.dumps(doc.to_dict()))


def _make_changeset(run_id: str, added: tuple[str, ...] = ()) -> Changeset:
    return Changeset(
        added=frozenset(added),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset(),
        run_id=run_id,
        base_run_id=None,
    )


def test_is_stale_false_when_run_ids_match(tmp_path: Path) -> None:
    """Fresh atlas built from changeset X must not report stale against
    changeset X with churn still in `added`.  This is the regression case."""
    _write_atlas(tmp_path, consumed_run_id="run-AAAA")
    atlas = CodebaseAtlas(index_dir=tmp_path, project_root=tmp_path)
    atlas.changeset = _make_changeset("run-AAAA", added=("a.py", "b.py"))
    assert atlas.is_stale() is False


def test_is_stale_true_when_changeset_run_id_advances(tmp_path: Path) -> None:
    """A new pipeline run produces a new changeset run_id; atlas built
    against the old run_id must report stale."""
    _write_atlas(tmp_path, consumed_run_id="run-AAAA")
    atlas = CodebaseAtlas(index_dir=tmp_path, project_root=tmp_path)
    atlas.changeset = _make_changeset("run-BBBB", added=("a.py",))
    assert atlas.is_stale() is True


def test_is_stale_true_when_atlas_missing(tmp_path: Path) -> None:
    """No atlas on disk → always stale."""
    atlas = CodebaseAtlas(index_dir=tmp_path, project_root=tmp_path)
    atlas.changeset = _make_changeset("run-X")
    assert atlas.is_stale() is True


def test_is_stale_falls_back_to_churn_for_pre_phase_136_atlas(tmp_path: Path) -> None:
    """Pre-Phase-136 atlas (no consumed_changeset_run_id stamp).  When
    the changeset shows churn, fall back to the legacy churn check →
    stale.  This is the safe-degradation path."""
    # Write an atlas without the stamp (simulates an old build).
    (tmp_path / "atlas.json").write_text(json.dumps({
        "content": "old",
        "generated_at": "2026-04-01T00:00:00Z",
        "model": "structural",
        "file_count": 1,
        "module_count": 1,
        "char_count": 3,
        "mode": "structural",
        # consumed_changeset_run_id intentionally omitted
    }))
    atlas = CodebaseAtlas(index_dir=tmp_path, project_root=tmp_path)
    atlas.changeset = _make_changeset("run-NEW", added=("a.py",))
    assert atlas.is_stale() is True


def test_save_stamps_consumed_changeset_run_id(tmp_path: Path) -> None:
    """`_save()` must stamp the current changeset's run_id onto the doc
    before persistence.  After a save, the on-disk atlas carries the
    correct stamp and is_stale returns False against the same changeset."""
    atlas = CodebaseAtlas(index_dir=tmp_path, project_root=tmp_path)
    atlas.changeset = _make_changeset("run-CONSUMED", added=("a.py", "b.py"))

    doc = AtlasDocument(
        content="just built",
        generated_at="2026-05-17T20:13:25Z",
        model="structural",
        file_count=2,
        module_count=1,
        char_count=10,
        mode="structural",
    )
    atlas._save(doc)

    # Verify the stamp landed on disk.
    on_disk = json.loads((tmp_path / "atlas.json").read_text())
    assert on_disk["consumed_changeset_run_id"] == "run-CONSUMED"

    # is_stale against the SAME changeset must now return False.
    assert atlas.is_stale() is False
