# Phase 73.4 — MCP Ecosystem Optimization Design

> Date: 2026-04-05 | Aligning CoDRAG's MCP primitives with Claude Code's ecosystem for native integration

---

## 1. Vision

CoDRAG currently exposes almost all capabilities through a single MCP primitive (tools). The MCP spec defines three primitives with distinct control models. By placing each capability on the right primitive, CoDRAG becomes a native part of every MCP client's ecosystem — not a bolted-on tool collection.

**Design principles:**
1. **Right primitive, right control model** — tools for agent-initiated actions, resources for user-browsable data, prompts for structured workflows
2. **No duplication across primitives** — same underlying data with different access patterns is OK; the same capability exposed twice is not
3. **Cross-client first** — resources and prompts work in Claude Code, Cursor, Windsurf, Gemini, VS Code. One implementation, every client.
4. **Compression-aware** — leverage Phase 73.3b tiering research to serve the right fidelity at each budget level
5. **Bootstrap handoff** — CLAUDE.md carries minimal routing; MCP server owns live structural context

---

## 2. The Three Control Models

The MCP spec defines three primitives. Each has a distinct initiator:

| Primitive | Who Initiates | Best For | CoDRAG Examples |
|-----------|--------------|----------|----------------|
| **Tool** | Model (autonomous) | Actions, dynamic queries the agent needs during reasoning | Search, impact analysis, save observations |
| **Resource** | User/App (via `@` mention) | Reference data to attach as context | Atlas, module map, hub files, audit findings |
| **Prompt** | User (via `/` command) | Structured interaction templates | Onboard, review, investigate, health check |

**Anti-pattern we're avoiding:** Making everything a tool. If the model doesn't need to autonomously decide when to fetch something, it shouldn't be a tool. Static reference data as a tool wastes tool-call budget and adds approval friction.

---

## 3. Current State: Backend Inventory

### 3.1 What Already Exists

| Capability | Location | Status |
|---|---|---|
| `resources/list` handler (4 resources) | `mcp/server.py:2092` | Working |
| `resources/read` handler with URI routing | `mcp/server.py:2133` | Working |
| Resource content generators (structure, atlas, files, health) | `mcp/server.py:2189+` | Working |
| Resource change notification | `mcp/server.py:350` | Working |
| `prompts/list` handler (3 prompts: analyze, review, plan) | `mcp/server.py:2360` | Working |
| `prompts/get` handler with argument support | `mcp/server.py:2364` | Working |
| Capabilities declaration (resources + prompts) | `mcp/server.py:2050` | Working (`listChanged: False`) |
| CLAUDE.md marker-based splicing | `rules_generator.py:682-698` | Working — preserves all user content |
| 3-tier client budgets with first-call boost | `mcp/server.py:145-186` | Working |
| Client detection via clientInfo | `mcp/server.py:2038-2046` | Working |
| 5 MCP tools with readOnlyHint + openWorldHint | `mcp_tools.py` | Working |

### 3.2 What Needs Enhancement

| Enhancement | Current State | Work |
|---|---|---|
| Additional resources (hubs, modules, audit, concepts, focus) | 4 resources | Add 3-5 more + content generators |
| Resource templates (`codrag://modules/{name}`) | Not implemented | `resources/templates/list` + resolution |
| Tier-adaptive resource content | Resources ignore tier | Wire `_get_context_budget()` |
| Better prompts (onboard, investigate, health) | 3 prompts exist | Refine existing + add new |
| Prompt resource embedding | Text-only responses | Add `resource` content type |
| Atlas hash in CLAUDE.md | Not implemented | ~40 lines across 2 files |
| Tool annotations (title, destructiveHint, idempotentHint) | Partial | ~3 fields per tool |
| `listChanged: True` + notifications | Declared False | Flip + emit on rebuild |
| Compression tiering (Phase 73.3b) | Hardcoded LOD | Parameterize with tier |

**~80% of the backend exists.** We are enhancing and expanding existing frameworks, not building from scratch.

---

## 4. Proposed Tool Placement

### 4.1 Tools (Model-Initiated — Agent Decides When to Call)

Keep tools lean. Only capabilities requiring autonomous model decision-making.

| Tool | Purpose | Change |
|---|---|---|
| `codrag` | Ambient structural context | **Slimmed** — orientation header + routing. Resources carry heavy reference data. Remains the "call at task start" entry point. |
| `codrag_search` | Semantic search + trace expansion | **Unchanged** |
| `codrag_impact` | Dependency/blast radius analysis | **Unchanged** |
| `codrag_observe` | Cross-session memory (save/get) | **Unchanged** |

