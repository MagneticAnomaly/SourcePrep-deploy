# Phase 22: Epistemic Trace — Visual Overview

> **One-page summary.** For implementation details see `PATH_FORWARD.md`.

---

## What We Have Today

```
┌──────────────┐        ┌──────────────┐
│  Rust Engine │ ───►   │  3b LLM Pass │
│  (tree-sitter)│       │  (augmenter) │
└──────────────┘        └──────────────┘
       │                      │
  Structural graph       Flat overlay
  nodes + edges          summary + role
  (code only)            (first 30 lines)
       │                      │
       ▼                      ▼
  ┌───────────┐         ┌──────────────┐
  │ .md files │         │ Every file   │
  │ = EMPTY   │         │ treated the  │
  │ NODES     │         │ same way     │
  │ (no edges,│         │ (shallow)    │
  │  no parse)│         │              │
  └───────────┘         └──────────────┘
```

**Problems**: Docs are disconnected. Long files lose 95% of content. No cross-references. No iterative deepening.

---

## What We're Building

```
                    THE EPISTEMIC PIPELINE
                    ═══════════════════════

  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │   PASS 0 ── Rust Structural Trace ── ~100ms             │
  │                                                         │
  │   Code:  tree-sitter → symbols + import edges           │
  │   Docs:  NEW regex scanner → sections + refs + links    │
  │   All:   content hashes, section digests with rankings  │
  │                                                         │
  │   Result: Rich graph. Docs finally have edges.          │
  │                                                         │
  └────────────────────────┬────────────────────────────────┘
                           │
                           ▼
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │   PASS 1 ── 3b Fast Catalogue ── ~10 min                │
  │                                                         │
  │   Strategic snippets: head + Rust-ranked hot sections   │
  │   (not blind first-100-lines — targeted reads)          │
  │                                                         │
  │   Output per node:                                      │
  │     summary + role + confidence + related_files         │
  │                                                         │
  │   Long files (>500 lines): chunked pre-summarization    │
  │                                                         │
  └────────────────────────┬────────────────────────────────┘
                           │
                           ▼
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │   PASS 0.5 ── Rust Validates LLM Hypotheses ── ~5ms     │
  │                                                         │
  │   3b said "FileA relates to FileB"                      │
  │     → Rust checks: do both nodes exist? conf >= 0.7?    │
  │     → YES: add "inferred" edge to graph                 │
  │     → NO:  discard                                      │
  │                                                         │
  │   Rust-extracted doc refs + LLM hypotheses agree?       │
  │     → Mutual confirmation → confidence boosted to 1.0   │
  │                                                         │
  │   Result: Graph now has semantic edges, validated.      │
  │                                                         │
  └────────────────────────┬────────────────────────────────┘
                           │
                           ▼
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │   PASS 2 ── 14b Epistemic Enrichment ── ~60 min         │
  │                                                         │
  │   Per node (reverse-topological order):                 │
  │     source + 3b summary + ALL neighbor summaries        │
  │     + structural edges + inferred edges + doc refs      │
  │                                                         │
  │   Produces:                                             │
  │     domain_tags        (monetization, auth, ui...)      │
  │     architecture_layer (presentation, data, infra)      │
  │     design_pattern     (singleton, observer, MVC)       │
  │     subsystem          (ad-framework, voting-engine)    │
  │     cross_references   (doc↔code links)                 │
  │     tech_debt          (stubs, TODOs, dead code)        │
  │     epistemic_score    (0.0–1.0: how well understood)   │
  │                                                         │
  └────────────────────────┬────────────────────────────────┘
                           │
                           ▼
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │   PASS 3 ── 14b Cluster Synthesis ── ~15 min            │
  │                                                         │
  │   Group nodes by domain_tags → subsystem clusters       │
  │   Per cluster: generate module-level summary            │
  │                                                         │
  │   "The ad-framework subsystem consists of 6 files,      │
  │    handles interstitial + banner ads, is partially      │
  │    stubbed, depends on Firebase, documented in 3 docs"  │
  │                                                         │
  │   Creates virtual module:* nodes in the graph           │
  │                                                         │
  └────────────────────────┬────────────────────────────────┘
                           │
                           ▼
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │   PASS 4+ ── Continuous Deepening ── converges          │
  │                                                     ◄─┐ │
  │   Re-enrich nodes whose neighbors changed             │ │
  │   Priority: biggest score-change first (BP-inspired)  │ │
  │   Detect: stale doc refs, contradictions, drift       │ │
  │   Stop when: all epistemic scores >= 0.95             │ │
  │                                                       │ │
  │   ► loops back until convergence ─────────────────────┘ │
  │                                                         │
  └─────────────────────────────────────────────────────────┘
```

---

## The Key Innovations

### 1. Rust as Scout, LLM as Thinker

```
  Rust reads FULL file (microseconds)
    │
    ├── extracts sections, refs, links, status markers
    ├── ranks sections by importance (ref density)
    ├── produces a digest stored in graph metadata
    │
    ▼
  LLM reads STRATEGIC EXCERPTS (head + top sections)
    │
    ├── sees 300 lines that MATTER instead of 100 random lines
    ├── has Rust-provided structural context (neighbors, refs)
    │
    ▼
  Result: Full-file understanding at fraction of the token cost
```

