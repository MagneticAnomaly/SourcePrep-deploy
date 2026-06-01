# Phase 143 — Implementation Plan

> Ordered work to clean the `docs/` folder and establish a two-repo
> private+public structure before OSS launch.

## Part A — Doc triage (every file, every directory)

**Goal:** every file in `docs/` tagged with a bucket.

**Buckets:**

| Bucket | Examples | Destination |
|---|---|---|
| `strategic-IP` | `Phase142_OSS-First/*`, `Phase143_*/*`, `Phase144_*/*`, `ACQUIRER_MAP.md`, `DISTRIBUTION_AND_REVENUE_PLAN.md`, `PARALLEL_LANES_*.md` | Private dev repo only; never published |
| `active-planning` | Current `PhaseNN_*/` directories where work is unshipped | Private dev repo only; revisit when work ships |
| `shipped-ADR` | Past `PhaseNN_*/` directories where the work is in production | Distill into 1-page ADR; publish |
| `research` | `EPISTEMOLOGY_SCORING.md`, `CURATED_TRACEABILITY_FRAMEWORK.md`, `RUST_ENRICHMENT_ANALYSIS.md`, benchmark reports | Polish; move to `docs/research/`; publish |
| `architecture` | High-level system docs that aren't phase-bound | Move to `docs/architecture/`; publish |
| `public-policy` | CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, LICENSE-AUDIT | Stubs in Phase 143; full content in Phase 142 Part C + Phase 144 |

**Deliverable:** `docs/Phase143_DocsCleanup/DOC_TRIAGE.md` — a table
listing every file in `docs/` with its bucket assignment and a
one-sentence rationale.

**Acceptance:** 100% of files in `docs/` accounted for. No file left
ambiguous. Disagreements escalate to Eric for adjudication, recorded
in the triage doc.

## Part B — ADR template finalized

**Goal:** a consistent one-page format for shipped-phase ADRs.

**Template structure:**

```markdown
# ADR-NNNN: <decision title>

**Status:** Accepted | Superseded by ADR-MMMM
**Date:** YYYY-MM-DD
**Phase origin:** Phase NN

## Context
1–2 paragraphs: what problem prompted this decision.

## Decision
1 paragraph: what we chose.

## Consequences
Bullet list: what changed in the code/architecture/operations.

## Alternatives considered
Brief: what we rejected and why.
```

**Deliverable:** `docs/adr/0000-template.md` + `docs/adr/README.md`
(index page).

**Acceptance:** template fits on one screen, is unambiguous, and
matches Michael Nygard's ADR conventions (industry standard).

## Part C — Distill ADRs from shipped phases

**Goal:** at least one ADR per significant shipped phase from Phase
100 onward. Phase plans stay private; the *decision and outcome*
become public ADRs.

**Initial target list** (Eric to confirm/extend):

| ADR # | Source phase | Decision |
|---|---|---|
| 0001 | Phase 113 | Daemon state location consolidation (`$PREP_DATA_DIR`) |
| 0002 | Phase 117 | Scoped rebuild endpoints + per-stage provenance |
| 0003 | Phase 139 | Embedder singleton + restart-to-reclaim documented reality |
| 0004 | Phase 141 | Silent swarm-cache truncation prevention + integrity hardening |
| 0005 | Phase 136 | Atlas swarm-success persists root `atlas.json` |
| 0006 | Phase 76/82 | AIMD concurrency control for cloud LLM rate discovery |
| 0007 | Phase 113 | Brand split: SourcePrep (user-facing) vs `prep` (code-level) |
| 0008 | Phase 122/124 | Audit/spaghetti pipeline migration |
| 0009 | (TBD) | Trace graph + curated traceability framework |
| 0010 | (TBD) | 15-stage build pipeline architecture |

**Deliverable:** populated `docs/adr/` directory.

**Acceptance:** each ADR is 1 page or less, reads as a clean
decision record (not a planning artifact), references the private
phase doc by name (so internal readers can find the full history).

## Part D — Polish research docs

**Goal:** existing research documents become credibility assets,
polished for public reading.

**Target docs** (initial list — Phase 143 audit may add more):

- `docs/EPISTEMOLOGY_SCORING.md` → `docs/research/epistemic-scoring.md`
- `docs/CURATED_TRACEABILITY_FRAMEWORK.md` → `docs/research/curated-traceability.md`
- `docs/RUST_ENRICHMENT_ANALYSIS.md` → `docs/research/rust-enrichment-analysis.md`
- Atlas retrieval benchmark reports → `docs/research/atlas-retrieval-benchmarks/`
- Agent persona benchmark reports → `docs/research/agent-benchmarks/`
- `docs/Phase10_Business_And_Competitive_Research/` — most stays private; any
  genuine technical research (e.g., embedding model comparisons) moves out

**Polish steps per doc:**
1. Remove competitive/business framing (any mention of acquirers,
   pricing, strategic positioning)
2. Remove internal jargon (Phase NN references, internal-only file
   paths)
