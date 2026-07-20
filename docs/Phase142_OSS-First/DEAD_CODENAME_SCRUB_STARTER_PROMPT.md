# Starter Prompt — Public-mirror dead-codename scrub (OSS-7)

> **Self-contained starter prompt** for a dedicated follow-up AI session.
> Goal: drive `tools/build_public_mirror.py` from **78 content-flagged files → 0**
> so the public mirror emits cleanly and the `public-mirror-gate` CI job turns
> green. This is the blocker that makes the OSS mirror emittable.
>
> Context docs (read these first):
> - `docs/Phase142_OSS-First/DEEP_RESEARCH_D_CODRAG_KEY_FINDINGS.md` (why the gate
>   exists, fail-closed/fresh-init, the two-keys split)
> - `docs/Phase142_OSS-First/STARTER_PROMPT.md` (the original 76-file worklist notes)
> - `docs/Phase142_OSS-First/PUBLIC_MIRROR_MANIFEST_2026-07-19.json` (older manifest)
> - `docs/Phase11_Deployment/FOR_ERIC_TODO.md` → **OSS-7** (this task)

## What this session is

**A code + config MUTATION session** (unlike the read-only DR sessions). You will
edit source, tests, `.gitignore`, and `tools/build_public_mirror.py`, run the gate
and the test suite repeatedly, and commit per logical unit. The finish line is:
`python tools/build_public_mirror.py` exits **0** (no content-denylist hits), the
mirror `--emit`s a tree with **zero** `codrag`/`RunPrep`/`.runprep`, and `pytest`
stays green.

The public mirror **excludes** any flagged file. So for **shippable code** (all of
`src/prep/`, `engine/`, `packages/ui/src/`, the public websites) exclusion is NOT
acceptable — those files MUST be scrubbed clean. Only artifacts may be dropped.

## Hard rules (read before touching anything)

- **Naming split is the law.** `SourcePrep` = user-facing **brand** (UI, marketing,
  domains, the `.sourceprep/` state dir). `prep` = **code** (CLI, Python imports,
  MCP tool names, `@prep/*` npm scope, `PREP_*` env vars). Pick the replacement by
  context:
  | Dead string | Replace with |
  |---|---|
  | `.codrag` (state dir) | `.sourceprep` |
  | `codrag_data` (state dir) | `prep_data` (the current canonical, per Phase 113) — but prefer **deleting** the reference; see category A/C |
  | `codrag` in code/identifiers | `prep` |
  | `codrag`/`CoDRAG` in brand/UI copy | `SourcePrep` |
  | `RunPrep` | `SourcePrep` (brand) or `prep` (code) by context |
  | `.runprep` | `.sourceprep` |
  | `@codrag/ui` | `@prep/ui` |
- **NO dead-codename legacy preservation.** `.runprep`/`codrag`/`RunPrep`/`codrag_data`
  are dead names with **zero users**. **Gut** the legacy read/write/fallback/detection
  paths — do NOT keep them as a "legacy fallback" or "migration safety net." When you
  gut compat code, update or delete the tests that pinned that compat behavior.
- **EXCEPTION — legitimate pattern-bearing files.** Some files MUST contain the dead
  strings and cannot be scrubbed: secret/codename **detection tooling** (the sanitizer
  crate, `content_sanitizer.py`, `rename_gate.sh`, the mirror gate itself, the two
  `publish_*_subtree.sh` scripts I just added regexes to) and **absence-asserting
  tests** (a test that proves `.codrag`/`codrag_data` is correctly IGNORED must name
  it). These get a **`content_scan_allowlist`** (you build this — see Method §2), NOT
  a scrub. Allowlisted files still **ship**; they just skip the content scan.
- **Don't break functionality.** Run `.venv/bin/pytest` on touched areas. Use the
  **project venv** (`.venv/bin/python`, `.venv/bin/pytest`) — NOT system python, and
  NEVER `pip install` anything (this repo IS `prep`; test via pytest, not raw imports).
- **npm lockfile caution.** `packages/ui/package-lock.json` has the stale `@codrag/ui`
  name. Regenerating it (`npm install --package-lock-only`) needs network — **flag it
  to Eric, don't assume it's safe to run headless.** A manual `name`-field edit may be
  enough; verify.
- **Commit per logical unit, LOCALLY.** Message style `chore(phase142): dead-codename
  scrub — <category>`. **NEVER push** without an explicit "push/deploy/ship" from Eric.
  **No `Co-Authored-By`.** **Never `git commit --amend` on main** (concurrent sessions
  collide — verify `git log -1` is yours before any history op).
