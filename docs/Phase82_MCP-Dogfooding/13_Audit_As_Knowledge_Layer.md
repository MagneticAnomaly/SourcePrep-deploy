# 13 — Audit as Knowledge Layer: CoDRAG's Role in the Audit Ecosystem

## The Insight

CoDRAG's audit tool (`codrag_audit`) currently tries to *be* an audit tool — it scans for large files, circular dependencies, naming issues, coupling problems. But the world already has excellent audit tools:

- **ruff** — Python linting and formatting (fast, comprehensive, growing)
- **mypy** — Python type checking
- **eslint / biome** — JavaScript/TypeScript linting
- **sonarqube / semgrep** — Security and quality analysis
- **clippy** — Rust linting
- **CodeScene** — Behavioral/git-based analysis
- **SARIF-producing tools** — Any tool that outputs Static Analysis Results Interchange Format

CoDRAG competing with these on their core competency is a losing game. They have years of rule development, massive communities, and deep language-specific knowledge. CoDRAG's `large_files.py` analyzer flagging `package-lock.json` as "critical" is a symptom of this — it's doing crude analysis that specialized tools handle with nuance.

**But these tools all share a blind spot: they don't understand the codebase as a system.**

ruff can tell you a function is too complex. It can't tell you that function is also a hub node with 23 dependents, sits at the intersection of two modules, and is part of a recent architectural decision to migrate from monolithic to subpackage structure. That contextual layer — the structural relationships, the design rationale, the historical decisions — is what CoDRAG uniquely provides.

## The Shift: From Auditor to Audit Intelligence Provider

### Current Model (CoDRAG runs the audit)

```
CoDRAG
├── large_files.py       ← reimplements what `wc -l` does
├── misplaced_imports.py  ← reimplements what import linters do  
├── circular_deps.py      ← reimplements what madge/pydeps do
├── naming.py             ← reimplements what ruff/eslint do
└── hub_bottlenecks.py    ← ✓ this IS unique to CoDRAG
```

CoDRAG is a mediocre linter AND an excellent structural analyzer. The mediocre linter dilutes the excellent structural analysis with noise (lock file warnings, generic remediation text, duplicated bottleneck findings).

### Proposed Model (CoDRAG enriches other audits)

```
External Audit Tools                    CoDRAG Knowledge Layer
├── ruff (Python lint)     ──enrich──→  + structural context per finding
├── mypy (type check)      ──enrich──→  + blast radius per error
├── eslint (JS lint)       ──enrich──→  + module boundary context
├── semgrep (security)     ──enrich──→  + concept alignment check
├── pytest (coverage)      ──enrich──→  + risk-weighted coverage gaps
│                                       │
│                                       ├── hub_bottlenecks    (CoDRAG-native)
│                                       ├── module_coupling     (CoDRAG-native)
│                                       ├── concept_violations  (CoDRAG-native, NEW)
│                                       └── architectural_drift (CoDRAG-native, NEW)
```

CoDRAG stops reimplementing lint rules and instead becomes the layer that makes lint findings *smarter*.

## What This Looks Like in Practice

### Scenario 1: ruff reports a complex function

**Today (ruff alone):**
```
src/codrag/mcp/server.py:1438:1: C901 `tool_impact` is too complex (23)
```

**With CoDRAG enrichment:**
```
src/codrag/mcp/server.py:1438:1: C901 `tool_impact` is too complex (23)
  [CoDRAG] This function is in a hub file (23 dependents). Complexity here 
  affects: mcp/__init__.py, mcp_server.py, and 21 other files.
  [CoDRAG] Concept "MCP handler simplification" (Phase 50) planned to split 
  this handler. See concept for rationale.
  [CoDRAG] Suggested split boundary: lines 1438-1480 (markdown assembly) vs 
  1481-1511 (API call + filtering). Trace graph shows these are separable.
```

### Scenario 2: mypy reports a type error

**Today (mypy alone):**
```
src/codrag/core/index.py:245: error: Argument 1 to "search" has 
incompatible type "str | None"; expected "str"  [arg-type]
```

