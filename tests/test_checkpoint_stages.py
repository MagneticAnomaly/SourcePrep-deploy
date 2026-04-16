from codrag.services.pipeline_checkpoint import CHECKPOINT_STAGES, _GOLDEN_FILES, STAGE_OUTPUTS


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
