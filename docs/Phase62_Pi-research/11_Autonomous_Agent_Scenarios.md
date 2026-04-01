# Phase 62 — Autonomous Agent Scenarios: Time-Aware Design & Concurrency Safety

> **Research Document 11 of N** | Phase 62: Pi & Agent Ecosystem Research
> Date: 2026-03-31
> Extends: [08_Dual_Agent_Architecture.md](./08_Dual_Agent_Architecture.md)
> Context: CoDRAG codrag structural analysis across 15+ source files

---

## 1. Executive Summary

This document designs 8 autonomous agent scenarios for CoDRAG, with a critical lens on:
- **Time cost** — how long each scenario actually takes to execute
- **Concurrency safety** — how agents avoid starving the pipeline of GPU/LLM slots
- **Batch size traps** — ensuring we don't hand a 35B local model 10,000 items to process
- **Model selection** — matching context window and reasoning depth to actual need

**Key finding: Most scenarios require NO LLM calls at all.** CoDRAG's audit pipeline is
pure Python/graph analysis (Tier 1). The LLM is only needed for *interpreting* results,
not generating them. This changes the economics dramatically.

---

## 2. CoDRAG's Tool Surface — What Agents Can Actually Call

### 2.1 MCP Tools (12 tools, all read-only except `codrag_observe`)

| Tool | LLM Required? | Execution Time | Output Size |
|------|--------------|----------------|-------------|
| `codrag()` | ❌ No — reads cached atlas | ~50ms | ~2-4K chars |
| `codrag(role="X")` | ❌ No — role vector × cached data | ~100ms | ~1.5-4K chars |
| `codrag_search(query)` | ❌ No — embedding similarity + graph expansion | ~200ms | ~12K chars |
| `codrag_search(type="symbol")` | ❌ No — index lookup | ~50ms | ~8K chars |
| `codrag_impact(file_path)` | ❌ No — graph traversal | ~100ms | ~6K chars |
| `codrag_audit(action="scan")` | ❌ No — pure Python analyzers | ~2-5s | ~15K chars |
| `codrag_audit(action="refactor")` | ❌ No — reads cached findings + code context | ~500ms | ~12K chars |
| `codrag_audit(action="verify")` | ❌ No — re-runs specific analyzers | ~1-2s | ~5K chars |
| `codrag_audit(action="report")` | ⚠️ Maybe — synthesize mode uses LLM | ~30-60s if LLM | ~20K chars |
| `codrag_audit(action="advise")` | ⚠️ Maybe — TODO detection is pure, proposals may use LLM | ~5-30s | ~15K chars |
| `codrag_observe(action="save")` | ❌ No — JSON file write | ~10ms | N/A |
| `codrag_observe(action="get")` | ❌ No — JSON file read + filter | ~20ms | ~5K chars |

> **Critical insight: 10 of 12 MCP tools require ZERO LLM calls.**
> The agent itself needs an LLM to reason about the results, but CoDRAG's tools are
> pure computation. This means agent tasks are bounded by the agent's model speed,
> NOT by CoDRAG's pipeline.

### 2.2 HTTP API Endpoints

| Endpoint | LLM? | Time | Modifies State? |
|----------|-------|------|-----------------|
| `GET /pipeline/status` | ❌ | ~10ms | No |
| `GET /watcher/status` | ❌ | ~10ms | No |
| `POST /pipeline/fast` | ✅ Triggers LLM pipeline | 10-60min | Yes — rebuilds graph |
| `POST /pipeline/deep` | ✅ Triggers LLM pipeline | 30-120min | Yes — enriches graph |
| `POST /opportunities/refresh` | ❌ Runs audit (Python) | ~5s | Yes — updates findings |
| `GET /opportunities` | ❌ | ~50ms | No |
| `GET /opportunities/export` | ❌ | ~100ms | No |

### 2.3 Internal Systems (Background, Always Running)

