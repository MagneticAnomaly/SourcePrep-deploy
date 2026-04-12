# 06 — Diagnostic Report: Why Phases 83-88 Show Partial Results on Haley

**Date:** 2026-04-08
**Context:** Phases 83-88 are fully implemented and deployed. The daemon is freshly restarted. All changes are retrieval-layer (MCP server, new audit analyzers, schema extensions). No pipeline rebuild is needed. Yet testing against the Haley/LinuxBrain project shows some features working perfectly and others returning empty results. This doc traces each issue to its root cause.

---
ok 
## What's Working vs What's Not

| Feature | Phase | Result on Haley | Verdict |
|---------|-------|----------------|---------|
| Impact direction=all → markdown, stdlib filtered | 83 | Clean markdown, 11 internal files, no stdlib | **Working** |
| Impact direction=dependents → markdown | 83 | Clean markdown, 30 dependents listed | **Working** |
| Audit scan → structural findings (coupling, cycles) | 83 | `## Structural Audit (0 findings)` | **Not working** |
| Audit scan → concept conflict findings | 83/84 | No findings (concepts store is empty) | **Expected** — no concepts saved |
| Audit enrichment (external findings) | 83/85 | Not tested yet | — |
| SARIF enrichment | 85 | Not tested yet | — |
| Symbol search → qualified name, signature, docstring | 83 | Bare `name @ path` — no enrichment | **Not working** |
| Concepts → assertion field, doc_links, supersede | 84 | Schema changes are in code | **Not testable** — no concepts to test |
| Concepts → observation promotion | 84 | Not tested yet | — |
| Concepts → conflict detection | 84 | In code, wired to audit | **Not testable** — no concepts |
| Intent classification for search | 86 | "where is PersonaMemoryStore" went through semantic search, not symbol lookup | **Not working or not wired** |
| Codebase immune system | 87 | Not tested — requires concepts with assertions | **Not testable** |
| Agent generator | 88 | Not tested | — |

**Summary: 2 features work, 2 don't work, 4 can't be tested (no data), 4 not tested.**

---

## ISSUE 1: Structural Audit Returns 0 Findings

### Symptom
`codrag_audit(action="scan")` returns `## Structural Audit (0 findings)` on a project with 57 known circular deps and `app.py` as a 235-edge hub.

### The Code Path
1. Dispatch at `server.py:3701` → `tool_audit_structural()`
2. `tool_audit_structural()` at `server.py:1902-1983` builds a `ctx` dict with:
   - `hub_files` from `GET /projects/{id}/trace/hub-files?k=50`
   - `cycles` from `GET /projects/{id}/audit/findings?limit=500`, filtered to `analyzer == "circular_deps"`
   - `modules` from `GET /projects/{id}/trace/modules`
   - `concepts` from `concept_store.list_concepts()`
   - `observations` from `observation_store.get_recent()`
3. Passes `ctx` to `run_structural_audit()` in `structural.py`
4. `run_structural_audit()` calls `_detect_coupling_hotspots(hub_files, ...)` and `_detect_import_cycles(cycles, ...)`

### Probable Root Causes

#### Root Cause A: Hub files API returns `path` but handler reads `file_path`

**THIS IS LIKELY A BUG.**

The API endpoint at `trace_routes/query.py:624` returns:
```python
{"hub_files": [{"path": p, "in_degree": d} for p, d in hubs]}
```

But the MCP handler at `server.py:1921` reads:
```python
fp = hf.get("file_path", "")   # ← reads "file_path"
deg = hf.get("in_degree", 0)
```

The API returns `"path"`, the handler reads `"file_path"`. **The field name doesn't match.** Every hub file gets `fp = ""` (the default), and the empty-string entries either fail the `if fp:` check at line 1923 or produce meaningless entries. The `hub_files` list passed to `run_structural_audit()` would be empty.

With an empty `hub_files` list, `_detect_coupling_hotspots()` at `structural.py:121` checks `if len(filtered) < 2: return []` — which it does, because the list is empty. **Zero coupling hotspot findings.**

**To verify:** Add a log line or check: does `GET /projects/{project_id}/trace/hub-files?k=50` return `"path"` or `"file_path"` keys? If the former, the handler needs to read `hf.get("path", "")` instead of `hf.get("file_path", "")`.

**Alternatively**, the endpoint URL might be wrong. The handler calls `/trace/hub-files` (with a hyphen) but the route is registered as `/trace/hub_files` (with an underscore) at `query.py:596`. FastAPI may or may not normalize hyphens to underscores — this depends on the router configuration. If the URL doesn't match, the request silently fails and `hub_data` is empty.

