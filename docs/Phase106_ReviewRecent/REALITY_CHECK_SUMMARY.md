# Phase 106: Reality-Check Summary of Phases 107-111

> **Date:** 2026-04-15
> **Scope:** Read-only verification of Phase 107-111 first-draft READMEs against current working tree + git log.
> **Method:** Three parallel Explore subagents (Wave 1: 107, 108, 110) + two parallel (Wave 2: 109, 111). Each agent cited file:line or commit SHA for every verdict. No tests run, no code executed.

---

## Headline finding

**The recent build is significantly ahead of the recent plans.** The Phase 107-111 READMEs were drafted from Phase 74-105 doc summaries without re-verifying against code. Many claims presented as "still open" had already shipped in the Phase 105a/105b series, the intent/path-weights series, and the immune/SARIF series.

A read of the READMEs in their original form would have led an implementer to re-do 40-60% of work already in the tree.

---

## Per-phase verdict roll-up

| Phase | FIXED in place | PARTIAL | STILL-OPEN | NEEDS-VERIFICATION | Framing health |
|---|---|---|---|---|---|
| **107** Pipeline Stability | 13 (§4.1 entire) + F-66 + F-41 | F-68, F-15, incremental recovery UI | §4.2 Atomic Stage Handoff (8) | §4.5 WAL audit (4) | **~65% stale** — §4.1 shouldn't have been a TODO list at all |
| **108** MCP Quality | FIX-1/2/3/4/6/9 + SARIF + role inference | FIX-8 client-aware (infra partial) | FIX-5, FIX-7, MCP-side rules flow | §4.3 swarm e2e, §4.5 resources/prompts | **~55% stale** — tool count wrong (5→6) |
| **109** Knowledge Layer | Phase 84 formalization (assertion/doc_links/supersede), SARIF, immune core, antibody store init, auto-seed, watcher wired | Lock-file filter, dashboard panel render, concept lifecycle tests | **Concept quality validation (0/8)**, severity recalibration (0/7), L2 scoped (0/5), AMBIENT_INJECT wiring | Dashboard live-render | **~30% stale** — plumbing mostly shipped; **validation never happened** |
| **110** Retrieval Intelligence | 7-intent classifier, path weights (config + ranking), semantic chunking (scoped MVP), role param, structural decomposition | Path-weight flow through LOD/atlas/trace, MCP response surfacing | coverage_ratio wiring, EXAMPLE/COMPARE polish, dashboard path_weights UI, R@1 re-benchmark, Phase 104 lens verification | §4.6 sub-atlas | **~70% stale** — Problem Statement largely describes superseded architecture |
| **111** MVP Readiness | Haley Q1+Q2, free tier, Fast Sync graceful skip, DevToolbar gating | Envelope format sampling, field-name consistency | **NEW: `/admin/*` unguarded, test-model ungated, runtime `CODRAG_DEV_MODE`**, SSE migration (0/7), MCP resilience (0/4), path_weights dashboard UI | Golden path QA (10), build-time checks | **~60% stale + new security gap** |

---

## Dependency implications (revised)

Original MASTER_INDEX recommended: **107 → 109 + 110 (parallel) → 108 → 111**.

Given the reality check, the real work graph is:

```
Phase 107 (now ~30% of original scope)
    ├─ §4.7 Recovery UI wiring  ── small ─→
    ├─ §4.2 Atomic StageHandoff ── large ─→ (decide: MVP-critical or defer)
    └─ §4.5 WAL audit           ── medium ─→

Phase 109 (quality validation dominates)
    └─ §4.1 Concept quality on 3+ real repos ← LARGEST REMAINING RISK across all five phases
    └─ §4.3 Severity recalibration
    └─ §4.5 AMBIENT_INJECT verification into tool_codrag responses

Phase 110 (polish, not core build)
    └─ coverage_ratio wiring
    └─ EXAMPLE + COMPARE intent polish
    └─ Dashboard path_weights UI (cross-cuts with 111 §5.8)

Phase 108 (3 fixes + one decision)
    └─ FIX-5 hub ranking multiplier
    └─ FIX-7 audit severity (overlaps with 109 §4.3)
    └─ FIX-8 client-aware rules flow (decide: MCP-driven regen vs install-time)
    └─ FIX-9 ← closed, no action

Phase 111 (security + surface trim)
    └─ §5.0 NEW — admin/* guards, CODRAG_DEV_MODE startup-only ← BLOCKING
    └─ §5.4 SSE consolidation (17 pollers)
    └─ §5.7 MCP resilience
    └─ §5.8 dashboard path_weights UI + marketing copy audit
```