**With CoDRAG enrichment:**
```
src/codrag/core/index.py:245: error: Argument 1 to "search" has 
incompatible type "str | None"; expected "str"  [arg-type]
  [CoDRAG] index.py is a core file (1843 lines, 45 dependents). This type 
  error may propagate to: search router, MCP search handler, dashboard search.
  [CoDRAG] The `search()` function was last modified in Phase 50 (MCP 
  consolidation). Observation: "search API accepts optional query for 
  ambient context mode."
  [CoDRAG] This looks intentional — the None case is the ambient codrag() 
  call with no query. Consider Optional[str] in the signature instead.
```

### Scenario 3: semgrep reports a security finding

**Today (semgrep alone):**
```
src/codrag/api/routers/llm.py:892: WARNING: User input passed to 
subprocess without sanitization [dangerous-subprocess-use]
```

**With CoDRAG enrichment:**
```
src/codrag/api/routers/llm.py:892: WARNING: User input passed to 
subprocess without sanitization [dangerous-subprocess-use]
  [CoDRAG] This endpoint is exposed via FastAPI at /api/llm/proxy. 
  It accepts external HTTP requests.
  [CoDRAG] The input originates from the model_name parameter in the 
  LLM proxy endpoint. Trace: request → router → subprocess call.
  [CoDRAG] No concept or observation justifies unsanitized subprocess 
  use here. This appears to be a genuine security gap.
  [CoDRAG] Blast radius: HIGH — this router has 15 dependents and is 
  accessible from the dashboard.
```

### Scenario 4: pytest coverage report

**Today (coverage alone):**
```
Name                              Stmts   Miss  Cover
src/codrag/mcp/server.py           1847    982    47%
src/codrag/core/index.py           1203    601    50%
src/codrag/services/pi_agent.py     445    389    13%
```

**With CoDRAG enrichment:**
```
Risk-Weighted Coverage Gaps (highest risk first):

1. src/codrag/mcp/server.py — 47% coverage, 23 dependents, 
   CRITICAL hub file. Risk score: 9.2/10
   → Untested: tool_impact, tool_trace_neighbors, tool_audit
   → These handlers serve MCP clients — failures are user-visible.
   
2. src/codrag/core/index.py — 50% coverage, 45 dependents,
   CRITICAL hub file. Risk score: 8.8/10
   → Untested: incremental reindex, embedding cache invalidation
   → Concept: "index correctness is non-negotiable" (Phase 48)

3. src/codrag/services/pi_agent.py — 13% coverage, 3 dependents,
   internal service. Risk score: 3.1/10
   → Low risk: Pi Agent runs as daemon thread, failures are non-fatal.
   → Observation: "All Pi scenarios are pure Python, zero LLM" (Phase 66)
```

The coverage numbers are the same. The risk interpretation is completely different. CoDRAG transforms raw metrics into actionable priorities.

## Architecture: The Enrichment API

### Option A: Post-Processing Pipeline

External tools produce findings → CoDRAG enriches them after the fact.

```
[ruff output] ──parse──→ [normalized findings] ──enrich──→ [CoDRAG-enriched findings]
```

**Implementation:**
```python
# New MCP tool or API endpoint
codrag_enrich(
    findings=[
        {
            "file": "src/codrag/mcp/server.py",
            "line": 1438,
            "rule": "C901",
            "message": "too complex (23)",
            "source": "ruff",
            "severity": "warning"
        }
    ],
    enrichments=["impact", "concepts", "observations", "suggestions"]
)
```

**Returns:**
```json
{
    "enriched_findings": [
        {
            "original": { ... },
            "impact": {
                "dependents": 23,
                "is_hub": true,
                "risk_score": 8.5
            },
            "concepts": [
                "MCP handler simplification planned (Phase 50)"
            ],
            "observations": [
                "tool_impact handler needs splitting (Phase 82 dogfood)"
            ],
            "suggestion": "Split at line 1480 — markdown assembly vs API logic are structurally independent."
        }
    ]
}
```

**Pros:** Non-invasive. Works with any tool that produces parseable output. No integration with tool internals needed.
**Cons:** Requires a parsing step per tool. Findings need normalization. Two-pass workflow.

### Option B: SARIF Enrichment

