# Documentation Mining Strategy — Epistemic Evidence from Docs

**Parent**: `Phase22_trace-epistomology/README.md`  
**Status**: Design

---

## The Problem

AI-assisted development workflows produce enormous `Docs/` folders. The HomeColab project has **200+ markdown files** spanning research, design specs, architecture audits, implementation plans, meeting notes, and stale drafts. These documents contain the project's **institutional memory** — the *why* behind the *what*.

Current trace augmentation treats these docs identically to code files: read 30 lines, classify role, produce a one-line summary. This throws away most of the epistemic value. A research doc's value isn't "what it says" — it's:

- **What decision did it drive?** (Research → Decision → Implementation chain)
- **Is the decision still active?** (Or was it shelved/superseded?)
- **What code does it describe?** (Cross-references to actual implementation)
- **Does the code match the doc?** (Drift detection)
- **What was considered and rejected?** (Negative knowledge — equally valuable)

---

## Document Taxonomy

Based on patterns observed across AI-assisted codebases:

### Active Knowledge (high epistemic value)
| Type | Pattern | Example | Value |
|---|---|---|---|
| **Architecture Decision** | Contains "Decision:", "Verdict:", "Chosen:" | `07_ARCHITECTURE_DECISION.md` | Explains *why* the code is structured this way |
| **Design Spec** | Contains wireframes, component specs, state machines | `VOTING_STATE_MACHINE.md` | Ground truth for expected behavior |
| **Implementation Plan** | Phased tasks with status markers | `FREEMIUM_IMPLEMENTATION_PLAN.md` | Links features to code files |
| **Migration Guide** | Before/after, breaking changes | `LISTING_CARD_MIGRATION_COMPLETE.md` | Explains historical transitions |
| **Active Reference** | Quick reference, API docs, style guides | `ADS_QUICK_REFERENCE.md` | Current source of truth |

### Research Knowledge (medium epistemic value)
| Type | Pattern | Example | Value |
|---|---|---|---|
| **Research Plan** | Hypotheses, methodology, questions | `01_RESEARCH_FRAMEWORK.md` | Shows what was investigated |
| **Research Findings** | Data, analysis, conclusions | `02_MARKET_SIZE_ANALYSIS.md` | Evidence behind decisions |
| **Competitor Analysis** | Feature comparisons, positioning | `03_COMPETITOR_ANALYSIS.md` | Context for feature priorities |

### Meta Knowledge (contextual value)
| Type | Pattern | Example | Value |
|---|---|---|---|
| **Task List** | Checkboxes, phase tasks | `01_TASKS.md` | Shows what's done vs pending |
| **Changelog** | Version history, release notes | `CHANGELOG.md` | Temporal context |
| **Convention Guide** | Naming rules, patterns | `CONVENTIONS.md` | Explains code style choices |
| **Audit Report** | Risk assessments, findings | `ARCHITECTURE_TODOS.md` | Known issues and risks |

### Low/Negative Knowledge (noise or traps)
| Type | Pattern | Example | Value |
|---|---|---|---|
| **Shelved Plan** | "De-prioritized", "On hold", "Phase N (future)" | Various | **Dangerous if mistaken for active** |
| **Superseded Doc** | Replaced by newer version | Old v1 specs | **Misleading if used as ground truth** |
| **Brainstorm Dump** | Unstructured ideas, question lists | Early drafts | Low signal-to-noise |
| **Generated Boilerplate** | Auto-generated READMEs, license files | `README.md` (template) | Near-zero unique value |

---

## Cross-Reference Extraction

### Explicit References

Documents contain direct references to code that can be extracted:

**File path references**:
```markdown
**Location**: `Managers/AdManager.swift`
See `1_Link_unfurrling_findings.md`
Canonical implementation: Packages/HomeColabShared/Sources/HomeColabShared/ShareTextParser.swift
```

