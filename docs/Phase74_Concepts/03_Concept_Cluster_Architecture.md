# Phase 74 — Concept Cluster Architecture

> **Research Document 3 of 5** | Phase 74: Concept Cluster Methodology  
> Date: 2026-04-04

---

## 1. Design Decision: Dashboard Panel, Not Pipeline Stage

### Why Not a 12th Pipeline Stage

Originally this was considered as a 12th stage in the 11-stage pipeline. After analysis, this is the wrong home:

| Concern | Pipeline Stage | Dashboard Panel |
|:---|:---|:---|
| **Initialization** | Runs every pipeline build | Runs on-demand ("Initialize Concepts") ✅ |
| **Mutability** | Regenerated on rebuild (ephemeral) | Persistent, user-editable ✅ |
| **Cost** | Adds ~2-5 min to every build | One-time cost, then incremental ✅ |
| **User control** | No user interaction during pipeline | Rich UI for editing/validation ✅ |
| **Dependencies** | Tightly coupled to orchestrator | Loosely coupled, reads existing data ✅ |

**Decision:** Concepts is a standalone system, initialized like the Architecture Diagram or Audit — on-demand, with its own lifecycle and persistence. It *reads* pipeline outputs (atlas, modules, catalogues, enrichment) but doesn't modify or extend the pipeline.

### Architectural Pattern

Following the established CoDRAG panel pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│  ModularDashboard                                                │
│                                                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ Pipeline   │  │ Audit      │  │ Architect  │  │ CONCEPTS │  │
│  │ Status     │  │ Findings   │  │ Diagram    │  │  (NEW)   │  │
│  └────────────┘  └────────────┘  └────────────┘  └──────────┘  │
│                                                                   │
│  Each panel has:                                                  │
│  • PanelCard  → Summary view on dashboard grid                   │
│  • DetailView → Full-screen overlay on click                     │
│  • Hook       → State management (useConceptSystem.ts)           │
│  • API        → Backend endpoints (/projects/{id}/concepts/...)  │
│  • Data       → File-based persistence (<index_dir>/concepts/)   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. System Architecture

### 2.1 Data Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                       │
│   EXISTING DATA                    CONCEPT ENGINE          USER       │
│   (read-only inputs)               (new system)            (curator)  │
│                                                                       │
│   ┌──────────┐                                                       │
│   │  Atlas    │──┐                                                   │
│   │  Text     │  │                                                   │
│   └──────────┘  │    ┌─────────────────┐                             │
│                  │    │                  │                            │
│   ┌──────────┐  ├───▶│  CONCEPT SEEDER │                            │
│   │  Module   │  │    │  (LLM-based)    │                            │
│   │ Synthesis │  │    │                  │                            │
│   └──────────┘  │    │  Extracts        │     ┌──────────────────┐   │
│                  │    │  candidate       │────▶│  CONCEPT STORE   │   │
│   ┌──────────┐  │    │  concepts from   │     │                  │   │
│   │  File     │──┤    │  existing data   │     │  concepts.json   │   │
│   │ Catalogue │  │    └─────────────────┘     │  clusters.json   │   │
│   └──────────┘  │                              │  questions.json  │   │
│                  │    ┌─────────────────┐      │  embeddings.npy  │   │
│   ┌──────────┐  │    │                  │     │                  │   │
│   │  Audit    │──┤    │  CONCEPT        │     └────────┬─────────┘   │
│   │ Findings  │  │    │  CLUSTERER      │              │             │
│   └──────────┘  │    │  (Leiden algo)   │◀─────────────┘             │
│                  │    │                  │                            │
│   ┌──────────┐  │    └─────────────────┘     ┌──────────────────┐   │
│   │  Trace    │──┘                             │  QUESTION        │   │
│   │  Graph    │    ┌─────────────────┐        │  GENERATOR       │   │
│   └──────────┘    │                  │        │  (LLM-based)     │   │
│                    │  CONCEPT        │        │                  │   │
│                    │  RETRIEVAL      │        │  Identifies gaps  │   │
│                    │  LAYER          │        │  Generates        │   │
│                    │                  │        │  clarifying Qs    │   │
│                    │  Augments:       │        └──────────────────┘   │
│                    │  • codrag_search │                               │
│                    │  • codrag (overview)                             │
│                    │  • Agent briefs  │                               │
│                    └─────────────────┘                               │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Architecture

