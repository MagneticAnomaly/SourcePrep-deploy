# Dead-codename scrub — findings & Eric-decision list (OSS-7)

> Session: 2026-07-20. Drives `tools/build_public_mirror.py` from
> **78 content-flagged files → 8** (the rename-infra migration group,
> which needs an Eric gut-vs-keep call before the gate can hit 0).
> Method: a 73-agent read-only classification workflow (one per flagged
> file) built a per-occurrence decision table; mutations applied
> sequentially by category, committed per logical unit.

## Gate progress

| Step | FLAGGED | Allowlist | Commit |
|---|---|---|---|
| Session start (origin/main `39da5e2b`) | 78 | 0 | — |
| Category A (build artifacts exclude + gitignore) | 73 | 0 | `f19a29db` |
| Allowlist mechanism + Category B (detection tooling) | 67 | 6 | `aa375df3` |
| Category C (core scrubs + CLAUDE.md allowlist) | 37 | 22 | `da235073` |
| Category D (internal-doc reword) | 29 | 23 | `ace9bd58` |
| Category E (tests) | **8** | 26 | `8106cdbf` |

The remaining 8 are the **rename-infra migration group** — see
"Eric-decision list" below. The gate cannot reach 0 until that decision
is made.

All commits are LOCAL on `main`; **NOT pushed** (no `[deploy]`/push signal).
Two concurrent sessions committed on `main` mid-scrub (`b8b93448` license-gate
hardening, `b2b0c028` NOTICE MPL, `1a354b43` footer refactor, `c2eae819`
MagneticAnomaly revert) — none touched scrub files, no collisions (no
`--amend` used; `git log -1` checked before each commit).

## Per-category actions

### A — build artifacts (EXCLUDE + gitignore)
- `packages/ui/vite.config.ts.timestamp-*.mjs` (2 tracked): `git rm --cached`
  + `.gitignore` (`*.timestamp-*.mjs`, `vite.config.ts.timestamp-*`) +
  `DENY_PATH_GLOBS`.
- `packages/ui/reports/mutation/mutation.html` (untracked Stryker report):
  `.gitignore` (`packages/ui/reports/mutation/`) + `DENY_PATH_GLOBS`
  (`packages/ui/reports/mutation/*`).
- `packages/ui/tsconfig.node.tsbuildinfo` (untracked; already gitignored):
  `DENY_PATH_GLOBS` (`*.tsbuildinfo`).
- `packages/ui/package-lock.json` (scrub, NOT exclude): stale root name
  `@codrag/ui` → `@prep/ui` (lines 2, 8; package.json already `@prep/ui`).
  Only 2 occurrences in 16,995 lines. **See Eric-decision #4 (npm regen).**

### B — detection tooling + sanitizer fixtures (ALLOWLIST, must ship)
6 entries added to `CONTENT_SCAN_ALLOWLIST` (all ship, all skip the content
scan because they MUST contain the flagged strings to function):
`engine/crates/prep-sanitize/src/lib.rs`, `src/prep/core/content_sanitizer.py`,
`scripts/rename_gate.sh`, `scripts/publish_deploy_subtree.sh`,
`scripts/publish_prep_mcp_subtree.sh`, `tests/test_remote_sync.py`.

### C — core scrubs (gutted dead-name detection/exclude paths)
- `scripts/dev.sh`: dropped pre-rename `~/.cache/codrag-sb-vite/` cleanup.
- `api/routers/projects/{crud,helpers}.py`, `trace_routes/query.py`: dropped
  the `**/.runprep/**` embedded-mode exclude (`.sourceprep/**` remains).
- `core/audit_log.py`: default DB path `runprep` → `sourceprep`.
- `core/concept_synthesizer.py`: `post-scrutiny` → `post-review`; `CoDRAG` → `SourcePrep`.
- `core/git_evidence.py`: reworded `src/codrag/` ghost-path examples to neutral.
- `core/roadmap_miner.py`, `core/todo_scanner.py`: dropped `.runprep`/`.codrag`
  from ImportError-fallback skip-dir sets.
- `core/watcher.py`: scrubbed stale `codrag_data`/`runprep` comments.
- `services/concept_store.py`, `core/group_reasoning.py`: `CoDRAG` → `SourcePrep`.
- `core/atlas/generator.py`: dropped `CoDRAG` + internal memory/SCRUTINY doc cites.
- `core/repo_profile.py`: dropped `.runprep` from `PREP_OUTPUT_DIRS`.
- `engine/crates/prep-walker/src/lib.rs`: dropped `**/.runprep/**` exclude glob.
- `core/feature_gate.py`: reworded stale `.runprep` legacy-fallback comments
  (the fallback code was already removed 2026-07-19; only comments remained —
  this was a **scrub, not an escalation**, despite being a rename-infra file).

