# Phase 115 — Progress Log

Chronological notes on each step. One section per step.

## 2026-04-17 — Phase kickoff

Context: overnight Deep Reasoning run surfaced filter leak (see `00_PROBLEM.md` §E1). Pipeline run `run-3639f940ba9f` still in flight at kickoff; letting it finish rather than interrupting.

Phase docs drafted: `00_PROBLEM.md`, `01_TARGET_DESIGN.md`, `IMPLEMENTATION_PLAN.md`.

Decision log:
- Let `run-3639f940ba9f` finish before restarting. Fix requires daemon restart regardless; interrupting mid-swarm risks P3/P5 pause bugs per pipeline-testing runbook.
- Phase 115 lands before Phase 113 on the filter side; path renames in 113 are orthogonal.
- `prep_data/` to `~/.local/share/prep/` tracked as separate work (Track C).

## Step 0 — Add `PREP_OUTPUT_*` registry

**Status:** complete

- Added `PREP_OUTPUT_DIRS = {".prep", "prep_data"}` at top of `src/prep/core/repo_profile.py`.
- Added `PREP_OUTPUT_FILE_GLOBS` tuple with the AI-tool/Prep-generated globs previously inlined in `DEFAULT_EXCLUDE_FILE_GLOBS`.
- Re-derived `DEFAULT_EXCLUDE_DIR_NAMES = PREP_OUTPUT_DIRS | { ... }`. Net behaviour change: `prep_data` now excluded (previously only `.prep` was).
- Re-derived `DEFAULT_EXCLUDE_FILE_GLOBS = (*PREP_OUTPUT_FILE_GLOBS,)`. Net behaviour change: removed `**/prep_data/ui_config.json` (redundant — whole dir excluded now).
- Verified invariants hold via `.venv/bin/python -c "from prep.core.repo_profile import ..."`.

Counts: 35 dirs, 11 file globs (prior: 34 dirs, 12 file globs — one dir gained, one redundant file glob dropped).

## Step 1 — Add generated dirs to `DEFAULT_EXCLUDE_DIR_NAMES`

**Status:** complete

Added 9 new dir names to `DEFAULT_EXCLUDE_DIR_NAMES`:
- `storybook-static` (the one that burned the Deep Reasoning run)
- `coverage`, `out`
- `.turbo`, `.vercel`, `.parcel-cache`, `.svelte-kit`, `.astro`, `.nuxt`

Total: 44 dirs (was 35 after Step 0).

## Step 2 — Add build-artifact file globs

**Status:** complete

Added 4 new file globs to `DEFAULT_EXCLUDE_FILE_GLOBS`:
- `**/*.d.ts` (TypeScript declaration — generated)
- `**/*.min.js`, `**/*.min.css`
- `**/*.map` (source maps)

Total: 15 file globs (was 11 after Step 0).

## Step 3 — Extend `ensure_repo_policy` auto-merge to file globs

**Status:** complete

Changes:
- `src/prep/core/repo_policy.py`: imported `DEFAULT_EXCLUDE_FILE_GLOBS`. Auto-merge in `ensure_repo_policy()` now unions dir globs + file globs + `**/.*` into `exclude_globs` and rewrites the file on disk if any default is missing.
- `src/prep/core/repo_profile.py::profile_repo()`: fresh-policy generation also includes `DEFAULT_EXCLUDE_FILE_GLOBS`, so new projects get them on first profile.

Verified against the dogfood `.prep/repo_policy.json`:
- 25 new entries will auto-merge on next daemon start.
- All four leak culprits in the add list: `**/storybook-static/**`, `**/prep_data/**`, `**/*.d.ts`, `**/*.map`.
- User-specific entries preserved: `**/*.lock`, `**/*.log`, `**/.DS_Store`.

Synthetic fixture test:
- Created a 2026-04-01 stub policy with only `**/node_modules/**`, `**/.git/**` — auto-merge added 9 expected new globs, kept the two old ones, and wrote back to disk.

## Step 4 — Sync Rust walker defaults

