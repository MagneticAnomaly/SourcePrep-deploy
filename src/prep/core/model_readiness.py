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
    # Cloud-proxied models (e.g. kimi-k2.5:cloud, qwen3-coder-next:cloud)
    # run on Ollama's cloud GPUs — there is no local VRAM to warm up.
    # Preloading sends an empty-prompt request that occupies a cloud
    # concurrency slot (Free=1, Pro=3, Max=10) and blocks actual pipeline
    # LLM calls with 429 Too Many Requests.  Skip preload entirely.
    if ":cloud" in model.lower():
        logger.debug("Skipping preload for cloud model %s — runs on remote GPUs", model)
        return ModelReadinessResult(
            status=ModelStatus.READY,
            message=f"Cloud model '{model}' — no local preload needed",
        )

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
# LM Studio readiness helpers (v1 REST API — LM Studio 0.4+)
# ---------------------------------------------------------------------------

def _lmstudio_api_base(url: str) -> str:
    """Normalise an LM Studio endpoint URL to the /api/v1 base.

    Users typically configure ``http://localhost:1234`` as the endpoint.
    The native management API lives at ``/api/v1/*`` (NOT the
    OpenAI-compat ``/v1/*`` path).
    """
    url = url.rstrip("/")
    if url.endswith("/api/v1"):
        return url
    if url.endswith("/v1"):
        url = url[:-3]
    return f"{url}/api/v1"


def _lmstudio_key_matches(key: str, model: str) -> bool:
    """Check if an LM Studio model key matches the user-provided model name.

    LM Studio keys use ``publisher/model-name`` format (e.g.
    ``qwen/qwen3-4b-2507``).  We accept a match if:
    - Exact match (case-insensitive)
    - Key ends with the model name (publisher prefix stripped)
    - Model contains the key or vice versa
    """
    key_l = key.lower().strip()
    model_l = model.lower().strip()
    if key_l == model_l:
        return True
    if key_l.endswith(f"/{model_l}"):
        return True
    if model_l.endswith(f"/{key_l}"):
        return True
    if model_l in key_l or key_l in model_l:
        return True
    return False


def lmstudio_server_reachable(url: str) -> bool:
    """Return True if the LM Studio server responds to a lightweight probe."""
    try:
        base = _lmstudio_api_base(url)
        r = requests.get(f"{base}/models", timeout=_QUICK_TIMEOUT)
        return r.status_code == 200
    except Exception:
        return False


def lmstudio_model_exists(url: str, model: str) -> bool:
    """Check whether *model* is available (downloaded) in LM Studio."""
    try:
        base = _lmstudio_api_base(url)
        r = requests.get(f"{base}/models", timeout=_QUICK_TIMEOUT)
        if r.status_code != 200:
            return False
        for m in r.json().get("models", []):
            if _lmstudio_key_matches(m.get("key", ""), model):
                return True
        return False
    except Exception:
        return False


def lmstudio_model_loaded(url: str, model: str) -> bool:
    """Check whether *model* is currently loaded into memory."""
    try:
        base = _lmstudio_api_base(url)
        r = requests.get(f"{base}/models", timeout=_QUICK_TIMEOUT)
        if r.status_code != 200:
            return False
        for m in r.json().get("models", []):
            if _lmstudio_key_matches(m.get("key", ""), model):
                if m.get("loaded_instances"):
                    return True
        return False
    except Exception:
        return False


def lmstudio_list_loaded(url: str) -> List[str]:
    """Return keys of all models currently loaded in LM Studio."""
    try:
        base = _lmstudio_api_base(url)
        r = requests.get(f"{base}/models", timeout=_QUICK_TIMEOUT)
        if r.status_code != 200:
            return []
        return [m.get("key", "") for m in r.json().get("models", []) if m.get("loaded_instances")]
    except Exception:
        return []


def _lmstudio_resolve_key(url: str, model: str) -> Optional[str]:
    """Resolve a user-provided model name to the exact LM Studio model key."""
    try:
        base = _lmstudio_api_base(url)
        r = requests.get(f"{base}/models", timeout=_QUICK_TIMEOUT)
        if r.status_code != 200:
            return None
        for m in r.json().get("models", []):
            key = m.get("key", "")
            if _lmstudio_key_matches(key, model):
                return key
        return None
    except Exception:
        return None


def _lmstudio_get_instance_id(url: str, model: str) -> Optional[str]:
    """Get the instance_id of a loaded model (needed for unload)."""
    try:
        base = _lmstudio_api_base(url)
        r = requests.get(f"{base}/models", timeout=_QUICK_TIMEOUT)
        if r.status_code != 200:
            return None
        for m in r.json().get("models", []):
            if _lmstudio_key_matches(m.get("key", ""), model):
                instances = m.get("loaded_instances", [])
                if instances:
                    return instances[0].get("id", m.get("key", ""))
        return None
    except Exception:
        return None


