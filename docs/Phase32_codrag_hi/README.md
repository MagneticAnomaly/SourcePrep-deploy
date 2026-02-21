# Phase 32: `codrag_hi` — IDE Sanity Check & Context Discovery Tool

## Concept

A new MCP tool called `codrag_hi` that serves as both a **developer diagnostic** and a **user onboarding/discovery** tool.

**User types "codrag_hi" in IDE chat → CoDRAG inspects project state → returns a friendly summary of what it's prepared to talk about + 3–6 suggested prompts ready to run.**

### Two personas, one tool

| Persona | Use case |
|---------|----------|
| **You (developer)** | Quick sanity check after changing file selection, rebuilding index, or testing MCP wiring. "Is the tool seeing what I expect?" |
| **End user** | Post-setup validation, context discovery after changing file tree selection. "What can CoDRAG help me with right now?" |

---

## 1. Feasibility Analysis

### What data is already available at MCP tool-call time?

Every `codrag_hi` call can hit these existing endpoints via `_api_get` / `_api_post` — **no new backend work required** for the data layer:

| Data | Endpoint | What it tells us |
|------|----------|-----------------|
| **Index status** | `GET /projects/{id}/status` | Loaded? Chunk count, model, built_at, building, stale |
| **Trace status** | (within status response) | Enabled? Node/edge count, last build |
| **Watcher status** | (within status response) | Auto-rebuild on? Pending changes? |
| **Trace coverage** | `GET /projects/{id}/trace/coverage` | Traced/untraced/stale file counts |
| **Project config** | (within project dict) | include_globs, exclude_globs, path_weights |
| **Atlas routing** | (within context response) | Routing segments, if available |
| **Available projects** | `GET /projects` | Multi-project awareness |
| **Top search results** | `POST /projects/{id}/search` | What's actually in the index (a canary query) |
| **License/tier** | `GET /license` | Feature gates the user has |

### What is NOT currently available?

| Missing data | Why it matters | Difficulty |
|--------------|---------------|------------|
| **Recently changed files** | Knowing what changed since last build makes prompts more relevant | **Low** — staleness check exists, but doesn't list specific files |
| **Open editor tabs** | IDE knows which files are open; MCP `initialize` roots give workspace, not open files | **Hard** — MCP protocol doesn't expose this (IDE-specific) |
| **User's last few queries** | Would enable "you were just looking at X" continuity | **Medium** — needs query history logging |

### Critical Prerequisite: `includedPaths` Server-Side Persistence

**The file tree selection (`includedPaths`) is half of CoDRAG's core RAG.** The trace graph + atlas provide structural context automatically. The file tree lets users manually select files/folders to add to the knowledge scope — with weights from 0.1–2.0. These two systems together ARE the RAG.

**Data flow audit (2026-02-20) — RESOLVED:**

```
Frontend (useFileSystem.ts):
  includedPaths ──── localStorage('codrag_included_paths')              ✅ local cache
                 ├─► handleBuild() → api.buildProject(id, false, paths)   ✅ sent at BUILD time
                 ├─► api.addScopeFiles() / api.removeScopeFiles()         ✅ scope orchestrator + SQLite
                 ├─► api.updateIncludedPaths(id, [...next])               ✅ full set to SQLite
                 └─► api.getIncludedPaths(id) on project load             ✅ hydrate from server

Backend:
  POST /projects/{id}/build           → included_paths filter      ✅ filters files at build time
  CodeIndex.build()                   → included_paths filter      ✅ only indexes selected files
  PUT  /projects/{id}/included_paths  → persist full set            ✅ SQLite project config
  GET  /projects/{id}/included_paths  → read included_paths         ✅ readable by MCP
  POST /projects/{id}/scope/add       → delta + persist             ✅ scope orchestrator + SQLite
  POST /projects/{id}/scope/remove    → delta + persist             ✅ scope orchestrator + SQLite
  GET  /projects/{id}/scope/status    → includes included_paths     ✅ MCP-readable
```

**All gaps closed.** The `included_paths` set is now:
- Persisted server-side in SQLite project config (survives browser clear, works across clients)
- Readable via `GET /projects/{id}/included_paths` (MCP `codrag_hi` can report what user selected)
- Synced from frontend on every toggle via `updateIncludedPaths` (belt) + `addScopeFiles`/`removeScopeFiles` (suspenders)
- Hydrated from server on project load (server is source of truth)

**Tests:** 22 tests in `tests/test_included_paths.py` covering persistence roundtrip, scope delta operations, build-time filtering, search scoping, context scoping, and combined weights+scope.

### Can it write an .md file?

**Short answer: It shouldn't need to.** The MCP tool returns structured text content — the IDE's AI chat renders it inline. Writing a file would be an unusual side effect for an MCP tool and creates questions about where to write, cleanup, and permissions.

