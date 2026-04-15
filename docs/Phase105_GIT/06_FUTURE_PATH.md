# 06 — Path Forward After Phase 105

Phase 105 ships a primitive plus two on-demand consumers (TODO gate +
Atlas decoration). This document sequences what could come next, each
gated on dogfood evidence from the previous step. Do not commit in
advance.

## Principle

**Earn each next integration.** Phase 105 proves that git evidence is
cheap, trustworthy, and useful. Each subsequent phase begins with an
**unlock signal** — specific evidence that justifies expanding. Without
the signal, the phase stays shelved or shrinks.

## Phase 105.5 — Commit-grouped Untraced panel

**Unlock signal.** γ dogfood shows the churn primitive is trustworthy.
Eric confirms the Untraced scope panel feels noisy in daily use.

**What ships.** Backend: `last_commit_for_files(paths)` primitive added
to `git_evidence.py`. Frontend: when the Untraced scope panel shows a
group of files, collapse rows by the commit that last touched them.
Returns to the actual pain point that triggered the Phase 105
conversation.

**Why this first.** Direct user value on the surface where the
conversation began. Uses only the already-shipped primitive plus one
small helper. No coupling with roadmap, concepts, or the pipeline.

**Effort.** ~1 week (1 primitive + 1 API endpoint + 1 UI component).

## Phase 106 — New pipeline stage: GIT_EVIDENCE (major architecture)

**Unlock signal.** γ dogfood shows multiple consumers of `git_evidence`
would benefit from the same cached data being available at build time
instead of on-demand. Specifically: CATALOGUE wants churn in its LLM
prompts; CLUSTERING wants co-change pairs; AUDIT wants churn ×
complexity.

**What ships.** Promote `git_evidence` from a side-car module to a
first-class pipeline stage inserted between STRUCTURAL (1) and
INFERRED_EDGES (2):

```
Sync    1. STRUCTURAL
        NEW 1b. GIT_EVIDENCE       ← new, deterministic, cheap
        2.  INFERRED_EDGES
        ...
```

The stage writes `git_evidence.json` (or similarly-named sibling
artifact) as part of the pipeline manifest. Downstream stages read it
through the same `STAGE_INPUT_FILES` mechanism as other artifacts.

**Pre-requisite work:**

1. Audit the pipeline sequencing bug (memory-flagged). Do not add a
   stage while the state machine is unreliable.
2. Decide resume/selfheal behavior for the new stage.
3. Add to `index_destroy_project`, `STAGE_INPUT_FILES`,
   `STAGE_IS_DETERMINISTIC` (trivially `True`), etc.
4. `commit_message_index` and `cochange_pairs` implemented as part of
   this phase to give CATALOGUE and CLUSTERING something to consume.

**Effort.** ~2 weeks including state-machine integration and dogfood
tuning.

## Phase 107 — CATALOGUE + KNOWLEDGE evidence enrichment

**Unlock signal.** 106 has landed. Stage is stable. The on-demand
atlas integration still works (dual-path during transition).

**What ships.**

- CATALOGUE's LLM prompt augmented with a concise churn summary for
  each file being catalogued ("this file has churned 23× in 60 days
  by 4 authors, recently touched lines: …"). Produces richer summaries.
- KNOWLEDGE's embedding input optionally includes recent commit
  message text — `codrag_search` finds "recently changed" code via
  semantic proximity.

**Open questions:**

- Does KNOWLEDGE embedding change require a re-index? Probably yes.
  Coordinate with any re-embedding windows.
- CATALOGUE prompt delta — quantify before shipping that it actually
  improves summary quality.

**Effort.** Probably 1.5 weeks CATALOGUE, 1 week KNOWLEDGE experiment.

## Phase 108 — Roadmap retirement with GitHub-push coordination

**Unlock signal.** 106 has landed (so `commit_message_index` is
available at build time). The roadmap view is actively used. A user
reports that completed-but-still-proposed nodes are annoying.

**What ships.** The retirement pass designed in the original
brainstorm, now with the GitHub coordination gap closed.

**Required design work:**

1. Keyword-match quality check. If γ atlas decoration + deterministic
   matching produced clean results, proceed deterministic. Otherwise
   plan embedding-similarity scoring.
2. GitHub-push retire policy. Options:
   - **A.** Never retire `source="github"` nodes.
   - **B.** Retire locally + close the GitHub issue via two-way sync.
   - **C.** Retire locally + flag the issue for manual review.
3. `sprint_intelligence` coordination — how does retirement interact
   with scoring trajectories?

**Effort.** ~2 weeks.

## Phase 109 — CLUSTERING with co-change signal

**Unlock signal.** 106 + 107 shipped. CLUSTERING output is evaluated
and found to miss co-change-coupled modules.

**What ships.** Co-change pairs (already produced by 106's stage
output) become a first-class clustering signal alongside imports.

**Pre-work:**

- De-duplication design between clustering output and
  `opportunity_manager.py`'s coupling signals.
- Anchor-rename handling (`git log --follow` or equivalent).
- Support-threshold tuning per 107 dogfood data.

**Effort.** ~1.5 weeks.

## Phase 110+ — Concept promotion and narrative synthesis

Speculative. Not committed.

- **Concept seed promotion from commit messages + anchor churn.** The
  original T2 idea, now built on proven evidence from 106+.
- **LLM narrative synthesis** — "what should I work on next" prose
  grounded in fused evidence. Deferred until everything below it is
  quietly trustworthy.
- **Blame-enriched audit findings.** Could leapfrog others if user
  demand surfaces.
- **Temporal lens for ambient `codrag()`.** "What changed in the last
  N commits" as an MCP response type.

## Meta: when to abandon

If Phase 105 dogfood reveals any of these:

- TODO churn gate produces high false-positive rates that don't tune
  out → reconsider the whole approach. Maybe richer signals needed
  (line-level, not file-level).
- Atlas labels feel wrong or noisy → tune thresholds; if that doesn't
  fix it, remove the decoration (feature flag off).
- Users don't notice or care → stop investing. Keep the primitive for
  its own sake as internal tooling. Do not proceed to 105.5+.
- Pipeline sequencing bug reoccurs or new pipeline instability emerges
  → **do not do Phase 106.** Stay on-demand indefinitely.

This is a phase, not a crusade. Success is quiet trust, not feature
count.
