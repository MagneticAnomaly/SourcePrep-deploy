"""STAGE_OUTPUTS registry + build_keep_set integrity."""
from __future__ import annotations

import pytest

from prep.services.pipeline.stages import (
    STAGE_OUTPUTS, PROJECT_META_ALLOWLIST, build_keep_set,
    StageId, FAST_SYNC_STAGES, DEEP_ENRICHMENT_STAGES, FINALIZE_STAGES,
)


def test_every_stage_has_outputs_entry() -> None:
    expected = set(FAST_SYNC_STAGES) | set(DEEP_ENRICHMENT_STAGES) | set(FINALIZE_STAGES)
    assert set(STAGE_OUTPUTS.keys()) == expected


def test_keep_set_for_enrichment_reset_preserves_fast_sync() -> None:
    keep = build_keep_set("enrichment")
    # Fast-sync representative outputs survive
    assert "trace_nodes.jsonl" in keep
    assert "trace_inferred_edges.jsonl" in keep
    assert "validation_manifest.json" in keep
    # Project meta survives
    assert "project.json" in keep
    assert "repo_policy.json" in keep
    # Enrichment outputs are NOT in keep set
    assert "trace_epistemic.jsonl" not in keep
    assert "trace_modules.jsonl" not in keep
    assert "atlas.json" not in keep
    assert "concepts_manifest.json" not in keep


def test_keep_set_for_finalize_reset_preserves_enrichment() -> None:
    keep = build_keep_set("finalize")
    # Enrichment outputs survive
    assert "trace_epistemic.jsonl" in keep
    assert "trace_modules.jsonl" in keep
    assert "deep_knowledge_manifest.json" in keep
    # Finalize outputs are NOT in keep set
    assert "atlas.json" not in keep
    assert "atlas_manifest.json" not in keep
    assert "rules_manifest.json" not in keep
    assert "concepts_manifest.json" not in keep
    assert "antibodies_manifest.json" not in keep


def test_invalid_scope_raises() -> None:
    with pytest.raises(ValueError, match="unknown reset scope"):
        build_keep_set("not_a_scope")


def test_swarm_synthesis_outputs_are_declared() -> None:
    """Regression: these were missing from the curated denylist."""
    cluster_outputs = STAGE_OUTPUTS[StageId.CLUSTERING].files
    atlas_outputs = STAGE_OUTPUTS[StageId.ATLAS].files
    assert "trace_cluster_swarm_synthesis.json" in cluster_outputs
    assert "atlas_swarm_synthesis.json" in atlas_outputs


def test_project_meta_allowlist_includes_essentials() -> None:
    assert "project.json" in PROJECT_META_ALLOWLIST.files
    assert "repo_policy.json" in PROJECT_META_ALLOWLIST.files
    assert "logs" in PROJECT_META_ALLOWLIST.dirs
    assert "backups" in PROJECT_META_ALLOWLIST.dirs