**Consolidation candidates:**
- `codrag_audit` read actions → resource (`codrag://audit`). Scan-on-demand remains a tool action (either kept as lean tool or folded into existing tool with an `action` parameter).
- `codrag_concepts` read → resource (`codrag://concepts`). Save action → fold into `codrag_observe` or keep as lean tool.

**New annotations on all tools:**

```python
# Example for codrag tool
{
    "name": "codrag",
    "title": "CoDRAG: Codebase Context",
    "annotations": {
        "readOnlyHint": True,
        "destructiveHint": False,     # NEW
        "idempotentHint": True,       # NEW
        "openWorldHint": True,
    },
}
```

| Annotation | codrag | search | impact | observe |
|---|---|---|---|---|
| `title` | "CoDRAG: Codebase Context" | "CoDRAG: Code Search" | "CoDRAG: Impact Analysis" | "CoDRAG: Observations" |
| `readOnlyHint` | `true` | `true` | `true` | `false` |
| `destructiveHint` | `false` | `false` | `false` | `false` |
| `idempotentHint` | `true` | `true` | `true` | `false` |
| `openWorldHint` | `true` | `true` | `true` | `true` |

### 4.2 Resources (User-Initiated via `@` — Browsable Reference Data)

Semi-static data users can pull into context on demand. Updated on index rebuild via `notifications/resources/list_changed`.

| Resource URI | Content | Update Trigger | Audience |
|---|---|---|---|
| `codrag://{pid}/atlas` | Full codebase atlas (identity, stack, workspace map, cross-cutting) | Index rebuild / atlas regen | assistant |
| `codrag://{pid}/structure` | Hub files list with edge counts, structural role descriptions | Index rebuild | assistant |
| `codrag://{pid}/modules` | Module list with file counts, dependencies, summaries | Index rebuild | assistant |
| `codrag://{pid}/modules/{name}` | Single module detail (**template resource**) | Index rebuild | assistant |
| `codrag://{pid}/audit` | Latest audit findings summary | Audit scan completion | both |
| `codrag://{pid}/concepts` | Epistemic knowledge layer — categories + top concepts | Concept save/approve | assistant |
| `codrag://{pid}/focus` | User's selected focus areas with content excerpts | User config change | assistant |
| `codrag://{pid}/health` | Index freshness, coverage, build status | Build events | both |

**Design decisions:**
- **Tier-adaptive content**: Resource responses respect the client's context budget. Claude Code reading `@codrag://hubs` gets 10 hubs at LOD 0. Cline gets 4 at LOD 2. Same URI, different fidelity.
- **Resource templates**: `codrag://{pid}/modules/{name}` enables auto-complete when users type `@codrag://modules/`. Requires `resources/templates/list` handler.
- **`listChanged: True`**: Emit `notifications/resources/list_changed` on index rebuild, audit completion, and concept events.
- **Audience annotation**: `audit` and `health` are `["user", "assistant"]` (humans browse these). Others are `["assistant"]` (model consumption).

### 4.3 Prompts (User-Initiated via `/` — Structured Workflows)

Reusable interaction templates. Work across ALL MCP clients (unlike `.claude/skills/`).

| Prompt | Arguments | Returns |
|---|---|---|
| `codrag-onboard` | none | Multi-message: system orientation + embedded `codrag://atlas` + suggested first actions |
| `codrag-review` | `file_path` (required), `scope` (optional: file/module/blast-radius) | Impact context + review checklist + embedded hub resources for related files |
| `codrag-investigate` | `query` (required) | Search strategy + trace expansion context + module map for relevant area |
| `codrag-health` | `focus` (optional: debt/complexity/coverage) | Embedded audit findings + prioritized recommendations |
| `codrag-plan` | `change` (required) | Impact analysis + affected files + change strategy (keep existing, refine) |

**Design decisions:**
- **Prompts embed resources** via `resource` content type (e.g., `onboard` embeds `codrag://atlas` and `codrag://modules`). This means prompt content stays fresh without duplication.
- **Arguments support auto-completion** via the MCP completion API. `file_path` completes from project index; `query` from recent searches.
- **Prompts return `role: "user"` messages** that prime the conversation — the model then uses tools (search, impact) as needed to fulfill the workflow.
- **`.claude/skills/codrag.md` remains** as a Claude Code-specific enhancement. Skills can restrict tool access and delegate to subagents — capabilities prompts lack. The skill and prompts serve different audiences: skill for Claude Code power users, prompts for all MCP clients.

