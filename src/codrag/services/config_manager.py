"""
CoDRAG Config Manager Service — Phase 23 Sprint 16b
=====================================================

**Origin:** Extracted from ``server.py`` (lines ~163–344).

**What this encapsulates:**
  - ``_DEFAULT_UI_CONFIG`` — default glob patterns, limits, and feature config
  - ``_ui_config_path()`` — resolve config file location
  - ``_default_ui_config()`` — build a default config dict from CLI args
  - ``_deep_merge()`` — recursive dict merge
  - ``_load_ui_config()`` — load + merge persisted config with defaults
  - ``_save_ui_config()`` — persist config to disk

**Consumers:** system router (global config GET/PUT), projects router
(default globs for new projects, coverage), LLM router (embedding source),
knowledge router, BuildManager (embedder creation).

**Phase 24 note (State Machine SM-1):**
  SM-1 (Dashboard Config) will own the config lifecycle. The load/save
  functions here will become the persistence layer beneath the state
  machine, which adds validation and change-event emission.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ── Default UI configuration ────────────────────────────────────

_DEFAULT_UI_CONFIG: Dict[str, Any] = {
    "repo_root": "",
    "core_roots": [],
    "working_roots": [],
    "include_globs": [
        # Documentation & Data
        "**/*.md", "**/*.txt", "**/*.json", "**/*.yaml", "**/*.yml", "**/*.toml", "**/*.xml", "**/*.csv", "**/*.tsv",
        "**/*.sql", "**/*.graphql", "**/*.gql", "**/*.proto",
        
        # Web
        "**/*.html", "**/*.css", "**/*.scss", "**/*.less", "**/*.sass",
        "**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx", "**/*.mjs", "**/*.cjs", "**/*.vue", "**/*.svelte", "**/*.astro",
        
        # Systems & Low Level
        "**/*.c", "**/*.h", "**/*.cpp", "**/*.hpp", "**/*.cc", "**/*.cxx", "**/*.hh", "**/*.hxx", "**/*.m", "**/*.mm",
        "**/*.rs", "**/*.go", "**/*.swift", "**/*.java", "**/*.kt", "**/*.kts", "**/*.scala", "**/*.sc",
        
        # Scripting & Backend
        "**/*.py", "**/*.pyi", "**/*.rb", "**/*.php", "**/*.pl", "**/*.pm", "**/*.lua", "**/*.tcl",
        "**/*.sh", "**/*.bash", "**/*.zsh", "**/*.fish", "**/*.ps1", "**/*.bat", "**/*.cmd",
        
        # .NET
        "**/*.cs", "**/*.fs", "**/*.vb", "**/*.cshtml", "**/*.aspx",
        
        # Functional
        "**/*.hs", "**/*.lhs", "**/*.ex", "**/*.exs", "**/*.erl", "**/*.hrl", "**/*.clj", "**/*.cljs", "**/*.cljc", "**/*.edn", "**/*.lisp", "**/*.lsp", "**/*.scm", "**/*.ss", "**/*.rkt", "**/*.ml", "**/*.mli", "**/*.elm",
        
        # Mobile
        "**/*.dart",
        
        # Data Science
        "**/*.r", "**/*.R", "**/*.jl", "**/*.ipynb",
        
        # Config & DevOps
        "**/*.cfg", "**/*.ini", "**/*.conf", "**/*.properties", "**/*.env", "**/*.env.*",
        "**/Dockerfile", "**/*.dockerfile", "**/Makefile", "**/*.mk", "**/CMakeLists.txt", "**/*.cmake",
        "**/*.gradle", "**/*.tf", "**/*.tfvars", "**/*.hcl", "**/*.sol"
    ],
    "exclude_globs": [
        "**/.*",  # Broadly exclude dotfiles and dot-directories
        "**/.git/**",
        "**/.venv/**",
        "**/__pycache__/**",
        "**/node_modules/**",
        "**/dist/**",
        "**/build/**",
        "**/.next/**",
        "**/*.map",
        "**/*.lock",
    ],
    "max_file_bytes": 500_000,  # Threshold for full indexing (above this = summary only)
    "hard_limit_bytes": 100_000_000,  # 100MB hard limit (above this = ignored)
    "trace": {"enabled": False},
    "auto_rebuild": {"enabled": False, "debounce_ms": 5000},
    "llm_config": None,  # Will be populated with defaults if missing
    "deep_analysis": {
        "mode": "manual",
        "threshold_percent": 20,
        "frequency": "weekly",
        "day_of_week": 0,
        "hour": 2,
        "budget_max_tokens": 50000,
        "budget_max_minutes": 30,
        "budget_max_items": 100,
        "priority": "lowest_confidence",
    },
    "pipeline_config": {
        "fast_sync": {
            "auto": True,
        },
        "deep_enrichment": {
            "mode": "manual",  # 'manual' | 'auto' | 'scheduled'
            "schedule": {
                "frequency": "weekly",
                "day_of_week": 0,
                "hour": 2,
            },
        },
        "budgets": {
            "max_tokens_per_run": 50000,
            "max_minutes_per_run": 30,
            "max_items_per_stage": 100,
        },
    },
}


# ── Config helpers ───────────────────────────────────────────────

def ui_config_path(config: Dict[str, Any]) -> Path:
    """Resolve the path to ui_config.json from the server config."""
    index_dir = Path(config.get("index_dir", "./codrag_data"))
    return index_dir / "ui_config.json"


def default_ui_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build a default UI config dict from CLI/server config."""
    from codrag.core import NativeEmbedder

    repo_root = str(config.get("repo_root") or "")

    cfg: Dict[str, Any] = dict(_DEFAULT_UI_CONFIG)
    cfg["repo_root"] = repo_root

    if repo_root:
        cfg["core_roots"] = []
    # Default LLM Config
    ollama_url = str(config.get("ollama_url") or "http://localhost:11434")
    model = str(config.get("model") or "nomic-embed-text")
    
    cfg["llm_config"] = {
        "saved_endpoints": [
            {
                "id": "default_ollama",
                "name": "Default Ollama",
                "provider": "ollama",
                "url": ollama_url,
            }
        ],
        "embedding": {
            "source": "huggingface",
            "hf_repo_id": "nomic-ai/nomic-embed-text-v1.5",
            "hf_downloaded": NativeEmbedder().is_available(),
            "endpoint_id": "default_ollama",
            "model": model,
        },
        "small_model": {
            "enabled": False,
            "endpoint_id": "",
            "model": "",
        },
        "large_model": {
            "enabled": False,
            "endpoint_id": "",
            "model": "",
        },
        "clara": {
            "enabled": False,
            "source": "huggingface",
            "hf_repo_id": "apple/CLaRa-7B-Instruct",
        }
    }

    return cfg


def deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge update dict into base dict."""
    for k, v in update.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_ui_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Load UI config — tries SQLite settings store first, falls back to JSON.

    Phase 24: If the settings store is initialized, all global settings are
    merged with defaults.  If not (e.g. tests without server init), falls
    back to the original JSON file loading.
    
    Args:
        config: The server ``_config`` dict (needs ``index_dir``, ``repo_root``, etc.).
    """
    cfg = default_ui_config(config)

    # Try SQLite store first (Phase 24)
    try:
        from codrag.services.settings_store import settings
        store_data = settings.get_all()
        if store_data:
            data = store_data
        else:
            data = _load_json_fallback(config)
    except RuntimeError:
        # Settings store not initialized — fall back to JSON
        data = _load_json_fallback(config)

    if data:
        _merge_config_data(cfg, data)

    return cfg


def _load_json_fallback(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Load config from ui_config.json (legacy fallback)."""
    path = ui_config_path(config)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return None


def _merge_config_data(cfg: Dict[str, Any], data: Dict[str, Any]) -> None:
    """Merge persisted data into a config dict (in-place)."""
    # Top-level merge
    for key in [
        "repo_root",
        "core_roots",
        "working_roots",
        "include_globs",
        "exclude_globs",
        "max_file_bytes",
        "trace",
        "auto_rebuild",
        "ui_preferences",
        "module_layout",
    ]:
        if key in data:
            cfg[key] = data[key]

    # Deep merge for llm_config to preserve defaults for missing fields
    if "llm_config" in data and isinstance(data["llm_config"], dict):
        if "llm_config" not in cfg or not isinstance(cfg["llm_config"], dict):
            cfg["llm_config"] = {}
        deep_merge(cfg["llm_config"], data["llm_config"])

    # Deep merge for deep_analysis schedule config
    if "deep_analysis" in data and isinstance(data["deep_analysis"], dict):
        if "deep_analysis" not in cfg or not isinstance(cfg["deep_analysis"], dict):
            cfg["deep_analysis"] = {}
        deep_merge(cfg["deep_analysis"], data["deep_analysis"])

    # Deep merge for pipeline_config (Phase 24)
    if "pipeline_config" in data and isinstance(data["pipeline_config"], dict):
        if "pipeline_config" not in cfg or not isinstance(cfg["pipeline_config"], dict):
            cfg["pipeline_config"] = {}
        deep_merge(cfg["pipeline_config"], data["pipeline_config"])


def save_ui_config(config: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    """Persist UI config — writes to both SQLite and JSON (dual-write).

    Phase 24: Writes to the SQLite settings store AND the legacy JSON file.
    The JSON write ensures backward compatibility during the transition.
    
    Args:
        config: The server ``_config`` dict (needs ``index_dir``).
        cfg: The UI config dict to save.
    """
    # Write to SQLite store (Phase 24)
    try:
        from codrag.services.settings_store import settings
        settings.import_from_dict(cfg)
    except RuntimeError:
        pass  # Store not initialized — skip

    # Also write to JSON for backward compat
    path = ui_config_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2))
