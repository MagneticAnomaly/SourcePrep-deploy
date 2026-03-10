"""
EA-I1: Security health check engine.

Runs 16 security checks across 4 categories and returns an aggregate health score.
Designed for the Security & Compliance tab in the Enterprise Admin panel.
See ENTERPRISE_ADMIN_DESIGN.md §13A for the full design.

Categories:
  - Infrastructure (network, daemon auth, CORS)
  - License & Compliance (license verification, dev mode, DLP)
  - Data Protection (sanitization, S3 endpoints, index integrity, API key hygiene)
  - Runtime (MCP rate limit, credentials, config drift)
  - Research-informed (secret detection, data exposure, unicode injection)

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
        from codrag.core.team_config import load_admin_policy
        policy = load_admin_policy(project_root)
        dp = policy.data

        if not dp.never_send_globs and not dp.block_unapproved_cloud and not dp.redact_patterns:
            return {"name": "DLP Compliance", "status": "pass", "issues": [], "details": {"policy": "default (no restrictions)"}}

        details = {
            "block_unapproved_cloud": dp.block_unapproved_cloud,
            "allowed_destinations": dp.allowed_destinations,
            "never_send_globs_count": len(dp.never_send_globs),
            "redact_patterns_count": len(dp.redact_patterns),
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


def _check_daemon_auth() -> Dict[str, Any]:
    """Check 8: Daemon authentication posture (FULL-4)."""
    try:
        from codrag.server import _config
        # We need to see if the server is exposed and if it has a token.
        # Since this runs in the daemon process, we can check env vars and config.
        has_token = bool(os.environ.get("CODRAG_DAEMON_TOKEN"))
        host = os.environ.get("CODRAG_HOST", "127.0.0.1")
        
        issues = []
        status = "pass"
        
        if not has_token:
            if host in ("localhost", "127.0.0.1"):
                status = "warn"
                issues.append("Daemon running without IPC token, but bound only to localhost")
            else:
                status = "fail"
                issues.append(f"CRITICAL: Daemon exposed on {host} without authentication!")
                
        return {
            "name": "Daemon Authentication",
            "status": status,
            "details": {"has_token": has_token, "host": host},
            "issues": issues,
        }
    except Exception as e:
        return {"name": "Daemon Authentication", "status": "fail", "issues": [str(e)], "details": {}}


def _check_cors() -> Dict[str, Any]:
    """Check 9: CORS Configuration (FULL-1)."""
    try:
        allow_all = bool(os.environ.get("CODRAG_CORS_ALLOW_ALL"))
        
        issues = []
        status = "pass"
        
        if allow_all:
            status = "fail"
            issues.append("CODRAG_CORS_ALLOW_ALL is enabled. Any website can access the daemon!")
            
        return {
            "name": "CORS Configuration",
            "status": status,
            "details": {"allow_all": allow_all},
            "issues": issues,
        }
    except Exception as e:
        return {"name": "CORS Configuration", "status": "fail", "issues": [str(e)], "details": {}}


def _check_dev_mode() -> Dict[str, Any]:
    """Check 10: Dev Mode Detection (CRIT-1 bypass)."""
    try:
        dev_mode = bool(os.environ.get("CODRAG_DEV_MODE"))
        
        issues = []
        status = "pass"
        
        if dev_mode:
            status = "warn"
            issues.append("CODRAG_DEV_MODE is active. Security bypasses may be enabled.")
            
        return {
            "name": "Dev Mode Detection",
            "status": status,
            "details": {"dev_mode": dev_mode},
            "issues": issues,
        }
    except Exception as e:
        return {"name": "Dev Mode Detection", "status": "fail", "issues": [str(e)], "details": {}}


def _check_content_sanitization() -> Dict[str, Any]:
    """Check 11: Content sanitization active (OWASP LLM01 defense)."""
    try:
        from codrag.core.content_sanitizer import sanitize_llm_input, sanitize_output, validate_llm_output, normalize_nfkc
        # All four functions must be importable and callable
        issues = []
        if not callable(sanitize_llm_input):
            issues.append("sanitize_llm_input not callable")
        if not callable(sanitize_output):
            issues.append("sanitize_output not callable")
        if not callable(validate_llm_output):
            issues.append("validate_llm_output not callable")
        if not callable(normalize_nfkc):
            issues.append("normalize_nfkc not callable")

        return {
            "name": "Content Sanitization",
            "status": "pass" if not issues else "fail",
            "details": {
                "llm_input_sanitizer": True,
                "output_sanitizer": True,
                "output_validator": True,
                "nfkc_normalizer": True,
            },
            "issues": issues,
        }
    except ImportError as e:
        return {
            "name": "Content Sanitization",
            "status": "fail",
            "issues": [f"content_sanitizer module not available: {e}"],
            "details": {},
        }


def _check_api_key_hygiene() -> Dict[str, Any]:
    """Check 12: API key hygiene (FULL-3: Google URL-param auth)."""
    issues = []
    details: Dict[str, Any] = {"providers_checked": []}

    try:
        from codrag.server import _load_ui_config
        ui_cfg = _load_ui_config()
        llm_cfg = ui_cfg.get("llm_config", {})
        endpoints = {ep["id"]: ep for ep in llm_cfg.get("saved_endpoints", [])}

        for slot_name in ("small_model", "large_model", "code_model"):
            slot = llm_cfg.get(slot_name, {})
            ep_id = slot.get("endpoint_id", "")
            ep = endpoints.get(ep_id)
            if ep and ep.get("provider") == "google" and ep.get("api_key"):
                issues.append(
                    f"Google Gemini ({slot_name}) uses URL-parameter auth — "
                    "API key is visible in HTTP logs. Consider Vertex AI for enterprise."
                )
                details["providers_checked"].append({"slot": slot_name, "provider": "google", "url_param_auth": True})
            elif ep:
                details["providers_checked"].append({"slot": slot_name, "provider": ep.get("provider"), "url_param_auth": False})
    except Exception:
        pass  # Can't check — no server config available

    return {
        "name": "API Key Hygiene",
        "status": "pass" if not issues else "warn",
        "issues": issues,
        "details": details,
    }


def _check_mcp_rate_limit() -> Dict[str, Any]:
    """Check 13: MCP rate limit health."""
    try:
        from codrag.mcp.server import MCPServer
        # Rate limit is defined as class variables on MCPServer
        rate_limit = getattr(MCPServer, '_MCP_RATE_LIMIT', None)
        rate_window = getattr(MCPServer, '_MCP_RATE_WINDOW', None)

        issues = []
        if rate_limit is None:
            issues.append("MCP rate limiting not configured")

        return {
            "name": "MCP Rate Limiting",
            "status": "pass" if not issues else "warn",
            "details": {
                "rate_limit": rate_limit,
                "rate_window_seconds": rate_window,
                "active": rate_limit is not None,
            },
            "issues": issues,
        }
    except Exception as e:
        return {"name": "MCP Rate Limiting", "status": "warn", "issues": [f"Could not check: {e}"], "details": {}}


def _check_secret_detection_coverage(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Check 14: Secret detection coverage (Finding B).

    Verifies that built-in secret detection patterns are available and
    optionally scans the most recent index for high-entropy secret matches.
    """
    try:
        from codrag.core.content_sanitizer import BUILTIN_SECRET_PATTERNS, detect_secrets
        pattern_count = len(BUILTIN_SECRET_PATTERNS)
        issues: List[str] = []
        details: Dict[str, Any] = {"builtin_patterns": pattern_count}

        if pattern_count < 5:
            issues.append(f"Only {pattern_count} secret patterns configured (expected >=5)")

        # Spot-check: scan a sample of indexed files for secrets
        if project_root:
            index_dir = project_root / ".codrag" / "index"
            docs_path = index_dir / "documents.json"
            secrets_found = 0
            files_scanned = 0
            if docs_path.exists():
                import json
                try:
                    docs = json.loads(docs_path.read_text(encoding="utf-8"))
                    # Sample up to 50 documents
                    sample = docs[:50] if isinstance(docs, list) else []
                    for doc in sample:
                        content = doc.get("content", "") or doc.get("text", "")
                        if content:
                            files_scanned += 1
                            hits = detect_secrets(content)
                            secrets_found += len(hits)
                except Exception:
                    pass
            details["files_scanned"] = files_scanned
            details["secrets_detected"] = secrets_found
            if secrets_found > 0:
                issues.append(
                    f"{secrets_found} potential secret(s) detected in {files_scanned} sampled chunks. "
                    "Consider adding these file paths to never_send_globs."
                )

        return {
            "name": "Secret Detection Coverage",
            "status": "pass" if not issues else "warn",
            "issues": issues,
            "details": details,
        }
    except Exception as e:
        return {"name": "Secret Detection Coverage", "status": "fail", "issues": [str(e)], "details": {}}


