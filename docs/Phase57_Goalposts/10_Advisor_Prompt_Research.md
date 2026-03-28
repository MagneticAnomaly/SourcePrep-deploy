# Advisor Prompt & Predictive Design Research

## 1. Competitive Landscape — What Works

### CodeScene (strongest parallel)
- Uses **25-factor "Code Health" scoring** (1–10) to prioritize refactoring
- Correlates **change frequency x code quality** = "hotspots" — files that are both messy *and* heavily edited
- Key innovation: **business impact framing** — not "this file is messy" but "this file costs you 2x in maintenance"
- Generates AI-powered refactoring suggestions with quality gates
- **What we should steal**: Their hotspot concept maps perfectly to our spaghetti scores + fan-in/fan-out data

### SWE-agent (autonomous fixing)
- Princeton's open-source LLM agent that navigates codebases and fixes bugs autonomously
- Uses a custom **Agent-Computer Interface (ACI)** to view/edit/execute code
- **What's relevant**: Our Advisor shouldn't fix — it should *propose* and hand off to tools like SWE-agent or Claude

### Sourcegraph Cody
- Deep semantic code search across entire repos
- Context-aware suggestions using RAG over code graph
- **What's relevant**: Our Atlas + trace graph is a richer context source than what Cody has access to

> [!IMPORTANT]
> CoDRAG has a **unique advantage**: we own the dependency graph, module boundaries, epistemic confidence scores, and Atlas identity doc. No other tool has this combination. The prompt should exploit all of these signals.

---

## 2. Prompt Engineering Best Practices (2024-2025)

### Techniques we should apply

| Technique | What it does | How it helps Advisor |
|-----------|-------------|---------------------|
| **Chain-of-Thought (CoT)** | Forces step-by-step reasoning before conclusions | Prevents shallow proposals — LLM must *explain* why |
| **Few-shot examples** | Shows desired output format with exemplars | Gets consistent, high-quality proposal structures |
| **Role-based persona** | "You are a ___" primes expertise | Multi-role persona: architect + product strategist + market analyst |
| **Structured output** | JSON schema with constraints | Already have this; need to add more structured fields |
| **Self-consistency** | Generate multiple reasoning paths, pick consensus | Run 2-3 passes, merge unique proposals |
| **ReAct** | Interleave reasoning with tool use | Future: let advisor call codrag_search mid-generation |

### Current prompt gaps

The existing `GOALPOSTS_PROMPT` in `goalposts_planner.py` (43 lines) has:
- Single role: "Staff Engineer and product strategist"
- 5 context sections dumped as text (Atlas, tech debt, intent, approved, answered)
- Direct "produce JSON" instruction
- No reasoning framework or CoT scaffolding
- No opportunity categories beyond the technical
- No few-shot examples of excellent proposals
- No business impact framing

---

## 3. The Three-Lens Framework

The Advisor should analyze opportunities through **three distinct lenses**, not just technical debt:

### Lens 1: Architecture and Infra ("How is this built?")
- Module coupling / circular dependencies
- Missing abstraction layers
- Performance bottlenecks (files with high fan-in = contention points)
- Deployment architecture gaps

### Lens 2: Product and UX Patterns ("What should this do?")
- Feature gaps inferred from the codebase structure
- UX patterns that are half-implemented
- API surface inconsistencies
- Missing user-facing capabilities that the architecture supports but doesn't expose

