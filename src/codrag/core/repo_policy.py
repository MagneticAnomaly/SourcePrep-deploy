from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .repo_profile import DEFAULT_EXCLUDE_DIR_NAMES, DEFAULT_ROLE_WEIGHTS, profile_repo

DEFAULT_POLICY_FILENAME = "repo_policy.json"

# Default primer configuration
DEFAULT_PRIMER_CONFIG = {
    "enabled": True,
    "filenames": ["AGENTS.md", "CODRAG_PRIMER.md", "PROJECT_PRIMER.md"],
    "score_boost": 0.25,  # Added to similarity score for primer chunks
    "always_include": False,  # If True, primer chunks always appear in context
    "max_primer_chars": 2000,  # Max chars to include from primer when always_include=True
}


def policy_path_for_index(index_dir: Path) -> Path:
    return Path(index_dir) / DEFAULT_POLICY_FILENAME


def load_repo_policy(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not path.exists():
            return None
        with open(path, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def write_repo_policy(path: Path, policy: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(policy, f, indent=2)


def _normalize_globs(v: Any) -> List[str]:
    if not isinstance(v, list):
        return []
    out: List[str] = []
    for x in v:
        if isinstance(x, str) and x.strip():
            out.append(x)
    return out


def _normalize_role_weights(v: Any) -> Dict[str, float]:
    if not isinstance(v, dict):
        return dict(DEFAULT_ROLE_WEIGHTS)

    out: Dict[str, float] = {}
    for k, val in v.items():
        if not isinstance(k, str) or not k:
            continue
        try:
            out[k] = float(val)
        except (TypeError, ValueError):
            continue

    return out or dict(DEFAULT_ROLE_WEIGHTS)


def _normalize_path_weights(v: Any) -> Dict[str, float]:
    """Normalize user-defined path weight overrides.

    Keys are relative paths (folders or files), values are floats 0.0–2.0.
    Folder weights propagate to children at search time; children can override.
    """
    if not isinstance(v, dict):
        return {}
    out: Dict[str, float] = {}
    for k, val in v.items():
        if not isinstance(k, str) or not k.strip():
            continue
        try:
            w = float(val)
        except (TypeError, ValueError):
            continue
        out[k.strip().strip("/")] = max(0.0, min(2.0, round(w, 2)))
    return out


def _normalize_primer_config(v: Any) -> Dict[str, Any]:
    """Normalize primer configuration, filling in defaults for missing fields."""
    if not isinstance(v, dict):
        return dict(DEFAULT_PRIMER_CONFIG)
    
    out = dict(DEFAULT_PRIMER_CONFIG)  # Start with defaults
    
    if "enabled" in v:
        out["enabled"] = bool(v["enabled"])
    
    if "filenames" in v and isinstance(v["filenames"], list):
        out["filenames"] = [str(f) for f in v["filenames"] if isinstance(f, str) and f.strip()]
    
    if "score_boost" in v:
        try:
            out["score_boost"] = max(0.0, min(1.0, float(v["score_boost"])))
        except (TypeError, ValueError):
            pass
    
    if "always_include" in v:
        out["always_include"] = bool(v["always_include"])
    
    if "max_primer_chars" in v:
        try:
            out["max_primer_chars"] = max(100, int(v["max_primer_chars"]))
        except (TypeError, ValueError):
            pass
    
    return out


def policy_from_profile(profile: Dict[str, Any], repo_root: Path) -> Dict[str, Any]:
    rec = profile.get("recommended") or {}

    return {
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root.resolve()),
        "include_globs": _normalize_globs(rec.get("include_globs")),
        "exclude_globs": _normalize_globs(rec.get("exclude_globs")),
        "role_weights": _normalize_role_weights(rec.get("role_weights")),
        "path_weights": _normalize_path_weights(rec.get("path_weights")),
        "primer": _normalize_primer_config(rec.get("primer")),
        "path_roles": profile.get("path_roles") or [],
        "detected_languages": profile.get("detected_languages") or [],
        "marker_files": profile.get("marker_files") or [],
    }


def ensure_repo_policy(index_dir: Path, repo_root: Path, force: bool = False) -> Dict[str, Any]:
    index_dir = Path(index_dir)
    repo_root = Path(repo_root).resolve()

    path = policy_path_for_index(index_dir)

    if not force:
        existing = load_repo_policy(path)
        if existing and str(existing.get("repo_root") or "") == str(repo_root):
            existing["include_globs"] = _normalize_globs(existing.get("include_globs"))
            
            # Ensure robust excludes are present (Auto-migration)
            current_excludes = set(_normalize_globs(existing.get("exclude_globs")))
            # Construct default globs from the centralized list
            default_excludes = {f"**/{d}/**" for d in DEFAULT_EXCLUDE_DIR_NAMES}
            default_excludes.add("**/.*")
            
            # Merge defaults if missing
            if not default_excludes.issubset(current_excludes):
                existing["exclude_globs"] = sorted(list(current_excludes | default_excludes))
                # Write back to disk so the change persists and is picked up by watchers
                write_repo_policy(path, existing)
            else:
                existing["exclude_globs"] = sorted(list(current_excludes))

            existing["role_weights"] = _normalize_role_weights(existing.get("role_weights"))
            existing["path_weights"] = _normalize_path_weights(existing.get("path_weights"))
            existing["primer"] = _normalize_primer_config(existing.get("primer"))
            return existing

    profile = profile_repo(repo_root)
    policy = policy_from_profile(profile, repo_root=repo_root)
    write_repo_policy(path, policy)
    return policy