- **Protected stash.** `stash@{0}` holds unpushed WIP — **read-only on the stash**,
  never pop/apply/drop.
- **prep MCP:** call `prep` (no args) first; `project_id` in `.sourceprep/AGENT_CONTEXT.md`.
  Use `prep_search`/`prep_impact` before editing hub files (paths.py, cli.py, server.py,
  rules_generator.py are hubs). Note unhelpful/wrong prep results as product feedback.
- **No image reads** (the model crashes on PNG Read). Verify text-only.

## Live scope (as of origin/main `b6e42ab5` — RE-RUN the gate for the current list)

`python tools/build_public_mirror.py` → **Included 1657 · Excluded 10 · FLAGGED 78**.
The 78 will drift as you work; the gate is the source of truth. Labels: 75 dead-codename,
29 internal-doc, 8 secret, 5 private-key (files can carry several).

### Decision framework — every flagged file is ONE of:
1. **SCRUB** (shippable code with a real dead-name) → replace per the naming table.
2. **ALLOWLIST** (must contain the pattern: detection tooling / sanitizer fixtures /
   absence-asserting tests) → add to `content_scan_allowlist`; it still ships.
3. **EXCLUDE + gitignore** (build artifact that should never have been tracked) →
   `git rm --cached` + add to `.gitignore` + add to the gate's `DENY_PATH_GLOBS`.
4. **ESCALATE to Eric** (gutting changes real behavior) → do NOT guess; list it.

### The 78, categorized (verify each against the live gate output)

**A. Build artifacts → EXCLUDE + gitignore (do NOT scrub):**
- `packages/ui/package-lock.json` (`@codrag/ui` — fix the `name` field; npm regen needs Eric/network)
- `packages/ui/reports/mutation/mutation.html` (Stryker report)
- `packages/ui/tsconfig.node.tsbuildinfo` (TS build cache)
- `packages/ui/vite.config.ts.timestamp-*.mjs` (2 Vite temp files)
→ these should already be gitignored patterns; `git rm --cached` them and extend
`.gitignore` + `DENY_PATH_GLOBS` (`*.tsbuildinfo`, `*.timestamp-*.mjs`, `reports/mutation/`).

**B. Detection tooling + sanitizer fixtures + my gate edits → ALLOWLIST (must ship, must contain the strings):**
- `engine/crates/prep-sanitize/src/lib.rs` (secret-detection unit-test fixtures — RSA header, AWS example, ghp placeholder)
- `src/prep/core/content_sanitizer.py` (private-key detection patterns)
- `scripts/rename_gate.sh` (dead-codename gate — contains the patterns it detects)
- `scripts/publish_deploy_subtree.sh`, `scripts/publish_prep_mcp_subtree.sh` (the secret/codename regexes I added in `c49bf098`)
- `tests/test_remote_sync.py` (dummy `AKIA1234567890ABCDEF` test value)
→ add to the new `content_scan_allowlist` with a one-line justification per entry.
(Note: `tools/build_public_mirror.py` itself is self-exempt already but STILL ships the
`codrag` strings via the self-scan exemption — DR-D §2.5. Consider templating those
literals or excluding the script from the mirror.)

