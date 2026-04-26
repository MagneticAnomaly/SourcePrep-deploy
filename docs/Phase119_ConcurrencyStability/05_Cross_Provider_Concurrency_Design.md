# Phase 119 — Cross-Provider Concurrency Design

> Research + design investigation
> Date: 2026-04-26
> Author: Claude (Opus 4.7), reviewed by Eric
> Builds on: 01_Design.md (CDS), 02_Implementation_Plan.md, 04_Swarm_Audit.md
> Status: design proposal — no code yet

## TL;DR

Phase 119 stabilized AIMD growth, but the system still cannot answer the most basic operational question: **"how many concurrent requests can this provider actually accept?"** Live evidence (swarm log `swarm_20260426_131828_swarm_adhoc-42.jsonl`, summarized in §1) shows Ollama Cloud silently queues requests beyond the plan's concurrency limit instead of returning 429 — exactly the case Phase 82 designed away when it disabled queue-time as an "unreliable" signal.

The right answer is provider-specific because the providers are not symmetric:

| Class | Providers | Detection mechanism |
|---|---|---|
| Header-rich | OpenAI, Anthropic, Moonshot Kimi (direct) | Read `*-ratelimit-remaining-*` headers per response — exact, real-time |
| Status-code-rich | Google Gemini | Honor 429 + `retry-after` |
| **Opaque** | **Ollama Cloud** | No headers, no 429 on concurrency overflow — must infer from latency variance |

**Recommended option:** Hybrid — Option C (per-provider signal handlers) backed by Option B (user-visible soft cap with a Probe button). Ollama Cloud, the user's primary backend, has no machine-readable signal so we fall back to plan-tier dropdown (Free=1 / Pro=3 / Max=10) sourced from [ollama.com/pricing](https://ollama.com/pricing) — these are the published numbers, not guesses, and we put the source in the help-text. AIMD continues to operate inside the soft cap.

