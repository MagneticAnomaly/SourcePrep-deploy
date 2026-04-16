"""
LLM Client for CoDRAG.

Universal multi-provider LLM client and response parsing utilities.
Extracted from augmenter.py (Refactor 2, GAP-1) to eliminate false
dependency chains — every LLM-consuming module was forced to import
from augmenter.py just to access the client.

Providers: ollama, openai, openai-compatible, anthropic, google.
"""
from __future__ import annotations

import json
import logging
import re
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Cloud rate-limit detection ────────────────────────────────────────

class CloudRateLimitError(Exception):
    """Raised when a cloud LLM endpoint returns HTTP 429 (rate limit exceeded).

    The pipeline orchestrator catches this to gracefully pause the pipeline
    instead of failing the entire run.  The user can resume later or switch
    to a local model.

    Attributes:
        retry_after: Seconds to wait before retrying (from Retry-After header), or None.
        model: The model tag that was rate-limited.
        endpoint: The endpoint URL.
    """

    def __init__(self, message: str, *, retry_after: Optional[int] = None,
                 model: str = "", endpoint: str = ""):
        super().__init__(message)
        self.retry_after = retry_after
        self.model = model
        self.endpoint = endpoint


def _is_cloud_model(model: str) -> bool:
    """Return True if the model tag indicates a cloud-hosted model."""
    return ":cloud" in model.lower()


_CLOUD_PROVIDERS = frozenset(("openai", "anthropic", "google"))


def _is_cloud_endpoint(llm: "LLMClient") -> bool:
    """Return True if the LLMClient targets a cloud-hosted endpoint.

    Checks both the model tag (``kimi-k2.5:cloud``) and the provider
    (OpenAI, Anthropic, Google APIs are always cloud).  Used by swarm
    callers to set shorter timeouts for sequential cloud processing.
    """
    return _is_cloud_model(llm.model) or llm.provider in _CLOUD_PROVIDERS


# ── Output safety guards ──────────────────────────────────────────────

class OutputMonitor:
    """Monitors streaming LLM output for degenerate patterns.

    Designed to catch repetition loops (e.g., a model repeating the same
    8-line block 73 times) and runaway output length.  Integrated into
    the streaming response loop in :meth:`LLMClient.generate`.
    """

    def __init__(self, max_chars: int = 0):
        self.max_chars = max_chars  # 0 = unlimited
        self.buffer = ""
        self._check_interval = 500  # chars between repetition checks
        self._last_check_len = 0

    def feed(self, chunk: str) -> tuple:
        """Feed a new chunk of streamed output.

        Returns:
            (should_abort: bool, reason: str)
        """
        self.buffer += chunk
        buf_len = len(self.buffer)

        # Guard 1: Absolute length limit
        if self.max_chars and buf_len > self.max_chars:
            return True, f"Output exceeded max_chars ({self.max_chars})"

        # Guard 2: Repetition detection (check every _check_interval chars)
        if buf_len - self._last_check_len >= self._check_interval:
            self._last_check_len = buf_len
            abort, reason = self._check_repetition()
            if abort:
                return True, reason

        return False, ""

    def _check_repetition(self) -> tuple:
        """Detect repetition loops in accumulated output."""
        lines = [l.strip() for l in self.buffer.split("\n") if len(l.strip()) > 40]
        if len(lines) < 12:
            return False, ""
        counts = Counter(lines)
        top_line, top_count = counts.most_common(1)[0]
        # If any single line appears > 4 times AND makes up > 25% of
        # substantial lines, it's almost certainly a loop.
        if top_count > 4 and top_count / len(lines) > 0.25:
            return True, f"Repetition loop detected ({top_count} repeats)"
        return False, ""

    def truncate_to_good_content(self) -> str:
        """If a loop was detected, return the content before the first repeat."""
        lines = self.buffer.split("\n")
        seen = {}
        for i, line in enumerate(lines):
            stripped = line.strip()
            if len(stripped) > 40:
                if stripped in seen:
                    # Return everything up to the line before this repeat
                    return "\n".join(lines[:i]).rstrip()
                seen[stripped] = i
        return self.buffer


# Default max_chars limits per CoDRAG task type.  Used by the pipeline
# to cap output length and prevent runaway generation.
TASK_MAX_CHARS = {
    "atlas_small": 15_000,
    "atlas_large": 80_000,
    "audit": 15_000,
    "group_reasoning": 8_000,
    "augmentation": 2_000,
    "epistemic": 3_000,
}


def batched_max_chars(task: str, batch_size: int) -> int:
    """Compute max_chars for a batched LLM response.

    The base TASK_MAX_CHARS values are per-item limits.  Batched responses
    contain N items in a JSON array, so the output scales roughly linearly.
    We add a fixed overhead for the JSON wrapper and some headroom.

    Returns 0 (unlimited) if the base task has no limit.
    """
    base = TASK_MAX_CHARS.get(task, 0)
    if base == 0 or batch_size <= 1:
        return base
    return base * batch_size + 500  # +500 for JSON wrapper overhead


