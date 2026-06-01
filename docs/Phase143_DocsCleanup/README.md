# Phase 143 — Docs Cleanup + Two-Repo Setup

> **The bet:** Before SourcePrep ships as Apache 2.0, the `docs/`
> folder needs a hard triage. Strategic IP moves out of public sight;
> shipped engineering decisions distill into ADRs; research/technical
> writing gets polished as credibility assets; the public mirror starts
> from a clean initial commit. This phase prepares the OSS surface
> for an unembarrassing first impression.

## Why this phase exists

The current `docs/` folder is the working journal of a project that
has been actively developed for 142 phases. It contains:

- Active business strategy (`Phase142_OSS-First/`, `ACQUIRER_MAP.md`)
- In-progress engineering planning (`Phase140_Prompt-Dogfood/`, others)
- Phase-by-phase decision records that read as scratch work
- Genuine technical research worth publishing
- The full architecture journey including incident postmortems
- `DISTRIBUTION_AND_REVENUE_PLAN.md` and other business strategy

Shipping this `docs/` directory as-is in the OSS public mirror would:

1. **Telegraph competitive intel** — Phase 142, ACQUIRER_MAP, and
   the business strategy docs reveal what we're optimizing for
2. **Read as messy** — half-finished planning thoughts give the wrong
   impression of product maturity to a Show HN reader
3. **Bury the good stuff** — genuine research like `EPISTEMOLOGY_SCORING.md`
   and `CURATED_TRACEABILITY_FRAMEWORK.md` should be front-and-center
   credibility assets, not lost in phase noise
4. **Lock out reversal** — once a doc is published under Apache 2.0,
   it's effectively permanent

Phase 143 is the bridge between "messy private dev repo" and
"polished public OSS mirror." It must complete before Phase 142
Part B (license application + repo restructure) can ship.

## Scope

In:

- **Doc triage** — every file in `docs/` tagged into one of four
  buckets: strategic-IP, active-planning, shipped-decision-ADR, or
  research-asset
- **ADR distillation** — past phases with shipped outcomes become
  one-page Architecture Decision Records in `docs/adr/`
- **Research polish** — `EPISTEMOLOGY_SCORING.md`, `CURATED_TRACEABILITY_FRAMEWORK.md`,
  `RUST_ENRICHMENT_ANALYSIS.md` and similar move to `docs/research/`
  and get a final edit pass for public consumption
- **Two-repo setup** — establish private dev repo (current location)
  + public mirror repo (new GitHub org, fresh init commit) with a
  documented sync workflow
- **New docs front door** — `docs/README.md` rewrite as a clean
  index for public readers
- **GitHub org + repo name decisions** — confirm `sourceprep` org
  availability + choose repo name

Out:

- Writing the actual OSS-facing CONTRIBUTING.md, SECURITY.md, README
  (those land in Phase 142 Part C — Phase 143 only provides skeletons)
- Trademark + legal review (Phase 144)
- License application (Phase 142 Part B)
- Building any product features

## Status

- [x] Phase scaffolded
- [ ] Doc triage spreadsheet drafted (every doc tagged)
- [ ] ADR template finalized
- [ ] Past-phase ADRs distilled (target: 8–15 ADRs from Phase 100+)
- [ ] Research docs polished + moved to `docs/research/`
- [ ] Strategic IP moved out of public-mirror path
- [ ] Two-repo structure operational (private dev + public mirror)
- [ ] Sync workflow documented in `OPERATIONS.md` (private)
- [ ] GitHub org + repo name confirmed
- [ ] `docs/README.md` rewrite shipped
- [ ] Phase 143 retro complete; ready to hand off to Phase 142 Part B

## Files in this phase

| File | Purpose |
|---|---|
| `README.md` | This file — phase summary and status |
| `IMPLEMENTATION_PLAN.md` | Ordered work (Parts A–G) with deliverables and acceptance criteria |
| (later) `DOC_TRIAGE.md` | The actual per-doc triage spreadsheet — generated during Part A |

## Success criteria

Phase 143 is **complete** when:

1. Every file in `docs/` is tagged with a bucket (strategic-IP /
   active-planning / shipped-ADR / research / public-policy)
2. ADR distillation produces at least one ADR per significant
   shipped phase from Phase 100 onward
3. Strategic IP and active planning are physically separated from
   the public-mirror tree (either via `.gitignore` exclusion or via
   the two-repo split)
4. The public mirror's first commit contains a clean `docs/`
   structure: `README.md`, `adr/`, `research/`, `architecture/`,
   and stubs for `CONTRIBUTING.md` + `SECURITY.md` (full content
   in Phase 142 Part C)
5. GitHub org `sourceprep` (or confirmed fallback) is reserved
6. The two-repo sync workflow is documented and tested with one
   round-trip (private dev → public mirror)

## Relationship to existing docs

| Existing doc | Phase 143 relationship |
|---|---|
| `docs/Phase142_OSS-First/OPEN_CORE_SPLIT.md` | This phase is a prerequisite. Phase 142 Part B cannot ship until docs are clean. |
| `docs/Phase142_OSS-First/SCRUTINY.md` §6 (history rewrite) | Phase 143 implements the two-repo strategy recommended there. |
| `docs/DISTRIBUTION_AND_REVENUE_PLAN.md` | Stays in private dev repo only (strategic IP). |
| All `PhaseNN_*/` directories | Each gets triaged: shipped → distill into ADR; active → keep private; abandoned → archive privately. |

## Dependencies

- **Blocks:** Phase 142 Part B (license application + repo restructure).
  Cannot ship the public mirror without docs cleanup first.
- **Blocked by:** None. Can start immediately.
- **Adjacent:** Phase 144 (legal pre-launch) — runs in parallel. The
  attorney work happens during the docs triage and they don't conflict.