**Status:** complete

`engine/crates/prep-walker/src/lib.rs` — `WalkConfig::default().exclude_globs` expanded from 8 → 57 entries, mirroring Python `DEFAULT_EXCLUDE_DIR_NAMES` (44 dirs as `**/X/**`) + `DEFAULT_EXCLUDE_FILE_GLOBS` (AI-tool + build-artifact globs) + Prep output globs.

Comment notes that this is a safety net; the trusted filter is resolved Python-side on each call. Selfheal (Step 7) will build its own from disk.

Build: `cargo build -p prep-walker --release` — succeeded (1m 36s fresh).
Tests: `cargo test -p prep-walker --release` — 6/6 pass.

maturin rebuild deferred until after Step 5 (Python-side TraceBuilder wiring); the two land together with one daemon restart.

## Step 5 — Delete TraceBuilder hardcoded defaults

**Status:** in progress

- `src/prep/core/trace/builder.py::TraceBuilder.__init__`: removed the hardcoded `DEFAULT_INCLUDES` / `DEFAULT_EXCLUDES` literals. When callers don't pass globs, TraceBuilder now calls `ensure_repo_policy()` for includes and `effective_excludes()` for excludes. A small safety-net list of language globs remains only as a fallback for the pathological case where the policy produces zero include globs (e.g. profile_repo ran on a repo with no detectable source).
- Added explicit import `from prep.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES` alongside the repo_policy imports (the rest of the file still references it for legacy fallback paths in the walker helpers).

Tests:
- `tests/test_trace_builder_globs.py` — 3 passed, 4 pre-existing failures.
- `test_trace_builder_includes_all_languages` passes now (TS-always-include-JS fix from `profile_repo` is the enabling change).
- Failures (`test_trace_builder_swift_analysis_smoke`, `test_generic_regex_analyzer_ruby`, `test_generic_regex_analyzer_kotlin`, `test_generic_regex_analyzer_csharp`) all reproduce on origin with `git stash push` → `pytest` → `git stash pop`. Not caused by Phase 115. Filed as pre-existing analyzer regressions for a separate triage pass.

## Step 6 — Fix epistemic_enrichment filter

**Status:** in progress

- `src/prep/core/epistemic_enrichment.py::EpistemicEnricher.load_trace_nodes()` now resolves `effective_excludes()` and drops any node whose `path` matches. Logs a WARNING with the drop count so stale trace_nodes.jsonl (from a pre-Phase-115 build) is visibly reconciled on first load post-upgrade.
- Defense layer, not a replacement for re-running the trace builder — the nodes stay in the .jsonl until the next rebuild rewrites the file.

Smoke test: `from prep.core.epistemic_enrichment import EpistemicEnricher; inspect.getsource(EpistemicEnricher.load_trace_nodes)` confirms `effective_excludes` + `pathspec` wired in.

## Step 7 — Fix Rust selfheal L3 gap

**Status:** complete

`engine/crates/prep-selfheal/src/main.rs` now accepts an optional `--extra-excludes-file <path>` argument. The file holds a JSON array of patterns sourced from `project.config.trace.ignore_patterns`; selfheal merges them onto the L1+L2 set at startup.

Context: selfheal is a standalone CLI and isn't called from Python today. The flag is the contract for when it is (or for users invoking it manually with a runtime ignore list).

Build: `cargo build -p prep-selfheal --release` — clean (4.5s).
Tests: `cargo test -p prep-selfheal --release` — 0 tests, pass.

## Step 8 — Audit watcher filter merge

**Status:** complete

`src/prep/core/watcher.py::AutoRebuildWatcher._load_policy_globs()` now returns excludes from `effective_excludes()` instead of reading `pol["exclude_globs"]` directly. Net behaviour identical post-Step-3 (ensure_repo_policy auto-merges L1 into L2 on disk), but the watcher now shares the single resolver with TraceBuilder and epistemic_enrichment. Inline comment documents the L3 gap — watcher has no project-config access, so runtime `trace.ignore_patterns` can drift. Tracked as future work.