### D — internal-doc reword
- `CONTRIBUTING.md`: build/test commands → `AGENTS.md` (CLAUDE.md is excluded
  from the mirror, so the old ref was dead).
- `core/atlas/validators.py`, `services/antibody_store.py`, `mcp/server.py`:
  `SCRUTINY`-named internal doc cites → neutral "2026-05-05 epistemic-audit pass".
- `core/docs_grounding.py`: `CLAUDE.md` → "your agent's rules file" in a
  comment (the CODE uses the `CLAUDE` stem, not flagged).
- `core/embedder.py`: dropped `CLAUDE.md` from the Phase 139 doc pointer.
- `core/lemon_squeezy.py`: dropped `DISTRIBUTION_AND_REVENUE_PLAN.md` cite.
- `marketing faq`: `CLAUDE.md or rules file` → `rules file`. **See Eric-decision #5.**

**Product-necessary CLAUDE.md filename references** (walker exclude globs,
rules-generator targets, dashboard/Storybook demos, MCP server's
`Path('CLAUDE.md')` atlas-hash read) are **allowlisted, not reworded** — the
literal filename is functional. 9 such files added to the allowlist.

### E — tests
- Mechanical `.runprep` → `.sourceprep` index-dir fixture renames (the
  index_dir is opaque to CodeIndex/TraceBuilder): `test_primer`,
  `test_l3_plumbing`, `test_trace_builder_globs`, `test_trace_endpoints`,
  `fixtures/FIXTURES.md`, `conftest` (`clean_codrag_dir` → `clean_sourceprep_dir`).
- **Gut-caused-failure fixes** (the category-C `.runprep`-exclusion gut removed
  `.runprep` from default excludes; tests now assert the live `.sourceprep`
  guard): `test_walker_parity` (assert `**/.sourceprep/**` + `**/prep_data/**`
  in Rust walker; reworded stale CoDRAG-era docstrings), `test_user_exclude_respected`
  (`.runprep` → `.sourceprep` throughout; renamed `test_*_codrag_output_guard`
  → `test_*_prep_output_guard`), `tests/core/test_git_evidence`
  (`.runprep/state.json` → `.sourceprep/state.json`; reworded `src/codrag/`
  docstring examples).
- SCRUTINY/CLAUDE.md reword in test docstrings: `test_antibody_store_lazy_init`,
  `test_atlas_determinism`, `test_atlas_validators`, `test_concept_stats_per_kind`,
  `test_module_tiers_role_weighted`, `test_configure_concept_store_init`,
  `test_settings_route_ordering`, `test_coverage_default_dir_excludes_merged`,
  `test_team_sync_integration`.
- **Stale-test fix (PRE-EXISTING failure)**: `test_docs_grounding` asserted
  `PREP_SELF_OUTPUT_MARKERS` contained `Auto-generated by RunPrep`/`CoDRAG`,
  but the source catalog dropped those legacy markers in a prior session —
  the assertion was already red. Removed the stale assertions; renamed
  `test_looks_like_prep_self_output_matches_legacy_codrag_rule` →
  `..._matches_get_context_marker` (the body is detected via the
  `Get structural codebase context from Prep tools` marker, not the
  frontmatter description — so it asserts `True`, as before).
- **Absence-asserting / product-necessary CLAUDE.md → allowlist** (3):
  `test_atlas_identity_brand` (CoDRAG fixture + `IDENTITY: CoDRAG not in`),
  `test_no_self_ingestion` (LEAK_CULPRITS now live `.sourceprep`/`prep_data`
  + `CLAUDE.md`), `tests/core/test_git_evidence` (`assert _is_excluded_path('CLAUDE.md')`).

## Content-scan allowlist (26 entries, all ship)

**Category B — detection tooling / sanitizer fixtures (6):**
`engine/crates/prep-sanitize/src/lib.rs`, `src/prep/core/content_sanitizer.py`,
`scripts/rename_gate.sh`, `scripts/publish_deploy_subtree.sh`,
`scripts/publish_prep_mcp_subtree.sh`, `tests/test_remote_sync.py`.

**Product-necessary CLAUDE.md filename refs (10):** `src/prep/core/repo_profile.py`,
`engine/crates/prep-walker/src/lib.rs`, `src/prep/core/rules_generator.py`,
`src/prep/mcp/server.py`, `src/prep/cli.py`, `src/prep/dashboard/src/hooks/useDashboardPanels.tsx`,
`packages/ui/src/stories/dashboard/FullDashboard.stories.tsx`,
`packages/ui/src/stories/project/FolderTree.stories.tsx`,
`scripts/phase103_observe_hook.py`, `tests/fixtures/walker_parity_repo/README.md`.

