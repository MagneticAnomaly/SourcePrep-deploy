# Phase 73.2b — Context Budget Empirical Analysis

> Date: 2026-04-05 | Testing actual MCP output at different budget levels

---

## Test Methodology

Called `prep` MCP tool at 6K, 12K, and 20K `max_chars` against the live Prep index.
Analyzed actual output structure, section breakdown, and content quality at each level.

## Finding 1: Budget Has No Effect — Output Is Identical at 6K, 12K, and 20K

```
┌────────────┬──────────────┬──────────┬──────┬───────────┐
│ Budget     │ Actual Output│ Hub Files│ Lines│ Fill Rate │
├────────────┼──────────────┼──────────┼──────┼───────────┤
│  6,000     │  7,948 chars │    1     │  99  │  133% (!) │
│ 12,000     │  8,542 chars │    2     │ 111  │   71%     │
│ 20,000     │  8,542 chars │    2     │ 111  │   43%     │
└────────────┴──────────────┴──────────┴──────┴───────────┘
```

**The 12K and 20K outputs are byte-identical.** The system has only ~8.5K chars worth of content to serve, regardless of budget. This means:

1. The hub/neighbor system can only find 2 hub files worth showing (from the focus areas)
2. The architecture section is a fixed-size dump (~3K) appended regardless of budget
3. Extra budget is completely wasted — there's no content to fill it

> [!CAUTION]
> **Raising budgets from 20K → 50K → 75K is meaningless if the backend can only produce 8.5K of content.** The budget increase is a "dial that goes to 11" — it looks bigger but doesn't do anything. We need to fix the content production side first.

---

## Finding 2: Architecture Section Is 35-38% of Output — And 91% Noise

Section breakdown of the actual output:

```
┌─────────────────────┬────────┬───────┬──────────────────────────────┐
│ Section             │ Chars  │   %   │ Quality Assessment           │
├─────────────────────┼────────┼───────┼──────────────────────────────┤
│ Module list (tiered)│  2,847 │ 33.3% │ ✅ EXCELLENT — 6 relevant   │
│                     │        │       │    modules with rich summaries│
├─────────────────────┼────────┼───────┼──────────────────────────────┤
│ Hub content         │    593 │  6.9% │ ⚠️ STARVED — only 2 hub     │
│                     │        │       │    files, should be 5-8      │
├─────────────────────┼────────┼───────┼──────────────────────────────┤
│ Architecture dump   │  2,972 │ 34.8% │ ❌ NOISE — 3742 modules,    │
│                     │        │       │    only 3/35 shown (9%)      │
│                     │        │       │    relevant to Prep.       │
│                     │        │       │    Includes: Javalin, OkHttp,│
│                     │        │       │    Gson, JPMS, Slim Framework│
├─────────────────────┼────────┼───────┼──────────────────────────────┤
│ Header + footer     │    135 │  1.6% │ OK                           │
└─────────────────────┴────────┴───────┴──────────────────────────────┘
```

### Architecture content quality:

| Category | Count | % | Examples |
|----------|-------|---|---------|
| Relevant to Prep | 3 | 9% | Pipeline Orchestration, Prep Evaluation |
| Generic/numbered names | 7 | 20% | "Ui Subsystem (Packages) #2", "#77", "#93" |
| 3rd-party library noise | 9 | 26% | Javalin, OkHttp, Gson, Slim, Lucide |
| Unrelated/unclear | 16 | 46% | "React Native Music Platform", "Enterprise Security" |

### Root cause
The architecture context shows **all 3742 modules in the global index**, not just Prep-relevant ones. This index includes UI library dependencies (OkHttp, Gson, Javalin) that happen to be in the monorepo. The cap (30 modules) just limits how many get shown — but the top 30 by file count are dominated by library code, not Prep code.

---

## Finding 3: Hub Content Is Severely Under-Budgeted

The hub section should be the **most valuable** part of the ambient context — it shows the most-connected files with full content. But it gets only **7% of the output**:

| What should be budget allocation | Actual | Proposed |
|----------------------------------|--------|----------|
| Module list: orientation | 33% → 30% | Keep — this is great |
| Hub files: structural spine | 7% → **50%** | Give most of the budget to actual code |
| Architecture annotations: user curations | 35% → **5%** | Only show if user has annotations |
| Neighbor files: structural context | 0% → **15%** | LOD 2-3 signatures for imports/exports |

---

## Finding 4: Header Still Has Stale Info

The header on the running daemon still shows the old format:
```
## Prep Context (2 chunks, 5426 chars)
Hubs: 8 | Modules: 30 | Neighbors: 0
```

Our Phase 73.2 changes (clean header) haven't taken effect because the MCP daemon hasn't been restarted. This is expected — the changes are in the code but the live server is running from the pre-change version.

---

## Finding 5: What We Actually Need at Each Tier

### Tier 2.5 (20K, local models) — Focus on orientation only
What fits: Module list (3K) + 3-4 hub files at LOD 0 (12K) + 2-3 neighbors at LOD 2 (2K) = ~17K
**Current problem:** Only 8.5K produced. Need backend to serve more hub content.

### Tier 2 (30K, Cursor/Windsurf) — Add structural graph
What fits: Module list (3K) + 6-8 hub files (20K) + 5-6 neighbors at LOD 1 (5K) + concepts (2K) = ~30K
**Extra value over 2.5:** More hub files → agent can plan 2-file changes without search.

### Tier 1 (50K, Opus/Gemini) — Add deep context
What fits: Module list (3K) + 10-12 hub files (30K) + 10 neighbors at LOD 0-1 (10K) + concepts (5K) + cross-module chains (2K) = ~50K
**Extra value over 2:** Agent can plan multi-file refactors in one shot.

### Tier 1 orient (75K, first call) — Maximum orientation
What fits: Everything in Tier 1 + extended hub content at LOD 0 + more neighbor depth = ~65K actual
**Purpose:** Build the complete mental model in one call. After this, standard budget is enough.

---

## Recommendations (Prioritized)

### P0: Fix the Architecture Section NOW
The architecture section is burning 35% of every response with noise. Two options:

**Option A (quick):** Skip the architecture section entirely in the MCP response (it's already represented in the module list). Just don't append it. Save 3K chars immediately.

**Option B (proper):** Filter the architecture modules to only show modules from the **project's own segment**, not global. This requires a segment filter in `get_architecture_context()`.

### P1: Increase Hub Coverage
The backend currently serves only 2 hub files even with 20K budget. The hub budget is `70% of remaining_budget` but `remaining_budget = max_chars - module_list_chars`. The module list + architecture noise leaves almost no room for hubs.

Fix: After removing the architecture section (P0), the hub budget jumps from ~2K to ~12K at 20K budget — enough for 5-6 full hub files.

### P2: Restart Daemon After Code Changes
All our Phase 73.2 changes (clean header, architecture budget cap, subsystem hint fix) are invisible until the MCP daemon restarts. After P0/P1, restart to see the combined effect.

### P3: Only Then Evaluate Higher Budgets
Once the output is actually quality-filling the budget, THEN we can meaningfully test whether 50K is better than 30K. Right now, both produce identical 8.5K content.

---

## Key Insight

> [!IMPORTANT]
> **The budget tiers we set (20K/30K/50K) are correct in principle but meaningless in practice until the content production pipeline fills those budgets with quality content.** The highest-impact fix is not raising the budget — it's removing the architecture noise that starves the hub content. After that, the budgets will naturally produce differentiated output at each tier.
