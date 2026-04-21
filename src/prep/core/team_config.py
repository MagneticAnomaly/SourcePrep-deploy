from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Any, Dict, List, Optional, Tuple

from .ids import stable_sha256

logger = logging.getLogger(__name__)


TEAM_CONFIG_REL_PATH = Path(".runprep") / "team_config.json"


@dataclass(frozen=True)
class TeamConfig:
    format_version: int
    enforcement_mode: str
    include_globs: List[str]
    exclude_globs: List[str]
    trace_enabled_default: bool
    embedding_provider: Optional[str]
    embedding_model: Optional[str]
    config_hash: str


@dataclass(frozen=True)
class TeamConfigLoadResult:
    present: bool
    path: Optional[Path]
    config: Optional[TeamConfig]
    error: Optional[str]


def team_config_path(project_root: Path) -> Path:
    return Path(project_root).resolve() / TEAM_CONFIG_REL_PATH


def _normalize_globs(v: Any) -> List[str]:
    if not isinstance(v, list):
        return []
    out: List[str] = []
    for x in v:
        if isinstance(x, str):
            s = x.strip()
            if s:
                out.append(s)
    return sorted(set(out))


def _canonical_json_for_hash(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _semantic_subset(raw: Dict[str, Any]) -> Dict[str, Any]:
    enforcement = raw.get("enforcement")
    if not isinstance(enforcement, dict):
        enforcement = {}

    policy = raw.get("policy")
    if not isinstance(policy, dict):
        policy = {}

    features = raw.get("features")
    if not isinstance(features, dict):
        features = {}

    models = raw.get("models")
    if not isinstance(models, dict):
        models = {}

    trace_enabled_default = features.get("trace_enabled_default")
    if not isinstance(trace_enabled_default, bool):
        trace_enabled_default = False

    embedding_provider = models.get("embedding_provider")
    if not isinstance(embedding_provider, str) or not embedding_provider.strip():
        embedding_provider = None

    embedding_model = models.get("embedding_model")
    if not isinstance(embedding_model, str) or not embedding_model.strip():
        embedding_model = None

    return {
        "format_version": raw.get("format_version"),
        "enforcement": {"mode": enforcement.get("mode")},
        "policy": {
            "include_globs": _normalize_globs(policy.get("include_globs")),
            "exclude_globs": _normalize_globs(policy.get("exclude_globs")),
        },
        "features": {"trace_enabled_default": trace_enabled_default},
        "models": {"embedding_provider": embedding_provider, "embedding_model": embedding_model},
    }


def load_team_config(project_root: Path) -> TeamConfigLoadResult:
    path = team_config_path(project_root)
    if not path.exists():
        return TeamConfigLoadResult(present=False, path=None, config=None, error=None)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return TeamConfigLoadResult(present=True, path=path, config=None, error=f"Invalid JSON: {e}")

    if not isinstance(raw, dict):
        return TeamConfigLoadResult(present=True, path=path, config=None, error="team_config must be a JSON object")

    normalized = _semantic_subset(raw)

    fv = normalized.get("format_version")
    if not isinstance(fv, int):
        return TeamConfigLoadResult(present=True, path=path, config=None, error="format_version must be an integer")
    if fv != 1:
        return TeamConfigLoadResult(present=True, path=path, config=None, error=f"Unsupported format_version: {fv}")

    enforcement_mode = (normalized.get("enforcement") or {}).get("mode")
    if not isinstance(enforcement_mode, str) or enforcement_mode not in {"warn", "strict"}:
        return TeamConfigLoadResult(
            present=True,
            path=path,
            config=None,
            error="enforcement.mode must be one of: warn, strict",
        )

    policy = normalized.get("policy") or {}
    include_globs = policy.get("include_globs") or []
    exclude_globs = policy.get("exclude_globs") or []

    features = normalized.get("features") or {}
    trace_enabled_default = features.get("trace_enabled_default")
    if not isinstance(trace_enabled_default, bool):
        trace_enabled_default = False

    models = normalized.get("models") or {}
    embedding_provider = models.get("embedding_provider")
    embedding_model = models.get("embedding_model")

    cfg_hash = stable_sha256(_canonical_json_for_hash(normalized), length=16)

    return TeamConfigLoadResult(
        present=True,
        path=path,
        config=TeamConfig(
            format_version=fv,
            enforcement_mode=enforcement_mode,
            include_globs=list(include_globs),
            exclude_globs=list(exclude_globs),
            trace_enabled_default=trace_enabled_default,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            config_hash=cfg_hash,
        ),
        error=None,
    )


# ── EA-C1: Admin Policy Schema ───────────────────────────────────────
#
# The admin_policy section of team_config.json lets IT administrators
# control which providers, models, and data handling rules are allowed.
# Two enforcement modes:
#   "suggest" — log violations but allow the action
#   "enforce" — block the action entirely

_LOCAL_PROVIDERS = {"ollama", "lm-studio"}


@dataclass(frozen=True)
class ProviderPolicy:
    """Which LLM providers are allowed/blocked."""
    allowed_providers: List[str] = field(default_factory=list)
    blocked_providers: List[str] = field(default_factory=list)
    allow_local_providers: bool = True
    allow_user_endpoints: bool = True
    allow_user_api_keys: bool = True
    locked_endpoints: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ModelPolicy:
    """Model restrictions."""
    allowed_models: List[str] = field(default_factory=list)
    blocked_models: List[str] = field(default_factory=list)
    require_approved_models: bool = False
    allow_any_local_model: bool = True
    # GW-3: Per-slot overrides
    # e.g. {"code": {"allowed_models": ["qwen2.5-coder"], "blocked_models": [], "require_approved_models": True}}
    slot_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class DataPolicy:
    """DLP: what data can be sent to which providers."""
    never_send_globs: List[str] = field(default_factory=list)
    redact_patterns: List[str] = field(default_factory=list)
    block_unapproved_cloud: bool = False
    allowed_destinations: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class SyncPolicy:
    """Team sync security constraints."""
    require_s3_https: bool = True
    allowed_s3_endpoints: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class NetworkPolicy:
    """Network-level restrictions."""
    block_metadata_endpoints: bool = True
    allowed_ports: List[int] = field(default_factory=list)


@dataclass(frozen=True)
class BudgetPolicy:
    """Token and cost budget limits."""
    monthly_token_limit: int = 0
    monthly_cost_limit_usd: float = 0.0
    alert_threshold_percent: float = 0.8


@dataclass(frozen=True)
class AdminPolicy:
    """Top-level admin policy from team_config.json admin_policy section."""
    provider: ProviderPolicy = field(default_factory=ProviderPolicy)
    model: ModelPolicy = field(default_factory=ModelPolicy)
    data: DataPolicy = field(default_factory=DataPolicy)
    sync: SyncPolicy = field(default_factory=SyncPolicy)
    network: NetworkPolicy = field(default_factory=NetworkPolicy)
    budgets: BudgetPolicy = field(default_factory=BudgetPolicy)
    enforcement_mode: str = "suggest"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict for the API."""
        from dataclasses import asdict
        return asdict(self)


def _str_list(raw: Any) -> List[str]:
    """Safely extract a list of strings from raw JSON."""
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if isinstance(x, str) and x.strip()]


def _int_list(raw: Any) -> List[int]:
    """Safely extract a list of ints from raw JSON."""
    if not isinstance(raw, list):
        return []
    out = []
    for x in raw:
        try:
            out.append(int(x))
        except (ValueError, TypeError):
            pass
    return out


def parse_admin_policy(raw: Dict[str, Any]) -> AdminPolicy:
    """Parse the admin_policy section from team_config JSON.

    Tolerant of missing keys — returns safe defaults for anything absent.
    """
    ap = raw.get("admin_policy")
    if not isinstance(ap, dict):
        return AdminPolicy()

    # Provider policy
    prov_raw = ap.get("provider") or {}
    provider = ProviderPolicy(
        allowed_providers=_str_list(prov_raw.get("allowed_providers")),
        blocked_providers=_str_list(prov_raw.get("blocked_providers")),
        allow_local_providers=bool(prov_raw.get("allow_local_providers", True)),
        allow_user_endpoints=bool(prov_raw.get("allow_user_endpoints", True)),
        allow_user_api_keys=bool(prov_raw.get("allow_user_api_keys", True)),
        locked_endpoints=list(prov_raw.get("locked_endpoints", [])),
    )

    # Model policy
    mod_raw = ap.get("model") or {}
    slot_overrides = {}
    if isinstance(mod_raw.get("slot_overrides"), dict):
        for k, v in mod_raw["slot_overrides"].items():
            if isinstance(v, dict):
                slot_overrides[str(k)] = {
                    "allowed_models": _str_list(v.get("allowed_models")),
                    "blocked_models": _str_list(v.get("blocked_models")),
                    "require_approved_models": bool(v.get("require_approved_models", False)),
                }

    model = ModelPolicy(
        allowed_models=_str_list(mod_raw.get("allowed_models")),
        blocked_models=_str_list(mod_raw.get("blocked_models")),
        require_approved_models=bool(mod_raw.get("require_approved_models", False)),
        allow_any_local_model=bool(mod_raw.get("allow_any_local_model", True)),
        slot_overrides=slot_overrides,
    )

    # Data policy (DLP)
    data_raw = ap.get("data") or {}
    data = DataPolicy(
        never_send_globs=_str_list(data_raw.get("never_send_globs")),
        redact_patterns=_str_list(data_raw.get("redact_patterns")),
        block_unapproved_cloud=bool(data_raw.get("block_unapproved_cloud", False)),
        allowed_destinations=_str_list(data_raw.get("allowed_destinations")),
    )

    # Sync policy
    sync_raw = ap.get("sync") or {}
    sync = SyncPolicy(
        require_s3_https=bool(sync_raw.get("require_s3_https", True)),
        allowed_s3_endpoints=_str_list(sync_raw.get("allowed_s3_endpoints")),
    )

    # Network policy
    net_raw = ap.get("network") or {}
    network = NetworkPolicy(
        block_metadata_endpoints=bool(net_raw.get("block_metadata_endpoints", True)),
        allowed_ports=_int_list(net_raw.get("allowed_ports")),
    )

    # Budget policy
    bud_raw = ap.get("budgets") or {}
    budgets = BudgetPolicy(
        monthly_token_limit=int(bud_raw.get("monthly_token_limit", 0)),
        monthly_cost_limit_usd=float(bud_raw.get("monthly_cost_limit_usd", 0.0)),
        alert_threshold_percent=float(bud_raw.get("alert_threshold_percent", 0.8)),
    )

    mode = str(ap.get("enforcement_mode", "suggest")).lower()
    if mode not in ("suggest", "enforce"):
        mode = "suggest"

    return AdminPolicy(
        provider=provider,
        model=model,
        data=data,
        sync=sync,
        network=network,
        budgets=budgets,
        enforcement_mode=mode,
    )


# ── EA-C8: Policy Enforcement Utilities ───────────────────────────────


def is_provider_allowed(provider: str, policy: AdminPolicy) -> bool:
    """Check if a provider is allowed by the admin policy.

    Local providers (ollama, lm-studio) are always allowed unless
    allow_local_providers is explicitly False.
    """
    p = provider.lower().strip()

    # Local providers get a pass unless explicitly disabled
    if p in _LOCAL_PROVIDERS and policy.provider.allow_local_providers:
        return True

    # Check explicit blocklist first
    if policy.provider.blocked_providers:
        if p in [x.lower() for x in policy.provider.blocked_providers]:
            return False

    # If allowlist is set, provider must be on it
    if policy.provider.allowed_providers:
        return p in [x.lower() for x in policy.provider.allowed_providers]

    # No restrictions → allowed
    return True


def is_model_allowed(
    model: str,
    policy: AdminPolicy,
    *,
    provider: Optional[str] = None,
    slot: Optional[str] = None,
) -> bool:
    """Check if a model name is allowed by the admin policy.

    Uses exact match for allowed_models and prefix/glob match for blocked_models.

    GW-1: If allow_any_local_model is True and the provider is a local provider
    (ollama, lm-studio), all model restrictions are bypassed. This lets developers
    use any model on local hardware while IT still controls cloud model access.

    GW-3: If slot is provided (e.g. "code", "large"), applies any slot_overrides
    defined in the policy before checking the base model policy.
    """
    m = model.lower().strip()

    # GW-1: Local providers bypass model restrictions when allow_any_local_model is True
    if provider and provider.lower() in _LOCAL_PROVIDERS and policy.model.allow_any_local_model:
        return True

    # GW-3: Determine effective allowed/blocked lists based on slot overrides
    allowed_models = policy.model.allowed_models
    blocked_models = policy.model.blocked_models
    require_approved = policy.model.require_approved_models

    if slot and slot in policy.model.slot_overrides:
        override = policy.model.slot_overrides[slot]
        if "allowed_models" in override:
            allowed_models = override["allowed_models"]
        if "blocked_models" in override:
            blocked_models = override["blocked_models"]
        if "require_approved_models" in override:
            require_approved = override["require_approved_models"]

    # Check blocklist (prefix matching)
    for pattern in blocked_models:
        pat = pattern.lower().strip()
        if pat in m or m.startswith(pat):
            return False

    # If allowlist is set and require_approved_models, model must be on it
    if require_approved and allowed_models:
        allowed_lower = [x.lower().strip() for x in allowed_models]
        # Check exact match or prefix match (e.g. "qwen3" matches "qwen3:8b")
        for allowed in allowed_lower:
            if m == allowed or m.startswith(allowed + ":"):
                return True
        return False

    # Check allowlist if set (non-strict mode — allowed_models as suggestions)
    # In non-strict mode, allowed_models is informational only
    return True


def filter_models_by_policy(
    models: List[str],
    policy: AdminPolicy,
    *,
    slot: Optional[str] = None,
) -> List[str]:
    """Filter a list of model names through the admin policy."""
    return [m for m in models if is_model_allowed(m, policy, slot=slot)]


def check_policy_violation(
    action: str,
    policy: AdminPolicy,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Tuple[bool, str]:
    """Check if an action violates the admin policy.

    Returns (allowed, reason).
    - In 'suggest' mode: always returns (True, reason) but logs the violation.
    - In 'enforce' mode: returns (False, reason) if policy is violated.
    """
    violations: List[str] = []

    if provider and not is_provider_allowed(provider, policy):
        violations.append(f"Provider '{provider}' is not allowed by admin policy")

    if model and not is_model_allowed(model, policy):
        violations.append(f"Model '{model}' is not allowed by admin policy")

    if not violations:
        return True, ""

    reason = "; ".join(violations)

    if policy.enforcement_mode == "suggest":
        logger.warning("ADMIN POLICY (suggest): %s — action: %s", reason, action)
        return True, reason

    # enforce mode
    logger.warning("ADMIN POLICY (enforce): BLOCKED %s — %s", action, reason)
    return False, reason


def load_admin_policy(project_root: Path) -> AdminPolicy:
    """Load admin policy from team_config.json for a project.

    Returns a default (permissive) AdminPolicy if the file doesn't exist
    or has no admin_policy section.
    """
    path = team_config_path(project_root)
    if not path.exists():
        return AdminPolicy()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return AdminPolicy()
        return parse_admin_policy(raw)
    except Exception as e:
        logger.warning("Failed to load admin policy from %s: %s", path, e)
        return AdminPolicy()
