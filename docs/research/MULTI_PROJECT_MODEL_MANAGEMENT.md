# Research: Multi-Project Model Management

**Status:** Research TODO — not yet implemented  
**Priority:** Low (relevant to power users / team setups)  
**Related:** Phase 31 (CLaRa replacement), Pipeline VRAM lifecycle

## Context

The current pipeline VRAM lifecycle assumes **one active project at a time**:
- Models are loaded before their stage group and unloaded after.
- No two models occupy VRAM simultaneously.
- `_maybe_unload_previous_model()` handles slot transitions (small→large).
- `_unload_group_models()` frees VRAM when a group finishes.

This breaks down when **multiple projects run concurrently** — a scenario
relevant to:
- Power users with multiple repos indexed simultaneously
- Team setups with a centralized CoDRAG server serving multiple users
- CI/CD integration where multiple projects queue builds

## Questions to Research

### 1. Concurrent Pipeline Runs
- Currently blocked: `_start_group()` rejects if any group for the same
  project is already active, but allows different projects to run.
- If Project A is in catalogue (small model) and Project B starts
  enrichment (large model), both models compete for VRAM.
- **Options:**
  - Global model lock: only one model loaded at a time, queue others
  - Per-GPU scheduling: track VRAM budget and schedule accordingly
  - Sequential project queue: finish one project's pipeline before starting another

### 2. Model Sharing Across Projects
- If two projects use the same small_model, the second project shouldn't
  trigger a reload.
- Need a reference-counting or "last-used" tracking mechanism.

### 3. Multi-GPU / Distributed Ollama
- Ollama can shard models across GPUs but doesn't support running
  different models on different GPUs simultaneously (as of 2024).
- With separate Ollama instances per GPU, we could route small_model
  to GPU 0 and large_model to GPU 1.
- This requires endpoint-level GPU affinity in the config.

### 4. Cloud Provider Concurrency
- OpenAI-compatible endpoints don't have VRAM concerns.
- The unload() call is already a no-op for cloud providers.
- Mixed setups (Ollama small + cloud large) need no special handling.

### 5. VRAM Budget Estimation
- Could query Ollama for model size and available VRAM before loading.
- Ollama API: `GET /api/show` returns model metadata including size.
- Compare against `GET /api/ps` (running models) for available capacity.

## Proposed Architecture (Future)

```
ModelScheduler
├── tracks: which models are loaded, by which project, on which endpoint
├── load(slot, project_id) → waits if VRAM is full, queues if needed
├── unload(slot, project_id) → ref-counted, only unloads when no project needs it
├── budget_check(model_name) → can this model fit in available VRAM?
└── per-endpoint locks → prevents two loads on same Ollama instance
```

## Implementation Notes

- The current `LLMClient.unload()` + `STAGE_MODEL_SLOT` mapping is
  sufficient for single-project use.
- Multi-project support should be a separate phase with its own
  design doc and testing plan.
- Consider adding a `--single-project` mode flag that enforces the
  current behavior and rejects concurrent pipeline runs across projects.

---

# Issues List

> **Note on attribution:** Issues prefixed `[AI-1]` are owned by the AI that
> originally drafted this doc. Issues prefixed `[AI-2]` are added in parallel
> while AI-1 is still working — do not edit AI-1 entries from AI-2 sessions
> and vice versa. Resolve overlap when both AIs sync.

## Graph Scope: Numbers Reconciliation (AI-2)

**Owner:** AI-2 (**FIXED** 2026-04-11)
**Reproduction project:** CoDRAG itself (`.codrag/` on `4TB-BAD`)
**Reported state:** Graph Scope panel shows `7017/21531 nodes enriched & embedded (33%)`
while `1485/2206 files traced (67.3%)`. The 33% number is wrong by construction
and the 7017 numerator is contaminated. Three independent bugs are stacked.

### GS-1 [AI-2]: Deep enrichment denominator mixes node kinds (UI + API)

**What's wrong**

The Deep Enrichment progress bar divides `enriched_nodes` (file-scoped only)
by `total_nodes` (all kinds, including markdown sections, symbols, and external
modules that epistemic enrichment never touches). The ratio is structurally
meaningless.

**Evidence (from `.codrag/` on this repo, 2026-04-11)**

`trace_nodes.jsonl` has 21531 entries, broken down by `kind`:

| kind             | count  |
|------------------|-------:|
| section          | 15289  |
| symbol           |  4544  |
| file             |  1481  |
| external_module  |   217  |
| **total**        | 21531  |

`trace_epistemic.jsonl` contains **only** `file:`-prefixed `node_id`s
(7022 lines, all `file:` kind). Sections, symbols, and external modules are
never written to it. So the displayed ratio compares a file-only numerator to
an all-kinds denominator.

**Source of the bug**

