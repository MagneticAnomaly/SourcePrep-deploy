# Phase 136 — Dogfood Fixes

> **Status:** Phase plan / Parts being specced
> **Authored:** 2026-05-17
> **Scope:** consolidate open prep-MCP dogfood findings into one phase with
> single-finding Parts (hybrid: cluster when one fix covers many, split when
> findings are independent)

## Why this phase exists

The dogfooding rule in `CLAUDE.md` says every MCP tool call is also a test of
the product. Three rounds of live dogfooding (Phase 82 baseline 2026-04-07,
followups 17–20 across 2026-05-04 → 2026-05-13, Phase 122 Custodian planning
2026-05-13) have produced a growing list of prep-side findings that are
out-of-scope for the phase that surfaced them. They have been recorded in
`docs/Phase82_MCP-Dogfooding/` and in `MASTER_TODO.md` but never assigned an
owner phase.

Phase 136 is that owner. Each Part takes one finding (or one tightly-coupled
cluster) and ships it end-to-end: code fix + pytest + live MCP probe
documenting the before/after.

## Functional scope, not cosmetic

This phase is about **tool functionality, not naming or polish for its own
sake**. Brand-drift findings (LLM module summaries still containing the
legacy "CoDRAG" name — P82-F7, P82-F8) are explicitly **out of scope** —
they do not affect tooling correctness and remain open in `MASTER_TODO.md`
for future cycles. Defense-in-depth hardening of already-shipped work
(P82-F2 module-budget clip, P82-F3 batched-synthesis re-prompt) likewise
stays in `MASTER_TODO.md`.

## Parts

Numbering is a stable identifier. Work order is below.
**Updated 2026-05-17** after live dogfood probes against the rebuilt
index — see `00_Status_2026-05-17.md`.

| # | Part | Status | Cluster | Triggers folded in |
|---|---|---|---|---|
| 01 | File-role split for search ranking | open | Search ranking | `project_search_docs_bias` memory, 2026-05-12 dogfood |
| 02 | `prep_impact` — Rust parser indented imports | ✅ shipped 2026-05-18 (`e16023c8`) | Impact correctness | P122-D1, P122-D2, P122-D3, 19_Followup Gap #2 |
| 03 | No-arg `prep` atlas — regression guard *(demoted)* | open | Ambient context | P82-F5/F6 — not reproducible on rebuild |
| 04 | `prep_search` LOCATE → EXPLAIN auto-fallback | ✅ shipped 2026-05-18 (`9c80a83a`) | Search routing | P82-F4, 18_Followup §1, 19_Followup Gap #1, self-observed 2026-05-18 |
| 05 | Atlas role projection — task-named files dominate role tag | open | Role projection | 19_Followup Gap #3 |
| 06 | Staleness indicator on MCP responses | open | Tool ergonomics | FIX-9 |
| 07 | `detail` parameter for progressive disclosure | open | Tool ergonomics | FIX-8 |
| 08 | Cross-tool "Next Steps" suggestions | open | Tool ergonomics | FIX-7 |
| 09 | Synthesizer empty-output regression — 1795 concepts unvalidated, 1334 questions pending | open | Pipeline quality | 2026-05-17 rebuild telemetry |
| 10 | Spaghetti scorer + audit size fallback (large_files, synthesizer prompt) | ✅ shipped 2026-05-18 (`a8d4c02f`, `a595d9c2`) | Audit correctness | 2026-05-17 vs 2026-05-11 telemetry diff |
| 11 | Atlas "Stale" immediately after rebuild (consumed_changeset_run_id) | ✅ shipped 2026-05-18 (`96882585`) | Pipeline correctness | 2026-05-17 dashboard screenshot |
| 12 | Group reasoning cache Jaccard fallback | ✅ shipped 2026-05-18 (`6cf89eee`) | Pipeline quality | 2026-05-18 dashboard — 98 of 109 groups falsely stale |
| 13 | Swarm ownership gate + arrival hold | ✅ shipped 2026-05-18 (`d30a6ddf`) | Resource correctness | 2026-05-18 dashboard — two SwarmOrchestrators racing |
| 13b | Cluster module reuse Jaccard fallback | ✅ shipped 2026-05-18 (`0517df89`) | Pipeline quality | parallel to Part 12 |
| | P122-D3 cosmetic header fix | ✅ shipped 2026-05-18 (`96882585`) | Tool ergonomics | folded into Phase 136 scaffold commit |

## Work order

```
02 → 11 → 09 → 10 → 01 → 04 → 05 → 06 → 07 → 08 → 03
```

Part 11 (atlas staleness false positive) jumps ahead of 09/10: it's a
simpler fix (~15 LOC), highly visible in the dashboard, and may
co-affect other Phase 135.5 stages — auditing now prevents future
discovery.

**Rationale (revised 2026-05-17):**

1. **Active correctness bugs first.** Parts 02, 09, 10 are all currently
   reproducible regressions:
   - **02:** `prep_impact` undercount silently biases Custodian toward
     unsafe deletes.
   - **09:** synthesizer wall-time timeout drops 1334 questions per run.
   - **10:** spaghetti scorer scored 0 of 1961 files (vs 657 of 1902 six
     days earlier).