SARIF (Static Analysis Results Interchange Format) is the standard output format for many audit tools. CoDRAG enriches SARIF files.

```
[tool] ──produces──→ [results.sarif] ──codrag enrich──→ [enriched.sarif]
```

**Implementation:**
```python
# CLI command
codrag enrich --input ruff-results.sarif --output enriched.sarif

# Or MCP tool
codrag_enrich(sarif_input="path/to/results.sarif", format="sarif")
```

CoDRAG reads the SARIF file, looks up each finding's file/line in the trace graph, appends enrichment data as SARIF `message.markdown` annotations or custom properties, and writes the enriched SARIF back.

**Pros:** Standards-based. Works with GitHub Code Scanning (which accepts SARIF). Many tools already produce SARIF. One integration covers many tools.
**Cons:** Not all tools produce SARIF. The SARIF spec is complex. Custom properties may not render in all SARIF viewers.

### Option C: Real-Time Context Provider (Recommended)

Instead of post-processing findings, CoDRAG provides context that audit tools can query in real-time.

```
[ruff plugin] ──asks CoDRAG──→ "What's the risk context for server.py:1438?"
              ←──responds────  { dependents: 23, is_hub: true, concepts: [...] }
```

**Implementation:**
This is essentially what `codrag_impact` and `codrag_search` already do, but with a thinner, finding-oriented API:

```python
# New MCP tool optimized for audit tool consumption
codrag_context_for_finding(
    file_path="src/codrag/mcp/server.py",
    line=1438,
    symbol="tool_impact",  # optional, for precision
    context_types=["impact", "concepts", "observations"]
)
```

Returns a compact, structured context blob that any tool can consume. The key difference from `codrag_impact` is:
- **File + line granularity** (not just file-level)
- **Pre-formatted for annotation** (compact, embeddable in tool output)
- **Optimized for batch calls** (tool sends 50 findings, gets 50 context blobs back efficiently)

**Pros:** Real-time, no post-processing. Any tool can integrate. Batch-friendly. Aligns with CoDRAG's identity as a context provider.
**Cons:** Requires tool-side integration (plugins for ruff, eslint, etc.). More engineering effort per tool.

### Hybrid: Option A + B for immediate value, Option C as the vision

1. **Now:** Build the `codrag_enrich` tool (Option A) that accepts any structured finding list and returns enriched findings. Immediately useful with CLI tools.
2. **Soon:** Add SARIF input/output support (Option B) for CI/CD integration and GitHub Code Scanning.
3. **Later:** Build lightweight plugins for popular tools (Option C) that query CoDRAG in real-time during analysis.

## What CoDRAG-Native Audit Keeps

Not everything should be delegated. CoDRAG has unique analytical capabilities that no external tool can provide:

### Keep: Structural Analysis (only CoDRAG can do this)
- **Hub bottleneck detection** — files with disproportionate in-degree. No lint tool tracks import fan-in.
- **Module coupling analysis** — cross-boundary import density. This requires the module clustering that CoDRAG builds.
- **Circular dependency detection with context** — madge/pydeps find cycles, but CoDRAG can explain *why* the cycle exists (which concept introduced it, which files are involved, what the blast radius of breaking it is).

### Keep: Concept-as-Assertion (NEW — CoDRAG's moat)
Concepts become testable architectural rules:

```python
# From concept: "dependency direction: agents/ → services/ → core/, never reverse"
# CoDRAG checks:
for edge in trace_graph.edges:
    if edge.source.module == "core" and edge.target.module == "agents":
        yield Finding(
            severity="warning",
            message=f"Architectural violation: {edge.source.path} imports from {edge.target.path}",
            concept="dependency direction (Phase 67)",
            suggestion="Move shared code to services/ or extract an interface in core/"
        )
```

This is something NO external tool can do — it requires understanding the project's stated architectural intent and checking reality against it. It's the intersection of `codrag_concepts` and `codrag_audit`.

### Keep: Architectural Drift Detection (NEW)
Compare the codebase's actual structure to its declared architecture:
- Module boundaries declared in concepts vs actual import patterns
- Dependency directions stated vs observed
- Design patterns declared vs implemented

Drift findings are high-signal because they represent the gap between intention and reality — exactly the kind of intelligence CoDRAG is built to provide.

