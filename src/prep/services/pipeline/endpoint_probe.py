"""Phase 119 Phase C: manual capacity probe for cloud LLM endpoints.

The user clicks "Probe" on a saved endpoint card. We fire ``burst_size``
parallel calibrated requests against the endpoint's lightest model,
measure per-request wall-clock, and detect a saturation point on the
latency staircase. The result is persisted as a small JSON record under
``<data_dir>/probes/`` and pushed onto an in-memory ring buffer keyed
by endpoint id, so the dashboard's CapacityHealth panel can show
"Probed 2h ago — saturation 10, recommended 9".

Design constraints (from the Phase C spec):

* Live probes burn the user's API budget — keep them safe and explicit.
  ``burst_size`` is bounded to ``[1, _BURST_HARD_CAP]``; defaults to 20.
* Each individual request uses ``max_tokens=1`` and a 1-token prompt.
* The probe itself is a single explicit user action — never invoked
  automatically.

The provider-resolution logic mirrors LLMClient: read the saved endpoint
from ``llm_config.saved_endpoints``, derive provider/base_url/api_key,
pick a low-cost model heuristically (fast model from
``llm_config.small_model`` if it points at this endpoint, else a
provider-default).

This module never makes real HTTP calls in tests — its only network
helper is ``_dispatch_request`` which is monkey-patched out by the test
suite. Saturation detection runs on synthetic latency profiles in tests
to keep the contract honest without touching live APIs.
"""
from __future__ import annotations

import asyncio
import json
import logging
import statistics
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Hard caps to keep probes cheap and bounded.
_BURST_HARD_CAP = 50
_BURST_DEFAULT = 20
_REQUEST_TIMEOUT_S = 30.0
_PROBE_HISTORY_MAXLEN = 10


# ── Per-provider request shape ────────────────────────────────────


# Default lightweight model per provider when we can't infer a better one
# from the endpoint's slot config. These are intentionally the cheapest
# option each provider offers so a probe costs ~$0 per click.
_DEFAULT_LIGHT_MODEL: Dict[str, str] = {
    "ollama": "llama3.2:1b",
    "openai": "gpt-4o-mini",
    "openai-compatible": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "google": "gemini-1.5-flash",
    "azure-openai": "gpt-4o-mini",
    "lm-studio": "default",
}


@dataclass
class _RequestSample:
    """One probe request's per-call telemetry."""
    index: int
    dispatch_at: float
    complete_at: float
    duration_ms: float
    status: str  # "ok" | "error" | "timeout"
    error: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class ProbeResult:
    """The aggregate result of one probe burst, returned to the UI."""
    endpoint_id: str
    probed_at: float
    burst_size: int
    wall_clock_ms: Dict[str, float]  # p50/p90/p99
    saturation_point: Optional[int]
    saturation_method: str  # "latency_staircase" | "header" | "none"
    recommended_concurrent: Optional[int]
    successes: int
    errors: int
    histogram_path: Optional[str]
    samples: List[Dict[str, Any]] = field(default_factory=list)


# ── Provider resolution ──────────────────────────────────────────


def _resolve_endpoint(endpoint_id: str) -> Optional[Dict[str, Any]]:
    """Look up the saved endpoint by id."""
    try:
        from prep.services.settings_store import settings
        llm_config = settings.get("llm_config") or {}
    except Exception as exc:
        logger.debug("Could not load settings for probe: %s", exc)
        return None
    for ep in llm_config.get("saved_endpoints", []):
        if ep.get("id") == endpoint_id:
            return ep
    return None


def _resolve_light_model(endpoint_id: str, provider: str) -> str:
    """Pick the lightest reasonable model for a probe call.

    Prefer the user's small_model slot if it is configured to point at
    this endpoint — that's the model the user already trusts for cheap
    fast-stage work. Fall back to the provider's default light model.
    """
    try:
        from prep.services.settings_store import settings
        llm_config = settings.get("llm_config") or {}
    except Exception:
        llm_config = {}

    small = llm_config.get("small_model") or {}
    if small.get("endpoint_id") == endpoint_id and small.get("model"):
        return str(small["model"])

    return _DEFAULT_LIGHT_MODEL.get(provider, "default")


