"""
BYOK Batch Profiles — maps model capabilities to per-stage batch sizes.

When a user configures a cloud (BYOK) model, we auto-detect its output token
class and select a batch profile.  Each profile defines how many items to
batch per API call at each pipeline stage.

The user sees ONE setting ("Auto" / "Large" / "Standard" / "Compact" / "Off").
All per-stage numbers are derived under the hood.

See docs/Phase35_BYOK/BYOK_BATCH_LIMITS.md for the research behind these numbers.
See https://docs.codrag.io/guides/byok-batching for the public disclosure.
"""

from __future__ import annotations

import enum
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def _get_plan_tier() -> str:
    """Resolve the current Ollama Cloud plan tier from settings.

    Returns "free" when unset (safest default).  Overridden by tests via
    patch.

    Phase 112 Fix 8: previously imported from ``codrag.services.config_manager``,
    which does not export ``get_advanced_llm_settings`` — so the ImportError
    was silently caught and every caller got "free".  The function lives on
    ``codrag.server``; import from there.
    """
    try:
        from codrag.server import get_advanced_llm_settings
        settings = get_advanced_llm_settings()
        return settings.get("ollama_plan_tier", "free")
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("Failed to resolve plan tier, defaulting to free: %s", exc)
        return "free"


def _resolve_plan_tier_concurrency() -> int:
    """Map the current plan tier to a concrete concurrency value.

    Phase 112 Fix 9: when the user selects ``ollama_plan_tier == "custom"``,
    honor their ``custom_concurrency`` input (clamped to [1, 32], matching
    the UI validation in AdvancedLLMSettings.tsx).  Otherwise look up the
    fixed per-tier value in PLAN_TIER_CONCURRENCY.
    """
    from codrag.core.swarm_optimizer import PLAN_TIER_CONCURRENCY

    tier = _get_plan_tier()
    if tier == "custom":
        try:
            from codrag.server import get_advanced_llm_settings
            settings = get_advanced_llm_settings()
            raw = settings.get("custom_concurrency", 1)
            return max(1, min(32, int(raw)))
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("Failed to resolve custom_concurrency, defaulting to 1: %s", exc)
            return 1
    return PLAN_TIER_CONCURRENCY.get(tier, 1)


# ── Stage IDs (mirrors pipeline_orchestrator.StageId values) ──────

class BatchStage(str, enum.Enum):
    """Pipeline stages that support batching."""
    CATALOGUE_SYMBOL = "catalogue_symbol"
    CATALOGUE_FILE = "catalogue_file"
    INFERRED_EDGES = "inferred_edges"
    EPISTEMIC_CODE = "epistemic_code"
    EPISTEMIC_DOC = "epistemic_doc"
    CLUSTERING = "clustering"


# ── Batch Profile ─────────────────────────────────────────────────

class BatchProfileName(str, enum.Enum):
    """Named batch profiles selectable by the user."""
    AUTO = "auto"
    LARGE = "large"        # 64K output (Claude Sonnet 4, Gemini 2.5 Pro)
    STANDARD = "standard"  # 32K output (GPT-4.1, Claude Opus 4)
    COMPACT = "compact"    # 16K output (GPT-4o, DeepSeek, Gemini Flash)
    CLOUD_SMALL = "cloud_small"  # Ollama cloud (hard 16K limit, no override)
    OFF = "off"            # No batching (local model behavior)


@dataclass(frozen=True)
class BatchProfile:
    """Per-stage batch sizes for a given output token class."""
    name: BatchProfileName
    output_class: str  # human-readable description
    sizes: Dict[BatchStage, int] = field(default_factory=dict)

    def batch_size(self, stage: BatchStage) -> int:
        """Get batch size for a stage. Returns 1 if stage not in profile."""
        return self.sizes.get(stage, 1)


# ── Built-in Profiles ────────────────────────────────────────────

