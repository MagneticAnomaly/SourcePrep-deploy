# Phase 64 — Role Composition Engine: Weighted Domain Blending for Ambiguous Roles

> **Research Document 2 of N** | Phase 64: Resolving Role Ambiguity
> Date: 2026-03-30
> Extends: [01_README.md](./README.md) (Sub-Atlas Architecture)

---

## 1. The Problem: Discrete Roles vs. Continuous Reality

The initial architecture (Doc 01) proposed hardcoded `RoleProjection` definitions:

```python
"engineering": RoleProjection(include_layers=["api", "service", ...])
"design":      RoleProjection(include_layers=["presentation", "component", ...])
```

This breaks for real-world roles because:

| Input Role | Problem |
|---|---|
| **"CEO"** | Needs everything at a glance — but HOW MUCH of everything? |
| **"Design Engineer"** | Split between engineering (60%) and design (40%) — but which 60%? |
| **"DevSecOps"** | Three domains blended: DevOps + Security + some Engineering |
| **"Full Stack Developer"** | All layers matter, but presentation and business_logic more than infrastructure |
| **"CTO"** | Like CEO but deeper on architecture, shallower on product |
| **"QA Lead"** | QA-heavy but also needs to understand API surface for test design |
| **"Technical Writer"** | Documentation + product + enough engineering to be accurate |
| **"Intern"** | Needs MORE context than a senior engineer, not less |

**The fundamental insight: A role is not a category. A role is a vector of weights across CoDRAG's existing epistemic dimensions.**

---

## 2. What CoDRAG Already Knows Per File

This is the critical realization. CoDRAG's epistemic enrichment pipeline already classifies every file along multiple dimensions that map directly to role relevance:

### 2.1 Architecture Layers (9 values, per-file)

From `VALID_ARCHITECTURE_LAYERS` in `epistemic_enrichment.py`:

```
presentation | business_logic | data | infrastructure | 
configuration | testing | documentation | build | unknown
```

Every file has exactly one `architecture_layer`. This is already indexed.

### 2.2 Domain Tags (1-4 free-form tags, per-file)

From the epistemic enrichment prompt:

```
domain_tags: 1-4 descriptive tags (e.g. "monetization", "auth", "ui", "data-persistence")
```

These are free-form strings produced by the LLM during Pass 2 enrichment. They appear on every `EpistemicEntry` and propagate up through clustering to `ModuleEntry.domain_tags` and `Segment.domain_tags`.

### 2.3 Epistemic Confidence (0.0-1.0, per-file)

From `epistemic_score.py` — a 6-component weighted composite:

```
SCORE_WEIGHTS = {
    "summary_confidence": 0.20,
    "validation_status":  0.15,
    "neighbor_coverage":  0.20,
    "cross_reference_density": 0.15,
    "enrichment_depth":   0.15,
    "staleness_check":    0.15,
}
```

### 2.4 Module Membership (per-file)

From `cluster.py` — every file belongs to exactly one `ModuleEntry`, which has:
- `domain_tags` (aggregated from member files)
- `architecture_layers` (aggregated from member files)
- `summary` (LLM-synthesized subsystem description)
- `component_status` (complete, partial, stubbed, deprecated)
- `avg_epistemic_confidence` (mean of member file confidences)

### 2.5 Graph Centrality (per-file)

From `routing.py` — files have `in_degree` counts from trace edges, used to identify hub files.

---

## 3. The Insight: Roles as Weight Vectors Over Existing Dimensions

Instead of hardcoding "a CEO sees these files", we define a role as a **weight vector** across CoDRAG's existing classification dimensions:

```
RoleVector = {
    # Architecture layer weights (how relevant each layer is to this role)
    "layer_weights": {
        "presentation":    0.0 - 1.0,
        "business_logic":  0.0 - 1.0,
        "data":            0.0 - 1.0,
        "infrastructure":  0.0 - 1.0,
        "configuration":   0.0 - 1.0,
        "testing":         0.0 - 1.0,
        "documentation":   0.0 - 1.0,
        "build":           0.0 - 1.0,
    },
    
    # Domain affinity keywords (fuzzy match against domain_tags)
    "domain_affinity": ["keyword1", "keyword2", ...],
    
    # Graph centrality preference (how much to prefer hub files)
    "centrality_weight": 0.0 - 1.0,
    
    # Detail level (0.0 = summary only, 1.0 = max detail)
    "detail_level": 0.0 - 1.0,
    
    # Total context budget (chars)
    "max_chars": int,
}
```