**Extraction regex patterns**:
```
# Backticked file paths
`([A-Za-z0-9_/.-]+\.(swift|py|ts|tsx|js|json|md))`

# Quoted file paths  
"([A-Za-z0-9_/.-]+\.(swift|py|ts|tsx|js|json|md))"

# TRACE markers (CoDRAG convention)
TRACE:\s*([a-z0-9._]+)

# See/Related markers
(?:See|Related|Ref|Reference):\s*[`"]?([A-Za-z0-9_/.-]+)[`"]?
```

**Class/Type references**:
```markdown
`FirestoreManager`, `AuthenticationManager`, `FilterStateManager`
integrating with `AdPlacementCoordinator`
```

**Extraction**: Match backticked identifiers against known symbol names from `trace_nodes.jsonl`.

### Implicit References

Documents describe concepts without naming specific files:

```markdown
"the ad framework" → maps to Components/Ads/*
"authentication flow" → maps to Managers/AuthenticationManager.swift + Views/Onboarding/*
"the voting system" → maps to Components/VoteButton.swift + Docs/Design/VOTING_STATE_MACHINE.md
```

**Extraction strategy**: Use embedding similarity between doc content chunks and code file summaries (from Pass 1). If a doc paragraph has >0.8 cosine similarity to a code file's summary, create an implicit `documents` edge.

This is where **Phase 16 (Context Intelligence)** and **Phase 22** intersect — the native embedding index enables implicit cross-reference discovery.

### Decision Chain Extraction

Many projects organize docs in numbered phases:

```
Phase01_Consolidate/
  01_AUDIT_RESULTS.md
  02_CONCEPTS_EXTRACTED.md
  03_BUSINESS_APP_VISION.md
  04_RESEARCH_QUESTIONS.md
  05_CROSS_REFERENCE_MAP.md

Phase02_DeepRealEstateApp-Research/
  01_RESEARCH_FRAMEWORK.md
  ...
  08_GO_NO_GO_DECISION.md

Phase03_ArchitectureStrategy/
  ...
  07_ARCHITECTURE_DECISION.md
  08_IMPLEMENTATION_PLAN.md
```

**Pattern**: Phase folders contain numbered docs that form a **decision chain**: research → analysis → decision → implementation plan.

**Extraction**:
1. Detect phase-numbered directories
2. Order docs by number within each phase
3. Create `precedes` edges: `01_AUDIT → 02_CONCEPTS → 03_VISION → ...`
4. Create `informs` edges between phases: `Phase01/05_CROSS_REFERENCE → Phase02/01_RESEARCH_FRAMEWORK`
5. Identify terminal docs (decisions, verdicts) and link to implementation code

### Status Assertion Extraction

Docs frequently assert the status of features or components:

```markdown
| Component | Status |
|-----------|--------|
| AdManager | ✅ Complete |
| SDK Integration | ⏳ Pending |

**Status**: Research Complete
**Verdict**: We can unlock "Verified" data without API integration

All tasks are marked as completed ✅
```

**Extraction**:
- Parse markdown tables with status columns
- Match status emoji patterns: ✅ → complete, ⏳ → pending, ❌ → blocked, 🔄 → in-progress
- Extract "Status:" and "Verdict:" lines
- Map status assertions to specific code files or features
- Store as `status_assertions` in epistemic entry

---

## Drift Detection

The most valuable epistemic signal from docs is **when they're wrong** — i.e., when the code has drifted from what the doc describes.

### Types of Drift

1. **Rename drift**: Doc references `InterstitialAdController.swift` but file is now `InterstitialAdManager.swift`
   - Detection: fuzzy match file references against actual trace nodes
   - Severity: Medium (file exists but name changed)

2. **Deletion drift**: Doc references a file that no longer exists in the trace
   - Detection: exact match against trace node file paths
   - Severity: High (doc describes something that's gone)

3. **Status drift**: Doc says "⏳ Pending" but code shows the feature is implemented
   - Detection: cross-reference status assertions against code signals (e.g., presence of imports, non-stubbed implementations)
   - Severity: Medium (doc is stale but not harmful)

4. **Architecture drift**: Doc describes architecture (e.g., "singleton pattern") that doesn't match trace edges
   - Detection: compare doc's described dependencies against actual import edges
   - Severity: High (doc is actively misleading)

5. **Supersession drift**: A newer doc exists that covers the same topic but the old one isn't marked superseded
   - Detection: embedding similarity between doc pairs + recency comparison
   - Severity: Low-Medium (confusing but not directly harmful)

### Drift Scoring

Each doc node gets a `drift_score` (0.0 = no drift, 1.0 = completely drifted):

```python
def compute_drift_score(doc_epistemic: EpistemicEntry) -> float:
    if not doc_epistemic.doc_meta:
        return 0.0
    
    dm = doc_epistemic.doc_meta
    total_refs = len(dm.references_code) + len(dm.references_docs)
    if total_refs == 0:
        return 0.0  # can't assess drift without references
    
    drift_count = len(dm.drift_detected)
    deletion_count = sum(1 for d in dm.drift_detected if d.type == "deleted")
    rename_count = sum(1 for d in dm.drift_detected if d.type == "renamed")
    
    # Deletions are worse than renames
    weighted_drift = (deletion_count * 1.0 + rename_count * 0.5) / total_refs
    
    return min(1.0, weighted_drift)
```

Drift score feeds into the doc's epistemic score:
- `drift_score < 0.1`: doc is current → boost epistemic score
- `drift_score 0.1-0.3`: minor drift → neutral
- `drift_score > 0.3`: significant drift → penalize epistemic score, flag for review

---

## Outlier and Stub Detection

### Orphan Documents

Docs that reference no code files and are referenced by no other docs. These are either:
- **Standalone guides** (e.g., `CONVENTIONS.md`) — still valuable
- **Abandoned drafts** — noise
- **Entry points** (e.g., top-level `README.md`) — valuable but differently

**Detection**: After cross-reference extraction, any doc with 0 code refs AND 0 doc refs AND `doc_type != "guide"` is flagged as potentially orphaned.

**Action**: Don't delete. Flag in UI as "⚠️ Unlinked document — may be outdated or standalone."

### Idea Stubs

Short docs (<50 lines) with questions, TODOs, or speculative language:
- "What if we..."
- "TODO: Research..."
- "Open question:"
- Files named with patterns like `IDEA_*.md`, `BRAINSTORM_*.md`, `SCRATCH_*.md`

**Detection**: Line count + keyword matching + `doc_status == "draft"`.

**Action**: Classify as `doc_type: "stub"`. Low epistemic weight. Don't use as context for code enrichment — but DO include in "project ideas" module synthesis.

### Shelved Plans

Docs that were once active but are now deprioritized:
- Contains: "De-prioritized", "Shelved", "On hold", "Future phase", "v2+"
- Or: located in a directory named `archived/`, `shelved/`, `old/`, `deprecated/`

**Detection**: Keyword + path heuristics.

**Action**: Classify as `doc_status: "shelved"`. **Critical**: These must NOT be used as active context for code enrichment. An LLM that sees a shelved plan might describe code as implementing features that were actually rejected.

**The shelved plan trap**: This is one of the most dangerous failure modes. If a shelved plan describes a feature in detail, and the 14b model uses that plan to enrich a code file, it might claim the code implements that feature — even though it doesn't. **Shelved docs must be quarantined from the enrichment context pool.**

### Contradiction Detection

Two docs making conflicting claims about the same subsystem:

**Detection approach**:
1. Group docs by `subsystem` or overlapping `references_code`
2. Extract key assertions from each (status, architecture, decisions)
3. Compare assertions: if Doc A says "Status: Complete" and Doc B says "Status: Pending" for the same feature → contradiction
4. Also: if Doc A says "We chose Option X" and Doc B says "We chose Option Y" for the same decision → contradiction

**Implementation**: This is a Pass 3 task (cluster-level reasoning). The 14b model receives all docs in a cluster and is asked to identify inconsistencies.

**Action**: Flag contradictions in the module synthesis. Don't auto-resolve — surface to user: "Conflicting status: ADS_FRAMEWORK_STATUS.md says ✅ Complete for InterstitialAdController, but ADS_INTEGRATION_GUIDE.md references it as pending."

---

## Integration with Enrichment Pipeline

### Pass 1 (3b): Document Classification
- Use `DOC_CLASSIFICATION_PROMPT` for `.md` files
- Produce: `doc_type`, `doc_status`, basic `summary`
- **No cross-reference extraction** (too complex for 3b)

### Pass 2 (14b): Document Enrichment
- Extract explicit cross-references (file paths, class names)
- Extract status assertions
- Detect drift against trace nodes
- Produce: `doc_meta` with full cross-reference data

### Pass 3 (14b): Cross-Document Synthesis
- Identify decision chains across phase-numbered docs
- Detect contradictions within doc clusters
- Produce: `documents` / `decides` / `supersedes` edges
- Identify orphans and stubs

### Pass 4+ (continuous): Drift Monitoring
- When a code file changes, re-check all docs that reference it
- When a doc changes, re-extract cross-references and re-check drift
- Decay epistemic scores of docs whose referenced code changed

---

## The "Every Codebase is Different" Principle

We can't hardcode assumptions about doc folder structure. Different teams organize differently:

| Pattern | Example | Detection |
|---|---|---|
| Phased folders | `Phase01/`, `Phase02/` | Regex: `Phase\d+` or `Step\d+` in path |
| Flat docs folder | `docs/*.md` | All `.md` in single directory |
| Colocated docs | `src/auth/README.md` next to `src/auth/login.ts` | `.md` files adjacent to code files |
| ADR pattern | `docs/adr/001-use-react.md` | `adr/` directory with numbered files |
| Wiki-style | `wiki/Home.md`, `wiki/Architecture.md` | `wiki/` directory |
| Scattered | `.md` files everywhere | No pattern — rely on content analysis |

**Our approach**: Don't detect folder structure. Instead, **analyze content**. The 14b model reads the doc and classifies it regardless of where it lives. A decision doc in `random_notes/` still gets classified as `architecture_decision` based on its content.

The folder structure heuristics are used only as **tiebreakers** when content analysis is ambiguous:
- File in `archived/` + ambiguous content → lean toward `shelved`
- File in `docs/adr/` + ambiguous content → lean toward `architecture_decision`
- File named `*_TASKS.md` → lean toward `plan`

---

## Metrics and Success Criteria

### Coverage Metrics
- **Cross-reference coverage**: % of code files referenced by at least one doc
- **Doc grounding**: % of docs that reference at least one existing code file
- **Drift rate**: % of doc-code references with detected drift

### Quality Metrics
- **Decision chain completeness**: % of identified decision chains with a terminal decision doc
- **Shelved plan quarantine rate**: % of shelved docs correctly excluded from enrichment context
- **Contradiction detection precision**: manual review of flagged contradictions

### Target Values (for a mature project)
- Cross-reference coverage: >60% of code files
- Doc grounding: >80% of docs
- Drift rate: <15% (healthy), >30% (needs doc review)
- Shelved plan quarantine: 100% (this is a correctness requirement, not a target)