def _parse_confidence(raw: Any, default: float = 0.5) -> float:
    """Safely parse a confidence value from LLM output.

    Handles common LLM quirks like returning ``": 0.85"`` or ``"~0.9"``
    instead of a bare number.
    """
    if isinstance(raw, (int, float)):
        return max(0.0, min(1.0, float(raw)))
    if not isinstance(raw, str):
        return default
    # Strip leading non-numeric characters (colon, tilde, spaces, etc.)
    s = raw.strip()
    # Remove common prefixes: ": ", "~ ", "≈ ", etc.
    while s and s[0] not in '0123456789.-':
        s = s[1:]
    s = s.strip()
    if not s:
        return default
    try:
        return max(0.0, min(1.0, float(s)))
    except (ValueError, TypeError):
        return default


def _get_llm_concurrency(stage: str = "fast") -> int:
    """Read LLM concurrency from pipeline config for the given stage group.

    Three separate settings matching the three model slots:

      - ``llm_concurrency_fast``: Stage 3 (catalogue).
        Uses the small/instruct model (e.g. qwen3:4b-instruct at 2.5 GB).

      - ``llm_concurrency_code``: Stage 2 (inferred_edges).
        Uses the coder model (e.g. qwen3-coder:30b at ~18 GB).
        Falls back to ``llm_concurrency_fast`` if not set.

      - ``llm_concurrency_deep``: Stages 6-9 (epistemic, clustering,
        deepening).  Uses the large/thinking model (e.g. deepseek-r1:32b
        or qwen3.5:35b-a3b at ~20 GB).

    Falls back to legacy ``llm_concurrency`` if none of the split keys are set.

    Each concurrent request needs its own KV cache in VRAM/RAM:
      Total memory = model_weights + (concurrency × kv_cache_size)

    Set OLLAMA_NUM_PARALLEL in Ollama to at least max(fast, code, deep).

    Args:
        stage: "fast" for catalogue (stage 3),
               "code" for inferred_edges (stage 2),
               "deep" for deep-enrichment stages (6-9).
    """
    try:
        from codrag.services.settings_store import settings
        config = settings.get("pipeline_config") or {}

        if stage == "deep":
            key = "llm_concurrency_deep"
        elif stage == "code":
            key = "llm_concurrency_code"
        else:
            key = "llm_concurrency_fast"

        # Try the split key first, fall back to fast key, then legacy single key
        value = config.get(key)
        if not value and stage == "code":
            value = config.get("llm_concurrency_fast")
        if not value:
            value = config.get("llm_concurrency", 1)
        return max(1, min(8, int(value)))
    except Exception:
        return 1


def _strip_think_tags(text: str) -> str:
    """Strip LLM thinking tokens from all model families.

    Handles:
    - Qwen3/3.5: <think>reasoning...</think>
    - DeepSeek-R1: <think>reasoning...</think>
    - Unclosed <think> tags (model output truncated mid-thought)
    - Nested or repeated think blocks
    - <output> wrapper tags some models add around the answer
    """
    # Strip closed <think>...</think> blocks (greedy within each block)
    text = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL)
    # Strip unclosed <think> (model started thinking but output was truncated)
    text = re.sub(r'<think>.*', '', text, flags=re.DOTALL)
    # Strip <output>...</output> wrapper some models add
    text = re.sub(r'</?output>\s*', '', text, flags=re.DOTALL)
    return text.strip()


def _repair_truncated_json(fragment: str) -> Optional[Dict[str, Any]]:
    """Try to recover a dict from a truncated JSON fragment.

    Strategy: progressively strip trailing incomplete content and try
    closing the string / object.  Handles truncation mid-key, mid-value,
    and mid-array (e.g. related_files list cut off).
    """
    # Strategy 1: try closing with various suffixes (handles mid-string/array truncation)
    for suffix in ('"]}', '"] }', ']}', '}', '"}', '" }', '"}}', '0}', 'null}'):
        try:
            return json.loads(fragment + suffix)
        except json.JSONDecodeError:
            continue

    # Strategy 2: progressively strip back to comma boundaries and try closing.
    # Try multiple commas from end→start because the last comma may be inside
    # a string value or array element, not a top-level object separator.
    pos = len(fragment)
    attempts = 0
    while attempts < 30:
        pos = fragment.rfind(",", 0, pos)
        if pos <= 0:
            break
        truncated = fragment[:pos]
        for suffix in ("}", '"]}', ']}', '"}'):
            try:
                return json.loads(truncated + suffix)
            except json.JSONDecodeError:
                continue
        attempts += 1

    return None