3. Add a 1-paragraph TL;DR at the top
4. Add a "What this is" framing for an external reader who hasn't
   seen the project
5. Verify any benchmarks/numbers are reproducible from public data

**Deliverable:** populated `docs/research/` directory.

**Acceptance:** each doc reads as standalone, no internal-only
references remain, technical claims are reproducible.

## Part E — Set up two-repo structure

**Goal:** establish private dev repo + public mirror with a documented
sync workflow.

**Steps:**

1. **Confirm GitHub org availability** (`sourceprep`) — if taken,
   fall back to `sourceprep-ai` or `sourceprep-io`. Decided in Part G.
2. **Create public mirror repo** in the org. Single initial commit
   labeled "Initial public release."
3. **First commit contents** include:
   - Engine, daemon, CLI, MCP server, dashboard source (cleaned)
   - Cleaned `docs/` per Parts A–D
   - Skeleton CONTRIBUTING.md, SECURITY.md, README.md (full content
     in Phase 142 Part C and Phase 144)
   - LICENSE (Apache 2.0)
   - NOTICE (Phase 144 deliverable)
   - CODE_OF_CONDUCT.md (industry-standard CCv2 template)
4. **Private dev repo** stays at `/Volumes/4TB-BAD/HumanAI/CoDRAG/`
   with full history and all internal docs intact. No changes here.
5. **Document sync workflow** in `docs/Phase143_DocsCleanup/OPERATIONS.md`
   (private only) — how to take a curated set of commits from private
   dev and apply them to public mirror.

**Sync workflow options to evaluate:**

| Approach | Pros | Cons |
|---|---|---|
| Manual `git format-patch` + `git am` | Full control over what's published | High overhead per release |
| `git subtree` push | Native git, no manual patching | Subtree semantics can confuse contributors |
| Scripted curation (e.g., `git filter-repo` per release) | Repeatable, automated | Setup cost upfront |

**Recommendation:** start with manual `git format-patch` for the
first 1–2 releases; automate after the workflow stabilizes.

**Deliverable:** public mirror repo with initial commit; private dev
repo unchanged; `OPERATIONS.md` (private) documenting sync workflow.

**Acceptance:** one full round-trip tested — make a docs change in
private, sync to public, verify the public commit log looks clean.

## Part F — New `docs/README.md` front door

**Goal:** public mirror's `docs/README.md` reads as a clean index for
external developers, not a working journal.

**Required sections:**

1. What is SourcePrep (1 paragraph)
2. Quick start (pointer to top-level README install instructions)
3. Architecture overview (pointer to `docs/architecture/`)
4. Decision records (pointer to `docs/adr/`)
5. Research (pointer to `docs/research/`)
6. Contributing (pointer to `CONTRIBUTING.md`)
7. Security disclosure (pointer to `SECURITY.md`)
8. License (pointer to `LICENSE`)

**Deliverable:** `docs/README.md` rewrite, ~100 lines, scannable.

**Acceptance:** a developer who's never seen SourcePrep can land on
this page and find what they need in <60 seconds.

## Part G — GitHub org + repo name decisions

**Goal:** locked-in names before public mirror creation.

**Decision matrix:**

| Org name | Status | Fallback |
|---|---|---|
| `sourceprep` | Check availability | `sourceprep-ai`, `sourceprep-io`, `getsourceprep` |

| Repo name | Pros | Cons |
|---|---|---|
| `sourceprep/sourceprep` | Matches brand exactly | Verbose |
| `sourceprep/prep` | Matches CLI command | Single-word repo names sometimes confused |
| `sourceprep/core` | Future-proof if repos split | Less brand-aligned |

**Recommendation:** `sourceprep/sourceprep` for the main repo
(brand alignment); reserve `sourceprep/prep` as redirect.

**Deliverable:** confirmed names; org created; redirects set.

**Acceptance:** the URL `github.com/sourceprep/sourceprep` resolves
to the new public mirror.

## Sequencing

Parts run mostly in this order, but can parallelize:

```
A (triage) ──┬──> C (distill ADRs) ──┐
             ├──> D (polish research) ─┤
             └──> E (two-repo setup) ──┴──> F (front door)

B (ADR template) ──> C
G (org name)    ──> E
```

**Critical path:** A → C → E → F. Roughly 1–2 weeks of focused work
for a solo dev.

**Adjacent work:** Phase 144 (legal pre-launch) runs in parallel —
attorney consults and USPTO filings happen during this phase's
calendar window without conflicting.

## Risks

| Risk | Mitigation |
|---|---|
| ADR distillation goes long (15+ phases, 2 hours each = 30 hours) | Time-box to 1 page per ADR; perfect is the enemy of shipped |
| `sourceprep` org name unavailable | Pre-checked fallbacks; not a critical blocker |
| Doc triage surfaces something genuinely embarrassing | Default to "keep private"; the cost of leaving a doc out is much lower than the cost of leaving something in |
| Sync workflow proves brittle in practice | Start manual; automate when patterns stabilize; accept some friction during the first releases |
