"""CoDRAG LLM Router — Phase 23 Sprint 13 (updated Phase 31)
========================================

**Endpoints:**
  Embedding:
    - GET  /embedding/status    — native embedder availability & cache status
    - POST /embedding/download  — download HF model to local cache

  Compression:
    - GET  /compression/status  — LinguaCompressor + LOD availability

  LLM Slots & Status:
    - GET  /llm/slots/status    — per-slot connectivity check (embedding, small, large)
    - GET  /llm/status          — legacy Ollama connectivity
    - GET  /api/llm/status      — alias for above

  LLM Testing & Proxy:
    - POST /llm/test            — legacy quick connectivity test
    - POST /api/llm/test        — alias for above
    - POST /api/llm/proxy/models     — list models from an endpoint
    - POST /api/llm/proxy/test       — test endpoint connectivity
    - POST /api/llm/model-status     — model readiness / preload
    - POST /api/llm/proxy/test-model — test a specific model with readiness gate

**Shared state accessed (from server.py):**
  - ``_config``           — CLI config (ollama_url, model)
  - ``_load_ui_config``   — read global config for llm_config slots
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import urllib.parse
import ipaddress
import socket

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok
from codrag.core import NativeEmbedder, LinguaCompressor
from codrag.core.model_readiness import (
    ModelStatus,
    get_model_status,
    ensure_model_ready,
)

def is_safe_url(url: str, provider: str) -> bool:
    """Basic SSRF protection: ensure URL is HTTP/HTTPS."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        return True
    except Exception:
        return False

logger = logging.getLogger(__name__)

router = APIRouter(tags=["llm"])


# ── Pydantic models ─────────────────────────────────────────────

class LLMProxyRequest(BaseModel):
    provider: str = "ollama"
    url: str
    api_key: Optional[str] = None


class LLMModelTestRequest(BaseModel):
    provider: str = "ollama"
    url: str
    model: str
    api_key: Optional[str] = None
    kind: str = "completion"


class ModelStatusRequest(BaseModel):
    provider: str = "ollama"
    url: str
    model: str
    api_key: Optional[str] = None
    ensure_ready: bool = False
    timeout_s: int = 120


# ═════════════════════════════════════════════════════════════════
# Embedding
# ═════════════════════════════════════════════════════════════════

@router.get("/embedding/status")
def embedding_status() -> Dict[str, Any]:
    """Return the current embedding provider status."""
    from codrag.server import _config
    native = NativeEmbedder()
    deps_ok = native.is_available()

    model_cached = False
    model_path = None
    if deps_ok:
        try:
            from huggingface_hub import try_to_load_from_cache  # type: ignore[import-untyped]
            cached = try_to_load_from_cache(
                NativeEmbedder.HF_REPO_ID, NativeEmbedder.ONNX_FILE
            )
            if cached is not None and not isinstance(cached, str):
                model_cached = False
            elif isinstance(cached, str):
                model_cached = True
                model_path = cached
        except Exception:
            pass

    source = _config.get("embedding_source", "native")
    model_name = str(NativeEmbedder.HF_REPO_ID).split("/")[-1]
    return ok({
        "available": deps_ok,
        "model": model_name,
        "dim": NativeEmbedder.DIM,
        "downloaded": model_cached,
        "source": source,
        "native_available": deps_ok,
        "model_cached": model_cached,
        "model_path": model_path,
        "hf_repo_id": NativeEmbedder.HF_REPO_ID,
        "onnx_file": NativeEmbedder.ONNX_FILE,
    })


@router.post("/embedding/download")
def embedding_download() -> Dict[str, Any]:
    """Download the native embedding model from HuggingFace Hub.

    The model is cached in the standard HF cache directory (~/.cache/huggingface/).
    This is a blocking call — the download happens synchronously.
    """
    native = NativeEmbedder()
    if not native.is_available():
        raise ApiException(
            status_code=400,
            code="NATIVE_DEPS_MISSING",
            message="Native embedding dependencies not installed",
            hint="pip install onnxruntime tokenizers huggingface-hub",
        )

    try:
        model_path = native.download_model()
    except Exception as e:
        raise ApiException(
            status_code=500,
            code="DOWNLOAD_FAILED",
            message=f"Model download failed: {e}",
            hint="Check your internet connection and try again.",
        )

    return ok({
        "status": "downloaded",
        "model_path": model_path,
        "hf_repo_id": NativeEmbedder.HF_REPO_ID,
    })