### Lens 3: Market and Strategy ("Why does this matter?")
- Competitive positioning opportunities (what would make this a premium tool?)
- Integration opportunities (what popular tools/services could this connect to?)
- Adoption friction points (what's making this hard to use?)
- Monetization-ready features (what could differentiate paid vs free?)

> [!TIP]
> The key insight from CodeScene's success: **framing technical findings in business terms** dramatically increases adoption. Don't say "high coupling in auth module" — say "auth module coupling will slow your next 3 feature launches by ~40%".

---

## 4. Proposed Prompt Improvements

### A. Enhanced System Prompt

```
You are a senior technical advisor with three specializations:

1. **Software Architect**: You identify structural improvements,
   dependency issues, and infrastructure evolution opportunities.

2. **Product Strategist**: You spot feature gaps, UX improvement
   opportunities, and capabilities the code supports but doesn't
   expose to users.

3. **Market Analyst**: You identify competitive advantages,
   integration opportunities, and adoption friction points.

For each proposal, you MUST:
- Ground it in specific files and modules from the Atlas
- Explain the business impact (not just technical merit)
- Classify as: architecture, product, market, security, or research
- Estimate the effort-to-impact ratio
```

### B. Chain-of-Thought Scaffolding

```
## Analysis Framework

Before generating proposals, work through these steps:

### Step 1: Structural Assessment
Review the module structure and dependency graph.
Identify: hotspots (high coupling + high change), orphaned modules,
missing edges (components that should be connected but aren't).

### Step 2: Capability Gap Analysis
Compare what the codebase CAN do (based on its architecture)
versus what it DOES do (based on exposed APIs/features).
Look for: half-built features, unused infrastructure, over-engineered
components that suggest abandoned designs.

### Step 3: Competitive Positioning
Given the product intent, what would make this product stand out?
Look for: unique data the product has, underexploited capabilities,
integration points with popular ecosystems.

### Step 4: Priority Synthesis
Rank proposals by: (business_impact x feasibility) / effort.
P0 = high impact, clearly feasible, low effort
P3 = speculative, unclear impact, or large effort
```

### C. Few-Shot Example

Adding one high-quality example proposal in the prompt dramatically improves output consistency:

```json
{
  "title": "Extract Plugin System from Monolithic Analyzer",
  "rationale": "The analyzer module has 12 registered analysis types 
    hardcoded in a switch statement. Extracting to a plugin registry 
    would let users add custom analyzers AND reduce merge conflicts.",
  "category": "architecture",
  "priority": "P1",
  "business_impact": "Reduces feature-delivery time for new analyzers 
    from ~3 days to ~2 hours. Enables community contributions.",
  "tasks": [...]
}
```

### D. New Output Fields

| Field | Type | Purpose |
|-------|------|---------|
| `business_impact` | string | Why a non-technical stakeholder should care |
| `lens` | enum | architecture / product / market |
| `confidence` | float | 0.0-1.0 based on data quality |
| `related_findings` | string[] | IDs of health findings that support this |
| `ai_handoff_context` | string | Pre-written context for Claude/GPT to action this |

---

## 5. Data Signals We Already Have (Underutilized)

The existing CoDRAG graph contains rich signals that the current prompt barely uses:

| Signal | Source | Current Use | Potential |
|--------|--------|-------------|-----------|
| Module boundaries | Atlas | Passed as text | Could identify module-level opportunities |
| Fan-in/fan-out | Spaghetti scorer | Not passed | Identifies contention points + coupling |
| Epistemic confidence | Deep analysis | Not passed | Low confidence = poorly understood = risky |
| Circular deps | Audit | Not passed | Architectural breakdown indicators |
| Tech debt markers | Spaghetti scorer | As summary | Could itemize per-module patterns |
| Hub files | Graph analysis | Not passed | Central points for high-impact changes |
| Import chains | Trace graph | Not passed | Dependency architecture visibility |

> [!CAUTION]
> Adding all signals at once would exceed context limits. Strategy: **layered context injection** — start with Atlas + top-5 hotspots + top-3 circular deps, expand on subsequent passes.

---

## 6. Implementation Priorities

### Now (Prompt v2)
1. Add Chain-of-Thought scaffolding to system prompt
2. Add `business_impact` and `lens` fields to output schema
3. Pass top-5 spaghetti hotspot files as structured data (not just audit summary)
4. Add 1 few-shot example proposal
5. Rename categories to include `product` and `market`

### Next (Prompt v3)
1. Add `confidence` field based on epistemic data quality
2. Pass circular dependency chains
3. Pass hub files with connectivity metrics
4. Add `ai_handoff_context` field for seamless Claude/GPT handoff

### Future
1. Multi-pass generation (architecture then product then market)
2. Self-consistency: generate 3 sets and deduplicate
3. ReAct: let advisor call codrag_search mid-generation to verify assumptions
4. Differential proposals: compare current vs previous state to find *new* opportunities
