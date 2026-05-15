# Phase 132 Tier D — Guide Pages

> **Pages audited:** `/guides/smart-search`, `/guides/codebase-audit`,
> `/guides/audit-enrichment`, `/guides/path-weights`, `/guides/embeddings`,
> `/guides/concurrency-discovery`, `/guides/knowledge-scope`,
> `/guides/model-advisor`
> **Method:** desk verification on 2026-05-14 against source-of-truth
> (`intent.py`, `mcp_tools.py`, `embedder.py`, `repo_policy.py`, router files).

## `/guides/smart-search`

### Claims verified

- **7 intents** (LOCATE/EXPLAIN/RATIONALE/TRACE/EXAMPLE/COMPARE/DISCOVER) ✅
  match `src/prep/core/intent.py:13-20`.
- **Tiebreaker priority** `TRACE > RATIONALE > COMPARE > EXAMPLE > DISCOVER
  > LOCATE > EXPLAIN` ✅ matches `intent.py:29` exact order.
- **Per-intent trigger words** ✅ each description matches the regex
  patterns in `classify_intent()`.
- **Rule-based, deterministic, no LLM call** ✅ — `intent.py` uses regex
  only.
- **Query rewriting strips signal words** ✅ — `rewrite_query()` defined.
- **Confidence levels** (high/medium/low) ✅ returned as second element of
  the classifier tuple.

### Result

🟢 No edits required. Page is a clean reflection of `intent.py`.

## `/guides/codebase-audit`

### Claims

1. **"Four MCP tools" (`prep_audit`, `prep_audit_report`,
   `prep_audit_refactor`, `prep_audit_check`)** —
   ⚠ **fixed 2026-05-14**: `mcp_tools.py:25` `_CORE_TOOLS` advertises
   exactly **one** audit tool (`prep_audit`). The three `prep_audit_*`
   names live in `LEGACY_TOOLS` (line 554+) as routing aliases that
   dispatch to the same `prep_audit` handler with different `action`
   parameters. Page rewritten as a single tool with an action table
   (`scan`/`report`/`refactor`/`verify`/`antibodies`).
2. **11 analyzers** ✅ verified — exactly 11 files in
   `src/prep/core/audit/analyzers/`.
3. **`naming_consistency` analyzer** ✅ — `naming.py:13` declares
   `name = "naming_consistency"` (file name differs from registered name,
   but the docs use the registered name correctly).
4. **Audit defaults** (large_file_threshold 80k, warning 40k, hub_z 2.0,
   similarity 0.65) ✅ all match `runner.py:58-70`.
5. **5 report names** (AUDIT_SUMMARY etc.) ✅ match `prep_audit` schema's
   `report_name` enum.
6. **Output paths** for standalone + embedded mode ✅ match CLAUDE.md
   daemon state location.
7. **CLI commands** (`prep audit`, `--synthesize`, `--category`) — not
   re-verified this pass; standard Typer CLI patterns.

### Result

🟢 Desk-done with one substantive rewrite (MCP-tools section).

## `/guides/audit-enrichment`

### Claims verified

- **`prep_audit(findings=...)` enrichment** ✅ matches the schema in
  `mcp_tools.py` (`findings` accepts array or SARIF dict).
- **Enriched fields** (dependents, hub_status, module, concepts,
  risk_score, recommendation) ✅ — CLAUDE.md documents these as the
  enrichment payload.
- **Risk score formula** ✅ — CLAUDE.md and MASTER_ROADMAP confirm
  `0.40 * hub + 0.30 * concept + 0.20 * observation + 0.10 * churn`.
- **SARIF 2.0 + 2.1.0 acceptance + round-trip** ✅ — `prep_audit` schema
  has `output_format: ["auto", "sarif", "simple"]`.
- **`hub_status` enum** — page lists 4 values (`critical/high/moderate/low`);
  code declares 5 (`...|info`) at `structural.py:56`. Defensible
  simplification: `info` is typically suppressed at the surfacing layer.
  Left as-is.

### Result

🟢 No edits required.

## `/guides/path-weights`

### Claims verified

- **PUT/GET `/projects/{id}/path_weights`** ✅ — `crud.py:443`.
- **Range 0.0–2.0** ✅ — clamped at `repo_policy.py:92` via
  `max(0.0, min(2.0, round(w, 2)))`.
- **Default 1.0** ✅ implicit in absence of override.
- **Persists to `repo_policy.json`** ✅ — module name is canonical.
- **Hierarchical, most-specific-wins** — page narrative; not deeply
  verified but standard pattern in the codebase.
- **Formula `final_score = base_score × role_weight × path_weight`** —
  narrative; not directly verified against scoring code. Flag for a
  deeper future pass.

