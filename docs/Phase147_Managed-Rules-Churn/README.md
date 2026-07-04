# Phase 147 — Managed Rules-File Churn: Static Pointer + Gitignored Volatile Context

> **The bet:** Every generated rules file (CLAUDE.md, AGENTS.md,
> `.cursor/rules/prep.mdc`, GEMINI.md, …) currently embeds volatile
> content — a fresh timestamp, atlas text, node/edge counts, focus
> areas, project_id — directly into git-tracked files. Every pipeline
> run dirties them. Splitting each managed block into a **stable
> tracked pointer** plus a **gitignored volatile context file** makes
> the tracked files converge to a fixed point, which permanently ends
> both the "another session has WIP" confusion and the recurring
> same-file-tail merge conflicts.

**Status:** Open — proposal v2 scrutinized and ready for execution
(one fresh-eyes read of the W1 behavior table + a 5-minute import
smoke remain as PR-2 gates).
**Owner:** Eric (created 2026-07-04).
**Primary code:** `src/prep/core/rules_generator.py`,
`src/prep/mcp/server.py` (W1 — atlas-dedup repoint, found in scrutiny)
**Predecessors:** Phase 50 (original rules generator), Phase 124 T9
(docs-per-module section), Phase 120 (scopes section), Phase 119
Task 16 (concurrency hint).
**Related phases:** Phase 143 (docs cleanup / OSS mirror — a slim
AGENTS.md is also a cleaner public-repo artifact), Phase 145 (where
the merge-conflict pain was repeatedly paid — the "pr-M/pr-N
same-file-tail conflict pattern" during the 2026-06-29 merge train).

## Why this phase exists

SourcePrep regenerates its managed rules blocks after every pipeline
run (`services/pipeline/post_flight.py:98` and `:159`, two more call
sites in `services/pipeline/workers/__init__.py:1488,1516`), on scope
CRUD (`api/routers/scopes.py:30`), at pipeline start
(`services/pipeline/orchestrator.py:1985`), and from the CLI
(`cli.py:919`). Each regeneration stamps `Last updated: <now>`
(`rules_generator.py:482-483`) into up to nine files, seven of which
are conventionally git-tracked.

Consequences observed while dogfooding this very repo:

1. **Phantom-WIP confusion.** Claude Code sessions see
   CLAUDE.md / AGENTS.md / `.cursor/rules/prep.mdc` modified in
   `git status` at session start and conclude another session left
   work in progress. Autonomous flows then hedge, ask, or try to
   "preserve" changes that are actually daemon noise.
2. **Recurring merge conflicts.** Branches regenerate the managed
   block at different times with different timestamps/atlas text.
   Every merge conflicts in the same file tail. 48 commits touch
   CLAUDE.md and 40 touch AGENTS.md in this repo's history; a
   meaningful fraction are pure regeneration noise
   (e.g. `2dae33eb chore(prep-managed): regenerate AGENTS.md / Cursor
   rule / CLAUDE.md atlas`).
3. **Graph pollution.** The embedded atlas makes AGENTS.md a fat
   pseudo-doc that the indexer then re-ingests (previously flagged:
   generated files are noise in the trace graph).

This is a **product** defect, not a repo-hygiene quirk: every client
project that adopts SourcePrep inherits the same churn.

## Scope

**In:**

- Split `_build_managed_content()` into static instructions
  (tracked) and volatile context (gitignored file).
- New volatile context file: `.sourceprep/AGENT_CONTEXT.md`,
  written by a single shared writer, referenced by all targets.
- Native import pointer for CLAUDE.md / GEMINI.md; read-instruction
  pointer for AGENTS.md and the other targets.
- `.gitignore` management: ensure the volatile file is ignored in
  client projects without clobbering user gitignore content.
- No-op write guard for tracked files (stop dirtying mtimes when
  content is unchanged).
- Migration of this repo's own rules files (dogfood-first).

**Out (explicitly):**

- Any change to atlas *generation* (content, LLM passes, hashing).
- MCP tool schemas or server behavior.
- Direct-mode parity work.
- Retroactive history rewrite of this repo (the churn commits stay).

## Documents

| File | Type | Status | What's in it |
|---|---|---|---|
| `README.md` (this file) | index | live | Why, scope, evidence summary, execution order, exit criteria |
| `PROPOSAL_static-pointer-volatile-context-v1.md` | proposal | **superseded by → v2** | First full design. Retained per phase convention — its hypothesized risk R5 turned out to be the critical W1 defect |
| `SCRUTINY_v1_static-pointer-volatile-context.md` | scrutiny — first pass | static | Checklist executed as code greps + reverse-engineering of exit criteria + V1–V3 doc research. **Defects D1 (critical: `mcp/server.py` atlas-dedup reads the hash we move — would permanently suppress the atlas in `prep()` responses), D2 (high: nested registered projects — `websites/apps` — dirty the parent repo; migration must be per-project), D3/D4 minor.** All V-spikes resolved; all OQs decided by Eric 2026-07-04 |
| `PROPOSAL_static-pointer-volatile-context-v2.md` | proposal — **ready for execution** | open | v1 + scrutiny fixes: §5.5 W1 server repoint with behavior table, §9.5 manual per-project migration checklist (all 15 registered projects), D3 sentinel header, D4 worktree limitation, resolved decisions. Execution gates in §15 |

Per Phase 145 working principles: scrutiny findings became v2, v1
stays as the teaching artifact.

## Execution order (updated 2026-07-04)

1. ~~Scrutiny pass~~ — **done** (same-author; see SCRUTINY doc).
2. ~~V1–V3 verification spikes~~ — **resolved via docs research**:
   Claude missing-import = silent skip (HIGH), in-repo gitignored
   import ≈ no approval dialog (MEDIUM — live smoke kept as PR-2
   gate), Gemini memport confirmed `.md`-only with graceful
   missing-file error (HIGH).
3. ~~PR-1/2/3 + W1~~ — **shipped 2026-07-04 as one commit**
   (`78661c83`, branch `phase147/static-pointer-split`, merged to
   local main). Implementation used a `_sections` gate on
   `_build_managed_content` instead of extracting two functions —
   zero template duplication, legacy tests pass untouched. 186
   rules-adjacent tests green; the 5 `test_mcp_server.py` failures
   are pre-existing stale assertions (fail identically on main).
   Bonus fix found by the kill-shot test: `_splice` no longer
   prepends `\n\n` when there is no user content above the markers
   (a one-time churn on generator-created files).
   **Still open from the gates:** fresh-eyes read of §5.5 W1 rows;
   the V2 live import smoke (first real Claude Code session in this
   repo doubles as it).
4. **§9.5 manual migration sweep — 2 of 15 done 2026-07-04:**
   SourcePrep root + nested `websites/apps` (`38e7e9fe`, one commit)
   and Applifier/ApplicationBrowser (`12efbe17` in that repo, not
   pushed). Verified live: `prep rules-regenerate` on both now
   leaves `git status` untouched. Remaining 13 projects: follow the
   v2 §9.5 table (HomeColab: regen only, no rebuild; Deep-Live-Cam:
   fork, never push; PMR/smoke-test: gitignored, nothing to commit).
   Note: `websites/GEMINI.md` turned out to be a hand-written Gemini
   prompt with no managed markers — not a generator artifact, left
   alone.
5. **Post-landing observation week:** confirm `git status` stays clean
   across real pipeline runs (daemon was down during migration — the
   first daemon-driven regen is the remaining live check) on this
   repo and one client repo.

## Exit criteria

- A full `Rebuild All` on this repo leaves `git status` untouched
  (no modified CLAUDE.md / AGENTS.md / prep.mdc / GEMINI.md).
- Two branches that each ran pipelines merge without conflicts in
  any rules file.
- Claude Code session in a fresh clone (volatile file absent)
  starts without error and the static block's fallback instruction
  is present in context.
- Atlas content still reaches agents: via `@import` in Claude
  Code/Gemini, via read-instruction elsewhere, **and via `prep()`
  when the volatile file is missing (W1 row 4 — the degraded-mode
  safety net)**, verified by a live dogfood session.
- Existing tests (`test_rules_generator_targets.py`,
  `test_rules_generator_scopes.py`,
  `test_rules_regen_preserves_atlas.py`, `test_atlas_hash.py`)
  updated and green; new tests cover the split, the gitignore
  ensure, the no-op guard, and the four rows of the W1 atlas-dedup
  behavior table.
- The §9.5 migration sweep completed: all 15 registered projects
  regenerated, inspected, and (where tracked) committed — nothing
  pushed.
