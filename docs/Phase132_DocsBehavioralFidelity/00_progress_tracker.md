# Phase 132 — Progress Tracker

> Companion to `README.md`. The README is the *plan*; this is the *state*.
> Update this file whenever a Tier item is touched.
>
> **Note (2026-05-26):** Phase 138 landed and renamed `/concepts/*` →
> `/how-it-works/*` and moved 4 explainer guides into the same section.
> Table-row labels below (e.g. `concepts/indexing`, `guides/embeddings`)
> reflect the path at the time of audit. Current URLs are
> `/how-it-works/indexing`, `/how-it-works/embeddings`, etc.

## Status snapshot — 2026-05-14 (late night)

**Overall:** ~90% complete. **All 6 desk tiers done (A through F).**
Remaining: install-required batch (Tier A), three CI fidelity tests, the
"what we found" findings memo. Phase 138 (Concepts rename + explainer
migration) scaffolded as a deferred follow-up.

### Tier F drift fixes landed 2026-05-14

| Fix | File touched | Why |
|---|---|---|
| Two `prep serve --debug` references → `prep mcp --debug` | `/troubleshooting/page.tsx` | `serve` command has no `--debug` flag; `mcp` does |
| `prep config set <key> <value>` → `prep config <key> <value>` | `/troubleshooting/page.tsx` | Real signature is two positional args |
| `prep config [--set <value>]` → `prep config [<value>]` positional | `/cli/commands/page.tsx` | Same root cause as above |

### Tier E drift fixes landed 2026-05-14

| Fix | File touched | Why |
|---|---|---|
| `prep serve` "PREP_LOG_LEVEL=DEBUG" hint → "prep mcp --debug" | `/cli/commands/page.tsx` | `PREP_LOG_LEVEL` never read in src/; logging hardcoded to INFO |
| `PREP_LOG_LEVEL` row removed; `PREP_DEV_MODE` added; `PREP_TIER` updated to note dev-mode dependency | `/cli/config/page.tsx` | Verified at `feature_gate.py:170-176` |
| `prep audit` CLI examples → `prep opportunities` (real command) | `/guides/codebase-audit/page.tsx` | `prep audit` does not exist; audit is MCP/REST/dashboard-triggered |

### Course-correction landed 2026-05-14 (legacy over-hide)

| Action | File touched | Why |
|---|---|---|
| RESTORED `/guides/models` + `/guides/byok-batching` + `/guides/dynamic-model-loading` to sidebar + sitemap | `docs.ts`, `sitemap.ts` | Initial hide was over-broad — only `/guides/model-advisor` is genuinely deprecated. The other three are essential: models is the AI Gateway page (most important guide), byok-batching covers cloud BYOK, dynamic-model-loading clarifies local-LLM support. |
| Renamed `/guides/models` → "AI Gateway" and rewrote recommendation section | `/guides/models/page.tsx` | Replaces the deprecated Model Setup Advisor with three simple stacks: cloud-first (matches dashboard screenshot, kimi-k2.6:cloud + gemini-3-flash-preview:cloud + qwen/qwen3.6-plus on OpenRouter), simpler all-Ollama-Cloud, and local-only Qwen3. |

### Tier D drift fixes landed 2026-05-14

| Fix | File touched | Why |
|---|---|---|
| "Four MCP tools" framing → "One `prep_audit` tool with action modes" | `/guides/codebase-audit/page.tsx` | `_CORE_TOOLS` advertises only `prep_audit`; others are LEGACY aliases |
| `nomic-embed-code` dim 4 096 → 3 584 (Matryoshka 768) | `/guides/embeddings/page.tsx` | `embedder.py:35` declares dim 3584 |

### Tier C drift fixes landed 2026-05-14

| Fix | File touched | Why |
|---|---|---|
| Storage backend `LanceDB / Qdrant / Chroma` → "stored locally on your machine" (clarity-tightened from numpy/JSON/SQLite jargon) | `/concepts/indexing/page.tsx` | No vector-DB deps in `src/prep/`; storage format isn't user-relevant; "local-first" is |
| Intent classifier `docs/tests/code/default` → "kind of question being asked" + link to MCP taxonomy (clarity-tightened from inline 7-enum list) | `/concepts/context/page.tsx` | Real 7-intent classifier already documented on `/mcp`; concepts page only needs the WHY, not the enum |

### Tier A drift fixes landed 2026-05-14

| Fix | File touched | Why |
|---|---|---|
| Mac App Store / MS Store / Linux wording | `/getting-started/page.tsx`, `/getting-started/installation/page.tsx` | Mac App Store **never** (sandboxing); MS Store + Linux **planned post-MVP** |
| Free-tier auto-trace claim | `/getting-started/page.tsx` | `feature_gate.py` confirms `auto_trace=Tier.FREE`; prior docs said Free was manual-only |
| "Graph Status → Build" panel reference | `/getting-started/page.tsx` | Panel was consolidated into `graph-structure` (Graph Scope) |
| "Language-aware docs compression: built in" | `/getting-started/page.tsx` Next Steps | `/guides/compression` lists it as roadmap, not shipping |