2. **Part 03 demoted.** Live `prep()` now returns full module parity
   (798/798 modules, 10/10 segments). The 2026-05-13 "1 of 10" bug is
   not reproducible against the rebuild. Part 03 now ships only the
   invariant test as a regression guard and goes last.
3. **Search routing fourth and fifth.** Part 01 (already specced) and
   Part 04 are paired halves of "`prep_search` works on natural-language
   queries." Part 04 may share test fixtures with Part 01.
4. **Atlas content quality** (Part 05) before **polish features**
   (06–08).
5. **Polish ordering inside Cluster F:** 06 (staleness) is a correctness
   signal — don't act on stale data — and ships before 07 (`detail`) and
   08 (next-steps), which are pure ergonomics.

## Testing methodology

Each Part has three layers of validation:

### Layer 1 — pytest (unit + integration)

Standard `tests/test_<topic>.py` with the regression case named explicitly.
Part 01's `tests/test_search_role_priors.py` plan is the template: name the
failing query, assert what the corrected ranker returns. Parts that need
graph fixtures (notably Part 02) build a tiny tmp-dir project and run a
real index.

### Layer 2 — live MCP probe (the "Phase 82 method")

Each Part's README includes a **Dogfood validation** section with:

- The exact MCP call to make against the running daemon
- The current broken output (paste verbatim)
- The expected fixed output

After implementation, the author re-runs the probe and pastes the new output
into the Part README. This is the loop that made the `17_Followup_2026-05-08.md`
scorecard credible — real calls, real diffs, real evidence.

### Layer 3 — phase scorecard

At phase close, `99_Scorecard.md` re-grades each MCP tool (`prep`,
`prep_search`, `prep_impact`, `prep_audit`, `prep_observe`, `prep_concepts`)
against the Phase 82 rubric (Signal / Noise / Consistency / Actionability /
Completeness). This is the artifact the next dogfooding pass picks up.

### Playwright — not used in Phase 136

None of the eight Parts surface in the dashboard React UI. All findings are
MCP server / search / impact / atlas-generation handlers (text in, text
out). If a future Part lands that touches the dashboard, it inherits a
Playwright requirement and the methodology section is updated.

## Methodology lifted from Phase 82

- **Per-tool rubric:** Signal, Noise, Consistency, Actionability,
  Completeness — letter-graded
- **Reproduction recipe per finding:** explicit `Test: <call> / Expected: …
  / Got: …` triple with code pointers
- **Then / Now scorecard format** for tracking across followups
- **Live MCP calls as primary validation surface,** not just unit tests
- **Scrutiny pass at Part close:** reverse-engineer for missed surface area
  (other readers of the changed artifact, related synthesis paths, broader
  test regressions)

## Out of scope

Tracked elsewhere — Phase 136 will not touch:

- **P82-F7 / P82-F8** — LLM module-summary brand drift ("CoDRAG" persisting
  in free-text summaries). Cosmetic, not functional. Remains open in
  `MASTER_TODO.md`.
- **P82-F2** — `module_budget_pct` safety clip in `_assemble_ambient_context`.
  Hardening on already-shipped Phase 82 follow-up FIX-16-1; not a
  user-surfaced finding.
- **P82-F3** — `_synthesize_batched` re-prompt loop. Architectural choice
  about batched-synthesis retry economics; needs its own design pass.
- **FIX-11** — observe/concepts boundary clarification. Partially closed by
  the 2026-05-08 `CLAUDE.md` rule-of-thumb addition.
- **P82-F1** — live `prep()` byte-count measurement. Verification of
  already-shipped FIX-16-1; folds into Part 03's dogfood validation.

## Phase close criteria

Phase 136 is done when:

1. All eight Parts have shipped (code + pytest + dogfood probe paste-in).
2. `99_Scorecard.md` is filled out with updated grades for all six MCP tools.
3. `MASTER_TODO.md` is updated: every Phase 136 trigger is checked off, and
   the deferred items (P82-F7/F8/F2/F3, FIX-11) are clearly labelled
   "deferred — not Phase 136 scope."
4. No new dogfood finding discovered during implementation is left
   unrecorded. New findings either become a Phase 136 Part (if the
   work order allows insertion) or get a `MASTER_TODO.md` entry with a
   reproduction recipe.

## Cross-references

- `docs/Phase82_MCP-Dogfooding/` — methodology baseline (README +
  `01`–`05` per-tool grades, `06`–`13` deep dives, `16`–`20` followups)
- `docs/Phase82_MCP-Dogfooding/07_Prioritized_Fix_Plan.md` — original
  FIX-1 through FIX-11 list (FIX-7/8/9 became Parts 08/07/06)
- `docs/MASTER_TODO.md` — line-anchored entries for P82-F* and P122-D*
- `docs/Phase122_FeatureUtilizationAudit/` — Custodian context for
  why Part 02 is the urgent fire