### 3.1 Example: CEO RoleVector

```python
CEO = RoleVector(
    layer_weights={
        "presentation":    0.3,   # Knows it exists, not details
        "business_logic":  0.7,   # Core value prop lives here
        "data":            0.4,   # Data architecture matters strategically
        "infrastructure":  0.2,   # Cloud costs, scaling concerns
        "configuration":   0.1,   # Don't need to know config format
        "testing":         0.2,   # Test coverage as quality signal
        "documentation":   0.8,   # Phase docs, research, decisions
        "build":           0.1,   # Build system is ops detail
    },
    domain_affinity=["architecture", "strategy", "api", "integration",
                     "security", "monetization", "user-facing"],
    centrality_weight=0.9,      # CEOs care about the most-connected things
    detail_level=0.3,           # High-level summaries, not code details
    max_chars=2000,             # Tight budget — executives scan, not read
)
```

**What this produces for a CEO:**
- High-hub-file emphasis (they see the most important files)
- Module-level summaries instead of file-level details
- Documentation/research phases are prominent (strategic context)
- Business logic modules emphasized (what the product does)
- Testing mentioned as coverage metrics, not test code
- Infrastructure mentioned as scaling/cost, not config details

### 3.2 Example: Design Engineer RoleVector

```python
DESIGN_ENGINEER = RoleVector(
    layer_weights={
        "presentation":    0.9,   # Primary domain — UI, components
        "business_logic":  0.6,   # Needs to understand data flow to UI
        "data":            0.3,   # Data models that render in UI
        "infrastructure":  0.1,   # Not relevant
        "configuration":   0.2,   # Design tokens, theme config
        "testing":         0.4,   # Component tests, visual regression
        "documentation":   0.5,   # Design docs, Storybook
        "build":           0.2,   # Storybook build config
    },
    domain_affinity=["ui", "component", "design-system", "layout", "theme",
                     "styling", "animation", "responsive", "a11y",
                     "api", "state-management"],  # Also needs API context
    centrality_weight=0.5,      # Components and API endpoints
    detail_level=0.7,           # Needs to see component APIs in detail
    max_chars=3000,             # More budget (they do actual work)
)
```

**What this produces:**
- Presentation layer at full detail (component APIs, props, patterns)
- Business logic at medium detail (data flow relevant to UI)
- API surface highlighted (design engineer needs to know data shapes)
- Design system documentation prominent
- Infrastructure/build suppressed

### 3.3 Example: DevSecOps (Three-Way Blend)

```python
DEVSECOPS = RoleVector(
    layer_weights={
        "presentation":    0.1,
        "business_logic":  0.3,   # Understands what's being secured
        "data":            0.5,   # Data handling = security surface
        "infrastructure":  0.9,   # Primary domain
        "configuration":   0.8,   # Config is security-critical
        "testing":         0.5,   # Security tests
        "documentation":   0.4,   # Deployment docs
        "build":           0.8,   # CI/CD, Docker, deploy pipelines
    },
    domain_affinity=["security", "auth", "infrastructure", "deploy",
                     "ci-cd", "docker", "monitoring", "encryption",
                     "token", "permission", "build", "pipeline"],
    centrality_weight=0.6,
    detail_level=0.7,
    max_chars=2500,
)
```

---

## 4. The Scoring Algorithm

Given a `RoleVector` and CoDRAG's indexed data, compute a **relevance score** for every file, then assemble the sub-atlas from the highest-scored files.

### 4.1 Per-File Relevance Score

```python
def compute_role_relevance(
    file_path: str,
    epistemic: EpistemicEntry,
    in_degree: int,
    total_files: int,
    role: RoleVector,
) -> float:
    """Compute how relevant a file is to a given role (0.0-1.0)."""
    
    # Component 1: Architecture Layer Match (weight: 0.30)
    layer = epistemic.architecture_layer
    layer_score = role.layer_weights.get(layer, 0.0)
    
    # Component 2: Domain Tag Affinity (weight: 0.35)
    # Fuzzy match file's domain_tags against role's affinity keywords
    tag_score = max_tag_affinity(epistemic.domain_tags, role.domain_affinity)
    
    # Component 3: Graph Centrality (weight: 0.20)
    # Normalize in_degree to 0-1 range, then apply role's centrality preference
    max_degree = ...  # from graph_stats
    norm_centrality = min(1.0, in_degree / max(1, max_degree * 0.3))
    centrality_score = norm_centrality * role.centrality_weight
    
    # Component 4: Epistemic Confidence (weight: 0.15)
    # Prefer well-understood files (high confidence = more useful context)
    confidence_score = epistemic.epistemic_confidence
    
    # Weighted composite
    relevance = (
        0.30 * layer_score +
        0.35 * tag_score +
        0.20 * centrality_score +
        0.15 * confidence_score
    )
    
    return relevance
```