### 2. Hypothesis-and-Test Loop

```
  LLM hypothesizes  ──►  Rust validates  ──►  Graph enriched
       │                       │                     │
  "FileA relates         "Both nodes              Inferred edge
   to FileB"              exist? Yes.              added with
                           Conf >= 0.7?            kind: inferred
                           Yes. Add it."
                                │
                           "FileC relates
                            to FileZ"
                                │
                           "FileZ doesn't
                            exist. Discard."
```

### 3. Epistemic Score = How Well We Understand

```
  Score Components:
  ┌─────────────────────────┬────────┐
  │ Structural completeness │  0.25  │  Has symbols, imports, edges?
  │ Semantic richness       │  0.25  │  Domain tags, patterns, layer?
  │ Cross-reference density │  0.20  │  Connected to docs + neighbors?
  │ Temporal currency       │  0.15  │  Recently validated? Not stale?
  │ Neighbor consistency    │  0.15  │  Neighbors agree on role?
  └─────────────────────────┴────────┘
                    │
                    ▼
            Composite: 0.87
            (needs more cross-refs to hit 0.95)

  Decay rules:
    Neighbor re-enriched  →  score × 0.95  (gentle nudge)
    Referenced doc updated →  score × 0.90  (re-check)
    Source file changed   →  score = 0.00  (full reset)
    Trace rebuilt         →  score × 0.80  (re-validate)
```

---

## Implementation Sprints

```
  Sprint 1 ─── Rust Markdown Extraction ──────────── 3-4 days
  │             markdown.rs: sections, refs, links, digests
  │             Docs get graph connections for the first time
  │
  Sprint 2 ─── Strategic Snippets + Augmenter ────── 3-4 days
  │  (parallel) _get_strategic_excerpt(), doc prompts,
  │             related_files field, chunked summarization
  │
  ├─────────── Quick wins ship here (~1 week) ──────────────
  │
  Sprint 3 ─── Pass 0.5: LLM→Rust Re-Trace ──────── 4-5 days
  │             incorporate_inferred_edges(), validation
  │
  Sprint 4 ─── Pass 2: 14b Epistemic Enrichment ─── 8-10 days
  │             Deep per-node enrichment, epistemic scoring
  │
  Sprint 5 ─── Pass 3: Cluster Synthesis ─────────── 5-6 days
  │             Module-level understanding, virtual nodes
  │
  Sprint 6 ─── Pass 4+: Continuous Loop ──────────── 6-8 days
  │             Convergence, drift detection, scheduling
  │
  └─────────── Full pipeline: ~5-6 weeks ───────────────────
```

---

## Before & After

### Before (current)

```
  File: Docs/ADS_FRAMEWORK_STATUS.md

  Graph:    ○ (bare node, zero edges)
  Summary:  "Documentation file for ad framework status"
  Role:     "documentation"
  Score:    N/A
```

### After (with pipeline)

```
  File: Docs/ADS_FRAMEWORK_STATUS.md

  Graph:    ○──references──► AdManager.swift
            ○──references──► BannerView.swift
            ○──references──► AdConfiguration.swift
            ○──links_to───► ADS_QUICK_REFERENCE.md
            ○──inferred───► InterstitialAdManager.swift
            ○──member_of──► module:ad-framework

  Summary:  "Master status tracker for the ad framework.
             Documents 6 components across interstitial and
             banner ad subsystems. 4 complete, 2 pending
             backend integration. References Firebase
             dependency for ad serving."

  Epistemic:
    domain_tags:       [monetization, ads]
    architecture_layer: documentation
    doc_type:          reference
    doc_status:        active (partially stale — section 3
                       references AdController, renamed to
                       AdManager in commit abc123)
    epistemic_score:   0.91
```

---

## Research Foundation

| Design Decision | Validated By |
|---|---|
| Hierarchical graph + community summaries | Microsoft GraphRAG (2024) |
| LLM hypothesizes → Rust validates | KARMA multi-agent KG enrichment (2025) |
| AST → code knowledge graph | KG-based Repo-Level Code Gen (2025) |
| Bottom-up topological enrichment | RepoAgent, EMNLP 2024 |
| Iterative convergence loop | Belief Propagation (Pearl 1988, Yedidia 2003) |
| Doc↔code drift detection | IEEE Documentation Drift Survey (2025) |
| Tree-sitter structural context | Aider repomap (2023) |
| KG as evolving agent memory | Dynamic Knowledge Memory survey (2025) |

---

## File Index

| Document | Purpose |
|---|---|
| **`OVERVIEW.md`** | This file — visual quick-read |
| `README.md` | Master strategy and thesis |
| `PATH_FORWARD.md` | Implementation plan + research validation |
| `MULTI_PASS_PIPELINE.md` | Detailed pass-by-pass prompt design |
| `EPISTEMOLOGY_SCORING.md` | Scoring system deep dive |
| `DOC_MINING_STRATEGY.md` | Documentation-specific enrichment |
| `RUST_ENRICHMENT_ANALYSIS.md` | Rust pass analysis + re-trace theory |