**Revised execution order:** **111 §5.0 (security, blocking) → 109 §4.1 (quality, highest risk) → parallel (107 Recovery UI, 110 polish, 108 fixes, 111 §5.4 SSE) → 111 §5.1 golden-path QA.**

---

## Cross-cutting surprises

1. **Phase 105a/b is done but invisible in the plans.** 13 items in 107 §4.1, the "Initialize Concepts" button in 109 §4.2, and multiple Haley API inconsistencies were silently closed by the 105 series. The first-draft READMEs didn't cross-reference recent commits.

2. **Audit severity is a shared weak spot.** 108 FIX-7 and 109 §4.3 are the same underlying work. Consolidate ownership.

3. **Path weights are a cross-phase consistency problem.** Shipped in backend (110), celebrated on marketing (111 §5.8), but not writable via dashboard UI (111 new item). The plans scattered the pieces; the gap is at the UI layer only.

4. **Concept quality validation has no owner in any plan.** Every phase assumes concepts work; none takes responsibility for proving they do on a real corpus. This is the single largest unvalidated assumption in the knowledge layer.

5. **AMBIENT_INJECT is half-wired.** `de4a6463` wired alert injection into "ambient context"; whether that context flows into `tool_codrag` responses needs a 5-minute verification. This is the killer feature for AI-agent use and should be checked in 109 §4.5 before shipping.

6. **New security gap not in any prior phase.** `/admin/*` endpoints (quarantine-project, block-endpoint, approve-config) and `test-model` are callable without auth or dev-mode guards. This is a hard-blocker for any public release and wasn't surfaced in Phase 101's dev-mode research.

---

## Recommended next step (Option D candidate)

Two candidates for deep-dive re-spec:

- **Phase 109 (Knowledge Layer Quality Validation)** — highest risk, largest unknown. Plumbing is shipped; we have no evidence it produces useful output. A focused re-spec could define: which repos to seed, grading rubric, iteration loop on seeder prompts, pass/fail for AMBIENT_INJECT e2e.
- **Phase 111 §5.0 Security Gaps** — smallest scope, blocking for MVP. A focused re-spec could enumerate all unguarded endpoints, choose a guard strategy (decorator + central allow-list vs per-route), and add a ruff/pytest rule that flags new unguarded admin routes.

My recommendation: **111 §5.0 first (small, blocking, ~1 day), then 109 concept-quality validation sprint (larger, highest remaining risk, ~1 week).**

---

## Artifacts

- `docs/Phase107_Pipeline-Stability/README.md` — reality-checked in place
- `docs/Phase108_MCP-Agentic-Quality/README.md` — reality-checked in place
- `docs/Phase109_Knowledge-Layer/README.md` — reality-checked in place
- `docs/Phase110_Retrieval-Intelligence/README.md` — reality-checked in place
- `docs/Phase111_MVP-Readiness/README.md` — reality-checked in place (incl. new §5.0 Security Gaps)
- `docs/Phase106_ReviewRecent/MASTER_INDEX.md` — original index, unchanged
- `docs/Phase106_ReviewRecent/GAP_ANALYSIS.md` — original gap analysis, unchanged
- `docs/Phase106_ReviewRecent/REALITY_CHECK_SUMMARY.md` — this file

Each revised README has a top banner noting "reality-checked 2026-04-15" and a new §1.5 section with claim-by-claim verdicts and evidence citations. Every `[ ]` TODO has a status tag: `[FIXED: <sha>]`, `[PARTIAL]`, `[STILL-OPEN]`, or `[NEEDS-VERIFICATION]`.
