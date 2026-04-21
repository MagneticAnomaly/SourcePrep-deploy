# Documentation Website UX Audit & Gap Analysis

> **Status**: Audit complete. Resolved items implemented. Remaining items tracked in `MASTER_TODO.md` and `MARKETING_MASTER_TODO.md`.

## 1. Docs Content Map (`docs.codrag.io`)

### Getting Started (`/getting-started`)
- **The "Trust Loop"**: Install → Launch App → Add Repo → Connect Editor → Verify.
- **Sub-pages**: `/installation`, `/quick-start`.

### Concepts (`/concepts`)
- **`/indexing`**: Semantic vs. structural indexing.
- **`/code-graph`**: How the Rust AST parser builds the trace graph.
- **`/graph-enrichment`**: The multi-pass LLM pipeline for domain tags and modules.
- **`/context`**: How retrieval and context assembly work.

### Guides (`/guides`)
- **`/embeddings`**: Breakdown of Native ONNX (Default) vs. Ollama (`nomic-embed-code`).
- **`/path-weights`**: How to steer search relevance hierarchically.
- **`/compression`**: Setting up 10–16× context compression.
- **`/models`**: Configuring LLMs for enrichment and analysis.

### Integration & Reference
- **`/mcp/cursor` & `/mcp/windsurf`**: Editor-specific connection guides.
- **`/dashboard`**: Walkthrough of UI panels.
- **`/cli`**: Command-line reference.
- **`/troubleshooting`**: Fixes for setup and build issues.
- **`/faq`**: Deep dive into context windows, token efficiency, and RAG.

---

## 2. Docs Gaps (Verified Against Codebase)

| Gap | Details | Status |
| :--- | :--- | :--- |
| **Codebase Atlas missing** | No concept page for pre-retrieval routing / subsystem segmentation. | TODO: Create `/concepts/atlas-routing` once Phase 29B lands. Added to `MARKETING_MASTER_TODO.md`. |
| **Pipeline stage count wrong** | Docs/website previously said "6-stage" or "multi-pass". Actual count is **9 stages** (Fast Sync 4 + Deep Enrichment 5). | ✅ Fixed in `FeatureBlocks.tsx` (marketing). TODO: Fix in `/concepts/graph-enrichment` (docs). Added to `MARKETING_MASTER_TODO.md`. |
| **Free tier described incorrectly** | Various places implied Trace Graph/MCP were Pro-only. Actual: Free = 1 project + manual only. Trace index, trace search, path weights, basic MCP all FREE. | ✅ Fixed on pricing page. TODO: Add `<Badge>Pro</Badge>` to docs for auto-rebuild, scheduled enrichment. Added to `MASTER_TODO.md`. |
| **"Verify" step in Getting Started** | Uses `trace_expand=true`. This actually works on Free (trace_index is FREE, only auto-trace is gated). But Free users must manually build the trace graph first. | TODO: Clarify in Getting Started that Free users need a manual trace build before this step. Added to `MARKETING_MASTER_TODO.md`. |
| **Panel name drift** | Dashboard docs should reflect current panel names (Graph Scope, Index Health, etc.). | TODO: Audit panel names in `/dashboard` docs page. |

---

## 3. Resolved Answers

1. **Codebase Atlas location**: Own concept page (`/concepts/atlas-routing`) — not buried under `/concepts/context`. Create once Phase 29B implementation is complete.
2. **Deep Analysis guide**: Yes, needed. Users spend their own LLM tokens on enrichment and need to understand budget controls. TODO item.
3. **Free Tier Verification**: The verify step (trace_expand) technically works on Free since trace_index is FREE. The issue is Free users must do a manual trace build first. Clarify this in the Getting Started guide.
4. **CLI/Dashboard toggle**: Large scope — needs its own sprint. Added to `MASTER_TODO.md` as a design task (toggle component, default to Dashboard).
5. **`<Badge>Pro</Badge>` component**: Yes — implement across docs. Pro-only features: auto-rebuild, scheduled enrichment, mcp_trace_expand, multi-repo agent. Added to `MASTER_TODO.md`.
6. **Academic terminology**: Needs its own research sprint. Keep academic language but find accessible alternatives for marketing. May rename panel titles, API fields, and docs concepts. Added to `MASTER_TODO.md`.
7. **Debug log export**: Yes — add to FAQ, Troubleshooting, and Security/Privacy page. Added to both `MASTER_TODO.md` and `MARKETING_MASTER_TODO.md`.

---

## 4. Remaining Gaps

- **`/concepts/atlas-routing`**: Blocked on Phase 29B completion.
- **`/concepts/graph-enrichment`**: Needs stage count update (9 stages).
- **`<Badge>Pro</Badge>` component**: Needs design + implementation across docs.
- **CLI/Dashboard toggle**: Large scope, needs strategy before building.
- **Debug log export guide**: Needed across FAQ + Troubleshooting + Security.
- **Academic terminology audit**: Cross-codebase rename research sprint.
- **Getting Started "Verify" clarification**: Free users need manual trace build first.

