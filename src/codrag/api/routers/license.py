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


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/license")
def get_license_status() -> Dict[str, Any]:
    """Get current license tier and feature availability."""
    lic = get_license()
    features = {}
    for feat in [
        "auto_rebuild", "auto_trace", "trace_index", "trace_search",
        "mcp_tools", "mcp_trace_expand", "path_weights",
        "clara_compression", "multi_repo_agent", "team_config", "audit_log",
    ]:
        features[feat] = check_feature(feat)
    features["projects_max"] = get_feature_limit("projects_max")
    return ok({
        "license": lic.to_dict(),
        "features": features,
    })


@router.post("/license/activate")
def activate_license(req: ActivateLicenseRequest) -> Dict[str, Any]:
    key = str(req.key or "").strip()
    if not key:
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="key is required")

    allowed_tiers = {"free", "starter", "pro", "team", "enterprise"}
    lic_data: Optional[Dict[str, Any]] = None

    # 1. Try to verify as a signed offline key (Production/Enterprise)
    # This is the most secure method and should be prioritized.
    verified_payload = verify_license_key(key)
    if verified_payload:
        lic_data = verified_payload
        logger.info(f"Verified signed license key for {lic_data.get('issued_to', 'unknown')}")

    # 2. Dev/Testing: Allow direct tier names
    if lic_data is None:
        tier_guess = key.lower()
        if tier_guess in allowed_tiers:
            lic_data = {"tier": tier_guess, "valid": True, "seats": 1, "features": []}
            logger.info(f"Activated dev license via tier name: {tier_guess}")

    # 3. Dev/Testing: Allow plain JSON
    if lic_data is None:
        try:
            if key.startswith("{") and key.endswith("}"):
                parsed = json.loads(key)
                if isinstance(parsed, dict):
                    lic_data = dict(parsed)
                    logger.info("Activated dev license via plain JSON")
        except Exception:
            pass

    # 4. Legacy: Try Base64 encoded JSON (plain or JWT-like parts)
    # This is mostly for backward compatibility or simple encoding
    if lic_data is None and "." in key:
        parts = [p for p in key.split(".") if p]
        payload_part: Optional[str] = None
        if len(parts) >= 2:
            # Assume middle part is payload in header.payload.signature
            # Or first part in payload.signature
            payload_part = parts[1] if len(parts) >= 3 else parts[0]
        
        if payload_part:
            try:
                padded = payload_part + "=" * (-len(payload_part) % 4)
                decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
                parsed = json.loads(decoded)
                if isinstance(parsed, dict):
                    lic_data = dict(parsed)
                    logger.info("Activated license via legacy token parsing")
            except Exception:
                pass

    if lic_data is None:
        # Final attempt: try decoding the whole key as base64
        try:
            padded = key + "=" * (-len(key) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
            parsed = json.loads(decoded)
            if isinstance(parsed, dict):
                lic_data = dict(parsed)
                logger.info("Activated license via base64 decoding")
        except Exception:
            pass

    if lic_data is None:
        raise ApiException(
            status_code=400,
            code="INVALID_LICENSE",
            message="Invalid license key",
            hint="Provide a valid signed license key, or a tier name (free/starter/pro) for development.",
        )

    tier_raw = str(lic_data.get("tier") or "").strip().lower()
    if tier_raw not in allowed_tiers:
        raise ApiException(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"Invalid license tier: {tier_raw}. Must be one of: {', '.join(allowed_tiers)}",
        )

    lic_data["tier"] = tier_raw
    lic_data.setdefault("valid", True)
    lic_data.setdefault("seats", 1)
    lic_data.setdefault("features", [])

    # Ensure critical timestamps are present if available in meta
    if "expires_at" not in lic_data and "meta" in lic_data:
         # Some issuers might put expiry in meta, flatten it if needed or standard schema logic
         pass

    license_path = Path.home() / ".codrag" / "license.json"
    license_path.parent.mkdir(parents=True, exist_ok=True)
    license_path.write_text(json.dumps(lic_data, indent=2), encoding="utf-8")

    clear_license_cache()
    
    # Reload license to ensure we return what the system sees
    new_status = get_license_status()
    return new_status


@router.post("/license/deactivate")
def deactivate_license() -> Dict[str, Any]:
    license_path = Path.home() / ".codrag" / "license.json"
    try:
        if license_path.exists():
            license_path.unlink()
    except Exception:
        raise ApiException(status_code=500, code="IO_ERROR", message="Failed to remove license file")

    clear_license_cache()
    return get_license_status()
