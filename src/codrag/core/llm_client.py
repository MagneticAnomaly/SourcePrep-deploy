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

    Handles think tags, markdown code fences, truncated JSON, and
    various model output quirks across Qwen3, DeepSeek-R1, and others.
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
    # Try finding first { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    # Truncated JSON repair: we have '{' but no '}' (LLM output was cut off)
    # Also try repair when } exists but parsing failed (} inside a string value)
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
                # Scale budget for thinking overhead, but cap at 24576 to
                # prevent runaway generation on small prompts (e.g., a 500-token
                # audit prompt with np=16384 would otherwise get 49K budget,
                # causing 30+ min of thinking for no benefit).
                effective_num_predict = min(
                    max(num_predict * 3, num_predict + 8192),
                    max(num_predict, 24576),  # never less than base, capped at 24K
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
                "stream": True,
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
            
            # Use stream=True so Ollama sends token-by-token.  This lets
            # the requests read-timeout fire if the model stalls (stream=False
            # holds the connection open with zero data until done, making
            # timeouts impossible).
            resp = requests.post(url, json=payload, timeout=(30, self.timeout), stream=True)
            resp.raise_for_status()
            # Accumulate streamed NDJSON chunks into a single response,
            # with OutputMonitor guarding against repetition loops.
            monitor = OutputMonitor(max_chars=max_chars) if max_chars else None
            text_parts = []
            thinking_parts = []
            tokens = 0
            aborted = False
            abort_reason = ""
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                chunk = json.loads(raw_line)
                resp_chunk = chunk.get("response", "")
                text_parts.append(resp_chunk)
                thinking_parts.append(chunk.get("thinking", ""))
                # Feed response chunks (not thinking) to the monitor
                if monitor and resp_chunk:
                    should_abort, reason = monitor.feed(resp_chunk)
                    if should_abort:
                        aborted = True
                        abort_reason = reason
                        logger.warning("OutputMonitor aborted: %s", reason)
                        break
                if chunk.get("done"):
                    tokens = chunk.get("eval_count", 0) + chunk.get("prompt_eval_count", 0)
                    break
            resp.close()
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
            
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            
            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})
            tokens = usage.get("total_tokens", 0)
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
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            # Anthropic returns content as a list of blocks
            content_blocks = data.get("content", [])
            text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
            usage = data.get("usage", {})
            tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
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

            resp = requests.post(url, json=payload, headers=headers, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})
            tokens = usage.get("total_tokens", 0)
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
            resp = requests.post(url, json=payload, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            candidates = data.get("candidates", [{}])
            parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
            text = "".join(p.get("text", "") for p in parts)
            usage = data.get("usageMetadata", {})
            tokens = usage.get("totalTokenCount", 0)
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
            "stream": True,
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

        resp = requests.post(url, json=payload, timeout=(30, self.timeout), stream=True)
        resp.raise_for_status()

        # Parse SSE stream
        monitor = OutputMonitor(max_chars=max_chars) if max_chars else None
        text_parts: list = []
        thinking_parts: list = []
        tokens = 0
        aborted = False
        abort_reason = ""

        for raw_line in resp.iter_lines(decode_unicode=True):
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
                tokens = stats.get("input_tokens", 0) + stats.get("total_output_tokens", 0)
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

        return text, tokens

    def is_available(self) -> bool:
        """Check if the endpoint is reachable."""
        import requests
        try:
            if self.provider == "lm-studio":
                from codrag.core.model_readiness import lmstudio_server_reachable
                return lmstudio_server_reachable(self.endpoint_url)
            elif self.provider == "ollama":
                resp = requests.get(f"{self.endpoint_url}/api/tags", timeout=5)
                return resp.status_code == 200
            elif self.provider in ("openai", "openai-compatible"):
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                resp = requests.get(f"{self.endpoint_url}/v1/models", headers=headers, timeout=5)
                return resp.status_code == 200
            elif self.provider == "anthropic":
                headers = {"anthropic-version": "2023-06-01"}
                if self.api_key:
                    headers["x-api-key"] = self.api_key
                resp = requests.get(f"{self.endpoint_url}/v1/models", headers=headers, timeout=5)
                return resp.status_code == 200
            elif self.provider == "google":
                params = {"key": self.api_key} if self.api_key else {}
                resp = requests.get(f"{self.endpoint_url}/v1beta/models", params=params, timeout=5)
                return resp.status_code == 200
            elif self.provider == "azure-openai":
                headers = {}
                if self.api_key:
                    headers["api-key"] = self.api_key
                url = f"{self.endpoint_url}/openai/deployments?api-version=2024-02-01"
                resp = requests.get(url, headers=headers, timeout=5)
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
            resp = requests.post(
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