| System | Competes for GPU? | Agent Interaction |
|--------|-------------------|-------------------|
| **AutoRebuildWatcher** | No (fs events only) | Read status only |
| **PipelineOrchestrator** | ✅ YES — stages 2-9 use LLM | Trigger via API |
| **MultiProjectCoordinator** | Controls GPU access | No direct access |
| **ModelReadiness** | Preload occupies 1 slot briefly | Read status only |
| **TokenTelemetry** | No | Read usage stats |
| **OpportunityManager** | No (Python analysis) | Trigger refresh, query |

---

## 3. Time & Concurrency Scrutiny

### 3.1 The Concurrency Trap

CoDRAG's pipeline has 3 model slots (defined in `_get_llm_concurrency()`):

```
VRAM Budget (typical setup with qwen3.5:35b):
  Model weights:    ~20 GB
  KV cache (×1):    ~2 GB
  KV cache (×2):    ~4 GB
  ────────────────────────
  Total (conc=1):   ~22 GB
  Total (conc=2):   ~24 GB
```

| Slot | Config Key | Usage | Concurrency |
|------|-----------|-------|-------------|
| `fast` | `llm_concurrency_fast` | Stage 3 (catalogue) | 1-4 parallel |
| `code` | `llm_concurrency_code` | Stage 2 (inferred edges) | 1-2 parallel |
| `deep` | `llm_concurrency_deep` | Stages 6-9 (enrichment) | 1-2 parallel |

**If an agent fires an LLM call while the pipeline is running on the same model:**
- **Local Ollama**: Requests queue — each concurrent request needs its own KV cache in VRAM.
  If `OLLAMA_NUM_PARALLEL=2` and pipeline has concurrency=2, agent requests queue behind
  pipeline requests. Throughput degrades but doesn't crash.
- **Cloud Ollama**: 429 Too Many Requests. Free tier = 1 concurrent, Pro = 3, Max = 10.
  Agent calls WILL conflict with pipeline calls.

### 3.2 The "10,000 Items" Problem

The user correctly identified this risk. Let's quantify it:

**CoDRAG's audit scan for this project produces:**
- ~5,000+ graph nodes (files in the index)
- ~20,000+ edges
- After collapsing (implemented in Phase 65): ~50-200 actionable findings

**If we naively ask an LLM to "analyze all findings":**
```
50 findings × ~300 chars each = ~15,000 chars input
+ System prompt: ~2,000 chars
+ Agent reasoning: ~5,000 chars output
────────────────────────────────────
Total context: ~22,000 chars = ~5,500 tokens

Time on qwen3.5:35b local:
  Prompt processing: ~5,500 tokens ÷ ~800 tok/s = ~7 seconds
  Generation: ~2,000 tokens ÷ ~30 tok/s = ~67 seconds
  Total: ~74 seconds per agent call
```

That's completely fine. The danger is if we DON'T pre-aggregate:

```
5,000 raw nodes × ~200 chars each = ~1,000,000 chars = ~250,000 tokens
→ WAY beyond any model's context window.
→ Would need ~4,100 batched calls at 60 items each
→ At 74s/call: ~84 HOURS. Catastrophic.
```

**Conclusion: The collapsing/grouping pass we built in Phase 65 is a PREREQUISITE for
agent scenarios.** Agents must work with the aggregated `ActionItem` list (50-200 items),
never the raw graph nodes (5,000+).

### 3.3 Time Budget Per Scenario (Realistic Estimates)