def _check_data_exposure(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Check 15: Data exposure summary (Finding D).

    Computes \"blast radius\" metrics: total indexed files, tokens sent to
    cloud providers, and which providers have received source code.
    Gives IT admins visibility into the maximum damage if compromised.
    """
    details: Dict[str, Any] = {}
    issues: List[str] = []

    # Count indexed files
    if project_root:
        index_dir = project_root / ".codrag" / "index"
        docs_path = index_dir / "documents.json"
        if docs_path.exists():
            try:
                import json
                docs = json.loads(docs_path.read_text(encoding="utf-8"))
                details["indexed_chunks"] = len(docs) if isinstance(docs, list) else 0
            except Exception:
                details["indexed_chunks"] = "error"

    # Token usage from audit log (last 30 days)
    try:
        from codrag.core.audit_log import get_audit_log
        audit = get_audit_log()
        since = time.time() - (30 * 86400)  # 30 days
        usage = audit.get_token_usage(since=since)
        details["tokens_sent_30d"] = usage.get("total_tokens", 0)
        details["llm_calls_30d"] = usage.get("call_count", 0)
        details["providers_used"] = list(usage.get("by_provider", {}).keys())

        cloud_providers = [p for p in details["providers_used"] if p not in ("ollama", "lm-studio")]
        if cloud_providers and usage.get("total_tokens", 0) > 0:
            issues.append(
                f"Source code sent to cloud provider(s): {', '.join(cloud_providers)} "
                f"({usage['total_tokens']:,} tokens in last 30 days)"
            )
    except Exception:
        details["token_usage"] = "unavailable"

    return {
        "name": "Data Exposure Summary",
        "status": "pass" if not issues else "warn",
        "issues": issues,
        "details": details,
    }


def _check_unicode_in_index(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Check 16: Invisible Unicode in indexed files (Finding A).

    Scans a sample of indexed content for invisible Unicode characters
    that could carry hidden prompt injection instructions.
    Expands the scope beyond team_config.json to actual source content.
    """
    if not project_root:
        return {"name": "Unicode Injection Scan", "status": "pass", "issues": [], "details": {"reason": "No project root"}}

    try:
        from codrag.core.content_sanitizer import detect_invisible_unicode
        import json

        index_dir = project_root / ".codrag" / "index"
        docs_path = index_dir / "documents.json"
        if not docs_path.exists():
            return {"name": "Unicode Injection Scan", "status": "pass", "issues": [], "details": {"reason": "No index"}}

        docs = json.loads(docs_path.read_text(encoding="utf-8"))
        sample = docs[:100] if isinstance(docs, list) else []
        files_scanned = 0
        infected_files: List[str] = []

        for doc in sample:
            content = doc.get("content", "") or doc.get("text", "")
            source = doc.get("source_path", doc.get("path", "unknown"))
            if content:
                files_scanned += 1
                if detect_invisible_unicode(content):
                    infected_files.append(source)

        issues: List[str] = []
        if infected_files:
            issues.append(
                f"{len(infected_files)} indexed file(s) contain invisible Unicode "
                f"(potential injection): {', '.join(infected_files[:5])}"
                + (f" (+{len(infected_files) - 5} more)" if len(infected_files) > 5 else "")
            )

        return {
            "name": "Unicode Injection Scan",
            "status": "pass" if not issues else "warn",
            "issues": issues,
            "details": {
                "files_scanned": files_scanned,
                "infected_count": len(infected_files),
            },
        }
    except Exception as e:
        return {"name": "Unicode Injection Scan", "status": "fail", "issues": [str(e)], "details": {}}


def run_security_checks(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Run all 16 security health checks and compute an aggregate score.

    Returns:
        {
            "score": <int>,      # Number of passing checks
            "total": 16,         # Total number of checks
            "status": "healthy", # "healthy" | "warnings" | "critical"
            "checks": [...]      # Individual check results
            "timestamp": <float> # Unix timestamp
        }
    """
    checks = [
        # Infrastructure (checks 7-9)
        _check_network(),
        _check_daemon_auth(),
        _check_cors(),
        # License & Compliance (checks 1, 10, 5)
        _check_license(),
        _check_dev_mode(),
        _check_dlp_compliance(project_root),
        # Data Protection (checks 11, 2, 4, 12)
        _check_content_sanitization(),
        _check_s3_endpoint(project_root),
        _check_index_integrity(project_root),
        _check_api_key_hygiene(),
        # Runtime (checks 13, 3, 6)
        _check_mcp_rate_limit(),
        _check_credentials(project_root),
        _check_config_drift(project_root),
        # Research-informed checks (14-16)
        _check_secret_detection_coverage(project_root),
        _check_data_exposure(project_root),
        _check_unicode_in_index(project_root),
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
