# Phase 74 — Implementation Roadmap

> **Research Document 5 of 5** | Phase 74: Concept Cluster Methodology  
> Date: 2026-04-04

---

## 1. Implementation Strategy

### Build Order (Dependencies First)

```
Phase A: Data Layer (Backend)          → Foundation
Phase B: Generation Engine (Backend)   → Concept seeding + clustering + questions
Phase C: API & Retrieval (Backend)     → REST endpoints + search augmentation
Phase D: Dashboard UI (Frontend)       → Panel card + detail view + editor
Phase E: MCP Integration (Glue)       → Concepts in codrag + codrag_search
Phase F: Agent Adapter (Glue)         → Role-scoped concept delivery
```

---

## 2. Phase A: Data Layer (2-3 days)

Build the persistence and data model foundation.

### Deliverables

| Task | File | Effort |
|:---|:---|:---|
| Concept data model | `src/codrag/core/concept_model.py` | 2h |
| Concept store (CRUD + persistence) | `src/codrag/services/concept_store.py` | 4h |
| Concept embeddings storage | Extend existing embedding infrastructure | 2h |
| API router skeleton | `src/codrag/api/routers/concepts.py` | 2h |

### Key Design Decisions

**Persistence format:** JSON files in `<index_dir>/concepts/`, consistent with how atlas, modules, and audit findings are stored. No new database dependencies.

**Embedding reuse:** Concept embeddings use the same ONNX/Ollama embedding model as code chunks. This ensures compatibility with existing similarity search.

**Validation:** Concepts have a `status` field. Seeds start at `status="seed"`, user approval moves to `status="active"`. Only active concepts are included in MCP context.

### Exit Criteria
- `ConceptStore().save(concept)` and `.load()` work end-to-end
- `concepts.json` persists correctly in the index directory
- API endpoint `GET /projects/{id}/concepts` returns stored concepts

---

## 3. Phase B: Generation Engine (3-5 days)

Build the LLM-powered concept extraction, clustering, and question generation.

### Deliverables

| Task | File | Effort |
|:---|:---|:---|
| Concept Seeder | `src/codrag/core/concept_seeder.py` | 8h |
| Concept Clusterer | `src/codrag/core/concept_clusterer.py` | 4h |
| Question Generator | `src/codrag/core/concept_questions.py` | 6h |
| Initialize endpoint | `src/codrag/api/routers/concepts.py` (extend) | 2h |

### Concept Seeder Strategy

The seeder reads existing pipeline outputs and extracts concepts:

```
Input Sources (in order of richness):
1. Atlas text → system-level concepts (5-10 concepts)
2. Module synthesis → per-module purpose concepts (10-20 concepts)  
3. Audit findings → constraint/anti-pattern concepts (5-10 concepts)
4. File catalogues → pattern/domain concepts (5-10 concepts)
5. Hub file analysis → importance/centrality concepts (3-5 concepts)

Total expected seeds: 30-55 concepts per initialization
```

**LLM model:** Uses the `deep` model slot (same as enrichment). Single call with assembled context. Estimated time: 60-120 seconds on local 35B model.

### Concept Clusterer Strategy

For Phase A, use simplified clustering (not full Leiden):
1. Embed all concept titles + first sentence of content
2. Compute pairwise cosine similarity matrix
3. Agglomerative clustering with threshold 0.6
4. LLM generates cluster labels (1 call, ~15s)

**Why simplified:** With 30-55 concepts, full Leiden is unnecessary overhead. Agglomerative clustering is deterministic, fast, and produces readable results. Upgrade to Leiden if concept count exceeds 200.

### Question Generator Strategy

1. Map concept anchors to modules
2. Identify "uncovered" modules (no concepts attached)
3. Rank by importance: `score = file_count * hub_concentration * edge_density`
4. Generate 5-10 questions for the top-ranked uncovered modules
5. LLM call with module context → targeted questions

### Exit Criteria
- `POST /projects/{id}/concepts/initialize` generates 30+ concept seeds
- Concepts are clustered into 3-8 coherent clusters
- 5+ clarifying questions are generated targeting uncovered modules
- Total initialization time: <3 minutes on local model

---

## 4. Phase C: API & Retrieval Integration (2-3 days)

Wire concepts into the retrieval layer and complete the API.

### Deliverables

| Task | File | Effort |
|:---|:---|:---|
| Concept retrieval layer | `src/codrag/core/concept_retrieval.py` | 6h |
| Concept search endpoint | `src/codrag/api/routers/concepts.py` (extend) | 2h |
| Question answer endpoint | `src/codrag/api/routers/concepts.py` (extend) | 3h |
| Coverage calculation | `src/codrag/core/concept_coverage.py` | 2h |

### Retrieval Integration

The concept retrieval layer hooks into the existing search pipeline:

```python
# In search.py — add concept augmentation
async def search_with_concepts(query, concept_store, code_results):
    concept_hits = concept_store.semantic_search(query, top_k=3)
    if concept_hits and concept_hits[0].score > 0.75:
        # Prepend top concept to results
        results.insert(0, format_concept_as_chunk(concept_hits[0]))
    return results
```

