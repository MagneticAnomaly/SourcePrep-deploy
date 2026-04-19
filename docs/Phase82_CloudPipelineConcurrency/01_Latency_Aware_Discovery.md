# Latency-Aware Discovery (AIMD + BBR) for LLM Concurrency

> **Status: SHIPPED (2026-04-18)** — Phase 82 completion landed on `main`.
> Cloud LLM concurrency is discovered at runtime via latency-aware AIMD,
> seeded at a jumpstart of 5, and is **unbounded** on the upward path.
> Discovered ceilings persist across daemon restarts via
> `ConcurrencyStore` (SQLite, per node_id + model_family).
> Implementation lives in `src/codrag/services/pipeline/scheduler.py`
> and `src/codrag/core/concurrency_store.py`.
>
> Historical note: this doc is the *spec*. For the delta between the
> earlier Phase 82 plan and what actually shipped, see
> `05_Completion_Plan.md`.
>
> Phase 82 reference document
> Date: 2026-04-07
> Purpose: Specify the dynamic concurrency scaling algorithm to optimally utilize both Ollama's local/cloud boundaries and API rate-limited components.

## Problem Statement

Earlier pipeline phases hardcoded LLM batch concurrency budgets (e.g. 100 for Cloud models, 1 for local Ollama instances).

This presents three critical issues:
1. **Ollama Cloud / Pro Max Plans:** Some Ollama instances are hosted on large cloud clusters (e.g., maximum limits of 12 parallel requests and 512 queued requests). If we only dispatch 1 at a time, we waste capacity.
2. **Silent Queuing:** If we dispatch 100 requests to an Ollama server that only supports 5 concurrently, Ollama does not return an HTTP 429 Rate Limit error. It silently accepts them and places them into an unbounded queue (e.g., 512 queue size). The requests then sit there until they time out from the client's perspective, or arbitrarily complete 5 minutes later, rendering typical naive 429-based rate limit discovery useless.
3. **Starvation vs Pipeline Greed:** Setting the max parallelism to match the provider's max limits allows one monolithic pipeline or Swarm block to lock down the entire connection, starving sideband tasks (e.g., CoDRAG MCP background tasks or real-time UI contextual searches) from proceeding until the queue clears out.

## Solution Strategy: Latency-Aware Discovery

We solve all three challenges using a hybrid Additive Increase / Multiplicative Decrease (AIMD) algorithm heavily inspired by modern TCP congestion control schemes like BBR (Bottleneck Bandwidth and Round-trip propagation time). 

### 1. Queue Detection via Meta-Latency
To detect when we have exceeded Ollama's concurrency limit without relying on 429s or blindly testing 512 requests:
* Ollama provides exact execution metrics in its JSON response payload: `prompt_eval_duration`, `eval_duration`, and `load_duration`.
* We measure the absolute "wall clock" turnaround time from HTTP socket initiation to JSON digestion (`total_duration`).
* **Wait Time = `total_duration` - (`eval_duration` + `prompt_eval_duration` + `load_duration`)**
* If **Wait Time > 2.0 seconds**, we know the request spent the majority of its lifespan waiting in the host's queue. We have exceeded the true backend execution concurrency limit.
* For standard Cloud Provider APIs (Anthropic, OpenAI), we use standard `x-ratelimit-remaining` HTTP Headers, or catch general `HTTP Timeouts` (which acts as proxy for overwhelmed servers).

### 2. Rapid Jumpstart (Slow-Start)
To rapidly determine if an LLM is supporting 1, 5, 12, or 100 parallel requests, the system starts with a `current_limit` of 5. It continuously doubles this limit upon completing successful batches (e.g. 5 $\rightarrow$ 10 $\rightarrow$ 20 $\rightarrow$ 40) right up until the "Queue Detection" trips (because wait times spiked). This prevents taking 500 iterations to discover the true ceiling.

### 3. Backoff & Multiplicative Decrease
Upon detecting a queue bloat, an HTTP Timeout, or an HTTP 429, the orchestrator triggers a Multiplicative Decrease:
* It sets `current_limit = min(current_limit * 0.5, current_in_flight_count)`.
* Disables `jumpstart` mode and enters a cautious `congestion_avoidance` mode where limit increases are extremely slow.

### 4. Headroom Margin (Reserve Slots)
When providing an available concurrency number back to consumers (e.g. `available_batch_workers()`), the `PipelineScheduler` clamps the allocation to `max(1, discovered_limit - 1)` (or `limit * 0.9` for N > 20). 

This enforces a **Priority Lane reserve slot**: leaving one concurrency slot intentionally untouched by heavy Swarm batches so that interactive agent tasks or MCP tools never hang trying to run a simple context query. 
