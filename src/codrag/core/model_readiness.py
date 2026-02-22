"""
Model readiness detection and warm-up for LLM providers.

Ollama (and similar local inference servers) have a cold-start problem:
the first request to a model triggers loading weights from disk into
VRAM, which can take 10-120+ seconds depending on model size and
hardware.  A naive timeout (e.g. 10 s) causes a confusing "timed out"
error even though the model would be ready moments later.

This module provides:
  - Status checking  — is the model downloaded? loaded in VRAM?
  - Preloading        — trigger model load without generating text
  - Wait-for-ready   — poll until model is serving or timeout
  - Normalisation     — handle `:latest` tag variants
"""

from __future__ import annotations

import enum
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model name normalisation
# ---------------------------------------------------------------------------

def normalise_model_name(name: str) -> str:
    """Strip the implicit ':latest' tag so names compare correctly.

    Ollama treats ``mistral`` and ``mistral:latest`` as the same model,
    but the API returns the tag inconsistently.
    """
    return re.sub(r":latest$", "", name.strip())


def _names_match(a: str, b: str) -> bool:
    return normalise_model_name(a) == normalise_model_name(b)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class ModelStatus(str, enum.Enum):
    """Lifecycle state of a model on the Ollama host."""

    NOT_FOUND = "not_found"        # model not downloaded
    DOWNLOADED = "downloaded"      # on disk but not in VRAM
    LOADING = "loading"            # preload triggered, waiting for VRAM
    READY = "ready"                # loaded in VRAM, serving requests
    ERROR = "error"                # provider unreachable or unexpected error


@dataclass
class ModelReadinessResult:
    """Rich status returned by readiness checks."""

    status: ModelStatus
    message: str
    model: str = ""
    provider: str = "ollama"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "model": self.model,
            "provider": self.provider,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Ollama readiness helpers
# ---------------------------------------------------------------------------

_QUICK_TIMEOUT = 3        # seconds – for lightweight metadata calls
_PRELOAD_TIMEOUT = 180    # seconds – for the preload generate call


def ollama_server_reachable(url: str) -> bool:
    """Return True if the Ollama server responds to a lightweight probe."""
    try:
        r = requests.get(f"{url}/api/tags", timeout=_QUICK_TIMEOUT)
        return r.status_code == 200
    except Exception:
        return False


def ollama_model_exists(url: str, model: str) -> bool:
    """Check whether *model* is downloaded on the Ollama host.

    Uses ``POST /api/show`` which returns 200 if the model exists.
    Falls back to scanning ``GET /api/tags`` if ``/api/show`` fails
    (some models like ministral have broken templates that cause
    ``/api/show`` to return 500 even though the model is installed).
    """
    try:
        r = requests.post(
            f"{url}/api/show",
            json={"name": model},
            timeout=_QUICK_TIMEOUT,
        )
        if r.status_code == 200:
            return True
    except Exception:
        pass

    # Fallback: scan /api/tags which lists all downloaded models
    try:
        r = requests.get(f"{url}/api/tags", timeout=_QUICK_TIMEOUT)
        if r.status_code == 200:
            for m in r.json().get("models", []):
                name = m.get("name", "")
                if _names_match(name, model):
                    return True
    except Exception:
        pass

    return False


def ollama_model_loaded(url: str, model: str) -> bool:
    """Check whether *model* is currently loaded into memory (VRAM/RAM).

    Uses ``GET /api/ps`` which lists running models.
    """
    try:
        r = requests.get(f"{url}/api/ps", timeout=_QUICK_TIMEOUT)
        if r.status_code != 200:
            return False
        data = r.json()
        for m in data.get("models", []):
            name = m.get("model") or m.get("name", "")
            if _names_match(name, model):
                return True
        return False
    except Exception:
        return False


