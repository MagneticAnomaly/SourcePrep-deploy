# Phase 43: AutoAudit — Autonomous Codebase Analysis & Documentation

## The Insight

In the Refactor 2 process, we performed the following steps **manually**:

1. **Large file scan** — `find | wc -l | sort` → identified 16 oversized files
2. **Class/function inventory** — `grep "class\|def"` → mapped every component's location
3. **Purpose research** — read docstrings, cross-referenced design docs, traced import chains
4. **Dependency analysis** — `grep "from .augmenter import"` → found misplaced concerns
5. **Duplication detection** — eyeballed 4 identical code blocks in TraceBuilder
6. **Gap identification** — reasoned about what should change based on #1–5
7. **Documentation generation** — wrote 8 markdown files (audit, plan, gap analysis, inventory)

**Every one of these steps can be expressed as graph queries + heuristic rules + LLM synthesis** — which is exactly what the CoDRAG pipeline already does for per-node enrichment. The difference is scope:

| Existing Pipeline | AutoAudit |
|---|---|
| Per-node enrichment ("what does this function do?") | Codebase-level analysis ("what's wrong with this architecture?") |
| Produces overlay data (trace_augmented.jsonl) | Produces **user-facing documents** (markdown reports) |
| Feeds into search/context | Feeds into **developer decision-making** |
| Runs after file changes | Runs on demand or on schedule |

AutoAudit is the **meta-cognitive layer** — CoDRAG reasoning about itself (or any codebase it indexes).

---

## What CoDRAG Already Knows

The trace graph + enrichment pipeline already computes nearly everything an audit needs:

### Data Already Available (no new computation)

| Data Source | Audit Use | File |
|---|---|---|
| `trace_nodes.jsonl` — file nodes with `language`, `metadata.size` | **File size analysis** — flag files over thresholds | trace.py |
| `trace_edges.jsonl` — import/contains/calls edges | **Import graph analysis** — detect circular deps, misplaced imports | trace.py |
| `trace_augmented.jsonl` — summaries, roles, related_files | **Purpose inventory** — what does each file do? | augmenter.py |
| `trace_epistemic.jsonl` — domain_tags, design_patterns, tech_debt, cross_references | **Gap detection** — which files have tech debt? missing patterns? | epistemic_enrichment.py |
| `trace_modules.jsonl` — module summaries, dependencies, component_status | **Architecture analysis** — subsystem health, dependency flow | cluster.py |
| `atlas.json` — architectural overview | **Orientation** — codebase-level context for LLM synthesis | atlas.py |
| Epistemic scores — composite 0.0–1.0 per node | **Understanding gaps** — which areas are least understood? | epistemic_score.py |
| Coverage data — traced/untraced/stale files | **Coverage gaps** — what hasn't been analyzed? | trace.py |
| In-degree/out-degree per node | **Hub detection** — which files are structural bottlenecks? | index.py |

### Data That Requires New Computation

| Analysis | Technique | Difficulty |
|---|---|---|
| **Duplicate code detection** | AST-level similarity (tree-sitter subtree hashing) or embedding cosine on chunk pairs | Medium |
| **Naming inconsistency** | Compare function/class names against domain vocabulary from modules | Low (heuristic) |
| **API surface audit** | Walk exported symbols, compare to docs coverage | Low (graph query) |
| **Dependency direction violations** | Define layer ordering rules, walk import edges for violations | Low (graph query) |
| **Dead code detection** | Find nodes with 0 in-degree (no importers) that aren't entry points | Low (graph query) |
| **Test coverage mapping** | Cross-reference test files with source files via import edges + naming | Low (graph query) |
| **Complexity hotspots** | Lines × in-degree × change frequency → risk score per file | Low (formula) |

---

## Architecture: Three Tiers

### Tier 1: Analyzers (Pure Graph Queries — No LLM)

Analyzers are pure functions that read the trace graph and produce structured findings. They run fast (< 1 second) and can execute without any LLM.