| Scenario | CoDRAG Tool Time | Agent LLM Calls | LLM Time (local 35B) | LLM Time (cloud) | Total |
|----------|-----------------|-----------------|----------------------|-------------------|-------|
| A: Watchdog | ~5s (scan) + ~20ms (observe) | 1 call (~20K ctx) | ~74s | ~15s | **~80s local / ~20s cloud** |
| B: Doctor | ~5s (scan) + ~10ms (status) | 1 call (~8K ctx) | ~35s | ~8s | **~40s local / ~13s cloud** |
| C: Geologist | ~150ms (atlas) + ~20ms (observe×2) | 1 call (~30K ctx) | ~120s | ~25s | **~2min local / ~25s cloud** |
| D: Dispatcher | ~5s (scan) + ~500ms (refactor) + ~300ms (impact×5) | 2-3 calls (~40K ctx) | ~350s | ~60s | **~6min local / ~1min cloud** |
| E: Librarian | ~100ms (observe get) + ~50ms (impact×5) | 1 call (~15K ctx) | ~55s | ~12s | **~1min local / ~12s cloud** |
| F: Reviewer | ~300ms (impact×3) + ~200ms (search) | 1 call (~25K ctx) | ~90s | ~18s | **~1.5min local / ~20s cloud** |
| G: Architect | ~150ms (atlas) + ~5s (scan) + ~500ms (report) | 2-3 calls (~60K ctx) | ~500s | ~90s | **~9min local / ~1.5min cloud** |
| H: Scholar | ~5s (scan quality) + ~200ms (search) | 1 call (~20K ctx) | ~74s | ~15s | **~80s local / ~20s cloud** |

### 3.4 Summary: Most Scenarios Are Fast

| Tier | Time (local) | Scenarios | Model Recommendation |
|------|-------------|-----------|---------------------|
| **Quick** (<2min) | A, B, E, H | `qwen3.5:35b` local — 1 LLM call, structured output |
| **Medium** (2-6min) | C, D, F | Cloud preferred for speed, local works but slow |
| **Heavy** (>6min) | G | Cloud recommended — multi-call, large context |

**None of these are catastrophic.** The worst case (Architect on local) is ~9 minutes,
which is acceptable for a monthly task.

---

## 4. Concurrency Safety Design

### 4.1 The Rule: Agent LLM Calls Must Not Starve the Pipeline

The pipeline is the primary consumer of LLM resources. Agent scenarios are secondary.
We need a simple, enforceable rule:

```
WHEN pipeline is running:
  Agent tasks → DEFER (queue, don't execute)
  
WHEN pipeline is idle:
  Agent tasks → EXECUTE (no contention)
  
WHEN cloud model:
  Agent tasks → RESPECT rate limits (built-in 429 retry)
```

### 4.2 Implementation: Agent Concurrency Gate

```python
# src/codrag/services/agent_gate.py (NEW, ~40 lines)
class AgentConcurrencyGate:
    """Ensures agent LLM calls don't compete with pipeline LLM calls.
    
    The agent gate checks:
    1. Is any pipeline stage currently running that uses the LLM?
    2. Is the model slot the agent needs currently occupied?
    
    If either is true, the agent waits (with exponential backoff)
    until the slot is free.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._agent_active = False  # Is an agent LLM call in progress?
    
    def can_run(self, project_id: str) -> bool:
        """Returns True if it's safe for an agent to make LLM calls."""
        # Check if pipeline is currently using LLM stages (2, 3, 6-9)
        try:
            from codrag.services.pipeline.orchestrator import pipeline_orchestrator
            status = pipeline_orchestrator.get_status(project_id)
            if status and status.get("state") == "running":
                running_stage = status.get("current_stage", "")
                llm_stages = {"inferred_edges", "catalogue", "enrichment", 
                              "group_reasoning", "clustering", "atlas", "deepening"}
                if running_stage in llm_stages:
                    return False
        except Exception:
            pass
        
        with self._lock:
            if self._agent_active:
                return False
            self._agent_active = True
            return True
    
    def release(self):
        with self._lock:
            self._agent_active = False
```

### 4.3 Token Telemetry Integration

CoDRAG already tracks token usage via `TokenTelemetry.record_usage()` in `llm_client.py`.
Agent LLM calls made through our LLM client automatically get tracked. But agent LLM
calls made through OpenCode or Pi's own LLM client won't be tracked.

