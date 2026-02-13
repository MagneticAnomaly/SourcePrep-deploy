"""
CLaRa model loading and inference.

Supports multiple backends:
- CUDA: NVIDIA GPUs via PyTorch
- MPS: Apple Silicon via PyTorch
- MLX: Apple Silicon native (coming soon)
- CPU: Fallback for any platform
"""

import logging
import threading
import time
import gc
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from clara_server.config import Backend, Settings, get_settings

logger = logging.getLogger(__name__)


class BaseModelBackend(ABC):
    """Abstract base class for model backends."""
    
    @abstractmethod
    def load(self, model_path: str, settings: Settings) -> None:
        """Load the model."""
        pass
    
    @abstractmethod
    def generate(
        self,
        memories: List[str],
        query: str,
        max_new_tokens: int = 128,
    ) -> str:
        """Generate answer from compressed memories."""
        pass
    
    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        pass
    
    @abstractmethod
    def unload(self) -> None:
        """Unload model and free resources."""
        pass
    
    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """Get backend info for status endpoint."""
        pass


class PyTorchBackend(BaseModelBackend):
    """PyTorch backend supporting CUDA and MPS."""
    
    def __init__(self, device: str = "auto"):
        self._model = None
        self._device = device
        self._actual_device = None
        self._dtype = None
        self._load_time = None
        self._torch_device = None  # torch.device object for patching
    
    def load(self, model_path: str, settings: Settings) -> None:
        """Load CLaRa model using PyTorch/Transformers."""
        import torch
        from huggingface_hub import snapshot_download
        from transformers import AutoModel
        
        start = time.time()
        
        # Determine device
        if self._device == "auto":
            self._device = settings.detect_backend()
        
        if self._device == Backend.CUDA.value:
            self._actual_device = f"cuda:{settings.device_id}"
            self._dtype = torch.float16
        elif self._device == Backend.MPS.value:
            self._actual_device = "mps"
            self._dtype = torch.float16
        else:
            self._actual_device = "cpu"
            self._dtype = torch.float32
        
        logger.info(f"Using device: {self._actual_device}, dtype: {self._dtype}")
        
        # Download model if needed
        cache_dir = settings.cache_dir / "hf_download"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Downloading/loading {settings.model}...")
        local_dir = snapshot_download(
            repo_id=settings.model,
            local_dir=str(cache_dir),
        )
        
        # Load from subfolder (CLaRa requires this structure)
        full_model_path = f"{local_dir}/{settings.subfolder}"
        logger.info(f"Loading model from {full_model_path}")
        
        self._model = AutoModel.from_pretrained(
            full_model_path,
            trust_remote_code=True,
            torch_dtype=self._dtype,
            device_map="auto" if self._actual_device.startswith("cuda") else None,
        )
        
        # Move to device if not using device_map
        if not self._actual_device.startswith("cuda"):
            self._model = self._model.to(self._actual_device)
        
        # Store torch device for patching hardcoded .to('cuda') calls in CLaRa model
        self._torch_device = torch.device(self._actual_device)
        
        # Patch the model's compress method to use correct device
        # Apple's CLaRa model has hardcoded .to('cuda') calls that break on MPS/CPU
        self._patch_clara_device()
        
        self._load_time = time.time() - start
        logger.info(f"Model loaded in {self._load_time:.1f}s")
    
    def generate(
        self,
        memories: List[str],
        query: str,
        max_new_tokens: int = 128,
    ) -> str:
        """Generate answer using CLaRa's generate_from_text method."""
        import torch
        
        if self._model is None:
            raise RuntimeError("Model not loaded")
        
        with torch.no_grad():
            output = self._model.generate_from_text(
                questions=[query],
                documents=[memories],
                max_new_tokens=max_new_tokens,
            )
        
        return output[0] if output else ""
    
    def _patch_clara_device(self) -> None:
        """
        Patch CLaRa model's hardcoded CUDA device calls.
        
        Apple's CLaRa model code on HuggingFace has hardcoded .to('cuda') calls
        in the compress method. This patches torch.Tensor.to() to intercept
        and redirect those calls to the correct device (MPS/CPU).
        """
        import torch
        
        if self._model is None or self._torch_device is None:
            return
        
        target_device = self._torch_device
        
        # Skip patching if we're actually on CUDA
        if str(target_device).startswith('cuda'):
            return
        
        # Monkey-patch torch.Tensor.to to intercept 'cuda' -> actual device
        # This fixes any hardcoded .to('cuda') in the CLaRa model code
        original_to = torch.Tensor.to
        
        def patched_to(tensor_self, *args, **kwargs):
            # Intercept .to('cuda') calls and redirect to target device
            if args:
                first_arg = args[0]
                if isinstance(first_arg, str) and first_arg == 'cuda':
                    args = (target_device,) + args[1:]
                elif isinstance(first_arg, torch.device) and first_arg.type == 'cuda':
                    args = (target_device,) + args[1:]
            if 'device' in kwargs:
                dev = kwargs['device']
                if dev == 'cuda' or (isinstance(dev, torch.device) and dev.type == 'cuda'):
                    kwargs['device'] = target_device
            return original_to(tensor_self, *args, **kwargs)
        
        torch.Tensor.to = patched_to
        logger.info(f"Installed tensor.to() patch: 'cuda' -> {target_device}")
    
    def is_loaded(self) -> bool:
        return self._model is not None
    
    def unload(self) -> None:
        """Unload model and free GPU memory."""
        if self._model is not None:
            del self._model
            self._model = None
            
            # Clear CUDA/MPS cache and run GC
            try:
                gc.collect()
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    torch.mps.empty_cache()
            except Exception:
                pass
            
            logger.info("Model unloaded")
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "backend": "pytorch",
            "device": self._actual_device,
            "dtype": str(self._dtype),
            "load_time_seconds": self._load_time,
        }