def _parse_json_response(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON extraction from LLM response.

    Handles think tags, markdown code fences, truncated JSON,
    thinking-model preambles (kimi-k2.5, DeepSeek-R1), and various
    model output quirks.

    Strategy (most specific → most aggressive):
    1. Strip XML think tags
    2. Direct parse
    3. Markdown code block extraction
    4. First { ... last } substring
    5. Backward brace-matching (for thinking models with { in preamble)
    6. Truncated JSON repair
    """
    # Step 0: Strip think tags BEFORE any parsing attempts
    text = _strip_think_tags(text)
    text = text.strip()
    if not text:
        return None
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting JSON from markdown code block
    if "```" in text:
        for block in text.split("```"):
            block = block.strip()
            if block.startswith("json"):
                block = block[4:].strip()
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue
    # Try finding first { ... last }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    # Step 5: Backward brace-matching — for thinking models (kimi-k2.5)
    # that emit natural language containing { before the actual JSON.
    # Walk backward from the last } to find the matching { via depth counting.
    if end >= 0:
        depth = 0
        in_string = False
        escape = False
        for i in range(end, -1, -1):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '}':
                depth += 1
            elif ch == '{':
                depth -= 1
                if depth == 0:
                    candidate = text[i : end + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        # This { wasn't the right one, keep scanning backward
                        depth = 1  # Reset to look for next outer {
                        continue

    # Step 6: Truncated JSON repair
    if start >= 0:
        fragment = text[start:]
        repaired = _repair_truncated_json(fragment)
        if repaired is not None:
            return repaired
    return None


class LLMClient:
    """
    Minimal LLM client for augmentation calls.
    Supports: ollama, openai, openai-compatible, anthropic, google.
    """

    # Ollama cloud queues requests beyond the concurrency limit (Free=1,
    # Pro=3, Max=10).  429 means the queue is full — a short wait for the
    # current request to finish is usually enough.  Two retries covers
    # both paid (queue drains fast) and free (queue drains slower) tiers.
    _MAX_429_RETRIES = 2

    def __init__(
        self,
        endpoint_url: str,
        model: str,
        provider: str = "ollama",
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        always_on: bool = False,
        debug_mode: bool = False,
    ):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.model = model
        self.provider = provider
        self.api_key = api_key
        self.timeout = timeout
        self.always_on = always_on
        self.debug_mode = debug_mode

        # F-59: thread-local Sessions for concurrent swarm workers.
        #
        # The original global Session approach deadlocked because:
        # 1. pool_maxsize=10 (default) with 10 workers + 1 zombie = 11 requests
        # 2. Even with pool_maxsize=20 + pool_block=False, the shared Session
        #    exhibited blocking under concurrent use
        #
        # Fix: use thread-local Sessions. Each worker thread gets its own
        # Session (and its own connection pool) via threading.local().
        # No contention possible since each thread owns its connection.
        import threading as _threading
        self._thread_local = _threading.local()

    @property
    def _session(self):
        """Thread-local requests.Session — each thread gets its own."""
        import requests as _requests
        s = getattr(self._thread_local, 'session', None)
        if s is None:
            s = _requests.Session()
            self._thread_local.session = s
        return s


    def _record_telemetry(self, prompt_tokens: int, completion_tokens: int, total_tokens: int) -> None:
        """Record token usage if a telemetry context is active.
        
        Caches the store reference after first successful import to avoid
        repeated module lookups on every LLM call.
        """
        try:
            store = getattr(self, '_telemetry_store', None)
            if store is None:
                from codrag.services.token_telemetry import telemetry
                store = self._telemetry_store = telemetry
            store.record_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                model=self.model,
                provider=self.provider,
            )
        except Exception as e:
            logger.debug("Failed to record token telemetry: %s", e)

    def _track_active(self, action: str) -> None:
        """Track active LLM requests for AI Gateway telemetry."""
        try:
            store = getattr(self, '_telemetry_store', None)
            if store is None:
                from codrag.services.token_telemetry import telemetry
                store = self._telemetry_store = telemetry
            
            if action == "start":
                # Determine model slot based on task if available, but
                # for generic AI Gateway display, generic tracking works.
                store.track_active_request(self.model, self.provider, getattr(self, '_model_slot', None))
            elif action == "stop":
                store.untrack_active_request()
        except Exception as e:
            logger.debug("Failed to track active request: %s", e)

    def _record_throughput(self, queue_time_ms: float = 0.0, rate_limit_remaining: Optional[int] = None, is_429_or_timeout: bool = False) -> None:
        """Phase 82: Asynchronously notify the PipelineScheduler of connection health for AIMD adjusting."""
        try:
            from codrag.services.pipeline.scheduler import pipeline_scheduler
            pipeline_scheduler.record_throughput_for_provider(
                self.provider, 
                self.model, 
                queue_time_ms=queue_time_ms, 
                rate_limit_remaining=rate_limit_remaining, 
                is_429_or_timeout=is_429_or_timeout
            )
        except Exception as e:
            logger.debug("Failed to report latency throughput to scheduler: %s", e)

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        num_predict: int = 2048,
        json_mode: bool = True,
        temperature: float = 0.1,
        response_schema: Optional[Dict[str, Any]] = None,
        think: Optional[bool] = None,
        max_chars: int = 0,
        num_ctx: Optional[int] = None,
    ) -> Tuple[str, int]:
        self._track_active("start")
        try:
            return self._generate_internal(
                prompt=prompt,
                system=system,
                num_predict=num_predict,
                json_mode=json_mode,
                temperature=temperature,
                response_schema=response_schema,
                think=think,
                max_chars=max_chars,
                num_ctx=num_ctx,
            )
        finally:
            self._track_active("stop")

    def _generate_internal(
        self,
        prompt: str,
        system: Optional[str] = None,
        num_predict: int = 2048,
        json_mode: bool = True,
        temperature: float = 0.1,
        response_schema: Optional[Dict[str, Any]] = None,
        think: Optional[bool] = None,
        max_chars: int = 0,
        num_ctx: Optional[int] = None,
    ) -> Tuple[str, int]:
        """
        Call the LLM and return (response_text, tokens_used).
        Raises on network/parse errors.

        Args:
            json_mode: If True (default), request JSON output from Ollama.
                       Set False for free-form prose (e.g. Atlas generation).
            temperature: Sampling temperature. Lower = more deterministic.
            response_schema: Optional JSON schema dict for guaranteed structured output 
                             (supported by OpenAI and Google).
            max_chars: If > 0, abort generation and truncate if output exceeds
                       this many characters.  Also enables repetition-loop
                       detection via :class:`OutputMonitor`.  Use
                       :data:`TASK_MAX_CHARS` for per-task defaults.
        """
        import requests

        # ── CORE security: sanitize input before ANY LLM call ──────
        # These are always-on, zero-quality-impact protections that run
        # for all tiers. They strip invisible Unicode (Rules File Backdoor)
        # and normalize homoglyphs (EchoLeak CVE-2025-32711).
        try:
            from codrag.core.content_sanitizer import sanitize_llm_input, validate_llm_output
            prompt = sanitize_llm_input(prompt)
            if system:
                system = sanitize_llm_input(system)
        except ImportError:
            pass  # content_sanitizer not available — skip gracefully

        # ── ENTERPRISE: DLP secret redaction (only when admin_policy configures it) ──
        # This is quality-impacting by design — IT makes a conscious tradeoff.
        try:
            from codrag.server import _load_ui_config
            ui_cfg = _load_ui_config()
            admin_policy_raw = ui_cfg.get("_admin_policy_cache")
            if not admin_policy_raw:
                # Try loading from active project
                active_id = None
                try:
                    from codrag.services.settings_store import settings
                    active_id = settings.get("active_project")
                except Exception:
                    pass
                if active_id:
                    try:
                        proj_root = None
                        try:
                            from codrag.services.settings_store import settings as _s
                            proj_root = _s.project_get(active_id, "root_path")
                        except Exception:
                            pass
                        if proj_root:
                            from pathlib import Path
                            from codrag.core.team_config import load_admin_policy
                            _policy = load_admin_policy(Path(proj_root))
                            if _policy.data.redact_patterns:
                                from codrag.core.content_sanitizer import redact_secrets_in_content
                                prompt = redact_secrets_in_content(prompt, _policy.data.redact_patterns)
                    except Exception:
                        pass
        except Exception:
            pass  # Enterprise DLP not available — skip gracefully

        # ── Audit trail: record LLM call metadata ──────────────────
        try:
            from codrag.core.audit_log import get_audit_log
            get_audit_log().record(
                event_type="llm_call",
                severity="info",
                message=f"LLM call: {self.provider}/{self.model}",
                metadata={
                    "provider": self.provider,
                    "model": self.model,
                    "endpoint": self.endpoint_url,
                    "num_predict": num_predict,
                    "prompt_chars": len(prompt),
                },
            )
        except Exception:
            pass

        if self.provider == "lm-studio":
            text, tokens = self._generate_lmstudio(
                prompt, system=system, num_predict=num_predict,
                json_mode=json_mode, temperature=temperature,
                response_schema=response_schema, think=think,
                max_chars=max_chars, num_ctx=num_ctx,
            )
            # CORE: validate output for suspicious patterns
            try:
                text, _warnings = validate_llm_output(text)
            except Exception:
                pass
            return text, tokens

        effective_provider = self.provider

        if effective_provider == "ollama":
            # When thinking is enabled, Ollama counts thinking tokens AND
            # response tokens against num_predict.  Scale the budget so the
            # model has room for both the reasoning trace and the answer.
            effective_num_predict = num_predict
            if think:
                # Scale budget for thinking overhead, but cap to prevent runaway
                # generation on small prompts (e.g., a 500-token audit prompt with
                # np=16384 would otherwise get 49K budget, causing 30+ min of
                # thinking for no benefit).  The cap is configurable via the
                # Advanced Settings "Max Thinking Budget" slider (Phase 112).
                try:
                    from codrag.server import get_advanced_llm_settings
                    max_budget = get_advanced_llm_settings().get(
                        "max_thinking_budget", 24576,
                    )
                except Exception:
                    max_budget = 24576
                effective_num_predict = min(
                    max(num_predict * 3, num_predict + 8192),
                    max(num_predict, max_budget),
                )
            options: Dict[str, Any] = {
                "temperature": temperature,
                "num_predict": effective_num_predict,
                "top_k": 20,
                "top_p": 0.95,
                "repeat_penalty": 1.15,
                "repeat_last_n": 256,
            }
            if num_ctx is not None:
                options["num_ctx"] = num_ctx
            payload: Dict[str, Any] = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,   # F-59 part 5: must match requests stream=False
                "options": options,
            }
            # Pass think=True/False to enable/disable reasoning mode.
            # When enabled, the model emits a separate thinking trace before
            # the answer; effective_num_predict above already accounts for
            # the extra token budget this requires.
            if think is not None:
                payload["think"] = think
            if json_mode and not response_schema:
                payload["format"] = "json"
            elif response_schema:
                # OpenAI structured outputs format (Ollama supports this for some models)
                payload["format"] = response_schema
            if system:
                payload["system"] = system

            url = f"{self.endpoint_url}/api/generate"
            
            if self.debug_mode:
                logger.info(f"\n[DEBUG_LLM] Request (ollama): POST {url}")
                logger.info(f"[DEBUG_LLM] Model: {self.model}, Budget: {effective_num_predict}")
                logger.info(f"[DEBUG_LLM] Prompt:\n{prompt}\n")
            
            t0 = time.monotonic()
            
            # F-59 part 4: use stream=False for cloud-proxied models.
            #
            # Cloud models (kimi-k2.5:cloud etc.) proxy through Ollama Cloud
            # which buffers the entire response and sends it as one batch —
            # NOT token-by-token NDJSON streaming.  With stream=True,
            # resp.iter_lines() hangs indefinitely after the response body
            # is received because the chunked-transfer decoder waits for
            # more chunks that never arrive.  The connection shows as
            # TIME_WAIT (TCP FIN sent) but iter_lines() doesn't see EOF.
            #
            # stream=False tells requests to buffer the full response body
            # before returning, then we split into NDJSON lines ourselves.
            # This is safe for all Ollama models since the response format
            # (NDJSON with a final {"done":true} line) is the same either
            # way — we just parse it from a string instead of a socket.
            #
            # The read timeout (self.timeout) still applies to stream=False:
            # requests will raise Timeout if no data arrives within the
            # timeout period.  For local models that genuinely stream
            # token-by-token, this means the timeout is per the ENTIRE
            # response (not per-token), which is acceptable since we set
            # timeout=60s and most responses complete in <30s.
            #
            # Retry on 429 (Too Many Requests) with exponential backoff.
            # F-59 rework: Use subprocess curl for cloud-proxied models.
            # requests.post() blocks indefinitely in daemon build threads
            # for cloud models (works fine standalone, works fine via curl).
            # Root cause unknown — suspected interaction between requests/
            # urllib3 and uvicorn's thread pool. curl returns in 8-18s for
            # the same calls that hang forever with requests.
            #
            # For local models, requests.post() works fine — keep it.
            _is_cloud_model = ":cloud" in self.model.lower()
            # F-74: The "cloud model hang" was caused by _record_throughput()
            # deadlocking on pipeline_scheduler._lock, NOT by requests.post().
            # With the non-blocking lock fix, requests.post() works fine for
            # all models including cloud-proxied ones.
            _resp = None
            for _attempt in range(self._MAX_429_RETRIES + 1):
                try:
                    _resp = self._session.post(url, json=payload, timeout=(30, self.timeout), stream=False)
                    if _resp.status_code != 429:
                        break
                    _resp.close()
                except requests.exceptions.Timeout:
                    self._record_throughput(is_429_or_timeout=True)
                    raise

                if _attempt < self._MAX_429_RETRIES:
                    self._record_throughput(is_429_or_timeout=True)
                    _wait = 5 * (_attempt + 1)  # 5s, 10s
                    logger.info(
                        "429 rate-limited by %s — retry %d/%d in %ds",
                        self.model, _attempt + 1, self._MAX_429_RETRIES, _wait,
                    )
                    time.sleep(_wait)
            resp = _resp
            resp.raise_for_status()
            # Parse the complete NDJSON response body.
            # Each line is a JSON object; the final one has "done": true.
            monitor = OutputMonitor(max_chars=max_chars) if max_chars else None
            text_parts = []
            thinking_parts = []
            tokens = 0
            total_exec_ms = 0.0
            aborted = False
            abort_reason = ""
            for raw_line in resp.text.splitlines():
                if not raw_line.strip():
                    continue
                try:
                    chunk = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                resp_chunk = chunk.get("response", "")
                text_parts.append(resp_chunk)
                thinking_parts.append(chunk.get("thinking", ""))
                if monitor and resp_chunk:
                    should_abort, reason = monitor.feed(resp_chunk)
                    if should_abort:
                        aborted = True
                        abort_reason = reason
                        logger.warning("OutputMonitor aborted: %s", reason)
                        break
                if chunk.get("done"):
                    eval_count = chunk.get("eval_count", 0)
                    prompt_eval_count = chunk.get("prompt_eval_count", 0)
                    eval_duration_ns = chunk.get("eval_duration", 0)
                    prompt_eval_duration_ns = chunk.get("prompt_eval_duration", 0)
                    load_duration_ns = chunk.get("load_duration", 0)
                    total_exec_ms = (eval_duration_ns + prompt_eval_duration_ns + load_duration_ns) / 1000000.0
                    tokens = eval_count + prompt_eval_count
                    self._record_telemetry(prompt_eval_count, eval_count, tokens)
                    break
            resp.close()
            logger.info("[F-59 curl] Parsing complete: %d text parts, %d tokens, aborted=%s", len(text_parts), tokens, aborted)

            t1 = time.monotonic()
            wall_time_ms = (t1 - t0) * 1000.0
            queue_time_ms = max(0.0, wall_time_ms - total_exec_ms)
            self._record_throughput(queue_time_ms=queue_time_ms)
            
            text = "".join(text_parts)
            thinking = "".join(thinking_parts)
            # If aborted due to repetition, truncate to the good content
            if aborted and monitor:
                text = monitor.truncate_to_good_content()
                logger.info("Truncated output from %d to %d chars (%s)",
                            len(monitor.buffer), len(text), abort_reason)
            # Ollama's new engine (Sept 2025+) puts thinking model output
            # in a separate "thinking" field.  For qwen3.5, deepseek-r1,
            # and other reasoning models, the JSON answer may land in
            # "thinking" while "response" is empty.  Concatenate both so
            # _parse_json_response / _strip_think_tags can handle it.
            if thinking and not text:
                # Model put everything in thinking field
                text = thinking
            elif thinking and text:
                # Model has both thinking and response — wrap thinking in
                # tags so _strip_think_tags can remove it cleanly.
                text = f"<think>{thinking}</think>{text}"
                
            if self.debug_mode:
                t1 = time.monotonic()
                logger.info(f"[DEBUG_LLM] Response (ollama):")
                logger.info(f"[DEBUG_LLM] Time: {t1 - t0:.2f}s, Tokens: {tokens}, Tok/s: {tokens / (t1 - t0) if t1 > t0 else 0:.1f}")
                logger.info(f"[DEBUG_LLM] Body:\n{text}\n")
                
            # CORE: validate output for suspicious patterns
            try:
                from codrag.core.content_sanitizer import validate_llm_output
                text, _warnings = validate_llm_output(text)
            except Exception:
                pass
            return text, tokens

        elif effective_provider in ("openai", "openai-compatible"):
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            
            if response_schema:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_response",
                        "schema": response_schema,
                        "strict": True
                    }
                }
            
            headers = {
                "Content-Type": "application/json",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Normalize base URL: OpenAI uses https://api.openai.com/v1,
            # but LM Studio / other servers use http://localhost:1234 (no /v1).
            # Auto-add /v1 if missing so the request hits /v1/chat/completions.
            base = self.endpoint_url if "v1" in self.endpoint_url else f"{self.endpoint_url}/v1"
            url = f"{base}/chat/completions"
            
            t0 = time.monotonic()
            _resp = None
            rate_limit_remaining = None
            for _attempt in range(self._MAX_429_RETRIES + 1):
                try:
                    _resp = self._session.post(url, json=payload, headers=headers, timeout=self.timeout)
                    
                    # Parse OpenAI ratelimit headers
                    srem = _resp.headers.get("x-ratelimit-remaining-requests")
                    if srem and srem.isdigit():
                        rate_limit_remaining = int(srem)

                    if _resp.status_code != 429:
                        break
                except requests.exceptions.Timeout:
                    self._record_throughput(is_429_or_timeout=True)
                    raise
                
                if _attempt < self._MAX_429_RETRIES:
                    self._record_throughput(is_429_or_timeout=True)
                    _wait = 5 * (_attempt + 1)
                    logger.info("429 rate-limited by %s — retry %d/%d in %ds", self.model, _attempt + 1, self._MAX_429_RETRIES, _wait)
                    time.sleep(_wait)
            resp = _resp
            resp.raise_for_status()
            
            t1 = time.monotonic()
            wall_time_ms = (t1 - t0) * 1000.0
            self._record_throughput(queue_time_ms=wall_time_ms, rate_limit_remaining=rate_limit_remaining)
            data = resp.json()
            
            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})
            prompt_toks = usage.get("prompt_tokens", 0)
            comp_toks = usage.get("completion_tokens", 0)
            tokens = prompt_toks + comp_toks
            self._record_telemetry(prompt_toks, comp_toks, tokens)
            
            # CORE: validate output
            try:
                from codrag.core.content_sanitizer import validate_llm_output
                text, _warnings = validate_llm_output(text)
            except Exception:
                pass
            return text, tokens
        
        elif effective_provider == "anthropic":
            messages = []
            messages.append({"role": "user", "content": prompt})

            payload: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "max_tokens": num_predict,
                "temperature": temperature,
            }
            if system:
                payload["system"] = system

            headers = {
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            if self.api_key:
                headers["x-api-key"] = self.api_key

            url = f"{self.endpoint_url}/v1/messages"
            t0 = time.monotonic()
            _resp = None
            rate_limit_remaining = None
            for _attempt in range(self._MAX_429_RETRIES + 1):
                try:
                    _resp = self._session.post(url, json=payload, headers=headers, timeout=self.timeout)
                    
                    # Parse Anthropic ratelimit headers
                    srem = _resp.headers.get("anthropic-ratelimit-requests-remaining")
                    if srem and srem.isdigit():
                        rate_limit_remaining = int(srem)

                    if _resp.status_code != 429:
                        break
                except requests.exceptions.Timeout:
                    self._record_throughput(is_429_or_timeout=True)
                    raise
                
                if _attempt < self._MAX_429_RETRIES:
                    self._record_throughput(is_429_or_timeout=True)
                    _wait = 5 * (_attempt + 1)
                    logger.info("429 rate-limited by %s — retry %d/%d in %ds", self.model, _attempt + 1, self._MAX_429_RETRIES, _wait)
                    time.sleep(_wait)
            resp = _resp
            resp.raise_for_status()
            
            t1 = time.monotonic()
            wall_time_ms = (t1 - t0) * 1000.0
            self._record_throughput(queue_time_ms=wall_time_ms, rate_limit_remaining=rate_limit_remaining)
            data = resp.json()

            # Anthropic returns content as a list of blocks
            content_blocks = data.get("content", [])
            text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
            usage = data.get("usage", {})
            input_toks = usage.get("input_tokens", 0)
            output_toks = usage.get("output_tokens", 0)
            tokens = input_toks + output_toks
            self._record_telemetry(input_toks, output_toks, tokens)
            
            # CORE: validate output
            try:
                from codrag.core.content_sanitizer import validate_llm_output
                text, _warnings = validate_llm_output(text)
            except Exception:
                pass
            return text, tokens

        elif effective_provider == "azure-openai":
            # Azure OpenAI uses deployment-based URLs and api-key header
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": num_predict,
            }
            if response_schema:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_response",
                        "schema": response_schema,
                        "strict": True,
                    },
                }

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["api-key"] = self.api_key

            # Azure uses: https://<resource>.openai.azure.com/openai/deployments/<deployment>/chat/completions?api-version=...
            url = f"{self.endpoint_url}/openai/deployments/{self.model}/chat/completions"
            params = {"api-version": "2024-02-01"}

            resp = self._session.post(url, json=payload, headers=headers, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})
            prompt_toks = usage.get("prompt_tokens", 0)
            comp_toks = usage.get("completion_tokens", 0)
            tokens = prompt_toks + comp_toks
            self._record_telemetry(prompt_toks, comp_toks, tokens)
            
            # CORE: validate output
            try:
                from codrag.core.content_sanitizer import validate_llm_output
                text, _warnings = validate_llm_output(text)
            except Exception:
                pass
            return text, tokens

        elif effective_provider == "google":
            # Google Gemini API — uses systemInstruction for system prompts
            contents = [{"role": "user", "parts": [{"text": prompt}]}]

            generation_config = {
                "temperature": temperature,
                "maxOutputTokens": num_predict,
            }
            
            if response_schema:
                generation_config["responseMimeType"] = "application/json"
                generation_config["responseSchema"] = response_schema
            elif json_mode:
                generation_config["responseMimeType"] = "application/json"

            payload: Dict[str, Any] = {
                "contents": contents,
                "generationConfig": generation_config,
            }
            if system:
                payload["systemInstruction"] = {"parts": [{"text": system}]}

            url = f"{self.endpoint_url}/v1beta/models/{self.model}:generateContent"
            params = {"key": self.api_key} if self.api_key else {}
            resp = self._session.post(url, json=payload, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            candidates = data.get("candidates", [{}])
            parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
            text = "".join(p.get("text", "") for p in parts)
            usage = data.get("usageMetadata", {})
            prompt_toks = usage.get("promptTokenCount", 0)
            comp_toks = usage.get("candidatesTokenCount", 0)
            tokens = prompt_toks + comp_toks
            self._record_telemetry(prompt_toks, comp_toks, tokens)
            # CORE: validate output
            try:
                from codrag.core.content_sanitizer import validate_llm_output
                text, _warnings = validate_llm_output(text)
            except Exception:
                pass
            return text, tokens

        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")


    def _generate_lmstudio(
        self,
        prompt: str,
        system: Optional[str] = None,
        num_predict: int = 2048,
        json_mode: bool = True,
        temperature: float = 0.1,
        response_schema: Optional[Dict[str, Any]] = None,
        think: Optional[bool] = None,
        max_chars: int = 0,
        num_ctx: Optional[int] = None,
    ) -> Tuple[str, int]:
        """Generate text using LM Studio's native /api/v1/chat endpoint.

        This gives us per-request control over context_length,
        max_output_tokens, and reasoning mode — features not available
        through the OpenAI-compatible /v1/chat/completions path.

        Streams via SSE: message.delta for text, reasoning.delta for
        thinking, chat.end for final stats.
        """
        import requests
        from codrag.core.model_readiness import _lmstudio_api_base

        base = _lmstudio_api_base(self.endpoint_url)
        url = f"{base}/chat"

        # Native API uses "input" — string for simple, array for system+user
        if system:
            input_val: Any = [
                {"type": "message", "role": "system", "content": system},
                {"type": "message", "role": "user", "content": prompt},
            ]
        else:
            input_val = prompt

        payload: Dict[str, Any] = {
            "model": self.model,
            "input": input_val,
            "temperature": temperature,
            "stream": False,   # F-59 part 5: must match requests stream=False
            "max_output_tokens": num_predict,
        }

        # Per-request context window — key advantage over OpenAI-compat path
        if num_ctx is not None:
            payload["context_length"] = num_ctx

        # Reasoning mode: "off" | "low" | "medium" | "high" | "on"
        if think is not None:
            payload["reasoning"] = "on" if think else "off"

        # System prompt (simple string form when input is a plain string)
        if system and isinstance(input_val, str):
            payload["system_prompt"] = system

        # F-59 part 4: stream=False to avoid iter_lines() hang (same fix
        # as the Ollama path above — cloud-proxied models don't stream).
        resp = self._session.post(url, json=payload, timeout=(30, self.timeout), stream=False)
        if resp.status_code == 400:
            try:
                err_body = resp.text[:500]
            except Exception:
                err_body = "(could not read body)"
            logger.error(
                "LM Studio native API 400 for model=%s url=%s: %s",
                self.model, url, err_body,
            )
        resp.raise_for_status()

        # Parse SSE response body (no longer streaming)
        monitor = OutputMonitor(max_chars=max_chars) if max_chars else None
        text_parts: list = []
        thinking_parts: list = []
        tokens = 0
        prompt_toks = 0
        comp_toks = 0
        aborted = False
        abort_reason = ""

        for raw_line in resp.text.splitlines():
            if not raw_line:
                continue
            # SSE lines are prefixed with "data: "
            line = raw_line
            if line.startswith("data: "):
                line = line[6:]
            if not line or line == "[DONE]":
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")

            if event_type == "message.delta":
                content = event.get("content", "")
                text_parts.append(content)
                if monitor and content:
                    should_abort, reason = monitor.feed(content)
                    if should_abort:
                        aborted = True
                        abort_reason = reason
                        logger.warning("OutputMonitor aborted: %s", reason)
                        break

            elif event_type == "reasoning.delta":
                thinking_parts.append(event.get("content", ""))

            elif event_type == "chat.end":
                result = event.get("result", {})
                stats = result.get("stats", {})
                prompt_toks = stats.get("input_tokens", 0)
                comp_toks = stats.get("total_output_tokens", 0)
                tokens = prompt_toks + comp_toks
                # If we didn't get streaming deltas, extract from final result
                if not text_parts:
                    for item in result.get("output", []):
                        if item.get("type") == "message":
                            text_parts.append(item.get("content", ""))
                        elif item.get("type") == "reasoning":
                            thinking_parts.append(item.get("content", ""))
                break

            elif event_type == "error":
                error_info = event.get("error", {})
                raise RuntimeError(
                    f"LM Studio error: {error_info.get('message', 'unknown')} "
                    f"(type={error_info.get('type', '?')})"
                )

        resp.close()
        text = "".join(text_parts)
        thinking = "".join(thinking_parts)

        # Handle repetition abort
        if aborted and monitor:
            text = monitor.truncate_to_good_content()
            logger.info("Truncated output from %d to %d chars (%s)",
                        len(monitor.buffer), len(text), abort_reason)

        # Merge thinking + response (same logic as Ollama path)
        if thinking and not text:
            text = thinking
        elif thinking and text:
            text = f"<think>{thinking}</think>{text}"

        # Record LM Studio token usage
        if tokens > 0:
            self._record_telemetry(prompt_toks, comp_toks, tokens)

        return text, tokens

    def is_available(self) -> bool:
        """Check if the endpoint is reachable."""
        import requests
        try:
            if self.provider == "lm-studio":
                from codrag.core.model_readiness import lmstudio_server_reachable
                return lmstudio_server_reachable(self.endpoint_url)
            elif self.provider == "ollama":
                resp = self._session.get(f"{self.endpoint_url}/api/tags", timeout=5)
                return resp.status_code == 200
            elif self.provider in ("openai", "openai-compatible"):
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                resp = self._session.get(f"{self.endpoint_url}/v1/models", headers=headers, timeout=5)
                return resp.status_code == 200
            elif self.provider == "anthropic":
                headers = {"anthropic-version": "2023-06-01"}
                if self.api_key:
                    headers["x-api-key"] = self.api_key
                resp = self._session.get(f"{self.endpoint_url}/v1/models", headers=headers, timeout=5)
                return resp.status_code == 200
            elif self.provider == "google":
                params = {"key": self.api_key} if self.api_key else {}
                resp = self._session.get(f"{self.endpoint_url}/v1beta/models", params=params, timeout=5)
                return resp.status_code == 200
            elif self.provider == "azure-openai":
                headers = {}
                if self.api_key:
                    headers["api-key"] = self.api_key
                url = f"{self.endpoint_url}/openai/deployments?api-version=2024-02-01"
                resp = self._session.get(url, headers=headers, timeout=5)
                return resp.status_code == 200
            return False
        except Exception:
            return False

    def unload(self) -> bool:
        """Unload the model from VRAM to free memory.

        For Ollama: sends a generate request with keep_alive=0.
        For LM Studio: uses the native /api/v1/models/unload endpoint.
        For cloud providers: no-op (no VRAM management needed).

        Returns True if the unload request was accepted."""
        import requests
        
        if self.always_on:
            logger.info("Skipping unload for %s (always_on=True)", self.model)
            return True

        if self.provider == "lm-studio":
            from codrag.core.model_readiness import lmstudio_unload
            return lmstudio_unload(self.endpoint_url, self.model)

        if self.provider != "ollama":
            return True  # No-op for cloud providers

        try:
            resp = self._session.post(
                f"{self.endpoint_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": "",
                    "keep_alive": 0,
                    "stream": False,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info("Unloaded model %s from VRAM", self.model)
                return True
            logger.warning("Unload request for %s returned %d", self.model, resp.status_code)
            return False
        except Exception as e:
            logger.warning("Failed to unload model %s: %s", self.model, e)
            return False
