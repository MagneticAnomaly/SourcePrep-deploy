# Website vs App Feature Audit & Copy Refinement

> **Status**: Audit complete. Resolved items implemented. Remaining items tracked in `MASTER_TODO.md` and `MARKETING_MASTER_TODO.md`.

## 1. Website Content Map

### Marketing Site (`runprep.io`)
- **Homepage (`/`)**: Hero, 2-step integration demo, feature grid, FAQ preview, trust strip.
- **`/pricing`**: Free / Starter / Pro / Team / Enterprise tiers.
- **`/security`**: Local-first, no telemetry, privacy policy (merged).
- **`/about`**, **`/faq`**, **`/download`**, **`/careers`**, **`/changelog`**, **`/blog`**, **`/community`**, **`/contact`**, **`/privacy`**, **`/terms`**.

### Docs Site (`docs.runprep.io`)
- Getting Started, MCP, Guides (Embeddings, Path Weights, Models), Concepts, Dashboard, CLI, Troubleshooting, FAQ.

### Support & Payments
- `support.runprep.io`: Headless GitHub (Discussions/Issues).
- `payments.runprep.io`: Lemon Squeezy checkout, recovery, success.

---

## 2. App Feature Map (Verified from Codebase)

### Core Engine & Retrieval
- **Native Embeddings**: ONNX `nomic-ai/nomic-embed-text-v1.5` (768 dim, ~132 MB). **v2-moe evaluated and rejected as default** — see [Embedding Model Decision](#embedding-model-decision) below.
- **Ollama**: Important for enrichment LLMs (3b catalogue + 14b deep reasoning). Running without LLMs is possible but **not recommended**.
- **Incremental Watcher**: Real-time Rust-powered file hashing and rebuilding (Pro/Starter only).
- **Path Weights**: User-defined multipliers (0.0–2.0). Available on **all tiers** including Free.
- **Context Compression**: 10–16× context compression. **Pro/Starter only**.

### Trace Graph & Enrichment
- **Rust Trace Builder**: AST parsing (imports, calls, hierarchy). Manual build available on **Free**; auto-build requires Pro/Starter.
- **Enrichment Pipeline**: **9 stages** in 2 groups:
  - Fast Sync (4): structural → catalogue → validation → knowledge
  - Deep Enrichment (5): enrichment → clustering → atlas → deepening → deep_knowledge
- **Codebase Atlas (Phase 29B)**: Pre-retrieval routing (NOT context injection).

### Feature Gating (Verified from `feature_gate.py`)
| Tier | Projects | Automation | Compression | MCP trace_expand | Trace Index |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Free** | 1 | Manual only | No | No | Yes (manual) |
| **Starter** | Unlimited | Full | Yes | Yes | Yes (auto) |
| **Pro** | Unlimited | Full | Yes | Yes | Yes (auto) |
| Starter = Pro with 4-month time limit. |

### Dashboard Panels
- Status: Index Health, Live Sync, Process Logs, AI Gateway.
- Knowledge: File Tree, Graph Scope.
- Search: Knowledge Query, Retrieved Context, Context Assembler, Prompt Buffer.
- Deep: Graph Enrichment Pipeline, Deep Analysis, Token Budget.
- Exploration: Code Graph Explorer, Codebase Atlas.

---

## 3. Resolved Actions

| Item | Resolution | File(s) Changed |
| :--- | :--- | :--- |
| Atlas "injected into every AI query" | ✅ Updated to "pre-retrieval routing" | `packages/ui/src/config/panelRegistry.ts` |
| Homepage "0 bytes sent to cloud" | ✅ Changed to "Local-first — your code stays on your machine" | `websites/apps/marketing/src/app/page.tsx` |
| Pricing Free tier wrong | ✅ Corrected: 1 project, manual only | `websites/apps/marketing/src/app/pricing/page.tsx` |
| Pricing Starter "3 projects" wrong | ✅ Corrected: Full Pro, time-limited | `websites/apps/marketing/src/app/pricing/page.tsx` |
| Pricing "100% local" overstatement | ✅ Changed to "Local-first" + BYOK mention | `websites/apps/marketing/src/app/pricing/page.tsx` |
| About page outdated copy | ✅ Rewritten to match current positioning | `websites/apps/marketing/src/app/about/page.tsx` |
| Code Graph badge "Pro" wrong | ✅ Changed to "Built-in" (trace_index is FREE) | `packages/ui/src/components/marketing/FeatureBlocks.tsx` |
| Pipeline "multi-pass" → 9-stage | ✅ Updated to "9-stage pipeline" | `packages/ui/src/components/marketing/FeatureBlocks.tsx` |
| "Epistemic scoring" in feature copy | ✅ Changed to "confidence scoring" | `packages/ui/src/components/marketing/FeatureBlocks.tsx` |
| Dashboard Starter 3-project hardcode | ✅ Removed (Starter = Pro) | `src/prep/dashboard/src/App.tsx` |

---

## 4. Resolved Answers to Strategic Questions

1. **Ollama messaging**: Keep Ollama prominent. It's essential for enrichment LLMs (3b + 14b). BYOK cloud is the alternative. Running without LLMs is possible but not recommended.
2. **Dashboard vs IDE**: Lead with MCP/IDE. Users type "prep" in their editor chat. The dashboard is a configuration backend, not the primary workflow.
3. **Atlas Routing**: Use "Smarter Context" as the headline. Use "pre-retrieval routing" in technical details.
4. **Academic terminology**: Needs its own research sprint (added to `MASTER_TODO.md`). Keep academic language but ensure it's not impenetrable.
5. **Path Weights**: Headline feature — "makes the app look very sophisticated".
6. **Free tier**: Free = 1 project + all features manual. Corrected across pricing and feature blocks.
7. **Perpetual license**: Needs competitive research (Sublime Text, JetBrains, Sketch). Added to `MARKETING_MASTER_TODO.md`.
8. **Screenshots**: Still needed. Added to `MARKETING_MASTER_TODO.md`.

---

## 5. Remaining Gaps

- **Embedding model upgrade**: ✅ RESOLVED — see Embedding Model Decision below.
- **Academic terminology audit**: Full cross-codebase rename research needed. (`MASTER_TODO.md`)
- **Debug log export guide**: Needed for FAQ + Troubleshooting + Security page. (`MASTER_TODO.md` + `MARKETING_MASTER_TODO.md`)
- **Community page**: Undefined scope, may not be MVP. (`MASTER_TODO.md`)
- **Support portal**: Private/SLA support for paid tiers undefined. (`MARKETING_MASTER_TODO.md`)
- **Homepage screenshots**: 3 placeholder assets still needed. (`MARKETING_MASTER_TODO.md`)
- **Perpetual license messaging**: Competitive research needed. (`MARKETING_MASTER_TODO.md`)
- **Lemon Squeezy post-purchase flow**: Needs investigation. (`MARKETING_MASTER_TODO.md`)

---

## 6. Embedding Model Decision

✅ **Moved to [Phase 33 — Embedding Model Evaluation](../Phase33_embed-tests/README.md).**

Decision finalized (2026-02-21): `nomic-embed-text-v1.5` ONNX is the sole production embedding model. `v2-moe` was evaluated across 10 repos and rejected due to score calibration fragility and an Ollama context limit bug (hard 512-token limit).