class MLXBackend(BaseModelBackend):
    """
    MLX backend for native Apple Silicon support.
    
    Status: Placeholder for future implementation.
    MLX provides better memory efficiency and performance on Apple Silicon.
    """
    
    def __init__(self):
        self._model = None
        self._load_time = None
    
    def load(self, model_path: str, settings: Settings) -> None:
        """Load CLaRa model using MLX."""
        # TODO: Implement MLX loading when CLaRa MLX weights are available
        # This will require either:
        # 1. Converting PyTorch weights to MLX format
        # 2. Apple releasing MLX-native weights
        raise NotImplementedError(
            "MLX backend is not yet implemented. "
            "CLaRa requires custom model code that needs MLX porting. "
            "Use 'mps' backend for Apple Silicon via PyTorch."
        )
    
    def generate(
        self,
        memories: List[str],
        query: str,
        max_new_tokens: int = 128,
    ) -> str:
        raise NotImplementedError("MLX backend not implemented")
    
    def is_loaded(self) -> bool:
        return self._model is not None
    
    def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "backend": "mlx",
            "status": "not_implemented",
            "load_time_seconds": self._load_time,
        }


class ClaraModel:
    """
    High-level CLaRa model wrapper.
    
    Automatically selects the best backend and provides a unified interface.
    Implements Ollama-style auto-unload to free RAM when idle.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._backend: Optional[BaseModelBackend] = None
        self._stats = {
            "requests": 0,
            "total_latency": 0.0,
            "errors": 0,
        }
        
        # Auto-unload state (Ollama-style)
        self._last_activity: Optional[float] = None
        self._unload_timer: Optional[threading.Timer] = None
        self._current_keep_alive: int = self.settings.keep_alive
        self._lock = threading.RLock()
    
    def load(self) -> None:
        """Load the model using the configured backend."""
        with self._lock:
            if self.is_loaded():
                logger.debug("Model already loaded")
                return
            
            backend_name = self.settings.detect_backend()
            logger.info(f"Initializing {backend_name} backend")
            
            if backend_name == Backend.MLX.value:
                self._backend = MLXBackend()
            else:
                self._backend = PyTorchBackend(device=backend_name)
            
            self._backend.load(self.settings.model, self.settings)
            self._update_activity()
    
    def compress(
        self,
        memories: List[str],
        query: str,
        max_new_tokens: Optional[int] = None,
        keep_alive: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Compress memories and generate answer.
        
        Automatically loads model if not loaded (lazy loading).
        Resets keep_alive timer after each request.
        
        Args:
            memories: List of memory strings to compress
            query: Question to answer from compressed context
            max_new_tokens: Maximum tokens in response
            keep_alive: Optional override for keep-alive duration
        
        Returns:
            Dict with success, answer, token counts, compression ratio, latency
        """
        # Lazy load if not loaded (Ollama-style)
        if not self.is_loaded():
            logger.info("Model not loaded, loading on demand...")
            try:
                self.load()
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                return {
                    "success": False,
                    "error": f"Failed to load model: {e}",
                    "answer": None,
                }
        
        if self._backend is None or not self._backend.is_loaded():
            return {
                "success": False,
                "error": "Model not loaded",
                "answer": None,
            }
        
        max_tokens = max_new_tokens or self.settings.max_new_tokens
        start = time.time()
        
        try:
            answer = self._backend.generate(memories, query, max_tokens)
            
            # Estimate token counts (rough approximation)
            original_tokens = sum(len(m.split()) * 1.3 for m in memories)
            compressed_tokens = original_tokens / 16  # CLaRa achieves ~16x compression
            
            latency = (time.time() - start) * 1000
            self._stats["requests"] += 1
            self._stats["total_latency"] += latency
            
            # Update activity and schedule unload timer
            self._update_activity(keep_alive)
            
            return {
                "success": True,
                "answer": answer,
                "original_tokens": int(original_tokens),
                "compressed_tokens": int(compressed_tokens),
                "compression_ratio": round(original_tokens / max(1, compressed_tokens), 1),
                "latency_ms": round(latency, 1),
            }
        
        except Exception as e:
            logger.exception("Compression failed")
            self._stats["errors"] += 1
            # Still update activity on error to prevent immediate unload
            self._update_activity(keep_alive)
            return {
                "success": False,
                "error": str(e),
                "answer": None,
            }
    
    def _update_activity(self, keep_alive: Optional[int] = None) -> None:
        """Update last activity time and schedule auto-unload."""
        self._last_activity = time.time()
        self._schedule_unload(keep_alive)
    
    def _schedule_unload(self, keep_alive: Optional[int] = None) -> None:
        """Schedule model unload based on keep_alive setting."""
        # Cancel any existing timer
        if self._unload_timer is not None:
            self._unload_timer.cancel()
            self._unload_timer = None
        
        if keep_alive is not None:
            self._current_keep_alive = keep_alive
        else:
            self._current_keep_alive = self.settings.keep_alive
            
        keep_alive = self._current_keep_alive
        
        # -1 means never unload
        if keep_alive < 0:
            return
        
        # 0 means immediate unload after request
        if keep_alive == 0:
            logger.info("keep_alive=0, unloading immediately")
            self.unload()
            return
        
        # Schedule unload after keep_alive seconds
        self._unload_timer = threading.Timer(keep_alive, self._auto_unload)
        self._unload_timer.daemon = True
        self._unload_timer.start()
        logger.debug(f"Scheduled auto-unload in {keep_alive}s")
    
    def _auto_unload(self) -> None:
        """Auto-unload callback - only unload if still idle."""
        with self._lock:
            if self._last_activity is None:
                return
            
            elapsed = time.time() - self._last_activity
            keep_alive = self._current_keep_alive
            
            if elapsed >= keep_alive:
                logger.info(f"Auto-unloading model after {elapsed:.0f}s idle (keep_alive={keep_alive}s)")
                self._do_unload()
    
    def _do_unload(self) -> None:
        """Internal unload without lock (called from locked context)."""
        if self._backend is not None:
            self._backend.unload()
            self._backend = None
        self._last_activity = None
        if self._unload_timer is not None:
            self._unload_timer.cancel()
            self._unload_timer = None
    
    def unload(self) -> None:
        """Unload model and free resources."""
        with self._lock:
            self._do_unload()
    
    def is_loaded(self) -> bool:
        """Check if model is loaded and ready."""
        return self._backend is not None and self._backend.is_loaded()
    
    def get_status(self) -> Dict[str, Any]:
        """Get model status for API endpoint."""
        backend_info = self._backend.get_info() if self._backend and self._backend.is_loaded() else {}
        
        # Calculate unload timing
        keep_alive = self._current_keep_alive
        last_activity_iso = None
        will_unload_at_iso = None
        seconds_until_unload = None
        
        if self._last_activity is not None:
            last_activity_iso = datetime.fromtimestamp(
                self._last_activity, tz=timezone.utc
            ).isoformat()
            
            if keep_alive > 0:
                unload_at = self._last_activity + keep_alive
                will_unload_at_iso = datetime.fromtimestamp(
                    unload_at, tz=timezone.utc
                ).isoformat()
                seconds_until_unload = max(0, int(unload_at - time.time()))
        
        return {
            "model": self.settings.model,
            "subfolder": self.settings.subfolder,
            "initialized": self.is_loaded(),
            **backend_info,
            "requests_served": self._stats["requests"],
            "errors": self._stats["errors"],
            "avg_latency_ms": (
                self._stats["total_latency"] / max(1, self._stats["requests"])
            ),
            # Auto-unload info (Ollama-style)
            "keep_alive_seconds": keep_alive,
            "last_activity": last_activity_iso,
            "will_unload_at": will_unload_at_iso,
            "seconds_until_unload": seconds_until_unload,
        }


# Global model instance
_model: Optional[ClaraModel] = None


def get_model() -> ClaraModel:
    """Get or create global model instance."""
    global _model
    if _model is None:
        _model = ClaraModel()
    return _model


def load_model() -> ClaraModel:
    """Load the global model instance."""
    model = get_model()
    if not model.is_loaded():
        model.load()
    return model