Smoke test: confirmed `effective_excludes` appears in `AutoRebuildWatcher._load_policy_globs` source.

## Step 9 — Python/Rust parity test

**Status:** complete

New test file `tests/test_walker_parity.py` with three tests:
- `test_rust_walker_mirrors_python_l1_excludes` — parses `exclude_globs: vec![...]` out of `engine/crates/prep-walker/src/lib.rs` and asserts every Python L1 entry appears in Rust.
- `test_rust_walker_covers_prep_output_dirs` — hard invariant: `**/.prep/**` and `**/prep_data/**` must be in Rust.
- `test_rust_walker_covers_leak_culprits` — the four leaks that motivated Phase 115.

First run caught real drift: Rust was missing `**/.cursor/rules/*.mdc` and `**/.windsurf/rules/*.md`. Added both to `WalkConfig::default()` and rebuilt Rust crate. Tests now pass (3/3).

## Step 10 — Integration test: user-exclude respected

**Status:** complete

New test file `tests/test_user_exclude_respected.py` with four tests proving the ADD-not-REPLACE contract:
- `test_effective_excludes_unions_all_three_layers` — L1, L2, L3, and `explicit_excludes` all appear in the resolved set.
- `test_user_excludes_added_to_existing_policy_survive_auto_migration` — writes a stub sparse policy with user customisations + one old default. `ensure_repo_policy()` back-fills every new default and preserves `**/*.lock` / `**/.DS_Store`. Persists to disk.
- `test_user_cannot_silently_remove_prep_output_guard` — even if the user deletes `**/.prep/**` from `repo_policy.json`, the next load puts it back. Self-ingestion is a hard invariant.
- `test_prep_output_file_globs_all_in_defaults` — every entry in the registry is in `DEFAULT_EXCLUDE_FILE_GLOBS`.

All 4 pass.

## Step 11 — Self-ingestion regression test

**Status:** complete

