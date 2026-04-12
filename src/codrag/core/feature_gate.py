"""
Feature gating for CoDRAG tiers.

Tiers:
  - free:       3 projects, all features (project limit only)
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
import time
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
        Tier.FREE: 3,
        Tier.MONTHLY: 999,
        Tier.PERPETUAL: 999,
        Tier.TEAM: 999,
        Tier.ENTERPRISE: 999,
    },
    "auto_rebuild": Tier.FREE,          # File watcher
    "auto_trace": Tier.FREE,            # Auto-rebuild triggers trace
    "trace_index": Tier.FREE,           # Manual trace build (everyone gets to try it)
    "trace_search": Tier.FREE,          # Search the trace graph
    "mcp_tools": Tier.FREE,             # MCP tools (basic)
    "mcp_trace_expand": Tier.FREE,      # Trace-aware context expansion via MCP
    "path_weights": Tier.FREE,          # Path weight overrides
    "multi_repo_agent": Tier.FREE,      # Multi-repo agent mode
    "team_config": Tier.TEAM,           # Shared team configuration
    "audit_log": Tier.ENTERPRISE,       # Audit logging
    # Phase 24: Pipeline automation gates
    "auto_fast_sync": Tier.FREE,        # Auto Fast Sync on file changes
    "auto_deep_enrichment": Tier.FREE,  # Auto/scheduled Deep Enrichment
    "auto_scope_rebuild": Tier.FREE,    # Auto Knowledge Scope rebuild on selection change
}


@dataclass(frozen=True)
class License:
    tier: Tier
    valid: bool = True
    email: Optional[str] = None
    expires_at: Optional[str] = None
    seats: int = 1
    features: list = field(default_factory=list)
    signature_verified: bool = False
    activation_method: Optional[str] = None

    # Map internal billing tiers to user-facing product tiers.
    # MONTHLY and PERPETUAL are both "Pro" — the only difference is billing.
    _USER_FACING = {
        "FREE": "free",
        "MONTHLY": "pro",
        "PERPETUAL": "pro",
        "TEAM": "team",
        "ENTERPRISE": "enterprise",
    }

    @staticmethod
    def _display_tier(tier: 'Tier') -> str:
        """Return the user-facing tier name (lowercase)."""
        return License._USER_FACING.get(tier.name, tier.name.lower())

    def to_dict(self):
        return {
            "tier": self._display_tier(self.tier),
            "valid": self.valid,
            "email": self.email,
            "expires_at": self.expires_at,
            "seats": self.seats,
            "features": self.features,
            "signature_verified": self.signature_verified,
            "activation_method": self.activation_method,
        }


_LICENSE_PATH = Path.home() / ".codrag" / "license.json"
_cached_license: Optional[License] = None


def _parse_expires_at(raw: Optional[str]) -> Optional[float]:
    """Parse expires_at as Unix timestamp or ISO 8601 string. Returns epoch float or None."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    try:
        return float(raw)
    except (ValueError, TypeError):
        pass
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, AttributeError):
        pass
    return None


def _is_license_expired(expires_at: Optional[str]) -> bool:
    """Check if the license has expired. Returns False if no expiry is set."""
    epoch = _parse_expires_at(expires_at)
    if epoch is None:
        return False
    return time.time() > epoch


def get_license() -> License:
    """Load the current license. Returns FREE tier if no license found."""
    global _cached_license
    if _cached_license is not None:
        return _cached_license

    # EA-A8: Dev override via env var — requires CODRAG_DEV_MODE=1
    env_tier = os.environ.get("CODRAG_TIER", "").strip().lower()
    if env_tier:
        dev_mode = os.environ.get("CODRAG_DEV_MODE", "").strip()
        if dev_mode != "1":
            logger.warning(
                "SECURITY: CODRAG_TIER=%s is set but CODRAG_DEV_MODE=1 is not. "
                "Ignoring CODRAG_TIER. Set CODRAG_DEV_MODE=1 to enable tier override for development.",
                env_tier,
            )
        else:
            _ENV_TIER_MAP = {"pro": "perpetual", "starter": "monthly"}
            env_tier = _ENV_TIER_MAP.get(env_tier, env_tier)
            try:
                tier = Tier[env_tier.upper()]
                _cached_license = License(tier=tier, activation_method="dev_env")
                logger.warning(
                    "DEV MODE: Using tier from CODRAG_TIER env: %s (NOT for production)",
                    tier.name,
                )
                return _cached_license
            except KeyError:
                logger.warning("Invalid CODRAG_TIER=%s, falling back to FREE", env_tier)

    # Try loading license file
    if _LICENSE_PATH.exists():
        try:
            data = json.loads(_LICENSE_PATH.read_text(encoding="utf-8"))

            # EA-A6: If license contains a signed key, verify signature first
            signed_key = data.get("key", "")
            signature_verified = False
            if signed_key:
                try:
                    from codrag.core.licensing import verify_license_key
                    verified_payload = verify_license_key(signed_key)
                    if verified_payload is None:
                        logger.error(
                            "SECURITY: License signature verification FAILED. "
                            "The license file may be tampered with. Falling back to FREE."
                        )
                        _cached_license = License(tier=Tier.FREE, valid=False)
                        return _cached_license
                    data = verified_payload
                    signature_verified = True
                    logger.info("License signature verified successfully")
                except ImportError:
                    logger.warning(
                        "cryptography library not available \u2014 cannot verify license signature. "
                        "Install with: pip install cryptography"
                    )
            else:
                logger.warning(
                    "SECURITY: License file at %s has no cryptographic signature. "
                    "Unsigned licenses will be rejected in a future version. "
                    "Re-activate your license at https://codrag.io/settings to get a signed license.",
                    _LICENSE_PATH,
                )

            tier_raw = str(data.get("tier", "free")).lower()
            _LEGACY_MAP = {"starter": "monthly", "pro": "perpetual"}
            tier_raw = _LEGACY_MAP.get(tier_raw, tier_raw)
            tier_str = tier_raw.upper()
            tier = Tier[tier_str] if tier_str in Tier.__members__ else Tier.FREE

            expires_at_raw = data.get("expires_at")
            valid = bool(data.get("valid", True))

            # EA-A7: Validate expires_at
            if valid and _is_license_expired(expires_at_raw):
                logger.warning(
                    "License has expired (expires_at=%s). Reverting to FREE tier. "
                    "Renew at https://codrag.io/pricing",
                    expires_at_raw,
                )
                valid = False
                tier = Tier.FREE

            _cached_license = License(
                tier=tier,
                valid=valid,
                email=data.get("email"),
                expires_at=str(expires_at_raw) if expires_at_raw else None,
                seats=int(data.get("seats", 1)),
                features=list(data.get("features", [])),
                signature_verified=signature_verified,
                activation_method=data.get("activation_method"),
            )
            logger.info(
                "Loaded license: tier=%s valid=%s signed=%s",
                tier.name, valid, signature_verified,
            )
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
        min_tier = License._display_tier(req) if isinstance(req, Tier) else "pro"
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