### Exit Criteria
- `POST /projects/{id}/concepts/search` returns semantically matched concepts
- `POST /projects/{id}/concepts/questions/{q_id}/answer` creates a concept from the answer
- Coverage endpoint reports accurate module coverage percentage
- Concept search integrates with existing `codrag_search` results

---

## 5. Phase D: Dashboard UI (4-6 days)

Build the frontend components and integrate with the dashboard.

### Deliverables

| Task | File | Effort |
|:---|:---|:---|
| ConceptsPanel (card) | `packages/ui/src/components/concepts/ConceptsPanel.tsx` | 3h |
| ConceptsDetail (overlay) | `packages/ui/src/components/concepts/ConceptsDetail.tsx` | 8h |
| ConceptCard | `packages/ui/src/components/concepts/ConceptCard.tsx` | 3h |
| ConceptEditor (sidebar) | `packages/ui/src/components/concepts/ConceptEditor.tsx` | 4h |
| ConceptClusterView | `packages/ui/src/components/concepts/ConceptClusterView.tsx` | 4h |
| ConceptQuestionList | `packages/ui/src/components/concepts/ConceptQuestionList.tsx` | 3h |
| useConceptSystem hook | `src/codrag/dashboard/src/hooks/useConceptSystem.ts` | 6h |
| Panel registry entry | `panelRegistry.ts` + `useDashboardPanels.tsx` | 2h |

### Component Breakdown

**ConceptsPanel** — The overview card on the dashboard grid. Shows concept count, cluster summary, coverage bar, and pending question count. "Initialize" button if no concepts exist.

**ConceptsDetail** — Full-screen overlay with three sections: Cluster Map, Concept List, and Clarifying Questions. Follows the same overlay pattern as ArchitectureDiagramDetail.

**ConceptCard** — A single concept displayed as an expandable card. Shows title, category badge, and first 2 lines of content. Expands to show full content, anchors, tags, and action buttons. Different border colors for seeds vs. active concepts.

**ConceptEditor** — Sidebar editor (slides in from right). Markdown editing for concept content, dropdown for category, anchor management, and tag editing.

**ConceptClusterView** — Grid of cluster cards, each showing the cluster label, concept count, and status breakdown (seeds vs. active). Clicking a cluster filters the concept list.

**ConceptQuestionList** — List of pending clarifying questions with inline answer capability. Expanding a question shows the context, suggested category, and a text area for the answer.

**useConceptSystem** — Central hook managing all concept state, API calls, optimistic updates, and initialization progress.

### Exit Criteria
- Dashboard shows Concepts panel card with accurate stats
- Clicking cards opens the full detail overlay
- Users can approve/edit/reject concept seeds
- Clarifying questions can be answered, creating new concepts
- Coverage bar updates in real-time as concepts are added

---

## 6. Phase E: MCP Integration (1-2 days)

Wire validated concepts into the MCP tool responses.

### Deliverables

| Task | File | Effort |
|:---|:---|:---|
| Concept context assembly | `src/codrag/mcp/server.py` (tool_context) | 4h |
| Concept-augmented search | `src/codrag/api/routers/projects/search.py` | 3h |

### MCP Context Format

```python
# In tool_context() → after atlas, before modules
if concepts_exist:
    context += "\n## Codebase Concepts\n"
    for cluster in clusters:
        context += f"### {cluster.label} ({len(cluster.concepts)} concepts)\n"
        for concept in cluster.concepts:
            if detail_level == "ambient":
                context += f"- {concept.title}\n"
            elif detail_level == "targeted":
                context += f"- **{concept.title}**: {concept.content[:200]}...\n"
```

### Exit Criteria
- `codrag` MCP tool includes concept summary in ambient context
- `codrag_search` surfaces relevant concepts alongside code results
- Token budget for concept context stays within limits (200-2000 chars depending on LOD)

---

## 7. Phase F: Agent Adapter Integration (1-2 days)

Weight concept delivery by agent role.

### Deliverables

| Task | File | Effort |
|:---|:---|:---|
| Role-scoped concept filtering | `src/codrag/mcp/server.py` (tool_context with role) | 3h |

### Role Weighting

```python
CONCEPT_WEIGHTS_BY_ROLE = {
    "researcher": ["technical.*", "domain.*"],           # All technical + domain
    "cto": ["technical.architecture_*", "process.*"],    # Architecture + process
    "backend_dev": ["technical.*", "process.workflow_*"], # Technical + workflows
    "designer": ["brand.*", "domain.user_mental_models"], # Brand + UX
    "custodian": ["technical.anti_patterns", "process.*"], # Anti-patterns + process
    "intern": ["domain.vocabulary", "process.*"],         # Vocabulary + process only
}
```

### Exit Criteria
- `codrag(role="designer")` surfaces brand concepts, not pipeline concepts
- `codrag(role="backend_dev")` surfaces technical concepts, not brand concepts
- Each role gets a concept-weighted view that's most relevant to their work

---

