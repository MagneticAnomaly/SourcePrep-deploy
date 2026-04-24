"""Per-stage provenance — Phase 117 Scope B.

Joins each stage's manifest model against the current LLM task-assignment
config to classify a stage as match / drift / recovered_stub / recovered_soft
/ missing. Consumed by /pipeline/status for UI rendering.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from prep.services.pipeline._model_resolution import resolve_model_for_stage

logger = logging.getLogger(__name__)


_STAGE_MANIFEST_FILE = {
    "trace": "trace_manifest.json",
    "inferred_edges": "trace_inferred_manifest.json",
    "augmentation": "trace_augment_manifest.json",
    "validation": "validation_manifest.json",
    "knowledge": "knowledge_manifest.json",
    "enrichment": "trace_epistemic_manifest.json",
    "group_reasoning": "group_reasoning_manifest.json",
    "clustering": "trace_modules_manifest.json",
    "deepening": "deepening_manifest.json",
    "deep_knowledge": "deep_knowledge_manifest.json",
    "atlas": "atlas_manifest.json",
    "rules": "rules_manifest.json",
    "concepts": "concepts_manifest.json",
    "audit": "audit_manifest.json",
    "antibodies": "antibodies_manifest.json",
}

_STAGE_TO_REBUILD_SCOPE = {
    # Sync (1-5)
    "trace": "sync",
    "inferred_edges": "sync",
    "augmentation": "sync",
    "validation": "sync",
    "knowledge": "sync",
    # Enrichment (6-10)
    "enrichment": "enrichment",
    "group_reasoning": "enrichment",
    "clustering": "enrichment",
    "deepening": "enrichment",
    "deep_knowledge": "enrichment",
    # Finalize (11-15) — no scope; per-stage recover
    "atlas": None,
    "rules": None,
    "concepts": None,
    "audit": None,
    "antibodies": None,
}


def _resolve_idx_dir(project_id: str) -> Path | None:
    try:
        from prep.core.project_registry import project_index_dir
        from prep.services.project_helpers import require_project
        return Path(project_index_dir(require_project(project_id)))
    except Exception:
        logger.debug("could not resolve idx_dir for %s", project_id, exc_info=True)
        return None


def _read_manifest(idx_dir: Path, stage_id: str) -> dict | None:
    filename = _STAGE_MANIFEST_FILE.get(stage_id)
    if not filename:
        return None
    path = idx_dir / filename
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _models_equal(a: tuple[str, str] | None, b: tuple[str, str] | None) -> bool:
    if a is None or b is None:
        return False
    return a[0].lower() == b[0].lower() and a[1] == b[1]


def _golden_model_for_stage(idx_dir: Path, stage_id: str) -> tuple[str, str] | None:
    meta = idx_dir / ".checkpoints" / "_golden" / "_meta.json"
    if not meta.is_file():
        return None
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        return None
    entry = (data.get("stage_models") or {}).get(stage_id)
    if not entry:
        return None
    provider = (entry.get("provider") or "").lower()
    model = entry.get("model_name") or ""
    if not provider or not model:
        return None
    return (provider, model)


def compute_stage_provenance(project_id: str, stage_id: str) -> dict[str, Any]:
    """Classify a stage's provenance state.

    Returns a dict with keys: state, manifest_model, current_config_model,
    chip_text, rebuild_scope.
    """
    idx_dir = _resolve_idx_dir(project_id)
    current_tuple = resolve_model_for_stage(project_id, stage_id)
    current_model_dict = (
        {"provider": current_tuple[0], "model_name": current_tuple[1]}
        if current_tuple else None
    )
    rebuild_scope = _STAGE_TO_REBUILD_SCOPE.get(stage_id)

    if idx_dir is None:
        return {
            "state": "missing",
            "manifest_model": None,
            "current_config_model": current_model_dict,
            "chip_text": None,
            "rebuild_scope": rebuild_scope,
        }

    manifest = _read_manifest(idx_dir, stage_id)

    # Missing
    if manifest is None:
        return {
            "state": "missing",
            "manifest_model": None,
            "current_config_model": current_model_dict,
            "chip_text": None,
            "rebuild_scope": rebuild_scope,
        }

    # Recovered stub path
    if manifest.get("restored") is True:
        golden = _golden_model_for_stage(idx_dir, stage_id)
        if _models_equal(golden, current_tuple):
            return {
                "state": "recovered_soft",
                "manifest_model": None,
                "current_config_model": current_model_dict,
                "chip_text": "Self-healed \u00b7 model likely current",
                "rebuild_scope": rebuild_scope,
            }
        return {
            "state": "recovered_stub",
            "manifest_model": None,
            "current_config_model": current_model_dict,
            "chip_text": "Self-healed \u00b7 provenance unknown \u00b7 Rebuild",
            "rebuild_scope": rebuild_scope,
        }

    # Genuine manifest path
    manifest_model = manifest.get("model") or {}
    manifest_tuple: tuple[str, str] | None = None
    if manifest_model:
        provider = (manifest_model.get("provider") or "").lower()
        model_name = manifest_model.get("model_name") or ""
        if provider and model_name:
            manifest_tuple = (provider, model_name)

    manifest_model_dict = (
        {"provider": manifest_tuple[0], "model_name": manifest_tuple[1]}
        if manifest_tuple else None
    )

    # Non-LLM stages (no manifest model AND no current-config model) → match, no chip
    if manifest_tuple is None and current_tuple is None:
        return {
            "state": "match",
            "manifest_model": None,
            "current_config_model": None,
            "chip_text": None,
            "rebuild_scope": None,
        }

    if _models_equal(manifest_tuple, current_tuple):
        return {
            "state": "match",
            "manifest_model": manifest_model_dict,
            "current_config_model": current_model_dict,
            "chip_text": None,
            "rebuild_scope": None,
        }

    chip = (
        f"Built with {manifest_tuple[1]} \u2192 now {current_tuple[1]} \u00b7 Rebuild"
        if manifest_tuple and current_tuple
        else "Model changed \u00b7 Rebuild"
    )
    return {
        "state": "drift",
        "manifest_model": manifest_model_dict,
        "current_config_model": current_model_dict,
        "chip_text": chip,
        "rebuild_scope": rebuild_scope,
    }