---

## 5. CLAUDE.md Bootstrap Handoff (Hash-Based Freshness)

### 5.1 Problem

CLAUDE.md currently embeds ~2-4K chars of atlas content that goes stale on index rebuild. The MCP server detects staleness via `atlas_updated.signal` but can only skip duplication, not update CLAUDE.md mid-session.

### 5.2 Solution: Content Hash

Embed a hash of the atlas content in CLAUDE.md. The MCP server computes the current hash on each `codrag` call and compares.

**In CLAUDE.md** (written by `rules_generator.py`):
```markdown
<!-- codrag-managed-start -->
<!-- codrag-atlas-hash:a3f2b7c1e9d4 -->
# CoDRAG Integration
codrag_project_id: 1d6f0b35-...
...
## Codebase Atlas
[full atlas content]
<!-- codrag-managed-end -->
```

**In MCP server** (`tool_context()`):
1. On `codrag` call, compute `hashlib.sha256(current_atlas).hexdigest()[:12]`
2. Compare to hash read from rules file (cached per project)
3. **Match** → skip atlas in response, note "atlas current in rules file" → saves 2-4K chars for code content
4. **Mismatch** → include fresh atlas + trigger async rules file regeneration
5. Return `atlas_fresh: true/false` in response metadata

**Existing marker system is safe.** `rules_generator.py:682-698` already uses `<!-- codrag-managed-start/end -->` markers and only replaces the managed section. All user content and content from other tools is preserved.

### 5.3 Implementation

~20 lines in `rules_generator.py` (embed hash when writing) + ~20 lines in `server.py` (compare and decide).

---

## 6. Compression Tier Integration (Phase 73.3b)

Leverage the 14-mechanism tiering research to serve tier-appropriate fidelity from both tools AND resources.

### 6.1 Tier-Adaptive Parameters

| Parameter | Tier 1 (50K) Claude/Gemini | Tier 2 (30K) Cursor/Windsurf | Tier 2.5 (20K) Local |
|---|---|---|---|
| Hub files | 10 @ LOD 0 | 6 @ LOD 0 | 4 @ LOD 2 |
| Neighbors | LOD 1 (source - comments) | LOD 2 (signatures) | LOD 4 (names + imports) |
| Module summaries | Full tiered | Significant + small | Significant only |
| LOD score thresholds | >=0.40 → LOD 0 | >=0.50 → LOD 0 | >=0.60 → LOD 0 |
| Trace expansion budget | 6K chars | 4K chars | 2K chars |
| Score threshold | min_score=0.15 | min_score=0.20 | min_score=0.25 |
| Concept summaries | Top 3 included | Not included | Not included |

### 6.2 Content Ordering (Lost-in-the-Middle)

Based on attention research (Liu et al., 2023; Chroma Context Rot, 2025) — most-actionable first, orientation at end:

```
1. Module list + atlas header    (top — highest attention)
2. Search results LOD 0          (focal code — right after orientation)
3. Hub files                     (structural spine — early-middle)
4. Trace neighbors               (supplementary — late-middle)
5. Module summaries              (orientation tail — end, recency attention bump)
```

### 6.3 Resource-Specific Tiering

Resources respect client tier. The same URI returns different fidelity based on `_get_context_budget()`:

- `@codrag://structure` in Claude Code → 10 hubs at LOD 0 (~15K chars)
- `@codrag://structure` in Cline → 4 hubs at LOD 2 (~4K chars)

This is automatic — the server knows the client tier from the initialize handshake.

---

## 7. Quick Fixes (Ship Independently)

These can land immediately with no dependencies on the larger work:

| Fix | File | Effort | Impact |
|---|---|---|---|
| Add `title` to all tool annotations | `mcp_tools.py` | Trivial | Better UI display in tool lists |
| Add `destructiveHint: false` to all tools | `mcp_tools.py` | Trivial | Clearer safety signal for auto-approval |
| Add `idempotentHint: true` to read-only tools | `mcp_tools.py` | Trivial | Better retry/auto-approval behavior |
| Document `"allow": ["mcp__codrag"]` in AGENTS.md | `rules_generator.py` | Small | Users stop clicking approve on every call |
| Flip `listChanged: True` in capabilities | `server.py:2050-2054` | Trivial | Enable dynamic resource/prompt refresh |
| Embed atlas hash in CLAUDE.md | `rules_generator.py` | Small | Eliminates stale atlas duplication |
| Hash comparison in `tool_context()` | `server.py` | Small | Smarter atlas dedup |

---