# ── Output Token Budget Reference (as of 2025-Q4) ────────────────
#
# Provider           Model                   Max Output Tokens
# ────────────────   ──────────────────────   ─────────────────
# Anthropic          Claude Sonnet 4          64,000
# Google             Gemini 2.5 Pro           65,536
# Anthropic          Claude Opus 4            32,000
# OpenAI             GPT-4.1                  32,768
# OpenAI             GPT-4o                   16,384
# Ollama Cloud       kimi, qwen, etc.         16,384 (HARD, no override)
#
# Ollama Cloud is the most restrictive: the 16K limit is enforced
# server-side and cannot be raised via num_predict.  Direct API
# providers (OpenAI, Anthropic, Google) allow setting max_tokens.
#
# Each catalogue item produces ~300–500 output tokens.
# Each inferred-edge item produces ~100–300 output tokens.
# Batch sizes below are calibrated to stay within ~80% of the
# output budget to leave headroom for JSON wrapper overhead.

PROFILE_LARGE = BatchProfile(
    name=BatchProfileName.LARGE,
    output_class="64K (Claude Sonnet 4, Gemini 2.5 Pro)",
    sizes={
        BatchStage.CATALOGUE_SYMBOL: 100,
        BatchStage.CATALOGUE_FILE: 100,
        BatchStage.INFERRED_EDGES: 50,
        BatchStage.EPISTEMIC_CODE: 50,
        BatchStage.EPISTEMIC_DOC: 15,
        BatchStage.CLUSTERING: 30,
    },
)

PROFILE_STANDARD = BatchProfile(
    name=BatchProfileName.STANDARD,
    output_class="32K (GPT-4.1, Claude Opus 4)",
    sizes={
        BatchStage.CATALOGUE_SYMBOL: 50,
        BatchStage.CATALOGUE_FILE: 50,
        BatchStage.INFERRED_EDGES: 30,
        BatchStage.EPISTEMIC_CODE: 25,
        BatchStage.EPISTEMIC_DOC: 10,
        BatchStage.CLUSTERING: 20,
    },
)

PROFILE_COMPACT = BatchProfile(
    name=BatchProfileName.COMPACT,
    output_class="16K (GPT-4o, DeepSeek, Gemini Flash)",
    sizes={
        BatchStage.CATALOGUE_SYMBOL: 20,
        BatchStage.CATALOGUE_FILE: 20,
        BatchStage.INFERRED_EDGES: 15,
        BatchStage.EPISTEMIC_CODE: 10,
        BatchStage.EPISTEMIC_DOC: 5,
        BatchStage.CLUSTERING: 10,
    },
)

# Ollama Cloud profile — hard 16K output limit that cannot be overridden.
# Smaller than COMPACT because the limit is absolute (no max_tokens knob)
# and thinking models (kimi) consume output budget on reasoning preamble.
PROFILE_CLOUD_SMALL = BatchProfile(
    name=BatchProfileName.CLOUD_SMALL,
    output_class="16K hard limit (Ollama Cloud: kimi, qwen, gemini)",
    sizes={
        BatchStage.CATALOGUE_SYMBOL: 5,
        BatchStage.CATALOGUE_FILE: 5,
        BatchStage.INFERRED_EDGES: 8,
        BatchStage.EPISTEMIC_CODE: 5,
        BatchStage.EPISTEMIC_DOC: 3,
        BatchStage.CLUSTERING: 5,
    },
)

PROFILE_OFF = BatchProfile(
    name=BatchProfileName.OFF,
    output_class="No batching (local model)",
    sizes={
        BatchStage.CATALOGUE_SYMBOL: 1,
        BatchStage.CATALOGUE_FILE: 1,
        BatchStage.INFERRED_EDGES: 1,
        BatchStage.EPISTEMIC_CODE: 1,
        BatchStage.EPISTEMIC_DOC: 1,
        BatchStage.CLUSTERING: 1,
    },
)

PROFILES: Dict[BatchProfileName, BatchProfile] = {
    BatchProfileName.LARGE: PROFILE_LARGE,
    BatchProfileName.STANDARD: PROFILE_STANDARD,
    BatchProfileName.COMPACT: PROFILE_COMPACT,
    BatchProfileName.CLOUD_SMALL: PROFILE_CLOUD_SMALL,
    BatchProfileName.OFF: PROFILE_OFF,
}


