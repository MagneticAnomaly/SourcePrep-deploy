"""Phase 134 — per-stage cutover tests. Each downstream stage
(augmenter, deepening, epistemic_enrichment, epistemic_score, audit
StalenessAnalyzer) consumes Changeset.should_process(path) and has
no hash comparison logic remaining."""
from __future__ import annotations

import inspect

from prep.services.pipeline.changeset import Changeset


def test_augmenter_uses_changeset_should_process_not_file_hash():
    """The augmenter's per-node 'should I process this' decision
    must consult self.changeset.should_process — not a hash compare.
    Verified by source-code inspection: the file must reference
    'should_process' and the AugmentationEntry field 'file_hash'
    must be absent (the field is deleted in Phase 134).

    Note: 'file_hashes' (plural, the manifest dict) is a separate
    concept and may persist until Task 10 deletes load_file_hashes().
    We check for the singular field name as a standalone token.
    """
    import re
    from prep.core import augmenter

    src = inspect.getsource(augmenter)
    assert "should_process" in src, (
        "augmenter.py must use self.should_process(path) "
        "as the staleness gate"
    )
    # Check the singular field name as a whole word — 'file_hashes' (the
    # manifest dict) is distinct and allowed until Task 10 cleans it up.
    singular_hits = re.findall(r'\bfile_hash\b', src)
    assert not singular_hits, (
        f"augmenter.py must NOT reference file_hash as a standalone token — "
        f"the AugmentationEntry field is deleted in Phase 134. "
        f"Found {len(singular_hits)} occurrences."
    )
    # Also verify the Phase 133 hot-fix helper is no longer imported.
    assert "is_hash_stale" not in src, (
        "augmenter.py must not import is_hash_stale; that helper "
        "is being deleted in Task 12."
    )


def test_augmentation_entry_has_no_file_hash_field():
    """AugmentationEntry's dataclass schema must not include
    file_hash (the field is deleted in Phase 134)."""
    from prep.core.augmenter import AugmentationEntry
    fields = {f.name for f in AugmentationEntry.__dataclass_fields__.values()}
    assert "file_hash" not in fields, (
        f"AugmentationEntry must not have file_hash field; got fields={fields}"
    )


def test_augmenter_skips_unchanged_files_per_changeset():
    """Behavioral: when changeset says a file is unchanged, the
    augmenter's _should_skip returns True (skip — cached entry is
    trusted). When changeset says modified, _should_skip returns
    False (re-process)."""
    from prep.core.augmenter import TraceAugmenter, AugmentationEntry

    cs = Changeset(
        added=frozenset({"new.py"}),
        modified=frozenset({"changed.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"old.py"}),
        run_id="r1",
        base_run_id=None,
    )
    aug = TraceAugmenter.__new__(TraceAugmenter)  # bypass __init__
    aug.changeset = cs

    now = "2026-01-01T00:00:00Z"
    existing = {
        "file:old.py": AugmentationEntry(
            node_id="file:old.py", summary="x",
            role="internal", confidence=0.9,
            augmented_at=now, model="test",
        ),
        "file:changed.py": AugmentationEntry(
            node_id="file:changed.py", summary="y",
            role="internal", confidence=0.9,
            augmented_at=now, model="test",
        ),
    }

    # _should_skip signature: (self, node, existing) -> bool
    # The actual method signature may differ — adapt to whatever
    # TraceAugmenter exposes for the per-node skip decision.
    assert aug._should_skip({"id": "file:old.py", "file_path": "old.py"}, existing) is True
    assert aug._should_skip({"id": "file:changed.py", "file_path": "changed.py"}, existing) is False
