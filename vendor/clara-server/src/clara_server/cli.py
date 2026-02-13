"""
Command-line interface for clara-server.

Usage:
    clara-server                    # Start with defaults
    clara-server --port 9000        # Custom port
    clara-server --reload           # Development mode with auto-reload
"""

import argparse
import logging
import sys

from clara_server.config import get_settings, override_settings


def setup_logging(level: str = "INFO"):
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def main():
    """Main entry point for clara-server CLI."""
    parser = argparse.ArgumentParser(
        description="Production-ready inference server for Apple's CLaRa context compression model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    clara-server                           # Start with defaults
    clara-server --port 9000               # Custom port
    clara-server --backend cuda            # Force CUDA backend
    clara-server --reload                  # Development mode
    CLARA_MODEL=apple/CLaRa-7B-Base clara-server  # Different model

Environment Variables:
    CLARA_MODEL        HuggingFace model ID (default: apple/CLaRa-7B-Instruct)
    CLARA_SUBFOLDER    Compression level (default: compression-16)
    CLARA_PORT         Server port (default: 8765)
    CLARA_HOST         Bind address (default: 0.0.0.0)
    CLARA_BACKEND      Backend: auto, cuda, mps, mlx, cpu (default: auto)
    CLARA_KEEP_ALIVE   Seconds to keep model loaded (default: 300, -1=never)
    CLARA_API_KEY      Optional API key for authentication
    CLARA_CACHE        Model cache directory
        """,
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Bind address (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Server port (default: 8765)",
    )
    parser.add_argument(
        "--backend",
        type=str,
        choices=["auto", "cuda", "mps", "mlx", "cpu"],
        default=None,
        help="Compute backend (default: auto)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="HuggingFace model ID (default: apple/CLaRa-7B-Instruct)",
    )
    parser.add_argument(
        "--subfolder",
        type=str,
        choices=["compression-16", "compression-128"],
        default=None,
        help="Compression level (default: compression-16)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes (default: 1)",
    )
    parser.add_argument(
        "--keep-alive",
        type=int,
        default=None,
        help="Seconds to keep model loaded after request (default: 300). Use 0 for immediate unload, -1 for never unload.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # Build settings overrides from CLI args
    overrides = {}
    if args.host:
        overrides["host"] = args.host
    if args.port:
        overrides["port"] = args.port
    if args.backend:
        overrides["backend"] = args.backend
    if args.model:
        overrides["model"] = args.model
    if args.subfolder:
        overrides["subfolder"] = args.subfolder
    if args.reload:
        overrides["reload"] = args.reload
    if args.workers:
        overrides["workers"] = args.workers
    if args.keep_alive is not None:
        overrides["keep_alive"] = args.keep_alive
    overrides["log_level"] = args.log_level
    
    # Apply overrides
    if overrides:
        settings = override_settings(**overrides)
    else:
        settings = get_settings()
    
    logger.info(f"Starting clara-server v0.1.0")
    logger.info(f"Model: {settings.model}")
    logger.info(f"Subfolder: {settings.subfolder}")
    logger.info(f"Backend: {settings.backend.value}")
    keep_alive_str = "never" if settings.keep_alive < 0 else f"{settings.keep_alive}s"
    logger.info(f"Keep-alive: {keep_alive_str}")
    logger.info(f"Binding to {settings.host}:{settings.port}")
    
    # Start server
    import uvicorn
    
    uvicorn.run(
        "clara_server.server:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers if not settings.reload else 1,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