### 4.2 Domain Tag Affinity (Fuzzy Matching)

CoDRAG's domain tags are free-form strings. A role's `domain_affinity` keywords need fuzzy matching:

```python
def max_tag_affinity(file_tags: List[str], affinity_keywords: List[str]) -> float:
    """Compute max fuzzy affinity between a file's tags and a role's keywords.
    
    Uses three strategies:
    1. Exact match (score: 1.0)
    2. Substring match (score: 0.7)  - "auth" matches "authentication"
    3. Semantic proximity (score: 0.5) - "ui" matches "presentation"
    
    Returns the best match score across all tag × keyword pairs.
    """
    if not file_tags or not affinity_keywords:
        return 0.0
    
    best = 0.0
    for tag in file_tags:
        tag_lower = tag.lower().replace("-", " ").replace("_", " ")
        for keyword in affinity_keywords:
            kw_lower = keyword.lower().replace("-", " ").replace("_", " ")
            
            # Exact match
            if tag_lower == kw_lower:
                return 1.0
            
            # Substring (either direction)
            if kw_lower in tag_lower or tag_lower in kw_lower:
                best = max(best, 0.7)
                continue
            
            # Semantic synonyms (predefined map)
            if are_synonyms(tag_lower, kw_lower):
                best = max(best, 0.5)
    
    return best

# Synonym clusters for fuzzy tag matching
SYNONYM_CLUSTERS = [
    {"ui", "presentation", "frontend", "component", "view", "layout"},
    {"api", "endpoint", "route", "handler", "controller", "rest"},
    {"auth", "authentication", "authorization", "permission", "security", "token"},
    {"data", "database", "persistence", "storage", "model", "schema", "orm"},
    {"deploy", "infrastructure", "devops", "ci-cd", "docker", "kubernetes"},
    {"test", "testing", "spec", "qa", "quality", "coverage"},
    {"build", "compile", "bundle", "webpack", "vite", "toolchain"},
    {"docs", "documentation", "readme", "guide", "reference"},
    {"state", "state-management", "store", "context", "redux"},
    {"style", "css", "theme", "design-system", "design-token", "styling"},
]
```

### 4.3 Assembly: Budget-Aware Context Generation

```python
def assemble_role_atlas(
    role: RoleVector,
    all_files: Dict[str, EpistemicEntry],
    modules: List[ModuleEntry],
    graph_stats: Dict,
    in_degrees: Dict[str, int],
) -> str:
    """Assemble a role-appropriate sub-atlas within budget."""
    
    # Step 1: Score every file
    scored_files = []
    for fp, entry in all_files.items():
        score = compute_role_relevance(
            fp, entry, in_degrees.get(fp, 0),
            len(all_files), role
        )
        scored_files.append((fp, entry, score))
    
    # Step 2: Sort by relevance (descending)
    scored_files.sort(key=lambda x: -x[2])
    
    # Step 3: Apply detail_level to determine granularity
    if role.detail_level < 0.3:
        # Executive mode: module summaries only
        return _assemble_module_level(modules, role, scored_files)
    elif role.detail_level < 0.7:
        # Manager mode: module summaries + top file highlights
        return _assemble_mixed_level(modules, role, scored_files)
    else:
        # Practitioner mode: file-level detail for relevant files
        return _assemble_file_level(role, scored_files)
    
    # Step 4: Truncate to budget
    # ... (LOD-style progressive compression)
```

---

## 5. Detail Levels: LOD for Roles

The `detail_level` parameter creates three tiers of context assembly, inspired by CoDRAG's existing Level of Detail compression:

### 5.1 Executive Level (detail_level < 0.3)

**Who:** CEO, VP, Board Member, Advisor

