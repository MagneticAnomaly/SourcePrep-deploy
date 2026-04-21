# Swarm UI & Configuration Plan — v2

> **Status:** Cleaned, math-verified, agent stack optimized for **quality first, throughput second**.
> v1 lives at `SWARM_UI_PLAN.md` for diff comparison.
> **Primary success metric:** synthesis quality (concept coverage, JSON validity rate, group-reasoning depth). Throughput is the secondary tiebreaker.

---

## 1. The Problem: The "Thinking" Slot Overload

Prep's `Large` (Thinking) slot currently serves a dual purpose in the Deep Enrichment pipeline:

1. **Individual file reasoning (Worker):** Per-file epistemic analysis on single files and their structural neighbors.
2. **Swarm orchestration (Coordinator + Synthesis):** Reading hundreds of file summaries, partitioning them into clusters, and synthesizing the final Domain Modules.

This becomes a problem with frontier open-weight reasoning models:

- **Kimi 2.5** is excellent at individual file reasoning, but a poor Swarm Coordinator — it hits token exhaustion (Bug F-29) writing `<think>` tags and fails to emit the rigid JSON routing schemas that the Swarm fan-out requires.
- **Gemini 3 Flash** is fast, has a 1M-token context window, and produces JSON without thinking overhead — but users currently cannot assign it as the Coordinator while keeping Kimi as the deep-thinking Worker.

## 2. Proposed Solution: Decoupled Swarm Slots

Separate the single `Large` configuration into distinct Swarm roles so users can run hybrid multi-model strategies.

> **Important:** The new `coordinator` slot drives **both** Swarm Phase 1 (planning) and Phase 3 (synthesis). Both phases share the same model profile: large context window, JSON-reliable output, low reasoning depth. Phase 2 (fan-out) is the only role for the Worker (thinking) slot.

If the Coordinator is unassigned, Prep falls back to using `Large` for both phases (preserves backward compatibility).

### Config schema (`packages/ui/src/types.ts` and `src/prep/services/config_manager.py`)

```json
"llm": {
  "small":       { "endpoint_id": "cloud", "model": "gemini-3-flash-preview:cloud" },
  "large":       { "endpoint_id": "cloud", "model": "kimi-k2.5:cloud" },
  "coordinator": { "endpoint_id": "cloud", "model": "gemini-3-flash-preview:cloud" },
  "code":        { "endpoint_id": "cloud", "model": "qwen3-coder-next:cloud" }
}
```

### Backend changes (`src/prep/core/swarm_orchestrator.py`)

The `SwarmOrchestrator` constructor currently accepts a single `llm: LLMClient`. Update to:

```python
class SwarmOrchestrator:
    def __init__(
        self,
        coordinator_llm: LLMClient,   # Phase 1 (planning) + Phase 3 (synthesis)
        worker_llm: LLMClient,        # Phase 2 (fan-out)
        # ...
    ):
```

Plumbing changes flow through `deep_enrichment.py`, `cluster.py`, `group_reasoning.py`, `concept_seeder.py`, and `atlas/generator.py` — every existing `SwarmOrchestrator(...)` call site.

If `coordinator_llm` is None at construction, fall back to `worker_llm` (inherit-from-Thinking behavior, surfaced in UI as a toggle).

## 3. UI Implementation (`AIModelsSettings.tsx`)

### Visual layout

A new card for Swarm Orchestration sits directly beneath the Thinking Model.

1. **⚡ Fast Model (Small)** — file cataloguing, intent detection
2. **🧠 Thinking Model (Large / Swarm Worker)** — deep reasoning, epistemic enrichment, Swarm fan-out
3. **🐝 Swarm Coordinator (NEW)** — cluster routing, large-context synthesis
   - **UI state:** "Inherit from Thinking Model" toggle (default ON for new users) so simple setups don't require explicit configuration.
4. **💻 Code Model** — edge discovery, structural tracing

### Component modifications

- **`ModelCard.tsx`** — add support for `'coordinator'` slot type.
- **`AIModelsSettings.tsx`** — render the new Swarm Coordinator `ModelCard`; update `RECOMMENDED_MODELS` (see §4).
- **`useDashboardPanels.tsx`** — wire the `'coordinator'` slot to the backend config save loop.

## 4. Recommended LLM Stack

The product is now centered on the **two-cloud-model Swarm**: Kimi 2.5 reasoning + Gemini 3 Flash orchestration. Local-only stacks remain supported but are not the primary recommendation.

### Primary stack (recommended for all users with cloud access)

