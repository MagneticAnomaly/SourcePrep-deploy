"""Configuration module — Settings class and config loading."""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class Settings:
    """Application settings loaded from environment variables or defaults.

    Attributes:
        database_url: Path or URL to the database.
        secret_key: Secret key for token signing.
        debug: Enable debug mode.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        max_connections: Maximum database connection pool size.
        token_expiry: Token expiry in seconds.
        cache_size: Maximum items in the LRU cache.
        allowed_origins: CORS allowed origins.
    """

    database_url: str = "sqlite:///app.db"
    secret_key: str = "change-me-in-production"
    debug: bool = False
    log_level: str = "INFO"
    max_connections: int = 5
    token_expiry: int = 3600
    cache_size: int = 256
    allowed_origins: list = field(default_factory=lambda: ["http://localhost:3000"])


def load_config(env_prefix: str = "APP_") -> Settings:
    """Load configuration from environment variables.

    Environment variables are mapped by prefix + field name in uppercase.
    For example, APP_DATABASE_URL maps to Settings.database_url.

    Args:
        env_prefix: Prefix for environment variable names.

    Returns:
        A Settings instance with values from environment or defaults.
    """
    kwargs: Dict[str, Any] = {}

    env_map = {
        "database_url": str,
        "secret_key": str,
        "debug": lambda v: v.lower() in ("1", "true", "yes"),
        "log_level": str,
        "max_connections": int,
        "token_expiry": int,
        "cache_size": int,
    }

    for field_name, converter in env_map.items():
        env_key = f"{env_prefix}{field_name.upper()}"
        value = os.environ.get(env_key)
        if value is not None:
            try:
                kwargs[field_name] = converter(value)
            except (ValueError, TypeError):
                pass

    origins_key = f"{env_prefix}ALLOWED_ORIGINS"
    origins = os.environ.get(origins_key)
    if origins:
        kwargs["allowed_origins"] = [o.strip() for o in origins.split(",")]

    return Settings(**kwargs)


def validate_config(settings: Settings) -> Optional[str]:
    """Validate configuration settings.

    Returns an error message if invalid, None if valid.
    """
    if settings.secret_key == "change-me-in-production" and not settings.debug:
        return "Secret key must be changed in production mode"

    if settings.max_connections < 1:
        return "max_connections must be at least 1"

    if settings.token_expiry < 60:
        return "token_expiry must be at least 60 seconds"

    if settings.cache_size < 1:
        return "cache_size must be at least 1"

    return None