**C. Core `src/prep/` + `engine/prep-walker` + `scripts/dev.sh` dead-codename → SCRUB (mandatory; can't be excluded):**
~25 files incl. `cli.py`, `server.py`, `core/paths.py`, `core/data_dir_migration.py`,
`core/feature_gate.py`, `core/config_manager.py`, `core/project_registry.py`,
`core/concept_store.py` (services), `core/audit_log.py`, `core/git_evidence.py`,
`core/watcher.py`, `core/atlas/generator.py`, `core/repo_profile.py`,
`core/roadmap_miner.py`, `core/todo_scanner.py`, `core/group_reasoning.py`,
`core/concept_synthesizer.py`, `api/routers/projects/{crud,helpers}.py`,
`api/routers/trace_routes/query.py`, `engine/crates/prep-walker/src/lib.rs`, `scripts/dev.sh`.
→ Scrub the strings. **ESCALATE the rename-infra** (`paths.py`, `data_dir_migration.py`,
`feature_gate.py`, `config_manager.py`, `project_registry.py`) where removing the
`codrag_data`/`.codrag`/`.runprep` read/detection path changes migration behavior —
per the no-legacy rule the default is GUT, but flag any that migrate real user state so
Eric confirms no live install depends on it.

**D. internal-doc references → SCRUB / REWORD (public files must not cite internal artifacts):**
~29 files flagged for citing `CLAUDE.md`/`SCRUTINY`/`ACQUIRER`/`AUDIT_2026-07-17`/
`HANDOFF_PROMPT`/`MARKETING_SITE_AUDIT`/`RESEARCH_ROUND_2`. Incl. `CONTRIBUTING.md`,
`core/{embedder,docs_grounding,lemon_squeezy,rules_generator}.py`, `mcp/server.py`,
`core/atlas/validators.py`, `services/antibody_store.py`, several `packages/ui` stories,
`websites/apps/marketing/src/app/faq/page.tsx`.
→ **CLAUDE.md ambiguity (recurring):** the gate flags every `CLAUDE.md`, but some are
LEGIT product references — `rules_generator.py` GENERATES a CLAUDE.md for the user's
project, and the FAQ describes that. Distinguish: a reference to *our internal* planning
CLAUDE.md → scrub; a reference to *the file SourcePrep writes for users* → reword to a
neutral phrasing (e.g. "your agent's rules file / AGENTS.md") OR allowlist if the exact
name is product-necessary. Prior guidance (STARTER_PROMPT.md:73) leaned reword. Decide
per file; when in doubt, reword to avoid the internal-doc names entirely.

**E. Tests that pin rename/migration behavior → UPDATE or ALLOWLIST (~40):**
`test_walker_parity`, `test_data_dir_migration`, `test_phase128_*`, `test_paths`,
`test_no_cwd_relative_codrag_data`, `test_trace_builder_globs`, `test_watcher_relevance`,
`conftest.py`, `tests/fixtures/*`, etc.
→ Per test: (a) if it pins compat you GUTTED in category C → rewrite it to assert the
dead name is NO LONGER handled, or delete it; (b) if it asserts the dead name is correctly
EXCLUDED/ignored (e.g. `test_no_cwd_relative_codrag_data.py`) → it must name the string,
so ALLOWLIST it; (c) if the reference is incidental → scrub. For any cross-module test you
change, keep at least one test that exercises the real seam (don't mock the thing under test).

## Method

1. `prep` first. Read the context docs. Re-run the gate to get the live 78.
2. **Build the `content_scan_allowlist` mechanism in `tools/build_public_mirror.py`:**
   a set of repo-relative paths that are still INCLUDED in the mirror but SKIP the
   content scan (wire it into `collect()` right before `content_hits()` is called —
   allowlisted → append to `included`, do not scan). Require a justification comment per
   entry. This is the tool for categories B and E(b).
3. Work category by category (A → B → C → D → E is a sane order). **Re-run
   `python tools/build_public_mirror.py` after each batch** and watch FLAGGED drop.
4. After gutting compat code (C), run `.venv/bin/pytest tests/<affected> -x` and fix/remove
   the tests that pinned removed behavior (E).
5. Iterate until the gate exits **0**.

## Verification (before you call it done)

- `python tools/build_public_mirror.py` → exit **0**, FLAGGED **0**.
- `python tools/build_public_mirror.py --emit /tmp/sp-mirror` → exit 0; then
  `grep -rIiE 'codrag|runprep' /tmp/sp-mirror` returns **nothing** (spot-check the
  emitted tree is truly clean). Then `rm -rf /tmp/sp-mirror`.
- `.venv/bin/pytest tests/ -x -q` green (or every red is an intentional, documented
  test change).
- `.venv/bin/ruff check src/` clean on files you touched. `.venv/bin/mypy src/` no new errors.
- No `@codrag/ui` left: `grep -rn '@codrag' packages/ --include=*.json --include=*.ts` empty.

## What to PRODUCE

1. The scrubbed tree (commits per logical unit).
2. The new `content_scan_allowlist` in `tools/build_public_mirror.py` (justified entries).
3. `docs/Phase142_OSS-First/DEAD_CODENAME_SCRUB_FINDINGS.md` — per-category actions taken,
   the allowlist justifications, and the **Eric-decision list** (rename-infra gut/keep,
   any tests deleted, the npm lockfile regen, any CLAUDE.md reword judgment calls).

## STOP and surface to Eric when

- The rename-infra gut-vs-keep calls (category C escalations) — does gutting break any
  real migration path? Do NOT guess; list them with your recommendation.
- Any test you deleted (vs. updated).
- The `package-lock.json` regen (needs network).
- The gate returns 0 AND the emit is verified clean.
- You have committed locally and NOT pushed (no `[deploy]`/push signal).

## Commit

Per logical unit, locally: `chore(phase142): dead-codename scrub — <category>`.
**NEVER push. No `Co-Authored-By`. Never `git commit --amend` on main** (verify
`git log -1` is yours first — concurrent sessions collide).