## 8. Implementation Plan

### Phase 1: Annotations & Bootstrap (1-2 days)

**Goal:** Quick wins that improve the integration immediately.

| Task | Files | Details |
|---|---|---|
| Add missing tool annotations | `mcp_tools.py` | `title`, `destructiveHint`, `idempotentHint` on all 5+ tools |
| Atlas content hash | `rules_generator.py` | Compute SHA-256 of atlas, embed as `<!-- codrag-atlas-hash:... -->` |
| Hash comparison logic | `server.py:tool_context()` | Compare current hash vs rules file hash, skip/include atlas accordingly |
| Flip `listChanged` | `server.py:2050-2054` | Set to `True` for tools, resources, prompts |
| Permission hint in AGENTS.md | `rules_generator.py:_build_managed_content()` | Add `"allow": ["mcp__codrag"]` recommendation |
| Emit `list_changed` on rebuild | `server.py` | Fire `notifications/tools/list_changed` when atlas signal detected |

### Phase 2: Resource Expansion (3-5 days)

**Goal:** Full resource surface for `@` browsing across all MCP clients.

| Task | Files | Details |
|---|---|---|
| Add new resource types | `server.py:handle_resources_list()` | Add hubs, modules, audit, concepts, focus to resource list |
| New content generators | `server.py` | `_resource_hubs()`, `_resource_modules()`, `_resource_audit()`, `_resource_concepts()`, `_resource_focus()` |
| Resource template support | `server.py` | Add `resources/templates/list` handler for `codrag://modules/{name}` |
| Template resolution in `resources/read` | `server.py:handle_resources_read()` | Parse template parameters, route to per-module content |
| Tier-adaptive resource content | `server.py` resource generators | Wire `_get_context_budget()` into resource content assembly |
| Resource annotations | `server.py:handle_resources_list()` | Add `audience`, `mimeType` annotations per resource |
| Wire `list_changed` notifications | `server.py` | Emit on index rebuild, audit completion, concept events |

### Phase 3: Prompt Enhancement (2-3 days)

**Goal:** Cross-client workflows via MCP prompts.

| Task | Files | Details |
|---|---|---|
| Refine existing prompts | `server.py:_PROMPTS` | Update analyze→onboard, improve review and plan |
| Add new prompts | `server.py:_PROMPTS` + `handle_prompts_get()` | `codrag-investigate`, `codrag-health` |
| Resource embedding in prompts | `server.py:handle_prompts_get()` | Add `resource` content type referencing `codrag://` URIs |
| Argument auto-completion | `server.py` | Add `completion/complete` handler for file_path and query args |
| Update skill to reference prompts | `.claude/skills/codrag.md` generator | Note prompt availability alongside tools |

### Phase 4: Compression Tiering (3-5 days)

**Goal:** Implement Phase 73.3b tier-adaptive context assembly.

| Task | Files | Details |
|---|---|---|
| Create `ContextTier` enum/config | New: `core/context_tier.py` | Tier 1/2/2.5 parameters from Section 6.1 |
| Parameterize `assign_lod()` | `core/lod_extractor.py` | Accept tier, adjust score→LOD thresholds |
| Tier-adaptive hub count + LOD | `api/routers/projects/search.py` | Hub count and LOD from tier config |
| Tier-adaptive neighbor LOD | `api/routers/projects/search.py` | Neighbor LOD from tier config |
| Content ordering fix | `mcp/server.py` context assembly | Reorder: orientation → focal → hubs → neighbors → summaries |
| Tier-adaptive score thresholds | `core/models.py` or search.py | min_score from tier config |
| Wire tier into MCP server | `mcp/server.py` | `_get_context_tier()` from client budget, pass to API calls |

### Phase 5: Tool Consolidation (2-3 days)

**Goal:** Slim down tool surface now that resources carry reference data.

| Task | Files | Details |
|---|---|---|
| Migrate `codrag_audit` read to resource | `mcp_tools.py`, `server.py` | Keep scan as tool; findings become resource-only |
| Migrate `codrag_concepts` read to resource | `mcp_tools.py`, `server.py` | Keep save as tool; browse becomes resource-only |
| Backward compat aliases | `mcp_tools.py:TOOL_ALIASES` | Legacy tool names → resource hints for one release cycle |
| Update AGENTS.md generation | `rules_generator.py` | Reflect new primitive placement in generated instructions |
| Update `.claude/skills/codrag.md` | `rules_generator.py` | Reference resources and prompts alongside tools |

---

## 9. Capability Placement Matrix (Final State)

