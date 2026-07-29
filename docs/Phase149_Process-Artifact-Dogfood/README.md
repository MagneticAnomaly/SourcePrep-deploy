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

ApplicationBrowser keeps **14** concurrent `git worktree`s under
`.claude/worktrees/`, each a full checkout. That duplicates the entire
`docs/` tree:

```
inside .claude/worktrees/*:   10,212 .md   (~12× the real docs/ tree)
```

These are **not** indexed. Two independent mechanisms exclude them:
the hard `**/.claude/**` exclude glob (`lib.rs:142`) **and** the
`ignore` crate's `.gitignore` respect (`WalkConfig.respect_gitignore`,
`lib.rs:50`) — the repo's `.gitignore` has `.claude/*`. **No action
needed here.**

> **Numbers note (scrutiny 2026-07-29).** An earlier draft of this
> section reconciled an "atlas 804 vs 871 checked-in .md, delta ~67"
> figure. That math was wrong and has been removed:
> - The 871 counted `docs/` **+ `.claude/plans` + `.claude/agents`**,
>   but the latter two (17 `.md`) are *excluded* by `**/.claude/**` —
>   they are not indexed, so they don't belong in the numerator.
> - On disk (excluding worktrees + DerivedData) there are actually
>   **1,762** `.md`: `docs/` 858, **`web/` 837** (generated
>   design-system docs), `eval/` 23, `Packages/` 14, `.claude/` 18,
>   `.sourceprep/` 6, root 5. The atlas's "804 markdown" is a
>   **2026-07-28 snapshot** of a *different population* (it reports
>   `web` as 54 files total, i.e. ~837 `web/` md are already excluded
>   as generated/gitignored content). So 804 is neither current nor a
>   simple subset of 871; don't use it for arithmetic.
>
> The qualitative claim below rests on `docs/` (858 tracked `.md`,
> fully tracked, not gitignored), not on the stale atlas count.

### The bad: tracked process artifacts under docs/ are indexed at full weight

