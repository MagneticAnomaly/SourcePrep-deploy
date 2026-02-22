"""
Feature gating for CoDRAG tiers.

Tiers:
  - free:       1 project, manual builds only, no watcher
  - monthly:    full Pro features, $7/month subscription
  - perpetual:  full Pro features, $79 one-time license (never expires)
  - team:       perpetual + shared config, centralized policy
  - enterprise: team + air-gapped, SSO, audit

License is read from ~/.codrag/license.json (offline Ed25519 signed token)
or overridden via CODRAG_TIER env var for development.

Note: MONTHLY and PERPETUAL are feature-identical. The only difference is
the payment model and expiry: monthly licenses carry an expires_at date.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Tier(IntEnum):
    FREE = 0
    MONTHLY = 1
    PERPETUAL = 2
    TEAM = 3
    ENTERPRISE = 4


# Feature → minimum tier required
# Note: MONTHLY and PERPETUAL are feature-identical. MONTHLY has an expiry date.
FEATURE_TIERS = {
    "projects_max": {
        Tier.FREE: 1,
        Tier.MONTHLY: 999,
        Tier.PERPETUAL: 999,
        Tier.TEAM: 999,
        Tier.ENTERPRISE: 999,
    },
    "auto_rebuild": Tier.MONTHLY,       # File watcher
    "auto_trace": Tier.MONTHLY,         # Auto-rebuild triggers trace
    "trace_index": Tier.FREE,           # Manual trace build (everyone gets to try it)
    "trace_search": Tier.FREE,          # Search the trace graph
    "mcp_tools": Tier.FREE,             # MCP tools (basic)
    "mcp_trace_expand": Tier.MONTHLY,   # Trace-aware context expansion via MCP
    "path_weights": Tier.FREE,          # Path weight overrides
    "context_compression": Tier.MONTHLY,  # LLMLingua-2 + LOD context compression
    "multi_repo_agent": Tier.MONTHLY,   # Multi-repo agent mode
    "team_config": Tier.TEAM,           # Shared team configuration
    "audit_log": Tier.ENTERPRISE,       # Audit logging
    # Phase 24: Pipeline automation gates
    "auto_fast_sync": Tier.MONTHLY,     # Auto Fast Sync on file changes
    "auto_deep_enrichment": Tier.MONTHLY,  # Auto/scheduled Deep Enrichment
    "auto_scope_rebuild": Tier.MONTHLY, # Auto Knowledge Scope rebuild on selection change
}


@dataclass(frozen=True)
class License:
    tier: Tier
    valid: bool = True
    email: Optional[str] = None
    expires_at: Optional[str] = None
    seats: int = 1
    features: list = field(default_factory=list)

    @staticmethod
    def _display_tier(tier: 'Tier') -> str:
        """Return the user-facing tier name (lowercase)."""
        return tier.name.lower()

    def to_dict(self):
        return {
            "tier": self._display_tier(self.tier),
            "valid": self.valid,
            "email": self.email,
            "expires_at": self.expires_at,
            "seats": self.seats,
            "features": self.features,
        }


_LICENSE_PATH = Path.home() / ".codrag" / "license.json"
_cached_license: Optional[License] = None


def get_license() -> License:
    """Load the current license. Returns FREE tier if no license found."""
    global _cached_license
    if _cached_license is not None:
        return _cached_license

    # Dev override via env var
    env_tier = os.environ.get("CODRAG_TIER", "").strip().lower()
    if env_tier:
        try:
            tier = Tier[env_tier.upper()]
            _cached_license = License(tier=tier)
            logger.info("Using tier from CODRAG_TIER env: %s", tier.name)
            return _cached_license
        except KeyError:
            logger.warning("Invalid CODRAG_TIER=%s, falling back to FREE", env_tier)

    # Try loading license file
    if _LICENSE_PATH.exists():
        try:
            data = json.loads(_LICENSE_PATH.read_text(encoding="utf-8"))
            tier_raw = str(data.get("tier", "free")).lower()
            # Backward compat: old license files may contain "starter" or "pro"
            _LEGACY_MAP = {"starter": "monthly", "pro": "perpetual"}
            tier_raw = _LEGACY_MAP.get(tier_raw, tier_raw)
            tier_str = tier_raw.upper()
            tier = Tier[tier_str] if tier_str in Tier.__members__ else Tier.FREE
            _cached_license = License(
                tier=tier,
                valid=bool(data.get("valid", True)),
                email=data.get("email"),
                expires_at=data.get("expires_at"),
                seats=int(data.get("seats", 1)),
                features=list(data.get("features", [])),
            )
            logger.info("Loaded license: tier=%s", tier.name)
            return _cached_license
        except Exception as e:
            logger.warning("Failed to load license from %s: %s", _LICENSE_PATH, e)

    _cached_license = License(tier=Tier.FREE)
    return _cached_license


def clear_license_cache():
    """Clear cached license (for testing or after license update)."""
    global _cached_license
    _cached_license = None


def check_feature(feature: str) -> bool:
    """Check if a feature is available at the current tier."""
    lic = get_license()
    if not lic.valid:
        return False

    req = FEATURE_TIERS.get(feature)
    if req is None:
        return True  # Unknown feature = no gate

    if isinstance(req, dict):
        # Limit-based feature (e.g., projects_max)
        return True  # Always "available", check limit via get_feature_limit

    return lic.tier >= req


def get_feature_limit(feature: str) -> int:
    """Get the numeric limit for a limit-based feature at the current tier."""
    lic = get_license()
    limits = FEATURE_TIERS.get(feature)
    if not isinstance(limits, dict):
        return 999  # Not a limit-based feature

    # Find the limit for current tier (or the highest tier <= current)
    for tier in sorted(limits.keys(), reverse=True):
        if lic.tier >= tier:
            return limits[tier]
    return limits.get(Tier.FREE, 0)


def require_feature(feature: str) -> None:
    """Raise if feature is not available at current tier."""
    if not check_feature(feature):
        lic = get_license()
        req = FEATURE_TIERS.get(feature)
        min_tier = req.name.lower() if isinstance(req, Tier) else "monthly"
        raise FeatureGateError(
            feature=feature,
            current_tier=License._display_tier(lic.tier),
            required_tier=min_tier,
        )


class FeatureGateError(Exception):
    """Raised when a feature is not available at the current tier."""

    def __init__(self, feature: str, current_tier: str, required_tier: str):
        self.feature = feature
        self.current_tier = current_tier
        self.required_tier = required_tier
        super().__init__(
            f"Feature '{feature}' requires {required_tier} tier "
            f"(current: {current_tier}). Upgrade at https://codrag.io/pricing"
        )