#### Root Cause B: Cycles come from legacy audit findings, not the trace graph

The MCP handler at `server.py:1928-1944` fetches cycles from:
```python
GET /projects/{project_id}/audit/findings?limit=500
```
Then filters for `f.get("analyzer") == "circular_deps"`.

This reads from the **legacy audit system** (the old `BaseAnalyzer` pipeline that runs during `POST /projects/{id}/audit`). The legacy audit must have been triggered for findings to exist. On Haley, the legacy audit may never have been run — meaning the findings endpoint returns an empty list, and cycles is `[]`.

Meanwhile, the 57 circular deps shown in the atlas came from the **atlas structural analysis** which is a different code path (`atlas/generator.py` graph traversal, stored in `atlas.json`). The structural audit in Phase 83 doesn't read from the atlas — it reads from the legacy audit findings.

**Two different data sources for the same information. The structural audit reads the empty one.**

**To verify:** Call `GET /projects/{project_id}/audit/findings?limit=500` for Haley's project ID directly and check if any findings exist.

**To fix (if confirmed):** The structural audit should either:
1. Query the trace graph directly for cycles (like the atlas does), rather than reading from legacy audit findings
2. Or: fall back to atlas cycle data when legacy findings are empty
3. Or: run a lightweight cycle detection on the trace graph as part of `run_structural_audit()` itself

#### Root Cause C: Exception swallowing hides the real error

Every data-gathering step in `tool_audit_structural()` is wrapped in `try/except Exception` with `logger.debug()`. If any API call fails (wrong URL, 404, connection error), the exception is silently caught and the empty list is used. This means:
- If `/trace/hub-files` returns a 404 (because the URL should be `/trace/hub_files`), `hub_files = []`
- If `/audit/findings` returns a 404 or empty because the legacy audit was never run, `cycles = []`
- No error is surfaced to the caller — the structural audit just sees empty inputs and returns 0 findings

**To fix:** At minimum, log at `warning` level when these critical data sources return empty. Add a note in the response: "Warning: no hub file data available. Structural analysis may be incomplete."

### Research Tasks for Issue 1
- [ ] Verify the API field name: does `/trace/hub_files` return `"path"` or `"file_path"`?
- [ ] Verify the API URL: is it `/trace/hub-files` or `/trace/hub_files`? Does FastAPI normalize the hyphen?
- [ ] Check whether Haley has legacy audit findings at all: `GET /projects/{project_id}/audit/findings`
- [ ] Check whether the atlas cycle data (from `atlas.json`) is accessible via a different API
- [ ] Consider having `run_structural_audit` detect cycles directly from the trace graph instead of relying on legacy findings

---

## ISSUE 2: Symbol Search Returns No Signatures/Docstrings

### Symptom
`codrag_search(query="_score_memory_with_relevance", type="symbol")` returns:
```
- `_score_memory_with_relevance` (symbol) @ `halley_core/memory_v2/store.py`
- `_score_memory_with_relevance` (symbol) @ `installers/obfuscated/halley_core/memory_v2/store.py`
```
No signature, no docstring, no qualified name, no line number.

### The Code Path
1. `server.py:3578` dispatches to `tool_trace_search()`
2. `tool_trace_search()` at line 1337-1344 extracts fields from each node:
```python
"qualified_name": n.get("qualified_name", n.get("name", "")),
"signature": n.get("signature", ""),
"docstring": (n.get("docstring", "") or "")[:200],
```
3. The markdown formatter at line 1355-1358 renders:
```python
if n.get("signature"):
    line += f"\n    `{n['signature']}`"
if n.get("docstring"):
    line += f"\n    {n['docstring']}"
```

### Probable Root Cause: Trace nodes don't have these fields

The formatter reads `signature`, `docstring`, `qualified_name` from the trace node data returned by the API. These fields would need to be populated during indexing — specifically during the Rust parser stage (tree-sitter AST extraction) or the Python enrichment stage.

**Key question: Does the Rust parser (`codrag-parser`) extract function signatures and docstrings into trace node metadata?**

If the parser stores them under different field names (e.g., `doc` instead of `docstring`, `params` instead of `signature`, `qualname` instead of `qualified_name`), the formatter would read empty strings.

If the parser doesn't extract them at all, the data simply isn't in the trace graph. This would be a **pipeline-layer gap** — the fields need to be added to the parser output. No retrieval-layer change can fix it; you'd need a pipeline rebuild with an updated parser.