## 8. Total Effort Estimate

| Phase | Effort | Dependencies |
|:---|:---|:---|
| A: Data Layer | 2-3 days | None |
| B: Generation | 3-5 days | Phase A |
| C: API & Retrieval | 2-3 days | Phase A |
| D: Dashboard UI | 4-6 days | Phases A, B, C |
| E: MCP Integration | 1-2 days | Phase C |
| F: Agent Adapter | 1-2 days | Phases C, E |
| **Total** | **13-21 days** | |

### Critical Path

```
A (Data) ──→ B (Generation) ──→ D (Dashboard UI)
    │                               │
    └───→ C (API & Retrieval) ──────┤
                    │                │
                    └──→ E (MCP) ──→ F (Agent Adapter)
```

**Parallelization:** Phases B and C can run in parallel after Phase A. Phase D can start UI scaffolding during Phase B.

---

## 9. Success Metrics

### Quantitative

| Metric | Target | How Measured |
|:---|:---|:---|
| Concept count per project | 20-50 | `GET /projects/{id}/concepts` |
| Cluster coherence | Each cluster has 3-8 concepts | Manual review |
| Module coverage | >70% of significant modules | Coverage endpoint |
| Question-to-concept conversion rate | >40% of questions answered | Question stats |
| MCP context token efficiency | Concepts add <10% overhead | Token telemetry |

### Qualitative

| Metric | Target | How Measured |
|:---|:---|:---|
| Concept seed quality | >60% of seeds approved without edits | User approval rate |
| Search result improvement | Concepts anchor results for "why" queries | Phase 73-style audit |
| Agent decision quality | Agents reference concepts when making architectural choices | Observation review |
| Onboarding acceleration | New AI agent operates effectively faster | Comparative test |

---

## 10. Research Open Questions

These questions require further investigation during or after implementation:

### Epistemological Questions

1. **Concept Drift Detection** — How do we detect when code evolves to contradict a concept? Possible approach: track concept anchors and flag when anchored files change significantly (similar to observation staleness).

2. **Concept Completeness** — Is there a theoretical limit to the number of useful concepts for a codebase? FCA suggests the lattice grows exponentially, but practical concept stores should be finite. Research needed on optimal concept density.

3. **Concept Authority** — When an LLM-seeded concept conflicts with a user-curated concept, who wins? Currently: user always wins. But what if the LLM detects that the user's concept is outdated? Research needed on concept authority negotiation.

### Technical Questions

4. **Embedding Model Choice** — Should concept embeddings use the same model as code chunk embeddings? Or should we use a model fine-tuned for abstract reasoning (since concepts are more like prose than code)?

5. **Concept Versioning** — Should concepts have version history (like git)? This would enable "concept archaeology" — understanding how conceptual understanding evolved over time.

6. **Cross-Project Concepts** — Some concepts apply to multiple projects (e.g., "CoDRAG's coding style"). Should there be a global concept store that feeds into per-project contexts?

### UX Questions

7. **Concept Discovery** — How do users find concepts they didn't know existed? The taxonomy navigation helps, but what about serendipitous discovery?

8. **Question Fatigue** — How many clarifying questions before users stop answering? Research suggests 3-5 per session max. Need to throttle question presentation.

9. **Concept Freshness Signal** — How do we visually indicate when a concept might be stale without alarming the user unnecessarily?

---

## 11. Future Directions

### Near-Term (Phase 75+)

- **Concept ↔ Architecture Diagram Integration** — Concepts displayed as overlay annotations on the architecture diagram nodes
- **Concept-Aware Audit** — Audit rules that check for concept violations ("this code contradicts concept X")
- **Concept Import/Export** — Import concepts from README files, ADR directories, wiki pages

### Medium-Term

- **Concept Collaboration** — Multiple users curate concepts in shared team projects
- **Concept Templates** — Pre-built concept sets for common tech stacks (React, FastAPI, etc.)
- **Concept Learning** — Track which concepts agents reference most and auto-promote them in context

### Long-Term

- **Concept-Driven Development** — Invert the model: write concepts FIRST, then generate code that embodies them
- **Epistemic Health Score** — Dashboard metric showing overall "concept coverage" as a project health indicator
- **Concept Provenance Graph** — Trace the origin of every concept through the knowledge spiral (SECI model)

---

## References

All references from [02_Academic_Foundations.md](./02_Academic_Foundations.md) apply. Additional implementation references:

- CoDRAG Panel Pattern: [Phase 71 Design Document](../Phase71_MasterArchitectureDiagram/71_Design_Document.md), Sections 14-16
- Existing Audit System: `src/codrag/core/audit/` — pattern for file-based analysis with dashboard display
- Module Clustering: `src/codrag/core/cluster.py` — existing clustering implementation to reference
- LOD Compression: existing context assembly for concept compression strategy
- Agent Adapters: [Phase 62, Doc 10](../Phase62_Pi-research/10_Universal_Adapter_Architecture.md) — role-scoped context delivery

---

*This completes the Phase 74 research series. The next step is implementation planning and user review.*