**Better approach:** Return rich, well-formatted markdown text in the MCP response. The AI in the IDE will display it natively. If a user explicitly wants to save the output, they can ask the AI to do that.

**Exception:** For the developer diagnostic use case, an optional `save` param could write to `.codrag/diagnostics/hi_<timestamp>.md` — but that's a Phase 2 enhancement, not MVP.

### Verdict: **Fully feasible — prerequisite COMPLETE**

All core data is accessible via existing endpoints. The `includedPaths` persistence gap has been closed (2026-02-20). The tool is a **read-only aggregator** — no mutations, no LLM calls, no new dependencies. The "suggested prompts" are generated by simple heuristics based on project state, not by an LLM.

---

## 2. Research TODO List

### R-1: `includedPaths` persistence — ✅ COMPLETE (2026-02-20)
- **Delivered:** `PUT/GET /projects/{id}/included_paths` endpoints, scope add/remove now persist to SQLite, frontend hydrates from server on project load, syncs full set on every toggle.
- **Files changed:** `api/routers/projects.py`, `api/routers/scope.py`, `dashboard/src/hooks/useFileSystem.ts`, `packages/ui/src/api/client.ts`
- **Tests:** 22 tests in `tests/test_included_paths.py` — all passing

### R-1b: IDE context injection (what files does the user see in the editor?)
- **Question:** Can MCP `initialize` or tool-call params carry the user's open editor tabs?
- **Research:** MCP spec `roots`, Windsurf/Cursor-specific extensions, VS Code `activeTextEditor`
- **Impact:** Determines whether prompts can reference specific OPEN files (beyond file tree selection)
- **Fallback:** File tree selection (includedPaths) is already the primary signal

### R-2: Prompt generation strategy
- **Question:** Should prompts be static templates (rule-based) or LLM-generated?
- **Recommendation:** Start rule-based. LLM adds latency and cost for what should be a fast sanity check (<500ms).
- **Rule examples:**
  - Index stale + watcher off → "Your index is 3 hours old. Want me to rebuild it?"
  - Trace coverage <50% → "Only 40% of code files are traced. Run the trace builder?"
  - Top chunks are all docs → "Your results are docs-heavy. Adjust path weights for src/?"
  - No index → "Let's build your index first: `codrag_build`"

### R-3: Output format
- **Question:** What's the ideal response structure? Pure markdown? Structured JSON the AI interprets? Both?
- **Consideration:** Different IDEs render MCP tool responses differently (Windsurf shows raw text, Cursor may format JSON)
- **Recommendation:** Return both: `summary_md` (human-readable) + `diagnostics` (structured JSON). Let the AI choose.

### R-4: Canary query strategy
- **Question:** What query do we run against the index to sample what's in it?
- **Options:**
  - A. Generic: `"main entry point"` — shows what the index thinks is important
  - B. Based on project name: `"what does {project_name} do"` — more relevant
  - C. Multiple quick searches: `"API"`, `"config"`, `"test"` — breadth scan
  - D. No query — just use index stats + file distribution from manifest
- **Recommendation:** Option D for MVP (zero latency), Option B for Phase 2

### R-5: Multi-project behavior
- **Question:** If the user has 3 projects, should `codrag_hi` report on all of them or just the resolved one?
- **Recommendation:** Report on the resolved project, but mention others exist. ("You also have `project-b` and `project-c` indexed.")

### R-6: Rate of information vs. token cost
- **Question:** How much data should the response contain? Full diagnostic dump vs. lean summary?
- **Constraint:** MCP responses consume AI context window tokens. A 2000-char response ≈ 500 tokens.
- **Target:** <1500 chars for the summary, <500 chars for diagnostics JSON.

---

## 3. MVP — ✅ SHIPPED (2026-02-20)

### Tool: `codrag_hi`

A single MCP tool with **no required parameters** and one optional `project_id`.

**Files changed:**
- `src/codrag/mcp_tools.py` — tool schema (no required params, optional `project_id`)
- `src/codrag/mcp_server.py` — `tool_hi()` daemon-mode implementation (parallel API fetch, markdown generation)
- `src/codrag/mcp_direct.py` — `tool_hi()` direct-mode implementation (in-process, simpler)
- `tests/test_codrag_hi.py` — 29 tests, all passing

