"""
LemonSqueezy License API client.

Handles activation, validation, and deactivation of license keys
via the LemonSqueezy REST API (Merchant of Record).

See: SECURITY_DESIGN_DECISIONS.md §CRIT-1
See: DISTRIBUTION_AND_REVENUE_PLAN.md §3

Flow:
  1. User buys on sourceprep.io/pricing → LS generates UUID license key
  2. User enters key in SourcePrep → POST /license/activate
  3. We call LS /v1/licenses/activate → get tier, expiry, instance_id
  4. Save to ~/.runprep/license.json with last_validated timestamp
  5. Every 7 days: POST /v1/licenses/validate → refresh or downgrade
  6. If offline > 30 days: downgrade to FREE (grace period expired)
"""

from __future__ import annotations

import logging
import platform
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

LS_API_BASE = "https://api.lemonsqueezy.com/v1/licenses"

# Map LS product variant names → SourcePrep tiers
# These will be configured after Eric creates the LS products (LS-01 to LS-04)
# For now, we also support tier names directly in the license meta
PRODUCT_TIER_MAP: Dict[str, str] = {
    # product_id → tier (filled in after LS setup)
    # "123456": "monthly",
    # "123457": "perpetual",
    # "123458": "team",
}

# Grace periods
VALIDATION_INTERVAL_SECONDS = 7 * 24 * 60 * 60   # 7 days
GRACE_PERIOD_SECONDS = 30 * 24 * 60 * 60          # 30 days


@dataclass
class LSActivationResult:
    """Result of a LemonSqueezy license activation or validation."""
    success: bool
    error: Optional[str] = None
    license_key: Optional[str] = None
    instance_id: Optional[str] = None
    tier: str = "free"
    email: Optional[str] = None
    expires_at: Optional[str] = None
    seats: int = 1
    product_id: Optional[str] = None
    variant_id: Optional[str] = None
    status: Optional[str] = None  # "active", "inactive", "expired", "disabled"


def _get_instance_name() -> str:
    """Generate a human-readable instance name for this machine."""
    return f"{platform.node()}_{platform.system()}_{platform.machine()}"


def activate_key(license_key: str) -> LSActivationResult:
    """Activate a license key with LemonSqueezy.

    Calls POST /v1/licenses/activate with the key and machine instance name.
    Returns activation details including instance_id (needed for deactivation).
    """
    import requests

    try:
        resp = requests.post(
            f"{LS_API_BASE}/activate",
            json={
                "license_key": license_key,
                "instance_name": _get_instance_name(),
            },
            timeout=15,
        )

        data = resp.json()

        if not data.get("activated") and not data.get("valid"):
            error = data.get("error", "Activation failed")
            # LS returns specific error messages
            if "limit" in str(error).lower():
                error = "Activation limit reached. Deactivate another machine first, or contact support."
            return LSActivationResult(success=False, error=str(error))

        # Extract license metadata
        meta = data.get("meta", {})
        instance = data.get("instance", {})
        license_key_data = data.get("license_key", {})

        # Determine tier from product_id or meta
        product_id = str(meta.get("product_id", ""))
        tier = PRODUCT_TIER_MAP.get(product_id, "")
        if not tier:
            # Fallback: check meta for tier hint (custom field in LS)
            tier = str(meta.get("tier", "") or license_key_data.get("tier", "") or "pro").lower()

        # Map variant names
        variant_name = str(meta.get("variant_name", "")).lower()
        if "team" in variant_name:
            tier = "team"
        elif "enterprise" in variant_name:
            tier = "enterprise"
        elif "perpetual" in variant_name or "lifetime" in variant_name:
            tier = "perpetual"
        elif "monthly" in variant_name or "subscription" in variant_name:
            tier = "monthly"

        return LSActivationResult(
            success=True,
            license_key=license_key,
            instance_id=instance.get("id"),
            tier=tier,
            email=meta.get("customer_email") or license_key_data.get("user_email"),
            expires_at=license_key_data.get("expires_at"),
            seats=int(license_key_data.get("activation_limit", 1) or 1),
            product_id=product_id,
            variant_id=str(meta.get("variant_id", "")),
            status=license_key_data.get("status"),
        )

    except requests.ConnectionError:
        return LSActivationResult(success=False, error="Cannot reach LemonSqueezy. Check your internet connection.")
    except requests.Timeout:
        return LSActivationResult(success=False, error="LemonSqueezy request timed out. Try again.")
    except Exception as e:
        logger.warning("LS activation error: %s", e)
        return LSActivationResult(success=False, error=f"Activation error: {e}")


def validate_key(license_key: str, instance_id: str) -> LSActivationResult:
    """Validate a previously activated license key.

    Called periodically (every 7 days) to confirm the license is still valid.
    If the subscription was cancelled, LS returns valid=false.
    """
    import requests

    try:
        resp = requests.post(
            f"{LS_API_BASE}/validate",
            json={
                "license_key": license_key,
                "instance_id": instance_id,
            },
            timeout=15,
        )

        data = resp.json()
        meta = data.get("meta", {})
        license_key_data = data.get("license_key", {})

        if data.get("valid"):
            product_id = str(meta.get("product_id", ""))
            tier = PRODUCT_TIER_MAP.get(product_id, "")
            if not tier:
                tier = str(meta.get("tier", "") or license_key_data.get("tier", "") or "pro").lower()

            return LSActivationResult(
                success=True,
                license_key=license_key,
                instance_id=instance_id,
                tier=tier,
                email=meta.get("customer_email") or license_key_data.get("user_email"),
                expires_at=license_key_data.get("expires_at"),
                seats=int(license_key_data.get("activation_limit", 1) or 1),
                status=license_key_data.get("status"),
            )
        else:
            return LSActivationResult(
                success=False,
                error=data.get("error", "License is no longer valid"),
                status=license_key_data.get("status"),
            )

    except requests.ConnectionError:
        return LSActivationResult(success=False, error="OFFLINE")
    except requests.Timeout:
        return LSActivationResult(success=False, error="TIMEOUT")
    except Exception as e:
        logger.warning("LS validation error: %s", e)
        return LSActivationResult(success=False, error=f"Validation error: {e}")


def deactivate_key(license_key: str, instance_id: str) -> bool:
    """Deactivate this instance's license activation.

    Frees up an activation slot so the user can activate on another machine.
    Returns True if deactivation succeeded.
    """
    import requests

    try:
        resp = requests.post(
            f"{LS_API_BASE}/deactivate",
            json={
                "license_key": license_key,
                "instance_id": instance_id,
            },
            timeout=15,
        )
        data = resp.json()
        return data.get("deactivated", False)
    except Exception as e:
        logger.warning("LS deactivation error: %s", e)
        return False


def needs_revalidation(last_validated: Optional[float]) -> bool:
    """Check if the license needs online re-validation (7-day interval)."""
    if last_validated is None:
        return True
    return (time.time() - last_validated) > VALIDATION_INTERVAL_SECONDS


def is_grace_period_expired(last_validated: Optional[float]) -> bool:
    """Check if the offline grace period has expired (30 days without validation)."""
    if last_validated is None:
        return True  # Never validated = no grace
    return (time.time() - last_validated) > GRACE_PERIOD_SECONDS


def grace_period_days_remaining(last_validated: Optional[float]) -> int:
    """Get days remaining in the grace period. Returns 0 if expired."""
    if last_validated is None:
        return 0
    remaining = GRACE_PERIOD_SECONDS - (time.time() - last_validated)
    return max(0, int(remaining / (24 * 60 * 60)))
