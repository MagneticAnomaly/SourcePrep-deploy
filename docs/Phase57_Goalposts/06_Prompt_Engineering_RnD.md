# Phase 57: Goalposts Prompt Engineering & Tooling Strategy — Deep R&D

> This document contains the findings from deep research into prompt design patterns, available data signals, 
> and tooling augmentation strategies for the Goalposts feature.

---

## 1. Prompt Pattern Inventory: Existing CoDRAG Pipeline

### 1a. Epistemic Enrichment (per-file, Stage 6a)
- **System persona**: "expert software architect performing deep analysis"
- **Output**: Structured JSON with 8 fields (extended_summary, domain_tags, architecture_layer, subsystem, design_patterns, cross_references, tech_debt, epistemic_confidence)
- **Context assembly**: Pass 1 summary + neighbor context (already-enriched neighbors) + source excerpt
- **Ordering**: Reverse topological (leaves first → dependents get enriched neighbor context)
- **Key insight for Goalposts**: tech_debt and staleness_risk per-file are valuable planning signals

### 1b. Group Reasoning (cross-file, Stage 6b)
- **System persona**: "expert software architect performing deep cross-file analysis"
- **Output**: JSON with 6 fields (pattern, data_flow, coupling_risks, blast_radius, architectural_insight, confidence)
- **Context assembly**: member epistemic summaries + internal edges
- **Uses deep reasoning** (think=True): the only pipeline stage that explicitly enables reasoning tokens
- **Key insight for Goalposts**: coupling_risks and architectural_insight are exactly what forward planning needs

### 1c. Atlas Generation (whole-repo, Stage 8)
- **System persona**: "senior software architect writing a codebase orientation document"  
- **Output**: Plain text prose with labeled sections (IDENTITY, STACK, ARCHITECTURE, SUBSYSTEMS, MODULE_DEPENDENCIES, FLOW, API SURFACE, DATA MODELS, PATTERNS, RISKS)
- **Budget scaling**: Character targets scale with file count and available VRAM
- **3 modes**: Single-doc, segmented root, per-segment
- **Key insight for Goalposts**: The Atlas RISKS section + MODULE DEPENDENCIES are the most planning-relevant sections

### 1d. Audit Synthesis (report generation, Stage 9)
- **System persona**: "senior software architect conducting a codebase health audit"
- **Output**: 5 Markdown reports (Summary with A–F grade, Architecture Analysis, Gap Analysis, Component Inventory, Tech Debt Roadmap)
- **Context assembly**: Findings + Atlas + module data + hub files + circular deps
- **Key insight for Goalposts**: The Gap Analysis format (GAP-N items with severity/effort/priority) is the closest existing pattern to what Goalposts needs

---

## 2. Available Data Signals (Current Goalposts vs. Full Potential)

### What our current prompt uses (V1):
| Signal | Source | Size |
|--------|--------|------|
| Atlas content | `atlas.json` | ~1.5K chars |
| Audit findings | `audit/findings.json` | Top 15 findings, ~3K chars |
| Product intent | User input | ~500 chars |

### What we're leaving on the table:

| Signal | Source | Size | Planning Value |
|--------|--------|------|----------------|
| **Module summaries** | `trace_modules.jsonl` | ~678K total | **HIGH** — domain_tags, dependencies, tech_debt_summary, data_flow per module |
| **Group reasoning** | `trace_group_reasoning.jsonl` | ~150K total | **HIGH** — coupling_risks, blast_radius, architectural_insight |
| **Epistemic entries** | `trace_epistemic.jsonl` | ~1.8M total | **MEDIUM** — staleness_risk, epistemic_confidence per file |
| **Audit reports** | `audit/*.md` | 5 reports | **HIGH** — Gap Analysis already has prioritized GAP-N items |
| **Segment atlases** | `atlas_segments/` | 9 segments | **MEDIUM** — subsystem-level depth for targeted proposals |
| **Spaghetti scores** | `audit/spaghetti.json` | File scores | **HIGH** — quantified complexity hotspots |

---

## 3. Industry Best Practices Applied

### 3a. CSIO Framework (Context/Scope/Intent/Output)
- **Context**: Currently "Staff Engineer and product strategist" — should be **3 distinct perspectives** (see Multi-Perspective below)
- **Scope**: Should be explicit about planning horizon (next 1-3 milestones, not roadmap for a year)
- **Intent**: Good — already have product intent. Should add structured intent categories
- **Output**: Good JSON schema — should add cross-references and dependency ordering