## Sequencing decision (2026-05-14)

This phase blocks Phase 137 (`docs/Phase137_DocsLiveAssetIntegration/`). Do
not start the Phase 137 page audit until at minimum Tiers A, B, C are
complete here. Reason: Phase 137 places live embeds based on what each page
*says*; rewriting page text during Phase 132 after Phase 137 places embeds
would force re-placement.

Deferred items (block on external factors, don't gate the rest):

- **Tier A onboarding fresh-install verification** — needs Mac/Windows
  install runs; batch when a fresh-install session happens
- **Tier D `team-sync` and `enterprise-deploy`** — depend on the
  SourcePrep-deploy public repo state (README flags this)
- **Tier D `byok-batching` and `dynamic-model-loading`** — incur real cloud
  spend; batch with other cloud-spend tasks

That leaves desk-bound work to attack first: Tier B remainder, Tier C, Tier
D desk items, Tier E, Tier F.

## Tier checklist with status

### Tier A — onboarding & first-run

| Item | Status | Notes |
|---|---|---|
| `getting-started/installation` | 🟢 desk-done | Mac App Store / MS Store / Linux drift fixed. Install-required batch flagged for fresh-install session. |
| `getting-started/quick-start` | 🟢 desk-done | Scope panel name verified; analyzer count "11" verified; no Free-tier-trace claim on this page. |
| `getting-started` (parent) | 🟢 desk-done | Free-tier trace claim corrected vs `feature_gate.py`; "Graph Status" panel reference updated to "Graph Scope"; "language-aware docs compression: built in" corrected to "on the roadmap". See `01_TierA_onboarding.md` resolution table. |

### Tier B — MCP integration

| Item | Status | Notes |
|---|---|---|
| `mcp/page.tsx` overview | ✅ done | Completed in prior session; see Task #20. Added `COMPARE` intent row; surfaced undocumented `roadmap` action branch in `server.py:4252` (out of scope to either document or remove — needs product decision). |
| `mcp/ides` | 🟢 desk-done | Renders from single-source `mcp-setup.ts`; intro line cleaned up (dropped registry-absent Roo/CodeGPT). AnimatedIDE storyId verified. See `02_TierB_mcp.md`. |
| `mcp/terminal` | 🟢 desk-done | Renders from same registry; intro matches CLI entries exactly. No edits. See `02_TierB_mcp.md`. |
| `mcp/paperclip` | 🟢 desk-done | 5 plugin tools verified vs `packages/paperclip-plugin-prep/src/worker/index.ts`. npm name verified. Brand drift `prep.dev` → `sourceprep.io/download` fixed. GitHub path `packages/paperclip-plugin` → `packages/paperclip-plugin-prep` fixed. AgentOpsPanel storyId verified. See `02_TierB_mcp.md`. |

### Tier C — concept pages

| Item | Status | Notes |
|---|---|---|
| `concepts/indexing` | 🟢 desk-done | Storage-backend drift (LanceDB → numpy+JSON) fixed. BLAKE3/watchdog/embedder verified. See `03_TierC_concepts.md`. |
| `concepts/code-graph` | 🟢 desk-done | 3-relationship-type framing is intentional simplification (real graph has 5+ edge kinds); flagged for product call. TraceGraph storyId verified. |
| `concepts/graph-enrichment` | 🟢 desk-done | 15 stages 1:1 with `StageId` enum verified. DEEP_REASONING/MODULE_SYNTHESIS display labels + stage-id footnotes confirmed intentional. Understanding-score weights + decay multipliers flagged for deeper future check. |
| `concepts/context` | 🟢 desk-done | Intent classifier drift fixed (docs/tests/code/default → real 7-intent taxonomy). Context Assembler panel verified. BM25 wiring + default k/max_chars flagged for Tier D. |

### Tier D — guides

| Item | Status | Notes |
|---|---|---|
| `guides/embeddings` | 🟢 desk-done | Fixed `nomic-embed-code` dim 4096 → 3584. R@1 + query-speed benchmark numbers flagged for re-run. See `04_TierD_guides.md`. |
| `guides/audit-enrichment` | 🟢 desk-done | Enriched-field schema verified vs CLAUDE.md risk-score formula. SARIF round-trip verified vs `prep_audit` schema. `hub_status` 4-vs-5-enum is defensible simplification. |
| `guides/codebase-audit` | 🟢 desk-done | "Four MCP tools" framing → real "one `prep_audit` tool with action modes" + action table. 11 analyzers, defaults, output paths all verified. |
| `guides/smart-search` | 🟢 desk-done | 7 intents, tiebreaker priority, trigger words, query rewriting all match `intent.py` 1:1. No edits. |
| `guides/compression` | 🟢 desk-done | Verified in Tier A audit (3–20× headline confirmed); LOD table cross-checked. |
| `guides/concurrency-discovery` | 🟢 desk-done | Both `/compute/concurrency/clear` + `/compute/scheduler` endpoints verified. 24-hour lock + Phase 82 latency-aware design aligns. |
| `guides/path-weights` | 🟢 desk-done | PUT/GET API verified at `crud.py:443`; range 0.0–2.0 clamping at `repo_policy.py:92`. Final-score formula narrative not source-verified. |
| `guides/knowledge-scope` | 🟢 desk-done | All 5 endpoints verified (`included_paths` GET/PUT + `scope/{add,remove,status}` in dedicated `routers/scope.py`). Storybook ID resolves. |
| `guides/byok-batching` | ⏳ defer | Cloud spend |
| `guides/team-sync` | ⏳ defer | External repo state |
| `guides/enterprise-deploy` | ⏳ defer | External repo state |
| `guides/dynamic-model-loading` | ⏳ defer | Two-slot VRAM setup |
| `guides/model-advisor` | 🔒 hidden 2026-05-14 | Deprecated. Per `project_llm_strategy.md` user decision: hidden from sidebar + sitemap. Replaced by a simple model-recommendation list on `/guides/models` (cloud-first / all-Ollama / local-only). Page file retained; safe to delete in a future cleanup pass. |
| `guides/models` | 🟢 desk-done 2026-05-14 | RESTORED (initial over-hide corrected). Renamed page from "Model Configuration" to **AI Gateway** — most important LLM guide. Three recommended-stack tables added (cloud-first matching dashboard screenshot; all-Ollama-Cloud simpler variant; local-only Qwen3). Removed link to deprecated model-advisor. |
| `guides/dynamic-model-loading` | 🟢 visible 2026-05-14 | RESTORED. Important explainer about local-LLM VRAM balancing — relevant for users running local models. Not deeply behavior-audited this pass; flag for content review. |
| `guides/byok-batching` | 🟢 visible 2026-05-14 | RESTORED. Covers cloud BYOK batching — Ollama-Cloud-first strategy relevant. Not deeply behavior-audited this pass; deferred (cloud spend to verify). |

### Tier E — CLI reference

| Item | Status | Notes |
|---|---|---|
| `cli/commands` | 🟢 desk-done | All 20 documented commands verified against `cli.py` `@app.command()` decorators. Removed fictional `PREP_LOG_LEVEL` hint. See `05_TierE_cli.md`. |
| `cli/config` | 🟢 desk-done | `PREP_DATA_DIR`, `PREP_ENGINE`, `PREP_TIER` verified. Removed fictional `PREP_LOG_LEVEL`; added `PREP_DEV_MODE` (required for `PREP_TIER` to take effect). Phase 113 migration sentinel confirmed. |

### Tier F — operational

| Item | Status | Notes |
|---|---|---|
| `troubleshooting` | 🟢 desk-done | Fixed two `prep serve --debug` references (flag doesn't exist; real path is `prep mcp --debug`). Fixed `prep config set <key> <value>` syntax to actual positional `prep config <key> <value>`. Other claims (port, error codes, defaults, paths) all verified. See `06_TierF_operational.md`. |
| `dashboard` (page) | 🟢 desk-done | Panel categories `status/search/context/config` verified against `panelRegistry.ts` (4 categories, ~27 panel entries). Panel Picker UI claims not deeply verified. StoryEmbed references flagged for Phase 137. |

### CI fidelity tests (definition of done #2)

| Test | Status |
|---|---|
| Sidebar / sitemap registry resolves to real `page.tsx` | ⏸ not wired |
| Panel-registry `docsUrl` anchors resolve to `AnchorHeading id=` | ⏸ not wired (but anchors verified manually in Phase 130 follow-up #18) |
| `<StoryEmbed storyId=>` resolves to real story | ⏸ not wired |
| Atlas IDENTITY brand check | ✅ landed in Phase 130 Issue 13 |
| Active-zones ghost filter | ✅ landed in Phase 130 Issue 13 |

### "What we found" memo (definition of done #3)

⏸ Not yet written. Should land as a final `99_findings_memo.md` in this
folder once Tier A–F are done, summarizing the top three behavioral-vs-docs
gaps as feedback to the broader team.

## Dogfooding findings (out of scope, documented elsewhere)

Two findings surfaced during this audit that are product gaps, not docs gaps.
Cross-referenced here for visibility:

- **Sparse `prep` no-arg atlas** — see
  `docs/Phase82_MCP-Dogfooding/20_Followup_2026-05-13.md` (P82-F5, P82-F6 in
  MASTER_TODO)
- **LLM module-summary brand drift** — same doc (P82-F7, P82-F8)

## How to add a tier-item entry to this tracker

When you finish (or partially finish) a tier item:

1. Update the row's status: ⏸ → 🟡 (partial) or ✅ (done) or ⏳ (deferred
   with reason) or ❌ (punted to product task)
2. Add a 1-2 line note. Link to a separate audit doc if the item was big
   enough to warrant one (e.g., `01_TierA_onboarding.md`).
3. Update the "Status snapshot" at the top.