**What they see:**
```
IDENTITY: CoDRAG is a local-first AI coding assistant with structural 
code intelligence.

MODULES (5 subsystems, 1143 files):
• Core Engine (249py): Pipeline orchestration, epistemic enrichment, 
  atlas generation. Status: complete.
• UI Library (230 files): Storybook design system, dashboard primitives. 
  Status: partial.
• Dashboard (37tsx): React hooks, state management. Status: partial.
• VS Code Extension (20ts): Daemon integration, embeddings. Status: partial.
• Webview UI (14tsx): Code navigation. Status: stubbed.

HEALTH: 23 opportunities found. 3 P0 (architecture), 8 P1 (quality).
```

**Budget:** ~800-1500 chars. Module-level only. No file paths. No code.

### 5.2 Manager Level (detail_level 0.3-0.7)

**Who:** Tech Lead, Engineering Manager, Product Manager, Architect

**What they see:**
```
IDENTITY: [same as executive]

ARCHITECTURE: Hexagonal core with 11-stage pipeline. State machines 
manage model lifecycle (ModelAwareness) and pipeline flow (orchestrator).
Hub files: index.ts (3294 edges), HeroSection.tsx (957 edges).

MODULES with key files:
• Core Engine:
  - orchestrator.py: 11-stage pipeline controller
  - atlas/generator.py: Codebase map generation (3 tiers)
  - llm_client.py: Universal multi-provider LLM interface
  Status: complete. Tech debt: 113 import cycles.

• UI Library:
  - components/search/: LOD search results with trace expansion
  - types/index.ts: Shared type definitions (hub, 3294 edges)

RISKS: 113 import cycles. ModelAwareness VRAM estimation is heuristic-only.
```

**Budget:** ~2000-3000 chars. Module summaries + key file highlights.

### 5.3 Practitioner Level (detail_level > 0.7)

**Who:** Software Engineer, Design Engineer, DevOps Engineer, Security Engineer

**What they see:**
```
IDENTITY: [same]
STACK: TypeScript, React, Python, Rust, Tauri.

ARCHITECTURE: [role-filtered detail]
Module dependencies specific to their work area.
File-level descriptions for high-relevance files.
API surfaces relevant to their domain.
Design patterns within their scope.
Tech debt affecting their area.
```

**Budget:** ~2500-4000 chars. File-level detail for relevant files. Module-level for peripherally relevant areas.

---

## 6. Handling Ambiguity: The Resolver

The hardest problem isn't the scoring — it's mapping an arbitrary role string to a `RoleVector`. Three strategies, in priority order:

### 6.1 Strategy A: Exact Match → Built-In Roles

```python
BUILT_IN_ROLES = {
    "ceo": CEO_VECTOR,
    "cto": CTO_VECTOR,
    "engineer": ENGINEER_VECTOR,
    "design engineer": DESIGN_ENGINEER_VECTOR,
    "security engineer": SECURITY_VECTOR,
    # ... 15-20 common roles
}

# Try exact match first
if role_string.lower() in BUILT_IN_ROLES:
    return BUILT_IN_ROLES[role_string.lower()]
```

### 6.2 Strategy B: Keyword Decomposition → Vector Blending

For compound roles, decompose into base roles and blend:

```python
def resolve_compound_role(role_string: str) -> RoleVector:
    """Resolve 'Design Engineer' → blend(design=0.4, engineer=0.6)"""
    
    # Keyword → base role mapping
    KEYWORD_TO_BASE = {
        "design": "design",
        "ux": "design",
        "ui": "design",
        "engineer": "engineering",
        "developer": "engineering",
        "dev": "engineering",
        "security": "security",
        "sec": "security",
        "ops": "devops",
        "devops": "devops",
        "infra": "devops",
        "qa": "qa",
        "test": "qa",
        "quality": "qa",
        "product": "product",
        "pm": "product",
        "lead": "lead",      # modifier: +centrality_weight
        "senior": "senior",  # modifier: -detail_level
        "junior": "junior",  # modifier: +detail_level
        "intern": "intern",  # modifier: +detail_level, +documentation
        "exec": "executive",
        "vp": "executive",
        "chief": "executive",
        "head": "executive",
        "architect": "architect",
        "writer": "writer",
        "docs": "writer",
        "data": "data",
        "ml": "data",
        "ai": "data",
    }
    
    # Tokenize input
    tokens = role_string.lower().replace("-", " ").replace("_", " ").split()
    
    # Map tokens to base roles
    base_roles = []
    modifiers = []
    for token in tokens:
        base = KEYWORD_TO_BASE.get(token)
        if base in ("lead", "senior", "junior", "intern"):
            modifiers.append(base)
        elif base:
            base_roles.append(base)
    
    if not base_roles:
        return BUILT_IN_ROLES.get("engineering", DEFAULT_VECTOR)
    
    if len(base_roles) == 1:
        vector = BUILT_IN_ROLES[base_roles[0]]
    else:
        # Blend multiple base roles
        vector = blend_vectors(
            [(BUILT_IN_ROLES[r], 1.0 / len(base_roles)) for r in base_roles]
        )
    
    # Apply modifiers
    for mod in modifiers:
        vector = apply_modifier(vector, mod)
    
    return vector
```

