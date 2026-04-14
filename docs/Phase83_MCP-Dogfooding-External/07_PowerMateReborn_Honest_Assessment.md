# 07 — PowerMateReborn: Honest Assessment of CoDRAG on a Small Real-World Project

**Date:** 2026-04-14
**Target:** PowerMateReborn — a native Swift macOS menu-bar app that resurrects Griffin PowerMate USB/Bluetooth hardware controllers. 24 files, ~5K lines of Swift.
**Pipeline:** Full finalize pipeline. Atlas (LLM mode), concepts (133 created), audit (62 findings, Tier 2 with 5 synthesized docs), antibodies (47 derived). kimi-k2.5:cloud model. 7.4 minutes total.
**Significance:** First test on a small, single-language, well-scoped project with the COMPLETE pipeline including concepts and antibodies. Previous tests (CoDRAG: huge multi-language monorepo; Haley: large Python project) tested scale. This tests depth on a small codebase.

---

## Grades

| Tool | Call | Grade | Notes |
|------|------|-------|-------|
| `codrag` ambient | default | **A** | Excellent atlas + architecture layers + concept count |
| `codrag_search` context | "how does the driver communicate with USB" | **A+** | Full source code returned with concept cross-references |
| `codrag_search` context | "why does brightness use DDC/CI" | **A** | 10 relevant concepts as the primary answer — rationale query routed to concepts |
| `codrag_search` symbol | `PowerMateTransport` | **B** | Found protocol + delegate, but no signatures/docstrings |
| `codrag_impact` dependents | AppDelegate.swift | **A** | 3 dependents (2 direct, 1 transitive) with relationship types |
| `codrag_impact` direction=all | PowerMateManager.swift | **D** | 1 node, 0 edges — graph is empty for this file |
| `codrag_audit` scan | structural | **B** | 1 finding (AppDelegate coupling hotspot), cycles still missing |
| `codrag_audit` report | AUDIT_SUMMARY | **A** | Full LLM-synthesized health report with grade, recommendations, module status table |
| `codrag_audit` antibodies | list | **F** | Error: AntibodyStore not initialized |
| `codrag_concepts` | get | **A+** | 133 concepts, 25 shown, rich and insightful |
| `codrag_observe` | get | N/A | No observations (expected — no agent has worked on this yet) |

**Overall: B+**

---

## What's Genuinely Excellent

### 1. The Concepts Are Remarkable (A+)

133 auto-generated concepts from a 24-file Swift project. Not boilerplate — genuinely insightful architectural observations that a senior developer would recognize as true:

- **"Hardware Capability Negotiation as First-Class Design Concern"** — correctly identifies that the 3-tier volume fallback (CoreAudio → AppleScript → software gain) treats hardware heterogeneity as a fundamental constraint, not an edge case
- **"Reverse-Engineered Protocol Necessity"** — correctly identifies that the BLE transport was built from packet captures because Griffin's GATT layout is undocumented
- **"Singleton as Necessary Evil for NSApplicationDelegate Contract"** — correctly identifies that the singleton in AppDelegate isn't lazy design but a forced constraint from macOS's application lifecycle
- **"DDC/CI Reliability Collapse on Apple Silicon as Platform Betrayal"** — correctly identifies a real industry pain point where Apple Silicon broke DDC/CI that worked on Intel

These aren't generic "this file uses a singleton pattern" observations. They capture the *why* — design rationale, platform constraints, business decisions. An agent inheriting these concepts understands not just what the code does but why it was written this way. This is exactly the value proposition CoDRAG claims.

**The concept-concept cross-referencing in search is powerful.** When I searched "why does brightness use DDC/CI," the top results were 10 relevant concepts, not code. For a RATIONALE query, concepts are the right answer. The system correctly identified that this was a "why" question and surfaced design decisions. This is the intent-classification behavior Phase 86 aims for, and it's partially working here through concept injection in search results.

### 2. The Audit Summary Report Is Excellent (A)

The AUDIT_SUMMARY is the first report I've seen that actually works across all test projects. It produced:

- **Health Grade: C** — honest assessment acknowledging good architecture but real problems
- **5 prioritized recommendations** with specific files, actions, and effort/value ratings
- **Module status table** — 24 modules with status (WARNING, INFO, HEALTHY) and key issues
- **Next steps** in three time horizons (immediate, short-term, medium-term)

Specific standout: "Audit Potentially Orphaned Files" — the report correctly notes that 11 files have no static import edges, but qualifies it: "verify whether these files are dead code or simply missing static import edges." This is honest — it admits the finding might be a graph limitation rather than a code problem. For a Swift project where the Rust parser may not resolve all imports, this self-awareness is valuable.