# ═════════════════════════════════════════════════════════════════
# Compression Status
# ═════════════════════════════════════════════════════════════════

@router.get("/compression/status")
def compression_status() -> Dict[str, Any]:
    """Return compression subsystem status (LLMLingua-2 + LOD)."""
    from codrag.core import LinguaCompressor
    
    lingua = LinguaCompressor()
    lingua_info = lingua.status()
    
    # Check if model is cached (only needs huggingface_hub, not llmlingua)
    model_cached = False
    model_path = None
    try:
        from huggingface_hub import try_to_load_from_cache  # type: ignore[import-untyped]
        cached = try_to_load_from_cache(
            LinguaCompressor.HF_MODEL_ID, "config.json"
        )
        if isinstance(cached, str):
            model_cached = True
            model_path = cached
    except Exception:
        pass
    
    lingua_info["downloaded"] = model_cached
    lingua_info["model_path"] = model_path
    lingua_info["hf_repo_id"] = LinguaCompressor.HF_MODEL_ID

    # LOD is always available (pure Python, no external deps)
    lod_info = {"available": True, "type": "lod"}

    return ok({
        "lingua": lingua_info,
        "lod": lod_info,
    })


@router.post("/compression/download")
def compression_download() -> Dict[str, Any]:
    """Download the LLMLingua-2 compression model from HuggingFace Hub.

    The model is cached in the standard HF cache directory (~/.cache/huggingface/).
    This is a blocking call — the download happens synchronously.
    Only requires huggingface_hub (not llmlingua) to download.
    """
    from codrag.core import LinguaCompressor

    try:
        from huggingface_hub import snapshot_download  # type: ignore[import-untyped]
    except ImportError:
        raise ApiException(
            status_code=400,
            code="HF_HUB_MISSING",
            message="huggingface_hub is not installed",
            hint="pip install huggingface-hub",
        )

    try:
        model_path = snapshot_download(
            repo_id=LinguaCompressor.HF_MODEL_ID,
            allow_patterns=["*.json", "*.bin", "*.safetensors", "*.txt"],
        )
    except Exception as e:
        raise ApiException(
            status_code=500,
            code="DOWNLOAD_FAILED",
            message=f"Model download failed: {e}",
            hint="Check your internet connection and try again.",
        )

    return ok({
        "status": "downloaded",
        "model_path": model_path,
        "hf_repo_id": LinguaCompressor.HF_MODEL_ID,
    })


# ═════════════════════════════════════════════════════════════════
# LLM Slots & Status
# ═════════════════════════════════════════════════════════════════