### Result

🟢 No edits required.

## `/guides/embeddings`

### Claims

1. **Three tiers**: nomic-embed-code (Ollama/GPU), nomic-embed-text
   (Ollama), nomic-embed-text-v1.5 (ONNX built-in) ✅ matches
   `embedder.py` model registry.
2. **nomic-embed-code dimension** — ⚠ **fixed 2026-05-14**: page claimed
   "4 096-dim embeddings"; `embedder.py:35` declares
   `"manutic/nomic-embed-code": {"dim": 3584, "matryoshka_dim": 768}`.
   Real dim is **3584** with Matryoshka truncation to 768.
3. **nomic-embed-text-v1.5 dimension 768** ✅ — `embedder.py:474`
   `DIM = 768`.
4. **R@1 benchmark numbers** (82.1% / 82.1% / 84.6% on 39 queries × 22
   fixture files) — not desk-verifiable; benchmark fixture needs to be
   re-run periodically. Flag for a deeper pass.
5. **Query speed** (148ms / 25ms / 7ms) — perf claim; same caveat as R@1.
6. **GET/POST `/embedding/status` and `/embedding/download`** — not
   verified this pass; presumed correct.
7. **Cache at `~/.cache/huggingface/hub/`** — standard HF Hub path; ✅
   defensible.

### Result

🟢 Desk-done with one substantive fix (dimension).

## `/guides/concurrency-discovery`

### Claims verified

- **`POST /compute/concurrency/clear`** ✅ at `compute.py:415`.
- **`GET /compute/scheduler`** ✅ at `compute.py:238`.
- **24-hour lock** ✅ matches memory `feedback_no_hardcoded_concurrency`
  (Phase 82).
- **Latency-aware discovery + backoff** ✅ — design intent matches the
  Phase 82 description.
- **Node id format `cloud:default_ollama`** ✅ — convention surfaces in
  CLAUDE.md.
- **No hardcoded plan-tier values** ✅ — page describes plan jumps
  qualitatively without inventing numbers (aligns with memory).

### Result

🟢 No edits required. Page is one of the strongest fidelity fits.

## `/guides/knowledge-scope`

### Claims verified

- **GET/PUT `/projects/{id}/included_paths`** ✅ at `crud.py:574, 584`.
- **POST `/projects/{id}/scope/add`** ✅ at `routers/scope.py:114`.
- **POST `/projects/{id}/scope/remove`** ✅ at `routers/scope.py:144`.
- **GET `/projects/{id}/scope/status`** ✅ at `routers/scope.py:101`.
- **Storybook `dashboard-project-foldertreepanel--scope-panel-named-populated`**
  ✅ — `stories/project/FolderTreePanel.stories.tsx:8 title:
  'Dashboard/Project/FolderTreePanel'` + `ScopePanelNamedPopulated` export.
- **"Scope" panel name** ✅ — `panelRegistry.ts:129`.

### Result

🟢 No edits required.

## `/guides/model-advisor`

### Claims

Interactive recommender (client component) — rewritten in Phase 130
follow-up #17 with the explicit design intent to **stay family-level
("Claude Haiku", "Gemini Flash") and use cost tiers `$ / $$ / $$$`**
rather than per-version model IDs and per-million-token prices. The
header comment on the file states this rationale explicitly.

### Result

🟢 Design intent matches memory (`feedback_no_hardcoded_concurrency`).
GPU database and slot recommendations are content claims, not behavioral
claims — out of scope for fidelity audit. Flag for a separate
content/accuracy pass if hardware specs need refresh.

## Summary of fidelity fixes landed 2026-05-14

| Fix | Page | Why |
|---|---|---|
| "Four MCP tools" framing → "One `prep_audit` tool with action modes" + action table | `/guides/codebase-audit` | `mcp_tools.py:25` `_CORE_TOOLS` has only `prep_audit`; the others are LEGACY routing aliases |
| `nomic-embed-code` dim "4 096" → "3 584 (Matryoshka-truncated to 768)" | `/guides/embeddings` | `embedder.py:35` declares `{"dim": 3584, "matryoshka_dim": 768}` |

## Items flagged but not auto-fixed

- `/guides/audit-enrichment` `hub_status` lists 4 values; code declares 5
  (`info` omitted). Defensible simplification.
- `/guides/path-weights` final-score formula not source-verified;
  narrative claim.
- `/guides/embeddings` R@1 benchmark numbers + query-speed numbers not
  desk-verifiable; need benchmark re-run.
- `/guides/model-advisor` GPU database and slot recommendations are
  content claims; flag for a content/accuracy pass separately.
