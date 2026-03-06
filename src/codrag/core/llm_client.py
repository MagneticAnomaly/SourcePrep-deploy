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
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


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
    ):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.model = model
        self.provider = provider
        self.api_key = api_key
        self.timeout = timeout
        self.always_on = always_on

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        num_predict: int = 2048,
        json_mode: bool = True,
        temperature: float = 0.1,
        response_schema: Optional[Dict[str, Any]] = None,
        think: Optional[bool] = None,
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
        """
        import requests

        # lm-studio uses the OpenAI-compatible API — alias it so the dispatch
        # below routes to the correct /v1/chat/completions path
        effective_provider = "openai-compatible" if self.provider == "lm-studio" else self.provider

        if effective_provider == "ollama":
            options: Dict[str, Any] = {
                "temperature": temperature,
                "num_predict": num_predict,
                "top_k": 20,
                "top_p": 0.95,
            }
            payload: Dict[str, Any] = {
                "model": self.model,
                "prompt": prompt,
                "stream": True,
                "options": options,
            }
            # Disable thinking mode to skip massive thinking token overhead.
            # Qwen3.5 generates 2000-5000 thinking tokens (3-5 min) before
            # answering.  Disabling thinking cuts this to ~30-60s per item
            # while still leveraging the full 27.8B dense model quality.
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
            # Use stream=True so Ollama sends token-by-token.  This lets
            # the requests read-timeout fire if the model stalls (stream=False
            # holds the connection open with zero data until done, making
            # timeouts impossible).
            resp = requests.post(url, json=payload, timeout=(30, self.timeout), stream=True)
            resp.raise_for_status()
            # Accumulate streamed NDJSON chunks into a single response
            text_parts = []
            thinking_parts = []
            tokens = 0
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                chunk = json.loads(raw_line)
                text_parts.append(chunk.get("response", ""))
                thinking_parts.append(chunk.get("thinking", ""))
                if chunk.get("done"):
                    tokens = chunk.get("eval_count", 0) + chunk.get("prompt_eval_count", 0)
                    break
            resp.close()
            text = "".join(text_parts)
            thinking = "".join(thinking_parts)
            # Ollama's new engine (Sept 2025+) puts thinking model output
            # in a separate "thinking" field.  For qwen3.5, deepseek-r1,
            # and other reasoning models, the JSON answer may land in
            # "thinking" while "response" is empty.  Concatenate both so
            # _parse_json_response / _strip_think_tags can handle it.
            if thinking and not text:
                # Model put everything in thinking field (common with format=json)
                text = thinking
            elif thinking and text:
                # Model has both thinking and response — wrap thinking in
                # tags so _strip_think_tags can remove it cleanly.
                text = f"<think>{thinking}</think>{text}"
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
            return text, tokens

        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")


    def is_available(self) -> bool:
        """Check if the endpoint is reachable."""
        import requests
        effective_provider = "openai-compatible" if self.provider == "lm-studio" else self.provider
        try:
            if effective_provider == "ollama":
                resp = requests.get(f"{self.endpoint_url}/api/tags", timeout=5)
                return resp.status_code == 200
            elif effective_provider in ("openai", "openai-compatible"):
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                resp = requests.get(f"{self.endpoint_url}/v1/models", headers=headers, timeout=5)
                return resp.status_code == 200
            elif effective_provider == "anthropic":
                headers = {"anthropic-version": "2023-06-01"}
                if self.api_key:
                    headers["x-api-key"] = self.api_key
                resp = requests.get(f"{self.endpoint_url}/v1/models", headers=headers, timeout=5)
                return resp.status_code == 200
            elif self.provider == "google":
                params = {"key": self.api_key} if self.api_key else {}
                resp = requests.get(f"{self.endpoint_url}/v1beta/models", params=params, timeout=5)
                return resp.status_code == 200
            return False
        except Exception:
            return False

    def unload(self) -> bool:
        """Unload the model from VRAM to free memory.

        For Ollama: sends a generate request with keep_alive=0.
        For OpenAI-compatible: no-op (cloud models don't need VRAM management).

        Returns True if the unload request was accepted.
        """
        import requests
        
        if self.always_on:
            logger.info("Skipping unload for %s (always_on=True)", self.model)
            return True

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