@router.get("/llm/slots/status")
def get_llm_slots_status() -> Dict[str, Any]:
    """Check connectivity for all configured model slots (embedding, small, large, code).
    
    Returns per-slot status with endpoint reachability and model availability.
    """
    from codrag.server import _load_ui_config
    ui_cfg = _load_ui_config()
    llm_cfg = ui_cfg.get("llm_config") or {}
    endpoints = llm_cfg.get("saved_endpoints") or []
    ep_map = {e["id"]: e for e in endpoints if isinstance(e, dict) and e.get("id")}

    def _check_slot(slot_key: str) -> Dict[str, Any]:
        slot_cfg = llm_cfg.get(slot_key) or {}
        if not isinstance(slot_cfg, dict):
            return {"configured": False, "status": "not_configured"}

        ep_id = slot_cfg.get("endpoint_id") or ""
        model = slot_cfg.get("model") or ""
        enabled = bool(slot_cfg.get("enabled", False))

        if not ep_id or not model:
            return {"configured": False, "status": "not_configured"}

        ep = ep_map.get(ep_id)
        if not ep:
            return {
                "configured": True, "enabled": enabled, "model": model,
                "endpoint_id": ep_id, "status": "endpoint_missing",
                "error": f"Endpoint '{ep_id}' not found in saved endpoints",
            }

        url = str(ep.get("url", "")).rstrip("/")
        provider = ep.get("provider", "ollama")

        try:
            if provider == "ollama":
                r = requests.get(f"{url}/api/tags", timeout=3)
                reachable = r.status_code == 200
                model_found = False
                if reachable:
                    tags = r.json().get("models", []) if isinstance(r.json(), dict) else []
                    model_found = any(
                        str(m.get("name", "")).startswith(model.split(":")[0])
                        for m in tags if isinstance(m, dict)
                    )
            else:
                r = requests.get(f"{url}/models", timeout=3, headers={
                    "Authorization": f"Bearer {ep.get('api_key', '')}",
                })
                reachable = r.status_code in (200, 401)
                model_found = r.status_code == 200
        except Exception as e:
            return {
                "configured": True, "enabled": enabled, "model": model,
                "endpoint_id": ep_id, "endpoint_url": url, "provider": provider,
                "status": "unreachable", "error": str(e),
            }

        if not reachable:
            return {
                "configured": True, "enabled": enabled, "model": model,
                "endpoint_id": ep_id, "endpoint_url": url, "provider": provider,
                "status": "unreachable", "error": "Endpoint did not respond",
            }

        return {
            "configured": True, "enabled": enabled, "model": model,
            "endpoint_id": ep_id, "endpoint_url": url, "provider": provider,
            "status": "connected" if model_found else "connected_no_model",
            "model_available": model_found,
        }

    # Check embedding separately (it has a different config shape)
    emb_cfg = llm_cfg.get("embedding") or {}
    emb_source = emb_cfg.get("source", "")
    if emb_source == "endpoint":
        emb_status = _check_slot("embedding")
        if not emb_status.get("configured"):
            ep_id = emb_cfg.get("endpoint_id", "")
            model = emb_cfg.get("model", "")
            if ep_id and model:
                ep = ep_map.get(ep_id)
                url = str((ep or {}).get("url", "")).rstrip("/") if ep else ""
                try:
                    r = requests.get(f"{url}/api/tags", timeout=3)
                    emb_status = {
                        "configured": True, "enabled": True, "model": model,
                        "endpoint_id": ep_id, "endpoint_url": url,
                        "status": "connected" if r.status_code == 200 else "unreachable",
                    }
                except Exception as e:
                    emb_status = {
                        "configured": True, "enabled": True, "model": model,
                        "endpoint_id": ep_id, "endpoint_url": url,
                        "status": "unreachable", "error": str(e),
                    }
    elif emb_source == "huggingface":
        emb_status = {"configured": True, "enabled": True, "source": "huggingface", "status": "local"}
    else:
        emb_status = {"configured": False, "status": "not_configured"}

    return ok({
        "embedding": emb_status,
        "small_model": _check_slot("small_model"),
        "large_model": _check_slot("large_model"),
        "code_model": _check_slot("code_model"),
    })


@router.get("/llm/status")
@router.get("/api/llm/status")
def get_llm_status() -> Dict[str, Any]:
    from codrag.server import _config, _load_ui_config
    ollama_url = str(_config.get("ollama_url") or "http://localhost:11434").rstrip("/")
    connected = False
    models: List[str] = []
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=2)
        if r.status_code == 200:
            payload = r.json()
            raw_models = payload.get("models") if isinstance(payload, dict) else None
            if isinstance(raw_models, list):
                for m in raw_models:
                    if isinstance(m, dict) and m.get("name"):
                        models.append(str(m.get("name")))
            connected = True
    except Exception:
        connected = False
        models = []

    ui_cfg = _load_ui_config()

    return ok(
        {
            "ollama": {"url": ollama_url, "connected": connected, "models": models},
        }
    )


# ═════════════════════════════════════════════════════════════════
# LLM Testing & Proxy
# ═════════════════════════════════════════════════════════════════

