# Phase 149 — Process-Artifact Ingestion: Identify, Under-Weight, or Faux-Archive

> **The bet:** The walker already excludes *config/tooling* junk
> (`**/.claude/**`, `**/.venv/**`, `**/DerivedData/**`, AI-rule files
> like `CLAUDE.md`/`AGENTS.md` — `engine/crates/prep-walker/src/lib.rs:142`,
> `src/prep/core/repo_profile.py:136`). But it has **no notion of a
> checked-in file that is a throwaway *process artifact*** — a handoff,
> a starter prompt, a dated session plan, a TODO snapshot. These leak
> into the tracked tree (users commit them into `docs/`) and are
> indexed as first-class Documentation at **equal weight with the
> locked design spec**. The bet: SourcePrep can tell a durable doc
> from an ephemeral one using *structural + churn* signals it already
> uniquely owns, and either ignore, under-weight, or virtually archive
> the ephemeral ones — without forcing the user to move files.

**Status:** Open — problem verified while dogfooding the
ApplicationBrowser repo; **no solution chosen yet.** This phase
records the thinking and the candidate directions. The three
directions in the title are **alternatives to evaluate**, not a
decided plan.
**Owner:** Eric (created 2026-07-29).
**Primary code (candidate touch sites):**
`engine/crates/prep-walker/src/lib.rs` (default excludes + `respect_gitignore`,
`WalkConfig`), `src/prep/core/repo_profile.py` (`DEFAULT_EXCLUDE_*`,
`DEFAULT_FILE_TIER` if introduced), `src/prep/core/repo_profile.py:243`
("Documentation" ext bucket — where a tier split would land),
the retrieval/atlas ranking path, and the named-scope surface
(Phase 120).
**Predecessors:** Phase 133 (dot-dir walker policy — the
"intentionally NOT excluded" list at `repo_profile.py:113` is the
template for a kept-vs-down-weighted split), Phase 120 (named scopes —
the natural home for an opt-in `process` scope), Phase 147 (managed
rules-file churn — same theme: generated/volatile content polluting
tracked files), Phase 129 (dev-leak audit), Phase 140 (prompt dogfood).
**Related phases:** Phase 143 (docs cleanup / OSS mirror — process
artifacts are also a worse public-repo artifact), Phase 136 (dogfood
fixes), Phase 32 (`hi_codrag` — doc-as-source weighting).

## Why this phase exists

Discovered while dogfooding SourcePrep against the ApplicationBrowser
repo (a second active SourcePrep project, id
`7cdea5e4-c94d-4612-be67-81597da3d6ec`). Two findings, one good and
one bad.

### The good: worktree/build duplication is already excluded

ApplicationBrowser keeps ~10 concurrent `git worktree`s under
`.claude/worktrees/`, each a full checkout. That duplicates the entire
`docs/` tree:

```
real repo (docs/ + .claude/plans + .claude/agents):   871 .md
inside .claude/worktrees/*:                         10,212 .md   (~12×)
```

The atlas reports **804 markdown** — the delta (871 − ~67 =
`CLAUDE.md`/`AGENTS.md`/`.claude/plans/*` file excludes) confirms the
10,212 worktree files are **not** indexed. The `**/.claude/**` exclude
(`lib.rs:142`) and the `ignore` crate's `.gitignore` respect
(`WalkConfig.respect_gitignore`, `lib.rs:50`) are doing their job.
**No action needed here.**

### The bad: checked-in process artifacts are indexed at full weight

All 871 checked-in `.md` are indexed uniformly as "Documentation"
(`repo_profile.py:243`). That includes a large volume of *process*
docs that are snapshotted context for a past session — high token
cost, low durable signal:

- `docs/superpowers/starter-prompts/2026-07-2*-*handoff-*.md` (per-session launch prompts)
- `docs/superpowers/plans/*HANDOFF*.md` (dated handoff bundles)
- `docs/reviews/STARTER_PROMPT_*.md`, `docs/Phase*/HANDOFF*.md`, `*EXECUTION_STARTER_PROMPT*`
- per-phase `*_handoff*.md`, dated `YYYY-MM-DD-*-starter-prompt.md`

