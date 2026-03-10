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
    LARGE = "large"        # 64K output models (Claude 4.5, Gemini 2.5 Pro)
    STANDARD = "standard"  # 32K output models (GPT-4.1, Claude 3)
    COMPACT = "compact"    # 8K–16K output models (DeepSeek, GPT-4o)
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

PROFILE_LARGE = BatchProfile(
    name=BatchProfileName.LARGE,
    output_class="64K (Claude Sonnet 4.5+, Gemini 2.5 Pro)",
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
    output_class="32K (GPT-4.1, GPT-5, Claude 3)",
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
    output_class="8K–16K (DeepSeek, GPT-4o, Gemini Flash, Haiku 3.5)",
    sizes={
        BatchStage.CATALOGUE_SYMBOL: 20,
        BatchStage.CATALOGUE_FILE: 20,
        BatchStage.INFERRED_EDGES: 15,
        BatchStage.EPISTEMIC_CODE: 10,
        BatchStage.EPISTEMIC_DOC: 5,
        BatchStage.CLUSTERING: 10,
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


def detect_profile(provider: str, model: str) -> BatchProfile:
    """Detect the best batch profile for a given provider + model name.

    Args:
        provider: LLM provider identifier ("ollama", "openai", "openai-compatible", "anthropic")
        model: Model name string (e.g. "claude-sonnet-4-5-20250514", "gpt-4.1-mini")

    Returns:
        The matching BatchProfile. Falls back to PROFILE_OFF if no match.
    """
    provider_lower = provider.lower().strip()
    model_lower = model.lower().strip()

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
) -> BatchProfile:
    """Resolve the batch profile, respecting user override.

    Args:
        provider: LLM provider identifier
        model: Model name string
        override: User-selected profile name ("auto", "large", "standard",
                  "compact", "off"), or None for auto-detect.

    Returns:
        The resolved BatchProfile.
    """
    if override and override.lower() != "auto":
        try:
            profile_name = BatchProfileName(override.lower())
            return PROFILES[profile_name]
        except (ValueError, KeyError):
            logger.warning("Unknown batch profile override '%s' — falling back to auto", override)

    return detect_profile(provider, model)