### 3. Semantic Search Returns Full Source Code (A+)

The USB communication query returned the entire `PowerMateUSBTransport.swift` and `MIDIController.swift` files with full source code. For a 24-file project, returning complete files is the right density — there's no need for chunk-level truncation when files are 100-200 lines.

More importantly, the search included **concept cross-references** at the top:
```
[Related concepts:]
  • Virtual Device Strategy Avoids Driver Certification Burden
  • Transport Agnosticism as Product Strategy
```

These give the agent architectural context before reading the code. "The transport abstraction exists because Griffin shipped both USB and Bluetooth variants" — now the agent understands the protocol/class before reading the implementation.

### 4. The Atlas Is Precise and Useful (A)

The atlas correctly identified:
- **Four architectural layers** (presentation, business logic, hardware abstraction, infrastructure) with specific files per layer
- **Entry points:** `Sources/main.swift`
- **Key design patterns:** "multi-tier adaptive controller architecture"
- **Technology stack:** Swift, SwiftUI, AppKit, CoreGraphics, CoreAudio, CoreBluetooth, CoreMIDI, IOKit, Sparkle 2, SPM

For a 24-file project, this is the right level of detail. Not overwhelming (80+ modules like Haley), not empty (like the incomplete Haley pipeline). Concise, accurate, immediately useful for orientation.

---

## What's Not Working

### 1. Impact Analysis Has Empty Graph (D)

`codrag_impact(file_path="Sources/PowerMateManager.swift", direction="all")` returned:
```
Nodes: 1 | Edges: 0
```

PowerMateManager.swift is the central orchestrator that imports from both transport files, the gesture engine, and is used by AppDelegate. It should have 5+ edges. The trace graph for this file is empty.

Meanwhile, `codrag_impact(file_path="Sources/AppDelegate.swift", direction="dependents")` returned 3 dependents correctly. So the impact tool works for some files but not others.

**Root cause hypothesis:** The pipeline used the Python engine backend (`"engine_backend": "python"`) rather than Rust. The Python parser may handle Swift differently — or may not support Swift at all. Some files get edges (AppDelegate has 52 incoming from the hub-files query), while others don't (PowerMateManager has 0 in the neighbors query). The edge data may come from reference/text matching rather than actual import parsing for Swift files.

**This is a significant gap for non-Python/non-TypeScript codebases.** CoDRAG's Rust parser targets Python and TypeScript. Swift import resolution likely falls back to text-based inference, which is inconsistent.

### 2. Symbol Search Returns No Signatures (B)

`codrag_search(query="PowerMateTransport", type="symbol")` returned:
```
- `PowerMateTransport` (symbol) @ `Sources/PowerMateManager.swift`:27
- `PowerMateTransportDelegate` (symbol) @ `Sources/PowerMateManager.swift`:19
```

Line numbers are present (good, this worked). Qualified names are shown. But no protocol definition, no method signatures, no associated types. For a Swift protocol, the signature would be:
```swift
protocol PowerMateTransport: AnyObject {
    var transportDelegate: PowerMateTransportDelegate? { get set }
    func start()
    func stop()
    var isConnected: Bool { get }
    func setLEDBrightness(_ brightness: UInt8)
}
```

The Phase 83 fix to include `signature`/`docstring` fields works when the trace nodes have that metadata. For Swift, the parser doesn't extract protocol/method signatures into node metadata. Same issue as noted for Haley — the retrieval formatter is correct, the pipeline data is missing.

### 3. Structural Audit Still Missing Cycles (B)

Same issue as Haley: 1 coupling hotspot found (AppDelegate, 52 deps), 0 cycle findings. The atlas found import cycles but the structural scanner reads from the legacy audit findings which don't have cycle data for embedded-mode projects.

The pipeline ran a full audit stage (62 findings), but those are the Tier 1 analyzer findings (large files, unused files, etc.), not the structural cycle findings that the Phase 83 scanner expects.

### 4. Antibodies Store Not Initialized (F)

`codrag_audit(action="antibodies")` returned:
```
Error: AntibodyStore not initialized. Call antibody_store.init(db_path) first.
```

The pipeline successfully derived 47 antibodies (from the 133 concepts), but the MCP server can't access them because the store isn't initialized in the daemon process. This is a wiring issue — the antibody derivation runs during the pipeline, but the antibody *store* used by the MCP server hasn't been initialized with the correct DB path for this project.

### 5. Impact Dependents for Hub File Shows Low Count

AppDelegate has "52 incoming dependencies" according to the structural audit, but `codrag_impact(direction="dependents")` only found 3. The 52 likely includes reference edges from docs and inferred edges, while the impact tool's dependents mode may only count `[calls]` and `[imports]` edges.

