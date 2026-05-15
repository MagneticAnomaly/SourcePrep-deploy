# Phase 132 Tier C — Concept Pages

> **Pages audited:** `/concepts/indexing`, `/concepts/code-graph`,
> `/concepts/graph-enrichment`, `/concepts/context`
> **Method:** desk verification on 2026-05-14 against source-of-truth files
> (`stages.py`, `intent.py`, `embedder_factory.py`, trace analyzers).

## `/concepts/indexing`

### Claims

1. **`prep-walker` (Rust) scans + BLAKE3 hashes** — ✅ verified.
   `engine/crates/prep-walker/` lists `blake3` as a Cargo dependency.
2. **Tree-sitter parsing** — ✅ verified by trace analyzer imports
   throughout `src/prep/core/trace/analyzers/`.
3. **Native Embedder (ONNX/nomic-embed-text) or optional Ollama** — ✅
   verified. `src/prep/services/embedder_factory.py` resolves to
   `NativeEmbedder` first, falls back to `OllamaEmbedder`.
4. **768-dimensional vectors** — left as-is (nomic-embed-text-v1.5 is 768
   dim per Nomic's published spec; no contradicting evidence in code).
5. **"Stored in a local LanceDB instance (or Qdrant/Chroma if configured)"** —
   ⚠ **fixed 2026-05-14**: zero references to LanceDB, Qdrant, or Chroma
   anywhere in `src/prep/`. Per CLAUDE.md "Storage" section, vectors are
   stored as JSON files + numpy arrays alongside a SQLite project registry.
   Page reworded accordingly.
6. **Real-time `watchdog` file watcher** — ✅ verified at
   `src/prep/core/watcher.py`.
7. **"<200 ms per save" incremental update** — perf claim, deferred to
   benchmark batch.
8. **Status badges Fresh / Stale / Building** — not verified this pass;
   leave for Tier F dashboard panel-category audit.
9. **Composition Code/Instructions/Graph** — not verified this pass.
10. **Default exclusions enumeration** — plausible defaults
    (`node_modules/`, `dist/`, `build/`, `.git/`, `.next/`, `target/`,
    `venv/`, `__pycache__/`); spot-check vs prep-walker config in a future
    pass.

### Result

🟢 Desk-done with one substantive fix (storage backend).

## `/concepts/code-graph`

### Claims

1. **Rust engine `prep-engine` + Tree-sitter** — ✅ verified.
2. **"Three relationship types: Definitions / References / Imports"** —
   ⚠ **design choice, not a bug**: the underlying trace graph carries at
   least 5 edge kinds (`contains`, `imports`, `implements`, `configures`,
   `listens_to` per atlas data) plus inferred kinds (`calls`, etc.). The
   page's 3-type framing is a user-facing simplification. Defensible as a
   conceptual narrative; flag if a later audit wants to expose the full
   edge-kind enumeration to power users.
3. **"~50k files in seconds" Rust speed claim** — perf; deferred.
4. **Multi-language list (Python, TypeScript, JavaScript, Go, Rust, Java,
   C, C++)** — analyzer modules exist for Python and JS; Rust/Java/etc.
   coverage via generic_regex analyzer. Defensible but could be tightened.
5. **`dashboard-trace-graph--default` Storybook embed** — ✅ verified.
   `packages/ui/src/stories/trace/TraceGraph.stories.tsx:6` declares
   `title: 'Dashboard/Trace/Graph'` and exports a `Default` variant.
6. **"15-stage Graph Enrichment pipeline" link** — ✅ verified (see next
   page).

### Result

🟢 Desk-done. No fixes; one design call flagged for future review.

## `/concepts/graph-enrichment`

### Claims

1. **15 stages in 3 groups of 5** — ✅ verified 1:1 against
   `src/prep/services/pipeline/stages.py:13-32` (`StageId` enum):
   - Sync (1-5): STRUCTURAL, INFERRED_EDGES, CATALOGUE, VALIDATION, KNOWLEDGE
   - Enrich (6-10): ENRICHMENT, GROUP_REASONING, CLUSTERING, DEEPENING, DEEP_KNOWLEDGE
   - Finalize (11-15): ATLAS, RULES, CONCEPTS, AUDIT, ANTIBODIES
2. **Display labels DEEP_REASONING and MODULE_SYNTHESIS** with footnotes
   "Stage id `enrichment`" and "Stage id `clustering`" — ✅ design decision
   landed in prior phase: user-facing labels are friendlier than the
   internal enum names. Footnotes preserve traceability. No change.
3. **Understanding score (epistemic) + 6 weighted dimensions (20/15/20/15/15/15)** —
   not source-of-truth-verified this pass. The weights and dimensions
   should be cross-checked against `epistemic_enrichment.py` in a future
   pass. Risk: low; this is product-narrative text.
4. **Score decay table (file change → 0.0, neighbor enriched × 0.95,
   trace rebuild × 0.80, etc.)** — same status: narrative claim, not
   verified against decay implementation. Flag for future pass.
5. **Research foundation citations** (GraphRAG 2024, KARMA 2025, etc.) —
   citations are external; presence in source code is not relevant.

### Result

🟢 Desk-done. Two narrative claims (understanding-score weights, decay
multipliers) flagged for a deeper future check against
`epistemic_enrichment.py`.

## `/concepts/context`

### Claims

1. **5-step assembly pipeline (retrieve → score → budget → compress →
   format)** — narrative pipeline; aligns with the implementations across
   `core/`, `services/`, and `api/routers/context.py` at a conceptual
   level. No specific drift.
2. **"Query intent (auto-classified — 'docs', 'tests', 'code', or
   'default')"** — ⚠ **fixed 2026-05-14**. Real classifier in
   `src/prep/core/intent.py` exposes 7 intents:
   `LOCATE / EXPLAIN / RATIONALE / TRACE / EXAMPLE / COMPARE / DISCOVER`.
   The "docs/tests/code/default" classifier does not exist in code. Page
   rewritten to reference the canonical 7-intent taxonomy and link to
   `/mcp` (which already documents it correctly).
