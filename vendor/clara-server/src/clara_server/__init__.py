"""
CLaRa-Remembers-It-All: Production-ready inference server for Apple's CLaRa context compression model.

"Because CLaRa remembers it all... in 16x less space."

This package provides a FastAPI-based REST API for CLaRa inference,
supporting multiple backends (CUDA, MPS, MLX, CPU) for universal deployment.
"""

__version__ = "0.1.0"
__author__ = "CLaRa-Remembers-It-All Contributors"
__license__ = "Apache-2.0"

from clara_server.server import app, create_app
from clara_server.model import ClaraModel
from clara_server.config import Settings

__all__ = ["app", "create_app", "ClaraModel", "Settings", "__version__"]
