"""Swarm model registry — finite list of validated swarm-capable models.

Loads swarm_models.json and exposes get_swarm_tier() for the pipeline
to check if the current model supports agent swarm orchestration.

The list is intentionally small and curated. Models not in the list
default to UNSUITABLE and use standard concurrent batching.
"""

import enum
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_REGISTRY_PATH = _DATA_DIR / "swarm_models.json"


class SwarmTier(str, enum.Enum):
    """Swarm capability tier for a model."""
    COORDINATOR = "coordinator"
    BOTH = "both"
    WORKER = "worker"
    UNSUITABLE = "unsuitable"

    @property
    def can_coordinate(self) -> bool:
        """Can this model act as a swarm coordinator?"""
        return self in (SwarmTier.COORDINATOR, SwarmTier.BOTH)


def _load_registry() -> Dict[str, Any]:
    """Load the swarm model registry from JSON."""
    try:
        with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load swarm registry from %s: %s", _REGISTRY_PATH, exc)
        return {"models": [], "default_tier": "unsuitable", "min_groups_threshold": 3}


@lru_cache(maxsize=1)
def _cached_registry() -> Dict[str, Any]:
    return _load_registry()


def get_swarm_tier(provider: str, model: str) -> SwarmTier:
    """Look up swarm tier for a model. Returns UNSUITABLE if not in list.

    Matching: provider must be in the entry's providers list, and the
    model name must contain the entry's 'contains' string (case-insensitive).
    First match wins.
    """
    registry = _cached_registry()
    provider_lower = provider.lower().strip()
    model_lower = model.lower().strip()

    for entry in registry.get("models", []):
        providers: List[str] = entry.get("providers", [])
        contains: str = entry.get("contains", "")

        if provider_lower in [p.lower() for p in providers] and contains.lower() in model_lower:
            tier_str = entry.get("tier", "unsuitable")
            try:
                return SwarmTier(tier_str)
            except ValueError:
                logger.warning("Unknown swarm tier '%s' for model %s", tier_str, entry.get("id"))
                return SwarmTier.UNSUITABLE

    return SwarmTier(registry.get("default_tier", "unsuitable"))


def get_min_groups_threshold() -> int:
    """Minimum number of groups required to activate swarm."""
    registry = _cached_registry()
    return int(registry.get("min_groups_threshold", 3))
