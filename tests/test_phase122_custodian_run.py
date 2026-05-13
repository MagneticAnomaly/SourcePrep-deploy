"""Unit tests for the Phase 122 Custodian driver."""
from tools.phase122_custodian_run import CANDIDATES, build_findings


def test_build_findings_one_per_candidate() -> None:
    findings = build_findings()
    assert len(findings) == len(CANDIDATES) == 11


def test_build_findings_use_dead_code_category() -> None:
    # The Custodian engine filters on category in
    # {dead_code, orphan, deprecated, unused_export}. Anything else is
    # silently dropped, so we hard-code "dead_code".
    findings = build_findings()
    assert all(f["category"] == "dead_code" for f in findings)


def test_build_findings_have_required_fields() -> None:
    findings = build_findings()
    for f in findings:
        assert f["id"].startswith("P122-")
        assert f["affected_files"], f
        assert f["affected_files"][0].startswith("src/prep/core/")
        assert f["affected_files"][0].endswith(".py")
        assert f["description"]


def test_candidates_list_matches_spec() -> None:
    # If this fails, the candidate list drifted from the spec/plan.
    expected = {
        "roadmap_miner", "treatment_registry", "swarm_optimizer",
        "lod_extractor", "github_sync", "budget_enforcement",
        "chunking", "inferred_edges", "batch_profiles",
        "swarm_registry", "context_config",
    }
    assert set(CANDIDATES) == expected