**CLAUDE.md product tests (4):** `tests/test_cli.py`,
`tests/test_phase133_bimodal_walker.py`, `tests/test_phase147_rules_split.py`,
`tests/test_rules_generator_targets.py`.

**Absence-asserting tests (6):** `tests/test_phase128_license_path_fallback.py`
(.runprep ignored), `tests/test_watcher_relevance.py` (.runprep excluded),
`tests/test_no_cwd_relative_codrag_data.py` (codrag_data regression guard),
`tests/test_atlas_identity_brand.py` (CoDRAG not surfaced), `tests/test_no_self_ingestion.py`
(LEAK_CULPRITS), `tests/core/test_git_evidence.py` (CLAUDE.md excluded).

Each entry has a one-line justification in `CONTENT_SCAN_ALLOWLIST` in
`tools/build_public_mirror.py`.

## Test-suite status

`pytest` on the touched E tests: **203 passed, 8 failed.** The 8 failures
are **PRE-EXISTING rot, not scrub-caused** (verified by re-running on
pre-cat-C state — same 8 fail):
- `test_primer` ×4
- `test_trace_builder_globs` ×4 (test_trace_builder_swift_analysis_smoke,
  test_generic_regex_analyzer_{kotlin,csharp,ruby})

Root cause: tree-sitter/regex analyzer issues (`UserController` not detected
in Ruby, etc.) — unrelated to dead codenames. The scrub introduced **zero**
new failures and fixed 5 gut-caused + 1 stale (test_docs_grounding marker).

`ruff check src/`: 798 errors, all **pre-existing** codebase-wide style nits
(`Optional[str]` → `X | None`, `List` → `list`). The scrub edits
(comment/docstring reword, `.runprep` → `.sourceprep`, dead-name removal)
touched no type annotations, so added zero new ruff errors.

---

## Eric-decision list

### #1 — RENAME-INFRA MIGRATION: gut vs keep (BLOCKING — the last 8 flagged files)

The 8 remaining flagged files are the Phase-113 one-time migration code
that reads/moves REAL user state from pre-rename installs (`.codrag/`,
`.runprep/`, `codrag_data/`, `~/.local/share/codrag/`):

- `src/prep/core/paths.py` — `_migrate_embedded_dir()` (renames
  `.codrag/`→`.runprep/`→`.sourceprep/` per project open + orphan warning)
  and `legacy_cwd_data_dir()` (returns `./codrag_data`).
- `src/prep/core/data_dir_migration.py` — entire file:
  `migrate_legacy_data_dir()` (CWD `codrag_data/` → XDG) and
  `migrate_from_legacy_codrag/prep/runprep()` (XDG `~/.local/share/{codrag,prep,runprep}/`
  → `sourceprep/`).
- `src/prep/core/project_registry.py` — the `_migrate_embedded_dir` call
  site in `read_project_pointer` (L506-509) + a `.codrag/.runprep` debug string.
- `src/prep/server.py` — the startup migration imports/calls (L38-53) +
  stale `runprep` copy (L9 docstring, L1314 CLI help — these are independent
  stale-copy scrubs I can do regardless).
- `src/prep/services/config_manager.py` — `./codrag_data`/`codrag_data` in
  the legacy `--index-dir` override-ignore tuple (L242).
- `tests/test_data_dir_migration.py` — entire file tests the migration.
- `tests/test_paths.py` — tests `_migrate_embedded_dir` + `legacy_cwd_data_dir`.
- `tests/test_phase128_paths_migration_orphan_warning.py` — tests the orphan
  warning (depends on `_migrate_embedded_dir`).

(`src/prep/cli.py` L238-246 also calls the migration functions, but cli.py
is already allowlisted for its product-necessary `CLAUDE.md` rules-target
map, so it is not in the flagged-8 — its migration calls are coupled to
this decision regardless: if data_dir_migration.py is gutted, cli.py's
imports break.)