### 3b. Multi-Perspective Analysis (KEY FINDING)
Industry research strongly suggests that planning prompts produce better results when they ask the LLM to approach from **multiple viewpoints simultaneously**, rather than a single "staff engineer" persona:

| Perspective | Focus Area | What It Catches |
|-------------|------------|-----------------|
| **Architect** | System design, boundaries, coupling | Structural bottlenecks, missing abstractions |
| **Product Designer** | User value, feature completeness | Feature gaps, UX improvements |
| **Tech Lead** | Implementability, team velocity | Effort estimates, dependency ordering |
| **SRE / Ops** | Reliability, observability, security | Missing error handling, monitoring gaps |

### 3c. Chain-of-Thought Reasoning
Group Reasoning already uses `think=True` with excellent results. Goalposts should use the same approach — the planning task benefits enormously from reasoning about relationships between signals, not just pattern-matching individual findings.

### 3d. Scaffolded Output Sections
Atlas prompts mandate specific sections (IDENTITY, STACK, etc.) which forces comprehensive analysis. The Goalposts prompt should similarly scaffold its reasoning:
1. **SITUATION**: What does this codebase do today? (from Atlas)
2. **GAPS**: What's missing or broken? (from Audit + Group Reasoning)
3. **DIRECTION**: Where does the user want to go? (from Intent)
4. **PROPOSALS**: What milestones bridge the gap? (synthesis)
5. **UNKNOWNS**: What design questions remain? (epistemic uncertainty)

---

## 4. Proposed Prompt Redesign (V2)

### 4a. New System Prompt

```
You are a design thinking partner for a software project. You will analyze the codebase from 
four perspectives — architect, product designer, tech lead, and SRE — to propose concrete 
milestones that move the project closer to its stated goals.

Rules:
1. Every proposal must reference specific modules, files, or components from the data.
2. Think step-by-step: first assess the current state, then identify gaps, then propose actions.
3. Distinguish between ideas that improve what exists vs. ideas that add new capability.
4. Order proposals by compound impact: which milestone unlocks the most downstream value?
5. Produce valid JSON only.
```

### 4b. New Context Assembly (V2)

```
# CODEBASE IDENTITY (Atlas)
{atlas_content}

# MODULE LANDSCAPE
Top modules by file count and their health status:
{module_summaries}  <!-- NEW: top 10-15 modules with domain_tags, component_status, tech_debt_summary -->

# COUPLING HOTSPOTS
{coupling_hotspots}  <!-- NEW: from group reasoning — highest coupling_risks -->

# COMPLEXITY HOTSPOTS  
{spaghetti_summary}  <!-- NEW: from spaghetti.json — worst file scores -->

# TECHNICAL DEBT & GAPS
{tech_debt_summary}  <!-- ENHANCED: include gap analysis items, not just raw findings -->

# User Intent
{product_intent}

# Previous Decisions
{approved_and_dismissed}
{answered_questions}
```

### 4c. New Output Schema (V2)

```json
{
  "situation_assessment": "2-3 sentences: what this codebase is and its current maturity level",
  "proposals": [
    {
      "title": "Concise milestone name",
      "rationale": "Why this matters NOW — cite specific modules/findings",
      "category": "architecture | security | feature | tech_debt | research | reliability",
      "perspective": "architect | designer | tech_lead | sre",
      "priority": "P0 | P1 | P2 | P3",
      "unlocks": ["Titles of other proposals this enables"],
      "tasks": [
        {
          "description": "Concrete action",
          "file_paths": ["affected files from Atlas/modules"],
          "effort": "small | medium | large"
        }
      ]
    }
  ],
  "questions": [
    {
      "question": "...",
      "context": "What ambiguity was detected and from which signal",
      "category": "...",
      "informs": ["Titles of proposals that depend on this answer"]
    }
  ]
}
```

**New fields:**
- `situation_assessment`: Forces the model to summarize its understanding before proposing
- `perspective`: Labels which viewpoint generated each proposal (architect/designer/tech_lead/sre)
- `unlocks`: Creates a dependency graph between proposals for sequencing
- `informs`: Links questions to the proposals that depend on their answers

---

## 5. Tooling Augmentation Strategies

### 5a. Enrich the Audit Pipeline for Planning Signals

**Problem**: The current audit analyzers focus on *code quality* — they don't produce *planning signals*.

