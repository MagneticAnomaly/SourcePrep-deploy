"""
Configuration management for clara-server.

Supports environment variables and .env files for flexible deployment.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Backend(str, Enum):
    """Supported compute backends."""
    AUTO = "auto"
    CUDA = "cuda"
    MPS = "mps"
    MLX = "mlx"
    CPU = "cpu"


class CompressionLevel(str, Enum):
    """CLaRa compression levels."""
    COMPRESSION_16 = "compression-16"
    COMPRESSION_128 = "compression-128"


class Settings(BaseSettings):
    """
    Server configuration.
    
    All settings can be overridden via environment variables prefixed with CLARA_.
    Example: CLARA_PORT=9000 clara-server
    """
    
    # Model settings
    model: str = Field(
        default="apple/CLaRa-7B-Instruct",
        description="HuggingFace model ID or local path"
    )
    subfolder: str = Field(
        default="compression-16",
        description="Model subfolder (compression-16 or compression-128)"
    )
    cache_dir: Path = Field(
        default=Path.home() / ".cache" / "clara-server",
        description="Directory for model cache"
    )
    
    # Server settings
    host: str = Field(default="0.0.0.0", description="Bind address")
    port: int = Field(default=8765, description="Server port")
    workers: int = Field(default=1, description="Number of worker processes")
    reload: bool = Field(default=False, description="Enable auto-reload for development")
    
    # Backend settings
    backend: Backend = Field(
        default=Backend.AUTO,
        description="Compute backend (auto, cuda, mps, mlx, cpu)"
    )
    device_id: int = Field(default=0, description="GPU device ID for CUDA")
    
    # Inference settings
    max_new_tokens: int = Field(default=128, description="Default max tokens for generation")
    batch_size: int = Field(default=1, description="Batch size for inference")
    
    # Auto-unload settings (Ollama-style memory management)
    keep_alive: int = Field(
        default=300,  # 5 minutes like Ollama default
        description="Seconds to keep model loaded after last request. 0=immediate unload, -1=never unload"
    )
    
    # Security settings (optional)
    api_key: Optional[str] = Field(default=None, description="API key for authentication")
    rate_limit: Optional[int] = Field(default=None, description="Requests per minute per IP")
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    class Config:
        env_prefix = "CLARA_"
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    def get_cache_path(self) -> Path:
        """Get full cache path including model name."""
        safe_name = self.model.replace("/", "_")
        return self.cache_dir / f"{safe_name}_{self.subfolder}"
    
    def detect_backend(self) -> str:
        """Auto-detect the best available backend."""
        if self.backend != Backend.AUTO:
            return self.backend.value
        
        # Try CUDA first
        try:
            import torch
            if torch.cuda.is_available():
                return Backend.CUDA.value
        except ImportError:
            pass
        
        # Try MPS (Apple Silicon via PyTorch)
        try:
            import torch
            if torch.backends.mps.is_available():
                return Backend.MPS.value
        except (ImportError, AttributeError):
            pass
        
        # Try MLX (native Apple Silicon)
        try:
            import mlx.core
            return Backend.MLX.value
        except ImportError:
            pass
        
        # Fall back to CPU
        return Backend.CPU.value


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def override_settings(**kwargs) -> Settings:
    """Override settings (useful for testing)."""
    global _settings
    _settings = Settings(**kwargs)
    return _settings