def lmstudio_load(
    url: str,
    model: str,
    timeout_s: int = _PRELOAD_TIMEOUT,
    context_length: Optional[int] = None,
) -> bool:
    """Load a model into memory via ``POST /api/v1/models/load``.

    Returns True if the model was successfully loaded.

    Args:
        context_length: Max context length for the model.  If None,
                        LM Studio uses its default for the model.
    """
    base = _lmstudio_api_base(url)
    resolved_key = _lmstudio_resolve_key(url, model)
    if resolved_key is None:
        logger.error("LM Studio: model '%s' not found on %s", model, url)
        return False

    payload: Dict[str, Any] = {"model": resolved_key}
    if context_length is not None:
        payload["context_length"] = context_length

    try:
        r = requests.post(f"{base}/models/load", json=payload, timeout=timeout_s)
        if r.status_code == 200:
            data = r.json()
            load_time = data.get("load_time_seconds", "?")
            logger.info("LM Studio: loaded '%s' (instance=%s, %.1fs)",
                        resolved_key, data.get("instance_id", "?"),
                        float(load_time) if load_time != "?" else 0)
            return True
        if lmstudio_model_loaded(url, model):
            logger.info("LM Studio: '%s' already loaded", resolved_key)
            return True
        logger.warning("LM Studio load '%s' returned %d: %s",
                        resolved_key, r.status_code, r.text[:300])
        return False
    except requests.Timeout:
        if lmstudio_model_loaded(url, model):
            return True
        logger.warning("LM Studio load '%s' timed out after %ds", resolved_key, timeout_s)
        return False
    except Exception as e:
        logger.warning("LM Studio load '%s' failed: %s", resolved_key, e)
        return False


def lmstudio_unload(url: str, model: str) -> bool:
    """Unload a model from memory via ``POST /api/v1/models/unload``."""
    base = _lmstudio_api_base(url)
    instance_id = _lmstudio_get_instance_id(url, model)
    if instance_id is None:
        logger.debug("LM Studio: '%s' not loaded, nothing to unload", model)
        return True
    try:
        r = requests.post(f"{base}/models/unload", json={"instance_id": instance_id}, timeout=10)
        if r.status_code == 200:
            logger.info("LM Studio: unloaded '%s' (instance=%s)", model, instance_id)
            return True
        logger.warning("LM Studio unload '%s' returned %d: %s",
                        instance_id, r.status_code, r.text[:300])
        return False
    except Exception as e:
        logger.warning("LM Studio unload '%s' failed: %s", instance_id, e)
        return False


def lmstudio_get_status(url: str, model: str) -> ModelReadinessResult:
    """Return a composite readiness status for *model* on LM Studio."""
    base_result = ModelReadinessResult(model=model, provider="lm-studio",
                                       status=ModelStatus.ERROR, message="")
    if not lmstudio_server_reachable(url):
        base_result.message = f"Cannot reach LM Studio at {url}"
        return base_result
    if not lmstudio_model_exists(url, model):
        base_result.status = ModelStatus.NOT_FOUND
        base_result.message = (f"Model '{model}' is not available in LM Studio. "
                                f"Download it via the LM Studio UI or: lms get {model}")
        return base_result
    if lmstudio_model_loaded(url, model):
        base_result.status = ModelStatus.READY
        base_result.message = f"Model '{model}' is loaded and ready"
        base_result.details["loaded_models"] = lmstudio_list_loaded(url)
        return base_result
    base_result.status = ModelStatus.DOWNLOADED
    base_result.message = f"Model '{model}' is available but not loaded into memory"
    return base_result


def lmstudio_ensure_ready(
    url: str,
    model: str,
    timeout_s: int = _PRELOAD_TIMEOUT,
    poll_interval_s: float = 1.0,
    context_length: Optional[int] = None,
) -> ModelReadinessResult:
    """Ensure *model* is loaded and ready in LM Studio, loading if necessary.

    Args:
        context_length: Max context length to set when loading the model.
    """
    status = lmstudio_get_status(url, model)
    if status.status == ModelStatus.READY:
        return status
    if status.status in (ModelStatus.NOT_FOUND, ModelStatus.ERROR):
        return status

    logger.info("LM Studio: model '%s' not loaded, triggering load on %s (timeout=%ds)...",
                model, url, timeout_s)
    status.status = ModelStatus.LOADING
    status.message = f"Loading model '{model}' into memory..."

    import threading
    load_done = threading.Event()
    load_ok = [False]

    def _do_load():
        load_ok[0] = lmstudio_load(url, model, timeout_s=timeout_s, context_length=context_length)
        load_done.set()

    t = threading.Thread(target=_do_load, daemon=True)
    t.start()
    deadline = time.monotonic() + timeout_s

    while time.monotonic() < deadline:
        if load_done.is_set():
            break
        if lmstudio_model_loaded(url, model):
            break
        time.sleep(poll_interval_s)

    if lmstudio_model_loaded(url, model):
        elapsed = timeout_s - (deadline - time.monotonic())
        status.status = ModelStatus.READY
        status.message = f"Model '{model}' loaded and ready (took ~{elapsed:.1f}s)"
        status.details["load_time_s"] = round(elapsed, 1)
        logger.info("LM Studio: model '%s' is now ready (%.1fs)", model, elapsed)
    elif load_done.is_set() and load_ok[0]:
        status.status = ModelStatus.READY
        status.message = f"Model '{model}' loaded and ready"
    elif load_done.is_set() and not load_ok[0]:
        status.status = ModelStatus.ERROR
        status.message = f"Failed to load model '{model}' in LM Studio"
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

    if provider == "lm-studio":
        return lmstudio_get_status(url, model)

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

    if provider == "lm-studio":
        return lmstudio_ensure_ready(url, model, timeout_s=timeout_s)

    return get_model_status(provider, url, model, api_key=api_key)