The **858 tracked `.md` under `docs/`** are indexed uniformly as
"Documentation" (`repo_profile.py:243`) — no per-doc tier or
down-weight exists in retrieval today (verified: see "Verified
against the code" below). Much throwaway `.md` is *already* filtered
elsewhere by `.gitignore` (the 837 generated `web/` docs, the
`.claude/` plans, `.sourceprep/`), so the unhandled gap is
specifically **tracked** process docs that users commit into `docs/`.
Within that 858, ~56 handoff-named files + ~19 starter-prompt files
are git-tracked — snapshotted context for a past session, high token
cost, low durable signal:

- `docs/superpowers/starter-prompts/2026-07-2*-*handoff-*.md` (per-session launch prompts)
- `docs/superpowers/plans/*HANDOFF*.md` (dated handoff bundles)
- `docs/reviews/STARTER_PROMPT_*.md`, `docs/Phase*/HANDOFF*.md`, `*EXECUTION_STARTER_PROMPT*`
- per-phase `*_handoff*.md`, dated `YYYY-MM-DD-*-starter-prompt.md`

These sit beside `docs/Phase00_plans/00-design-spec-draft.md` (the
locked source of truth) as peers. Expected consequences (mechanisms
#1–#3 are plausible and worth measuring before claiming them proven;
#4 is certain):

1. **Retrieval dilution.** `prep_search` for an architecture question
   can surface `2026-07-29-handoff-E-post-laneB.md` ahead of the design
   spec. A handoff is past-session context; it should not compete with
   durable docs in the default pool. *(Plausible — docs are confirmed
   in the retrieval corpus, see below — but not yet measured as an
   actual mis-rank.)*
2. **Atlas skew.** "Top docs per module" links planning docs to
   modules; handoffs/starter prompts get linked too, so a module's
   "why" surfaces ephemeral process instead of the ratified spec.
   *(Plausible; the md→code link map is `atlas_markdown_links.json`,
   Phase 124 T2 — handoffs/starter prompts would appear in it.)*
3. **Doc-graph noise (hypothesis).** Handoffs cite many specs (high
   out-degree) but nothing cites them back (in-degree ≈ 0) — leaves
   that look like hubs — and doc-to-doc back-references may inflate
   the cycle/noise count. *(Unverified — the link map records md→code
   links; md↔md in-degree was not checked. Treat as a hypothesis to
   test, not a finding.)*
4. **Not a code-graph problem (certain).** Trace/impact operate on
   Swift symbols, which are clean. The blast radius is retrieval +
   atlas ranking, not structural correctness.

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
files). The gap is the **tracked process docs that live outside those
dirs** — and CoDRAG's own repo is a test case: it has a root
`HANDOFF.md`. So this is a cross-tool, generalizable ingestion-quality
problem, not a single repo's hygiene.

## Verified against the code (2026-07-29 scrutiny)

Every CoDRAG-side claim this doc leans on was checked against the
source (all TRUE, with caveats):

1. **Named scopes exist and work as opt-in retrieval filters (Phase 120).**
   `scope` is a param on `prep`/`prep_search`/`prep_impact`/`prep_concepts`/`prep_observe`
   (`mcp_tools.py:70-76…459-465`), threaded through `mcp/server.py`,
   resolved by `core/scope_resolver.py:22-54` (`resolve_mask`), and a
   `ScopeRecord` carries arbitrary `paths: list[str]`
   (`core/scope_store.py:13-36`). A new `process` scope holding a
   subset of docs is creatable today; `prep_search(scope="process")`
   would then bound retrieval to exactly those paths. **Direction B/C's
   opt-in scope is not new infrastructure — it reuses Phase 120.**
2. **The walker exclude list is parity-pinned.** `tests/test_walker_parity.py`
   asserts every Python `DEFAULT_EXCLUDE_*` glob appears in the Rust
   walker (`:51-64`, one-way: Python ⊆ Rust), plus self-ingestion
   guards and leak-culprit globs. **Any change to excludes needs a
   matching parity assertion** — and a tier/pool change wants an
   equivalent "what's in the default pool" regression + a
   false-positive guard (the `00-design-spec-draft.md` "draft" case
   must stay durable).
3. **No doc down-weighting exists today — but there *is* a filename-specific
   doc up-weight precedent.** The retrieval scoring path
   (`core/index.py` `search()` `:1144-1273`) applies keyword/fts/path/
   structural/primer/segment/role/intent boosts; `is_doc` (`:504`) is
   used only for stats and to pick `chunk_markdown` vs `chunk_code`
   (`:574-577`), never as a score modifier. **Caveat:** `_primer_boosts`
   (`:2091-2115`) gives +0.25 (cap 0.50) to root-level `AGENTS.md` /
   `PREP_PRIMER.md` / `PROJECT_PRIMER.md`. That is class-specific and
   *up*-weights, so "no doc down-weighting" holds — but a future
   down-weight is the symmetric counterpart to an existing pattern,
   not a wholly new kind of logic.
4. **Per-file git history is already captured (the churn signal is free).**
   `core/git_evidence.py` (Phase 105) exposes `FileChurn` (commits,
   first/last_seen, authors, lines ±) via `recent_churn_by_file(window_days)`,
   cached in-memory + on disk (`:140-178`), and `classify_hub`
   (`:296-314`) already derives `stable`/`evolving`/`fragile`/`unknown`
   labels from it. **Caveat:** `commits` is commits *within the window*
   (default 60 days, `:132`), not lifetime churn. A classifier can
   reuse `recent_churn_by_file()` directly; lifetime count needs a
   wider window or one extra git call.
5. **Walker hard-exclude overrides `.gitignore` re-includes — a real trap.**
   `exclude_globs` become negated overrides applied *on top of* the
   gitignore layer (`lib.rs:215-220`, each glob rewritten `!{glob}`;
   corroborated by `test_walker_parity.py:145-147`). A repo's
   `.gitignore` `!.claude/agents/` does **not** re-include
   `.claude/agents/` — the hard `**/.claude/**` wins. **Implication:
   if we ever want `.claude/plans/`-style paths in a `process` scope,
   that requires removing them from the hard `exclude_globs`, not a
   `.gitignore` `!` rule.** Faux-archive must not assume gitignore can
   punch back in under a hard exclude.
6. **Docs are already in the semantic retrieval corpus.** `_DOC_EXTS`
   (`core/index.py:174`), markdown chunked via `chunk_markdown`
   (`:574-575`) into the **same** `docs`/`vectors` arrays as code
   (`:564-565`), ranked by the same `search()` scoring over the whole
   embedding matrix. **"Down-weight docs in retrieval" builds on an
   existing capability** — it's a new modifier keyed on
   `is_doc`/`_DOC_EXTS`, with no pool partition to retrofit.

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
| **Graph** (CoDRAG's edge) | high out-degree, ≈0 in-degree from code/durable docs | strong (if it holds) | **only a structural indexer sees this** — the moat. **Unverified for md↔md:** the link map is md→code (Phase 124 T2); md-to-md in-degree was not measured. Must be validated before leaning on it. |
| **Git churn** | 1 commit, never edited after creation, recent | strong | **Already available** — `core/git_evidence.py` `FileChurn` via `recent_churn_by_file()`; `classify_hub` already labels `stable`/`evolving`/`fragile`. **Windowed (default 60d), not lifetime** — widen the window or add one git call for all-time count. |

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
   generated files*, this phase is about *user/agent-generated tracked
   docs*. Adjacent, not overlapping.
8. **Target population: tracked docs, not all throwaway md.** Much
   throwaway md is *already* filtered by `.gitignore` (ApplicationBrowser's
   837 generated `web/` docs, `.claude/` plans, `.sourceprep/`). The
   gap is specifically **tracked** process docs under `docs/`. `web/`
   is a second throwaway family (generated design-system docs) worth
   naming, but it's already handled here — don't re-filter what
   gitignore already drops. Confirm the classifier operates on the
   indexed (tracked, non-excluded) set, not the raw on-disk set.
9. **Faux-archive re-include trap.** Walker hard-excludes override
   `.gitignore` re-includes (verified, `lib.rs:215-220`). So faux-archive
   cannot rely on gitignore to punch a path back into a `process` scope
   if that path sits under a hard-excluded dir (e.g. `.claude/plans/`).
   Re-including such paths means editing `exclude_globs`, not a
   `.gitignore` `!` rule. Design the scope membership as an explicit
   path list, not a gitignore inversion.
10. **Down-weight as the symmetric counterpart to an existing boost.**
    `_primer_boosts` already up-weights three root primer files in
    `search()` (`core/index.py:2091-2115`). A `process` down-weight is
    the same kind of filename/class-keyed modifier — lower-risk than
    "net-new logic," and it should slot into the same boost-application
    site (`:1218`) rather than a parallel path.
11. **Classifier-feeding-archive (Direction A').** The classifier can
    *serve* Direction A, not just B/C: SourcePrep surfaces "N docs look
    like process artifacts — archive them?" and the user accepts a
    `git mv` to a gitignored `archive/`. This is archive-as-a-feature
    (the user's "archive should be important" emphasis) rather than
    archive-as-discipline. Decide whether A is guidance-only or ships
    a one-click archive driven by the same classifier.

## Non-goals

- Not changing the walker's existing dir/glob excludes — those are
  correct and tested.
- Not auto-deleting user files. "Archive" always means move-to-gitignored
  (Direction A) or virtual-exclude (Direction C), never `rm`.
- Not judging *user* docs (READMEs, wikis, ADRs) — only process
  artifacts. The classifier must fail safe toward `durable`.

## Next step

A brainstorm/design pass to pick among B/C (and whether A is
guidance-only or ships a classifier-driven one-click archive — A'),
define the durable bootstrap set, and decide score-vs-label and
default-on-vs-opt-in before any code. The verification above de-risks
the pass: the opt-in scope (Phase 120), the retrieval modifier site
(`core/index.py:1218`), and the churn signal (`core/git_evidence.py`)
all already exist, so B/C are additive — not greenfield. The two
things still to *prove* (not assume) before committing: (a) the
md↔md graph in-degree hypothesis (#3 / signal table), and (b) an
actual mis-rank in `prep_search` where a handoff beats the spec (#1).
No implementation in this phase yet.