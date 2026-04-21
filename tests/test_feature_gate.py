"""
Tests for feature gating (tier enforcement).

Covers:
- Tier hierarchy and feature checks
- Project count limits per tier
- Feature gating errors
- License loading from env var
- Default FREE tier behavior
"""

import os
import pytest

from prep.core.feature_gate import (
    Tier,
    License,
    check_feature,
    get_feature_limit,
    require_feature,
    get_license,
    clear_license_cache,
    FeatureGateError,
    FEATURE_TIERS,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear license cache before and after each test."""
    clear_license_cache()
    old_tier = os.environ.pop("PREP_TIER", None)
    old_dev = os.environ.pop("PREP_DEV_MODE", None)
    # Tests that set PREP_TIER also need PREP_DEV_MODE=1
    os.environ["PREP_DEV_MODE"] = "1"
    yield
    clear_license_cache()
    if old_tier is not None:
        os.environ["PREP_TIER"] = old_tier
    else:
        os.environ.pop("PREP_TIER", None)
    if old_dev is not None:
        os.environ["PREP_DEV_MODE"] = old_dev
    else:
        os.environ.pop("PREP_DEV_MODE", None)


class TestTierHierarchy:
    def test_tier_ordering(self):
        assert Tier.FREE < Tier.MONTHLY < Tier.PERPETUAL < Tier.TEAM < Tier.ENTERPRISE

    def test_free_is_zero(self):
        assert int(Tier.FREE) == 0


class TestLicenseFromEnv:
    def test_env_free(self):
        os.environ["PREP_TIER"] = "free"
        lic = get_license()
        assert lic.tier == Tier.FREE
        assert lic.valid is True

    def test_env_monthly(self):
        os.environ["PREP_TIER"] = "monthly"
        lic = get_license()
        assert lic.tier == Tier.MONTHLY

    def test_env_perpetual(self):
        os.environ["PREP_TIER"] = "perpetual"
        lic = get_license()
        assert lic.tier == Tier.PERPETUAL

    def test_env_team(self):
        os.environ["PREP_TIER"] = "team"
        lic = get_license()
        assert lic.tier == Tier.TEAM

    def test_env_enterprise(self):
        os.environ["PREP_TIER"] = "enterprise"
        lic = get_license()
        assert lic.tier == Tier.ENTERPRISE

    def test_env_invalid_falls_back_to_free(self):
        os.environ["PREP_TIER"] = "diamond"
        lic = get_license()
        assert lic.tier == Tier.FREE

    def test_no_env_defaults_to_free(self):
        os.environ.pop("PREP_TIER", None)
        lic = get_license()
        assert lic.tier == Tier.FREE


class TestFeatureChecks:
    def test_free_can_auto_rebuild(self):
        os.environ["PREP_TIER"] = "free"
        assert check_feature("auto_rebuild") is True

    def test_monthly_can_auto_rebuild(self):
        os.environ["PREP_TIER"] = "monthly"
        assert check_feature("auto_rebuild") is True

    def test_free_can_trace_index(self):
        os.environ["PREP_TIER"] = "free"
        assert check_feature("trace_index") is True

    def test_free_can_trace_search(self):
        os.environ["PREP_TIER"] = "free"
        assert check_feature("trace_search") is True

    def test_free_can_mcp_tools(self):
        os.environ["PREP_TIER"] = "free"
        assert check_feature("mcp_tools") is True

    def test_free_can_mcp_trace_expand(self):
        os.environ["PREP_TIER"] = "free"
        assert check_feature("mcp_trace_expand") is True

    def test_monthly_can_mcp_trace_expand(self):
        os.environ["PREP_TIER"] = "monthly"
        assert check_feature("mcp_trace_expand") is True

    def test_unknown_feature_allowed(self):
        os.environ["PREP_TIER"] = "free"
        assert check_feature("nonexistent_feature") is True

    def test_free_can_auto_trace(self):
        os.environ["PREP_TIER"] = "free"
        assert check_feature("auto_trace") is True

    def test_monthly_can_auto_trace(self):
        os.environ["PREP_TIER"] = "monthly"
        assert check_feature("auto_trace") is True


class TestProjectLimits:
    def test_free_limit_is_3(self):
        os.environ["PREP_TIER"] = "free"
        assert get_feature_limit("projects_max") == 3

    def test_monthly_limit_is_999(self):
        os.environ["PREP_TIER"] = "monthly"
        assert get_feature_limit("projects_max") == 999

    def test_perpetual_limit_is_999(self):
        os.environ["PREP_TIER"] = "perpetual"
        assert get_feature_limit("projects_max") == 999

    def test_team_limit_is_999(self):
        os.environ["PREP_TIER"] = "team"
        assert get_feature_limit("projects_max") == 999


class TestRequireFeature:
    def test_require_allowed_feature_passes(self):
        os.environ["PREP_TIER"] = "monthly"
        require_feature("auto_rebuild")  # Should not raise

    def test_require_gated_feature_raises(self):
        os.environ["PREP_TIER"] = "free"
        with pytest.raises(FeatureGateError) as exc_info:
            require_feature("team_config")
        assert exc_info.value.feature == "team_config"
        assert exc_info.value.current_tier == "free"
        assert exc_info.value.required_tier == "team"
        assert "prep.io/pricing" in str(exc_info.value)

class TestLicenseToDict:
    def test_to_dict_structure(self):
        lic = License(tier=Tier.PERPETUAL, email="test@example.com")
        d = lic.to_dict()
        assert d["tier"] == "pro"
        assert d["valid"] is True
        assert d["email"] == "test@example.com"
        assert d["seats"] == 1

    def test_free_to_dict(self):
        lic = License(tier=Tier.FREE)
        d = lic.to_dict()
        assert d["tier"] == "free"
        assert d["valid"] is True
        assert d["email"] is None


class TestLicenseEndpoint:
    """Test the /license API endpoint via TestClient."""

    def test_license_endpoint_returns_features(self):
        os.environ["PREP_TIER"] = "free"
        from prep.server import app
        from starlette.testclient import TestClient

        client = TestClient(app)
        res = client.get("/license")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["license"]["tier"] == "free"
        assert data["features"]["auto_rebuild"] is True
        assert data["features"]["trace_index"] is True
        assert data["features"]["projects_max"] == 3

    def test_license_endpoint_perpetual(self):
        os.environ["PREP_TIER"] = "perpetual"
        from prep.server import app
        from starlette.testclient import TestClient

        client = TestClient(app)
        res = client.get("/license")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["license"]["tier"] == "pro"
        assert data["features"]["auto_rebuild"] is True
        assert data["features"]["projects_max"] == 999


class TestWatcherGate:
    """Test that the watcher endpoint is available to all tiers (fully unlocked)."""

    def test_free_can_auto_rebuild(self):
        os.environ["PREP_TIER"] = "free"
        assert check_feature("auto_rebuild") is True

    def test_team_config_still_gated(self):
        os.environ["PREP_TIER"] = "free"
        assert check_feature("team_config") is False


class TestTraceExpandGate:
    """Test that trace_expand is available to all tiers (fully unlocked)."""

    def test_free_trace_expand_allowed(self):
        os.environ["PREP_TIER"] = "free"
        assert check_feature("mcp_trace_expand") is True

    def test_monthly_trace_expand_allowed(self):
        os.environ["PREP_TIER"] = "monthly"
        assert check_feature("mcp_trace_expand") is True