**Strategy**: Add a `planning_signals` analyzer to the audit pipeline that extracts:

| Signal | Source | Value for Planning |
|--------|--------|--------------------|
| Feature completeness heatmap | Module domain_tags vs. Atlas subsystems | Shows under-served areas |
| Coupling risk ranking | Group reasoning coupling_risks | Shows fragility hotspots |
| Staleness distribution | Epistemic staleness_risk | Shows neglected areas |
| API surface gaps | Atlas API SURFACE section | Shows missing endpoints |
| Test coverage gaps | Module data + testing annotations | Shows reliability risks |

This analyzer would NOT run during normal audit — it would run as a **pre-step of Goalposts generation**, producing a compact `goalposts_signals.json` that the planner consumes.

### 5b. Module Health Scoring

**Problem**: Modules have `component_status` but it's a simple string ("active", "stable"). We need a numeric health score for ranking.

**Strategy**: Compute a per-module health score from:
- Epistemic confidence (avg across member files)
- Tech debt count
- Coupling risk count (from group reasoning)
- Spaghetti score (avg file complexity)
- Staleness risk distribution

This becomes a single 0-100 score per module that Goalposts can sort by: "propose milestones for the least healthy modules first."

### 5c. Intent-Aware Atlas Generation

**Problem**: The Atlas describes *what the codebase IS*, not *what it could become*. When a user sets a product intent, the Atlas has no knowledge of where the project is going.

**Strategy (Future)**: Add an optional "target architecture" field to the Atlas prompt that includes the product intent. This would make the Atlas's RISKS section more targeted — e.g., if the intent says "add multi-tenant support", the Atlas would specifically flag files that assume single-tenancy.

> [!IMPORTANT]
> This is a **future enhancement** — it requires changes to the Atlas generator and should only be done after Goalposts V1 proves the concept.

### 5d. Spaghetti-Informed Task Ranking

**Problem**: Our V1 tasks have `effort: small|medium|large` but no quantitative backing.

**Strategy**: Use spaghetti file scores to auto-estimate effort:
- Files with `score > 70`: Large effort (high coupling + complexity)
- Files with `score 40-70`: Medium effort
- Files with `score < 40`: Small effort

The planner can include this data in context so the LLM's effort estimates are grounded in actual complexity metrics rather than guessing.

### 5e. Cross-Session Memory via `codrag_observe`

**Strategy**: After each generation pass, save key observations:
- Which proposals were approved (user's design preferences)
- Which were dismissed (things the user doesn't value)
- Q&A pairs (design decisions made)

This creates a persistent design-decision log that future sessions can reference — the AI remembers what the user cares about.

---

## 6. Implementation Priority

| Enhancement | Effort | Impact | When |
|-------------|--------|--------|------|
| Add module summaries to prompt context | Small | High | **V2 (next)** |
| Add coupling hotspots from group reasoning | Small | High | **V2 (next)** |
| Add spaghetti scores to prompt context | Small | Medium | **V2 (next)** |
| Multi-perspective system prompt | Small | High | **V2 (next)** |
| `unlocks` dependency field in output | Small | Medium | **V2 (next)** |
| `situation_assessment` preamble | Small | Medium | **V2 (next)** |
| Planning signals pre-analyzer | Medium | High | V3 |
| Module health scoring | Medium | Medium | V3 |
| Spaghetti-informed effort estimates | Small | Medium | V3 |
| Intent-aware Atlas generation | Large | High | V4+ |
| Cross-session memory integration | Medium | Medium | V4+ |

---

## 7. Recommendations

1. **Immediate (V2 prompt redesign)**: Enrich the prompt with module summaries + group reasoning coupling risks + spaghetti scores. Switch to multi-perspective system prompt. Add `situation_assessment`, `perspective`, and `unlocks` fields. Estimated: 2-3 hours of planner.py changes.

2. **Short-term (V3 tooling)**: Build the `planning_signals` pre-analyzer as a lightweight module that runs before Goalposts generation. Add module health scoring. Estimated: half-day.

3. **Medium-term (V4 integration)**: Intent-aware Atlas, cross-session memory. These are genuine product differentiators but require broader architectural changes.

4. **Dashboard UX**: The V2 `perspective` field enables a powerful UI affordance — filter/group proposals by viewpoint (architect vs. designer vs. SRE). The `unlocks` field enables a dependency graph visualization.