| Slot | Model | Why |
|---|---|---|
| **Small** | `gemini-3-flash-preview:cloud` | Cheap, fast, JSON-reliable. No reason to run a weak local model when Gemini Flash handles cataloguing better at near-zero cost. |
| **Large (Swarm Worker)** | `kimi-k2.5:cloud` | Best-in-class open-weight reasoning. 256K context. Use `think=True` for deep per-file analysis. |
| **Coordinator (Phase 1 + 3)** | `gemini-3-flash-preview:cloud` | 1M context window — can swallow all worker outputs in one synthesis call. No thinking overhead → reliable JSON. |
| **Code** | `qwen3-coder-next:cloud` | Cloud-hosted code-specialized model. 256K context. Used for edge discovery, structural tracing. |

### Fallback stack (no cloud / air-gapped)

| Slot | Model |
|---|---|
| Small | `gemma3:12b` |
| Large | `gemma3:27b` (or any local 27B+ instruct model) |
| Coordinator | `gemma3:27b` (via inherit toggle) |
| Code | `qwen3-coder-next:cloud` if available, else `qwen3-coder` local |

> **Removed from `RECOMMENDED_MODELS`:** `qwen3:4b`, `qwen3:8b`, `qwen3:14b`, `qwen3:30b`. The qwen3 base family is too weak for reliable structured-JSON output at the small slot and has been superseded by qwen3.5 / Gemma3 in our internal testing. `qwen3-coder` (and `qwen3-coder-next:cloud`) remain — they're the only qwen3-family models retained.

### Updated `RECOMMENDED_MODELS` constant (`packages/ui/src/components/llm/AIModelsSettings.tsx`)

```ts
const RECOMMENDED_MODELS: Record<string, string[]> = {
  embedding:   ['nomic-embed-text', 'nomic-embed-code'],
  small:       ['gemini-3-flash-preview:cloud', 'gemma3:12b'],
  large:       ['kimi-k2.5:cloud', 'gemma3:27b'],
  coordinator: ['gemini-3-flash-preview:cloud', 'gemma3:27b'],
  code:        ['qwen3-coder-next:cloud', 'qwen3-coder'],
};
```

## 5. Benefits of this Architecture

1. **Quality:** Routes JSON-heavy orchestration to a model that doesn't think, and reasoning-heavy file analysis to a model that thinks well. Each slot runs a model whose strengths match its job — which lifts synthesis quality and eliminates F-29 thinking-bug stalls.
2. **Cost efficiency:** Small + Coordinator share Gemini Flash (cheap, low GPU time). Worker spends GPU time only where it matters — deep per-file reasoning.
3. **Extensibility:** Positions Prep cleanly for future massive-context routing tasks as more 1M+ context models emerge.

## 6. Cloud Optimization (Advanced Settings)

The defaults above are calibrated for the Ollama Cloud Pro/Max plans. Power users on the Max plan ("deep pockets") can override safety limits via a new **Advanced Settings** panel. All overrides default to OFF (safe) so the out-of-the-box experience matches the documented profile sizes.

### 6.1 Make the `CLOUD_SMALL` (16K) bottleneck configurable

**File:** `src/prep/core/batch_profiles.py`

Currently, any model containing `:cloud` is forced into `CLOUD_SMALL` (16K output cap, batch sizes 3–8). The 16K cap reflects two compounding constraints:

- Ollama Cloud's hard 16K server-side output cap.
- Thinking models (Kimi) burn output budget on `<think>` preamble, leaving even less for JSON.

**Action:** Add an Advanced Settings toggle: **"Enforce Cloud Token Safety Limits"** (default: ON).

**Impact when disabled (Max-plan users):**
- `gemini-3-flash-preview:cloud` → promote to `LARGE` profile (64K output, batch sizes from §LARGE in `batch_profiles.py`).
- `qwen3-coder-next:cloud` → promote to `STANDARD` (32K output).
- `kimi-k2.5:cloud` → **stays on `CLOUD_SMALL`-equivalent batch sizes** even when promoted, because the thinking-preamble constraint is independent of the 16K cap. (Worker batch sizing is ultimately governed by §7.)

### 6.2 Make Kimi's thinking budget configurable

**File:** `src/prep/core/llm_client.py`

Currently, when `think=True`, Prep caps `num_predict` at 24,576 to prevent runaway billing.

**Action:** Surface this cap in Advanced Settings as **"Max Thinking Budget"** (default: 24,576).

**Impact:** Max-plan users can uncap (or raise to 65K) for `kimi-k2.5:cloud`. We *want* Kimi to think extensively about complex domain logic. If billing isn't a concern, give it the full reasoning budget.