def ollama_list_loaded(url: str) -> List[str]:
    """Return names of all models currently loaded in memory."""
    try:
        r = requests.get(f"{url}/api/ps", timeout=_QUICK_TIMEOUT)
        if r.status_code != 200:
            return []
        data = r.json()
        return [
            m.get("model") or m.get("name", "")
            for m in data.get("models", [])
        ]
    except Exception:
        return []


def ollama_preload(
    url: str,
    model: str,
    keep_alive: str = "10m",
    timeout_s: int = _PRELOAD_TIMEOUT,
    options: Optional[Dict[str, Any]] = None,
) -> bool:
    """Trigger model loading by sending an empty generate request.

    Returns True if Ollama accepted the request (which means the model
    is now loaded or loading).  The call blocks until the model is
    fully loaded—Ollama queues it internally.

    For embedding-only models (e.g. nomic-embed-text) that don't
    support /api/generate, falls back to /api/embed with a tiny input.

    Args:
        options: Ollama options dict (e.g. ``{"num_ctx": 8192}``).
                 Passed through so the model is loaded with the correct
                 context window from the start.
    """
    # Try /api/generate first (works for LLM models)
    try:
        r = requests.post(
            f"{url}/api/generate",
            json={
                "model": model,
                "prompt": "",
                "keep_alive": keep_alive,
                "stream": False,
                **(({"options": options} if options else {})),
            },
            timeout=timeout_s,
        )
        if r.status_code == 200:
            return True
    except requests.Timeout:
        # Timeout doesn't mean failure – model may still be loading
        return False
    except Exception:
        pass

    # Fallback: /api/embed for embedding-only models
    try:
        r = requests.post(
            f"{url}/api/embed",
            json={
                "model": model,
                "input": "warmup",
                "keep_alive": keep_alive,
                **(({"options": options} if options else {})),
            },
            timeout=timeout_s,
        )
        return r.status_code == 200
    except requests.Timeout:
        return False
    except Exception:
        return False


def ollama_get_status(url: str, model: str) -> ModelReadinessResult:
    """Return a composite readiness status for *model* on *url*.

    This is the primary status API.  It performs up to 3 lightweight
    checks in sequence (server → model exists → model loaded) and
    returns the most specific status it can determine.
    """
    base = ModelReadinessResult(model=model, provider="ollama", status=ModelStatus.ERROR, message="")

    # 1. Server reachable?
    if not ollama_server_reachable(url):
        base.status = ModelStatus.ERROR
        base.message = f"Cannot reach Ollama at {url}"
        return base

    # 2. Model downloaded?
    if not ollama_model_exists(url, model):
        base.status = ModelStatus.NOT_FOUND
        base.message = f"Model '{model}' is not downloaded. Run: ollama pull {model}"
        return base

    # 3. Model loaded in memory?
    if ollama_model_loaded(url, model):
        base.status = ModelStatus.READY
        base.message = f"Model '{model}' is loaded and ready"
        loaded = ollama_list_loaded(url)
        base.details["loaded_models"] = loaded
        return base

    # Model exists on disk but is not loaded
    base.status = ModelStatus.DOWNLOADED
    base.message = f"Model '{model}' is downloaded but not loaded into memory"
    return base