```python
class AuditAnalyzer(ABC):
    """Base class for all audit analyzers."""
    
    @abstractmethod
    def analyze(self, ctx: AuditContext) -> List[Finding]:
        """Run the analysis and return findings."""
        ...

@dataclass
class Finding:
    """A single audit finding."""
    analyzer: str          # e.g. "large_files", "circular_deps"
    severity: str          # "critical" | "warning" | "info" | "suggestion"
    category: str          # "size" | "architecture" | "quality" | "coverage"
    title: str             # Human-readable title
    description: str       # Detailed explanation
    file_paths: List[str]  # Affected files
    evidence: Dict         # Analyzer-specific data (metrics, counts, etc.)
    suggested_action: str  # What to do about it

@dataclass  
class AuditContext:
    """Everything an analyzer needs — pre-loaded from the trace graph."""
    nodes: Dict[str, Dict]           # All trace nodes
    edges: List[Dict]                # All trace edges
    augmentations: Dict[str, Dict]   # Summaries/roles per node
    epistemic: Dict[str, Dict]       # Deep enrichment per node
    modules: List[Dict]              # Cluster synthesis results
    atlas: Optional[Dict]            # Atlas document
    file_hashes: Dict[str, str]      # For staleness
    project_root: Path
    index_dir: Path
```

**Built-in Analyzers:**

| Analyzer | Input | Output |
|---|---|---|
| `LargeFileAnalyzer` | node sizes | Files over threshold with line counts |
| `CircularDependencyAnalyzer` | import edges | Cycle lists with involved files |
| `MisplacedImportAnalyzer` | import edges + module membership | Cross-module imports that violate layer rules |
| `DuplicateLogicAnalyzer` | augmentation summaries | Files with suspiciously similar descriptions |
| `DeadCodeAnalyzer` | in-degree = 0 + role != entry_point | Unreachable files/symbols |
| `TestCoverageAnalyzer` | test files + source files via edges | Source files with no test counterpart |
| `HubBottleneckAnalyzer` | in-degree distribution | Files with disproportionate fan-in |
| `TechDebtAggregator` | epistemic tech_debt fields | Aggregated tech debt by module |
| `StalenessAnalyzer` | file hashes + enrichment timestamps | Stale enrichments needing refresh |
| `NamingConsistencyAnalyzer` | symbol names + domain vocabulary | Naming convention violations |
| `ApiSurfaceAnalyzer` | exported symbols vs docs | Undocumented public API |

### Tier 2: Synthesizer (LLM — Produces Documents)

The Synthesizer takes Tier 1 findings and uses an LLM to generate human-readable documents. This is analogous to how the Atlas generator takes module data and produces a narrative.

```python
class AuditSynthesizer:
    """LLM-based synthesis of audit findings into documents."""
    
    def synthesize_report(
        self,
        findings: List[Finding],
        atlas: Optional[AtlasDocument],
        modules: List[ModuleEntry],
        output_dir: Path,
    ) -> List[AuditDocument]:
        """Generate markdown documents from findings."""
        ...
```

**Document Types Generated:**

| Document | Content | Analogous Refactor2 Doc |
|---|---|---|
| `AUDIT_SUMMARY.md` | Executive summary: health score, top findings, recommended actions | 01_large_files_audit.md |
| `ARCHITECTURE_ANALYSIS.md` | Module dependency flow, layer violations, hub bottlenecks | 02_architectural_optimizations.md |
| `GAP_ANALYSIS.md` | Misplaced concerns, duplicated logic, missing abstractions | 06_gap_analysis.md |
| `COMPONENT_INVENTORY.md` | Every class/module with purpose, location, consumers | 05_annotated_refactor_plan.md |
| `TECH_DEBT_REPORT.md` | Aggregated tech debt by module with severity and effort estimates | (new) |
| `TEST_COVERAGE_MAP.md` | Source → test file mapping, uncovered areas | (new) |

### Tier 3: Continuous Monitoring (Deepening Loop Integration)

AutoAudit findings feed back into the epistemic system:

1. **Findings become observations** — stored via the existing ObservationStore (Phase 39 W3), automatically flagged stale when files change
2. **Audit documents are indexed** — generated markdown files are added to the CodeIndex as documentation, searchable via MCP
3. **Drift-aware re-auditing** — when the deepening loop detects stale nodes, it can trigger a targeted re-audit of affected modules
4. **Convergence-aware scheduling** — full audits run when the epistemic graph converges (all nodes settled), not on every file change

---

## Integration Points

### Option A: New Pipeline Stage (Stage 12)

Add `AUDIT` as a new stage after `DEEP_KNOWLEDGE` in the deep enrichment group:

```
Group B — Deep Enrichment:
  6.  epistemic       (14b LLM)
  7.  group_reasoning  (14b LLM)
  8.  clustering       (14b LLM)
  9.  atlas            (14b LLM)
  10. deepening        (loop)
  11. deep_knowledge   (embedding)
  12. audit            (analyzers + LLM synthesis)  ← NEW
```

**Pros:** Runs automatically after deep enrichment converges. Has access to the freshest data.
**Cons:** Adds to pipeline duration. Not every enrichment run needs an audit.