**Option GUT (recommended):** delete `_migrate_embedded_dir` +
`legacy_cwd_data_dir` from paths.py; delete data_dir_migration.py + remove
the startup calls in server.py/cli.py + the call in project_registry.py;
remove `codrag_data` from config_manager.py's tuple; delete/rewrite the 3
migration tests. **Pro:** completes the no-legacy goal; the OSS public
release has zero users with these dirs (fresh mirror, first commit);
Eric's dev machines have almost certainly migrated (Phase 113 was months
ago, sentinels set); smaller codebase. **Con:** any unmigrated install
(Eric's machine? beta? CI?) with a `.codrag/`/`.runprep/`/`codrag_data/`/
`~/.local/share/codrag/` dir would strand that state (daemon rebuilds
fresh). **Risk: low.**

**Option KEEP (allowlist migration tooling):** keep the migration code,
allowlist paths.py + data_dir_migration.py + the migration tests; rename
the public migration functions to neutral names (`migrate_from_legacy_codrag`
→ `migrate_from_legacy_dir_a`, etc.) so cli.py/server.py imports don't
carry dead names; reword the project_registry.py debug string. **Pro:**
preserves migration for any straggler install. **Con:** messier (function
renames spread the change; broad allowlisting of core files); preserves
dead-codename legacy the no-legacy rule says to gut.

**My recommendation: GUT.** Confirm no live install (your machines, beta
testers, CI) still has an unmigrated dead-name state dir whose data would
be stranded. If yes → KEEP; if no → GUT.

### #2 — Deleted/rewritten tests (per "surface deleted tests")
- `test_docs_grounding::test_looks_like_prep_self_output_matches_legacy_codrag_rule`
  → renamed `..._matches_get_context_marker` and reworded (assertion stays
  `True`; the `CoDRAG` description was never what triggered detection —
  the `Get structural codebase context from Prep tools` marker was). Not a
  deletion, but semantics shifted. The stale `assert "Auto-generated by
  RunPrep"/"CoDRAG" in PREP_SELF_OUTPUT_MARKERS` lines were **deleted**
  (the catalog already dropped those markers in a prior session).
- If you choose GUT (#1): `test_data_dir_migration.py` (entire file),
  `test_paths.py` migration tests, and `test_phase128_paths_migration_orphan_warning.py`
  would be deleted/rewritten — I will surface those before doing them.

### #3 — config_manager.py L242 (low-risk, coupled to #1)
`if override and override not in ("./codrag_data", "codrag_data", "./prep_data", "prep_data"):`
— the tuple ignores legacy CWD `--index-dir` overrides. If GUT: remove
`./codrag_data`/`codrag_data` (keep `./prep_data`/`prep_data`? — not
flagged, still semantically "ignore CWD-relative legacy override"). If
KEEP: leave as-is and reword/allowlist. Recommend removing the two
`codrag_data` entries either way (low risk: no user passes `--index-dir
./codrag_data`).

### #4 — npm lockfile regen (needs network)
`packages/ui/package-lock.json` root name was hand-edited `@codrag/ui` →
`@prep/ui` (lines 2, 8) — the headless stopgap. A proper
`npm install --package-lock-only` regen (which would also sync any other
stale refs) needs network. **Flag for Eric:** run the regen when convenient
and re-commit, or confirm the manual edit is sufficient.

### #5 — marketing FAQ CLAUDE.md reword (judgment call)
`websites/apps/marketing/src/app/faq/page.tsx` "claude-md" FAQ item:
`CLAUDE.md or rules file` → `rules file` (drops the `CLAUDE.md` literal;
the item ID `claude-md` is kept — it doesn't match the gate regex).
**Alternative:** revert to `CLAUDE.md` + allowlist the faq (the FAQ
legitimately discusses the Claude Code rules file; product-accurate).
I reworded to clear the gate with the endorsed neutral phrasing. **If you
want the Claude-Code-specific framing back** (SEO/clarity for Claude Code
users), say so and I'll revert + allowlist.

## Verification (current state — gate NOT yet 0)

- `python tools/build_public_mirror.py` → exit 1, FLAGGED **8** (the
  migration group above). Need Eric-decision #1 to proceed.
- `--emit` NOT yet clean (refuses to emit with unresolved hits).
- `pytest` touched-E-tests: 203 passed, 8 pre-existing failed (documented).
- `ruff`/`mypy`: no new errors from the scrub (pre-existing style nits only).
- `grep -rn '@codrag' packages/ --include=*.json --include=*.ts` → empty
  (the `@codrag/ui` lockfile name was the only one; now `@prep/ui`).

## Next step (after Eric decides #1)

1. Apply GUT or KEEP per decision #1 (paths.py, data_dir_migration.py,
   project_registry.py, server.py migration block, cli.py migration
   block, config_manager.py, 3 migration tests).
2. Scrub the independent stale copy in server.py (L9, L31, L1314).
3. Re-run gate → target exit 0, FLAGGED 0.
4. `--emit /tmp/sp-mirror` + `grep -rIiE 'codrag|runprep' /tmp/sp-mirror`
   → confirm clean.
5. Commit locally. **NEVER push** without explicit signal.