**The enrichment stage** (kimi-k2.5:cloud deepening) generates `summary` and `role` annotations per file/symbol — we can see these in search results. But enrichment may not produce structured `signature`/`docstring` fields. The file-level enrichment summaries ("Initializes a PersonaMemoryStore instance...") are LLM-generated descriptions, not extracted code signatures.

### Research Tasks for Issue 2
- [ ] Examine a trace node for `_score_memory_with_relevance` directly: what fields does it have? Use `GET /projects/{project_id}/trace/search?q=_score_memory_with_relevance` and inspect the raw response
- [ ] Check the Rust parser output: does `codrag-parser` extract `docstring`, `signature`, `qualified_name`? Look in `engine/crates/codrag-parser/src/`
- [ ] Check if the Python-side trace node model (`core/trace/models.py`) stores these fields
- [ ] If the parser doesn't extract them: this IS a pipeline gap. The Phase 83 retrieval fix added the formatter but the data source doesn't exist yet
- [ ] If the parser extracts them under different names: fix the field mapping in `tool_trace_search`

---

## ISSUE 3: Intent Classification Not Routing "where is X" to Symbol Search

### Symptom
`codrag_search(query="where is PersonaMemoryStore")` returned semantic search results (PersonaMemoryStore.__init__, location_state_machine.py, persona_routes.py) instead of a clean symbol lookup.

### The Code Path
Search dispatch at `server.py:3576-3596`:
```python
search_type = args.get("type", "context")
if search_type == "symbol":
    result = await self.tool_trace_search(...)
else:
    result = await self.tool_search(...)
```

The routing is based on the `type` parameter, which defaults to `"context"`. My call didn't pass `type="symbol"`, so it went through semantic search.

### Root Cause: Phase 86 intent classification may not be wired into dispatch

Phase 86 (Intent Classification) was designed to add a classifier that automatically detects intent from the query text. But the dispatch at line 3577 still only checks `args.get("type", "context")` — there's no call to an intent classifier.

**Research needed:** Is the Phase 86 intent classifier actually wired into the search dispatch? Or was it designed but not yet integrated into the call chain? Look for:
- An `intent` parameter in the MCP schema for `codrag_search`
- A `classify_intent()` call anywhere in the search dispatch path
- Any code in `src/codrag/core/query_analyzer.py` that does intent classification vs just structural signal extraction

The existing `QueryAnalyzer.extract_signals()` (from the earlier Phase 73 work) extracts file names and symbols from queries, but that's for boosting within semantic search, not for routing to a different search mode entirely. Intent classification (LOCATE → symbol search, RATIONALE → concept search, etc.) is a different feature.

### Research Tasks for Issue 3
- [ ] Check if Phase 86 intent classification is wired into `handle_call_tool` dispatch or `tool_search`
- [ ] Check if `src/codrag/core/query_analyzer.py` has an `classify_intent()` function or if it only has `extract_signals()`
- [ ] Check if the `codrag_search` MCP schema has an `intent` parameter
- [ ] If not wired: this is an integration gap — the classifier exists in code but isn't called

---

## ISSUE 4: Impact Dependents for app.py Returns Only Doc References

### Symptom
`codrag_impact(file_path="halley_core/api/app.py", direction="dependents")` returns 30 direct dependents, ALL `.md` files with `[references]` edge type, ZERO code imports. But the atlas identifies `app.py` as a 235-edge hub and `direction=all` found 10 internal code files that import from `app.py`.

### Analysis
The `direction=all` call routes to `tool_trace_neighbors()` which returns both directions (files app.py imports AND files that import app.py). The `direction=dependents` call routes to `tool_impact()` which calls a different API endpoint.

`tool_impact()` at `server.py:1438-1511` calls:
```
GET /projects/{project_id}/trace/impact/{file_path}
```

This endpoint may have a different edge resolution strategy than `tool_trace_neighbors`. It may only return `references` edges (doc mentions) rather than `imports` edges (code dependencies). Or the edge direction may be inverted — the endpoint may be returning files that `app.py` references (outgoing references TO docs) rather than files that reference `app.py` (incoming edges FROM importers).