**Solution for Pi (custom daemon):** Pi uses CoDRAG's `LLMClient` directly → telemetry is automatic.

**Solution for OpenCode:** OpenCode has its own LLM client. We would need to either:
- (a) Read OpenCode's session stats after each run (it exposes `opencode stats`)
- (b) Accept that OpenCode's token usage is untracked in CoDRAG's telemetry
- (c) Have OpenCode call `codrag_observe` to report its own usage

Option (b) is pragmatic for now. OpenCode is interactive/on-demand. Pi is continuous.

---

## 5. Pi vs. OpenCode — Strengths by Task

### 5.1 Where Pi Wins

Pi is a custom Python process that imports `codrag` directly. This gives it:

| Advantage | Why It Matters |
|-----------|----------------|
| **Direct Python imports** | Can call `run_audit()` directly, not through MCP serialization |
| **HTTP API access** | Can trigger `POST /pipeline/fast` to rebuild graph |
| **CoDRAG's own LLMClient** | Inherits all safety guards: OutputMonitor, CloudRateLimitError, think-tag stripping, truncated JSON repair |
| **Token telemetry** | LLM calls automatically tracked in CoDRAG's dashboard |
| **Agent concurrency gate** | Can check `agent_gate.can_run()` before making LLM calls |
| **No installation** | Pi is just a Python script in the CoDRAG codebase |
| **Free on local models** | Uses the same Ollama instance CoDRAG already manages |

### 5.2 Where OpenCode Wins

| Advantage | Why It Matters |
|-----------|----------------|
| **File editing** | Can modify files (with permission controls) |
| **Git integration** | Can run `git diff`, `git log`, `git blame` |
| **Shell commands** | Can run tests, linters, formatters |
| **Subagent spawning** | Can parallelize work across child sessions |
| **Session persistence** | Conversations survive across invocations |
| **Multi-IDE support** | Works in terminal, Zed, JetBrains, Neovim (via ACP) |
| **GitHub Actions** | Native CI/CD integration |

### 5.3 Task Assignment Matrix (Scrutinized)

| Scenario | Pi? | OpenCode? | Why? |
|----------|-----|-----------|------|
| A: Watchdog | ✅ **Yes** | ❌ No | Pure CoDRAG tools, needs telemetry integration, runs frequently |
| B: Doctor | ✅ **Yes** | ❌ No | Needs HTTP API to trigger pipeline, needs agent gate |
| C: Geologist | ✅ **Yes** | ⚠️ Optional | MCP-only, but Pi gets telemetry tracking |
| D: Dispatcher | ✅ **Yes** | ❌ No | Multi-step MCP choreography, needs gate, needs telemetry |
| E: Librarian | ✅ **Yes** | ❌ No | `codrag_observe` is Pi's natural habitat |
| F: Reviewer | ❌ No | ✅ **Yes** | Needs git access + file reading |
| G: Architect | ✅ **Yes** | ⚠️ Optional | MCP-only, Pi gets telemetry, but OpenCode could write proposals to files |
| H: Scholar | ✅ **Yes** | ❌ No | Needs HTTP API to trigger re-enrichment |

**Verdict: Pi handles 7 of 8 scenarios. OpenCode handles 1 (code review prep).
They can run simultaneously because they use different LLM slots or the same slot
with the agent gate enforcing sequential access.**

---

## 6. Scenario Designs (Scrutinized, Time-Aware)

### 6.1 Scenario A: Watchdog (Continuous Health Monitor)

**Trigger:** After every pipeline rebuild completes (watcher → pipeline → Watchdog)