# ── Model Registry ───────────────────────────────────────────────
# Maps (provider, model_pattern) → profile name.
# Patterns are checked in order; first match wins.
# Uses regex on the model name for flexible matching.

_MODEL_REGISTRY = [
    # Anthropic — Haiku first (lower output limits despite version branding)
    ("anthropic", r"claude.*haiku.*(?:-|\\.|/)4(?:-|\\.|/)5", BatchProfileName.COMPACT),
    ("anthropic", r"claude.*haiku.*(?:-|\\.|/)3(?:-|\\.|/)5", BatchProfileName.COMPACT),
    ("anthropic", r"claude.*haiku", BatchProfileName.COMPACT),
    # Anthropic — Claude 4.5+ Sonnet/Opus (64K output)
    ("anthropic", r"claude.*(?:-|\\.|/)4(?:-|\\.|/)6", BatchProfileName.LARGE),
    ("anthropic", r"claude.*(?:-|\\.|/)4(?:-|\\.|/)5", BatchProfileName.LARGE),
    ("anthropic", r"claude.*(?:-|\\.|/)4(?:-|\\.|/|$)", BatchProfileName.LARGE),
    # Anthropic — Claude 3.x family (32K output)
    ("anthropic", r"claude.*(?:-|\\.|/)3", BatchProfileName.STANDARD),
    # Anthropic — catch-all
    ("anthropic", r".*", BatchProfileName.STANDARD),

    # OpenAI — GPT-5 family (treat as Standard until output limits confirmed)
    ("openai", r"gpt-5", BatchProfileName.STANDARD),
    # OpenAI — GPT-4.1 family (32K output, 1M context)
    # More specific patterns first to avoid gpt-4.1 matching before gpt-4.1-mini
    ("openai", r"gpt-4\.1-nano", BatchProfileName.STANDARD),
    ("openai", r"gpt-4\.1-mini", BatchProfileName.STANDARD),
    ("openai", r"gpt-4\.1", BatchProfileName.STANDARD),
    # OpenAI — GPT-4o family (16K output)
    ("openai", r"gpt-4o", BatchProfileName.COMPACT),
    # OpenAI — o-series reasoning models (100K output but expensive/slow)
    ("openai", r"o[34]", BatchProfileName.STANDARD),
    # OpenAI — catch-all
    ("openai", r".*", BatchProfileName.COMPACT),

    # OpenAI-compatible — covers many providers
    # Google Gemini via compatible API
    ("openai-compatible", r"gemini.*3.*pro", BatchProfileName.LARGE),
    ("openai-compatible", r"gemini.*3.*flash", BatchProfileName.COMPACT),
    ("openai-compatible", r"gemini.*2\.5.*pro", BatchProfileName.LARGE),
    ("openai-compatible", r"gemini.*2\.5.*flash", BatchProfileName.COMPACT),
    ("openai-compatible", r"gemini.*1\.5", BatchProfileName.COMPACT),
    # DeepSeek (8K output)
    ("openai-compatible", r"deepseek", BatchProfileName.COMPACT),
    # Claude via compatible API (e.g. AWS Bedrock, OpenRouter)
    ("openai-compatible", r"claude.*haiku", BatchProfileName.COMPACT),
    ("openai-compatible", r"claude.*(?:-|\\.|/)4(?:-|\\.|/)6", BatchProfileName.LARGE),
    ("openai-compatible", r"claude.*(?:-|\\.|/)4(?:-|\\.|/)5", BatchProfileName.LARGE),
    ("openai-compatible", r"claude.*(?:-|\\.|/)4(?:-|\\.|/|$)", BatchProfileName.LARGE),
    ("openai-compatible", r"claude.*(?:-|\\.|/)3", BatchProfileName.STANDARD),
    # GPT via compatible API (e.g. Azure, OpenRouter)
    ("openai-compatible", r"gpt-5", BatchProfileName.STANDARD),
    ("openai-compatible", r"gpt-4\.1", BatchProfileName.STANDARD),
    ("openai-compatible", r"gpt-4o", BatchProfileName.COMPACT),
    # Hosted open-weight models (Llama, Mistral, etc.)
    ("openai-compatible", r"llama", BatchProfileName.COMPACT),
    ("openai-compatible", r"mistral", BatchProfileName.COMPACT),
    ("openai-compatible", r"qwen", BatchProfileName.COMPACT),
    # Generic fallback for unknown compatible models
    ("openai-compatible", r".*", BatchProfileName.COMPACT),

    # Azure OpenAI — deployment names map to GPT models
    ("azure-openai", r"gpt-5", BatchProfileName.STANDARD),
    ("azure-openai", r"gpt-4\.1", BatchProfileName.STANDARD),
    ("azure-openai", r"gpt-4o", BatchProfileName.COMPACT),
    ("azure-openai", r"gpt-4", BatchProfileName.COMPACT),
    ("azure-openai", r".*", BatchProfileName.COMPACT),

    # Ollama — always local, no batching
    ("ollama", r".*", BatchProfileName.OFF),
]