**However:** The 30 results ALL have the same file as the target (they're all docs in `Docs_Halley/`), and they all have `[references]` edge type. These docs reference `app.py` by name in their text — this is correct (they do mention app.py). But the code files that `import from halley_core.api.app` are missing.

**Possible causes:**
1. The impact API endpoint only returns `references` type edges and not `imports` type edges for some projects
2. The trace graph for Haley doesn't have reverse import edges (file A imports from file B → edge from A to B, but no reverse edge from B to A for "dependents" queries)
3. The impact endpoint uses a different graph traversal than the neighbors endpoint, and the traversal doesn't follow import edges in the reverse direction

### Research Tasks for Issue 4
- [ ] Call `GET /projects/{project_id}/trace/impact/halley_core/api/app.py` directly and inspect the raw response — what edge types are returned?
- [ ] Compare with `GET /projects/{project_id}/trace/neighbors?node_id=file:halley_core/api/app.py&direction=incoming` — does this show code importers?
- [ ] Check if the trace graph stores reverse import edges, or if the neighbors endpoint computes them on-the-fly from the forward edge set
- [ ] The 10 internal files from the `direction=all` test (metrics.py, residency_policy.py, etc.) — these are files that `app.py` imports FROM. They showed up in `direction=all` because they're in app.py's dependency neighborhood. But they may not be in app.py's "dependents" because they're dependencies, not dependents. In other words: `direction=all` showed app.py's *dependencies*, not its *dependents*. The actual dependents (files that import FROM app.py) may genuinely be only docs + the obfuscated mirror.

**This might not be a bug.** If `app.py` is a Flask application entry point, other code files may not import from it — they get imported BY it. The 235-edge count from the atlas may be counting outgoing edges (app.py imports 235 things), not incoming edges (235 things import app.py). In that case, the dependents query correctly returns only doc references because only docs reference app.py — code files don't import from the entry point.

**To verify:** Check whether the 235-edge count in the atlas is for in-degree (incoming = dependents) or out-degree (outgoing = dependencies). The atlas said "halley_core/api/app.py (235 edges)" without specifying direction.

---

## ISSUE 5: Concepts, Immune System, and Agent Generator Not Testable

### Root Cause
The Haley project has no concepts saved. Phase 84 (Concepts Formalization), Phase 87 (Immune System), and Phase 88 (Agent Generator) all depend on concepts being populated.

- **Phase 84** added `assertion`, `doc_links`, `superseded_by` fields to concepts. Can't test without concepts.
- **Phase 87** generates antibodies from concepts with assertions. Can't test without concepts.
- **Phase 88** generates agent teams from structural knowledge + audit findings. Partially testable (audit findings are missing due to Issue 1).

### Research Tasks for Issue 5
- [ ] Manually save 2-3 test concepts for Haley to verify Phase 84 fields work
- [ ] Save a concept with an assertion to verify Phase 87 antibody generation
- [ ] Re-run the audit after fixing Issue 1 to verify Phase 88 can read structural findings

---

## Cross-Cutting Concern: Silent Failure Pattern

The most systemic issue across all of these is **silent failure with empty defaults**. Every data-gathering step in `tool_audit_structural()` swallows exceptions and falls back to empty lists. The structural audit runs with empty inputs and returns 0 findings. The symbol formatter reads empty fields and renders bare paths. No errors, no warnings, no indication that the results are incomplete.

This pattern makes debugging extremely difficult. The tool appears to work — it returns a valid response with correct formatting. But the response has no content because the underlying data was silently unavailable.

### Recommended Fix: Add Data Availability Indicators

Every tool response should include a data availability section when inputs are empty:

```markdown
## Structural Audit (0 findings)

⚠ Data availability:
- Hub files: 0 loaded (expected >0 for a project with traced files)
- Import cycles: 0 loaded (legacy audit may not have been run)
- Concepts: 0 loaded
- Observations: 5 loaded

Run `POST /projects/{id}/audit` to generate legacy findings, 
or investigate why hub file data is unavailable.
```

This turns a mysterious "0 findings" into an actionable diagnostic.

---

## Summary: Research Priority Order

| # | Issue | Most Likely Cause | Effort to Verify | Effort to Fix |
|---|-------|-------------------|-----------------|--------------|
| 1 | Audit 0 findings | **`"path"` vs `"file_path"` field mismatch** + cycles read from empty legacy store | 5 min (check API response) | 5 min (fix field name) |
| 2 | Symbol search bare paths | Trace nodes don't have `signature`/`docstring` fields (parser doesn't extract them) | 10 min (inspect trace node) | Hours if parser needs updating (pipeline change) |
| 3 | Intent classification not routing | Phase 86 classifier may not be wired into dispatch | 5 min (grep for classify_intent) | 30 min (wire into dispatch) |
| 4 | Impact dependents only shows docs | May be correct behavior (app.py is an entry point, nothing imports it) | 10 min (check edge direction in atlas) | May not need fixing |
| 5 | Concepts/immune/agent untestable | No concepts saved | 5 min (save test concepts) | N/A |

**Issue 1 is almost certainly the `"path"` vs `"file_path"` key mismatch.** That's a one-line fix that would likely unblock the entire structural audit for all external projects. Start there.
