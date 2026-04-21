"""
CoDRAG Embedder Factory — Phase 23 (S-23.6)
=============================================

Extracted from ``build_manager.py`` to separate embedder creation concerns
from build threading/caching.

**Resolution priority (highest → lowest):**
  1. Explicit ``embedding_source`` parameter (project-level override).
  2. Dashboard ``llm_config.embedding`` settings persisted in ui_config / settings store.
  3. CLI ``_config`` values (``--model``, ``--ollama-url``).
  4. NativeEmbedder (if deps available), else OllamaEmbedder fallback.

**Usage:**
  ``from prep.services.embedder_factory import create_embedder``
  ``embedder = create_embedder()``                    # auto-resolve
  ``embedder = create_embedder("native")``            # explicit
  ``embedder = create_embedder("ollama")``            # explicit
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from prep.core import NativeEmbedder, OllamaEmbedder

logger = logging.getLogger(__name__)


def create_embedder(embedding_source: Optional[str] = None) -> Any:
    """Create the appropriate embedder based on configuration.

    Priority (highest → lowest):
    1. Explicit *embedding_source* parameter (project-level override).
    2. Dashboard ``llm_config.embedding`` settings persisted in ui_config.json.
    3. CLI ``_config`` values (``--model``, ``--ollama-url``).
    4. NativeEmbedder (if deps available), else OllamaEmbedder fallback.

    **Headless safety:** If ``codrag.server`` is not importable (e.g., in
    a headless Docker container without FastAPI), steps 2-3 are skipped
    gracefully and we fall through to step 4.
    """
    # Try to load server config — gracefully degrade in headless mode
    _config: dict = {}
    _load_ui_config = None
    try:
        from prep.server import _config as _srv_config, _load_ui_config as _srv_load_ui
        _config = _srv_config
        _load_ui_config = _srv_load_ui
    except ImportError:
        logger.debug("codrag.server not available (headless mode); skipping dashboard/CLI config")

    # ── 1. Explicit project-level override ──────────────────
    if embedding_source == "ollama":
        ollama_url = _config.get("ollama_url", "http://localhost:11434")
        model = _config.get("model", "nomic-embed-text")
        logger.info("Using OllamaEmbedder (project override, model=%s, url=%s)", model, ollama_url)
        return OllamaEmbedder(model=model, base_url=ollama_url)

    if embedding_source == "native":
        native = NativeEmbedder()
        if native.is_available():
            logger.info("Using NativeEmbedder (project override)")
            return native

    # ── 2. Dashboard llm_config (ui_config.json) ────────────
    if embedding_source is None and _load_ui_config is not None:
        try:
            ui_cfg = _load_ui_config()
            emb_cfg = (ui_cfg.get("llm_config") or {}).get("embedding") or {}
            dash_source = emb_cfg.get("source", "")

            if dash_source == "huggingface":
                native = NativeEmbedder()
                if native.is_available():
                    logger.info("Using NativeEmbedder (dashboard: HuggingFace source)")
                    return native
                logger.warning("Dashboard set to HuggingFace but NativeEmbedder deps missing")

            elif dash_source == "endpoint":
                ep_id = emb_cfg.get("endpoint_id", "")
                dash_model = emb_cfg.get("model", "")
                if ep_id and dash_model:
                    endpoints = (ui_cfg.get("llm_config") or {}).get("saved_endpoints") or []
                    ep = next((e for e in endpoints if e.get("id") == ep_id), None)
                    if ep and ep.get("provider") == "ollama":
                        ep_url = ep.get("url", "http://localhost:11434")
                        logger.info(
                            "Using OllamaEmbedder (dashboard: endpoint=%s, model=%s, url=%s)",
                            ep_id, dash_model, ep_url,
                        )
                        return OllamaEmbedder(model=dash_model, base_url=ep_url)
        except Exception:
            logger.debug("Failed to read dashboard embedding config; falling back", exc_info=True)

    # ── 3. CLI _config fallback ─────────────────────────────
    cli_source = _config.get("embedding_source", "native")
    if cli_source == "ollama":
        ollama_url = _config.get("ollama_url", "http://localhost:11434")
        model = _config.get("model", "nomic-embed-text")
        logger.info("Using OllamaEmbedder (cli fallback, model=%s, url=%s)", model, ollama_url)
        return OllamaEmbedder(model=model, base_url=ollama_url)

    # ── 4. NativeEmbedder default / OllamaEmbedder fallback ─
    native = NativeEmbedder()
    if native.is_available():
        logger.info("Using NativeEmbedder (nomic-embed-text-v1.5 via ONNX)")
        return native

    logger.warning("NativeEmbedder deps not installed; falling back to OllamaEmbedder")
    ollama_url = _config.get("ollama_url", "http://localhost:11434")
    model = _config.get("model", "nomic-embed-text")
    return OllamaEmbedder(model=model, base_url=ollama_url)