@router.post("/llm/test")
@router.post("/api/llm/test")
def test_llm() -> Dict[str, Any]:
    from codrag.server import _config, _load_ui_config
    ollama_url = str(_config.get("ollama_url") or "http://localhost:11434").rstrip("/")
    ollama_connected = False
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=2)
        if r.status_code == 200:
            ollama_connected = True
    except Exception:
        ollama_connected = False

    ui_cfg = _load_ui_config()

    return ok(
        {
            "ollama": {"connected": ollama_connected},
        }
    )


@router.post("/api/llm/proxy/models")
def proxy_models(req: LLMProxyRequest) -> Dict[str, Any]:
    url = req.url.rstrip("/")
    models: List[str] = []
    
    try:
        if req.provider == "ollama":
            r = requests.get(f"{url}/api/tags", timeout=5)
            if r.status_code == 200:
                data = r.json()
                for m in data.get("models", []):
                    if isinstance(m, dict) and "name" in m:
                        models.append(m["name"])
        
        elif req.provider in ("openai", "openai-compatible", "anthropic"):
            headers = {}
            if req.api_key:
                headers["Authorization"] = f"Bearer {req.api_key}"
            
            target = f"{url}/models"
            if "v1" not in url and req.provider != "anthropic":
                 target = f"{url}/v1/models"
            
            r = requests.get(target, headers=headers, timeout=5)
            if r.status_code == 200:
                data = r.json()
                for m in data.get("data", []):
                    if isinstance(m, dict) and "id" in m:
                        models.append(m["id"])
                        
    except Exception as e:
        raise ApiException(status_code=500, code="CONNECTION_FAILED", message=str(e))

    return ok({"models": models})


@router.post("/api/llm/proxy/test")
def proxy_test(req: LLMProxyRequest) -> Dict[str, Any]:
    url = req.url.rstrip("/")
    if not is_safe_url(url, req.provider):
        return ok({"success": False, "message": "Invalid or unsafe URL scheme", "models": []})

    success = False
    message = ""
    models: List[str] = []

    try:
        if req.provider == "ollama":
            r = requests.get(f"{url}/api/tags", timeout=5)
            if r.status_code == 200:
                success = True
                data = r.json()
                models = [m["name"] for m in data.get("models", []) if "name" in m]
                message = f"Connected to Ollama v{r.headers.get('version', 'unknown')}"
            else:
                message = f"HTTP {r.status_code}: {r.text[:100]}"
        
        else:
            headers = {}
            if req.api_key:
                headers["Authorization"] = f"Bearer {req.api_key}"
            
            target = f"{url}/models"
            if "v1" not in url and req.provider != "anthropic":
                 target = f"{url}/v1/models"

            r = requests.get(target, headers=headers, timeout=5)
            if r.status_code == 200:
                success = True
                data = r.json()
                models = [m.get("id") for m in data.get("data", []) if "id" in m]
                message = "Connected successfully"
            else:
                message = f"HTTP {r.status_code}: {r.text[:100]}"

    except Exception as e:
        message = str(e)

    return ok({"success": success, "message": message, "models": models})


@router.post("/api/llm/model-status")
def model_status_endpoint(req: ModelStatusRequest) -> Dict[str, Any]:
    """Check model readiness status, optionally triggering preload.

    When ``ensure_ready`` is True the server will attempt to preload
    the model and block until it is ready (up to ``timeout_s``).
    """
    url = req.url.rstrip("/")
    if req.ensure_ready:
        result = ensure_model_ready(
            provider=req.provider,
            url=url,
            model=req.model,
            api_key=req.api_key,
            timeout_s=req.timeout_s,
        )
    else:
        result = get_model_status(
            provider=req.provider,
            url=url,
            model=req.model,
            api_key=req.api_key,
        )
    return ok(result.to_dict())