### 6.3 Strategy C: LLM-Resolved Vectors (Future, Optional)

For truly novel roles, use the LLM to generate a weight vector:

```python
def llm_resolve_role(role_string: str, codebase_summary: str) -> RoleVector:
    """Ask the LLM to generate layer weights for an unknown role."""
    prompt = f"""Given a codebase with these architecture layers:
    presentation, business_logic, data, infrastructure, configuration, 
    testing, documentation, build
    
    And this codebase summary:
    {codebase_summary}
    
    A person with the role "{role_string}" needs a context briefing.
    
    Rate each architecture layer's relevance to this role (0.0-1.0):
    {{"presentation": 0.X, "business_logic": 0.X, ...}}
    Also provide:
    - detail_level (0.0 = summary, 1.0 = code-level): float
    - domain_keywords: list of 5-10 keywords this role cares about
    - centrality_preference (0.0 = niche files, 1.0 = hub files): float
    """
    # ... parse response into RoleVector
```

This is expensive (1 LLM call per novel role) but cacheable per project. Only used when Strategies A and B both fail.

---

## 7. The Blending Algorithm

The core mathematical operation for compound roles:

```python
def blend_vectors(
    weighted_roles: List[Tuple[RoleVector, float]],
) -> RoleVector:
    """Blend multiple RoleVectors with weights that sum to 1.0.
    
    Example: Design Engineer = blend([
        (DESIGN_VECTOR, 0.4),
        (ENGINEER_VECTOR, 0.6),
    ])
    """
    # Normalize weights
    total = sum(w for _, w in weighted_roles)
    normalized = [(v, w / total) for v, w in weighted_roles]
    
    # Blend layer weights (weighted average)
    blended_layers = {}
    for layer in VALID_ARCHITECTURE_LAYERS:
        blended_layers[layer] = sum(
            v.layer_weights.get(layer, 0.0) * w
            for v, w in normalized
        )
    
    # Union domain affinity keywords (deduplicated)
    all_keywords = []
    seen = set()
    for v, _ in normalized:
        for kw in v.domain_affinity:
            if kw not in seen:
                all_keywords.append(kw)
                seen.add(kw)
    
    # Blend scalar values (weighted average)
    centrality = sum(v.centrality_weight * w for v, w in normalized)
    detail = sum(v.detail_level * w for v, w in normalized)
    budget = int(sum(v.max_chars * w for v, w in normalized))
    
    return RoleVector(
        layer_weights=blended_layers,
        domain_affinity=all_keywords,
        centrality_weight=centrality,
        detail_level=detail,
        max_chars=budget,
    )
```

### 7.1 Modifier Application

```python
def apply_modifier(vector: RoleVector, modifier: str) -> RoleVector:
    """Apply a seniority/role modifier to a RoleVector."""
    v = copy(vector)
    
    if modifier == "senior":
        v.detail_level = max(0.0, v.detail_level - 0.15)  # Less hand-holding
        v.centrality_weight = min(1.0, v.centrality_weight + 0.1)  # More strategic
    
    elif modifier == "junior" or modifier == "intern":
        v.detail_level = min(1.0, v.detail_level + 0.2)  # More detail
        v.max_chars = int(v.max_chars * 1.3)  # Bigger context budget
        # Boost documentation weight (they need the docs)
        v.layer_weights["documentation"] = min(1.0, 
            v.layer_weights.get("documentation", 0.5) + 0.3)
    
    elif modifier == "lead":
        v.centrality_weight = min(1.0, v.centrality_weight + 0.2)
        v.detail_level = max(0.0, v.detail_level - 0.1)
        # Add testing visibility (leads care about quality)
        v.layer_weights["testing"] = min(1.0,
            v.layer_weights.get("testing", 0.3) + 0.2)
    
    return v
```

---