- API: `src/codrag/api/routers/trace_routes/enrichment.py:314`
  unconditionally returns `total_nodes = _fast_count("trace_nodes.jsonl")`
  alongside `total_file_nodes`. Both are returned to the client.
- UI: `packages/ui/src/components/trace/GraphStructurePanel.tsx:211`
  uses `total = epistemic.total_nodes || augmentation?.total_nodes || epistemic.total_file_nodes || epistemic.enriched_nodes`.
  The fallback chain prefers the wrong value first. `total_file_nodes` exists
  in the response but is only used as a third-tier fallback.
- The original commentary on line 209-210 even acknowledges this:
  `// Use total_nodes (all kinds) since enrichment processes all node types`
  — that comment is **factually wrong** for epistemic enrichment, which is
  per-file only.

**Suggested fix direction (do not implement until GS-2/GS-3 are also designed)**

- Either: change `DeepCoverageBar` to prefer `total_file_nodes` over `total_nodes`.
- Or: split the bar into two — one for "files enriched" (epistemic),
  one for "symbols augmented" (augmentation pass), each with its own correct
  denominator. The augmentation pipeline does process `sym:` nodes, so its
  bar should compare against `kind=symbol` count.

### GS-2 [AI-2]: `trace_epistemic.jsonl` is append-only and full of orphans

**What's wrong**

When a file is excluded from the trace graph (via Exclude Tree, Patterns tab,
or scope change), its old enrichment row stays in `trace_epistemic.jsonl`
forever. There is no garbage collection step that prunes entries whose
`node_id` no longer corresponds to a node in `trace_nodes.jsonl`.

**Evidence**

```
file nodes in trace_nodes.jsonl:               1481
unique node_ids in trace_epistemic.jsonl:      7022
overlap (legit current enrichments):           1395
orphan enrichments (no matching trace node):   5627  ← 80% of file is junk
```

Sample orphan node_ids:
- `file:tests/eval/real_repos/alamofire-swift/docs/docsets/...`
- `file:tests/eval/real_repos/gson-java/test-shrinker/.../ClassWithUnreferencedNoArgsConstructor.java`
- `file:tests/eval/real_repos/alamofire-swift/docs/Classes/URLEncodedFormParameterEncoder/Destination.html`

These are all paths from the `tests/eval/real_repos/` corpora that were
indexed at some point and then excluded. Their enrichment rows were never
removed.

**Real coverage, after pruning orphans:**
`1395 enriched / 1481 file nodes ≈ 94.2%` — *not* 33%.

### GS-3 [AI-2]: Same orphan accumulation in `trace_augmented.jsonl` and `knowledge_documents.json`

GS-2 is not isolated to the epistemic file. The same scope-change-without-GC
pattern has contaminated every derived artifact:

| File                          | Unique node_ids / paths | Live (in current graph) | Orphans       |
|-------------------------------|-----------------------:|------------------------:|--------------:|
| `trace_epistemic.jsonl`       | 7022                   | 1395                    | 5627  (80%)   |
| `trace_augmented.jsonl`       | 55743                  | ~3300 est.              | ~52400 (~94%) |
| `knowledge_documents.json`    | 7295                   | 1481                    | 5814  (80%)   |

`trace_augmented.jsonl` is the worst offender:
- 7177 unique `file:` prefixes (vs 1481 actual file nodes)
- 48566 unique `sym:` prefixes (vs 4544 actual symbol nodes)

These orphans inflate every derived metric, waste disk space (the augmented
file is 26 MB on this repo, the knowledge embeddings npy is 192 MB), and
silently confuse anything that joins on `node_id` between artifacts.

**Suggested fix direction**

Add a `prune_orphan_enrichments` step that runs:
1. After scope changes (`/trace/ignore` already invalidates the coverage cache
   at `enrichment.py:257-258` — extend it to also prune the derived artifacts).
2. At the start of each pipeline build, before counting "already enriched".
3. As a one-shot CLI: `codrag prune --orphans` for users with already-corrupted
   indexes (like this repo right now).

Pruning is safe: the data was generated for files that no longer exist in
the graph, so by definition nothing should reference it.

### GS-4 [AI-2]: Manifest `processed` counter is monotonic and disagrees with disk

**What's wrong**

`enrichment.py:335` reads `quality.processed` from `trace_epistemic_manifest.json`
as the canonical "enriched_nodes" count. That value is 7017, but the actual
disk file has 7022 lines. The manifest counter does not get reset on prune
or scope change either, and is not derived from a `wc -l`. It's a running
total of "how many enrichment calls have we ever made", not a current state.

**Evidence**

```
trace_epistemic.jsonl:                 7022 lines
manifest quality.processed:            7017 (returned by API, displayed in UI)
```