### 6.3 Maximize Swarm concurrency (dynamic throttling)

**Files:** `src/prep/core/swarm_orchestrator.py`, `src/prep/core/cluster.py`, `src/prep/core/batch_profiles.py`

**F-59 status (verified 2026-04-12, see `docs/Phase79_Swarm/07_Rework/SWARM_HANG_INVESTIGATION.md`):** The daemon-hang root cause was identified as compounding timeout misconfiguration (600s HTTP timeout, no per-worker timeout, zombie coordinator connections). It was fixed via per-worker timeouts (120s cloud / 300s local), wall-time caps (600s cloud / 1800s local), and zombie-session cleanup. **The hang itself is resolved.** Concurrent cloud requests now work end-to-end inside the daemon.

**Stale code to remove:** `batch_profiles.py:get_batch_concurrency()` still hardcodes `return 1` for cloud models with the comment "F-59 WORKAROUND — cloud models forced sequential". This is now obsolete and must be replaced with the plan-tier-aware logic below.

**Real limitation today:** Ollama Cloud's per-plan concurrency tier:
- Free plan: 1 concurrent model
- Pro plan: 3 concurrent models
- Max plan: 10 concurrent models

**Action:** Expose **"Ollama Cloud Plan"** selector in Advanced Settings (Free/Pro/Max/Custom). The selected tier is the upper bound for the `ThreadPoolExecutor` in Swarm fan-out — the optimizer in §7 then picks the actual concurrency for each phase.

**Impact:** A Max-plan user can consistently push 10 concurrent Kimi workers, maximizing throughput for deep reasoning passes.

### 6.4 Implementation TODOs (Advanced Settings)

- [ ] Build "Advanced LLM Settings" UI panel (nested under or near AI Models).
- [ ] Add "Enforce Cloud Token Safety Limits" toggle (default ON). Wire to `is_cloud_model_via_ollama` / `resolve_profile` in `batch_profiles.py`.
- [ ] Add "Max Thinking Budget" input (default 24,576). Wire to `llm_client.py` to override the hardcap when `think=True`.
- [ ] Add "Ollama Cloud Plan" selector (Free/Pro/Max/Custom). Wire to `get_batch_concurrency()` and the optimizer in §7.
- [ ] Remove the stale F-59 hardcap (`return 1`) from `batch_profiles.py:get_batch_concurrency()` and replace with the tier-aware logic.

## 7. Dynamic Swarm Batching & Concurrency Optimizer

Static batch profiles can't optimize across plan tiers and per-phase intent. We introduce a runtime calculator in `src/prep/core/swarm_optimizer.py` (new file, exported from `batch_profiles.py` for backward compatibility).

### Constraints

1. **Plan tier** caps concurrency: Free=1, Pro=3, Max=10.
2. **Billing is GPU-time-based** — heavy reasoning (Kimi, `think=True`) costs exponentially more than fast processing (Gemini).
3. **Quality first:** small batches give Worker models more attention per item; large batches let Synthesis see cross-cutting structure.

### Tool: `get_optimal_swarm_config(model_id, plan_tier, total_work_items, role) -> SwarmConfig`

#### 7.1 Worker (Kimi) — Phase 2 fan-out

Goal: deep reasoning per file. Maximize concurrency first, then size batches to cover the remainder.

- **Formula:** `concurrency = plan_max_slots`, `batch_size = min(KIMI_MAX_BATCH, ceil(total_items / concurrency))`
- **`KIMI_MAX_BATCH = 10`** (single source of truth — see §7.3)

Worked example — Prep deep enrichment (155 groups, ~16 Kimi prompts):

| Plan | Concurrency | Waves | Approx Phase 2 wall-clock |
|------|-------------|-------|---------------------------|
| Free | 1  | 16 sequential | ~30–80 min |
| Pro  | 3  | 6 waves       | ~12–30 min |
| Max  | 10 | 2 waves       | ~4–10 min  |

Worked example — Prep concept seeding (602 modules, ~61 Kimi prompts):

| Plan | Concurrency | Waves | Approx Phase 2 wall-clock |
|------|-------------|-------|---------------------------|
| Free | 1  | 61 sequential | hours |
| Pro  | 3  | 21 waves      | ~45–90 min |
| Max  | 10 | 7 waves       | ~15–35 min |

> **Math correction from v1:** v1 §6 Scenario A claimed "Pro plan = 3 conc × 15 batch over 100 = ~7 sequential waves." That arithmetic is wrong (3×15=45/wave → 2.2 waves) AND the cap-15 number contradicted §6.1 which said cap-20. Both are now superseded by the single `KIMI_MAX_BATCH=10` constant, which is the value justified by quality-first reasoning (deeper attention per file).