### Option B: Independent Tool (Recommended)

A standalone command and API endpoint, separate from the pipeline:

```bash
codrag audit                        # Full audit → writes reports to .codrag/audit/
codrag audit --category architecture  # Architecture-only
codrag audit --format json            # Machine-readable output
```

```
POST /projects/{id}/audit           # Trigger audit
GET  /projects/{id}/audit/status    # Check progress
GET  /projects/{id}/audit/reports   # List generated reports
GET  /projects/{id}/audit/report/{name}  # Read a specific report
```

MCP tool:
```
codrag_audit          # Trigger or fetch latest audit summary
codrag_audit_report   # Get a specific report by name
```

**Pros:** On-demand, doesn't slow the pipeline. Can run at different granularities. User-controlled.
**Cons:** Must ensure graph data is fresh before running.

### Option C: Hybrid (Best of Both)

- **Tier 1 analyzers run automatically** as part of deep enrichment (lightweight, < 1s)
- **Tier 2 synthesis runs on demand** via CLI/API/MCP (expensive, uses LLM)
- **Tier 3 monitoring is always-on** via the deepening loop

This means the *findings* are always fresh (updated with every pipeline run), but the *documents* are generated only when the user asks.

---

## Output Location

Generated audit documents live in the project's index directory alongside other pipeline artifacts:

```
{index_dir}/
├── trace_nodes.jsonl
├── trace_edges.jsonl
├── trace_augmented.jsonl
├── trace_epistemic.jsonl
├── trace_modules.jsonl
├── atlas.json
├── audit/                          ← NEW
│   ├── findings.json               # Raw structured findings (Tier 1)
│   ├── AUDIT_SUMMARY.md            # Executive summary (Tier 2)
│   ├── ARCHITECTURE_ANALYSIS.md
│   ├── GAP_ANALYSIS.md
│   ├── COMPONENT_INVENTORY.md
│   ├── TECH_DEBT_REPORT.md
│   └── audit_manifest.json         # Timestamps, versions, staleness
```

These files are:
1. **Searchable** — indexed by CodeIndex alongside source code and docs
2. **Servable via MCP** — `codrag_audit_report` tool returns them
3. **Viewable in dashboard** — new Audit panel shows findings + report links
4. **Version-tracked** — `audit_manifest.json` records when each report was generated and what graph state it was based on

---

## What We Leverage From Refactor2

Every step we did manually maps to an analyzer:

| Manual Step | Analyzer | Graph Data Used |
|---|---|---|
| `find \| wc -l \| sort` | `LargeFileAnalyzer` | `trace_nodes[kind=file].metadata.size` |
| `grep "class\|def"` | Already in trace graph | `trace_nodes[kind=symbol]` |
| Read docstrings, cross-ref docs | Already in augmentations | `trace_augmented[].summary, role` |
| `grep "from .augmenter import"` | `MisplacedImportAnalyzer` | `trace_edges[kind=imports]` + module membership |
| Eyeball duplicate code blocks | `DuplicateLogicAnalyzer` | Augmentation summary cosine similarity |
| Reason about gaps | `TechDebtAggregator` + LLM synthesis | `trace_epistemic[].tech_debt` + module deps |
| Write markdown reports | `AuditSynthesizer` | All of the above → LLM → markdown |

---

## Prompt Design for Tier 2 Synthesis

The synthesis prompts follow the same pattern as Atlas generation — structured data in, narrative out:

```
AUDIT_SUMMARY_SYSTEM = """You are a senior software architect conducting a 
codebase health audit. Produce a concise, actionable executive summary."""

AUDIT_SUMMARY_PROMPT = """Generate an audit summary for this codebase.

CODEBASE ATLAS:
{atlas_content}

FINDINGS ({finding_count} total):
{findings_formatted}

MODULE HEALTH:
{module_health}

Generate a markdown document with:
1. Health Score (A-F grade with rationale)
2. Critical Findings (severity=critical, max 5)  
3. Top Recommendations (max 5, ordered by impact)
4. Module-by-Module Status (1-line per module)
5. Suggested Next Steps

Be specific — reference exact file paths and line counts."""
```

---

## User Experience

