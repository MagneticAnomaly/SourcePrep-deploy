# 00 — Feasibility Audit

**Date:** 2026-04-11
**Purpose:** Check every Prep capability an essay depends on against the actual source code. Honest signal, not optimism.

This file exists because the first content brainstorm drifted into capabilities Prep doesn't currently have. Everything below was verified by code inspection on the dates shown.

## Summary table

| Capability | Status | Exposed via | Notes |
|---|---|---|---|
| Cycle detection | ✅ Works | `prep_audit` (structural scan) | Tarjan's SCC in `src/prep/core/audit/analyzers/circular_deps.py` |
| Hub file ranking | ⚠️ Works but simpler than expected | `prep_audit`, Atlas | **Z-score on in-degree**, not PageRank. See Aider comparison. |
| Impact analysis (blast radius) | ✅ Works | `prep_impact` MCP tool | Transitive via `max_hops` (default 2). File- and symbol-level. |
| Atlas / codebase overview | ✅ Works, scale-untested | `prep` ambient context, HTTP API | Real implementation in `src/prep/core/atlas/generator.py`. Not tested >~3k files. |
| Rust source parsing | ✅ Works | Rust engine → Python pipeline | `engine/crates/prep-parser/src/rust_lang.rs`, tree-sitter-rust |
| Concepts + antibodies (constraint checking) | ❌ Framework only | `prep_audit action="antibodies"` lists them | **Triggers don't fire at runtime.** Data model exists; monitoring loop does not. See below. |
| Indexing scale | ⚠️ Tested to ~2k files | — | 17 real test repos in `tests/eval/real_repos/`, none above ~2k. No evidence of successful 5k+ runs. |
| External repo registration | ⚠️ Backend exists, UX unclear | `prep init`? project registry API | Works but the user-facing flow is under-documented. Test manually before publishing scenarios that assume it. |

## Detail: things that affect the essay plan

### Hub ranking is z-score, not PageRank

Implementation: `src/prep/core/audit/analyzers/hub_bottlenecks.py`. The algorithm is:

1. Compute in-degree for every node in the import graph.
2. Compute mean + standard deviation of in-degree.
3. Flag nodes whose z-score > 2.0 and whose in-degree ≥ 8 as "hub bottlenecks."

This is outlier detection by fan-in, not centrality. It answers "which files have unusually many inbound imports" correctly. It does *not* answer "which files are structurally most important" the way PageRank would (PageRank weights an edge by the importance of its source, so being imported by an important file counts more than being imported by a leaf). For small and medium codebases these often agree. For large codebases they can diverge meaningfully.

**Implication for essays:** The Aider comparison essay (#04) must be honest about this. Prep's hub ranking is simpler than Aider's. The comparison still has interesting angles — z-score outlier detection has its own properties, and Prep's atlas surfaces more than just hub files — but the essay cannot claim Prep ranks hubs better. If the comparison ends up suggesting Prep should adopt PageRank, that is itself a finding worth writing about.

### Antibodies: framework exists, triggers don't fire

Files: `src/prep/core/antibodies.py`, `src/prep/core/antibody_derivation.py`. The data model is real — `suggest_antibody()` extracts triggers from concept assertions (import patterns, file modifications, regex matches). `prep_audit(action="antibodies")` lists what was derived. Tests in `test_antibodies.py` cover serialization/deserialization.

What is missing: there is no evidence of a runtime monitor that evaluates antibodies against code changes and emits alerts. No end-to-end test fires an antibody in response to a violation. The "immune system alerts in `prep()` ambient context" described in CLAUDE.md appears to be aspirational.

The memory note `project_pipeline_sequencing_bug.md` ("deep enrichment stages don't advance; state machine regressions from Phase 76/89/91/92") is related but not the whole story — those phases fixed state machine problems in enrichment, not the antibody firing gap.

**Implication for essays:** The originally planned "architecture antibody" essay is killed. It cannot be honestly demonstrated today. The replacement is `05_where_prep_fails.md`, which catalogs this exact gap (among others) as part of the honest dogfooding piece.

### Aider's repo map — claim verified

Verified against https://github.com/Aider-AI/aider/blob/main/aider/repomap.py:

- Line 368: `import networkx as nx`
- Line 470: `G = nx.MultiDiGraph()`
- Lines 518–525: `nx.pagerank(G, weight="weight", **pers_args)` with optional personalization

So Aider uses **personalized PageRank via `networkx.pagerank`** on a graph whose nodes are files, whose edges are weighted by symbol references extracted by tree-sitter tags. The Aider docs page at https://aider.chat/docs/repomap.html only says "graph ranking algorithm" — cite the source file for specificity.

Personalization biases the ranking toward files relevant to the current chat context, which is a distinct design choice from Prep's static z-score outlier detection. The comparison essay can honestly examine this tradeoff.

### Scale: realistic targets

17 real test repos exist in `tests/eval/real_repos/`. None are larger than ~2k files. Max observed in committed test artifacts: cobra-go and gin-go (both ~2k). There is no committed evidence that Prep has successfully indexed Zulip (~5k Python files), Django (~3k), or Supabase end-to-end.

**Implication for essays:** First experiments run against `tests/eval/real_repos/` candidates, not aspirational targets. A separate scale test should be run *before* committing to essays that assume it works on Django-size codebases. If the scale test fails, the failure itself becomes content for essay #05.

## What was killed

| Essay idea | Reason |
|---|---|
| "The architecture antibody" | Antibody triggers don't fire; cannot demonstrate end-to-end |
| "500 lines of Python" implementation | Prep is not a 500-line project; format collision |
| "Skills vs MCP" rebuttal to Willison | No genuine disagreement; borrow-audience play |
| "Four failure modes" taxonomy | Invented on the spot with no evidence behind categories |

## What this unlocks

Five essay plans that are all grounded in capabilities that actually exist today:

1. **Cycles** — uses `prep_audit` + `circular_deps.py`. Zero dependency on half-built features.
2. **Hub file problem** — uses `prep_impact` + hub detection. Honest about z-score limitation.
3. **Day zero** — uses atlas generation. Scale-bounded to test repos.
4. **Aider comparison** — uses atlas + Aider's actual repo map output. Accurate about both algorithms.
5. **Where Prep fails** — uses the audit itself as raw material. Converts weakness into credibility.