**Response structure:**
```json
{
  "_ai_note": "STANDALONE (user only said 'codrag_hi'): Present the summary conversationally... WITH A QUESTION: Briefly acknowledge, then answer...",
  "summary": "I'm looking at **my-app** — 120 files selected across **src/** (45 files), **docs/** (22 files)...",
  "diagnostics": {
    "project_id": "proj_abc",
    "project_name": "my-app",
    "index_loaded": true,
    "total_chunks": 847,
    "building": false,
    "stale": false,
    "stale_count": 0,
    "trace_enabled": true,
    "trace_nodes": 523,
    "trace_edges": 641,
    "trace_coverage_pct": 80,
    "watch_enabled": true,
    "included_paths_count": 120,
    "path_weights": {"src/core/": 1.5},
    "other_projects": ["backend-api"]
  }
}
```

### Two scenarios: standalone vs. with-prompt

The `_ai_note` field in every response tells the AI model how to present the data:

| Scenario | User says | AI behavior |
|----------|-----------|-------------|
| **Standalone** | "codrag_hi" (nothing else) | Present the summary conversationally — "I'm looking at your src/, docs/, and tests/ directories…" Mention health issues naturally. Offer suggested prompts as numbered next-step options. |
| **With a question** | "codrag_hi, then explain the auth module" | Briefly acknowledge what you see (1–2 sentences), then answer the question. Call `codrag_search` if specific code context is needed. |

The tool description also shapes this behavior: *"Present the response CONVERSATIONALLY — tell the user what files and areas you're looking at, mention any health issues, and offer the suggested prompts as numbered next-step options. If the user also asked a question, briefly summarize what you see then answer their question (use codrag_search for specifics)."*

**Example `summary` (what the tool returns):**
```markdown
I'm looking at **my-app** — 120 files selected across **src/** (45 files), **docs/** (22 files), **tests/** (18 files).
The index has 847 searchable chunks.
I can also follow the code graph (523 nodes, 641 edges, 80% coverage) to trace imports, calls, and structural relationships.
Priority areas: `src/core/` = 1.5×, `docs/` = 0.5×.

Everything looks good — index is fresh and trace graph is active.

**Here are some things I can help with:**
1. How is my-app structured? What are the main modules?
2. What API endpoints does this project expose?
3. What areas have good test coverage and what's missing?
4. What are the most connected modules in the code graph?

_(You also have backend-api, shared-lib indexed.)_
```

**Example AI response (standalone, what the user sees in chat):**
> Hi! I'm looking at your **my-app** project — I can see 120 files across `src/`, `docs/`, and `tests/`. The index has 847 chunks and the trace graph is active with 523 nodes and 641 edges (80% coverage). `src/core/` is boosted to 1.5×.
>
> Everything looks good — index is fresh and I'm ready to help. Here are some things I can do:
>
> 1. How is my-app structured? What are the main modules?
> 2. What API endpoints does this project expose?
> 3. What areas have good test coverage?
> 4. What are the most connected modules in the code graph?
>
> Just pick a number or ask me anything!

### Implementation details

**Data assembly (daemon mode):** 6 API calls in parallel via `asyncio.gather`:
```
codrag_hi called
  ├─ _resolve_project_id()                    → project_id
  ├─ asyncio.gather (parallel):
  │   ├─ GET /projects/{id}/status            → index, trace, watch, stale
  │   ├─ GET /projects/{id}/included_paths    → user's file selection
  │   ├─ GET /projects/{id}/path_weights      → weight overrides
  │   ├─ GET /projects/{id}/trace/coverage    → traced/untraced counts
  │   ├─ GET /projects                        → other available projects
  │   └─ GET /projects/{id}                   → project name
  ├─ Extract & compute:
  │   ├─ dir_counts from included_paths       → top 5 directories
  │   └─ trace_pct from coverage              → coverage percentage
  ├─ Build conversational summary (first-person, data-rich)
  ├─ Generate rule-based prompts (3-6)
  ├─ Build _ai_note (standalone vs. with-prompt guidance)
  └─ Return {_ai_note, summary, diagnostics}
```

**Health observation heuristics:**
- No index → "No index exists yet — run `codrag_build` to get started."
- Building → "Index is currently building — results will improve once it finishes."
- Stale (without watcher) → "{N} file(s) changed since last build. Run `codrag_build` to refresh..."
- Stale (with watcher) → "{N} file(s) changed since last build. Auto-rebuild is on, so it will catch up shortly."
- Trace coverage <60% → "Trace coverage is only {X}% ({traced}/{total} files)."
- Auto-rebuild off (index fresh) → "Auto-rebuild is off — if you change files, I won't pick up the changes until you rebuild."
- All clear → "Everything looks good — index is fresh and trace graph is active."

**Prompt generation heuristics:**
- `src/`, `lib/`, `core/`, `app/` → "How is {name} structured?"
- `api/`, `routes/`, `endpoints/` → "What API endpoints does this project expose?"
- `components/`, `views/`, `pages/` → "What UI components are available?"
- `tests/`, `test/` → "What areas have good test coverage?"
- `docs/` → "Summarize the project documentation"
- Trace enabled → "Most connected modules in the code graph?"
- Stale → "Rebuild my index: `codrag_build`"
- Fallbacks fill to minimum 3, maximum 6 prompts

