"""
CoDRAG License Router — Phase 23 Sprint 10
============================================

**Origin:** Extracted from ``server.py`` (lines ~1261–1393).

**Endpoints moved here:**
  - GET  /license            — current tier, feature availability
  - POST /license/activate   — activate via signed key, tier name, JSON, or base64
  - POST /license/deactivate — remove license file, revert to free tier

**Shared state accessed (from server.py):**
  - None — license is stored on disk at ``~/.codrag/license.json``
    and read via ``codrag.core.feature_gate``.

**Phase 24 note (State Machine — SM-7 License & Feature Gate):**
  Currently license state is stateless (read from disk each time).
  SM-7 will add a lifecycle: UNCHECKED → VALID → EXPIRED → GRACE_PERIOD.
  The ``/license/activate`` endpoint will become a state transition
  (UNCHECKED/EXPIRED → VALID), and feature checks will be performed at
  transition time in other state machines (e.g. SM-4, SM-5, SM-6) rather
  than at query time. This router is the natural home for SM-7 transition
  endpoints when that work happens.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok
from codrag.core.feature_gate import (
    get_license,
    check_feature,
    get_feature_limit,
    clear_license_cache,
)
from codrag.core.licensing import verify_license_key

logger = logging.getLogger(__name__)

router = APIRouter(tags=["license"])


# ── Pydantic models ─────────────────────────────────────────────

class ActivateLicenseRequest(BaseModel):
    key: str


class DevTierOverrideRequest(BaseModel):
    tier: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/license")
def get_license_status() -> Dict[str, Any]:
    """Get current license tier and feature availability."""
    lic = get_license()
    features = {}
    for feat in [
        "auto_rebuild", "auto_trace", "trace_index", "trace_search",
        "mcp_tools", "mcp_trace_expand", "path_weights",
        "context_compression", "multi_repo_agent", "team_config", "audit_log",
    ]:
        features[feat] = check_feature(feat)
    features["projects_max"] = get_feature_limit("projects_max")
    return ok({
        "license": lic.to_dict(),
        "features": features,
    })


@router.post("/license/activate")
def activate_license(req: ActivateLicenseRequest) -> Dict[str, Any]:
    """Activate a license key.

    Supports three activation methods (tried in order):
    1. LemonSqueezy UUID key → calls LS API for online activation
    2. Ed25519 signed offline key → cryptographic verification (enterprise)
    3. Dev/testing: tier name, JSON, or base64 (requires CODRAG_DEV_MODE=1)
    """
    import time as _time

    key = str(req.key or "").strip()
    if not key:
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="key is required")

    allowed_tiers = {"free", "monthly", "perpetual", "team", "enterprise"}
    _legacy_tier_map = {"starter": "monthly", "pro": "perpetual"}
    lic_data: Optional[Dict[str, Any]] = None

    # ── Method 1: LemonSqueezy UUID key (production path) ────────
    # LS keys look like UUIDs: 38b1460a-5104-4067-a91d-77b872934d51
    _uuid_like = len(key) >= 30 and key.count("-") >= 3 and all(c in "0123456789abcdef-" for c in key.lower())
    if _uuid_like:
        try:
            from codrag.core.lemon_squeezy import activate_key
            result = activate_key(key)
            if result.success:
                lic_data = {
                    "tier": result.tier,
                    "valid": True,
                    "email": result.email,
                    "expires_at": result.expires_at,
                    "seats": result.seats,
                    "features": [],
                    "license_key": result.license_key,
                    "instance_id": result.instance_id,
                    "product_id": result.product_id,
                    "activated_at": _time.time(),
                    "last_validated": _time.time(),
                    "activation_method": "lemonsqueezy",
                }
                logger.info("Activated license via LemonSqueezy: tier=%s email=%s", result.tier, result.email)
            else:
                raise ApiException(
                    status_code=400,
                    code="ACTIVATION_FAILED",
                    message=result.error or "LemonSqueezy activation failed",
                )
        except ApiException:
            raise
        except ImportError:
            logger.warning("lemon_squeezy module not available — falling back to offline methods")
        except Exception as e:
            logger.warning("LS activation failed, trying offline methods: %s", e)

    # ── Method 2: Ed25519 signed offline key (enterprise) ────────
    if lic_data is None:
        verified_payload = verify_license_key(key)
        if verified_payload:
            lic_data = verified_payload
            lic_data["activation_method"] = "ed25519"
            lic_data["signature_verified"] = True
            lic_data["last_validated"] = _time.time()
            logger.info("Verified signed license key for %s", lic_data.get("issued_to", "unknown"))

    # ── Method 3: Dev/testing shortcuts ──────────────────────────
    # Only available when CODRAG_DEV_MODE=1 is set
    dev_mode = os.environ.get("CODRAG_DEV_MODE", "").strip() == "1"

    if lic_data is None and dev_mode:
        tier_guess = _legacy_tier_map.get(key.lower(), key.lower())
        if tier_guess in allowed_tiers:
            lic_data = {"tier": tier_guess, "valid": True, "seats": 1, "features": [], "activation_method": "dev"}
            logger.info("DEV MODE: Activated via tier name: %s", tier_guess)

    if lic_data is None and dev_mode:
        try:
            if key.startswith("{") and key.endswith("}"):
                parsed = json.loads(key)
                if isinstance(parsed, dict):
                    lic_data = dict(parsed)
                    lic_data["activation_method"] = "dev_json"
                    logger.info("DEV MODE: Activated via plain JSON")
        except Exception:
            pass

    if lic_data is None:
        raise ApiException(
            status_code=400,
            code="INVALID_LICENSE",
            message="Invalid license key. Enter a valid LemonSqueezy license key.",
            hint="Purchase a license at https://codrag.io/pricing",
        )

    # Normalize tier
    tier_raw = str(lic_data.get("tier") or "pro").strip().lower()
    tier_raw = _legacy_tier_map.get(tier_raw, tier_raw)
    if tier_raw not in allowed_tiers:
        tier_raw = "pro"  # Safe default for LS keys without explicit tier
    lic_data["tier"] = tier_raw
    lic_data.setdefault("valid", True)
    lic_data.setdefault("seats", 1)
    lic_data.setdefault("features", [])
    lic_data.setdefault("activated_at", _time.time())
    lic_data.setdefault("last_validated", _time.time())

    # Save to disk
    license_path = Path.home() / ".codrag" / "license.json"
    license_path.parent.mkdir(parents=True, exist_ok=True)
    license_path.write_text(json.dumps(lic_data, indent=2), encoding="utf-8")

    clear_license_cache()

    # Audit log
    try:
        from codrag.core.audit_log import get_audit_log
        get_audit_log().record(
            event_type="license_activated",
            severity="info",
            message=f"License activated: tier={tier_raw}, method={lic_data.get('activation_method')}",
            metadata={"tier": tier_raw, "method": lic_data.get("activation_method"), "email": lic_data.get("email")},
        )
    except Exception:
        pass

    return get_license_status()


@router.post("/license/validate")
def validate_license_online() -> Dict[str, Any]:
    """Re-validate the current license with LemonSqueezy.

    Called periodically (every 7 days) by the dashboard.
    Updates last_validated timestamp on success.
    If LS says invalid → downgrade to FREE.
    If offline → check grace period (30 days).
    """
    import time as _time

    license_path = Path.home() / ".codrag" / "license.json"
    if not license_path.exists():
        return ok({"validated": False, "reason": "No license file"})

    try:
        lic_data = json.loads(license_path.read_text(encoding="utf-8"))
    except Exception:
        return ok({"validated": False, "reason": "Cannot read license file"})

    ls_key = lic_data.get("license_key")
    instance_id = lic_data.get("instance_id")
    method = lic_data.get("activation_method", "")

    # Only LS-activated licenses need online validation
    if method != "lemonsqueezy" or not ls_key or not instance_id:
        return ok({"validated": True, "reason": "Offline license — no validation needed", "method": method})

    # Check if validation is needed (7-day interval)
    from codrag.core.lemon_squeezy import needs_revalidation, validate_key, is_grace_period_expired, grace_period_days_remaining

    last_validated = lic_data.get("last_validated")
    if not needs_revalidation(last_validated):
        days_since = int((_time.time() - (last_validated or 0)) / 86400) if last_validated else 0
        return ok({
            "validated": True,
            "reason": f"Recently validated ({days_since}d ago)",
            "next_check_days": max(0, 7 - days_since),
        })

    # Call LS API
    result = validate_key(ls_key, instance_id)

    if result.success:
        # Update last_validated timestamp
        lic_data["last_validated"] = _time.time()
        lic_data["valid"] = True
        if result.tier:
            lic_data["tier"] = result.tier
        if result.expires_at:
            lic_data["expires_at"] = result.expires_at
        license_path.write_text(json.dumps(lic_data, indent=2), encoding="utf-8")
        clear_license_cache()
        return ok({"validated": True, "reason": "License confirmed valid by LemonSqueezy"})

    elif result.error in ("OFFLINE", "TIMEOUT"):
        # Network error — check grace period
        grace_days = grace_period_days_remaining(last_validated)
        if is_grace_period_expired(last_validated):
            # Grace period expired — downgrade
            lic_data["valid"] = False
            lic_data["tier"] = "free"
            license_path.write_text(json.dumps(lic_data, indent=2), encoding="utf-8")
            clear_license_cache()
            logger.warning("License grace period expired (offline > 30 days). Downgrading to FREE.")
            return ok({
                "validated": False,
                "reason": "Offline grace period expired (30 days). Connect to internet to re-validate.",
                "grace_days_remaining": 0,
            })
        else:
            return ok({
                "validated": True,
                "reason": f"Offline — using cached license ({grace_days} days remaining in grace period)",
                "grace_days_remaining": grace_days,
            })

    else:
        # LS explicitly says invalid (subscription cancelled, refunded, etc.)
        lic_data["valid"] = False
        lic_data["tier"] = "free"
        license_path.write_text(json.dumps(lic_data, indent=2), encoding="utf-8")
        clear_license_cache()
        logger.warning("License invalidated by LemonSqueezy: %s", result.error)

        try:
            from codrag.core.audit_log import get_audit_log
            get_audit_log().record(
                event_type="license_invalidated",
                severity="warning",
                message=f"License invalidated: {result.error}",
                metadata={"error": result.error},
            )
        except Exception:
            pass

        return ok({
            "validated": False,
            "reason": result.error or "License is no longer valid",
        })


@router.post("/license/deactivate")
def deactivate_license() -> Dict[str, Any]:
    """Deactivate the license and revert to FREE tier.

    If this is a LemonSqueezy license, calls LS API to free the activation slot.
    """
    license_path = Path.home() / ".codrag" / "license.json"

    # Try to deactivate with LS first (frees activation slot)
    if license_path.exists():
        try:
            lic_data = json.loads(license_path.read_text(encoding="utf-8"))
            ls_key = lic_data.get("license_key")
            instance_id = lic_data.get("instance_id")
            if ls_key and instance_id:
                from codrag.core.lemon_squeezy import deactivate_key
                if deactivate_key(ls_key, instance_id):
                    logger.info("Deactivated license with LemonSqueezy (freed activation slot)")
                else:
                    logger.warning("LS deactivation failed — removing local license anyway")
        except Exception as e:
            logger.warning("Error during LS deactivation: %s", e)

    # Remove local license file
    try:
        if license_path.exists():
            license_path.unlink()
    except Exception:
        raise ApiException(status_code=500, code="IO_ERROR", message="Failed to remove license file")

    clear_license_cache()

    # Audit log
    try:
        from codrag.core.audit_log import get_audit_log
        get_audit_log().record(
            event_type="license_deactivated",
            severity="info",
            message="License deactivated",
        )
    except Exception:
        pass

    return get_license_status()


@router.get("/license/seats")
def get_seat_status() -> Dict[str, Any]:
    """SEAT-1: Get seat usage for the current license.

    Returns seat count, activation limit, and activation method info.
    For LS licenses, this reflects the LS activation limit.
    """
    license_path = Path.home() / ".codrag" / "license.json"
    if not license_path.exists():
        return ok({"seats_used": 0, "seats_total": 1, "tier": "free", "activations": []})

    try:
        lic_data = json.loads(license_path.read_text(encoding="utf-8"))
    except Exception:
        return ok({"seats_used": 0, "seats_total": 1, "tier": "free", "activations": []})

    tier = lic_data.get("tier", "free")
    seats_total = int(lic_data.get("seats", 1))
    method = lic_data.get("activation_method", "")
    instance_id = lic_data.get("instance_id")
    email = lic_data.get("email")
    activated_at = lic_data.get("activated_at")
    last_validated = lic_data.get("last_validated")

    # This machine counts as 1 used seat
    activations = []
    if instance_id:
        import platform
        activations.append({
            "instance_id": instance_id,
            "machine": platform.node(),
            "platform": platform.system(),
            "activated_at": activated_at,
            "is_current": True,
        })

    # Grace period info
    grace_days = None
    if method == "lemonsqueezy" and last_validated:
        try:
            from codrag.core.lemon_squeezy import grace_period_days_remaining
            grace_days = grace_period_days_remaining(last_validated)
        except Exception:
            pass

    return ok({
        "seats_used": len(activations),
        "seats_total": seats_total,
        "tier": tier,
        "email": email,
        "activation_method": method,
        "instance_id": instance_id,
        "last_validated": last_validated,
        "grace_days_remaining": grace_days,
        "activations": activations,
    })


@router.post("/license/dev-override")
def set_dev_tier_override(req: DevTierOverrideRequest) -> Dict[str, Any]:
    """Set or clear a dev tier override via CODRAG_TIER env var.

    This is a development/testing tool — it overrides the effective tier
    for the running process without modifying the license file on disk.
    """
    allowed = {"free", "pro", "team", "enterprise"}
    tier = (req.tier or "").strip().lower()

    if not tier:
        # Clear override — revert to real license
        os.environ.pop("CODRAG_TIER", None)
        os.environ.pop("CODRAG_DEV_MODE", None)
        logger.info("Cleared dev tier override")
    else:
        if tier not in allowed:
            raise ApiException(
                status_code=400,
                code="VALIDATION_ERROR",
                message=f"Invalid tier: {tier}. Must be one of: {', '.join(sorted(allowed))}",
            )
        os.environ["CODRAG_TIER"] = tier
        os.environ["CODRAG_DEV_MODE"] = "1"
        logger.info("Set dev tier override: %s", tier)

    clear_license_cache()
    return get_license_status()
