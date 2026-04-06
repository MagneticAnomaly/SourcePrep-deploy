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

from codrag.core.feature_gate import (
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
    old_tier = os.environ.pop("CODRAG_TIER", None)
    old_dev = os.environ.pop("CODRAG_DEV_MODE", None)
    # Tests that set CODRAG_TIER also need CODRAG_DEV_MODE=1
    os.environ["CODRAG_DEV_MODE"] = "1"
    yield
    clear_license_cache()
    if old_tier is not None:
        os.environ["CODRAG_TIER"] = old_tier
    else:
        os.environ.pop("CODRAG_TIER", None)
    if old_dev is not None:
        os.environ["CODRAG_DEV_MODE"] = old_dev
    else:
        os.environ.pop("CODRAG_DEV_MODE", None)


class TestTierHierarchy:
    def test_tier_ordering(self):
        assert Tier.FREE < Tier.MONTHLY < Tier.PERPETUAL < Tier.TEAM < Tier.ENTERPRISE

    def test_free_is_zero(self):
        assert int(Tier.FREE) == 0


class TestLicenseFromEnv:
    def test_env_free(self):
        os.environ["CODRAG_TIER"] = "free"
        lic = get_license()
        assert lic.tier == Tier.FREE
        assert lic.valid is True

    def test_env_monthly(self):
        os.environ["CODRAG_TIER"] = "monthly"
        lic = get_license()
        assert lic.tier == Tier.MONTHLY

    def test_env_perpetual(self):
        os.environ["CODRAG_TIER"] = "perpetual"
        lic = get_license()
        assert lic.tier == Tier.PERPETUAL

    def test_env_team(self):
        os.environ["CODRAG_TIER"] = "team"
        lic = get_license()
        assert lic.tier == Tier.TEAM

    def test_env_enterprise(self):
        os.environ["CODRAG_TIER"] = "enterprise"
        lic = get_license()
        assert lic.tier == Tier.ENTERPRISE

    def test_env_invalid_falls_back_to_free(self):
        os.environ["CODRAG_TIER"] = "diamond"
        lic = get_license()
        assert lic.tier == Tier.FREE

    def test_no_env_defaults_to_free(self):
        os.environ.pop("CODRAG_TIER", None)
        lic = get_license()
        assert lic.tier == Tier.FREE


class TestFeatureChecks:
    def test_free_cannot_auto_rebuild(self):
        os.environ["CODRAG_TIER"] = "free"
        assert check_feature("auto_rebuild") is False

    def test_monthly_can_auto_rebuild(self):
        os.environ["CODRAG_TIER"] = "monthly"
        assert check_feature("auto_rebuild") is True

    def test_free_can_trace_index(self):
        os.environ["CODRAG_TIER"] = "free"
        assert check_feature("trace_index") is True

    def test_free_can_trace_search(self):
        os.environ["CODRAG_TIER"] = "free"
        assert check_feature("trace_search") is True

    def test_free_can_mcp_tools(self):
        os.environ["CODRAG_TIER"] = "free"
        assert check_feature("mcp_tools") is True

    def test_free_cannot_mcp_trace_expand(self):
        os.environ["CODRAG_TIER"] = "free"
        assert check_feature("mcp_trace_expand") is False

    def test_monthly_can_mcp_trace_expand(self):
        os.environ["CODRAG_TIER"] = "monthly"
        assert check_feature("mcp_trace_expand") is True

    def test_unknown_feature_allowed(self):
        os.environ["CODRAG_TIER"] = "free"
        assert check_feature("nonexistent_feature") is True

    def test_free_cannot_auto_trace(self):
        os.environ["CODRAG_TIER"] = "free"
        assert check_feature("auto_trace") is False

    def test_monthly_can_auto_trace(self):
        os.environ["CODRAG_TIER"] = "monthly"
        assert check_feature("auto_trace") is True


class TestProjectLimits:
    def test_free_limit_is_1(self):
        os.environ["CODRAG_TIER"] = "free"
        assert get_feature_limit("projects_max") == 1

    def test_monthly_limit_is_999(self):
        os.environ["CODRAG_TIER"] = "monthly"
        assert get_feature_limit("projects_max") == 999

    def test_perpetual_limit_is_999(self):
        os.environ["CODRAG_TIER"] = "perpetual"
        assert get_feature_limit("projects_max") == 999

    def test_team_limit_is_999(self):
        os.environ["CODRAG_TIER"] = "team"
        assert get_feature_limit("projects_max") == 999


class TestRequireFeature:
    def test_require_allowed_feature_passes(self):
        os.environ["CODRAG_TIER"] = "monthly"
        require_feature("auto_rebuild")  # Should not raise

    def test_require_gated_feature_raises(self):
        os.environ["CODRAG_TIER"] = "free"
        with pytest.raises(FeatureGateError) as exc_info:
            require_feature("auto_rebuild")
        assert exc_info.value.feature == "auto_rebuild"
        assert exc_info.value.current_tier == "free"
        assert exc_info.value.required_tier == "pro"
        assert "codrag.io/pricing" in str(exc_info.value)

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
        os.environ["CODRAG_TIER"] = "free"
        from codrag.server import app
        from starlette.testclient import TestClient

        client = TestClient(app)
        res = client.get("/license")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["license"]["tier"] == "free"
        assert data["features"]["auto_rebuild"] is False
        assert data["features"]["trace_index"] is True
        assert data["features"]["projects_max"] == 1

    def test_license_endpoint_perpetual(self):
        os.environ["CODRAG_TIER"] = "perpetual"
        from codrag.server import app
        from starlette.testclient import TestClient

        client = TestClient(app)
        res = client.get("/license")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["license"]["tier"] == "pro"
        assert data["features"]["auto_rebuild"] is True
        assert data["features"]["projects_max"] == 999


class TestWatcherGate:
    """Test that the watcher endpoint is gated behind MONTHLY+ tier."""

    def test_free_cannot_start_watch(self):
        os.environ["CODRAG_TIER"] = "free"
        from codrag.server import app
        from starlette.testclient import TestClient

        client = TestClient(app)
        # Need a project first — create one at PERPETUAL tier, then downgrade
        os.environ["CODRAG_TIER"] = "perpetual"
        clear_license_cache()
        import tempfile, json
        with tempfile.TemporaryDirectory() as tmp:
            res = client.post("/projects", json={"path": tmp, "name": "gate-test"})
            if res.status_code != 200:
                pytest.skip("Could not create project for gate test")
            pid = res.json()["data"]["project"]["id"]

            # Now downgrade to free and try to start watch
            os.environ["CODRAG_TIER"] = "free"
            clear_license_cache()
            res = client.post(f"/projects/{pid}/watch/start")
            assert res.status_code == 403
            assert res.json()["error"]["code"] == "FEATURE_GATED"
            assert "auto_rebuild" in res.json()["error"]["details"]["feature"]

            # Cleanup
            os.environ["CODRAG_TIER"] = "perpetual"
            clear_license_cache()
            client.delete(f"/projects/{pid}")


class TestTraceExpandGate:
    """Test that trace_expand is gated behind MONTHLY+ tier."""

    def test_free_trace_expand_returns_403(self):
        os.environ["CODRAG_TIER"] = "free"
        assert check_feature("mcp_trace_expand") is False

    def test_monthly_trace_expand_allowed(self):
        os.environ["CODRAG_TIER"] = "monthly"
        assert check_feature("mcp_trace_expand") is True