These sit beside `docs/Phase00_plans/00-design-spec-draft.md` (the
locked source of truth) as peers. Observed consequences:

1. **Retrieval dilution.** `prep_search` for an architecture question
   can surface `2026-07-29-handoff-E-post-laneB.md` ahead of the design
   spec. A handoff is past-session context; it should not compete with
   durable docs in the default pool.
2. **Atlas skew.** "Top docs per module" links planning docs to
   modules; handoffs/starter prompts get linked too, so a module's
   "why" surfaces ephemeral process instead of the ratified spec.
3. **Doc-graph noise.** Handoffs cite many specs (high out-degree) but
   nothing cites them back (in-degree ≈ 0) — leaves that look like
   hubs — and doc-to-doc back-references inflate the cycle/noise count.
4. **Not a code-graph problem.** Trace/impact operate on Swift symbols,
   which are clean. The blast radius is retrieval + atlas ranking, not
   structural correctness.

### The general pattern (not just this user)

This is not an ApplicationBrowser quirk. Every AI-coding tool that
supports long-running, resumable sessions generates the same families
of process artifacts, and users commit them into `docs/`:

| Tool family | Typical artifacts |
|---|---|
| Claude Code | `HANDOFF.md`, `*handoff*`, `starter-prompt`/`STARTER_PROMPT_*`, `.claude/plans/*` (already excluded via `.claude/`), dated `YYYY-MM-DD-*-starter-prompt.md` |
| Cursor | `.cursor/rules/*.mdc` (already excluded), session handoffs |
| Windsurf | `.windsurfrules` (already excluded), `.windsurf/rules/*.md` (already excluded) |
| General | TODO snapshots, scrutiny-wave notes, dated plan bundles |

CoDRAG already excludes the *config* instances (the dot-dirs + rule
files). The gap is the **checked-in process docs that live outside
those dirs** — and CoDRAG's own repo is a test case: it has a root
`HANDOFF.md`. So this is a cross-tool, generalizable ingestion-quality
problem, not a single repo's hygiene.

## Candidate directions (not decided)

The user explicitly does not have a solution in mind. Three
directions are on the table; they are **alternatives to evaluate**,
possibly combinable.

### Direction A — User-side archive hygiene (doc-side, not code)

Recommend periodic *archiving* (not deletion) of process artifacts
once the work has merged and the durable memory is recorded elsewhere:
move `*handoff*`, `*starter*`, `STARTER_PROMPT_*`, dated
`*-HANDOFF*`, and TODO snapshots into a gitignored `archive/` (or
`git rm` after the memory topic file exists). Keep durable docs:
locked specs, decision records, phase READMEs, ratified designs,
ATS/canonical tables.

**Why "archive not delete":** process docs sometimes hold the only
record of *why* a non-obvious change was made; git history is
searchable but not retrieval-indexed. A gitignored `archive/` keeps
them off-disk-for-prep but on-disk-for-the-user.

**Limit:** this is per-user discipline, not a SourcePrep capability.
It is worth recommending in guidance, but it does not solve the
problem for users who never prune. **Directions B/C are the
SourcePrep-side fix.**

### Direction B — Identify + ignore/under-weight (retrieval tiering)

Classify each indexed doc into a tier — `durable` / `process` /
`transient` — and **down-weight `process`/`transient` in default
`prep_search` retrieval and the atlas "top docs"**, while keeping
them reachable via a **named scope** (e.g. `scope="process"`,
Phase 120) for when a user *wants* a handoff.

Inputs to the classifier (combine as a score; **no single signal is
sufficient**):