@router.post("/api/llm/proxy/test-model")
def proxy_test_model(req: LLMModelTestRequest) -> Dict[str, Any]:
    """Test a specific model with readiness-aware logic.

    For Ollama models: checks if model is loaded via ``/api/ps`` first.
    If not loaded, preloads it (up to 120 s) before sending the actual
    test request.  This prevents false "timed out" errors caused by
    cold-start model loading.
    """
    url = req.url.rstrip("/")
    if not is_safe_url(url, req.provider):
        return ok({"success": False, "message": "Invalid or unsafe URL scheme", "model_status": "unknown"})

    success = False
    message = ""
    model_status_str = "unknown"
    
    try:
        if req.provider == "ollama":
            if req.kind == "embedding":
                readiness = get_model_status(
                    provider="ollama", url=url, model=req.model,
                )
                model_status_str = readiness.status.value

                if readiness.status in (ModelStatus.NOT_FOUND, ModelStatus.ERROR):
                    message = readiness.message
                    return ok({
                        "success": False,
                        "message": message,
                        "model_status": model_status_str,
                    })

                try:
                    r = requests.post(
                        f"{url}/api/embeddings",
                        json={"model": req.model, "prompt": "Test embedding"},
                        timeout=120,
                    )
                    if r.status_code == 200:
                        success = True
                        load_info = ""
                        try:
                            resp_data = r.json()
                            load_ns = resp_data.get("load_duration", 0)
                            if load_ns > 0:
                                load_info = f" (load: {load_ns / 1e9:.1f}s)"
                        except Exception:
                            pass
                        message = f"Model responded successfully{load_info}"
                        model_status_str = ModelStatus.READY.value
                    else:
                        message = f"HTTP {r.status_code}: {r.text[:100]}"
                except requests.Timeout:
                    message = f"Model '{req.model}' timed out (may still be loading)"
                    model_status_str = ModelStatus.LOADING.value
            else:
                readiness = ensure_model_ready(
                    provider="ollama",
                    url=url,
                    model=req.model,
                    timeout_s=120,
                )
                model_status_str = readiness.status.value

                if readiness.status == ModelStatus.NOT_FOUND:
                    message = readiness.message
                    return ok({
                        "success": False,
                        "message": message,
                        "model_status": model_status_str,
                    })

                if readiness.status == ModelStatus.LOADING:
                    message = readiness.message
                    return ok({
                        "success": False,
                        "message": message,
                        "model_status": model_status_str,
                    })

                try:
                    r = requests.post(
                        f"{url}/api/generate",
                        json={"model": req.model, "prompt": "Hi", "stream": False},
                        timeout=30,
                    )

                    if r.status_code == 200:
                        success = True
                        load_info = ""
                        try:
                            resp_data = r.json()
                            load_ns = resp_data.get("load_duration", 0)
                            if load_ns > 0:
                                load_info = f" (load: {load_ns / 1e9:.1f}s)"
                        except Exception:
                            pass
                        message = f"Model responded successfully{load_info}"
                        model_status_str = ModelStatus.READY.value
                    else:
                        try:
                            err_data = r.json()
                            ollama_err = err_data.get("error", "")
                        except Exception:
                            ollama_err = ""
                        if ollama_err:
                            message = f"Ollama error: {ollama_err}"
                        else:
                            message = f"HTTP {r.status_code}: {r.text[:200]}"
                except requests.Timeout:
                    message = f"Model '{req.model}' timed out (may still be loading)"
                    model_status_str = ModelStatus.LOADING.value
                
        elif req.provider in ("openai", "openai-compatible"):
            headers = {}
            if req.api_key:
                headers["Authorization"] = f"Bearer {req.api_key}"
            
            base = url if "v1" in url else f"{url}/v1"
            
            if req.kind == "embedding":
                r = requests.post(
                    f"{base}/embeddings",
                    headers=headers,
                    json={"model": req.model, "input": "Test"},
                    timeout=30,
                )
            else:
                r = requests.post(
                    f"{base}/chat/completions",
                    headers=headers,
                    json={
                        "model": req.model, 
                        "messages": [{"role": "user", "content": "Hi"}],
                        "max_tokens": 5
                    },
                    timeout=30,
                )
                
            if r.status_code == 200:
                success = True
                message = "Model responded successfully"
                model_status_str = ModelStatus.READY.value
            else:
                message = f"HTTP {r.status_code}: {r.text[:100]}"

    except requests.Timeout:
        message = "Request timed out — model may still be loading. Try again in a moment."
        model_status_str = ModelStatus.LOADING.value
    except Exception as e:
        message = str(e)

    return ok({"success": success, "message": message, "model_status": model_status_str})