```
Backend:
src/codrag/
├── api/routers/
│   └── concepts.py              # NEW — REST endpoints for concepts CRUD
├── core/
│   ├── concept_seeder.py        # NEW — LLM-based concept extraction from atlas/modules
│   ├── concept_clusterer.py     # NEW — Leiden clustering on concept affinity graph
│   ├── concept_retrieval.py     # NEW — Concept-aware search augmentation
│   └── concept_questions.py     # NEW — Gap detection + clarifying question generation
├── services/
│   └── concept_store.py         # NEW — Persistence layer (JSON files in index dir)
└── mcp/
    └── server.py                # MODIFY — Include concepts in tool_context()

Frontend:
packages/ui/src/components/concepts/
├── ConceptsPanel.tsx            # Overview card for dashboard grid
├── ConceptsDetail.tsx           # Full-screen overlay
├── ConceptCard.tsx              # Individual concept display/edit
├── ConceptClusterView.tsx       # Cluster visualization
├── ConceptEditor.tsx            # Markdown editor for concept content
├── ConceptQuestionList.tsx      # Clarifying questions UI
├── ConceptTaxonomyNav.tsx       # Category tree navigation
└── index.ts                     # Barrel exports

src/codrag/dashboard/src/hooks/
└── useConceptSystem.ts          # State management, API calls, persistence
```

---

## 3. Data Model

### 3.1 Concept (Core Entity)

```python
@dataclass
class Concept:
    """A first-class unit of knowledge about the codebase."""
    
    id: str                          # UUID
    title: str                       # "Why we use SQLite for storage"
    content: str                     # Markdown body (the actual knowledge)
    category: str                    # From taxonomy: "technical.architecture_rationale"
    
    # Provenance
    source: str                      # "seeded" | "user" | "question_answer" | "imported"
    confidence: float                # 0.0-1.0 (seeded=0.5, user-validated=1.0)
    
    # Anchoring
    anchors: List[ConceptAnchor]     # Links to code (files, modules, symbols, or "system")
    
    # Clustering
    cluster_id: Optional[str]        # Which concept cluster this belongs to
    
    # Search
    embedding: Optional[List[float]] # Semantic embedding for retrieval
    tags: List[str]                  # User + LLM generated tags
    
    # Lifecycle
    status: str                      # "seed" | "active" | "deprecated" | "rejected"
    created_at: str
    updated_at: str
    validated_by: str                # "user" | "auto" | empty (for seeds)
    
    # Metadata
    related_concept_ids: List[str]   # Cross-references to other concepts
    source_evidence: List[str]       # Which atlas/module/catalogue text generated this seed
```

### 3.2 Concept Anchor

```python
@dataclass
class ConceptAnchor:
    """Links a concept to the code it describes."""
    
    anchor_type: str     # "file" | "module" | "symbol" | "system" | "directory"
    target: str          # File path, module ID, symbol name, or "system" for global concepts
    relevance: float     # How relevant this anchor is (0.0-1.0)
```

### 3.3 Concept Cluster

```python
@dataclass
class ConceptCluster:
    """A group of related concepts forming a knowledge domain."""
    
    id: str
    label: str           # "Pipeline Architecture" | "Brand Identity"
    description: str     # LLM-generated summary of what this cluster covers
    concept_ids: List[str]
    parent_cluster_id: Optional[str]   # For hierarchical clustering
    level: int           # 0 = top-level, 1 = sub-cluster
```

### 3.4 Clarifying Question

