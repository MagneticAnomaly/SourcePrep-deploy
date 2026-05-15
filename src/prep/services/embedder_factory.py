"""
Prep Embedder Factory — Phase 23 (S-23.6), Phase 139 singleton
=============================================================

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

**Phase 139 (2026-05-15):** embedders returned by this factory are
**process-wide singletons** keyed by (kind, identity). Multiple calls
to ``create_embedder(...)`` with the same resolved configuration
return the same instance. This eliminates the duplicate-InferenceSession
problem documented in ``docs/Phase139_EmbedderMemoryHardening/``.

``close_shared_embedders()`` releases all cached embedders — wire to
graceful daemon shutdown and ``/pipeline/rebuild/stop``.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from prep.core import NativeEmbedder, OllamaEmbedder

logger = logging.getLogger(__name__)


# Phase 139 singleton cache. Key is a tuple (kind, identity) where
# `kind` is "native" | "ollama" and `identity` is a stable per-kind
# tuple of the constructor args that affect model state — model name,
# base_url, etc. Each entry holds one live Embedder instance.
_SHARED_EMBEDDERS: dict[tuple, Any] = {}
_SHARED_EMBEDDERS_LOCK = threading.Lock()


def _cache_get_or_make(key: tuple, factory: Any) -> Any:
    """Return cached embedder for *key* or construct via *factory* under the lock."""
    # Fast path — read without holding the lock (dict reads are atomic for our key shape).
    cached = _SHARED_EMBEDDERS.get(key)
    if cached is not None:
        return cached
    with _SHARED_EMBEDDERS_LOCK:
        cached = _SHARED_EMBEDDERS.get(key)
        if cached is not None:
            return cached
        instance = factory()
        _SHARED_EMBEDDERS[key] = instance
        return instance


def close_shared_embedders() -> int:
    """Drop all cached embedders and call close() on any that expose it.

    Returns the number of embedders released. Per RESEARCH.md §1.1 this
    will not deterministically reclaim CoreML/ANE memory in the live
    process — restart is the documented remedy — but it does drop the
    Python references so the next call gets a fresh session.

    Wired to: graceful daemon shutdown, ``/pipeline/rebuild/stop``.
    """
    import gc
    with _SHARED_EMBEDDERS_LOCK:
        n = len(_SHARED_EMBEDDERS)
        for key, emb in list(_SHARED_EMBEDDERS.items()):
            try:
                close = getattr(emb, "close", None)
                if callable(close):
                    close()
            except Exception:
                logger.debug("close() failed for embedder %r", key, exc_info=True)
        _SHARED_EMBEDDERS.clear()
    gc.collect()
    if n:
        logger.info("Released %d shared embedder(s)", n)
    return n


def _drop_cached(key: tuple) -> None:
    """Remove a cache entry. Used when an embedder fails its readiness check."""
    with _SHARED_EMBEDDERS_LOCK:
        emb = _SHARED_EMBEDDERS.pop(key, None)
    if emb is not None:
        close = getattr(emb, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                logger.debug("close() failed for dropped embedder %r", key, exc_info=True)


def _is_available(emb: Any) -> bool:
    """Check ``emb.is_available()`` if defined, treat absence as available."""
    fn = getattr(emb, "is_available", None)
    if fn is None:
        return True
    try:
        return bool(fn())
    except Exception:
        return True  # transient — let the caller try


def _native_key() -> tuple:
    """Stable cache key for NativeEmbedder — only one instance ever."""
    # NativeEmbedder is parameterless in practice (defaults to nomic-embed-text-v1.5).
    # If we ever support multiple native models, extend this tuple.
    return ("native", NativeEmbedder.HF_REPO_ID)


def _ollama_key(model: str, base_url: str) -> tuple:
    return ("ollama", model, base_url)


def create_embedder(embedding_source: Optional[str] = None) -> Any:
    """Create or return the cached embedder for the resolved configuration.

    Priority (highest → lowest):
    1. Explicit *embedding_source* parameter (project-level override).
    2. Dashboard ``llm_config.embedding`` settings persisted in ui_config.json.
    3. CLI ``_config`` values (``--model``, ``--ollama-url``).
    4. NativeEmbedder (if deps available), else OllamaEmbedder fallback.

    **Headless safety:** If ``prep.server`` is not importable (e.g., in
    a headless Docker container without FastAPI), steps 2-3 are skipped
    gracefully and we fall through to step 4.

    **Phase 139 — singleton:** the returned embedder is cached
    process-wide and reused across all subsequent calls with the same
    resolved configuration. Use ``close_shared_embedders()`` to release.
    """
    # Try to load server config — gracefully degrade in headless mode
    _config: dict = {}
    _load_ui_config = None
    try:
        from prep.server import _config as _srv_config, _load_ui_config as _srv_load_ui
        _config = _srv_config
        _load_ui_config = _srv_load_ui
    except ImportError:
        logger.debug("prep.server not available (headless mode); skipping dashboard/CLI config")

    # ── 1. Explicit project-level override ──────────────────
    if embedding_source == "ollama":
        ollama_url = _config.get("ollama_url", "http://localhost:11434")
        model = _config.get("model", "nomic-embed-text")
        return _cache_get_or_make(
            _ollama_key(model, ollama_url),
            lambda: (
                logger.info("Using OllamaEmbedder (project override, model=%s, url=%s)", model, ollama_url)
                or OllamaEmbedder(model=model, base_url=ollama_url)
            ),
        )

    if embedding_source == "native":
        native = _cache_get_or_make(
            _native_key(),
            _make_native_logged("project override"),
        )
        if native is not None and _is_available(native):
            return native
        # Explicit native requested but deps missing — drop the unusable
        # entry and fall through to CLI / fallback. Without this, a
        # broken native cache pin sticks for the daemon lifetime.
        _drop_cached(_native_key())

    # ── 2. Dashboard llm_config (ui_config.json) ────────────
    if embedding_source is None and _load_ui_config is not None:
        try:
            ui_cfg = _load_ui_config()
            emb_cfg = (ui_cfg.get("llm_config") or {}).get("embedding") or {}
            dash_source = emb_cfg.get("source", "")

            if dash_source == "huggingface":
                native = _cache_get_or_make(
                    _native_key(),
                    _make_native_logged("dashboard: HuggingFace source"),
                )
                if native is not None and _is_available(native):
                    return native
                _drop_cached(_native_key())
                logger.warning("Dashboard set to HuggingFace but NativeEmbedder deps missing")

            elif dash_source == "endpoint":
                ep_id = emb_cfg.get("endpoint_id", "")
                dash_model = emb_cfg.get("model", "")
                if ep_id and dash_model:
                    endpoints = (ui_cfg.get("llm_config") or {}).get("saved_endpoints") or []
                    ep = next((e for e in endpoints if e.get("id") == ep_id), None)
                    if ep and ep.get("provider") == "ollama":
                        ep_url = ep.get("url", "http://localhost:11434")
                        return _cache_get_or_make(
                            _ollama_key(dash_model, ep_url),
                            lambda: (
                                logger.info(
                                    "Using OllamaEmbedder (dashboard: endpoint=%s, model=%s, url=%s)",
                                    ep_id, dash_model, ep_url,
                                )
                                or OllamaEmbedder(model=dash_model, base_url=ep_url)
                            ),
                        )
        except Exception:
            logger.debug("Failed to read dashboard embedding config; falling back", exc_info=True)

    # ── 3. CLI _config fallback ─────────────────────────────
    cli_source = _config.get("embedding_source", "native")
    if cli_source == "ollama":
        ollama_url = _config.get("ollama_url", "http://localhost:11434")
        model = _config.get("model", "nomic-embed-text")
        return _cache_get_or_make(
            _ollama_key(model, ollama_url),
            lambda: (
                logger.info("Using OllamaEmbedder (cli fallback, model=%s, url=%s)", model, ollama_url)
                or OllamaEmbedder(model=model, base_url=ollama_url)
            ),
        )

    # ── 4. NativeEmbedder default / OllamaEmbedder fallback ─
    native = _cache_get_or_make(
        _native_key(),
        _make_native_logged("nomic-embed-text-v1.5 via ONNX"),
    )
    if native is not None and _is_available(native):
        return native
    _drop_cached(_native_key())

    logger.warning("NativeEmbedder deps not installed; falling back to OllamaEmbedder")
    ollama_url = _config.get("ollama_url", "http://localhost:11434")
    model = _config.get("model", "nomic-embed-text")
    return _cache_get_or_make(
        _ollama_key(model, ollama_url),
        lambda: OllamaEmbedder(model=model, base_url=ollama_url),
    )


def _make_native_logged(reason: str):
    """Return a factory closure that constructs a NativeEmbedder with a log line."""
    def factory():
        logger.info("Using NativeEmbedder (%s)", reason)
        # Mark this construction as factory-driven so the singleton-bypass
        # warning in NativeEmbedder.__init__ does not fire (Phase 139 Q11).
        return NativeEmbedder(_from_factory=True)  # type: ignore[call-arg]
    return factory
