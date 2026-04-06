# Phase 74: Concepts System — Implementation Plan

Build the **Concepts** epistemic layer into CoDRAG — backend concept store, generation engine, API endpoints, MCP integration, and dashboard panel.

## Context

CoDRAG answers "**what** is in the codebase" (atlas, modules) and "**where** things connect" (trace graph). Concepts answer "**why** — why this architecture, why this pattern, why this naming convention." This knowledge currently lives only in developers' heads (epistemic debt).

The architecture follows the existing **Observation Store** pattern (SQLite-backed, FTS5 search, staleness tracking) and the **Panel Registration** pattern (useDashboardPanels hook + PANEL_REGISTRY + detail overlay).

## User Review Required

> [!IMPORTANT]
> **LLM Model Dependency** — The Concept Seeder uses the `large_model` slot (thinking model) for extraction. This means concepts can only be generated when the deep enrichment model is configured. Should we fall back to `small_model` for faster but lower-quality concept seeding?

> [!WARNING]
> **Module list noise** — The CoDRAG overview currently returns 600+ modules (many 1-2 file subsystems). The Concept Seeder will need to filter to only modules with ≥5 files to avoid generating noise concepts. This is the same issue flagged in Phase 73.

---

## Proposed Changes

### Backend — Data Layer

#### [NEW] [concept_store.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/services/concept_store.py)
SQLite-backed concept store modeled after [observation_store.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/services/observation_store.py):
- `concepts` table: `id, project_id, title, content, category, status (seed|active|archived), confidence, anchors (JSON array of file paths), tags, cluster_id, created_at, updated_at, stale, stale_reason`
- `concepts_fts` FTS5 table for semantic text search
- Singleton pattern matching observation_store
- Same staleness/eviction logic — when anchored files change, concepts are flagged stale
- Categories: `technical`, `domain`, `process`, `brand`, `constraint`, `pattern`, `decision`
- Max 200 concepts per project (vs. 500 observations — concepts are heavier)

---

### Backend — Generation Engine

#### [NEW] [concept_seeder.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/concept_seeder.py)
LLM-powered concept extraction from existing pipeline outputs:
- **Inputs**: Atlas text, module synthesis data, audit findings, hub file analysis
- **Model**: Uses `large_model` slot via existing LLMClient
- **Output**: 20-40 concept seeds with title, content, category, and file anchors
- **Single LLM call**: Assembles all pipeline data into one prompt (~4000 chars), generates structured JSON response
- **Filters modules to ≥5 files** to prevent noise concept generation from the 600+ tiny modules

#### [NEW] [concept_questions.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/concept_questions.py)
Gap detection and clarifying question generation:
- Reads module list + existing concept anchors
- Identifies "uncovered" modules (no concepts anchored to them)
- Generates 5-8 targeted questions ranked by module importance (file count × hub concentration)
- Questions stored in `concept_questions` table
- Answering a question creates a new concept with `status="active"` (user-validated)

---

### Backend — API Layer

#### [NEW] [concepts.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/api/routers/projects/concepts.py)
REST endpoints under `/projects/{project_id}/concepts/`:

| Method | Path | Purpose |
|:---|:---|:---|
| `GET` | `/` | List all concepts (filterable by status, category, cluster) |
| `POST` | `/initialize` | Run concept seeder + question generator |
| `GET` | `/{id}` | Get single concept |
| `PUT` | `/{id}` | Update concept (user edits) |
| `PATCH` | `/{id}/approve` | Change status from seed → active |
| `PATCH` | `/{id}/archive` | Change status to archived |
| `DELETE` | `/{id}` | Delete concept |
| `GET` | `/questions` | List pending clarifying questions |
| `POST` | `/questions/{id}/answer` | Answer question → create concept |
| `GET` | `/stats` | Coverage, counts by status/category |
| `POST` | `/search` | FTS5 search across concepts |

#### [MODIFY] [\_\_init\_\_.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/api/routers/projects/__init__.py)
Register the new `concepts` router.

---

### Backend — MCP Integration

#### [MODIFY] [server.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/mcp/server.py)
Wire concepts into `tool_context()` (ambient context assembly, ~line 920-960):

```python
# After architecture context (Phase 71), before result assembly
try:
    concepts_data = await self._api_get(
        f"/projects/{project_id}/concepts/stats"
    )
    if isinstance(concepts_data, dict) and concepts_data.get("total", 0) > 0:
        active = concepts_data.get("active", 0)
        cats = concepts_data.get("by_category", {})
        concept_line = f"\n[Concepts: {active} active"
        if cats:
            concept_line += f" — {', '.join(f'{k}: {v}' for k, v in cats.items())}"
        concept_line += "]\n"
        md_parts.append(concept_line)
except Exception as e:
    logger.debug("Concepts context failed: %s", e)
```