**Step-by-step execution:**
```
1. Pipeline completes → callback fires
2. Pi checks agent_gate.can_run() → True (pipeline just finished)
3. Pi calls codrag_audit(action="scan") → ~5s, returns ~50-200 findings
4. Pi calls codrag_observe(action="get", query="last_scan") → ~20ms, returns previous scan
5. Pi computes delta: new findings, resolved findings, changed severity
6. Pi calls LLM(prompt="Summarize this delta", context=~15K chars) → ~74s local
7. Pi calls codrag_observe(action="save", content=delta_summary) → ~10ms
8. Total: ~80 seconds
```

**Batch size guard:**
```python
# Pi does NOT process individual nodes (5,000+)
# It processes the aggregated ActionItem list (50-200)
findings = codrag_audit(action="scan")  # Already aggregated
assert len(findings) < 500, f"Too many un-collapsed findings: {len(findings)}"
```

**Frequency guard:**
```python
# Pi skips if nothing changed since last scan
if watcher_status["stale_since"] is None:
    return  # Index hasn't changed, no point re-scanning
```

**Cost:** Free (local model). ~80 seconds per execution. ~0 tokens wasted on no-ops.

---

### 6.2 Scenario D: Dispatcher (Smart Triage) — Most Complex

**Trigger:** On-demand (user clicks "Triage" in dashboard or Pi detects >50 findings)

**Step-by-step execution:**
```
1. Pi checks agent_gate.can_run() → True
2. Pi calls codrag_audit(action="scan") → ~5s, returns N findings
3. If N < 10: Skip (not enough findings to need triage). Total: ~5s
4. Pi selects TOP 10 critical/warning findings (already sorted by severity)
5. For each of the top 10:
   Pi calls codrag_impact(file_path=finding.files[0]) → ~100ms each = ~1s total
6. Pi assembles triage context: 10 findings × impact analysis
   → ~25K chars total context
7. Pi calls LLM(prompt="Group by root cause, suggest attack order", 
                context=~25K chars) → ~120s local / ~25s cloud
8. Pi calls codrag_observe(action="save", category="pattern", 
                           content=triage_result) → ~10ms
9. Total: ~130s local (2.2min) / ~30s cloud
```

**Batch size guard:**
- Only the TOP 10 findings get impact analysis (not all 200)
- Impact analysis is graph traversal (no LLM, ~100ms each)
- LLM gets a pre-filtered, pre-summarized context (~25K chars, well within 32K window)

**Why this works on local 35B:**
- 25K chars = ~6,200 tokens. Well within `qwen3.5:35b`'s 32K window.
- Single LLM call, not 200 calls.
- The intelligence is in the PROMPT (grouping logic), not in processing volume.

---

### 6.3 Scenario F: Reviewer (Code Review Prep) — OpenCode Only

**Trigger:** Pre-commit hook or manual `opencode run --agent reviewer "..."` invocation

**Step-by-step execution:**
```
1. OpenCode runs `git diff --name-only HEAD~1` → list of changed files
2. For each changed file (typically 3-10):
   OpenCode calls codrag_impact(file_path=file, direction="dependents") → ~100ms each
   OpenCode calls codrag_impact(file_path=file, direction="dependencies") → ~100ms each
3. OpenCode calls codrag_audit(action="scan", category="architecture") → ~2s
4. OpenCode assembles review brief from impact results + relevant findings
5. OpenCode calls LLM to synthesize → ~90s local / ~18s cloud
6. OpenCode writes review brief to stdout or PR comment
7. Total: ~1.5min local / ~20s cloud
```