def ollama_ensure_ready(
    url: str,
    model: str,
    timeout_s: int = _PRELOAD_TIMEOUT,
    poll_interval_s: float = 1.0,
    keep_alive: str = "10m",
    options: Optional[Dict[str, Any]] = None,
) -> ModelReadinessResult:
    """Ensure *model* is loaded and ready, preloading if necessary.

    1. If model is already loaded → return READY immediately.
    2. If model exists on disk → trigger preload and poll until ready.
    3. If model not found → return NOT_FOUND.

    This is the function to call before any LLM operation that requires
    the model to be hot.

    Args:
        options: Ollama options dict (e.g. ``{"num_ctx": 8192}``).
                 Forwarded to the preload request so the model is
                 loaded with the correct context window.
    """
    status = ollama_get_status(url, model)

    if status.status == ModelStatus.READY:
        return status

    if status.status in (ModelStatus.NOT_FOUND, ModelStatus.ERROR):
        return status

    # Model is DOWNLOADED but not loaded — trigger preload
    logger.info("Model '%s' not loaded, triggering preload on %s (timeout=%ds)...", model, url, timeout_s)
    status.status = ModelStatus.LOADING
    status.message = f"Loading model '{model}' into memory..."

    deadline = time.monotonic() + timeout_s

    # Fire off the preload request.  Ollama's /api/generate with empty
    # prompt blocks until the model is loaded, so we use it with the
    # full timeout.  But we also poll /api/ps in parallel so we can
    # give intermediate status updates.
    import threading

    preload_done = threading.Event()
    preload_ok = [False]

    def _do_preload():
        preload_ok[0] = ollama_preload(url, model, keep_alive=keep_alive, timeout_s=timeout_s, options=options)
        preload_done.set()

    t = threading.Thread(target=_do_preload, daemon=True)
    t.start()

    # Poll /api/ps while preload is running
    while time.monotonic() < deadline:
        if preload_done.is_set():
            break
        if ollama_model_loaded(url, model):
            break
        time.sleep(poll_interval_s)

    # Final check
    if ollama_model_loaded(url, model):
        elapsed = timeout_s - (deadline - time.monotonic())
        status.status = ModelStatus.READY
        status.message = f"Model '{model}' loaded and ready (took ~{elapsed:.1f}s)"
        status.details["load_time_s"] = round(elapsed, 1)
        logger.info("Model '%s' is now ready (%.1fs)", model, elapsed)
    elif preload_done.is_set() and preload_ok[0]:
        status.status = ModelStatus.READY
        status.message = f"Model '{model}' loaded and ready"
    elif preload_done.is_set() and not preload_ok[0]:
        status.status = ModelStatus.ERROR
        status.message = f"Failed to load model '{model}' — preload request failed"
    else:
        status.status = ModelStatus.LOADING
        status.message = f"Model '{model}' is still loading (exceeded {timeout_s}s poll window)"

    return status


# ---------------------------------------------------------------------------
# Generic provider readiness (extensible)
# ---------------------------------------------------------------------------

def get_model_status(
    provider: str,
    url: str,
    model: str,
    api_key: Optional[str] = None,
) -> ModelReadinessResult:
    """Get readiness status for a model on any supported provider.

    For cloud providers (OpenAI, Anthropic) models are always "ready"
    if the endpoint is reachable.  Cold-start handling is only relevant
    for local inference servers like Ollama.
    """
    url = url.rstrip("/")

    if provider == "ollama":
        return ollama_get_status(url, model)

    # OpenAI / Anthropic / compatible — always "ready" if endpoint works
    try:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        target = f"{url}/models" if "v1" in url else f"{url}/v1/models"
        r = requests.get(target, headers=headers, timeout=_QUICK_TIMEOUT)
        if r.status_code == 200:
            return ModelReadinessResult(
                status=ModelStatus.READY,
                message="Endpoint reachable",
                model=model,
                provider=provider,
            )
    except Exception:
        pass

    return ModelReadinessResult(
        status=ModelStatus.ERROR,
        message=f"Cannot reach {provider} endpoint at {url}",
        model=model,
        provider=provider,
    )


def ensure_model_ready(
    provider: str,
    url: str,
    model: str,
    api_key: Optional[str] = None,
    timeout_s: int = _PRELOAD_TIMEOUT,
    keep_alive: str = "10m",
) -> ModelReadinessResult:
    """Ensure a model is ready for inference, preloading if needed.

    Only Ollama models need preloading.  For cloud providers this is
    equivalent to ``get_model_status``.
    """
    url = url.rstrip("/")

    if provider == "ollama":
        return ollama_ensure_ready(url, model, timeout_s=timeout_s, keep_alive=keep_alive)

    return get_model_status(provider, url, model, api_key=api_key)