# ── Local provider set (never batched) ────────────────────────────
_LOCAL_PROVIDERS = frozenset({"ollama", "lm-studio"})

# ── Cloud model patterns served via Ollama ────────────────────────
# These model families are always cloud-hosted even when accessed
# through the Ollama API (via ollama-cloud-code proxy or :cloud suffix).
_OLLAMA_CLOUD_PATTERNS = [
    r"kimi",            # Moonshot Kimi — always cloud
    r"gemini",          # Google Gemini — always cloud
    r"gpt-[45]",        # OpenAI GPT-4/5 — always cloud
    r"claude",          # Anthropic Claude — always cloud
    r"mistral-large",   # Mistral Large — cloud-only
    r"command-r",       # Cohere Command R — cloud-only
]


def is_cloud_model_via_ollama(
    provider: str, model: str, context_tokens: int = 0,
) -> bool:
    """Detect if an Ollama-served model is actually a cloud model.

    Cloud models benefit from batching even though they're accessed
    via the Ollama API (provider="ollama").

    Detection signals (any one is sufficient):
    1. Model name has `:cloud` suffix
    2. Model name matches a known cloud-only family
    3. Context window > 200K (no consumer-local model has this)
    """
    if provider.lower().strip() != "ollama":
        return False

    model_lower = model.lower().strip()

    # Signal 1: Explicit :cloud suffix
    if ":cloud" in model_lower:
        return True

    # Signal 2: Known cloud-only model families
    for pattern in _OLLAMA_CLOUD_PATTERNS:
        if re.search(pattern, model_lower):
            return True

    # Signal 3: Very large context window
    if context_tokens > 200_000:
        return True

    return False


def detect_profile_from_context(
    context_tokens: int, provider: str, model: str = "",
) -> BatchProfile:
    """Derive batch profile from the model's actual context window size.

    This is more accurate than regex matching because it uses the real
    capability reported by the provider API rather than guessing from
    the model name.

    For Ollama providers, checks whether the model is actually a cloud
    model (kimi, gemini, etc.) before defaulting to OFF.

    Args:
        context_tokens: Model context window in tokens (e.g. 128000, 1000000).
        provider: LLM provider identifier.
        model: Model name (used for cloud-via-Ollama detection).

    Returns:
        The matching BatchProfile.
    """
    provider_lower = provider.lower().strip()

    if provider_lower in _LOCAL_PROVIDERS:
        # Check if this is actually a cloud model served via Ollama
        if not is_cloud_model_via_ollama(provider, model, context_tokens):
            return PROFILE_OFF
        # Cloud model via Ollama — use CLOUD_SMALL profile.
        # Ollama Cloud has a hard 16K output token limit (server-enforced,
        # cannot be raised via num_predict).  Thinking models (kimi) also
        # consume output budget on reasoning preamble, leaving even less
        # for actual JSON.  CLOUD_SMALL uses batch sizes of 5-8 items
        # to fit reliably within this budget.
        logger.info(
            "Cloud model detected via Ollama: %s (context=%d) — using cloud_small profile (16K output limit)",
            model, context_tokens,
        )
        return PROFILE_CLOUD_SMALL

    if context_tokens >= 200_000:     # 200K+ (Gemini 2.5 Pro 1M, Claude 4.5 200K)
        return PROFILE_LARGE
    elif context_tokens >= 100_000:   # 100K–200K (GPT-4.1 1M, Claude 3 200K)
        return PROFILE_STANDARD
    elif context_tokens >= 32_000:    # 32K–100K (GPT-4o 128K, DeepSeek 64K)
        return PROFILE_COMPACT
    else:                             # <32K — too small for safe batching
        return PROFILE_OFF