## 8. Worked Examples

### 8.1 CEO Viewing CoDRAG

**Input:** `role = "CEO"`
**Resolved:** Exact match → `CEO_VECTOR` (detail_level=0.3, centrality=0.9)

**Scoring top 5 files:**

| File | Layer | Tags | In-Degree | Layer Score | Tag Score | Central. | Conf. | **Total** |
|------|-------|------|-----------|-------------|-----------|----------|-------|-----------|
| `packages/ui/src/index.ts` | presentation | ui, export | 3294 | 0.3 | 0.5 | 0.9 | 0.8 | **0.59** |
| `src/codrag/cli.py` | infrastructure | cli, interface | 89 | 0.2 | 0.5 | 0.3 | 0.9 | **0.42** |
| `src/codrag/core/atlas/generator.py` | business_logic | atlas, intelligence | 45 | 0.7 | 0.7 | 0.2 | 0.85 | **0.56** |
| Phase 62 strategic docs | documentation | strategy, architecture | 12 | 0.8 | 1.0 | 0.1 | 0.7 | **0.69** |
| `src/codrag/core/audit/` | business_logic | quality, health | 34 | 0.7 | 0.5 | 0.15 | 0.8 | **0.51** |

**Result:** Strategy docs + atlas generator + audit system surface as most relevant. Exactly what a CEO needs.

**Detail level 0.3 → Module-level output:**
```
IDENTITY: CoDRAG is a local-first codebase intelligence engine with 
MCP integration, VS Code extension, and React dashboard.

MODULES (5 active):
• Core Engine (249 files): Structural code analysis, 11-stage 
  pipeline, semantic search with LOD compression.
• UI Library (230 files): Storybook design system. Status: partial.
• Dashboard (37 files): React monitoring interface.
• VS Code Ext (20 files): IDE integration via daemon.
• Webview UI (14 files): In-editor code navigation. Status: stubbed.

STRATEGY: Strategic pivot to Knowledge Provider model (Phase 62).
Sunsetting PM features, focusing on universal export (JSON, SARIF, CSV).

HEALTH: 23 actionable opportunities. 3 critical (architecture).
```

~750 chars. A CEO can read this in 30 seconds and understand the product.

### 8.2 "Design Engineer" Viewing CoDRAG

**Input:** `role = "Design Engineer"`
**Resolved:** Compound decomposition → `blend(design=0.4, engineering=0.6)`

**Blended layer weights:**
```
presentation:    0.4 * 0.9 + 0.6 * 0.3 = 0.54
business_logic:  0.4 * 0.6 + 0.6 * 0.8 = 0.72
data:            0.4 * 0.3 + 0.6 * 0.5 = 0.42
infrastructure:  0.4 * 0.1 + 0.6 * 0.4 = 0.28
testing:         0.4 * 0.4 + 0.6 * 0.3 = 0.34
documentation:   0.4 * 0.5 + 0.6 * 0.3 = 0.38
...
```

**Blended detail_level:** `0.4 * 0.7 + 0.6 * 0.8 = 0.76` → Practitioner mode

**Result:** They see both UI component details AND business logic architecture, weighted toward engineering but with design context preserved. The design portion brings in Storybook docs, component APIs, and design tokens that a pure engineer wouldn't see.

### 8.3 "Intern" Viewing CoDRAG

**Input:** `role = "Intern"`
**Resolved:** Keyword match → `engineering` base + `intern` modifier

**Modifier effects:**
- `detail_level` bumped from 0.8 → **1.0** (maximum detail)
- `max_chars` bumped from 3000 → **3900** (30% more context)
- `documentation` layer weight bumped from 0.3 → **0.6** (they need to RTFM)

**Result:** An intern gets MORE context than a senior engineer — they see all the files a senior sees, plus documentation, readmes, and onboarding guides that a senior would know to skip. The system gives them training wheels.

---

## 9. Storage and Caching

### 9.1 Built-In Vectors Are Code Constants

The 15-20 built-in `RoleVector` definitions live in Python as constants. No disk I/O, no LLM calls.

### 9.2 Resolved Vectors Are Cached Per-Project

When Strategy B (keyword decomposition) or C (LLM resolution) produces a vector, cache it:

```
.codrag/role_cache.json
{
    "design_engineer": { "layer_weights": {...}, ... },
    "devsecops": { "layer_weights": {...}, ... },
    "ceo": null  // null = use built-in (no cache needed)
}
```

