# 05 — Risks for Option γ

Scoped to the risks that actually apply to the Phase 105 scope
(`git_evidence.py` + TODO churn gating + Atlas hub & hot-zone
decoration). Replaces the original T1-era risk list.

## Risks that apply

### R1 — False-positive TODO demotion

**Scenario.** A TODO in a stable infrastructure file that legitimately
hasn't been touched in 6+ months gets demoted despite still being a
real open item.

**Likelihood.** Medium on long-lived repos. Low-to-medium here.

**Mitigation.**

- Demotion (P3), not deletion. Visible, just deprioritized.
- Generous default (180 days).
- Rollback flag: `settings.git_evidence.enabled = false`.
- Acceptance gate 5: zero live TODOs incorrectly demoted on manual
  review.

### R2 — Misclassified atlas hubs

**Scenario.** A hub gets labeled `stable` or `evolving` in a way that
does not match reality — e.g. a file marked `stable` because this
window's commits happened to miss it, or `fragile` from a single
multi-author refactor burst.

**Likelihood.** Medium at threshold boundaries. The labels are coarse
by design so most cases land clearly in one bucket.

**Mitigation.**

- Thresholds are module-level constants, tunable in one place.
- Unknown state for paths absent from churn map — atlas emits today's
  format in that case, no false labeling.
- Rollback flag: `settings.git_evidence.atlas_decoration = false`
  (independent of TODO gate flag).
- Acceptance gate 6: Eric spot-checks labels on this repo before
  shipping.
- Labels are deterministic, not LLM-generated — a bad label is fixable
  by threshold tuning, not prompt engineering.

### R3 — Shallow clone in CI / customer repos

**Scenario.** Repo is shallow-cloned; `git log` only sees recent
commits; files appear "untouched" when they're absent from history.

**Mitigation.**

- `git rev-parse --is-shallow-repository` check on module init.
- Shallow → evidence returns empty churn; TODO gating skipped; atlas
  labels are all `unknown` (no decoration rendered).
- One-time warning log.
- Scanner and atlas both fail open — no exceptions, no regressions.

### R4 — Atlas token budget creep

**Scenario.** Scope creep in a follow-up phase adds more atlas
decorations without discipline. Atlas bloats. MCP ambient response
loses compression advantage.

**Mitigation.**

- Acceptance gate 8 locks Phase 105 to < 50 token growth.
- Spec rules in `04b_INTEGRATION_ATLAS.md`: no raw numbers; labels
  one-word each; hot zones capped at 5.
- Any later phase adding atlas decoration must restate a token budget
  gate.

### R5 — Cache reset gap (repeat F-78 pattern)

**Scenario.** New cache directory added; `index_destroy_project`
doesn't know about it; orphan `git_evidence/` lingers after reset.

**Mitigation.**

- Acceptance gate 2: destroy removes `git_evidence/`.
- Registered explicitly alongside existing stores.

### R6 — Performance on very large repos

**Scenario.** 50k-file, 5-year-history customer repo. `git log
--numstat --since=60 days` is slow.

**Likelihood.** Low for Phase 105 — consumers are the TODO scanner
(bounded) and the Atlas (called once per build).

**Mitigation.**

- `--max-count 2000` cap.
- Cache built on first use, reused until HEAD changes.
- Caps are per-project configurable later if needed.

### R7 — Coordination with `sprint_intelligence.py` scorer

**Scenario.** Scorer reads `priority` as input. Our TODO gate adjusts
priority. Score movement could surprise users.

**Likelihood.** Low — priority changing is the scorer's intended input.

**Mitigation.** None preemptively. Post-ship dogfood check confirms
score movement on demoted TODOs is reasonable (downward, proportional).

### R8 — Filesystem permission issues reading `.git`

**Scenario.** Unlikely; some container setups.

**Mitigation.** Subprocess errors caught; evidence unavailable;
callers fail open.

## Risks that no longer apply

- **Triangulated noise.** No fusion is happening in Option γ.
- **Keyword matching is too coarse.** No keyword matching.
- **GitHub issue divergence from auto-retire.** Option γ never
  retires.
- **Scorer competition from churn boost.** Option γ doesn't boost
  roadmap scores.
- **Concept store coupling.** Option γ doesn't touch concepts.
- **Opportunity surface duplication.** No new node sources.
- **T2 concept promotion scope creep.** Deferred to a future phase.
- **New pipeline stage sequencing risk.** Option γ uses on-demand
  module access; no new stage.
- **LLM prompt changes.** Atlas labels are deterministic post-process;
  no LLM prompt touched.

## Open questions for implementation

### Q1 — Exact `source_ref` shape for `todo_scan` nodes

Assumed `"file:<path>:<line>"`. Confirm in `todo_scanner.py` during
implementation.

### Q2 — Project root resolution helper

Standalone vs embedded mode differ. Identify canonical resolver in
`services/`.

### Q3 — Settings namespace

Where should `settings.git_evidence.*` keys live? Check
`settings_store.py` conventions.

### Q4 — Calendar days vs commit count for windows

Default: 180 calendar days for TODO gating, 60 for hub classification.
Alternative: "last N commits". Ship calendar; revisit only if dogfood
shows quiet-period failures.

### Q5 — Directory depth for hot zones

Default: 3 segments deep. Tune during dogfood if granularity wrong.

### Q6 — Atlas hub ordering after grouping

Today hubs are ordered by edge count. When we group by label, do we
keep original order within each group, or re-sort? Recommend: preserve
original order within each group — no ordering change semantically,
just visual grouping.

### Q7 — Atlas LLM path vs deterministic path

`generator.py` has multiple atlas-generation paths (`generate`,
`generate_structural`, `generate_segmented`). Need to identify which
paths hit line 469 and whether decoration should apply to all or just
the root-atlas path. Recommend: decoration in deterministic
formatting helpers only; LLM paths keep their existing prose.

All have safe defaults; none block implementation.

## Summary

Eight active risks. Four have mitigation via acceptance gates; two
via rollback flags; two accepted as low-likelihood with post-ship
dogfood checks. None are blocking.