**This doesn't conflict with Pi because:**
- OpenCode uses its own LLM client (separate from CoDRAG's)
- If OpenCode uses Ollama, it queues behind any pipeline work
- Reviewer is triggered on-demand (not continuously), so conflicts are rare

---

## 7. Model Routing for Agents

### 7.1 Adding a 4th Model Slot: "Agent"

CoDRAG currently has 3 model slots. We add a 4th for agent tasks:

| Slot | Config Key | Pipeline Use | Agent Use |
|------|-----------|-------------|-----------|
| `fast` | `llm_concurrency_fast` | Stage 3 (catalogue) | — |
| `code` | `llm_concurrency_code` | Stage 2 (inferred edges) | — |
| `deep` | `llm_concurrency_deep` | Stages 6-9 (enrichment) | — |
| **`agent`** | **`agent_model`** | — | **Pi scenarios A-H** |

**Default `agent_model`:** Same as `deep` slot (reuse existing model configuration).
Most agent tasks are "deep reasoning about audit data" — same profile as epistemic
enrichment.

**Config extension in pipeline settings:**
```json
{
  "pipeline_config": {
    "model_deep": "qwen3.5:35b-a3b",
    "llm_concurrency_deep": 2,
    "agent_model": "qwen3.5:35b-a3b",     // default: same as deep
    "agent_enabled": true,                  // kill switch
    "agent_auto_scan": true,                // Watchdog auto-runs after pipeline
    "agent_triage_threshold": 50,           // Auto-triage when >50 findings
    "agent_cooldown_seconds": 300           // Min gap between agent runs
  }
}
```

### 7.2 Why a Separate Slot Matters

Even though the agent often uses the SAME model as the `deep` slot, having a separate
config key means:
- Users can override it (e.g., use a smaller 8B model for cheap agent tasks)
- The agent gate can check if the agent slot is currently occupied
- Token telemetry can attribute costs to "agent" vs "pipeline_deep"
- The dashboard can show agent model status independently

### 7.3 Cloud Model for Heavy Tasks

For Scenarios C (Geologist), D (Dispatcher), and G (Architect), the user can set:
```json
{
  "agent_model": "kimi-k2.5:cloud"
}
```

This uses Ollama Cloud, which:
- Has 128K context window (vs local 32K)
- Costs ~$0.05-$0.15 per agent run
- Is rate-limited (Free=1, Pro=3 concurrent)
- Already handled by CoDRAG's `CloudRateLimitError` and 429 retry logic

---

## 8. Pi Architecture: Minimal Python Daemon

### 8.1 Design Philosophy

Pi is NOT a framework. It's a ~200-line Python script that:
1. Imports CoDRAG's existing modules directly (no MCP serialization overhead)
2. Uses CoDRAG's `LLMClient` (inherits all safety guards)
3. Respects the agent gate (no GPU contention)
4. Writes results to `codrag_observe` (cross-session memory)
5. Runs as a background thread in the CoDRAG daemon (no separate process)

### 8.2 Integration Points

```
┌─────────────────────────────────────────────────────┐
│  CoDRAG Daemon (FastAPI + background threads)       │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  │
│  │ HTTP Server  │  │ Watcher      │  │ Pipeline │  │
│  │ (FastAPI)    │  │ (watchdog)   │  │ Orch.    │  │
│  └──────────────┘  └──────┬───────┘  └────┬─────┘  │
│                            │               │         │
│                     on_rebuild_complete     │         │
│                            │               │         │
│                     ┌──────▼───────┐       │         │
│                     │  Pi Agent    │       │         │
│                     │  ──────────  │       │         │
│                     │  Watchdog    │       │         │
│                     │  Dispatcher  │       │         │
│                     │  Librarian   │       │         │
│                     │  etc.        │       │         │
│                     │              │       │         │
│                     │  Uses:       │       │         │
│                     │  • LLMClient │◄──────┘         │
│                     │  • run_audit │  (shared model)  │
│                     │  • observe   │                  │
│                     │  • gate      │                  │
│                     └──────────────┘                  │
└─────────────────────────────────────────────────────┘
```

### 8.3 Skeleton Implementation

```python
# src/codrag/services/pi_agent.py (~200 lines)

class PiAgent:
    """Proactive Intelligence agent — autonomous background analysis.
    
    Runs as a background thread within the CoDRAG daemon.
    All LLM calls go through CoDRAG's LLMClient (inheriting safety guards).
    Respects AgentConcurrencyGate (no GPU contention with pipeline).
    Results written to codrag_observe (cross-session memory).
    """
    
    def __init__(self, project_id: str, settings: dict):
        self.project_id = project_id
        self.enabled = settings.get("agent_enabled", False)
        self.auto_scan = settings.get("agent_auto_scan", True)
        self.cooldown = settings.get("agent_cooldown_seconds", 300)
        self._last_run_at = 0.0
        self._gate = AgentConcurrencyGate()
    
    def on_pipeline_complete(self, group: str):
        """Called by PipelineOrchestrator after a group completes."""
        if not self.enabled or not self.auto_scan:
            return
        if time.time() - self._last_run_at < self.cooldown:
            return  # Respect cooldown
        
        # Run Watchdog scenario in background thread
        threading.Thread(target=self._run_watchdog, daemon=True).start()
    
    def _run_watchdog(self):
        """Scenario A: Compare current scan against last scan, report delta."""
        if not self._gate.can_run(self.project_id):
            logger.info("Pi: Pipeline still using LLM, deferring watchdog")
            return
        
        try:
            # Step 1: Get current findings (pure Python, ~5s)
            from codrag.core.audit.runner import run_audit
            result = run_audit(self._index_dir, self._project_root)
            current_findings = result.findings
            
            # Step 2: Get previous scan from observations
            from codrag.services.observation_store import observation_store
            prev_obs = observation_store.get(
                project_id=self.project_id, 
                query="scan_delta", 
                limit=1
            )
            
            # Step 3: Compute delta (pure Python, ~0ms)
            delta = self._compute_delta(current_findings, prev_obs)
            if not delta["new"] and not delta["resolved"]:
                logger.info("Pi: No changes since last scan, skipping LLM")
                return
            
            # Step 4: Summarize with LLM (1 call, ~74s local)
            summary = self._llm_summarize_delta(delta)
            
            # Step 5: Save observation
            observation_store.save(
                project_id=self.project_id,
                content=summary,
                category="pattern",
            )
            
            self._last_run_at = time.time()
            logger.info("Pi: Watchdog complete — %d new, %d resolved", 
                        len(delta["new"]), len(delta["resolved"]))
        finally:
            self._gate.release()
```

---

## 9. Implementation Phases (Time-Boxed)

### Phase 1: Foundation (2-3 days)

| Task | Effort | Deliverable |
|------|--------|-------------|
| Create `agent_gate.py` | 1h | Concurrency gate that checks pipeline state |
| Add `agent_model` to pipeline settings | 1h | 4th model slot in settings store |
| Create `pi_agent.py` skeleton | 2h | Background thread with on_pipeline_complete hook |
| Wire Pi to PipelineOrchestrator | 1h | Callback after group completion |
| Implement Scenario A (Watchdog) | 3h | Delta scan + LLM summary + observe save |
| Test concurrency safety | 2h | Verify agent defers when pipeline is running |

**Exit criteria:** Pi runs Watchdog automatically after each pipeline rebuild.
Dashboard shows "Last agent scan: 2 min ago — 3 new findings, 1 resolved."

### Phase 2: Intelligence (3-4 days)

| Task | Effort | Deliverable |
|------|--------|-------------|
| Implement Scenario E (Librarian) | 2h | Stale observation cleanup |
| Implement Scenario D (Dispatcher) | 4h | Impact-aware triage with top-10 grouping |
| Implement Scenario B (Doctor) | 2h | Index integrity check + auto-rebuild |
| Add `agent_model` UI to AI Gateway panel | 3h | Model dropdown in dashboard |
| Add agent status to Opportunities panel | 2h | "Last scan" indicator |

**Exit criteria:** Pi runs 4 scenarios. Dashboard shows agent model config and
scan timestamps.

### Phase 3: Strategic Analysis (2-3 days)

| Task | Effort | Deliverable |
|------|--------|-------------|
| Implement Scenario C (Geologist) | 3h | Weekly drift detection with atlas snapshots |
| Implement Scenario G (Architect) | 4h | Monthly architecture proposals |
| Implement Scenario H (Scholar) | 2h | Enrichment quality monitoring |
| Create OpenCode config for Scenario F (Reviewer) | 2h | `.opencode/opencode.json` + reviewer agent |

**Exit criteria:** Full 8-scenario coverage. Pi and OpenCode coexist.

---

## 10. Risk Analysis

### 10.1 Risk: Agent Hot-Loops

**Threat:** Watchdog triggers → finds issues → triggers pipeline → pipeline completes → 
Watchdog triggers → finds same issues → loops forever.

**Mitigation:** 
- Cooldown timer (`agent_cooldown_seconds`, default 300s = 5 min)
- Delta-only reporting (skip if no changes since last scan)
- Guard: `if watcher_status["stale_since"] is None: return`

### 10.2 Risk: Cloud Rate Limits

**Threat:** Pi uses `kimi-k2.5:cloud` for Dispatcher while pipeline runs `qwen3.5:35b-a3b:cloud`.
Both hit Ollama Cloud's concurrency limit.

**Mitigation:**
- Agent gate prevents concurrent LLM calls when pipeline is running
- CoDRAG's `CloudRateLimitError` + 429 retry logic already handles this
- Pi defaults to local model; cloud is opt-in for heavy scenarios only

### 10.3 Risk: Observation Store Pollution

**Threat:** Pi generates thousands of observations over weeks, making `codrag_observe`
noisy for human users and other agents.

**Mitigation:**
- Pi observations use a distinct category: `category="agent_scan"` or `category="agent_triage"`
- Librarian scenario (E) periodically garbage-collects stale agent observations
- UI can filter by category (agent observations hidden by default in MCP responses)

### 10.4 Risk: Model Context Overflow

**Threat:** Scenario G (Architect) needs ~60K tokens but local `qwen3.5:35b` has 32K.

**Mitigation:**
- Architect scenario auto-detects context budget from model config
- If local model: truncate to top-20 most relevant findings + module summaries (~25K)
- If cloud model: use full context (~60K)
- CoDRAG's LOD compression already handles progressive context reduction

---

## 11. Conclusion: Pi + OpenCode, Not Pi OR OpenCode

**Pi is the right tool for 7 of 8 scenarios** because:
1. Zero-install (it's already Python code in the CoDRAG repo)
2. Inherits all CoDRAG safety guards (OutputMonitor, rate limiting, JSON repair)
3. Token telemetry is automatic
4. Agent gate integration is native
5. Runs as a daemon thread (no separate process management)
6. Free on local models (same Ollama instance)

**OpenCode is the right tool for code review prep** because:
1. It can read files and run git commands
2. It can write review briefs to files or PR comments
3. It integrates with IDEs via ACP
4. It has its own session management

**They coexist safely because:**
- Pi uses CoDRAG's agent gate → defers to pipeline
- OpenCode is on-demand (not continuous) → minimal contention
- Both use the SAME Ollama instance → Ollama queues requests internally
- Pi's token usage is tracked in CoDRAG's telemetry → visible in dashboard
- The 4th model slot (`agent_model`) can be configured independently

---

## Appendix A: Where This Document Fits

```
Phase 62 Research Index:
  01-05: Pi foundation research
  06: Ecosystem mapping
  07: Strategic pivot (knowledge provider)
  08: Dual-agent architecture (Pi + Claude Code)
  09: Dashboard design strategy
  10: Universal adapter architecture (A2A, SARIF)
  ► 11: Autonomous agent scenarios (THIS DOCUMENT)
       — Time-aware design with concurrency safety
       — 8 scenarios with realistic time/cost estimates
       — Pi + OpenCode coexistence architecture
       — Implementation phases (7-10 days total)
```