```python
@dataclass
class ClarifyingQuestion:
    """A system-generated question designed to elicit a concept."""
    
    id: str
    question: str        # "Why does the pipeline use 11 stages?"
    context: str         # Evidence that prompted this question
    target_category: str # Suggested concept category for the answer
    target_anchors: List[str]  # Suggested code anchors
    
    # State
    status: str          # "pending" | "answered" | "dismissed"
    answer: Optional[str]        # User's response
    generated_concept_id: Optional[str]  # Concept created from the answer
    
    created_at: str
    priority: float      # How important this question is (based on code coverage gap)
```

### 3.5 Persistence

```
<index_dir>/concepts/
├── concepts.json         # All concepts (array of Concept objects)
├── clusters.json         # Concept clusters (from Leiden)
├── questions.json        # Active clarifying questions
├── history.json          # Audit trail (concept edits, answers, etc.)
└── embeddings.npy        # Concept embedding vectors (for retrieval)
```

---

## 4. Concept Generation Pipeline

### 4.1 Phase 1: Seed Generation

The Concept Seeder reads CoDRAG's existing enrichment data and extracts candidate concepts:

```python
class ConceptSeeder:
    """Extracts concept seeds from existing CoDRAG knowledge."""
    
    def seed(self, project_data: ProjectData) -> List[Concept]:
        """
        Input sources (in priority order):
        1. Atlas text — parse for domain concepts, system overview
        2. Module synthesis — each module → potential technical concept
        3. File catalogues — identify repeated patterns, anti-patterns
        4. Audit findings — extract constraint rationale
        5. Trace graph metadata — hub files → importance concepts
        6. README/docs — existing documentation → concept extraction
        """
```

**LLM Prompt Strategy:**

```
SYSTEM: You are a knowledge engineer extracting conceptual understanding 
from a codebase analysis. For each concept, provide:
- A clear title (what the concept IS)
- A description (WHY this matters and HOW to think about it)  
- A category from: {domain.business_rules, domain.vocabulary, 
  technical.architecture_rationale, technical.pattern_intentions,
  technical.anti_patterns, technical.constraint_rationale,
  brand.identity, brand.positioning, process.workflow_rules, ...}
- Confidence level (0.3 for speculative, 0.7 for well-evidenced)
- Code anchors (which files/modules this concept relates to)

INPUT: Here is the codebase atlas and module synthesis data:
{atlas_text}

MODULES:
{module_summaries}

KEY FINDINGS:
{audit_findings_summary}

Extract 15-25 concept seeds. Focus on WHY things exist, not WHAT they do.
The "what" is already captured in catalogues. We need the "why" and "how to 
think about it."
```

### 4.2 Phase 2: Clustering

After seeding, the Concept Clusterer groups related concepts:

```python
class ConceptClusterer:
    """Groups concepts into coherent knowledge domains."""
    
    def cluster(self, concepts: List[Concept]) -> List[ConceptCluster]:
        """
        1. Compute pairwise concept similarity (via embeddings)
        2. Build concept affinity graph (edge weight = similarity)
        3. Apply Leiden algorithm with resolution parameter
        4. Generate cluster labels via LLM
        5. Optionally: hierarchical clustering (level 0 → level 1)
        """
```

**Simplified Leiden (since we have <100 concepts, not 50,000 graph nodes):**

For the initial version, we can use a simpler clustering approach:
- Compute cosine similarity between all concept embeddings
- Threshold at 0.7 similarity to create edges
- Run connected components (or simple agglomerative clustering)
- Generate cluster labels via LLM

Full Leiden is overkill for <100 concepts — save it for when the concept store grows large.

### 4.3 Phase 3: Question Generation

The Question Generator identifies gaps in concept coverage:

```python
class ConceptQuestionGenerator:
    """Identifies uncovered code areas and generates clarifying questions."""
    
    def generate(self, concepts: List[Concept], modules: List[Module]) -> List[ClarifyingQuestion]:
        """
        Gap Detection:
        1. Map all concept anchors to their target modules
        2. Identify modules with NO concept coverage
        3. Identify modules with LOW concept coverage (<2 concepts)
        4. Prioritize by module importance (file count, hub score, edge count)
        
        Question Generation:
        5. For each gap, generate a targeted question:
           - "Module X has Y files but no documented rationale. 
              Why does this module exist? What role does it play?"
           - "File Z is a hub file with W connections. 
              What makes it so central? Why is it structured this way?"
        """
```

---

## 5. Retrieval Integration

### 5.1 Concept-Augmented Search

When `codrag_search` is called, the concept layer provides a secondary retrieval channel:

```python
class ConceptRetrieval:
    """Augments codrag_search with concept-aware retrieval."""
    
    def augment_search(self, query: str, code_results: List[Chunk]) -> List[Chunk]:
        """
        1. Embed the query
        2. Find concepts with high similarity to the query (top 3)
        3. If a concept matches with score > 0.8:
           a. Prepend concept text to the search results
           b. Boost code chunks anchored to the matched concept
        4. If a concept matches with score 0.6-0.8:
           a. Append concept as "Related Concept" in results
        """
```

### 5.2 Concept Context in `codrag` Overview

When the `codrag` MCP tool is called, concepts are included in the ambient context:

```
## Codebase Concepts (12 concepts in 4 clusters)

### Pipeline Architecture (4 concepts)
- "11-Stage Pipeline Design": The pipeline uses 11 stages because stages 1-5 are 
  structural (fast, no LLM) while stages 6-10 are epistemic (deep, LLM-required). 
  This split enables "Fast Sync" (stages 1-5 only) for quick updates.
- "Concurrency Model": Pipeline uses 3 model slots (fast, code, deep) to avoid 
  VRAM contention on consumer GPUs...

### Brand & Positioning (3 concepts)
- "Sovereign Context": User code never leaves their machine...
- ...
```

**Token budget:** Concepts are compressed using LOD (Level of Detail). At high compression, only cluster labels + concept titles are shown (~200 chars). At full detail, concept bodies are included (~2000 chars). The `max_chars` parameter controls this.

### 5.3 Concept Delivery Modes

| Mode | Trigger | Content Level | Token Cost |
|:---|:---|:---|:---|
| **Ambient** | Every `codrag` call | Cluster labels + titles only | ~200 chars |
| **Targeted** | `codrag_search` matches a concept | Matched concept(s) full text | ~500-1500 chars |
| **Deep** | Explicit request or "concepts" query | All concepts in matched cluster | ~3000-5000 chars |
| **Full** | `codrag_search(query="concepts", type="context")` | All concepts | ~8000-15000 chars |

---

## 6. MCP Tool Integration

### 6.1 Option A: Add to Existing Tools (Recommended)

Concepts are surfaced *through* existing MCP tools, not as a new tool:

- `codrag()` → includes concept summary in ambient context
- `codrag_search(query="why does the pipeline...")` → concept about pipeline design surfaces
- `codrag_audit(action="advise")` → concepts provide contextual framing for recommendations

This avoids adding a 6th MCP tool (which costs token budget for tool descriptions).

### 6.2 Option B: New MCP Tool (If Explicit Access Needed)

```python
# codrag_concepts(action, query, category)
# action: "list" | "search" | "get" | "add"
# query: semantic search query
# category: filter by taxonomy category
```

**Recommendation:** Start with Option A. The value of concepts is that they *implicitly improve everything* — agents don't need to know about concepts to benefit from them. If explicit concept access becomes valuable, add Option B later.

---

## 7. API Design