def get_batch_concurrency(provider: str, node_id: str | None = None, model: str | None = None) -> int:
    """Max concurrent batched API calls for a provider.

    Phase 56B: Queries the scheduler's ``available_batch_workers()`` to
    dynamically divide the concurrency budget across active projects.
    A single project running alone gets the full ``cloud_concurrency``
    budget; multiple projects share it fairly.

    When ``node_id`` is explicitly provided, queries that exact node.
    Otherwise, **auto-discovers** the matching node from the scheduler's
    active slots — Phase 72 fix: the scheduler now resolves by the
    project's *actual* acquired node before falling back to prefix
    matching.

    For local Ollama nodes this still returns 1 to protect VRAM.
    Cloud APIs (OpenAI, Anthropic, Google, Ollama cloud-proxied) use
    the configured ``cloud_concurrency`` budget.
    """
    provider_lower = provider.lower().strip()

    # Cloud models: use Ollama Cloud plan tier to cap concurrency.
    # F-59 root cause (daemon hang from timeout misconfiguration) was
    # resolved on 2026-04-12 — see docs/Phase79_Swarm/07_Rework/
    # SWARM_HANG_INVESTIGATION.md.  Concurrent cloud requests now work
    # end-to-end inside the daemon; the real limit is the plan tier.
    _is_cloud = provider_lower not in _LOCAL_PROVIDERS
    if not _is_cloud and model:
        _is_cloud = is_cloud_model_via_ollama(provider_lower, model or "")
    if _is_cloud:
        tier = _get_plan_tier()
        plan_concurrency = _resolve_plan_tier_concurrency()
        logger.info(
            "Batch concurrency: %d (plan tier=%s, provider=%s, model=%s)",
            plan_concurrency, tier, provider_lower, model,
        )
        return plan_concurrency

    # Read the calling project's ID from the telemetry context so the
    # scheduler can give the priority ⭐ project the full cloud budget.
    calling_project_id: str | None = None
    try:
        from codrag.services.token_telemetry import _telemetry_ctx, _fallback_ctx, _fallback_lock
        ctx = _telemetry_ctx.get()
        if not ctx:
            with _fallback_lock:
                ctx = _fallback_ctx
        if ctx:
            calling_project_id = ctx.get("project_id")
    except ImportError:
        pass

    # Phase 56B: try the scheduler for adaptive concurrency
    try:
        from codrag.services.pipeline.scheduler import pipeline_scheduler

        if node_id is not None:
            workers = pipeline_scheduler.available_batch_workers(
                node_id, project_id=calling_project_id,
            )
            logger.info(
                "Batch concurrency: %d workers (explicit node=%s, project=%s)",
                workers, node_id, calling_project_id,
            )
            return workers

        # Auto-discover: find the best matching node in the scheduler
        workers = pipeline_scheduler.available_batch_workers_for_provider(
            provider_lower, model, project_id=calling_project_id,
        )
        if workers is not None:
            logger.info(
                "Batch concurrency: %d workers (auto-discovered, provider=%s, model=%s, project=%s)",
                workers, provider_lower, model, calling_project_id,
            )
            return workers
    except ImportError:
        pass

    # Fallback: hardcoded defaults (pre-Phase 56B behavior)
    # Phase 112 fix 4: honor the user's Ollama Cloud plan tier even when
    # the scheduler is unreachable.  Previously hardcoded 3 for cloud
    # would exceed the Free tier (=1) limit and under-utilize Max (=10).
    is_cloud_model = provider_lower not in _LOCAL_PROVIDERS
    if not is_cloud_model and model:
        is_cloud_model = is_cloud_model_via_ollama(provider_lower, model)
    if is_cloud_model:
        fallback = _resolve_plan_tier_concurrency()
    else:
        fallback = 1
    logger.info(
        "Batch concurrency: %d workers (FALLBACK — no scheduler, provider=%s, cloud=%s)",
        fallback, provider_lower, is_cloud_model,
    )
    return fallback