**Graceful degradation:** If any endpoint fails (e.g., trace not configured), `asyncio.gather(return_exceptions=True)` catches the exception and the tool still returns a useful response from the endpoints that succeeded.

### Tests: 29 passing

| Category | Count | What's tested |
|----------|-------|--------------|
| **Summary structure** | 6 | Header, project name, index stats, building state, trace stats, no-index state |
| **Health notes** | 4 | Stale, stale+watcher, low trace coverage, nominal |
| **Knowledge scope** | 3 | Included paths, path weights, dir summarization |
| **Prompt generation** | 7 | No-index, src/, tests/, api/, trace, stale, min 3 / max 6 |
| **Diagnostics** | 1 | All expected keys present |
| **Edge cases** | 3 | Endpoint failures, summary length <2000 chars, other projects |
| **MCP integration** | 5 | tools/call dispatch, project_id override, tools/list, schema validation |

---

## 4. Roadmap

### Phase A: MVP (this sprint)
- **A.0: `includedPaths` persistence** — `PUT/GET /projects/{id}/included_paths`, frontend sync, fix broken `addScopeFiles`/`removeScopeFiles` stubs
- A.1: Add `codrag_hi` tool to MCP schema + both server modes
- A.2: Rule-based prompt generation from project state (including file selection)
- A.3: Response: formatted markdown summary + structured diagnostics
- A.4: Tests
- **Gate:** Works in Windsurf and Cursor, response renders cleanly, <500ms, reports user's file selection

### Phase B: Smarter Prompts
- **Canary queries:** Run 1–2 fast searches to sample what's in the index
- **Directory profiling:** Analyze manifest to report language breakdown, code/docs ratio
- **Stale file listing:** Name the specific files that changed (top 5)
- **Trace hub files:** Mention the most-connected nodes ("The core of your project is `index.py` with 47 connections")
- **Gate:** Prompts feel project-specific, not generic

### Phase C: Context-Aware (IDE integration)
- **Open editor tabs:** If IDE passes open file info via MCP extensions, use it
- **Cross-client sync:** Tauri app, VS Code extension, and browser dashboard all read/write the same server-side `includedPaths`
- **Targeted prompts:** Combine file selection + open tabs for maximum relevance
- **Gate:** Multi-client file selection works seamlessly

### Phase D: Diagnostic Mode
- **Optional `mode` param:** `"user"` (default, friendly) vs `"dev"` (full diagnostic dump)
- **Dev mode includes:** raw index stats, embedding model, config dump, atlas status, pipeline stage, enrichment scores
- **Optional `save` param:** Writes `.codrag/diagnostics/hi_<timestamp>.md`
- **Diff mode:** Compare current state to last saved diagnostic
- **Gate:** Useful for development debugging and support tickets

### Phase E: Interactive Discovery (stretch)
- **Query history:** "Last time you asked about authentication — want to continue?"
- **IDE integration:** If IDE passes open file info via MCP extensions, use it
- **Adaptive prompts:** Learn from which suggested prompts users actually run
- **Gate:** Feels like a personalized assistant, not a status page

---

## 5. Open Questions

| ID | Question | Impact | Decision needed by |
|----|----------|--------|-------------------|
| Q-1 | Should the tool be named `codrag_hi` or something more discoverable like `codrag_discover` or `codrag_overview`? | Branding, discoverability | Phase A |
| Q-2 | Should the prompt count be fixed (always 5) or dynamic (3–6 based on how much is interesting)? | UX consistency vs. relevance | Phase A |
| Q-3 | Do we need a `verbose` flag for MVP or is that Phase D? | Scope | Phase A |
| Q-4 | How do we handle the "no index built yet" state? Full onboarding wizard or just "run codrag_build"? | First-run experience | Phase A |
| Q-5 | Should prompts include the actual MCP tool syntax (e.g., "ask codrag: ...") or just natural language? | IDE compatibility | Phase A |
| Q-6 | Is <500ms response time achievable when hitting 3–4 endpoints sequentially? Should we parallelize? | UX | Phase A |

---

## 6. Why This Matters

This isn't just a diagnostic — it's the **first-contact experience** for every CoDRAG user. Today, after setup, the user stares at their IDE and thinks "now what?" `codrag_hi` answers that question instantly.

For development, it replaces the cycle of: open dashboard → check index status → check trace → mentally map what's available → go back to IDE → figure out what to ask. One command, full picture.

**Marketing angle:** "Type `codrag_hi` and your AI tells you what it knows about your code."