```
# Concept CRUD
GET    /projects/{id}/concepts                    # List all concepts (with filters)
POST   /projects/{id}/concepts                    # Create a concept
PUT    /projects/{id}/concepts/{concept_id}        # Update a concept
DELETE /projects/{id}/concepts/{concept_id}        # Delete a concept

# Concept Generation
POST   /projects/{id}/concepts/initialize          # Seed + cluster concepts
POST   /projects/{id}/concepts/generate-questions   # Generate clarifying questions

# Questions
GET    /projects/{id}/concepts/questions            # List pending questions
POST   /projects/{id}/concepts/questions/{q_id}/answer  # Answer a question → creates concept
POST   /projects/{id}/concepts/questions/{q_id}/dismiss # Dismiss a question

# Clusters
GET    /projects/{id}/concepts/clusters             # Get concept clusters

# Stats
GET    /projects/{id}/concepts/coverage             # Coverage report (% of modules with concepts)

# Search
POST   /projects/{id}/concepts/search               # Semantic search over concepts
```

---

## 8. UI-Relevant Architectural Decisions

### 8.1 "Initialize" Pattern

Like the Architecture Diagram panel, the Concepts panel starts empty with a prominent "Initialize Concepts" button. When clicked:

1. Backend runs Concept Seeder (LLM call, ~60-120s)
2. Backend runs Concept Clusterer (~5s)
3. Backend runs Question Generator (~30s)
4. Frontend receives concepts, clusters, and questions
5. Panel transitions from "empty" to "populated" state

### 8.2 Concept as Editable Knowledge

Every concept is a markdown-editable card. Users can:
- Edit the title and content
- Change the category
- Add/remove anchors
- Approve seeds (→ status changes from "seed" to "active")
- Deprecate outdated concepts
- Create new concepts from scratch ("Quick Add")

### 8.3 Clarifying Questions as Onboarding

The questions UI serves dual purpose:
- For the user: "Fill in the gaps" in codebase understanding
- For the system: "Train" the concept model on domain knowledge the LLM can't infer

Questions are presented as a friendly list with one-click expansion:
```
❓ "Why does the pipeline use 11 stages instead of fewer?"
   Context: The pipeline has stages 1-5 (structural) and 6-10 (epistemic).
   This separation is unusual — most analysis tools use 3-4 stages.
   Category suggestion: Technical > Architecture Rationale
   
   [Answer this] [Dismiss] [Generate concept from existing docs]
```

### 8.4 Overlay / Structural Similarity to Architecture Diagram

Per the user's UI vision, concepts should structurally mirror the Architecture Diagram's overlay approach:

```
┌──────────────────────────────────────────────────────────────────┐
│ CONCEPTS                                    [Initialize] [+ Add] │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │  CONCEPT CLUSTERS (visual, clickable)                        │  │
│ │                                                              │  │
│ │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │  │
│ │  │ Pipeline     │  │ Brand &      │  │ API Design   │      │  │
│ │  │ Architecture │  │ Positioning  │  │ Patterns     │      │  │
│ │  │ (5 concepts) │  │ (3 concepts) │  │ (4 concepts) │      │  │
│ │  └──────────────┘  └──────────────┘  └──────────────┘      │  │
│ │                                                              │  │
│ │  ┌──────────────┐  ┌──────────────┐                         │  │
│ │  │ Domain       │  │ Process &    │                         │  │
│ │  │ Model        │  │ Conventions  │                         │  │
│ │  │ (4 concepts) │  │ (3 concepts) │                         │  │
│ │  └──────────────┘  └──────────────┘                         │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│ ─── PENDING QUESTIONS (3) ─────────────────────────────────────  │
│                                                                   │
│ ❓ Why does the pipeline use 11 stages?        [Answer] [Dismiss] │
│ ❓ What makes orchestrator.py architecturally   [Answer] [Dismiss] │
│    critical vs. other large files?                                 │
│ ❓ Why is the watcher separate from the         [Answer] [Dismiss] │
│    pipeline scheduler?                                             │
│                                                                   │
│ ─── COVERAGE ───────────────────────────────────────────────────  │
│ █████████████░░░░░░ 68% of modules have concept coverage          │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

*Next: [04_UI_Design.md](./04_UI_Design.md) — Detailed UI design for the Concepts panel*