def detect_profile(provider: str, model: str) -> BatchProfile:
    """Detect the best batch profile for a given provider + model name.

    Uses regex matching on the model name. Prefer detect_profile_from_context()
    when the model's actual context window is known.

    Args:
        provider: LLM provider identifier ("ollama", "openai", "openai-compatible", "anthropic")
        model: Model name string (e.g. "claude-sonnet-4-5-20250514", "gpt-4.1-mini")

    Returns:
        The matching BatchProfile. Falls back to PROFILE_OFF if no match.
    """
    provider_lower = provider.lower().strip()
    model_lower = model.lower().strip()

    # Check for cloud models via Ollama BEFORE the registry catch-all.
    # When context_tokens is unknown, use CLOUD_SMALL as a safe default.
    # Ollama Cloud has a hard 16K output token limit — see reference above.
    if is_cloud_model_via_ollama(provider, model):
        logger.info(
            "Cloud model detected via Ollama (no context info): %s — using cloud_small profile",
            model,
        )
        return PROFILE_CLOUD_SMALL

    for reg_provider, pattern, profile_name in _MODEL_REGISTRY:
        if reg_provider == provider_lower:
            if re.search(pattern, model_lower):
                profile = PROFILES[profile_name]
                logger.info(
                    "Batch profile for %s/%s: %s (%s)",
                    provider, model, profile.name.value, profile.output_class,
                )
                return profile

    logger.info("No batch profile match for %s/%s — defaulting to OFF", provider, model)
    return PROFILE_OFF


def resolve_profile(
    provider: str,
    model: str,
    override: Optional[str] = None,
    context_tokens: Optional[int] = None,
) -> BatchProfile:
    """Resolve the batch profile, respecting user override.

    Resolution order:
    1. Explicit user override ("large", "standard", "compact", "off")
    2. Context-window-based detection (if context_tokens is known)
    3. Regex-based model name detection (fallback)

    Args:
        provider: LLM provider identifier
        model: Model name string
        override: User-selected profile name ("auto", "large", "standard",
                  "compact", "off"), or None for auto-detect.
        context_tokens: Model context window in tokens, if known from the
                        provider API. Enables accurate auto-detection.

    Returns:
        The resolved BatchProfile.
    """
    if override and override.lower() != "auto":
        try:
            profile_name = BatchProfileName(override.lower())
            return PROFILES[profile_name]
        except (ValueError, KeyError):
            logger.warning("Unknown batch profile override '%s' — falling back to auto", override)

    # Phase 112: honor the "Enforce Cloud Token Safety" toggle.
    # When OFF (power users on paid plans), promote cloud models out of
    # CLOUD_SMALL — except Kimi, where the thinking-preamble constraint
    # (not the 16K cap) is binding.  See SWARM_UI_PLAN_v2.md §6.1.
    try:
        from codrag.server import get_advanced_llm_settings
        enforce_safety = get_advanced_llm_settings().get(
            "enforce_cloud_token_safety", True,
        )
    except Exception:
        enforce_safety = True

    if not enforce_safety and is_cloud_model_via_ollama(provider, model):
        model_lower = (model or "").lower()
        if "kimi" in model_lower:
            return PROFILE_CLOUD_SMALL  # thinking-preamble eats output budget
        if "gemini" in model_lower:
            return PROFILE_LARGE
        return PROFILE_STANDARD

    # Prefer context-window-based detection when available
    if context_tokens and context_tokens > 0:
        profile = detect_profile_from_context(context_tokens, provider, model)
        logger.info(
            "Batch profile for %s/%s: %s (via %dK context window)",
            provider, model, profile.name.value, context_tokens // 1000,
        )
        return profile

    return detect_profile(provider, model)