Cache key is the normalized role string. Invalidated when the project's atlas is regenerated (because domain tag vocabulary may change).

### 9.3 Sub-Atlas Results Are NOT Cached

Because they depend on the full atlas content (which changes), role sub-atlases are computed on-the-fly. But the computation is pure Python (no LLM, no disk I/O beyond loading the cached atlas) — ~5-10ms per projection.

---

## 10. How This Integrates with CoDRAG's Existing Infrastructure

### 10.1 Data Flow

```
Pipeline produces:
  trace_epistemic.jsonl  → per-file: architecture_layer, domain_tags, confidence
  trace_modules.jsonl    → per-module: domain_tags, architecture_layers, summary
  atlas.json             → full atlas content
  graph_stats            → in_degree counts per file

Role Composition Engine reads ALL of the above (already on disk)
  → Scores every file against the RoleVector
  → Assembles context at the appropriate detail_level
  → Returns a role-filtered sub-atlas string
```

### 10.2 What We Reuse (Zero New Pipeline Stages)

| Component | Reused How |
|---|---|
| `EpistemicEntry.architecture_layer` | Primary scoring dimension (Component 1) |
| `EpistemicEntry.domain_tags` | Tag affinity matching (Component 2) |
| `EpistemicEntry.epistemic_confidence` | Confidence weighting (Component 4) |
| `ModuleEntry.summary` | Executive-level context |
| `ModuleEntry.domain_tags` | Module-level affinity |
| `ModuleEntry.architecture_layers` | Module-level layer matching |
| In-degree from edges | Centrality scoring (Component 3) |
| `AtlasDocument.content` | Base content for filtering |
| `SegmentDescriptor.covers` | Segment-level matching (optional) |

### 10.3 New Code (All Python, No LLM)

| New | Purpose | Location |
|---|---|---|
| `RoleVector` dataclass | Role weight definition | `atlas/role_vectors.py` |
| `BUILT_IN_ROLES` | 15-20 preset vectors | `atlas/role_vectors.py` |
| `resolve_role()` | String → RoleVector resolver | `atlas/role_resolver.py` |
| `compute_role_relevance()` | Per-file scoring | `atlas/role_scoring.py` |
| `assemble_role_atlas()` | Budget-aware assembly | `atlas/role_assembly.py` |
| `SYNONYM_CLUSTERS` | Fuzzy tag matching | `atlas/role_vectors.py` |
| CLI `--role` flag | CLI access | `cli.py` |
| MCP `role` parameter | MCP access | `mcp/server.py` |

---

## 11. The Elegance: Why This Works

### 11.1 No New Data Collection

Every dimension used in scoring already exists in the CoDRAG pipeline. We're not adding a new enrichment pass. We're not asking the LLM to re-analyze anything. We're just re-weighting data we already have.

### 11.2 O(1) After First Computation

Once the scored file list is computed (O(n) where n = file count), selecting the top-K files and assembling context is O(k log k). For a 1000-file project, this is <10ms.

### 11.3 Naturally Composable

Because roles are vectors, they compose mathematically. "Senior Design Lead" = `blend(design=0.4, engineering=0.3, lead modifier) * senior modifier`. No special cases. No if/else trees.

### 11.4 The Knowledge Graph IS the Adapter

The user's question was: *"How can we build an adapter that took in the ambiguity of the roles and output strategic foundations?"*

The answer: **CoDRAG's existing epistemic graph IS the adapter.** The `architecture_layer` and `domain_tags` are the semantic backbone. The `RoleVector` is just a lens — a set of weights that selects which facets of the existing knowledge to reveal.

