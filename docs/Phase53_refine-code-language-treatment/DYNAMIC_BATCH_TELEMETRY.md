# Sprint 1: Dynamic Batching & Exploratory Telemetry

## Problem Statement

When using cloud LLMs (OpenAI, Anthropic, Gemini, Groq) for structured batch generation, requests can fail for two primary reasons:
1. **API / Hardware Overload:** Rate limits (HTTP 429), timeouts, or 500/503 errors.
2. **Parsing / Format Failures:** The LLM successfully replied, but the JSON output string was malformed, incomplete, or deviated from the required schema.

If a batch (e.g., size=5) fails, a naive fallback strategy simply drops the batch size to 1 and processes the items individually. However, this is suboptimal:
1. We lose the efficiency of batching permanently for that run.
2. We don't learn *why* size 5 failed or if size 4, 3, or 2 would have succeeded under current conditions.
3. We have no data to tune robust, dynamic fallback algorithms for production.

## Goal

Design an **Exploratory Telemetry Strategy** into the augmentation pipeline. During our testing phases, when a batch fails, we want to intentionally gather data by trying various fallback batch sizes/variations. This rich telemetry will allow us to observe failure thresholds across different cloud models and design a bulletproof, data-driven dynamic batching and rate-limit recovery algorithm.

---

## Proposed Architecture

### 1. Enhanced `AugmentResult` Telemetry (Validation)
Building on the `items_batched`, `batches_attempted`, and `batches_failed` telemetry recently added to `AugmentResult` in `augmenter.py`, we will add structural tracking for failure scenarios:

```python
@dataclass
class RetryTelemetry:
    original_batch_size: int
    attempted_batch_size: int
    failure_type: str  # "rate_limit_429", "timeout", "parse_error", "server_5xx"
    retry_delay_ms: int
    success: bool
    tokens_used: int
    duration_ms: float
    model: str
```

### 2. The Exploratory Fallback Engine

We will introduce a `BatchRetryStrategy` class in `src/codrag/core/batch_strategy.py`.
When `_call_batch` throws an exception, it enters the fallback engine.

```python
class BatchRetryStrategy:
    """Manages adaptive and exploratory retries for failed LLM batches."""
    
    def __init__(self, mode: str = "exploratory"):
        self.mode = mode # "exploratory" or "production_safe"
    
    def calculate_next_attempts(
        self, 
        failed_items: List[Dict], 
        error_type: str
    ) -> List[List[Dict]]:
        """
        Given a failed batch and the reason it failed, determine how to split it up 
        for the next attempts.
        """
        # If the API is overloaded (429/500/timeout), we might want to try the same 
        # batch size again, but after an exponential backoff.
        # However, for our 'exploratory' testing phase, we want to test boundaries:
        if self.mode == "exploratory":
            size = len(failed_items)
            
            # Example: If size 5 failed due to parsing, try size 3 + 2.
            # If those fail, try 1s.
            if size == 5:
                # Return list of batches to execute next
                return [failed_items[:3], failed_items[3:]]
            elif size == 3 or size == 2:
                # Split into 1s
                return [[item] for item in failed_items]
            else:
                return [] # size 1 failed, we tried everything
```

### 3. Modifying `augmenter.py` Batch Dispatch

We will refactor the batch dispatch logic in `augmenter.py` (e.g. `_call_file_batch`, `_call_doc_batch`) to utilize this strategy:

```python
def _process_with_exploratory_fallback(self, items: List[Dict], prompt_builder_fn, system_msg, schema):
    results = []
    queue = [items] # List of batches to process
    
    while queue:
        current_batch = queue.pop(0)
        start_time = time.time()
        
        try:
            # 1. Attempt LLM generation
            parsed = self._execute_batch(current_batch, prompt_builder_fn, system_msg, schema)
            results.extend(parsed)
            
            # Record Success Telemetry
            self._record_telemetry(success=True, size=len(current_batch), time=time.time()-start_time)
            
        except BatchParseError as e:
            # 2. Record Parse Failure Telemetry
            self._record_telemetry(success=False, size=len(current_batch), reason="parse_error")
            
            # 3. Calculate exploratory fallback
            next_batches = self.retry_strategy.calculate_next_attempts(current_batch, "parse_error")
            
            # Prepend to queue to process immediately
            queue = next_batches + queue
            
        except LLMAPITimeoutError as e:
            # Similar handling for network/API limits
            pass
            
    return results
```

### 4. Telemetry Output & Extensibility

All retry events (`RetryTelemetry`) will be flushed to an `exploratory_retries.jsonl` file in the `.codrag/logs` folder at the end of the pipeline run.

Later, we can run analytics scripts over this data to answer questions like:
- "Does `kimi-k2.5:cloud` consistently fail parsing at batch size 5, but succeed 99% of the time at batch size 3?"
- "Do 429 Rate Limits from Anthropic recover faster if we wait 2 seconds vs 5 seconds?"
- "Which content classes (docs vs code) trigger the most parse fail fallbacks?"

## Implementation Plan (Tasks)

1. **Task 1.1:** Define `RetryTelemetry` dataclass and append logic to sink data to `logs/exploratory_retries.jsonl`.
2. **Task 1.2:** Create `BatchRetryStrategy` in `batch_strategy.py` with an "exploratory" mode that tests different subdivisions of failed batches.
3. **Task 1.3:** Refactor `_call_*_batch` functions in `augmenter.py` to use a queue-based or recursive fallback approach utilizing the `BatchRetryStrategy`.
4. **Task 1.4:** Update `AugmentResult` accumulation so that the new deep retry loops cleanly add to `items_batched`, `batches_failed`, and `synthetic_reasons`.