3. **BM25 keyword search alongside semantic + graph retrieval** — narrative;
   not deeply checked. The Phase 86 design doc mentions BM25 as part of
   the retrieval pipeline; if BM25 is not actually wired, mark as
   aspirational. Flag for next pass.
4. **Code compression 3–20×, no model; docs compression ~2.4×, lightweight
   language model** — partial drift: per `/guides/compression`, language
   compression is "built and available in the settings panel but requires
   additional setup" (i.e., not on by default). The "~2.4×" number lacks a
   corresponding code-side measurement. Leave the line as-is since
   `/guides/compression` already qualifies the rollout status; flag for
   review if/when language compression ships fully.
5. **Citation format `@src/file.ts:10-20`** — narrative; aligns with
   existing context router behavior.
6. **Context Assembler panel** — ✅ verified at
   `packages/ui/src/config/panelRegistry.ts:96` (`title: 'Context Assembler'`).
7. **Default retrieval params (k=20, max_chars=24,000)** — not verified
   this pass; defaults could drift over time. Flag for tier D when the
   smart-search guide is audited.

### Result

🟢 Desk-done with one substantive fix (intent taxonomy). Three narrative
items flagged for future deeper verification.

## Summary of fidelity fixes landed 2026-05-14

| Fix | Page | Why |
|---|---|---|
| Storage backend `LanceDB / Qdrant / Chroma` → `numpy arrays + JSON metadata, SQLite registry` | `/concepts/indexing` | Verified at `core/index.py:114-135` (`embeddings.npy`); no vector-DB dependencies in codebase |
| Intent classifier `docs/tests/code/default` → real 7-intent taxonomy + file-type weights | `/concepts/context` | Refined twice on 2026-05-14 (see scrutiny pass below) |

## Scrutiny pass — corrections to the Tier C audit (2026-05-14)

A reverse-engineering scrutiny round caught three places where the first
audit pass under-verified the claims. Findings logged here for honesty.

### Edge kinds — canonical list is 5, but only 2 come from parsers

`src/prep/core/trace/models.py:68` declares the canonical kinds as
`contains | imports | calls | implements | documented_by`. Reality:

| Kind | Produced by |
|---|---|
| `contains` | Python parser analyzers ✅ |
| `imports`  | Python parser analyzers ✅ |
| `calls`    | Inferred-edges LLM pipeline (default kind in `inferred_edges.py`) |
| `implements` | Inferred-edges pipeline (atlas shows 1307 `implements` edges in this repo) |
| `documented_by` | **Aspirational** — declared in the docstring but not produced by any code today |

The Rust engine (`engine/crates/prep-graph/`) treats `kind` as a string —
it consumes whatever upstream Python analyzers produce, not a new kind
producer. The atlas-aggregated kinds `configures`/`listens_to` come from
the inferred-edges LLM, not from the canonical-kind schema.

So `/concepts/code-graph`'s **"Three relationship types"** (Definitions /
References / Imports) is a defensible user-facing simplification but is
not a 1:1 mapping to edge-kind enums. It collapses parser+inferred edges
together and silently omits doc↔code links. Left as-is; not worth
rewriting for a narrative concept page, but flagged for the future
findings memo as a candidate accuracy bump.

### Intent classification — three classifiers, not one

