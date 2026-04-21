"""Tests for Prep Role Resolver (Phase 64A)."""
import pytest

from prep.core.atlas.role_resolver import resolve_role, KEYWORD_TO_BASE
from prep.core.atlas.role_vectors import BUILT_IN_ROLES, RoleVector


class TestExactMatch:
    """Test built-in role exact matching."""

    def test_lowercase_exact(self):
        rv = resolve_role("ceo")
        assert rv.role_id == "ceo"
        assert rv.display_name == "CEO"

    def test_uppercase_exact(self):
        rv = resolve_role("CEO")
        assert rv.role_id == "ceo"

    def test_mixed_case(self):
        rv = resolve_role("CTO")
        assert rv.role_id == "cto"

    def test_all_builtins_resolve(self):
        for role_id, expected in BUILT_IN_ROLES.items():
            rv = resolve_role(role_id)
            assert rv.role_id == expected.role_id
            assert rv.display_name == expected.display_name

    def test_engineer_alias(self):
        rv = resolve_role("engineering")
        assert rv.role_id == "engineering"


class TestKeywordDecomposition:
    """Test compound role decomposition via keywords."""

    def test_design_engineer(self):
        rv = resolve_role("Design Engineer")
        # Should resolve to built-in design_engineer
        assert rv.role_id == "design_engineer"

    def test_compound_unknown_words(self):
        rv = resolve_role("Frontend Developer")
        # "frontend" maps to design, "developer" maps to engineering
        # Should be blended
        assert rv.display_name == "Frontend Developer"
        # Should have both design and engineering influences
        assert rv.layer_weights.get("presentation", 0) > 0

    def test_security_analyst(self):
        rv = resolve_role("Security Analyst")
        # "security" maps to security base
        assert rv.layer_weights.get("security", 0) > 0 or \
               any("security" in d for d in rv.domain_affinity)

    def test_data_engineer_compound(self):
        rv = resolve_role("Data Engineer")
        # "data" -> data_engineer, "engineer" -> engineering
        assert rv.display_name == "Data Engineer"

    def test_unknown_falls_to_engineering(self):
        rv = resolve_role("Underwater Basket Weaver")
        assert rv.role_id == "engineering"  # fallback
        assert rv.display_name == "Software Engineer"  # fallback display name


class TestModifiers:
    """Test seniority and scope modifier application."""

    def test_senior_lowers_detail(self):
        base = resolve_role("engineer")
        senior = resolve_role("Senior Engineer")
        assert senior.detail_level < base.detail_level

    def test_senior_raises_centrality(self):
        base = resolve_role("qa")
        senior = resolve_role("Senior QA")
        assert senior.centrality_weight >= base.centrality_weight

    def test_junior_raises_detail(self):
        base = resolve_role("Engineer")
        junior = resolve_role("Junior Engineer")
        assert junior.detail_level > base.detail_level

    def test_lead_lowers_detail(self):
        base = resolve_role("Engineer")
        lead = resolve_role("Lead Engineer")
        assert lead.detail_level < base.detail_level

    def test_intern_hits_max_detail(self):
        intern = resolve_role("Intern")
        assert intern.detail_level >= 0.9

    def test_staff_increases_centrality(self):
        base = resolve_role("Engineer")
        staff = resolve_role("Staff Engineer")
        assert staff.centrality_weight >= base.centrality_weight

    def test_principal_is_very_strategic(self):
        principal = resolve_role("Principal Engineer")
        assert principal.detail_level < resolve_role("Engineer").detail_level

    def test_vp_is_executive_leaning(self):
        vp = resolve_role("VP Engineering")
        assert vp.detail_level < 0.5  # VP should be strategic


class TestEdgeCases:
    """Test edge cases and resilience."""

    def test_empty_string_returns_engineering(self):
        rv = resolve_role("")
        assert rv.role_id == "engineering"

    def test_whitespace_only_returns_engineering(self):
        rv = resolve_role("   ")
        assert rv.role_id == "engineering"

    def test_numbers_in_role(self):
        rv = resolve_role("Engineer L5")
        assert rv.display_name in ("Engineer L5", "Software Engineer")

    def test_very_long_role_name(self):
        rv = resolve_role("Senior Principal Distinguished Staff Software Engineer")
        # Should not crash; senior/principal modifiers should apply
        assert rv.detail_level < 0.5

    def test_copy_isolation(self):
        """Resolved role should not mutate built-in presets."""
        original_detail = BUILT_IN_ROLES["ceo"].detail_level
        rv = resolve_role("CEO")
        rv.detail_level = 0.99
        assert BUILT_IN_ROLES["ceo"].detail_level == original_detail


class TestKeywordToBase:
    """Test the keyword-to-base-role mapping."""

    def test_frontend_maps_to_full_stack(self):
        assert KEYWORD_TO_BASE.get("frontend") == "full_stack"

    def test_backend_maps_to_engineering(self):
        assert KEYWORD_TO_BASE.get("backend") == "engineering"

    def test_infra_maps_to_devops(self):
        assert KEYWORD_TO_BASE.get("infra") == "devops"

    def test_test_maps_to_qa(self):
        assert KEYWORD_TO_BASE.get("test") == "qa"

    def test_product_maps_to_product(self):
        assert KEYWORD_TO_BASE.get("product") == "product"