Wire concepts into `tool_search()` (~line 795-833):
- After code chunk retrieval, query concept store for matching concepts
- If concept score > 0.75, prepend concept title + first 200 chars as context anchor
- This gives the AI "why" context alongside the "what" code

#### [MODIFY] [server.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/mcp/server.py) (tool registration)
Add `codrag_concepts` as a 6th MCP tool with actions:
- `action="get"` — List/search concepts (default)
- `action="save"` — Create/update a concept (same UX pattern as observations)
- This follows the observation store's tool design pattern exactly

---

### Backend — Staleness Tracking

#### [MODIFY] [scope_orchestrator.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/services/scope_orchestrator.py)
Add concept staleness tracking alongside observation staleness (~line 342):
```python
# After marking observations stale
from codrag.services.concept_store import concept_store
concept_store.mark_stale_batch(project_id, changed_paths, "file modified")
```

---

### Frontend — Dashboard

#### [NEW] [ConceptsPanel.tsx](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/components/concepts/ConceptsPanel.tsx)
Dashboard card showing:
- Concept count (seeds / active / total)
- Category breakdown (horizontal stacked bar)
- Coverage metric (% of major modules with concept anchors)
- "Initialize" button if no concepts exist
- Pending question count badge

#### [NEW] [ConceptsDetail.tsx](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/components/concepts/ConceptsDetail.tsx)
Full-screen overlay (follows ArchitectureDiagramDetail pattern):
- **Left column**: Concept list, filterable by category/status
- **Right column**: Selected concept editor (title, content as markdown, category dropdown, file anchor management, tags)
- **Bottom section**: Clarifying questions with inline answer capability
- Concept cards show: title, category badge, status indicator (seed vs active), first 2 lines of content
- Approve/archive/delete actions on each card

#### [NEW] [useConceptSystem.ts](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/dashboard/src/hooks/useConceptSystem.ts)
Central hook (follows useAuditSystem / useGoalpostsSystem pattern):
- Fetches concept stats and full concept list
- Handles initialize, approve, edit, archive, delete
- Manages question list and answer submission
- Optimistic UI updates

#### [MODIFY] [useDashboardPanels.tsx](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/dashboard/src/hooks/useDashboardPanels.tsx)
Register the Concepts panel in the panel hook:
- Import ConceptsPanel and ConceptsDetail
- Add `concepts: UseConceptSystemReturn` to DashboardPanelsProps
- Add `concepts` panel content entry
- Add concepts detail handler

#### [MODIFY] [App.tsx](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/dashboard/src/App.tsx)
Wire useConceptSystem and pass to useDashboardPanels.

---

## Open Questions

> [!IMPORTANT]
> **Concept clustering** — Should we implement concept clustering (grouping 30+ concepts into 3-8 knowledge domains) in Phase 74, or defer to a follow-up phase? This adds complexity (embedding similarity + agglomerative clustering) but makes the UI more navigable. My recommendation: **defer clustering to Phase 75** and ship the flat concept list first with manual category tagging.

> [!WARNING]
> **MCP tool naming** — Should the new MCP tool be `codrag_concepts` (a 6th standalone tool) or should concepts be folded into `codrag_observe` as a new category? The observation store already handles save/get with categories. My recommendation: **start with a new `codrag_concepts` tool** for clean separation, since concepts have richer metadata (anchors, categories, status lifecycle) than observations.

---

## Verification Plan

### Automated Tests
```bash
# Backend unit tests
.venv/bin/pytest tests/test_concept_store.py -v
.venv/bin/pytest tests/test_concept_seeder.py -v  
.venv/bin/pytest tests/test_concept_api.py -v

# MCP integration (manual — verify tool responses)
# Call codrag → should show concept count in ambient context
# Call codrag_search → should surface matching concepts
```

### Manual Verification
1. Start the dashboard (`scripts/dev.sh`)
2. Verify Concepts panel card appears in dashboard grid
3. Click "Initialize" → verify 20+ concept seeds generated
4. Approve/edit concepts → verify status changes persist
5. Answer a clarifying question → verify new concept created
6. Call `codrag` from MCP → verify concept summary appears in output
7. Call `codrag_search` with a concept topic → verify concept surfaces in results