New test file `tests/test_no_self_ingestion.py`. Scaffolds a tmpdir repo containing 16 leak-culprit paths (exact fixtures from `00_PROBLEM.md §E1`: storybook-static/*, .prep/*, prep_data/*, .d.ts, .map, .min.js, AGENTS.md, CLAUDE.md, .cursor/rules/*.mdc, .windsurf/rules/*.md, .github/copilot-instructions.md) plus 4 legit control files.

Three tests prove no path survives the filter:
- `test_effective_excludes_blocks_every_leak_culprit` — `pathspec.match_file()` against the resolved exclude set returns True for all 16.
- `test_policy_excludes_persist_every_leak_culprit_glob` — `repo_policy.json` on disk carries the covering globs, so downstream tools reading the file directly (Rust walker, selfheal, watcher) block too.
- `test_trace_builder_does_not_enumerate_leak_culprits` — end-to-end via `TraceBuilder._enumerate_files()`. Zero culprits returned; the legit `src/prep/core/trace/builder.py` control file still surfaces.

Initial run failed with `ValueError` from `relative_to()` — macOS `/var/` vs canonical `/private/var/` mismatch. Fixed by calling `tmpdir.resolve()` in the scaffold helper.

All 3 pass.

## Phase 115 closeout

Combined test run (Steps 9–11): `tests/test_walker_parity.py`, `tests/test_user_exclude_respected.py`, `tests/test_no_self_ingestion.py`, `tests/test_trace_builder_globs.py` → **13 passed, 4 pre-existing failures** (Swift/Ruby/Kotlin/C# analyzer regressions verified on origin via stash).

Outstanding follow-ups (tracked for future phases, not blocking 115):
- Watcher L3 plumbing: needs project config access to honour runtime `trace.ignore_patterns`.
- maturin rebuild: Rust walker + selfheal updates need a Python-binding rebuild before the daemon picks them up. Defer until pipeline-stage daemon restart.
- Pre-existing analyzer failures: unrelated to Phase 115, triage separately.

## Audit pass — caller-side blind spots

Reverse-engineered the filter plumbing and found three unfiltered `load_trace_nodes` call-sites the initial plan missed (Explore agent audit, 2026-04-17).

Added `src/prep/core/trace/loaders.py::load_filtered_trace_nodes()` as the shared reader contract — applies `effective_excludes()` + pathspec at read time. Rewired four callers:

- `src/prep/core/epistemic_enrichment.py::EpistemicEnricher.load_trace_nodes` — now a 3-line wrapper.
- `src/prep/core/augmenter.py::TraceAugmenter.load_trace_nodes` — **BLOCKER** pre-fix: this was feeding unfiltered nodes into Pass 1 augmentation. Pre-Phase-115 leak paths could be re-enriched every build.
- `src/prep/api/routers/projects/search.py::_load_trace_nodes_for_project` — **BLOCKER** pre-fix: unfiltered LOD context for structured search results could include storybook-static / *.d.ts content.
- `src/prep/core/atlas/role_projection.py::_load_trace_nodes` — fallback path; derives repo_root from on-disk policy since the caller only has `index_dir`.

L3 status (clarified, not a bug):
- `src/prep/services/pipeline/workers.py:174-179` already unions `project.config.trace.ignore_patterns` into the `exclude_globs` it passes to `TraceBuilder`. Pipeline runs honour L3 today.
- Loaders and watcher don't have a Project handle, so the L3 path never fires there. Known gap — requires a Project lookup-by-index_dir helper. Tracked as follow-up; not blocking.

Noise cleanup:
- `src/prep/core/watcher.py::_extra_exclude_globs` — dropped the hardcoded `**/.prep` triple (now redundant with L1). Kept the `index_dir`-relative guards for projects that use a non-standard index location outside the Prep-owned dir names.

Test verification:
- All 13 Phase 115 tests still pass after the audit fixes.
- Manual import check confirms all four loader sites now route through `load_filtered_trace_nodes` or `effective_excludes`.

## L3 plumbing closed

Added `project_registry.project_for_index_dir()` and `trace_ignore_patterns_for_index()` — reverse-look up the Project via `<index_dir>/project.json` (the existing pointer file) and return `project.config.trace.ignore_patterns`.

Wired auto-resolve into:
- `core/trace/loaders.py::load_filtered_trace_nodes` — when caller passes `trace_ignore_patterns=None` (the default), loader fetches L3 from the registry. Pass `[]` explicitly to opt out (hot path avoidance).
- `core/watcher.py::AutoRebuildWatcher._load_policy_globs` — calls `trace_ignore_patterns_for_index()` on every load so L3 edits take effect without a trace rebuild.

Downstream: all four audited loaders (augmenter, epistemic, search, role_projection) inherit L3 automatically via the shared helper.

Test: `tests/test_l3_plumbing.py` (5 tests) — pointer resolution happy path, missing pointer, missing-in-registry, end-to-end L3 filtering through the loader, and explicit-empty opt-out (asserts registry is NOT called). All pass.

## Phase 115 — closed

Layer contract now universal:
- L1 (code defaults) — `repo_profile.DEFAULT_EXCLUDE_DIR_NAMES` + `DEFAULT_EXCLUDE_FILE_GLOBS` + `PREP_OUTPUT_*` registry.
- L2 (per-project policy) — `repo_policy.json`, auto-migrates on load (Step 3).
- L3 (runtime ignores) — `project.config.trace.ignore_patterns`, plumbed through workers.py (pipeline), and auto-resolved in loaders + watcher via pointer lookup.

Every path that walks the filesystem or reads `trace_nodes.jsonl` now goes through `effective_excludes()`. Self-ingestion guard (`**/.prep/**`, `**/prep_data/**`) is a hard invariant enforced by `ensure_repo_policy()` — even a direct edit to `repo_policy.json` gets corrected on the next load.

Total: 18 tests green for Phase 115 (13 Phase 115 + 5 L3 plumbing), 4 unrelated pre-existing failures documented as not caused by this phase.