Phased delivery: **Phase A** (this week) makes the existing `cloud_concurrency` setting a hard cap that AIMD respects (today it's ignored on cloud paths, see `scheduler.py:178`) and surfaces a per-provider recommendation in the settings UI. **Phase B** adds header-driven discovery for OpenAI/Anthropic/Kimi. **Phase C** adds an active probe button and a "real capacity" health view.

---

## Part 1 — Empirical research

### 1.0 The local evidence (why this is not theoretical)

`/Users/ericbintner/.local/share/sourceprep/logs/swarm/swarm_20260426_131828_swarm_adhoc-42.jsonl` records a 24-worker fanout phase against `kimi-k2.6:cloud` (Ollama Cloud Max). All 24 dispatches happen between t=9.030s and t=14.156s — a 5-second burst the client believes is parallel. Completions span t=20.329s through t=49.639s, with `duration_s` values:

```
9.838, 10.383, 11.450, 11.570, 12.644, 16.369, 16.431, 17.724,
18.298, 19.363, 21.109, 22.851, 23.034, 24.492, 25.359, 26.142,
26.203, 28.402, 28.443, 28.819, 29.309, 31.406, 33.613, 37.448
```

That is a near-perfect staircase: roughly batch 1 finishes ~10s, batch 2 ~11–12s, batch 3 ~16–18s, then 21s, 23s, 25s, 28s, 31s, 33s, 37s. The last worker took ~3.8× the first. **Worker durations of identical-shape work should not vary by 4× under truly parallel inference**. The pattern is consistent with Ollama Cloud Max's published concurrency=10 limit ([ollama.com/pricing](https://ollama.com/pricing)): about 10 fire immediately, the rest serialize behind them in roughly 3 cohorts. No 429s, no Retry-After, no error path — server-side queueing.

This is the signal Phase 82 disabled.

### 1.1 Ollama Cloud

| Aspect | Finding | Source |
|---|---|---|
| Concurrency limits | Free=1, Pro=3, Max=10 (concurrent models/requests) | [ollama.com/pricing](https://ollama.com/pricing) |
| RPM/TPM | Not published — usage is GPU-time-billed, not request-rate-capped | [ollama.com/pricing](https://ollama.com/pricing) |
| Concurrency overflow behavior | "Requests beyond your plan's concurrency limit are queued and processed as soon as a slot is available." Queue has fixed depth; if full, **rejected** (no error code published) | [ollama.com/pricing](https://ollama.com/pricing) |
| Hourly/usage-cap behavior | 429 with body `{"error":"you've reached your hourly usage limit, please wait or upgrade"}` | [continuedev/continue#9233](https://github.com/continuedev/continue/issues/9233), [docs.ollama.com/api/errors](https://docs.ollama.com/api/errors) |
| Local OSS overflow behavior | 503 with `{"error":"server busy, please try again"}` once `OLLAMA_MAX_QUEUE` exceeded; otherwise FIFO queue | [docs.ollama.com/faq](https://docs.ollama.com/faq), [glukhov.org](https://www.glukhov.org/llm-performance/ollama/how-ollama-handles-parallel-requests/) |
| Rate-limit headers | None. Ollama Cloud does not expose `x-ratelimit-*`, no quota field in body | [ollama/ollama#15663](https://github.com/ollama/ollama/issues/15663) (filed feature request) |

Validates the user's hypothesis: **Pro=3, Max=10**. Confirmed verbatim from the pricing page.

The error-codes documentation page lists 200 / 400 / 404 / 429 / 500 / 502 — and notably no 429 path for concurrency overflow on cloud, only for hourly limits ([docs.ollama.com/api/errors](https://docs.ollama.com/api/errors)).

### 1.2 OpenAI

| Aspect | Finding | Source |
|---|---|---|
| Tier system | Spend-based (5 tiers: $5 / $50 / $100 / $250 / $1000+ cumulative) | [platform.openai.com/docs/guides/rate-limits](https://platform.openai.com/docs/guides/rate-limits), [inference.net guide](https://inference.net/content/openai-rate-limits-guide/) |
| Tier 1 (representative) | gpt-4o: 500 RPM / 30k TPM. gpt-4o-mini: 500 RPM / 200k TPM. gpt-5: ~1000 RPM / 500k TPM | [inference.net guide](https://inference.net/content/openai-rate-limits-guide/), [scriptbyai 2026](https://www.scriptbyai.com/rate-limits-openai-api/) |
| Tier 5 | gpt-4o: 10k RPM / 800k TPM. gpt-4o-mini: 10k RPM / 4M TPM. gpt-5.2: 10k RPM / 5M TPM | [inference.net guide](https://inference.net/content/openai-rate-limits-guide/), [crazyrouter 2026](https://crazyrouter.com/en/blog/ai-api-rate-limits-every-provider-compared-2026) |
| Concurrent requests | **Not separately limited** — RPM/TPM are the binding constraint | [platform.openai.com/docs/guides/rate-limits](https://platform.openai.com/docs/guides/rate-limits) |
| Headers exposed | `x-ratelimit-limit-requests`, `x-ratelimit-remaining-requests`, `x-ratelimit-reset-requests`, `x-ratelimit-limit-tokens`, `x-ratelimit-remaining-tokens`, `x-ratelimit-reset-tokens`. Plus `Retry-After` on 429. | [platform.openai.com cookbook](https://cookbook.openai.com/examples/how_to_handle_rate_limits) |
| Burst behavior | Hard 429 with `Retry-After` once RPM/TPM exceeded. No silent queueing. | [milvus.io guide](https://milvus.io/ai-quick-reference/how-can-i-handle-rate-limiting-in-the-openai-api) |

OpenAI is the easy case: every response carries the live remaining budget. The right concurrency cap for OpenAI is whatever lets you stay below the RPM/TPM ceiling — and you can read the ceiling on every response.

### 1.3 Anthropic Claude

| Aspect | Finding | Source |
|---|---|---|
| Tier system | Spend-based: Tier 1 ($5) → Tier 4 ($400). Custom > $200k/mo. | [platform.claude.com/docs/en/api/rate-limits](https://platform.claude.com/docs/en/api/rate-limits) |
| Tier 1 | 50 RPM, 30k ITPM, 8k OTPM (Sonnet 4.x, Opus 4.x); 50k ITPM (Haiku 4.5) | same |
| Tier 2 | 1000 RPM, 450k ITPM, 90k OTPM (most models) | same |
| Tier 3 | 2000 RPM, 800k ITPM, 160k OTPM (Sonnet/Opus); 1M ITPM (Haiku 4.5) | same |
| Tier 4 | 4000 RPM, 2M ITPM, 400k OTPM (Sonnet/Opus); 4M ITPM (Haiku 4.5) | same |
| Concurrent requests | **Not separately limited** — RPM is the constraint. Token-bucket algorithm. | same |
| Headers exposed | `anthropic-ratelimit-requests-limit/-remaining/-reset`, `anthropic-ratelimit-tokens-limit/-remaining/-reset`, plus split `input-tokens` and `output-tokens` variants. `retry-after` on 429. | same |
| Burst behavior | Hard 429 with `retry-after` indicating exact wait. Token bucket means short bursts above limit are tolerated; sustained excess gets blocked. | same |
| Special: Cache-aware ITPM | Cache reads do NOT count toward ITPM on Sonnet/Opus 4.x — effective throughput much higher than the headline number | same |

Anthropic is the gold-standard case. Headers are dense and accurate. There's no concurrent-request count to discover; what matters is RPM/TPM headroom.

### 1.4 Google Gemini

| Aspect | Finding | Source |
|---|---|---|
| Tier system | Free / Tier 1 / Tier 2 / Tier 3 (spend-based on Tier 1+) | [ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits), [yingtu.ai 2026](https://yingtu.ai/en/blog/gemini-api-rate-limits-explained) |
| Free tier | 2.5 Pro: 5 RPM / 100 RPD. 2.5 Flash: 10 RPM / 250 RPD. 2.5 Flash-Lite: 15 RPM / 1000 RPD. Shared 250k TPM. | [yingtu.ai 2026](https://yingtu.ai/en/blog/gemini-api-rate-limits-explained) |
| Tier 1 (paid) | 150–300 RPM (model-dependent), several M TPM | same |
| Tier 2/3 | 1000–4000 RPM, larger TPM | [crazyrouter 2026](https://crazyrouter.com/en/blog/ai-api-rate-limits-every-provider-compared-2026) |
| Concurrent requests | **Not separately limited** | inferred — no docs claim a concurrency cap |
| Headers exposed | Limited / inconsistent. Google AI Studio surfaces limits via dashboard. The public API doc does not enumerate `x-ratelimit-*` headers. | [ai.google.dev rate-limits page](https://ai.google.dev/gemini-api/docs/rate-limits) |
| Burst behavior | 429 with quota-exceeded error body. `Retry-After` per HTTP convention. | [cometapi guide](https://www.cometapi.com/how-to-fix-google-gemini-2-5-pro-api-rate-limits/) |
| Free tier December 2025 cuts | RPD quotas reduced in Dec 2025 — limits are unstable, may move again | [aifreeapi.com](https://www.aifreeapi.com/en/posts/gemini-api-free-tier-rate-limits) |

Gemini is the **status-code-rich, header-poor** case. We have to rely on 429 + `Retry-After` rather than predictive headers.

### 1.5 Moonshot Kimi (direct API, NOT via Ollama)

| Aspect | Finding | Source |
|---|---|---|
| Tier system | 6 tiers based on cumulative recharge | [platform.kimi.ai/docs/pricing/limits](https://platform.kimi.ai/docs/pricing/limits) |
| Tier 0 ($0–$1) | **1 concurrent**, 3 RPM, 500k TPM, 1.5M TPD | same |
| Tier 1 ($10) | **50 concurrent**, 200 RPM, 2M TPM, unlimited TPD | same |
| Tier 2 ($20) | **100 concurrent**, 500 RPM, 3M TPM | same |
| Tier 3 ($100) | **200 concurrent**, 5000 RPM, 3M TPM | same |
| Tier 4 ($1000) | **400 concurrent**, 5000 RPM, 4M TPM | same |
| Tier 5 ($3000) | **1000 concurrent**, 10k RPM, 5M TPM | same |
| Headers / error codes | Not documented in the public limits page. Need empirical probe to confirm. | gap |

Kimi direct is unique — it is the only provider that publishes an **explicit concurrency number** per tier. This is the clean "ask the user which tier they're on, hard-cap to that number" case.

### 1.6 Ollama-as-proxy (Kimi/Qwen/DeepSeek/etc via Ollama Cloud)

The Ollama pricing page is unambiguous: cloud limits are **plan-tier-based, not model-based** ([ollama.com/pricing](https://ollama.com/pricing), [ollama.com/blog/cloud-models](https://ollama.com/blog/cloud-models)). Whether you call `kimi-k2.6:cloud`, `qwen3.5:cloud`, or `deepseek-v3.1:671b-cloud`, the binding limit is your Ollama Cloud plan's concurrency (1/3/10) and your hourly/weekly usage cap. The upstream provider's limits do not pass through.

This is structurally different from going direct: a Tier 1 Kimi account ($10) gets you 50 concurrent direct, but only 3 concurrent via Ollama Cloud Pro. We must treat "kimi via Ollama" and "kimi direct" as different endpoints with different caps.

---

## Part 2 — Validating the silent-queue hypothesis

The user already had local evidence (the swarm log). The web research confirms it from the other side:

1. **Ollama's pricing page itself** says concurrency overflow is queued, not rejected: *"Requests beyond your plan's concurrency limit are queued and processed as soon as a slot is available"* ([ollama.com/pricing](https://ollama.com/pricing)). This is a deliberate UX choice on Ollama's part — the alternative (returning 429 immediately) would force every client to implement their own queue, so they queue server-side. The cost is opacity to the client.

2. **The errors documentation** lists 429 only in the context of "rate limit exceeded" (the hourly/weekly cap), not concurrency overflow ([docs.ollama.com/api/errors](https://docs.ollama.com/api/errors)). 503 is documented for OSS-Ollama queue full but the cloud variant doesn't surface it for ordinary concurrency contention.

3. **The ollama/ollama#15663 feature request** explicitly asks Ollama to add `x-ratelimit-*` headers, noting that *"Ollama Cloud API responses do not include account-level quota or usage information"* and calling Ollama "the outlier" versus OpenAI/Anthropic/Google. As of April 2026 the request is open without official response — i.e., **the silent behavior is current-state, not a bug Ollama has acknowledged**.

4. **Local-Ollama benchmarks** (Glukhov, Markaicode, Red Hat ollama-vs-vllm comparison) consistently show cumulative latency under load — *"TTFT rose dramatically with more users because incoming requests had to wait in a queue before being processed"* ([Red Hat](https://developers.redhat.com/articles/2025/08/08/ollama-vs-vllm-deep-dive-performance-benchmarking)). The cloud endpoint inherits this scheduling model.

**Conclusion:** Ollama Cloud silently queues. There is no header signal, no error code, no body field. The only signal available to a client is **wall-clock latency variance under burst load** — exactly what Phase 82 chose to ignore.

This is the same conclusion the swarm log forced. The product implication is structural, not a tweak: Phase 82's bandwidth-probing AIMD cannot discover Ollama Cloud's concurrency limit because the only signal that exists for that limit (latency staircase) was deliberately removed from the input set.

---

## Part 3 — Design strategy

I considered four options. Each is described, then I recommend a hybrid.

### Option A — Re-enable Phase 82's queue-wait-time signal

**Mechanism:** Resurrect the disabled queue-wait-time / latency-variance signal. Maintain a rolling per-slot histogram of `duration_s`. If p95 > 2× p50 and N >= 8 samples, treat as "saturating" → MD by 1 (not by 2). If p99 / p50 < 1.3 across a 30s window, treat as "headroom" → AI.

**Per-provider applicability:** Works for any provider where queue depth maps to latency increase. Best for Ollama Cloud (the only signal). Mediocre for OpenAI/Anthropic/Kimi/Gemini where headers/429s are more direct.

**User interaction:** Zero-config.

**Failure modes:**
- Cold-cache vs warm-cache latency variance is structural in LLMs; we'd see false saturation when nothing is happening. Phase 82 documented this exact concern when disabling the signal.
- Network jitter on the user's home connection bleeds into the histogram. Ericbintner is on a USB-attached drive over a residential connection — our floor variance is high.
- Slow workers don't necessarily mean queueing. Long generations naturally spread.

**Why this isn't sufficient on its own:** the original Phase 82 instinct was correct — pure latency-variance has too much non-queue noise to be a primary signal. But used as a *confirming* signal alongside a hard cap, it's defensible.

### Option B — User-provided soft cap with guidance + Probe button

**Mechanism:** The settings UI has a per-endpoint `max_concurrent` field. Today it exists but is ignored on cloud paths (`scheduler.py:178` returns `min(self.max_concurrent, self.current_limit)` only after deliberately bypassing the clamp for `is_cloud` slots). Re-enable the clamp. Provide a help-text per provider with the documented numbers from §1, and a "Probe" button that fires N parallel calibrated requests, reports the duration histogram, and recommends a value.

**Per-provider applicability:** Universal. The user always wins with a stated number.

**User interaction:** One-time setup per endpoint. Probe takes ~30s, results persist.

**Failure modes:**
- Stale: if the user upgrades their plan, they have to re-probe.
- Wrong tier guess: the dropdown defaults to Pro, user is on Free — over-shoots, hits queue, sees slow runs. Mitigation: "Probe" button verifies.

**Why this is the foundation:** it's the only option that works for Ollama Cloud's silent-queue case. The dropdown is sourced from real published numbers, not invented constants.

### Option C — Per-provider signal handlers (plugin-style discovery)

**Mechanism:** Each provider gets a small `ConcurrencyDiscovery` adapter that knows how to read the signals that provider exposes:

```
class OpenAIDiscovery:    reads x-ratelimit-remaining-requests, predicts saturation
class AnthropicDiscovery: reads anthropic-ratelimit-requests-remaining + tokens
class GeminiDiscovery:    listens for 429 + retry-after; no proactive prediction
class KimiDiscovery:      no headers — uses tier-table lookup keyed on user-set tier
class OllamaDiscovery:    no headers, no 429-on-overflow — uses Option A latency variance
                          *only* when current_limit > tier-cap (i.e. only as a sanity check)
```

**Per-provider applicability:** Universal by construction.

**User interaction:** Zero-config for header-rich providers; one-time tier selection for Kimi/Ollama.

**Failure modes:**
- Adapter rot — when providers add headers (Gemini may), we lag.
- Mis-detection of provider on custom OpenAI-compatible endpoints (LMStudio, vLLM proxies, OpenRouter). Mitigation: explicit provider field already exists in endpoint config.

### Option D — Active probe at first run

**Mechanism:** On first use of an endpoint, the daemon fires a calibrated burst (e.g., 20 short requests in 100ms) and measures the latency curve. Saturation point becomes the persisted ceiling. Periodically re-probe (e.g., once per week) when load is otherwise idle.

**Per-provider applicability:** Universal. Most accurate for Ollama Cloud (where it's the only way).

**User interaction:** Visible at startup as "calibrating concurrency for cloud:default_ollama (15s)…"

**Failure modes:**
- Burns user budget on probes (each request costs cents on most providers).
- First-run latency hit may surprise the user.
- Provider load varies — a probe at 3am may say 10, but at 2pm the user gets 6 with the same plan because Ollama is shedding traffic.

**Where it shines:** as a manual button (Option B's "Probe") rather than automatic.

### Recommended: B + C (with A as a confirming signal, D as the explicit Probe)

Concretely:

1. **Hard cap (B)** drives growth. AIMD operates inside `[min_limit, soft_cap]` where `soft_cap = min(user_setting, tier_table[provider][plan])`. Today AIMD ignores `max_concurrent` on cloud — fix that.
2. **Per-provider discovery (C)** drives the *predictive* signals. Where headers exist, use them. Where they don't, the soft cap is the ceiling and AIMD just operates safely inside it.
3. **Latency variance (A)** is enabled only as a *confirming* signal: if `current_limit == soft_cap` AND p95/p50 > 2 over an 8-request window AND we're an Ollama-class provider, log a "soft-cap may be too high" warning. We do not auto-reduce based on it; we tell the user.
4. **Probe button (D)** is a manual user action attached to each endpoint card in settings. One click, ~30s, displays a histogram and a recommended value.

This addresses the user's three constraints:
- **Validates empirically**: Probe button gives the user a direct answer for their plan.
- **Works for ALL six providers**: the dispatch in (C) covers each cleanly.
- **No hard-coded values**: numbers come from the tier-table loaded from a JSON resource (or from headers, or from the probe). The fallback dropdown shows the *source URL* in help-text and reads the numbers from a versioned config so we can update without a code release.

### Provider-by-provider concurrency strategy

| Provider | Soft-cap source | Live signal | Auto-detect possible? |
|---|---|---|---|
| Ollama Cloud Free | Tier table → 1 | None machine-readable. Latency variance as confirming signal. | No — must use plan dropdown |
| Ollama Cloud Pro | Tier table → 3 | None | No — must use plan dropdown |
| Ollama Cloud Max | Tier table → 10 | None | No — must use plan dropdown |
| Local Ollama (OSS) | `OLLAMA_NUM_PARALLEL` (env probe, fall back to 4) | 503 on queue full | Partial — env probe works |
| OpenAI | Tier table → effective concurrency = floor(RPM × p50_seconds / 60) | `x-ratelimit-remaining-requests` headers | **Yes** — header-driven |
| Anthropic | Tier table; effective concurrency derived from RPM/p50 | `anthropic-ratelimit-*` headers | **Yes** — header-driven |
| Google Gemini | Tier table | 429 + `Retry-After` only | Reactive only — no predictive headers |
| Moonshot Kimi (direct) | Tier table — Kimi publishes explicit concurrency per tier | Need empirical probe | **Yes** — explicit concurrency value per tier |

### Why a "soft cap dropdown" is the right shape, not a regression

The user's prior feedback ([no-hardcoded-cloud-concurrency](MEMORY.md)) is about not baking values into code. The dropdown in this design:

1. Reads its values from `concurrency_limits.json` (a versioned data file we ship and can hot-update).
2. Each entry cites its source URL.
3. The user is the source of truth for "which tier am I on", which we *cannot* know from the API.
4. The Probe button lets the user empirically validate that the dropdown number matches their actual experience.

This is consistent with Phase 82's principle: **don't hardcode behavior**, but it's compatible with **let the user state a fact about themselves** and showing them the published numbers as guidance.

---

## Part 4 — Phased plan

### Phase A — Restore the soft cap (this week)

**Goal:** stop AIMD from ignoring the user's `cloud_concurrency` setting. Surface tier guidance in UI.

**Files affected:**
- `src/prep/services/pipeline/scheduler.py` — line 178 `effective_max()` currently returns `min(max_concurrent, current_limit)` for local but bypasses for cloud (see line 172 comment block). Change to always clamp by `max_concurrent` when `max_concurrent > 0`. A value of `0` means "auto" (Phase 82 unbounded behavior).
- `src/prep/services/pipeline/concurrency_store.py` — persist soft cap alongside discovered ceiling so daemon restart doesn't lose it.
- `src/prep/dashboard/src/components/settings/v2/pages/AIModelsSettings.tsx` (or equivalent) — per-endpoint dropdown with provider-derived defaults + help-text linking to the source URL.
- New: `src/prep/data/concurrency_limits.json` — provider × tier table, ships with the package.
- `src/prep/api/routers/settings.py` — accept `cloud_concurrency` in endpoint payload (it may already be wired; verify).

**Test strategy:**
- Unit: `tests/test_scheduler_soft_cap.py` — set `max_concurrent=3`, jumpstart from 5, assert `effective_max()` returns 3 even pre-edge.
- Live: re-run the rust_repo swarm with `cloud_concurrency=3` for `cloud:default_ollama` (Pro plan match). Expect smooth duration histogram, not the 9.8→37.4 staircase.

**Risk: Low.** The change is "honor a setting that already exists in the schema". Users who never set `cloud_concurrency` (the `=0` default) keep current behavior.

**Status: SHIPPED 2026-04-26.** See `06_Phase_A_Plan.md` for the as-built changes.

Commits (in order):
- `f0a9a2d1` — `dynamic_capacity` respects `max_concurrent` when set
- `5bcacd43` — docstring tightening
- `e68d469c` — `concurrency_limits.json` data file
- `e2023865` — schema validation hardening
- `17be7a06` — `GET /llm/plan-limits` endpoint
- `69f85d9a` — `PlanDropdown` component + Storybook stories
- `7d29435d` — PlanDropdown review fixes
- `9d468f50` — Wire PlanDropdown + save validation
- `ce6f382f` — review fixes (validator scope, test coverage)

Live verification: daemon restarted with new code; `/llm/plan-limits`
returns the 6-provider table; `dynamic_capacity` honors
`max_concurrent` on cloud slots; PlanDropdown renders in
Settings → AI Models.

**Known follow-up (not in Phase A scope):** the warnings array
returned by the validator on `PUT /global/config` is not yet surfaced
to the user. `useLLMConfig.ts` currently discards the response. A
follow-up task should add a notification surface to display these
warnings — e.g. when a user saves a cloud-Ollama endpoint without a
plan tier, they should see "Pick your plan tier — Ollama Cloud
doesn't expose rate-limit headers, so we can't auto-detect it."

### Phase B — Per-provider header-driven discovery

**Goal:** for OpenAI / Anthropic / Kimi-direct, the daemon predicts saturation from response headers and proactively throttles before 429.

**Files affected:**
- New: `src/prep/services/pipeline/discovery/__init__.py` — adapter dispatch.
- New: `src/prep/services/pipeline/discovery/openai_discovery.py` — header parser + budget tracker.
- New: `src/prep/services/pipeline/discovery/anthropic_discovery.py` — same for `anthropic-ratelimit-*`.
- New: `src/prep/services/pipeline/discovery/kimi_discovery.py` — tier-table lookup, no headers.
- New: `src/prep/services/pipeline/discovery/gemini_discovery.py` — reactive 429 + `Retry-After` only.
- New: `src/prep/services/pipeline/discovery/ollama_discovery.py` — tier-table lookup; latency-variance as confirming signal only.
- `src/prep/core/llm_client.py` — capture response headers, route to discovery adapter on each response.
- `src/prep/services/pipeline/scheduler.py` — accept "predicted saturation" hint from discovery; use as input to AIMD's MD path (treat it as a soft-fail signal).

**Test strategy:**
- Mock-server tests for each provider's headers (OpenAI fixture, Anthropic fixture, Kimi/Gemini reactive fixtures). One test per adapter that asserts "header value X → discovery state Y".
- Integration: synthetic 200-request stream against mocked-OpenAI showing limit enforcement before 429 fires.
- Per project memory note `feedback_test_full_import_chain`: at least one end-to-end test must use a real `httpx` mock at the transport layer, not at the discovery layer, so we exercise the header capture seam.

**Risk: Medium.** Provider header schemas drift. Centralize parsing in adapters and have explicit fallbacks: missing header → fall back to soft cap.

**Status: SHIPPED 2026-04-26.** Per-provider header-driven discovery is live for OpenAI and Anthropic; Kimi/Gemini/Ollama route to a no-op adapter and continue relying on the Phase A soft cap. Phase B narrows growth WITHIN the [min, max] band Phase A defined; the `dynamic_capacity` clamp at `max_concurrent` is preserved.

As-built deviations from the plan above:
- The hint-mediated path is the success-side AIMD step, not the MD path. 429s remain the only trigger for multiplicative decrease — saturation hints proactively *prevent* growth into the 429 zone but do not synthesize a backoff event from header readings alone.
- Kimi/Gemini/Ollama adapters were not split into separate files. They share the single `noop_discovery.py` since they all surface the same behavior at this layer (no predictive headers → use Phase A soft cap). Per-tier UI behavior already lives in Phase A's `concurrency_limits.json`.
- Saturation thresholds: `score >= 0.9` is "hard" (jumpstart→congestion_avoidance), `score >= 0.7` is "soft" (skip the +1 / x2). Lifted directly from the spec preamble; documented as `_SAT_HARD` / `_SAT_SOFT` in `scheduler.py`.

Commits (in order):
- `b9fb69eb` — discovery package skeleton (`base.py`, `noop_discovery.py`, dispatch, 11 noop tests)
- `32ffa7df` — OpenAI + Anthropic adapters (23 unit tests across 2 files)
- `1a0d5ccc` — scheduler consumes `SaturationHint` (10 unit tests)
- `9f396037` — `llm_client.py` passes full response headers + status into the scheduler hook

Verification: 75 tests pass (`tests/test_discovery_*.py` + `tests/test_scheduler_saturation_hint.py` + Phase A regression suite). Live verification deferred — Phase B is invisible until OpenAI/Anthropic responses come back, which requires the user to switch providers. Static unit tests are sufficient for ship.

### Phase C — Probe button + capacity health view

**Goal:** explicit user-driven calibration; dashboard panel showing observed-vs-stated capacity.

**Files affected:**
- New: `src/prep/api/routers/compute.py::probe_endpoint` — POST endpoint, fires N=20 calibrated short requests, returns histogram + recommendation.
- New: `packages/ui/src/components/llm/ProbeButton.tsx` — button on each endpoint card; runs probe, displays histogram + suggested value, "Apply" button writes to soft cap.
- `packages/ui/src/components/trace/ConcurrencyHealth.tsx` — extend to show per-endpoint actual vs stated capacity, with a "stale" badge if last probe > 7 days ago.

**Test strategy:**
- API route test: probe endpoint runs in a sandbox, asserts response shape includes `histogram`, `recommended_concurrency`, `confidence`.
- Storybook: `ProbeButton.stories.tsx` covering states (idle / probing / done / error).
- Manual: Probe a real Ollama Cloud endpoint and verify the recommendation matches plan.

**Risk: Low-Medium.** Mostly UI + a bounded backend endpoint. Cost: probes burn a few cents on paid providers — gate behind explicit user click.

**Status: SHIPPED 2026-04-26.** Probe button + Capacity Health panel live in Settings → Diagnostics.

As-built:
- `src/prep/services/pipeline/endpoint_probe.py` — orchestrator + saturation detector. Public entry point: `run_probe(endpoint_id, burst_size=20)`. Burst clamped to `[1, 50]`. Each request uses `max_tokens=1` against the endpoint's lightest model (small_model slot if it points at this endpoint, else a provider-default like `gpt-4o-mini` / `claude-3-5-haiku-latest`). Per-endpoint in-memory ring buffer (last 10) + per-probe JSON record at `<data_dir>/probes/<endpoint_id>_<ts>.json`.
- `POST /compute/endpoint-probe` — fires the burst; returns `{wall_clock_ms{p50,p90,p99}, saturation_point, saturation_method, recommended_concurrent, successes, errors, histogram_path}`. Saturation detection: header hint (Phase B) wins when score ≥ 0.5; otherwise scan the windowed-p90 latency staircase for the first index where p90 > 2× the calibration p50.
- `GET /compute/endpoint-probe/history?endpoint_id=...&limit=10` — recent probes. Falls back to disk-persisted records when the in-memory ring is empty (post-restart).
- `packages/ui/src/components/llm/ProbeButton.tsx` — idle/probing/done/error states; "Apply N to plan" calls `onEdit({...ep, cloud_concurrency: recommended, plan_tier: 'custom'})`. Cloud-only (gated by `providerNeedsCloudPlan`).
- `packages/ui/src/components/concurrency/CapacityHealth.tsx` — sibling to `ConcurrencyHealth`. Per saved cloud endpoint: plan tier + soft cap (Phase A), live AIMD limit + in-flight (Phase 119), saturation pill (Phase B placeholder until a stable API is exposed), last probe summary (Phase C).
- Mounted in `src/prep/dashboard/src/components/settings/v2/pages/Diagnostics.tsx` above the existing Concurrency Health section.

Verification: 10 new probe tests + 36 regression baseline pass (`pytest tests/test_endpoint_probe.py tests/test_concurrency_*.py tests/test_ollama_probe.py`). UI build + dashboard tsc clean. `_dispatch_request` is monkey-patched in tests — no live API calls in CI.

---

## Part 5 — What this answers

| Provider | Can auto-detect concurrency? | Mechanism | Confidence |
|---|---|---|---|
| Ollama Cloud Free | No | User-stated tier (1) | High (published) |
| Ollama Cloud Pro | No | User-stated tier (3) | High (published) |
| Ollama Cloud Max | No | User-stated tier (10) | High (published) |
| Local Ollama (OSS) | Partial | `/api/ps` + `OLLAMA_NUM_PARALLEL` env probe | High |
| OpenAI Tier N | Yes | `x-ratelimit-remaining-requests` header per response | High |
| Anthropic Tier N | Yes | `anthropic-ratelimit-*` headers | Highest (densest header set) |
| Google Gemini | Reactive | 429 + `Retry-After` only — no predictive headers | Medium |
| Moonshot Kimi (direct) | Yes (with tier input) | Published explicit concurrency per tier | High |

**Translation for the user:** auto-detection is real for OpenAI, Anthropic, and Kimi-direct. For Ollama Cloud — the user's primary backend — auto-detection is **not possible** without a deliberate probe, and even the probe only tells you the plan-tier ceiling. The dropdown approach is the right answer there. For Gemini, we can stay safe but we cannot grow proactively; only react to 429.

---

## Open questions / future work

1. **Probe cost on paid providers.** OpenAI Tier 1 probe = 20× short requests ≈ $0.005. Acceptable for a button click, not for automatic re-probing. **Decision:** Phase C button is manual-only.
2. **Ollama Cloud per-model concurrency.** Pricing page says "per model" — does running `kimi-k2.6:cloud` and `gemini-3-flash-preview:cloud` simultaneously give us 2× the cap, or is it 10 total at Max? Empirically testable; flag for the Probe-button validation pass.
3. **Custom OpenAI-compatible endpoints.** OpenRouter, LMStudio, vLLM all advertise OpenAI-compatible APIs but may not return full `x-ratelimit-*` headers. Discovery adapter for "OpenAI-compatible" should fall back to soft cap when headers are missing rather than assume infinite.
4. **Anthropic 429 acceleration limits.** Documented behavior: a sharp ramp-up triggers 429 even below RPM. The discovery adapter needs to handle this — treat acceleration-limit 429s as a temporary signal, not as our usual MD edge.
5. **Whether to expose the soft cap as a single dropdown of plan names** (Free / Pro / Max → 1 / 3 / 10) **or a free-form integer**. Recommend dropdown with "Custom…" override; reduces user error and makes the source citation cleaner.

---

## References

External:
- [ollama.com/pricing](https://ollama.com/pricing)
- [docs.ollama.com/cloud](https://docs.ollama.com/cloud)
- [docs.ollama.com/faq](https://docs.ollama.com/faq)
- [docs.ollama.com/api/errors](https://docs.ollama.com/api/errors)
- [ollama/ollama#15663 — feature request to expose quota headers](https://github.com/ollama/ollama/issues/15663)
- [ollama/ollama#15453 — Cloud reliability issues](https://github.com/ollama/ollama/issues/15453)
- [continuedev/continue#9233 — deepseek 429 on Ollama Cloud](https://github.com/continuedev/continue/issues/9233)
- [glukhov.org — How Ollama Handles Parallel Requests](https://www.glukhov.org/llm-performance/ollama/how-ollama-handles-parallel-requests/)
- [Red Hat — Ollama vs vLLM benchmark](https://developers.redhat.com/articles/2025/08/08/ollama-vs-vllm-deep-dive-performance-benchmarking)
- [platform.openai.com/docs/guides/rate-limits](https://platform.openai.com/docs/guides/rate-limits)
- [cookbook.openai.com — How to handle rate limits](https://cookbook.openai.com/examples/how_to_handle_rate_limits)
- [inference.net — OpenAI rate limits 2026 guide](https://inference.net/content/openai-rate-limits-guide/)
- [scriptbyai 2026 — OpenAI API rate limits update](https://www.scriptbyai.com/rate-limits-openai-api/)
- [platform.claude.com/docs/en/api/rate-limits](https://platform.claude.com/docs/en/api/rate-limits)
- [ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [yingtu.ai 2026 — Gemini rate limits](https://yingtu.ai/en/blog/gemini-api-rate-limits-explained)
- [aifreeapi.com — Gemini free tier 2026](https://www.aifreeapi.com/en/posts/gemini-api-free-tier-rate-limits)
- [platform.kimi.ai/docs/pricing/limits](https://platform.kimi.ai/docs/pricing/limits)
- [crazyrouter.com — AI API rate limits compared 2026](https://crazyrouter.com/en/blog/ai-api-rate-limits-every-provider-compared-2026)

Internal:
- `docs/Phase119_ConcurrencyStability/01_Design.md` — Phase 119 CDS spec
- `docs/Phase119_ConcurrencyStability/04_Swarm_Audit.md` — swarm orchestration audit
- `docs/Phase82_CloudPipelineConcurrency/` — Phase 82 design (the AIMD that disabled queue-time signal)
- `~/.local/share/sourceprep/logs/swarm/swarm_20260426_131828_swarm_adhoc-42.jsonl` — local evidence log
- `src/prep/services/pipeline/scheduler.py:178` — `effective_max()` cloud-bypass