**Key insight:** Kimi Phase 2 dominates wall-clock on every plan. Phases 1 and 3 (Gemini) are always ~5–45s regardless of plan tier. Plan upgrades only move the needle by shrinking Phase 2 waves.

#### 7.2 Coordinator + Synthesis (Gemini) — Phases 1 and 3

Goal: massive-context synthesis with preserved cross-reference attention. Concurrency doesn't matter (one synthesis pass per swarm); batch size is everything, **derived from payload tokens, not raw item count**.

- **Formula:**
  ```
  batch_size = min(
      GEMINI_MAX_BATCH_ITEMS,                                  # 200
      GEMINI_ATTENTION_QUALITY_CEILING_TOKENS // avg_item_tokens,  # 200K / avg
  )
  ```
- **Why payload-driven:** A Kimi worker output might be 500 tokens or 2,500 tokens. A static item-count cap (v1's 500) could silently span 250K–1.25M tokens and blow past attention-quality limits.

**All plans:** Feed Gemini as much context as attention quality allows. For the Prep project (602 modules × ~1,000 tokens/output = 602K tokens), this yields **3 Gemini synthesis calls** (200 items each) — preserving cross-referencing quality while still collapsing 602 items into ~3 passes instead of 60+.

### 7.3 Light safeguards (single source of truth)

All Swarm sizing constants live in `swarm_optimizer.py`:

- **`KIMI_MAX_BATCH = 10`** — never exceed 10 files per Kimi prompt. Beyond ~10, thinking-preamble attention dilutes and output JSON schemas degrade regardless of context window.
- **`GEMINI_MAX_BATCH_ITEMS = 200`** — absolute ceiling on items per Gemini call, independent of payload size. Protects against degenerate cases (many tiny outputs that pack into one call but still blow item-wise attention).
- **`GEMINI_ATTENTION_QUALITY_CEILING_TOKENS = 200_000`** — payload cap where Gemini 3 Flash cross-reference attention still holds sharp. Primary quality lever.
- **`GEMINI_HARD_CONTEXT_TOKENS = 800_000`** — 80% of the 1M window; hard safety cap that accounts for system prompt + generated output headroom.
- **Per-worker timeout** — already enforced by `swarm_orchestrator.py` (120s cloud / 300s local). Workers exceeding this are marked failed; fan-out continues with partial results.

The two caps serve different jobs:
- `KIMI_MAX_BATCH` is a **per-item attention lever** — keeps each file's reasoning sharp.
- `GEMINI_ATTENTION_QUALITY_CEILING_TOKENS` is a **cross-reference attention lever** — keeps synthesis sharp across items.

The 10-vs-200-item gap is defensible: both numbers derive from the same principle (*attention quality per item*) applied to different content densities — raw file analysis under thinking-budget pressure vs. pre-digested JSON synthesis at 1M context.

The previous v1 plan had `KIMI_MAX_BATCH=10` in §6 and `KIMI_MAX_BATCH=20` in §6.1 — that contradiction is resolved here.

## 8. Universality & Future Native APIs

Ollama Cloud's plan tiers (Free/Pro/Max) are the guiding light, but the architecture is universally applicable.

**Future planning:**

- **OpenAI / Anthropic / Google Native APIs:** Direct providers enforce rate limits via RPM (Requests Per Minute) and TPM (Tokens Per Minute) rather than rigid concurrent-connection slots.
- `get_optimal_swarm_config()` will be extended to accept these rate limits and translate them into dynamic concurrency / batch-size thresholds — riding exactly at the edge of a user's tier (e.g., OpenAI Tier 1 vs Tier 5).

## 9. Success Metrics

Quality first, throughput second. We'll measure both before and after enabling the decoupled stack:

| Metric | Definition | Target (post-rollout) |
|--------|------------|------------------------|
| **Synthesis JSON validity rate** | % of Phase 1 + Phase 3 calls that produce valid parseable JSON | ≥ 99% (vs ~85% baseline with Kimi-as-coordinator due to F-29) |
| **Concept coverage** | Concepts surfaced per 100 files vs hand-curated reference set | +20% over Kimi-only baseline |
| **Group-reasoning depth** | Avg `<think>` tokens per worker (proxy for reasoning effort) | ≥ 4,000 tokens/worker on Max plan |
| **Swarm wall-clock (Prep project)** | End-to-end time for deep enrichment on 1,800-file index | ≤ 30 min on Max plan |
| **Per-worker failure rate** | % of fan-out workers that timeout or error | ≤ 2% |

## 10. Test Plan

### Unit tests (`tests/`)

- `test_swarm_orchestrator.py` — verify constructor accepts both `coordinator_llm` and `worker_llm`; verify inherit-from-Thinking fallback when `coordinator_llm=None`.
- `test_swarm_optimizer.py` (new) — verify `get_optimal_swarm_config()` for each (plan_tier, role, total_items) combination matches the §7.1 / §7.2 tables.
- `test_batch_profiles.py` — verify removal of F-59 hardcap; verify "Enforce Cloud Token Safety Limits" toggle promotes Gemini to LARGE and Kimi stays on CLOUD_SMALL-equivalent batch sizes.

### Integration tests

- `test_concept_seeder_swarm.py` / `test_atlas_swarm.py` / `test_cluster_swarm.py` — extend to verify both LLMs are used (Coordinator for Phases 1+3, Worker for Phase 2). Mock both clients separately and assert per-phase routing.
- `test_pipeline_scheduler.py` — verify swarm tier detection still works with the new coordinator slot.

### In-daemon smoke tests (manual, per release)

1. Prep project, finalize → concept seeding swarm, 602 modules, Pro plan (3 workers).
2. Prep project, deep enrichment → group reasoning swarm, 155 groups, Max plan (10 workers).
3. mini-redis-rust project, finalize → concept seeding, 19 modules, Free plan (1 worker).

### UI tests

- Storybook story for `ModelCard` with `'coordinator'` slot.
- Verify "Inherit from Thinking Model" toggle disables the Coordinator dropdown and shows the Thinking model's name.

## 11. Rollback & Inherit-from-Thinking Fallback

### Backward compatibility

- Existing configs without a `coordinator` block continue to work — `config_manager.py` defaults `coordinator_llm = large_llm` when the key is absent.
- The UI's "Inherit from Thinking Model" toggle is ON by default for users who upgrade — surfaces the Coordinator card but doesn't force them to configure anything.
- Existing pipeline runs in flight at upgrade time use the Worker model for both phases (no behavioral change).

### Rollback

If the decoupled-slot rollout causes regressions:

1. **Feature flag:** Wrap the dual-LLM constructor path in a `SWARM_DECOUPLED_SLOTS` flag (default ON post-rollout). Setting OFF restores `SwarmOrchestrator(llm=large_llm)` everywhere.
2. **Config compatibility:** Configs containing `coordinator` are not mutated on rollback — they're simply ignored when the flag is OFF.
3. **No DB migration needed** — slot config lives in `ui_config.json` / settings DB, not in the index.

## 12. MVC Implementation Path

The Minimum Viable Configuration focuses on the dual-cloud Swarm flow.

### Step 1 — Core optimizer logic

- **Target:** new `src/prep/core/swarm_optimizer.py` (re-exported from `batch_profiles.py` for compatibility).
- **Change:** implement `get_optimal_swarm_config(model_id, plan_tier, total_items, role)` per §7. Constants `KIMI_MAX_BATCH=10`, `GEMINI_MAX_BATCH=500`, `GEMINI_CONTEXT_BUFFER_PCT=0.80` defined here.
- **Also:** remove the stale F-59 hardcap from `batch_profiles.py:get_batch_concurrency()`.

### Step 2 — Decoupled Swarm initialization

- **Targets:** `src/prep/core/swarm_orchestrator.py`, `src/prep/core/cluster.py`, `src/prep/core/group_reasoning.py`, `src/prep/core/concept_seeder.py`, `src/prep/core/atlas/generator.py`.
- **Change:** inject `coordinator_llm` (Gemini) and `worker_llm` (Kimi); apply the optimizer's per-phase sizing. Implement the inherit-from-Thinking fallback (§2).

### Step 3 — UI & Advanced Settings

- **Targets:** `packages/ui/src/components/llm/AIModelsSettings.tsx`, `ModelCard.tsx`, `useDashboardPanels.tsx`.
- **Change:** add the Swarm Coordinator slot with "Inherit from Thinking" toggle; add Advanced Settings panel with the three overrides (Cloud Token Safety, Max Thinking Budget, Ollama Cloud Plan).
- **Recommended models:** ship the updated `RECOMMENDED_MODELS` constant from §4.

### Step 4 — Tests & metrics

- Add the unit + integration tests from §10.
- Wire the §9 metrics into the existing telemetry pipeline so we can observe quality deltas across the rollout.
