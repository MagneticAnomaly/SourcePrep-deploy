# Phase 57: Goalposts — Architecture Scrutiny Report

> Comprehensive code quality audit and architectural review of all implemented Goalposts code
> and planning documents. Reverse-engineered every file to identify bugs, design flaws, and
> opportunities for improvement.

---

## Executive Summary

**Overall Assessment: SOLID FOUNDATION WITH 2 REAL BUGS AND 3 DESIGN DEBTS**

The implementation is architecturally sound — correctly modeled as an independent background job (not a pipeline stage), clean separation of concerns across models/planner/API/hook. However, there are **2 bugs that will cause data corruption in production** and **3 design debts** that should be fixed before shipping.

The planning documents have **3 superseded docs** that should be consolidated to avoid confusion.

---

## 🐛 BUGS (Must Fix)

### BUG-1: Proposal Deduplication Failure (CRITICAL)

**File**: [goalposts_planner.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/goalposts_planner.py#L198-L201)

```python
# Line 199: existing_ids is computed but NEVER USED
existing_ids = {p.id for p in state.proposals}  # ← dead code
state.proposals.extend(new_proposals)             # ← always appends
```

**Impact**: Every time the user clicks "Generate", ALL new proposals are blindly appended. After 3 generations, you'd have 15-21 proposals accumulating, with duplicates addressing the same issues. The `existing_ids` set was clearly intended for dedup but was never wired.

**Fix**: Either:
- (A) Clear old `proposed` proposals before extending (re-generation replaces stale proposals), or
- (B) Deduplicate by title similarity before appending

**Recommended (A)** — Simpler, and matches user mental model: "Generate" produces a fresh set of proposals. Approved/dismissed ones are preserved.

---

### BUG-2: Polling Interval Leak (Medium)

**File**: [useGoalpostsSystem.ts](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/dashboard/src/hooks/useGoalpostsSystem.ts#L37-L46)

```typescript
const poll = setInterval(() => {
  api.getGoalposts(selectedProjectId)
    .then((s) => { ... if (!s.generating) clearInterval(poll) })
    .catch(() => clearInterval(poll))
}, 2000)
// ← No cleanup if component unmounts or project changes
```

**Impact**: If the user starts generation then switches projects or closes the panel, the `setInterval` keeps running in background, making requests to the old project ID until generation finishes. With multiple switches, multiple orphaned intervals accumulate.

**Fix**: Store the interval ID in a ref, clean up in a `useEffect` cleanup function:
```typescript
const pollRef = useRef<NodeJS.Timeout | null>(null)
// In handleGenerate: pollRef.current = setInterval(...)
// In useEffect: return () => { if (pollRef.current) clearInterval(pollRef.current) }
```

---

## ⚠️ DESIGN DEBTS (Should Fix)

### DEBT-1: Non-Atomic File Writes

**File**: [goalposts_models.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/goalposts_models.py#L211-L218)

```python
def save_goalposts(state, index_dir):
    path.write_text(json.dumps(state.to_dict(), indent=2), ...)
    # ← NOT atomic! Crash during write = corrupted goalposts.json
```

**Context**: The rest of CoDRAG uses temp-file + `os.rename` for atomic writes (see `group_reasoning.py` L527-547, `epistemic_enrichment.py`). Goalposts should follow the same pattern.

**Risk**: Low probability but high impact — a crash during generation could lose all user approvals/dismissals.

---

### DEBT-2: Thread Safety on Module-Level Dicts

**File**: [goalposts.py router](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/api/routers/goalposts.py#L53-L54)

```python
_generate_threads: Dict[str, threading.Thread] = {}
_generate_errors: Dict[str, str] = {}
```

No locking. Concurrent requests to `GET /goalposts` and `POST /generate` for the same project could read/write these dicts simultaneously. FastAPI runs on multiple threads by default with `run_in_threadpool`.

**Fix**: Use a `threading.Lock` or switch to a `ConcurrentDict` pattern. Low risk in practice (single-user local app) but a code quality concern.

---

### DEBT-3: Parasitic Task Configuration

**File**: [goalposts_planner.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/goalposts_planner.py#L165-L186)

```python
# Uses audit's task type and max chars
task=PipelineTask.AUDIT,  # ← Should be PipelineTask.GOALPOSTS
max_chars=TASK_MAX_CHARS.get("audit", 15_000),  # ← Should have own key
```

And in the API router:
```python
llm_client = _get_llm_client_for_task("audit")  # ← Shares audit's slot
```

**Impact**: If audit and goalposts are configured differently in the future (different models, different context windows), this coupling will cause silent misconfiguration. Also, if `PipelineTask.GOALPOSTS` is later added to `context_config.py`, existing code won't automatically use it.

**Fix**: Add `PipelineTask.GOALPOSTS` to `context_config.py` and `TASK_MAX_CHARS["goalposts"]` to `llm_client.py`. Keep the "large" LLM slot mapping (already correct in `server.py` line 409).

---

## 📋 DOCUMENTATION ISSUES

### DOC-1: Superseded Documents Still Present

| Document | Status | Issue |
|----------|--------|-------|
| `01_Goalposts_Vision.md` | Partially superseded | Line 25 has raw user annotation `>>> to resolve this We can simply add this as an additioan...` |
| `02_Architecture_Pipeline.md` | **Fully superseded** by `05_Revised_Implementation_Plan.md` | Claims "pipeline stage" + "sprints" — contradicts actual implementation |
| `03_Dashboard_UX.md` | Partially superseded | Describes Kanban board, "Interrogate/Refine" chat threads — not in current scope |

**Recommendation**: Add a `DEPRECATED` banner at the top of docs 01-03, or consolidate into `07_MCP_Integration_Plan.md` which is now the single source of truth.

### DOC-2: State Terminology Mismatch

- `GoalpostState` type includes `'refined'` (in TypeScript and Python models)
- But `ProposalUpdate` in the API router only accepts `"approved" | "dismissed"` (line 158)
- The `'refined'` state is unreachable from the API — leftover from the "Interrogate/Refine" concept in `03_Dashboard_UX.md`

**Fix**: Remove `'refined'` from `VALID_STATES` and `GoalpostState` type, or implement the refinement workflow.

---

## ✅ WHAT'S GOOD (No Changes Needed)

| Area | Assessment |
|------|-----------|
| **Data model** (`goalposts_models.py`) | Clean dataclasses, proper `to_dict`/`from_dict` round-tripping, schema versioning |
| **TypeScript types** (`types.ts`) | Perfect alignment with Python models |
| **API client** (`client.ts`) | All 5 methods correctly typed, proper `encodeURIComponent` for IDs |
| **Server.py registration** | Correct — router included, goalposts in `TASK_TO_SLOT` as "large", in `_LONG_TIMEOUT_TASKS` |
| **Hook architecture** (`useGoalpostsSystem.ts`) | Correct pattern — hydrate-on-project-change, optimistic updates with error revert |
| **Prompt design** | Adequate for V1 — grounded in Atlas + audit findings, JSON output schema well-specified |
| **`can_generate_goalposts()`** | Clean readiness check, Atlas-only minimum requirement is correct |

---

## 🔧 PROPOSED FIX PLAN

| ID | Severity | Effort | Description |
|----|----------|--------|-------------|
| BUG-1 | 🔴 Critical | Small | Fix proposal dedup — clear stale proposed items before extending |
| BUG-2 | 🟡 Medium | Small | Clean up polling interval on unmount |
| DEBT-1 | 🟡 Medium | Small | Atomic file writes for `save_goalposts` |
| DEBT-2 | 🟢 Low | Small | Thread lock on `_generate_threads`/`_generate_errors` |
| DEBT-3 | 🟢 Low | Small | Add `PipelineTask.GOALPOSTS` + `TASK_MAX_CHARS["goalposts"]` |
| DOC-1 | 🟢 Low | Trivial | Mark docs 01-03 as superseded |
| DOC-2 | 🟢 Low | Trivial | Remove unreachable `'refined'` state |

**Total estimated effort**: ~1 hour for all fixes.

---

## 🏗️ MAJOR OVERHAUL ASSESSMENT

**Verdict: No major overhaul needed.**

The architecture is fundamentally correct:
- Independent background job (not blocking pipeline) ✅
- Simple data model (proposals + questions + intent) ✅
- REST API follows existing CoDRAG patterns ✅
- Frontend hook matches established patterns ✅
- MCP tool design (from `07_MCP_Integration_Plan.md`) is clean and minimal ✅

The only question worth revisiting is whether the prompt should use more data signals (module summaries, group reasoning). But per the pruned V2 plan in `07_MCP_Integration_Plan.md`, this is correctly deferred — V1 should ship with Atlas + audit only, then iterate based on output quality.

---

## Second Pass: End-to-End Connectivity Audit

### Connection Map

```
BACKEND (✅ fully connected)
─────────────────────────────────────────────────────────────────
goalposts_models.py ──imported──→ goalposts_planner.py     ✅
goalposts_planner.py ──imported──→ goalposts.py (router)   ✅
goalposts.py (router) ──registered──→ server.py L559/L572  ✅
server.py TASK_TO_SLOT["goalposts"] = "large"              ✅
server.py _LONG_TIMEOUT_TASKS includes "goalposts"         ✅

FRONTEND TYPES & API (✅ defined, ⚠️ partially exported)
─────────────────────────────────────────────────────────────────
types.ts has GoalpostCategory, GoalpostState, etc.         ✅
client.ts has 5 API methods (interface + implementation)   ✅
@codrag/ui index.ts type export list (L10-78)              ❌ MISSING Goalpost types
@codrag/ui index.ts `export * from './api'` (L219)         ⚠️ Exports client, not types

DASHBOARD WIRING (❌ NOT connected)
─────────────────────────────────────────────────────────────────
GoalpostsPanel.tsx                                         ❌ DOES NOT EXIST
useGoalpostsSystem.ts hook                                 ✅ EXISTS but orphaned
App.tsx import useGoalpostsSystem                          ❌ NOT imported
App.tsx call useGoalpostsSystem(selectedProjectId)          ❌ NOT called
App.tsx pass goalposts to useDashboardPanels                ❌ NOT passed
useDashboardPanels.tsx GoalpostsSystem prop                 ❌ NOT in interface
useDashboardPanels.tsx panel registration                   ❌ NOT registered

MCP TOOL (❌ NOT implemented)
─────────────────────────────────────────────────────────────────
codrag_goalposts in TOOLS list                             ❌ NOT in tools
tool_goalposts_view() method                               ❌ NOT implemented
tool_goalposts_detail() method                             ❌ NOT implemented
handle_tools_call dispatch                                 ❌ NOT added
MCP instructions string mention                            ❌ NOT mentioned
```

### ⚠️ NEW FINDING: Type Export Gap (WILL BREAK BUILD)

**File**: [index.ts](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/index.ts#L10-L78)

The `@codrag/ui` package index explicitly lists every exported type on lines 10-78. The Goalposts types (`GoalpostCategory`, `GoalpostState`, `GoalpostTask`, `GoalpostProposal`, `GoalpostQuestion`, `GoalpostsResponse`) are **NOT in this list**.

The hook `useGoalpostsSystem.ts` line 3 does:
```typescript
import type { GoalpostsResponse, GoalpostProposal, GoalpostQuestion } from '@codrag/ui'
```

This import **will fail at build time** because these types are not re-exported from the package index. They exist in `types.ts` but aren't in the explicit export list.

**Fix needed**: Add to `index.ts` after line 185 (where AuditPanel types are exported):
```typescript
// Types - Goalposts (Phase 57)
export type { GoalpostCategory, GoalpostState, GoalpostTask, GoalpostProposal, GoalpostQuestion, GoalpostsResponse } from './types';
```

### Summary: What Needs to Be Done to Complete Goalposts

| # | Item | Effort | Blocks |
|---|------|--------|--------|
| 1 | Fix BUG-1: Proposal dedup in `goalposts_planner.py` | Small | Production correctness |
| 2 | Fix BUG-2: Interval leak in `useGoalpostsSystem.ts` | Small | Memory leak |
| 3 | Add Goalpost type exports to `@codrag/ui` `index.ts` | Trivial | **Blocks entire frontend** |
| 4 | Create `GoalpostsPanel.tsx` component | Medium | Dashboard visibility |
| 5 | Wire hook in `App.tsx` (import, call, pass) | Small | Dashboard connectivity |
| 6 | Add Goalposts to `useDashboardPanels.tsx` | Small | Panel appears in dashboard |
| 7 | Fix DEBT-1: Atomic file writes | Small | Data safety |
| 8 | Implement `codrag_goalposts` MCP tool | Medium | AI assistant integration |
| 9 | Remove unreachable `'refined'` state | Trivial | Clean API contract |
| 10 | Add `PipelineTask.GOALPOSTS` config | Small | Correct LLM settings |
