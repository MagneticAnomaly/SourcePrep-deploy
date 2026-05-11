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


def test_deepening_uses_changeset_not_file_hash():
    from prep.core import deepening
    import re
    src = inspect.getsource(deepening)
    assert "should_process" in src, (
        "deepening.py must consult changeset.should_process for stale_set"
    )
    # Token-boundary check (avoid matching the word in a docstring like
    # "the file_hash field is gone").
    # Find any actual code references (not in a comment line).
    for lineno, line in enumerate(src.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        # Inside a method body — file_hash should not appear as a name
        # being accessed or assigned.
        if re.search(r'\bfile_hash\b', line) and "Phase 134" not in line:
            assert False, (
                f"deepening.py line {lineno} still references file_hash:\n  {line}"
            )
    assert "is_hash_stale" not in src
    assert "_load_manifest_hashes" not in src, (
        "_load_manifest_hashes is deleted in Phase 134 — staleness "
        "comes from the changeset, not from a per-stage manifest read"
    )
    assert "_load_file_hashes" not in src, (
        "_load_file_hashes is deleted in Phase 134 — staleness "
        "comes from the changeset, not from manifest file hash reads"
    )


def test_deepening_stale_set_from_changeset():
    """The stale_set in DriftDetector comes from changeset.modified |
    changeset.deleted (NOT from a hash comparison). Pre-Phase-134
    stale_set was the set of nodes whose stored aug.file_hash differed
    from the manifest's current_hash. Post-Phase-134 stale_set is the
    set of nodes whose file_path is in changeset.modified | deleted."""
    import prep.core.deepening as deepening_mod

    cs = Changeset(
        added=frozenset(),
        modified=frozenset({"changed.py"}),
        deleted=frozenset({"gone.py"}),
        unchanged=frozenset({"old.py"}),
        run_id="r1",
        base_run_id=None,
    )
    # Find the class with _compute_stale_set
    cls = None
    for name in dir(deepening_mod):
        obj = getattr(deepening_mod, name)
        if isinstance(obj, type) and hasattr(obj, "_compute_stale_set"):
            cls = obj
            break
    assert cls is not None, (
        "deepening module must expose a class with _compute_stale_set "
        "method (the Phase 134 changeset-driven stale-set helper)"
    )
    worker = cls.__new__(cls)
    worker.changeset = cs

    augmentations = {
        "file:changed.py": {"node_id": "file:changed.py"},
        "file:gone.py": {"node_id": "file:gone.py"},
        "file:old.py": {"node_id": "file:old.py"},
    }
    stale = worker._compute_stale_set(augmentations)
    assert "file:changed.py" in stale  # in changeset.modified
    assert "file:gone.py" in stale     # in changeset.deleted (orphan)
    assert "file:old.py" not in stale  # in changeset.unchanged


def test_epistemic_enrichment_uses_changeset_not_file_hash():
    from prep.core import epistemic_enrichment
    import re
    src = inspect.getsource(epistemic_enrichment)
    assert "should_process" in src
    # Token-boundary check
    for lineno, line in enumerate(src.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        if re.search(r'\bfile_hash\b', line) and "Phase 134" not in line:
            assert False, (
                f"epistemic_enrichment.py line {lineno} still references file_hash:\n  {line}"
            )
    assert "is_hash_stale" not in src
    # The lambda/method that loaded manifest hashes is gone.
    assert 'manifest.get("file_hashes"' not in src and "manifest.get('file_hashes'" not in src, (
        "epistemic_enrichment.py must not read manifest.file_hashes — "
        "staleness is in the changeset, not the manifest"
    )


def test_epistemic_enrichment_is_stale_uses_changeset():
    """EpistemicEnricher._needs_enrichment returns True iff the file_path is
    in changeset.modified (need re-enrichment) — never from a hash
    compare."""
    from prep.core.epistemic_enrichment import EpistemicEnricher

    cs = Changeset(
        added=frozenset({"new.py"}),
        modified=frozenset({"changed.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"old.py"}),
        run_id="r1",
        base_run_id=None,
    )
    enricher = EpistemicEnricher.__new__(EpistemicEnricher)
    enricher.changeset = cs
    # Provide minimal augmentations so _needs_enrichment's "is the file
    # already enriched" check has something to look at.
    augmentations = {
        "file:changed.py": {"node_id": "file:changed.py"},
        "file:old.py": {"node_id": "file:old.py"},
    }

    # Simulate that both nodes have existing enrichment entries (so we test
    # the stale branch, not the "not yet enriched" branch).
    from prep.core.epistemic_score import EpistemicEntry
    existing = {
        "file:changed.py": EpistemicEntry(
            node_id="file:changed.py",
            extended_summary="x",
            domain_tags=[],
            architecture_layer="unknown",
        ),
        "file:old.py": EpistemicEntry(
            node_id="file:old.py",
            extended_summary="y",
            domain_tags=[],
            architecture_layer="unknown",
        ),
    }

    # _needs_enrichment(node, existing, augmentations) -> bool
    # changed.py is in changeset.modified → needs re-enrichment
    assert enricher._needs_enrichment(
        {"id": "file:changed.py", "file_path": "changed.py"}, existing, augmentations
    ) is True
    # old.py is in changeset.unchanged → skip
    assert enricher._needs_enrichment(
        {"id": "file:old.py", "file_path": "old.py"}, existing, augmentations
    ) is False