# ── Network primitive (monkey-patched in tests) ──────────────────


async def _dispatch_request(
    *,
    endpoint: Dict[str, Any],
    model: str,
    timeout_s: float,
) -> Tuple[str, Dict[str, str], Optional[str]]:
    """Make one minimal LLM call and return ``(status, headers, error)``.

    Tests monkey-patch this whole function — we never want real network
    traffic from the test suite. The production impl uses ``httpx`` and
    targets the OpenAI / Anthropic / Ollama / Gemini chat-completion
    surfaces with ``max_tokens=1`` for the cheapest possible call.

    ``status`` is ``"ok"``, ``"error"``, or ``"timeout"``.
    """
    import httpx

    provider = endpoint.get("provider", "ollama")
    base_url = (endpoint.get("url") or "").rstrip("/")
    api_key = endpoint.get("api_key") or ""

    headers: Dict[str, str] = {}
    payload: Dict[str, Any]
    method = "POST"
    url = base_url

    if provider in ("openai", "openai-compatible", "azure-openai"):
        url = f"{base_url}/chat/completions"
        if api_key:
            if provider == "azure-openai":
                headers["api-key"] = api_key
            else:
                headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ok"}],
            "max_tokens": 1,
        }
    elif provider == "anthropic":
        url = f"{base_url}/v1/messages"
        if api_key:
            headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ok"}],
            "max_tokens": 1,
        }
    elif provider == "google":
        # Gemini sends key as URL param.
        url = f"{base_url}/v1beta/models/{model}:generateContent"
        if api_key:
            url = f"{url}?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "ok"}]}],
            "generationConfig": {"maxOutputTokens": 1},
        }
    else:
        # ollama / lm-studio (OpenAI-compatible chat)
        url = f"{base_url}/api/chat" if provider == "ollama" else f"{base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ok"}],
            "stream": False,
            "options": {"num_predict": 1} if provider == "ollama" else None,
        }
        # Strip None entries — ollama tolerates them, lm-studio doesn't.
        payload = {k: v for k, v in payload.items() if v is not None}

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.request(method, url, headers=headers, json=payload)
            captured = {k.lower(): v for k, v in resp.headers.items()}
            if resp.status_code == 200:
                return "ok", captured, None
            return "error", captured, f"http {resp.status_code}"
    except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
        # httpx raises various subclasses; we treat all as errors.
        if isinstance(exc, asyncio.TimeoutError):
            return "timeout", {}, "timeout"
        return "error", {}, type(exc).__name__


# ── Saturation detection ─────────────────────────────────────────