| Signal | Example | Strength | Notes |
|---|---|---|---|
| **Filename** | `*handoff*`, `*starter*`, `*STARTER_PROMPT*`, `YYYY-MM-DD-*` | weak alone | `00-design-spec-draft.md` contains "draft" but is the locked truth → false-positive risk |
| **Path** | `docs/handoffs/`, `*/starter-prompts/`, `*/plans/*HANDOFF*` | medium | strong when the repo self-organizes; weak when flat |
| **Content** | "You are continuing a session", "Starter prompt", merge-SHA + branch + worktree-name density | strong | boilerplate the tools emit reliably |
| **Graph** (CoDRAG's edge) | high out-degree, ≈0 in-degree from code/durable docs | strong | **only a structural indexer sees this** — the moat |
| **Git churn** | 1 commit, never edited after creation, recent | strong | `git log --follow`; throwaway docs are write-once |

**Why tiering, not a hard exclude:** hard-excluding checked-in files
is dangerous (the "draft" false-positive above). Down-weighting + an
opt-in scope is reversible and degrades gracefully when the
classifier is wrong.

### Direction C — Faux archive (virtual archive tier)

A SourcePrep-only concept: treat a doc **as if archived** without the
user moving it. Concretely — a doc classified `process`/`transient`
is (a) removed from the *default* retrieval pool and atlas, (b)
excluded from the doc-link graph used for hub/cycle detection, (c)
kept in a `process` scope for explicit retrieval, and (d) flagged in
the UI/atlas ("4 process docs hidden — show"). The file stays exactly
where it is on disk and in git.

**How it differs from B:** B is *ranking* (down-weight, still
surfaced, still in the graph). C is *virtual exclusion* (out of the
default pool and graph entirely, opt-in only). C is closer to the
user's "ignore" framing; B is closer to "under-weight." They likely
compose: a `process` tier that is *under-weighted* in search but
*faux-archived* out of the structural graph.

**Attraction:** it gives the user the indexing benefit of archiving
without the chore, and it is per-project reversible (re-classify, not
`git mv`). **Risk:** "faux archive" is a new mental model the user
has to trust; if the classifier hides a doc the user needed in the
default pool, it feels like silent data loss. Needs a visible
"hidden count" affordance and an easy override.

## Open questions

1. **Hard line vs score.** Is `durable`/`process`/`transient` a hard
   three-way label or a continuous weight? Score + threshold is more
   robust to edge cases but harder to reason about and surface.
2. **Where does the classifier live?** Walker (Rust, fast, cold
   filename/path only) vs pipeline (Python, can see graph + churn +
   content). Likely split: walker tags cheap signals, pipeline
   enriches with graph/churn/content.
3. **Graph-signal specifics.** What exactly is "in-degree from
   durable docs"? Need to define the durable set first — chicken/egg.
   Bootstrapping: seed durable = specs + decision records + READMEs +
   files referenced by code; iterate.
4. **Default-on vs opt-in.** Does faux-archive/under-weighting ship
   on by default (better out-of-box retrieval, risk of hiding wanted
   docs) or opt-in (safe, but most users never turn it on)?
5. **Parity/test story.** The walker exclude list is pinned by
   `tests/test_walker_parity.py`; any tier change needs an equivalent
   regression on what *is*/isn't in the default pool, plus a
   false-positive guard (the "draft" case must stay durable).
6. **Public-mirror interaction.** Phase 143 builds an OSS mirror;
   process artifacts are also a worse public artifact. Does the
   faux-archive classification feed the mirror's exclude set too?
7. **Does this subsume part of Phase 147?** Phase 147 splits managed
   rules files into tracked-pointer + gitignored-volatile. The
   volatile half is conceptually the same "generated content shouldn't
   be durable" theme — but Phase 147 is about *SourcePrep's own
   generated files*, this phase is about *user/agent-generated checked-in
   docs*. Adjacent, not overlapping.

## Non-goals

- Not changing the walker's existing dir/glob excludes — those are
  correct and tested.
- Not auto-deleting user files. "Archive" always means move-to-gitignored
  (Direction A) or virtual-exclude (Direction C), never `rm`.
- Not judging *user* docs (READMEs, wikis, ADRs) — only process
  artifacts. The classifier must fail safe toward `durable`.

## Next step

A brainstorm/design pass to pick among B/C (and whether A is just
guidance), define the durable bootstrap set, and decide score-vs-label
and default-on-vs-opt-in before any code. No implementation in this
phase yet.