---

## What This Test Reveals About CoDRAG's Strengths and Weaknesses

### Strength: Knowledge Layer Is Exceptional

The combination of atlas + concepts + audit report creates a knowledge layer that far exceeds what any static analysis tool provides:

1. **Atlas** tells you what the project is and how it's structured
2. **Concepts** tell you why it's designed this way
3. **Audit report** tells you what's wrong and what to fix

For an agent arriving at this codebase for the first time, these three tools provide a complete mental model in under 10 seconds. No other tool (Sourcegraph, Cursor, CodeScene) generates this kind of integrated knowledge automatically.

### Weakness: Graph Quality Varies by Language

CoDRAG was built for Python/TypeScript codebases. On Swift:
- Import resolution is inconsistent (some files have edges, some don't)
- Symbol search has no signatures (parser doesn't extract Swift protocol/method signatures)
- Impact analysis is unreliable (PowerMateManager shows 0 edges despite being central)

The knowledge layer (concepts, atlas, audit report) works regardless of language because it's LLM-generated from code content, not parser-extracted. The structural layer (impact, symbol search, graph traversal) degrades on unsupported languages.

### Weakness: Pipeline Artifacts Not Always Accessible via MCP

The pipeline successfully:
- Generated 133 concepts → accessible via `codrag_concepts` ✓
- Ran audit with 62 findings → accessible via `codrag_audit report` ✓
- Derived 47 antibodies → **NOT accessible** (store not initialized) ✗
- Generated atlas → accessible via `codrag` ✓

The antibody gap is a wiring issue, not a generation issue. The data exists but the MCP server can't reach it.

---

## Comparison to Previous Tests

| Dimension | CoDRAG (self) | Haley | PowerMateReborn |
|-----------|--------------|-------|-----------------|
| **Size** | 1012 files, multi-language | 2747 files, Python + TS + React | 24 files, Swift |
| **Pipeline** | Iterative over months | Fresh, complete | Fresh, complete with concepts + antibodies |
| **Concepts** | 0 | 0 | **133** — first project with auto-concepts |
| **Antibodies** | 0 | 0 | **47** — first project with auto-antibodies (but inaccessible) |
| **Audit report** | Partial (structural fallback) | Failed (not found) | **Full LLM synthesis with grade + recommendations** |
| **Search quality** | B | A- | A+ (concepts in results) |
| **Impact quality** | Mixed | Mixed | Mixed (same graph gaps) |
| **Atlas quality** | B+ | A- | A (right density for project size) |

PowerMateReborn is the first project where the **complete knowledge pipeline** ran end-to-end: atlas → concepts → audit → antibodies. The result is a qualitatively different experience — concepts in search results, a real audit report with a health grade, and 133 pieces of architectural knowledge auto-extracted from 24 files.

---

## Top Issues to Address

| # | Issue | Severity | Root Cause | Fix Type |
|---|-------|----------|-----------|----------|
| 1 | Antibody store not initialized in MCP | High | Wiring gap — pipeline writes, MCP can't read | **Retrieval** — init store in server startup |
| 2 | Impact graph empty for most Swift files | High | Python parser doesn't resolve Swift imports well | **Pipeline** — improve Swift import inference or fall back to text matching |
| 3 | Structural audit missing cycles | Medium | Reads from legacy audit findings, not trace graph | **Retrieval** — query trace graph directly for cycles |
| 4 | Symbol search no signatures for Swift | Medium | Parser doesn't extract Swift protocol/method signatures | **Pipeline** — add Swift signature extraction |
| 5 | Hub count (52) vs dependents count (3) mismatch | Low | Different edge type filters | **Retrieval** — document or reconcile |

---

## The Bottom Line

**CoDRAG's knowledge layer (concepts, atlas, audit reports) is the real product.** On PowerMateReborn, it auto-generated 133 concepts that capture design rationale a senior developer would need hours of code reading to understand. The audit report gives an honest health grade with actionable recommendations. The atlas is precise and proportional to the project size.

**The structural layer (impact, symbol search, graph traversal) is the weak point.** It works well for Python/TypeScript but degrades on other languages. For a product that supports "any codebase," this needs either better multi-language parsing or honest scoping ("structural features work best with Python and TypeScript").

**The most impressive thing:** A 24-file Swift project, 7.4 minutes of pipeline time, and CoDRAG produced knowledge that would take a developer 2-3 hours of code reading to assemble manually. The concept "DDC/CI Reliability Collapse on Apple Silicon as Platform Betrayal" alone demonstrates understanding that goes beyond surface-level analysis — it identifies a real platform problem that affected the project's architecture. That's the kind of insight that justifies the product.
