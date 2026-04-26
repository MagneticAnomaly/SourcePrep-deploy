"""Best-effort probe of an Ollama daemon's parallel-request capacity.

Phase 119: when configuring a new cloud:* slot for an Ollama-proxied
endpoint with no persisted ceiling, we'd like a smarter seed than the
Phase 82 default of 5. Read OLLAMA_NUM_PARALLEL from the environment
first; fall back to GET /api/ps and count loaded models; finally
default to 5.
"""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

_DEFAULT = 5
_HARD_CAP = 256


def probe_ollama_concurrency(host: str, timeout: float = 1.5) -> int:
    """Return a sensible seed for a new cloud-via-Ollama slot.

    Order of precedence:
      1. OLLAMA_NUM_PARALLEL env var (if a positive int).
      2. GET <host>/api/ps — count of currently-loaded models.
      3. Default seed (5).

    Result is in [1, 256]: positive sources are capped at 256; non-positive
    or missing sources fall through to the default seed (5). Network/parse
    errors are swallowed and treated as missing.
    """
    env = os.getenv("OLLAMA_NUM_PARALLEL")
    if env:
        try:
            n = int(env)
            if n > 0:
                return min(n, _HARD_CAP)
        except ValueError:
            logger.debug("OLLAMA_NUM_PARALLEL=%r is not an int; falling back", env)

    host = host.rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"
    try:
        resp = requests.get(f"{host}/api/ps", timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            count = len(data.get("models") or [])
            if count > 0:
                return min(count, _HARD_CAP)
    except Exception as exc:
        logger.debug("Ollama probe failed for %s: %s", host, exc)

    return _DEFAULT