### CLI
```bash
$ codrag audit
🔍 Running 11 analyzers on project "CoDRAG" (2,461 files)...
  ✓ LargeFileAnalyzer:       16 findings (4 critical, 12 warning)
  ✓ CircularDependency:      0 findings
  ✓ MisplacedImport:         3 findings (1 critical)
  ✓ DuplicateLogic:          2 findings
  ✓ DeadCode:                8 findings
  ✓ TestCoverage:            14 findings (5 warning)
  ✓ HubBottleneck:           3 findings
  ✓ TechDebt:                7 findings
  ✓ Staleness:               0 findings
  ✓ NamingConsistency:       1 finding
  ✓ ApiSurface:              4 findings

📊 Total: 58 findings (5 critical, 21 warning, 32 info)

📝 Generating reports...
  ✓ AUDIT_SUMMARY.md          (2.1 KB)
  ✓ ARCHITECTURE_ANALYSIS.md  (4.8 KB)
  ✓ GAP_ANALYSIS.md           (3.2 KB)
  ✓ COMPONENT_INVENTORY.md    (8.4 KB)
  ✓ TECH_DEBT_REPORT.md       (2.9 KB)
  ✓ TEST_COVERAGE_MAP.md      (1.6 KB)

Reports saved to: ~/.local/share/codrag/projects/{id}/audit/
```

### MCP
```
AI: Let me check the codebase health.
[calls codrag_audit]
→ Returns: executive summary + top 5 findings + health grade

AI: Can you show me the architecture analysis?
[calls codrag_audit_report name="ARCHITECTURE_ANALYSIS"]
→ Returns: full architecture report markdown
```

### Dashboard
- **Audit Panel** — findings list with severity badges, category filters
- **Health Score Ring** — A-F grade in the IndexHealthPanel
- **Module Health Map** — color-coded module cards (green/yellow/red)

---

## Implementation Plan

### Sprint 1: Core Framework + Tier 1 Analyzers (~3 days)
- `src/codrag/core/audit/` subpackage
- `models.py` — Finding, AuditContext, AuditDocument, AuditManifest
- `context.py` — AuditContext loader (reads all graph data into memory)
- `analyzers/large_files.py`
- `analyzers/misplaced_imports.py`
- `analyzers/dead_code.py`
- `analyzers/hub_bottlenecks.py`
- `analyzers/tech_debt.py`
- `analyzers/staleness.py`
- `runner.py` — orchestrates all analyzers, writes `findings.json`
- Tests: 1 test per analyzer (~30 tests)

### Sprint 2: Advanced Analyzers (~2 days)
- `analyzers/circular_deps.py` (Tarjan's algorithm on import graph)
- `analyzers/duplicate_logic.py` (summary cosine similarity)
- `analyzers/test_coverage.py` (source↔test mapping)
- `analyzers/naming.py` (domain vocabulary check)
- `analyzers/api_surface.py` (exported vs documented)

### Sprint 3: Tier 2 Synthesis + CLI (~2 days)
- `synthesizer.py` — LLM-based document generation
- `prompts.py` — audit-specific prompt templates
- 6 document generators (summary, architecture, gaps, inventory, debt, coverage)
- `cli.py` additions — `codrag audit` command
- API endpoints — POST/GET audit

### Sprint 4: Integration + Dashboard (~2 days)
- MCP tools — `codrag_audit`, `codrag_audit_report`
- Pipeline integration — Option C hybrid (findings auto-updated, synthesis on-demand)
- Dashboard Audit panel
- Index audit documents for search

---

## Open Questions

1. **Should audit findings affect epistemic scores?** E.g., a file flagged as "misplaced" could get a score penalty, making it a priority for the deepening loop to re-analyze.
>>> maybe later, let's keep initial build simple

2. **Should users be able to define custom analyzers?** E.g., "flag any file importing from `legacy/`" — this would be a repo_policy extension.
>>> maybe, we can consider this later. this could also be a setting

3. **Should audit reports be git-tracked?** If the project is in embedded mode (`.codrag/` in the repo), audit reports would appear in git diff. This could be useful for code review but noisy for CI.
>>> I think this should be a user setting (maybe per project) personally I would want it to be git-tracked but I don't represent all devs -- I would researdh this and we can arrive at a default setting based on assumptions about how most devs might prefer.

4. **What's the right LLM slot?** Synthesis quality benefits from the large model (14b+), but the small model (3b) would be faster and cheaper. Could use small for summaries, large for architecture analysis.
>>> good, could we use the fast model in a stage in fast sync, then the large model in "Continuous Deepening" stage? would this fit into the plan? I'm open to options here.

5. **Should the audit compare against previous runs?** A "delta audit" showing "3 new findings since last week" would be powerful for continuous monitoring. Requires versioned findings.
>>> Hmm mabybe. I'm concerned it might confuse the model, only if we know it can be helpful, maybe plan but save for later