| Capability | Tool | Resource | Prompt | CLI | HTTP API | Dashboard |
|---|---|---|---|---|---|---|
| Ambient context / atlas | `codrag` (slim) | `codrag://atlas` | embedded in onboard | overview | /atlas | Architecture panel |
| Semantic search | `codrag_search` | — | embedded in investigate | search | /search | Search panel |
| Impact analysis | `codrag_impact` | — | embedded in review | — | /trace/impact | Trace panel |
| Hub files | — | `codrag://structure` | — | coverage | /trace/hub_files | — |
| Module map | — | `codrag://modules` | — | — | /modules | — |
| Single module detail | — | `codrag://modules/{name}` | — | — | /modules/{id} | — |
| Audit findings | — | `codrag://audit` | embedded in health | audit | /audit/findings | Audit panel |
| Audit scan | `codrag_audit` (scan only) | — | — | audit scan | POST /audit | Dashboard |
| Observations | `codrag_observe` | — | — | — | /observations | Observations |
| Concepts (browse) | — | `codrag://concepts` | — | — | /concepts | Concepts |
| Concepts (save) | `codrag_observe` or dedicated | — | — | — | POST /concepts | Create concept |
| Focus areas | — | `codrag://focus` | — | — | /included_paths | Settings |
| Index health | — | `codrag://health` | embedded in health | status | /status | Status |
| Onboard workflow | — | — | `codrag-onboard` | — | — | — |
| Review workflow | — | — | `codrag-review` | — | — | — |
| Investigate workflow | — | — | `codrag-investigate` | — | — | — |
| Health check workflow | — | — | `codrag-health` | — | — | — |
| Plan change workflow | — | — | `codrag-plan` | — | — | — |

---

## 10. Key Design Decisions

### 10.1 Why keep `codrag` as a tool AND have resources?

The `codrag` tool serves a unique role: it's the "call at task start" entry point that agents invoke autonomously. No resource can do this — resources require user action (`@` mention). The tool returns a slim orientation response; resources carry the heavy reference data. Different access patterns, same underlying data.

### 10.2 Why not merge prompts into Claude Code skills?

Skills are Claude Code-only. MCP prompts work in Cursor, Windsurf, Gemini, VS Code, Copilot — every MCP client. One implementation serves all. The `.claude/skills/codrag.md` remains for Claude Code power users who need skill-specific features (subagent delegation, tool restriction).

### 10.3 Why tier-adaptive resources?

The same `@codrag://structure` URI should work for a 1M-context Opus user and a 20K-context local model user. Returning 15K chars to a 20K budget client is unusable. Tier-adaptive content means resources "just work" regardless of client capability.

### 10.4 Why the atlas hash instead of removing atlas from CLAUDE.md?

CLAUDE.md is static context — always in the agent's window without a tool call. This is valuable for sessions where the daemon might not be running, or when the agent is reasoning before its first tool call. The hash ensures we never waste budget sending the same atlas twice.

---

## 11. Research References

| Source | Key Finding |
|---|---|
| MCP Spec (2025-06-18) | Tools = model-controlled, Resources = app-driven, Prompts = user-controlled |
| MCP Tool Annotations Blog (2026-03) | `readOnlyHint`, `destructiveHint`, `idempotentHint` influence auto-approval classifiers |
| Claude Code MCP Docs | Supports resources (`@` mention), prompts (`/` commands), tool annotations |
| Phase 73.3b Compression Research | 14 context knobs, 3 tiers; Selection > Fidelity > Volume |
| Lost in the Middle (Liu et al., 2023) | Content at beginning/end gets most attention |
| Context Rot (Chroma, 2025) | Every model degrades with context length; less, better > more, worse |
| LongCodeZip (Shi et al., 2025) | Token pruning corrupts code; extractive compression (LOD) is correct |
| CodexGraph (Liu et al., 2024) | Graph retrieval 2.5x better than embedding-only for code |

---

## 12. Success Criteria

1. **All 5+ resources browsable** via `@` in Claude Code, Cursor, and VS Code
2. **All 5 prompts available** as `/mcp__codrag__*` slash commands across MCP clients
3. **Tool count stays at 4** (codrag, search, impact, observe) — lean and focused
4. **Atlas hash eliminates duplication** — `codrag` response omits atlas when CLAUDE.md is current
5. **Tier-adaptive content** — resource fidelity matches client capability automatically
6. **CLAUDE.md remains safe** — marker-based splicing never overwrites user content
7. **Zero regressions** — existing tool callers see no behavior change (backward compat aliases)
