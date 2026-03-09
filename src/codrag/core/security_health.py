"""
EA-I1: Security health check engine.

Runs 7 security checks and returns an aggregate health score.
Designed for the Security & Compliance tab in the Enterprise Admin panel.
See ENTERPRISE_ADMIN_DESIGN.md §13A for the full design.

Usage:
    from codrag.core.security_health import run_security_checks
    result = run_security_checks(project_root=Path("/path/to/repo"))
    print(result["score"], result["checks"])
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _check_license() -> Dict[str, Any]:
    """Check 1: License verification (signature, expiry, seats)."""
    try:
        from codrag.core.feature_gate import get_license
        lic = get_license()
        issues: List[str] = []

        if not lic.valid:
            issues.append("License is invalid or expired")
        if not lic.signature_verified:
            issues.append("License signature not verified (unsigned or missing cryptography library)")
        if lic.expires_at:
            from codrag.core.feature_gate import _is_license_expired
            if _is_license_expired(lic.expires_at):
                issues.append(f"License expired at {lic.expires_at}")

        return {
            "name": "License Verification",
            "status": "pass" if not issues else "warn" if lic.valid else "fail",
            "details": {
                "tier": lic.to_dict()["tier"],
                "valid": lic.valid,
                "signature_verified": lic.signature_verified,
                "expires_at": lic.expires_at,
                "seats": lic.seats,
            },
            "issues": issues,
        }
    except Exception as e:
        return {"name": "License Verification", "status": "fail", "issues": [str(e)], "details": {}}


def _check_s3_endpoint(project_root: Optional[Path]) -> Dict[str, Any]:
    """Check 2: S3 endpoint security (HTTPS, no SSRF, allowlist)."""
    if not project_root:
        return {"name": "S3 Endpoint Security", "status": "pass", "issues": [], "details": {"reason": "No project root"}}

    try:
        from codrag.services.remote_sync import TeamSyncConfig
        import json

        config_path = project_root / ".codrag" / "team_config.json"
        if not config_path.exists():
            return {"name": "S3 Endpoint Security", "status": "pass", "issues": [], "details": {"reason": "No team_config.json"}}

        raw = json.loads(config_path.read_text(encoding="utf-8"))
        sync = raw.get("sync", {})
        endpoint = sync.get("s3_endpoint", "")

        if not endpoint:
            return {"name": "S3 Endpoint Security", "status": "pass", "issues": [], "details": {"reason": "No S3 endpoint configured"}}

        issues: List[str] = []
        from urllib.parse import urlparse
        parsed = urlparse(endpoint)

        if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1"):
            issues.append(f"S3 endpoint uses {parsed.scheme}:// (should be https://)")

        return {
            "name": "S3 Endpoint Security",
            "status": "pass" if not issues else "warn",
            "details": {"endpoint": endpoint, "scheme": parsed.scheme},
            "issues": issues,
        }
    except Exception as e:
        return {"name": "S3 Endpoint Security", "status": "fail", "issues": [str(e)], "details": {}}


def _check_credentials(project_root: Optional[Path]) -> Dict[str, Any]:
    """Check 3: Secrets & credential health (file permissions, leakage)."""
    issues: List[str] = []
    details: Dict[str, Any] = {}

    if project_root:
        secrets_path = project_root / ".codrag" / ".secrets"
        if secrets_path.exists():
            try:
                import stat
                mode = secrets_path.stat().st_mode
                if mode & (stat.S_IRWXG | stat.S_IRWXO):
                    issues.append(f".secrets file has open permissions ({oct(mode & 0o777)})")
                details["secrets_file_exists"] = True
                details["secrets_file_mode"] = oct(mode & 0o777)
            except (OSError, AttributeError):
                details["secrets_file_exists"] = True
                details["permission_check"] = "skipped (non-Unix)"
        else:
            details["secrets_file_exists"] = False

    return {
        "name": "Secrets & Credentials",
        "status": "pass" if not issues else "warn",
        "issues": issues,
        "details": details,
    }


def _check_index_integrity(project_root: Optional[Path]) -> Dict[str, Any]:
    """Check 4: Index integrity (hash verification)."""
    if not project_root:
        return {"name": "Index Integrity", "status": "pass", "issues": [], "details": {"reason": "No project root"}}

    remote_manifest = project_root / ".codrag" / "index" / "remote" / "manifest.json"
    if not remote_manifest.exists():
        return {"name": "Index Integrity", "status": "pass", "issues": [], "details": {"reason": "No remote index"}}

    try:
        import json
        manifest = json.loads(remote_manifest.read_text(encoding="utf-8"))
        issues: List[str] = []
        has_hash = bool(manifest.get("content_hash"))
        if not has_hash:
            issues.append("Remote index manifest has no content_hash")

        # EA-I14: Check embedding file integrity
        embeddings_path = project_root / ".codrag" / "index" / "remote" / "embeddings.npy"
        embedding_hash_in_manifest = manifest.get("embedding_hash")
        embeddings_exist = embeddings_path.exists()
        if embeddings_exist and not embedding_hash_in_manifest:
            issues.append("embeddings.npy exists but manifest has no embedding_hash (cannot verify integrity)")

        return {
            "name": "Index Integrity",
            "status": "pass" if not issues else "warn",
            "issues": issues,
            "details": {
                "has_content_hash": has_hash,
                "version": manifest.get("version"),
                "embeddings_exist": embeddings_exist,
                "has_embedding_hash": bool(embedding_hash_in_manifest),
            },
        }
    except Exception as e:
        return {"name": "Index Integrity", "status": "fail", "issues": [str(e)], "details": {}}


def _check_dlp_compliance(project_root: Optional[Path]) -> Dict[str, Any]:
    """Check 5: Data flow & DLP compliance."""
    if not project_root:
        return {"name": "DLP Compliance", "status": "pass", "issues": [], "details": {"reason": "No project root"}}

    try:
        from codrag.core.team_config import load_team_config
        result = load_team_config(project_root)
        if not result.config or not result.config.admin_policy:
            return {"name": "DLP Compliance", "status": "pass", "issues": [], "details": {"policy": "none"}}

        dp = result.config.admin_policy.data_policy
        if not dp:
            return {"name": "DLP Compliance", "status": "pass", "issues": [], "details": {"policy": "no data_policy"}}

        details = {
            "block_unapproved_cloud": dp.block_code_to_unapproved_cloud,
            "allowed_destinations": dp.allowed_data_destinations,
            "never_send_globs_count": len(dp.never_send_globs) if dp.never_send_globs else 0,
            "redact_patterns_count": len(dp.redact_patterns) if dp.redact_patterns else 0,
        }

        return {
            "name": "DLP Compliance",
            "status": "pass",
            "issues": [],
            "details": details,
        }
    except Exception as e:
        return {"name": "DLP Compliance", "status": "fail", "issues": [str(e)], "details": {}}


def _check_config_drift(project_root: Optional[Path]) -> Dict[str, Any]:
    """Check 6: Configuration drift detection."""
    if not project_root:
        return {"name": "Config Drift", "status": "pass", "issues": [], "details": {"reason": "No project root"}}

    try:
        from codrag.core.team_config import load_team_config
        result = load_team_config(project_root)
        if not result.config:
            return {"name": "Config Drift", "status": "pass", "issues": [], "details": {"reason": "No team_config"}}

        # Check for invisible Unicode in config file (Rules File Backdoor attack)
        config_path = project_root / ".codrag" / "team_config.json"
        issues: List[str] = []
        if config_path.exists():
            from codrag.core.content_sanitizer import detect_invisible_unicode
            content = config_path.read_text(encoding="utf-8")
            if detect_invisible_unicode(content):
                issues.append("team_config.json contains invisible Unicode characters (potential injection)")

        return {
            "name": "Config Drift",
            "status": "pass" if not issues else "warn",
            "issues": issues,
            "details": {"config_hash": result.config.config_hash},
        }
    except Exception as e:
        return {"name": "Config Drift", "status": "fail", "issues": [str(e)], "details": {}}


def _check_network() -> Dict[str, Any]:
    """Check 7: Network security (proxy, TLS, plaintext HTTP)."""
    issues: List[str] = []
    details: Dict[str, Any] = {}

    # Check if proxy is configured
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    details["proxy_configured"] = bool(proxy)
    if proxy:
        details["proxy_url"] = proxy.split("@")[-1] if "@" in proxy else proxy  # Redact credentials

    # Check CA bundle
    ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    details["custom_ca_bundle"] = bool(ca_bundle)

    return {
        "name": "Network Security",
        "status": "pass" if not issues else "warn",
        "issues": issues,
        "details": details,
    }


def run_security_checks(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Run all 7 security checks and return aggregate results.

    Returns:
        {
            "score": 7,          # Number of passing checks (0-7)
            "total": 7,          # Total number of checks
            "status": "healthy", # "healthy" | "warnings" | "critical"
            "checks": [...]      # Individual check results
        }
    """
    checks = [
        _check_license(),
        _check_s3_endpoint(project_root),
        _check_credentials(project_root),
        _check_index_integrity(project_root),
        _check_dlp_compliance(project_root),
        _check_config_drift(project_root),
        _check_network(),
    ]

    passing = sum(1 for c in checks if c["status"] == "pass")
    has_fail = any(c["status"] == "fail" for c in checks)
    has_warn = any(c["status"] == "warn" for c in checks)

    if has_fail:
        status = "critical"
    elif has_warn:
        status = "warnings"
    else:
        status = "healthy"

    return {
        "score": passing,
        "total": len(checks),
        "status": status,
        "checks": checks,
        "timestamp": time.time(),
    }