```
                  The Adapter Architecture
                  ═══════════════════════
                  
  "Design Engineer"        "CEO"          "DevSecOps"
        │                   │                  │
        ▼                   ▼                  ▼
  ┌──────────────────────────────────────────────────┐
  │            Role Resolver (Strategy A/B/C)          │
  │                                                     │
  │  "Design Engineer"                                  │
  │    → tokenize → ["design", "engineer"]              │
  │    → map → [design, engineering]                    │
  │    → blend → RoleVector{pres=0.54, biz=0.72, ...}  │
  └───────────────────────┬──────────────────────────────┘
                          │ RoleVector
                          ▼
  ┌──────────────────────────────────────────────────┐
  │            Role Scoring Engine                      │
  │                                                     │
  │  For each of CoDRAG's indexed files:               │
  │    score = weighted(                                 │
  │      layer_match,    ← EpistemicEntry.layer         │
  │      tag_affinity,   ← EpistemicEntry.domain_tags   │
  │      centrality,     ← graph in_degree              │
  │      confidence      ← EpistemicEntry.confidence    │
  │    )                                                 │
  └───────────────────────┬──────────────────────────────┘
                          │ Scored file list
                          ▼
  ┌──────────────────────────────────────────────────┐
  │            Role Assembly (LOD-Aware)                │
  │                                                     │
  │  detail_level < 0.3 → Module summaries              │
  │  detail_level 0.3-0.7 → Modules + key files        │
  │  detail_level > 0.7 → File-level detail             │
  │                                                     │
  │  Truncate to max_chars budget                       │
  └───────────────────────┬──────────────────────────────┘
                          │ Sub-Atlas (string)
                          ▼
  ┌──────────────────────────────────────────────────┐
  │        Protocol Stack (MCP / CLI / AGENTS.md)      │
  │                                                     │
  │  MCP:  codrag(role="design engineer")               │
  │  CLI:  codrag context --role "ceo"                  │
  │  File: AGENTS.md with embedded role-filtered atlas  │
  └──────────────────────────────────────────────────┘
```

---

## 12. Open Questions (Resolved from Doc 01)

### Q1 (from Doc 01): Should role projections combine with segment routing?

**Answer: Yes, naturally.** The `RoleVector` scoring already works at the file level. When segment routing is active, the role score simply provides an additional signal alongside the segment routing score. They multiply:

```python
final_score = segment_routing_score * role_relevance_score
```

A file that's in a top-matched segment AND has high role relevance appears first. A file in a matched segment but with low role relevance appears later. Orthogonal dimensions, multiplicative composition.

### Q2 (from Doc 01): Who defines roles — CoDRAG or the consuming tool?

**Answer: Three tiers.**
1. CoDRAG ships ~20 built-in vectors (code constants)
2. Users define custom roles via `role_projections.json` (flat config)
3. The consuming tool (Paperclip) passes arbitrary strings → resolved on-the-fly

### Q3 (from Doc 01): Should roles influence search scores?

**Answer: Phase 2, but the math is ready.** The `role_relevance_score` can be passed as a boost factor to `codrag_search`, just like `ROUTING_SEGMENT_BOOST`:

```python
ROLE_RELEVANCE_BOOST = 0.10  # additive boost for role-relevant files in search results
```

---

## 13. Implementation Estimate (Revised)

| Component | Effort | Dependencies |
|---|---|---|
| `RoleVector` dataclass + built-in roles | 1 day | None |
| `resolve_role()` (Strategy A + B) | 1 day | RoleVector |
| `compute_role_relevance()` scoring | 1 day | RoleVector + existing epistemic data |
| `assemble_role_atlas()` (3 detail levels) | 2 days | Scoring + existing atlas/modules |
| `--role` CLI + MCP parameter | 0.5 day | Assembly |
| `SYNONYM_CLUSTERS` fuzzy matching | 0.5 day | None |
| Role-filtered `rules_generator.py` | 0.5 day | Assembly |
| **Total Phase 64A** | **~7 days** | |
| LLM-resolved vectors (Strategy C) | 2-3 days (Phase 64B) | |

---

## 14. Decision Summary

| Question | Decision | Rationale |
|---|---|---|
| Are discrete role categories sufficient? | **No** — need continuous vectors | CEO, Design Engineer, Intern prove categories break |
| Can we leverage existing epistemic data? | **Yes** — architecture_layer + domain_tags + confidence + centrality | All already indexed per file |
| How do we resolve ambiguous role strings? | **Three strategies**: exact match → keyword decomposition → LLM fallback | Covers 99% of cases without LLM cost |
| How do compound roles work? | **Vector blending** with weighted averages | Mathematically clean, naturally composable |
| How do seniority modifiers work? | **Modifier functions** that adjust detail_level, centrality, and specific layer weights | "Senior" = less detail, more strategic; "Intern" = more detail, more docs |
| What's the runtime cost? | **<10ms** — pure Python scoring on cached data | No LLM calls for built-in or keyword-resolved roles |

---

*This document establishes the mathematical foundation for role-based context routing. The key insight is that CoDRAG's existing epistemic pipeline produces exactly the dimensional data needed — we're not building new intelligence, we're projecting existing intelligence through new lenses.*
