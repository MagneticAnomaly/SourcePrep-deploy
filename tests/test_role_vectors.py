"""Tests for Prep Role Vectors (Phase 64A)."""
import pytest

from prep.core.atlas.role_vectors import (
    BUILT_IN_ROLES,
    RoleVector,
    SYNONYM_CLUSTERS,
    are_synonyms,
    max_tag_affinity,
)


class TestRoleVectorDataclass:
    """Test the RoleVector dataclass."""

    def test_basic_construction(self):
        rv = RoleVector(role_id="test", display_name="Test Role")
        assert rv.role_id == "test"
        assert rv.display_name == "Test Role"
        assert rv.centrality_weight == 0.5
        assert rv.detail_level == 0.7
        assert rv.max_chars == 3000

    def test_custom_fields(self):
        rv = RoleVector(
            role_id="custom",
            display_name="Custom",
            layer_weights={"presentation": 0.9},
            domain_affinity=["ui", "design"],
            centrality_weight=0.2,
            detail_level=0.1,
            max_chars=1500,
        )
        assert rv.layer_weights["presentation"] == 0.9
        assert rv.domain_affinity == ["ui", "design"]
        assert rv.centrality_weight == 0.2
        assert rv.detail_level == 0.1
        assert rv.max_chars == 1500

    def test_to_dict_roundtrip(self):
        rv = RoleVector(
            role_id="rt",
            display_name="Roundtrip",
            layer_weights={"data": 0.5},
            domain_affinity=["db"],
            centrality_weight=0.3,
            detail_level=0.8,
            max_chars=2000,
        )
        d = rv.to_dict()
        rv2 = RoleVector.from_dict(d)
        assert rv.role_id == rv2.role_id
        assert rv.layer_weights == rv2.layer_weights
        assert rv.domain_affinity == rv2.domain_affinity
        assert rv.centrality_weight == rv2.centrality_weight
        assert rv.detail_level == rv2.detail_level
        assert rv.max_chars == rv2.max_chars

    def test_copy_independence(self):
        rv = BUILT_IN_ROLES["ceo"].copy()
        rv.detail_level = 0.99
        assert BUILT_IN_ROLES["ceo"].detail_level != 0.99


class TestBuiltInRoles:
    """Test the built-in role presets."""

    def test_expected_roles_exist(self):
        expected = [
            "ceo", "cto", "engineering", "architect", "full_stack",
            "design", "design_engineer", "qa", "security",
            "devops", "devsecops", "product", "writer",
            "data_engineer", "intern",
        ]
        for role_id in expected:
            assert role_id in BUILT_IN_ROLES, f"Missing built-in role: {role_id}"

    def test_all_roles_have_layer_weights(self):
        for role_id, rv in BUILT_IN_ROLES.items():
            assert rv.layer_weights, f"{role_id} has empty layer_weights"
            assert all(0.0 <= v <= 1.0 for v in rv.layer_weights.values()), \
                f"{role_id} has layer_weight outside [0, 1]"

    def test_all_roles_have_domain_affinity(self):
        for role_id, rv in BUILT_IN_ROLES.items():
            assert rv.domain_affinity, f"{role_id} has empty domain_affinity"

    def test_detail_levels_range(self):
        for role_id, rv in BUILT_IN_ROLES.items():
            assert 0.0 <= rv.detail_level <= 1.0, f"{role_id} detail_level={rv.detail_level}"

    def test_centrality_weights_range(self):
        for role_id, rv in BUILT_IN_ROLES.items():
            assert 0.0 <= rv.centrality_weight <= 1.0, f"{role_id} centrality={rv.centrality_weight}"

    def test_max_chars_reasonable(self):
        for role_id, rv in BUILT_IN_ROLES.items():
            assert 500 <= rv.max_chars <= 10000, f"{role_id} max_chars={rv.max_chars}"

    def test_ceo_is_executive_level(self):
        ceo = BUILT_IN_ROLES["ceo"]
        assert ceo.detail_level < 0.3, "CEO should be executive detail level"
        assert ceo.centrality_weight >= 0.8, "CEO should prioritize hub files"
        assert ceo.max_chars <= 2000, "CEO context should be compact"

    def test_intern_is_practitioner_level(self):
        intern = BUILT_IN_ROLES["intern"]
        assert intern.detail_level >= 0.8, "Intern should be practitioner detail level"
        assert intern.max_chars >= 3000, "Intern should get generous context"

    def test_design_engineer_is_hybrid(self):
        de = BUILT_IN_ROLES["design_engineer"]
        # Should care about both presentation and business_logic
        assert de.layer_weights.get("presentation", 0) >= 0.7
        assert de.layer_weights.get("business_logic", 0) >= 0.4


class TestSynonymClusters:
    """Test synonym cluster matching."""

    def test_same_cluster_are_synonyms(self):
        assert are_synonyms("ui", "presentation")
        assert are_synonyms("api", "endpoint")
        assert are_synonyms("auth", "security")
        assert are_synonyms("data", "database")
        assert are_synonyms("deploy", "devops")

    def test_different_cluster_not_synonyms(self):
        assert not are_synonyms("ui", "deploy")
        assert not are_synonyms("auth", "test")
        assert not are_synonyms("data", "build")

    def test_unknown_tags_not_synonyms(self):
        assert not are_synonyms("xyzzy", "plugh")
        assert not are_synonyms("unknown", "ui")

    def test_cluster_count(self):
        assert len(SYNONYM_CLUSTERS) >= 10


class TestMaxTagAffinity:
    """Test fuzzy domain tag matching."""

    def test_exact_match_returns_1(self):
        assert max_tag_affinity(["auth"], ["auth"]) == 1.0
        assert max_tag_affinity(["ui", "layout"], ["ui"]) == 1.0

    def test_substring_match_returns_07(self):
        assert max_tag_affinity(["authentication"], ["auth"]) == 0.7
        assert max_tag_affinity(["auth"], ["authentication"]) == 0.7

    def test_synonym_match_returns_05(self):
        assert max_tag_affinity(["ui"], ["presentation"]) == 0.5
        assert max_tag_affinity(["api"], ["handler"]) == 0.5

    def test_no_match_returns_0(self):
        assert max_tag_affinity(["ui"], ["database"]) == 0.0
        assert max_tag_affinity(["auth"], ["build"]) == 0.0

    def test_empty_inputs_returns_0(self):
        assert max_tag_affinity([], ["auth"]) == 0.0
        assert max_tag_affinity(["auth"], []) == 0.0
        assert max_tag_affinity([], []) == 0.0

    def test_best_match_wins(self):
        # Has both a synonym match and an exact match — exact should win
        score = max_tag_affinity(["auth", "presentation"], ["auth", "ui"])
        assert score == 1.0  # "auth" == "auth" is exact

    def test_hyphen_normalization(self):
        score = max_tag_affinity(["state-management"], ["state management"])
        assert score >= 0.7  # substring match after normalization
