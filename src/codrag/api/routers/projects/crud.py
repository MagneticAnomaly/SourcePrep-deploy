"""
Project CRUD endpoints — list, add, get, update, delete, path_weights, included_paths.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from codrag.api.envelope import ApiException, ok
from codrag.core.feature_gate import (
    License, get_license, get_feature_limit, FeatureGateError, Tier
)
from codrag.core.project_registry import (
    ProjectAlreadyExists, ProjectNotFound, Project, project_index_dir,
)
from codrag.core.repo_policy import (
    load_repo_policy, policy_path_for_index, write_repo_policy,
    _normalize_path_weights,
)
from codrag.core.repo_profile import scan_for_presets, STACK_PRESETS

from .helpers import _srv, _get_project_globs
from .models import (
    AddProjectRequest,
    UpdateProjectRequest,
    PathWeightsRequest,
    IncludedPathsRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


@router.get("/projects")
def list_projects() -> Dict[str, Any]:
    reg = _srv()._get_registry()
    projects: List[Dict[str, Any]] = []
    
    # We need to use project_to_dict to ensure activity_status is injected correctly
    for p in reg.list_projects():
        projects.append(_srv()._project_to_dict(p))
        
    return ok({"projects": projects, "total": len(projects)})


@router.post("/projects")
def add_project(req: AddProjectRequest) -> Dict[str, Any]:
    if req.mode not in ("standalone", "embedded", "custom"):
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message=f"Invalid mode: {req.mode}")

    # Check project count limit for current tier
    from codrag.services.project_helpers import get_project_activity_status
    reg = _srv()._get_registry()
    active_count = sum(1 for p in reg.list_projects() if get_project_activity_status(p.id) == "active")
    max_projects = get_feature_limit("projects_max")
    
    if active_count >= max_projects:
        lic = get_license()
        raise FeatureGateError(
            feature="projects_max",
            current_tier=License._display_tier(lic.tier),
            required_tier="pro",
        )

    p = Path(str(req.path)).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise ApiException(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"Path does not exist: {p}",
        )

    # Validate index_path for custom mode
    custom_index_path: Optional[str] = None
    if req.mode == "custom":
        if not req.index_path:
            raise ApiException(
                status_code=400,
                code="VALIDATION_ERROR",
                message="index_path is required for custom mode",
            )
        try:
            ip = Path(req.index_path).expanduser().resolve()
            # We don't necessarily require it to exist yet (we can create it), 
            # but maybe we should ensure parent exists or it's a valid path.
            # For now just resolving it is enough check for basic validity.
            custom_index_path = str(ip)
        except Exception as e:
            raise ApiException(
                status_code=400,
                code="VALIDATION_ERROR",
                message=f"Invalid index_path: {e}",
            )

    # Determine defaults based on tier
    lic = get_license()
    # Auto-rebuild is enabled by default for Monthly tier and above
    auto_rebuild_default = lic.tier >= 1  # Tier.MONTHLY = 1

    reg = _srv()._get_registry()
    default_cfg: Dict[str, Any] = {
        "include_globs": list(_srv()._DEFAULT_UI_CONFIG.get("include_globs") or []),
        "exclude_globs": list(_srv()._DEFAULT_UI_CONFIG.get("exclude_globs") or []),
        "max_file_bytes": int(_srv()._DEFAULT_UI_CONFIG.get("max_file_bytes") or 500_000),
        "hard_limit_bytes": int(_srv()._DEFAULT_UI_CONFIG.get("hard_limit_bytes") or 100_000_000),
        "trace": {"enabled": True},  # Cross-reference on by default for all tiers
        "auto_rebuild": {
            "enabled": auto_rebuild_default,
            "debounce_ms": 5000,
        },
    }
    
    if req.mode == "embedded":
        if "**/.codrag/**" not in default_cfg["exclude_globs"]:
            default_cfg["exclude_globs"].append("**/.codrag/**")
    
    # Store custom index path in config if applicable
    if custom_index_path:
        default_cfg["index_path"] = custom_index_path

    if (_srv()._DEFAULT_UI_CONFIG.get("auto_rebuild") or {}).get("debounce_ms") is not None:
        default_cfg["auto_rebuild"]["debounce_ms"] = int(
            (_srv()._DEFAULT_UI_CONFIG.get("auto_rebuild") or {}).get("debounce_ms")
        )

    # Auto-detect stack presets to populate include_globs
    try:
        detected = scan_for_presets(p)
        if detected:
            logger.info(f"Auto-detected stack presets for {p.name}: {detected}")
            detected_globs = []
            for preset in detected:
                detected_globs.extend(STACK_PRESETS.get(preset, []))
            
            # Merge unique into include_globs
            current_globs = set(default_cfg["include_globs"])
            for g in detected_globs:
                if g not in current_globs:
                    default_cfg["include_globs"].append(g)
                    current_globs.add(g)
    except Exception as e:
        logger.warning(f"Failed to auto-detect stack presets: {e}")

    # Detect existing index directory — reuse it, never overwrite
    existing_index = False
    existing_index_files: List[str] = []
    if req.mode == "embedded":
        codrag_dir = p / ".codrag"
        if codrag_dir.is_dir():
            existing_index_files = [f.name for f in codrag_dir.iterdir() if not f.name.startswith(".")]
            existing_index = len(existing_index_files) > 0
            logger.info(
                "Reusing existing .codrag directory at %s (%d files: %s)",
                codrag_dir, len(existing_index_files),
                ", ".join(existing_index_files[:10]),
            )
    elif req.mode == "custom" and custom_index_path:
        cp = Path(custom_index_path)
        if cp.is_dir() and any(cp.iterdir()):
            existing_index = True
            logger.info("Reusing existing custom index directory at %s", cp)

    try:
        proj = reg.add_project(path=str(p), name=req.name, mode=req.mode, config=default_cfg)
    except ProjectAlreadyExists:
        raise ApiException(
            status_code=409,
            code="PROJECT_ALREADY_EXISTS",
            message=f"A project already exists at '{p}'",
            hint="Use a different path or remove the existing project first.",
        )

    result: Dict[str, Any] = {"project": _srv()._project_to_dict(proj)}
    if existing_index:
        result["existing_index"] = {
            "reused": True,
            "files": existing_index_files[:20] if existing_index_files else [],
        }

    warning_msg = None
    from codrag.services.config_manager import load_ui_config
    ui_cfg = load_ui_config(_srv()._config)
    max_active = ui_cfg.get("max_active_projects", "infinite")
    if max_active != "infinite":
        max_active_int = int(max_active)
        active_count = 0
        for p_reg in reg.list_projects():
            pcfg = p_reg.config if isinstance(p_reg.config, dict) else {}
            if "active" in pcfg and pcfg["active"] is True:
                active_count += 1
        
        if active_count > max_active_int:
            lic = get_license()
            if lic.tier not in (Tier.TEAM, Tier.ENTERPRISE):
                warning_msg = f"It is recommended to use {max_active_int} or fewer active projects because it can be performance invasive."

    if warning_msg:
        result["warning"] = warning_msg

    return ok(result)


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    return ok({"project": _srv()._project_to_dict(proj)})


@router.put("/projects/{project_id}")
def update_project(project_id: str, req: UpdateProjectRequest) -> Dict[str, Any]:
    reg = _srv()._get_registry()

    warning_msg = None

    # Detect activity toggle: compare old config.active with new config.active
    old_proj = _srv()._require_project(project_id)
    old_active = (old_proj.config or {}).get("active", True)
    new_active = old_active  # default: unchanged
    if req.config and "active" in req.config:
        new_active = bool(req.config["active"])

    # Enforce max_active_projects
    if not old_active and new_active:
        from codrag.services.config_manager import load_ui_config
        ui_cfg = load_ui_config(_srv()._config)
        max_active = ui_cfg.get("max_active_projects", "infinite")
        
        if max_active != "infinite":
            max_active_int = int(max_active)
            active_count = 0
            for p in reg.list_projects():
                if p.id == project_id:
                    continue
                # Only count projects explicitly toggled ON by the user.
                # Projects without the "active" field in config default to True
                # for backward compat but should NOT count against the limit.
                pcfg = p.config if isinstance(p.config, dict) else {}
                if "active" in pcfg and pcfg["active"] is True:
                    active_count += 1
            
            if active_count >= max_active_int:
                lic = get_license()
                if lic.tier in (Tier.TEAM, Tier.ENTERPRISE):
                    raise ApiException(
                        status_code=400,
                        code="MAX_ACTIVE_PROJECTS_REACHED",
                        message=f"You already have {max_active_int} active project(s). This limit is enforced for performance.",
                        hint="Deactivate another project first.",
                    )
                else:
                    warning_msg = f"It is recommended to use {max_active_int} or fewer active projects because it can be performance invasive."

    # F-63/F-69/F-86: Merge incoming config with existing config atomically.
    #
    # The dashboard fires PUT /projects/{id} frequently with a partial
    # snapshot of its cached projectConfig (auto_config changes, active
    # toggle, etc.). Without an atomic merge, two problems happen:
    #   1. Partial updates would wipe fields the client didn't send.
    #   2. The client's cached `trace.ignore_patterns` is stale relative
    #      to whatever POST /trace/ignore (the dedicated endpoint that
    #      owns that field) just wrote — so accepting it here would
    #      silently revert the user's just-added exclude.
    #
    # Strategy: route the whole merge through ProjectRegistry.mutate_config
    # so the read+write happens inside a single SQLite transaction with
    # BEGIN IMMEDIATE. trace.ignore_patterns is treated as authoritative
    # in the DB — incoming values for that key are dropped on the floor.
    # Any other trace fields (enabled, paused) are deep-merged.
    incoming_config = req.config
    incoming_name = req.name

    def _merge(old_cfg: Dict[str, Any]) -> Dict[str, Any]:
        if incoming_config is None:
            return old_cfg
        old_dict = old_cfg if isinstance(old_cfg, dict) else {}
        merged = {**old_dict, **incoming_config}
        if "trace" in incoming_config:
            old_trace = old_dict.get("trace") or {}
            new_trace = dict(incoming_config.get("trace") or {})
            # ignore_patterns is owned by POST /trace/ignore — never let a
            # generic PUT clobber it with a stale snapshot.
            new_trace.pop("ignore_patterns", None)
            merged["trace"] = {**old_trace, **new_trace}
        return merged

    try:
        if incoming_config is not None:
            updated = reg.mutate_config(project_id, _merge, touch=req.touch)
            if incoming_name is not None:
                updated = reg.update_project(project_id, name=incoming_name, touch=req.touch)
        else:
            updated = reg.update_project(
                project_id,
                name=incoming_name,
                touch=req.touch,
            )
    except ProjectNotFound:
        raise ApiException(
            status_code=404,
            code="PROJECT_NOT_FOUND",
            message=f"Project with ID '{project_id}' not found",
            hint="Add the project first or select an existing project.",
        )

    if req.path_weights is not None:
        updated = _persist_path_weights(updated, req.path_weights)

    # ── Invalidate cached indexes when config changes ─────────────
    if req.config:
        try:
            srv = _srv()
            bm = srv.build_manager
            bm.project_indexes.pop(project_id, None)
            bm.project_knowledge_indexes.pop(project_id, None)
            bm._layered_indexes.pop(project_id, None)
        except Exception:
            pass

    # ── React to activity toggle ──────────────────────────────────
    if old_active and not new_active:
        # DEACTIVATED: stop watcher + cancel pipelines
        _deactivate_project(project_id)
    elif not old_active and new_active:
        # ACTIVATED: start watcher if auto mode is configured
        _activate_project(updated)

        # Write the active project signal so MCP instances re-route here
        try:
            from codrag.core.project_registry import write_active_project_signal
            write_active_project_signal(project_id)
            logger.info(f"Wrote active project signal for {project_id}")
        except Exception as e:
            logger.warning(f"Failed to write active project signal: {e}")

    # ── React to priority change ───────────────────────────────────
    if req.config and ("priority_level" in req.config or "is_starred" in req.config):
        old_cfg = old_proj.config or {}
        old_level = old_cfg.get("priority_level", "boost" if old_cfg.get("is_starred") else "none")
        new_level = (req.config.get("priority_level")
                     or ("boost" if req.config.get("is_starred") else None)
                     or old_level)
        if new_level != old_level:
            try:
                from codrag.services.pipeline.scheduler import pipeline_scheduler
                pipeline_scheduler.set_priority(project_id, new_level)
                logger.info("Priority for %s changed: %s → %s", project_id, old_level, new_level)
            except Exception as exc:
                logger.warning("Failed to update scheduler priority: %s", exc)

    response_data = {"project": _srv()._project_to_dict(updated)}
    if warning_msg:
        response_data["warning"] = warning_msg
    return ok(response_data)


@router.put("/projects/{project_id}/path_weights")
def update_path_weights(project_id: str, req: PathWeightsRequest) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    updated = _persist_path_weights(proj, req.path_weights)
    return ok({"project": _srv()._project_to_dict(updated), "path_weights": updated.config.get("path_weights", {})})


@router.get("/projects/{project_id}/path_weights")
def get_path_weights(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    pw = proj.config.get("path_weights", {})
    return ok({"path_weights": pw})


def _deactivate_project(project_id: str) -> None:
    """Stop watcher and cancel all pipelines for a project being deactivated."""
    # Stop file watcher
    watcher = _srv()._project_watchers.pop(project_id, None)
    if watcher is not None:
        watcher.stop()
        logger.info("Stopped watcher for deactivated project %s", project_id)

    # Cancel both pipeline groups
    try:
        from codrag.services.pipeline_orchestrator import pipeline_orchestrator
        cancelled_fast = pipeline_orchestrator.cancel_fast_sync(project_id)
        cancelled_deep = pipeline_orchestrator.cancel_deep_enrichment(project_id)
        if cancelled_fast or cancelled_deep:
            logger.info(
                "Cancelled pipelines for deactivated project %s (fast=%s, deep=%s)",
                project_id, cancelled_fast, cancelled_deep,
            )
    except Exception as exc:
        logger.warning("Failed to cancel pipelines for %s: %s", project_id, exc)

    # Phase 96 follow-up: Clear runtime scheduler priority for the project
    # being deactivated. The persisted priority_level in the project config
    # is preserved — it will reapply when the project is reactivated. But
    # the runtime _priority_projects entry must be removed so the project's
    # exclusive/boost flag doesn't continue affecting other projects'
    # acquisition behavior while it's inactive.
    try:
        from codrag.services.pipeline.scheduler import pipeline_scheduler
        if project_id in pipeline_scheduler.priority_projects:
            pipeline_scheduler.set_priority(project_id, "none")
            logger.info(
                "Cleared runtime priority for deactivated project %s "
                "(persisted priority_level remains in project config)",
                project_id,
            )
    except Exception as exc:
        logger.warning(
            "Failed to clear scheduler priority for %s: %s", project_id, exc,
        )


def _activate_project(proj: Project) -> None:
    """Start watcher and trigger auto-sync for a project being activated."""
    cfg = proj.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    trace_enabled = bool((trace_cfg or {}).get("enabled", False))
    fast_sync_auto = bool(cfg.get("fast_sync_auto", False))

    # Phase 96 follow-up: Re-apply persisted priority level when the
    # project is activated. _deactivate_project clears the runtime
    # priority but preserves priority_level in the project config so
    # this restore is symmetric.
    try:
        from codrag.services.pipeline.scheduler import pipeline_scheduler
        priority_level = cfg.get("priority_level")
        if not priority_level and cfg.get("is_starred"):
            priority_level = "boost"
        if priority_level and priority_level != "none":
            pipeline_scheduler.set_priority(proj.id, priority_level)
            logger.info(
                "Restored runtime priority %s for activated project %s",
                priority_level, proj.id,
            )
    except Exception as exc:
        logger.warning(
            "Failed to restore scheduler priority for %s: %s", proj.id, exc,
        )

    # Start watcher if fast_sync is set to auto
    if fast_sync_auto:
        try:
            start_project_watch(proj.id)
            logger.info("Started watcher for activated project %s", proj.id)
        except Exception as exc:
            logger.warning("Failed to start watcher for %s: %s", proj.id, exc)

    # Trigger fast sync if trace is enabled and auto mode
    if trace_enabled and fast_sync_auto:
        try:
            from codrag.services.pipeline_orchestrator import pipeline_orchestrator
            pipeline_orchestrator.run_fast_sync(proj.id)
            logger.info("Triggered fast sync for activated project %s", proj.id)
        except Exception as exc:
            logger.warning("Failed to trigger fast sync for %s: %s", proj.id, exc)


def _persist_path_weights(proj: Project, raw_weights: Dict[str, float]) -> Project:
    """Normalize and persist path_weights to project config AND repo_policy.json."""
    normalized = _normalize_path_weights(raw_weights)

    # Update project config in SQLite
    reg = _srv()._get_registry()
    new_config = dict(proj.config)
    new_config["path_weights"] = normalized
    updated = reg.update_project(proj.id, config=new_config)

    # Also persist to repo_policy.json on disk so next build picks it up
    idx_dir = project_index_dir(proj)
    pp = policy_path_for_index(idx_dir)
    policy = load_repo_policy(pp)
    if policy is not None:
        policy["path_weights"] = normalized
        write_repo_policy(pp, policy)

    # Hot-update the in-memory manifest so searches use new weights immediately
    idx = _srv()._project_indexes.get(proj.id)
    if idx is not None and idx._manifest:
        cfg = idx._manifest.get("config")
        if isinstance(cfg, dict):
            cfg["path_weights"] = normalized

    return updated


# ── Included Paths (Knowledge Scope) ─────────────────────────

@router.put("/projects/{project_id}/included_paths")
def update_included_paths(project_id: str, req: IncludedPathsRequest) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    updated = _persist_included_paths(proj, req.included_paths)
    return ok({
        "project": _srv()._project_to_dict(updated),
        "included_paths": updated.config.get("included_paths", []),
    })


@router.get("/projects/{project_id}/included_paths")
def get_included_paths(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    paths = proj.config.get("included_paths", [])
    return ok({"included_paths": paths})


def _persist_included_paths(proj, paths: List[str]):
    """Persist included_paths to project config in SQLite.

    Uses mutate_config for atomic read-modify-write so concurrent writers
    (e.g. POST /trace/ignore racing on an exclude-click that also triggers
    a mutual-exclusion un-include) cannot clobber each other's fields.

    If a pipeline is running, triggers a hot scope reload so the new
    include/exclude scope takes effect immediately.
    """
    # Deduplicate and sort for deterministic storage
    normalized = sorted(set(str(p) for p in paths if p))

    reg = _srv()._get_registry()
    updated = reg.mutate_config(
        proj.id,
        lambda cfg: {**cfg, "included_paths": normalized},
    )

    # P48-F34: Hot scope reload if pipeline is running
    try:
        from codrag.services.pipeline_orchestrator import pipeline_orchestrator
        pipeline_orchestrator.hot_scope_reload(proj.id)
    except Exception:
        pass  # Non-fatal — patterns saved, will take effect on next run

    return updated


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, purge: bool = False) -> Dict[str, Any]:
    reg = _srv()._get_registry()
    
    # Enforce purge=True for Free tier
    lic = get_license()
    if lic.tier < Tier.MONTHLY:
        purge = True
        
    try:
        reg.remove_project(project_id, purge=bool(purge))
    except ProjectNotFound:
        raise ApiException(
            status_code=404,
            code="PROJECT_NOT_FOUND",
            message=f"Project with ID '{project_id}' not found",
            hint="Add the project first or select an existing project.",
        )

    _srv()._project_indexes.pop(project_id, None)
    _srv()._project_trace_indexes.pop(project_id, None)
    with _srv()._project_build_lock:
        _srv()._project_build_threads.pop(project_id, None)
        _srv()._project_last_build_result.pop(project_id, None)
        _srv()._project_last_build_error.pop(project_id, None)
    with _srv()._project_trace_build_lock:
        _srv()._project_trace_build_threads.pop(project_id, None)

    return ok({"removed": True, "purged": bool(purge)})


@router.post("/projects/{project_id}/archive")
def archive_project(project_id: str) -> Dict[str, Any]:
    """Archive a project (Free tier explicit lock)"""
    proj = _srv()._require_project(project_id)
    reg = _srv()._get_registry()
    
    new_config = dict(proj.config)
    new_config["archived"] = True
    new_config["active"] = False
    
    updated = reg.update_project(proj.id, config=new_config)
    _deactivate_project(project_id)
    
    return ok({"project": _srv()._project_to_dict(updated)})


@router.post("/projects/{project_id}/unarchive")
def unarchive_project(project_id: str) -> Dict[str, Any]:
    """Unarchive a project (requires Pro tier or available Free slots)"""
    proj = _srv()._require_project(project_id)
    reg = _srv()._get_registry()
    
    lic = get_license()
    
    # On Free tier, check if we have room
    if lic.tier < Tier.MONTHLY:
        from codrag.services.project_helpers import get_project_activity_status
        active_count = sum(1 for p in reg.list_projects() if get_project_activity_status(p.id) == "active")
        max_projects = get_feature_limit("projects_max")
        
        if active_count >= max_projects:
            raise ApiException(
                status_code=403,
                code="PROJECTS_MAX_REACHED",
                message=f"You have reached the maximum of {max_projects} active projects.",
                hint="Upgrade to Pro to unlock unlimited active projects.",
            )
            
    new_config = dict(proj.config)
    new_config["archived"] = False
    new_config["active"] = True
    
    updated = reg.update_project(proj.id, config=new_config)
    _activate_project(updated)
    
    return ok({"project": _srv()._project_to_dict(updated)})


@router.post("/projects/validate-pointers")
def validate_pointers() -> Dict[str, Any]:
    """Validate and heal .codrag/project.json pointers for all projects.

    Checks every registered project and ensures its pointer file
    exists with the correct project ID. Heals mismatches automatically.

    Returns:
        - healed: projects whose pointers were created/fixed
        - stale: projects whose paths no longer exist on disk
        - ok: projects that were already correct
    """
    reg = _srv()._get_registry()
    report = reg.validate_and_heal_pointers()
    return ok(report)