def detect_saturation(
    samples: List[_RequestSample],
    *,
    header_hint_score: Optional[float] = None,
    header_hint_suggested_max: Optional[int] = None,
) -> Tuple[Optional[int], str]:
    """Return ``(saturation_point, method)`` for a sequence of probe samples.

    Method order of precedence:
      1. ``"header"`` — if the Phase B header parser produced a score
         ≥ 0.5 with a ``suggested_max``, use that. Headers are
         authoritative when present.
      2. ``"latency_staircase"`` — sort samples by ``dispatch_at`` and
         find the first index ``N`` (1-indexed) where the **batched p90**
         of the first ``N`` durations exceeds ``2 *`` p50 of the first
         few "calibration" samples. This catches the Ollama-style
         staircase where the first K parallel slots run unimpeded and
         the (K+1)th queues up behind a busy worker.
      3. ``"none"`` — no saturation observed within the burst.

    The saturation point is the *count of concurrent requests at which
    latency degraded*, so e.g. a return value of ``10`` means "at 10
    concurrent the endpoint started slowing down — pick 9 to stay
    below the cliff".
    """
    if header_hint_score is not None and header_hint_score >= 0.5 and header_hint_suggested_max:
        return int(header_hint_suggested_max), "header"

    successful = [s for s in samples if s.status == "ok"]
    if len(successful) < 4:
        return None, "none"

    # Sort by dispatch order for the staircase scan.
    successful.sort(key=lambda s: s.dispatch_at)
    durations = [s.duration_ms for s in successful]

    # Calibrate baseline from the *fastest* third (these are usually the
    # first slots to land — they ran un-queued).
    cal_n = max(2, len(durations) // 3)
    calibration = sorted(durations)[:cal_n]
    p50_cal = statistics.median(calibration) if calibration else 0.0
    if p50_cal <= 0:
        return None, "none"

    threshold = 2.0 * p50_cal

    # Walk forward looking for the first N where the windowed p90 over
    # the *first N* samples in dispatch order crosses the threshold.
    # We use a window of min(5, N) so a single slow outlier doesn't
    # mis-fire the saturation flag.
    for n in range(2, len(durations) + 1):
        window_size = min(n, 5)
        window = durations[max(0, n - window_size):n]
        if not window:
            continue
        # p90 of the window
        sorted_window = sorted(window)
        idx = max(0, int(0.9 * (len(sorted_window) - 1)))
        p90 = sorted_window[idx]
        if p90 > threshold:
            return n, "latency_staircase"

    return None, "none"


def _aggregate(samples: List[_RequestSample]) -> Dict[str, float]:
    """Compute p50/p90/p99 from request durations."""
    durations = [s.duration_ms for s in samples if s.status == "ok"]
    if not durations:
        return {"p50": 0.0, "p90": 0.0, "p99": 0.0}
    sorted_d = sorted(durations)

    def _pct(p: float) -> float:
        if not sorted_d:
            return 0.0
        idx = max(0, min(len(sorted_d) - 1, int(p * (len(sorted_d) - 1))))
        return float(sorted_d[idx])

    return {
        "p50": round(_pct(0.50), 1),
        "p90": round(_pct(0.90), 1),
        "p99": round(_pct(0.99), 1),
    }


# ── Probe orchestration ──────────────────────────────────────────


async def _run_burst(
    endpoint: Dict[str, Any],
    model: str,
    burst_size: int,
) -> List[_RequestSample]:
    """Fire ``burst_size`` parallel requests and collect samples."""

    async def _one(idx: int) -> _RequestSample:
        dispatch = time.time()
        status, headers, error = await _dispatch_request(
            endpoint=endpoint, model=model, timeout_s=_REQUEST_TIMEOUT_S,
        )
        complete = time.time()
        return _RequestSample(
            index=idx,
            dispatch_at=dispatch,
            complete_at=complete,
            duration_ms=round((complete - dispatch) * 1000.0, 1),
            status=status,
            error=error,
            headers=headers,
        )

    results = await asyncio.gather(*[_one(i) for i in range(burst_size)])
    return list(results)


def _persist_record(
    *,
    endpoint_id: str,
    record: Dict[str, Any],
) -> Optional[str]:
    """Write the probe record to ``<data_dir>/probes/<endpoint_id>_<ts>.json``.

    Returns the absolute path or ``None`` on error.
    """
    try:
        from prep.core import paths
        target_dir = paths.data_dir() / "probes"
        target_dir.mkdir(parents=True, exist_ok=True)
        ts = int(record.get("probed_at") or time.time())
        # Salt with a uuid so concurrent probes don't collide.
        fname = f"{endpoint_id}_{ts}_{uuid.uuid4().hex[:6]}.json"
        path = target_dir / fname
        path.write_text(json.dumps(record, indent=2))
        return str(path)
    except Exception as exc:
        logger.warning("Could not persist probe record: %s", exc)
        return None


async def run_probe(endpoint_id: str, burst_size: int = _BURST_DEFAULT) -> ProbeResult:
    """Public entry point — invoked by the API handler.

    Resolves the endpoint, fires the burst, computes aggregates, persists
    the record, and pushes the result onto the in-memory history ring.
    Raises ``ValueError`` if the endpoint is unknown.
    """
    burst = max(1, min(int(burst_size), _BURST_HARD_CAP))
    endpoint = _resolve_endpoint(endpoint_id)
    if endpoint is None:
        raise ValueError(f"Unknown endpoint id: {endpoint_id}")

    provider = endpoint.get("provider", "ollama")
    model = _resolve_light_model(endpoint_id, provider)

    probed_at = time.time()
    samples = await _run_burst(endpoint, model, burst)

    successes = sum(1 for s in samples if s.status == "ok")
    errors = burst - successes

    saturation, method = detect_saturation(samples)

    # Recommended concurrent: saturation - 1, clamped to [1, burst].
    recommended: Optional[int] = None
    if saturation is not None:
        recommended = max(1, min(burst, saturation - 1))

    aggregates = _aggregate(samples)

    record: Dict[str, Any] = {
        "endpoint_id": endpoint_id,
        "probed_at": probed_at,
        "burst_size": burst,
        "wall_clock_ms": aggregates,
        "saturation_point": saturation,
        "saturation_method": method,
        "recommended_concurrent": recommended,
        "successes": successes,
        "errors": errors,
        "samples": [
            {
                "index": s.index,
                "duration_ms": s.duration_ms,
                "status": s.status,
                "error": s.error,
            }
            for s in samples
        ],
    }
    histogram_path = _persist_record(endpoint_id=endpoint_id, record=record)
    record["histogram_path"] = histogram_path

    # Push onto in-memory history.
    probe_history.append(endpoint_id, record)

    return ProbeResult(
        endpoint_id=endpoint_id,
        probed_at=probed_at,
        burst_size=burst,
        wall_clock_ms=aggregates,
        saturation_point=saturation,
        saturation_method=method,
        recommended_concurrent=recommended,
        successes=successes,
        errors=errors,
        histogram_path=histogram_path,
        samples=record["samples"],
    )


# ── In-memory history store ──────────────────────────────────────


class _ProbeHistoryStore:
    """Per-endpoint ring buffer of recent probe records.

    In-memory only — survives within a single daemon process. Persisted
    JSON files are the durable record (loaded on demand via
    ``read_persisted``).
    """

    def __init__(self, maxlen: int = _PROBE_HISTORY_MAXLEN) -> None:
        self._maxlen = maxlen
        self._records: Dict[str, List[Dict[str, Any]]] = {}

    def append(self, endpoint_id: str, record: Dict[str, Any]) -> None:
        bucket = self._records.setdefault(endpoint_id, [])
        bucket.append(record)
        # Trim from the left (oldest) when over capacity.
        if len(bucket) > self._maxlen:
            del bucket[: len(bucket) - self._maxlen]

    def get(self, endpoint_id: str, limit: int = _PROBE_HISTORY_MAXLEN) -> List[Dict[str, Any]]:
        bucket = self._records.get(endpoint_id, [])
        safe_limit = max(1, min(int(limit), self._maxlen))
        return bucket[-safe_limit:]

    def clear(self) -> None:
        self._records.clear()

    def latest(self, endpoint_id: str) -> Optional[Dict[str, Any]]:
        bucket = self._records.get(endpoint_id) or []
        return bucket[-1] if bucket else None


probe_history = _ProbeHistoryStore()


def read_persisted(endpoint_id: str, limit: int = _PROBE_HISTORY_MAXLEN) -> List[Dict[str, Any]]:
    """Re-hydrate probe records from disk, sorted oldest-first.

    Useful after daemon restart when the in-memory ring is empty.
    Silently returns ``[]`` on any I/O error.
    """
    try:
        from prep.core import paths
        target_dir = paths.data_dir() / "probes"
        if not target_dir.exists():
            return []
        records: List[Dict[str, Any]] = []
        for path in sorted(target_dir.glob(f"{endpoint_id}_*.json")):
            try:
                records.append(json.loads(path.read_text()))
            except Exception:
                continue
        records.sort(key=lambda r: r.get("probed_at") or 0.0)
        safe_limit = max(1, min(int(limit), 50))
        return records[-safe_limit:]
    except Exception:
        return []


# Re-export for tests
__all__ = [
    "ProbeResult",
    "_RequestSample",
    "_dispatch_request",
    "_run_burst",
    "detect_saturation",
    "probe_history",
    "read_persisted",
    "run_probe",
]
