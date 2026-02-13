"""
FastAPI server for CLaRa inference.

Provides REST API endpoints for context compression.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from clara_server.config import Settings, get_settings
from clara_server.model import ClaraModel, get_model, load_model

logger = logging.getLogger(__name__)

# Track server start time
_start_time: Optional[float] = None


# Request/Response Models
class CompressRequest(BaseModel):
    """Request body for /compress endpoint."""
    memories: List[str] = Field(
        ...,
        description="List of memory strings to compress",
        min_length=1,
        examples=[["User likes hiking.", "User has a dog named Max."]]
    )
    query: str = Field(
        ...,
        description="Question to answer from compressed memories",
        min_length=1,
        examples=["What activities does the user enjoy?"]
    )
    max_new_tokens: int = Field(
        default=128,
        description="Maximum tokens in response",
        ge=1,
        le=512
    )
    keep_alive: Optional[int] = Field(
        default=None,
        description="Seconds to keep model loaded after request (overrides default). 0=immediate unload, -1=never unload."
    )


class CompressResponse(BaseModel):
    """Response body for /compress endpoint."""
    success: bool
    answer: Optional[str] = None
    error: Optional[str] = None
    original_tokens: int = 0
    compressed_tokens: int = 0
    compression_ratio: float = 0
    latency_ms: float = 0


class StatusResponse(BaseModel):
    """Response body for /status endpoint."""
    model: str
    subfolder: str
    initialized: bool
    backend: Optional[str] = None
    device: Optional[str] = None
    dtype: Optional[str] = None
    load_time_seconds: Optional[float] = None
    requests_served: int = 0
    errors: int = 0
    avg_latency_ms: float = 0
    uptime_seconds: int = 0
    # Auto-unload info (Ollama-style)
    keep_alive_seconds: Optional[int] = None
    last_activity: Optional[str] = None
    will_unload_at: Optional[str] = None
    seconds_until_unload: Optional[int] = None


class HealthResponse(BaseModel):
    """Response body for /health endpoint."""
    status: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - load model on startup."""
    global _start_time
    _start_time = time.time()
    
    logger.info("Starting clara-server...")
    
    try:
        load_model()
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        # Don't crash - allow health checks to report unhealthy
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down clara-server...")
    model = get_model()
    model.unload()


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Args:
        settings: Optional settings override (useful for testing)
    
    Returns:
        Configured FastAPI application
    """
    settings = settings or get_settings()
    
    app = FastAPI(
        title="clara-server",
        description="Production-ready inference server for Apple's CLaRa context compression model",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Optional API key authentication
    async def verify_api_key(request: Request):
        if settings.api_key:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(401, "Missing API key")
            token = auth_header.split(" ", 1)[1]
            if token != settings.api_key:
                raise HTTPException(403, "Invalid API key")
    
    # Health check (no auth required)
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health():
        """
        Health check endpoint.
        
        Returns 200 if server is running and model is loaded.
        Returns 503 if model failed to load.
        """
        model = get_model()
        if not model.is_loaded():
            raise HTTPException(503, "Model not loaded")
        return HealthResponse(status="ok")
    
    # Status endpoint
    @app.get("/status", response_model=StatusResponse, tags=["Status"])
    async def status():
        """
        Get server status and model information.
        
        Returns model info, backend details, and request statistics.
        """
        model = get_model()
        model_status = model.get_status()
        
        uptime = int(time.time() - _start_time) if _start_time else 0
        
        return StatusResponse(
            uptime_seconds=uptime,
            **model_status
        )
    
    # Compress endpoint (main functionality)
    @app.post(
        "/compress",
        response_model=CompressResponse,
        tags=["Compression"],
        dependencies=[Depends(verify_api_key)] if settings.api_key else [],
    )
    async def compress(request: CompressRequest):
        """
        Compress memories and generate answer.
        
        Takes a list of memory strings and a query, compresses the memories
        using CLaRa's 16x semantic compression, and generates an answer.
        
        **Example:**
        ```json
        {
            "memories": [
                "User enjoys hiking in national parks.",
                "User has visited Yellowstone and Yosemite.",
                "User prefers backcountry camping."
            ],
            "query": "What outdoor activities does the user enjoy?"
        }
        ```
        """
        model = get_model()
        
        if not model.is_loaded():
            raise HTTPException(503, "Model not loaded")
        
        result = model.compress(
            memories=request.memories,
            query=request.query,
            max_new_tokens=request.max_new_tokens,
            keep_alive=request.keep_alive,
        )
        
        return CompressResponse(**result)
    
    # Root redirect to docs
    @app.get("/", include_in_schema=False)
    async def root():
        """Redirect root to API documentation."""
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/docs")
    
    return app


# Default app instance
app = create_app()