### Drop or Delegate: Generic Analysis
- **Large file detection** → delegate to wc/loc tools, or just don't report it (IDEs show file sizes)
- **Naming convention checks** → delegate to ruff/eslint (they have configurable naming rules)
- **Unused import detection** → delegate to ruff (autofix-capable)
- **Generic complexity metrics** → delegate to radon/eslint-complexity

## What Changes in the Codebase

### Deprecate or Reduce
| Analyzer | Action | Reason |
|----------|--------|--------|
| `large_files.py` | Deprecate or make info-only | Other tools + IDEs handle this; CoDRAG's version is crude |
| `naming.py` (if exists) | Deprecate | ruff/eslint are authoritative |
| Generic complexity | Deprecate | radon/eslint-complexity are better |

### Enhance
| Analyzer | Enhancement | Why |
|----------|-------------|-----|
| `misplaced_imports.py` | Deduplicate + add concept context | Keep the structural analysis, fix the UX |
| `hub_bottlenecks.py` | Add risk scoring (deps × churn × coverage) | Make findings actionable |
| `circular_deps` | Add concept-aware explanation | "This cycle was introduced during X, concept Y says..." |

### Build New
| New Capability | Description |
|---------------|-------------|
| `concept_violations.py` | Check concept assertions against trace graph |
| `architectural_drift.py` | Compare declared vs actual module boundaries |
| `codrag_enrich` tool | Accept external findings, return enriched findings |
| SARIF enrichment | Read/write SARIF with CoDRAG annotations |
| Batch context API | Efficient "context for N findings" endpoint |

### Modify Existing Tools
| Tool | Change |
|------|--------|
| `codrag_audit` scan | Default to CoDRAG-native findings only (structural + concepts). External tool findings available via `codrag_enrich`. |
| `codrag_audit` report | Reports synthesize CoDRAG-native + enriched external findings together |
| `codrag_audit` refactor | Works the same but with richer context from concept alignment |

## The Vision: CoDRAG as the Contextual Backbone

```
                    ┌─────────────────────────┐
                    │  Agent / Developer IDE   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    CoDRAG MCP Server     │
                    │                          │
                    │  codrag_search           │
                    │  codrag_impact           │
                    │  codrag_concepts         │
                    │  codrag_observe          │
                    │  codrag_enrich  ← NEW    │
                    │  codrag_audit            │
                    │    ├─ structural (native) │
                    │    ├─ concept violations  │
                    │    └─ enriched external   │
                    └──┬──────────┬──────────┬─┘
                       │          │          │
              ┌────────▼──┐  ┌───▼────┐  ┌──▼────────┐
              │   ruff     │  │ mypy   │  │  semgrep  │
              │   eslint   │  │ clippy │  │  pytest   │
              │   biome    │  │        │  │  coverage │
              └────────────┘  └────────┘  └───────────┘
```

External tools do what they're good at (language-specific analysis, security scanning, type checking). CoDRAG does what it's good at (structural context, design rationale, blast radius, concept alignment). The enrichment layer combines them into intelligence that neither can produce alone.

This aligns perfectly with the Phase 62 strategic pivot: "CoDRAG discovers opportunities. You choose how to manage them." Extended: "CoDRAG provides context. Your tools provide findings. Together they produce intelligence."

## Migration Path

### Phase 1: Add `codrag_enrich` tool (1-2 days)
Accept a list of findings (JSON format), return enriched findings with impact, concepts, and observations. No external tool integration needed — agents can call it manually.

### Phase 2: SARIF support (1 day)
Parse SARIF input, enrich, output enriched SARIF. Enables CI/CD integration.

### Phase 3: Concept-as-assertion analyzer (2-3 days)
New audit analyzer that checks concept assertions against the trace graph. This is the killer feature — architectural intent verification.

### Phase 4: Reduce native audit scope (1 day)
Deprecate or downgrade generic analyzers (large_files, naming). Keep structural and concept-based analyzers.

### Phase 5: Tool-specific plugins (ongoing)
Build lightweight integrations for popular tools. Start with ruff (Python) and eslint (TypeScript) since those are CoDRAG's own stack.