The 5-row delta between the two is a separate symptom — most likely from
the multi-pass enrichment writing duplicate `node_id`s for the same file
across passes, where the manifest counts unique pass completions and the
disk file appends every row.

**Suggested fix direction**

The API should derive `enriched_nodes` from the *current* set of unique
`node_id`s in `trace_epistemic.jsonl` that *also exist* in the current
`trace_nodes.jsonl`. The manifest's `processed` field is fine for telemetry
but should not be the source of truth for the UI bar.

### Cross-reference

These four bugs combine to produce the displayed `7017/21531 (33%)`:
- GS-1 makes the denominator 14× too large.
- GS-2 makes the numerator 5× too large in absolute terms (and structurally
  meaningless because the orphan rows have nothing to compare against).
- GS-4 picks a stale counter for the numerator instead of measuring current state.
- GS-3 means even fixing the bar still leaves 26 MB + 192 MB of dead data
  on disk and contaminates other downstream features.

The **real, currently-correct** number for the bar should be approximately
`1395 / 1481 ≈ 94%` once orphans are pruned. The structural fix is to make
the API return a self-consistent `(enriched, total)` pair derived from the
current node set, not from append-only logs.


## Graph Scope: System-Excluded Files Visibility (AI-2)

**Owner:** AI-2 (research complete, implementation future)

### GS-5 [AI-2]: Always-excluded AI instruction files are invisible in the Exclude Tree

**Context**

CoDRAG unconditionally excludes AI agent instruction files from tracing
because they are already available to the AI via direct injection (CLAUDE.md
is loaded into the system prompt, AGENTS.md is auto-generated by CoDRAG,
etc.). Tracing them wastes LLM tokens on meta-content. This is correct
behavior — the issue is that users can't see this is happening.

**Where the canonical list lives**

`src/codrag/core/repo_profile.py` defines two related constants:

1. **`DEFAULT_EXCLUDE_FILE_NAMES`** (lines 52-63) — simple filename set:
   `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.cursorrules`, `.cursorignore`,
   `.windsurfrules`, `.clinerules`, `.roorules`, `.clineignore`, `.qwencoderules`

2. **`DEFAULT_EXCLUDE_FILE_GLOBS`** (lines 66-86) — glob patterns actually
   enforced by the trace system:
   - `**/AGENTS.md` — CoDRAG-generated
   - `**/CLAUDE.md` — Claude Code
   - `**/.cursor/rules/*.mdc` — Cursor rules
   - `**/.cursorrules` — Cursor (legacy)
   - `**/.windsurfrules` — Windsurf
   - `**/.windsurf/rules/*.md` — Windsurf rules
   - `**/.github/copilot-instructions.md` — GitHub Copilot
   - `**/GEMINI.md` — Gemini CLI
   - `**/.clinerules` — Cline
   - `**/.roorules` — Roo
   - `**/.qwencoderules` — Qwen Code

**Where they're enforced (three call sites)**

| File | Line | How |
|------|------|-----|
| `src/codrag/core/trace/builder.py` | 100 | `TraceBuilder.__init__` extends `exclude_globs` |
| `src/codrag/core/trace/coverage.py` | 93-99 | Coverage always appends them (Phase 89 comment) |
| `src/codrag/core/index.py` | 286 | Index building extends `exclude_globs` |

All three unconditionally append these globs — user config cannot override them.

**The UX issue**

The Exclude Tree tab in Graph Scope shows user-controllable excludes but gives
no indication that these system files are always excluded. If a user sees
`AGENTS.md` in their repo and wonders why it's not traced, there's no
explanation in the UI. Conversely, if a user tries to include `CLAUDE.md`
via the Exclude Tree toggle, it silently has no effect because the system
exclude overrides user intent.

**Proposed future UX**

Show system-excluded files in the Exclude Tree as **disabled rows** with a
lock icon and a tooltip explaining "Always excluded — AI instruction files
are already available via direct injection." The rows should:
- Be visually distinct (greyed out, lock icon, no toggle)
- Not be toggleable (the system exclusion is not overridable)
- Have a tooltip or info popover explaining why
- Optionally be collapsible under a "System Excludes" group header
- Source their list from `DEFAULT_EXCLUDE_FILE_GLOBS` via the API (not
  hardcoded in the frontend)

**Maintenance note**

The `DEFAULT_EXCLUDE_FILE_GLOBS` list will need updating as new AI coding
agents emerge. Current coverage: Claude Code, Cursor, Windsurf, Copilot,
Gemini CLI, Cline, Roo, Qwen Code. Missing from the list as of 2026-04-11:
- `CODEX.md` — OpenAI Codex CLI (if it adopts a rules file convention)
- `**/.aider*` — Aider config files
- `**/.continue/**` — Continue.dev config
- Any future convention from Amazon Q, Sourcegraph Cody, etc.