The first Tier C audit replaced "docs/tests/code/default" with the
7-intent taxonomy. Scrutiny revealed there are actually **three distinct
classifiers** in the codebase:

| Classifier | Location | Buckets | Role |
|---|---|---|---|
| Search intent (user-facing) | `src/prep/core/intent.py` | LOCATE / EXPLAIN / RATIONALE / TRACE / EXAMPLE / COMPARE / DISCOVER | Routes `prep_search` to per-intent retrieval pipelines (Phase 86) |
| Trace-traversal intent (internal) | `src/prep/core/index.py:41-67` `_detect_intent` | debug / refactor / add_feature / understand / general | Tunes trace direction, hop count, edge-kind filter |
| File-type weighting (internal) | `src/prep/core/index.py:1104, 1110` | docs / code / tests / other | Scoring multipliers based on file type (NOT a query classifier) |

The **original docs page** was conflating the file-type weights (which are
real and do affect scoring) with intent classification. Net result: my
first fix was directionally right (the 7-intent taxonomy IS what
`prep_search` exposes) but lost the file-type-weighting reference.

**Refinement landed 2026-05-14**: the page now lists both the 7-intent
classifier AND file-type weights as separate inputs to scoring, alongside
the existing path-weights / priming / recency factors.

### Other claim verifications

| Claim | Status |
|---|---|
| 768-dimensional embeddings (`/concepts/indexing`) | ✅ verified at `core/embedder.py:474` (`DIM = 768`); also Matryoshka truncation logic |
| BLAKE3 hashing (`/concepts/indexing`) | ✅ `engine/crates/prep-walker/Cargo.toml` lists `blake3` dep |
| Storage as `embeddings.npy` + `documents.json` (`/concepts/indexing`) | ✅ `core/index.py:114-135` |
| Context Assembler panel name (`/concepts/context`) | ✅ `panelRegistry.ts:96` |
| 15-stage pipeline 1:1 (`/concepts/graph-enrichment`) | ✅ matches `stages.py` `StageId` enum exactly |
| TraceGraph storyId `dashboard-trace-graph--default` | ✅ resolves |

## Cross-session observations saved

- **1aa49e9eb3c0** anchored to `src/prep/core/intent.py` — locks down
  7-intent taxonomy as canonical; flags 4-bucket references as stale.
- **4ea487034030** anchored to `src/prep/services/embedder_factory.py` —
  documents that SourcePrep doesn't ship with LanceDB/Qdrant/Chroma.

## Items deferred to a deeper pass

- `/concepts/graph-enrichment` understanding-score weights vs
  `epistemic_enrichment.py`.
- `/concepts/graph-enrichment` score-decay multipliers vs decay
  implementation.
- `/concepts/context` BM25 wiring verification.
- `/concepts/context` default `k=20` / `max_chars=24000` vs current
  context router defaults.
- `/concepts/code-graph` edge-kind framing — keep 3-type simplification
  or expose full enumeration to power users? (product call)

## Clarity scrutiny pass — 2026-05-14

Re-read with a "is this what a USER needs to know?" lens. The two Tier C
edits I landed earlier today were technically accurate but went
in-the-weeds. Tightened both:

| Page | Before (over-detailed) | After (user-relevant) |
|---|---|---|
| `/concepts/indexing` (Storage step) | "numpy arrays plus JSON metadata, alongside a SQLite project registry" | "stored locally on your machine. Raw source code never leaves your localhost" |
| `/concepts/context` (Scoring step) | inline list of all 7 intent enum values | "the kind of question being asked (auto-classified — see the MCP reference for the full intent taxonomy)" |

### Pre-existing verbose sections flagged (NOT auto-rewritten)

These sections existed before Phase 132 and are candidate clarity rewrites
— flagging for product/copy decision rather than touching unilaterally:

- `/concepts/graph-enrichment` **"Understanding Score"** section enumerates
  6 weighted dimensions with exact percentages (20/15/20/15/15/15). User
  takeaway is "scores composite multiple signals"; the weights belong in
  internal docs.
- `/concepts/graph-enrichment` **"Score Decay"** table lists 5 decay
  multipliers (× 0.95, × 0.90, × 0.80, × 0.97). User takeaway is "scores
  degrade when things change, decayed nodes get re-analyzed"; the exact
  multipliers belong in implementation docs.
- `/concepts/graph-enrichment` **"Research Foundation"** citations (GraphRAG,
  KARMA, RepoAgent, etc.) — defensible as a credibility signal but reads
  more like a paper than a docs page.

Recommendation: rewrite the understanding-score + score-decay sections as
short paragraphs ("scores blend ~6 signals; they decay when neighbors
change") with a "details" disclosure for power users. Defer to product
decision before touching.
