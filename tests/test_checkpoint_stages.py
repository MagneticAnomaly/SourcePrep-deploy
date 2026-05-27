from prep.services.pipeline_checkpoint import (
    CHECKPOINT_STAGES,
    STAGE_OUTPUTS,
    TRACE_FILES,
    _GOLDEN_FILES,
)


def test_checkpoint_stages_covers_all_15_pipeline_stages():
    """Every pipeline stage should be checkpoint-eligible.

    Missing stages cannot be recovered by the selfheal path or per-stage
    restore, which is the gap closed by Phase 114.
    """
    expected = {
        "structural", "inferred_edges", "catalogue", "validation", "knowledge",
        "enrichment", "group_reasoning", "clustering", "deepening", "deep_knowledge",
        "atlas", "rules", "concepts", "audit", "antibodies",
    }
    assert expected.issubset(CHECKPOINT_STAGES), (
        f"missing from CHECKPOINT_STAGES: {expected - CHECKPOINT_STAGES}"
    )


def test_golden_files_includes_finalize_tail_manifests():
    needed = {
        "rules_manifest.json",
        "concepts_manifest.json",
        "audit_manifest.json",
        "antibodies_manifest.json",
    }
    assert needed.issubset(set(_GOLDEN_FILES)), (
        f"missing from _GOLDEN_FILES: {needed - set(_GOLDEN_FILES)}"
    )


def test_stage_outputs_has_entries_for_finalize_tail():
    for stage in ("rules", "concepts", "audit", "antibodies"):
        assert stage in STAGE_OUTPUTS, f"STAGE_OUTPUTS missing {stage}"
        assert STAGE_OUTPUTS[stage], f"STAGE_OUTPUTS[{stage}] is empty"


def test_stage_outputs_includes_group_reasoning():
    """Regression for 2026-05-27 silent data loss.

    Before this guard, ``group_reasoning`` had no STAGE_OUTPUTS entry and
    ``trace_group_reasoning.jsonl`` was absent from TRACE_FILES.  Result:
    ``create_checkpoint`` skipped the file and ``restore_checkpoint``
    silently no-op'd it.  When the swarm hit its wall-time cap and wrote
    61 of 166 expected records, IntegrityGuard's recovery logged
    "RESTORED 10 files from checkpoint" — none of the 10 was the
    shrunken file — and the stage advanced as "completed" with
    corrupted data.
    """
    assert "group_reasoning" in STAGE_OUTPUTS, (
        "STAGE_OUTPUTS missing group_reasoning — checkpoint/restore "
        "cannot protect its output file. See pipeline_checkpoint.py "
        "header comment for the incident this guards against."
    )
    files = set(STAGE_OUTPUTS["group_reasoning"])
    assert "trace_group_reasoning.jsonl" in files, (
        f"STAGE_OUTPUTS[group_reasoning] must include "
        f"trace_group_reasoning.jsonl, got {files}"
    )


def test_trace_files_covers_every_stage_output():
    """Every file in STAGE_OUTPUTS values must appear in TRACE_FILES.

    ``create_checkpoint`` and ``restore_checkpoint`` both iterate
    TRACE_FILES — anything outside that list is unprotected by the
    per-run rollback path, even if it appears in STAGE_OUTPUTS.

    Finalize-tail manifests are exempt because finalize stages are not
    expected to be rolled back via the checkpoint path (they re-run
    cheaply); they live in _GOLDEN_FILES for the longer-lived backup.
    """
    finalize_tail_exempt = {
        "rules_manifest.json",
        "concepts_manifest.json",
        "audit_manifest.json",
        "antibodies_manifest.json",
        # Atlas writes go through a separate atomic-swap path and are
        # not covered by the per-stage checkpoint either.
        "atlas.json",
        "atlas_prev.json",
        "atlas_segments_manifest.json",
        "atlas_routing.json",
        "atlas_routing_embeddings.npy",
    }
    trace_set = set(TRACE_FILES)
    missing: dict[str, list[str]] = {}
    for stage, files in STAGE_OUTPUTS.items():
        gaps = [f for f in files if f not in trace_set and f not in finalize_tail_exempt]
        if gaps:
            missing[stage] = gaps
    assert not missing, (
        f"STAGE_OUTPUTS files not in TRACE_FILES (per-run checkpoint "
        f"cannot protect them): {missing}. Either add them to "
        f"TRACE_FILES or extend the exemption set with rationale."
    )


def test_golden_files_covers_every_stage_output():
    """Golden snapshot must cover every stage output file.

    The 2026-05-27 incident also exposed that ``trace_group_reasoning.jsonl``
    was in _GOLDEN_FILES but its manifest sibling was named wrong
    (``trace_group_reasoning_manifest.json`` instead of the actual
    ``group_reasoning_manifest.json``), so golden never actually
    snapshotted the manifest either.
    """
    golden_set = set(_GOLDEN_FILES)
    missing: dict[str, list[str]] = {}
    for stage, files in STAGE_OUTPUTS.items():
        gaps = [f for f in files if f not in golden_set]
        if gaps:
            missing[stage] = gaps
    assert not missing, (
        f"STAGE_OUTPUTS files not in _GOLDEN_FILES: {missing}. "
        f"Long-lived backups (golden snapshot) cannot protect them."
    )
