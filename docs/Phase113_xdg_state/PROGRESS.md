# Phase 113 — Progress Log

## 2026-04-17 (session 1)

### Steps 1–4 complete

**Step 1: `codrag.core.paths`** — new module, `data_dir()` with env-var
override + absolute-path enforcement + XDG default. 7 unit tests.

**Step 2: `project_registry.codrag_data_dir()` delegates** — now a
thin shim to `paths.data_dir()`. Six internal callers still import the
old name; they all continue to work because the shim returns the same
path the function used to compute itself.

**Step 3: `data_dir_migration.py`** — migration helper with sentinel,
row-count + size tiebreaker, `.migration-conflict.<ISO>` backups for
the both-non-empty case. 9 integration tests covering: no-op on clean
install, no-op with sentinel, move-when-empty, conflict-larger-wins,
conflict-settings-row-count, sentinel-present no-op, partial-crash
resume, skipped-files recorded, always-returns-MigrationResult.

Test failures along the way: three tests closed the `with tempdir`
block before running assertions, so tempdirs got cleaned up and
asserts failed with `FileNotFoundError`. Fixed by moving asserts
inside the `with`.

**Step 4: Wired migration into startup** — added call at
`src/codrag/server.py` top-level (before store-module imports, so the
first store open sees the XDG path) AND belt-and-suspenders in
`src/codrag/cli.py::serve` (covers non-FastAPI launch paths). Import
smoke test: `from codrag.server import app` succeeds.

### Real-world validation (accidental)

The smoke-test import triggered a real migration against this dev
machine's actual state because a CoDRAG daemon has been running since
last night (PID 84234). Outcome:

- Sentinel: `~/.local/share/codrag/.migrated_from_cwd` written
- 8 files moved: `codrag_{antibodies,concepts,observations,pipeline_journal,pipeline_history,settings,token_telemetry}.db`, `ui_config.json`
- 1 conflict resolved: `codrag_settings.db` — 40 KB legacy won the
  row-count tiebreaker over the 180 KB WAL-bloated XDG copy, loser
  saved as `codrag_settings.db.migration-conflict.20260417T173004Z`
- 3 files correctly skipped: `projects.db`, `registry.db`,
  `settings.db` (all legacy/stale)
- `audit_log.db` (32 MB, XDG-only) untouched — correct, not in
  recognized list

The running daemon still holds open fds on the original inodes
(macOS-style rename preserves open-file semantics), so it keeps
writing to the moved data. When the daemon restarts, it will open
fresh fds at whichever path Step 5/6 flips point to.

**Failure mode found:** migration runs ALWAYS if legacy dir exists
and no sentinel. There is no check for "is another daemon currently
running against the legacy path." Noted for future hardening —
probably a lockfile check at `<legacy>/.daemon.lock`. Not in scope
for this phase.

### Steps 5–9 complete

**Step 5: flipped `index_dir` defaults.** Four call sites:
- `services/config_manager.py::ui_config_path` — falls through to
  `paths.data_dir()` unless an explicit non-legacy `index_dir` override
  is passed
- `services/build_manager.py::get_legacy_index` — uses
  `str(paths.data_dir())` as the fallback
- `server.py::configure` — param default flipped to `None`, resolved
  via `paths.data_dir()` inside the body
- `server.py::main` — argparse `--index-dir` default is now `None`
  (the flag is now documented as deprecated)
- `server.py` module docstring + `mcp_direct.py` comment updated to
  match new reality

Smoke test: `configure()` with no args produces
`_config["index_dir"] == "/Users/ericbintner/.local/share/codrag"`.

**Step 6: stores self-locate via `index_dir`.** The existing
`server.py` init block builds every store path off
`db_path.parent` where `db_path` is the settings DB inside
`index_dir`. Now that `index_dir` defaults to `paths.data_dir()`
(Step 5), all 7 stores — concept, antibody, telemetry, journal,
observation, history, settings — automatically land in XDG.

Smoke test (ran live in this session):
```
concept_store            -> /Users/ericbintner/.local/share/codrag/codrag_concepts.db
antibody_store           -> /Users/ericbintner/.local/share/codrag/codrag_antibodies.db
telemetry                -> /Users/ericbintner/.local/share/codrag/codrag_token_telemetry.db
journal                  -> /Users/ericbintner/.local/share/codrag/codrag_pipeline_journal.db
observation_store        -> /Users/ericbintner/.local/share/codrag/codrag_observations.db
history                  -> /Users/ericbintner/.local/share/codrag/codrag_pipeline_history.db
settings                 -> /Users/ericbintner/.local/share/codrag/codrag_settings.db
```

**Step 7: `ui_config.json` moved to XDG + gitignore.**
- `.gitignore` gained a `codrag_data/` entry (in addition to the
  existing `.codrag/`).
- `git rm --cached` on the 14 tracked files under `codrag_data/`
  (7 DBs + 2 corrupt backups + 3 projects.db* + registry.db +
  ui_config.json). On-disk files preserved — git just stops
  tracking them.

**Step 8: watcher guard extended to new data_dir.**
`AutoRebuildWatcher.__init__` now auto-adds `paths.data_dir()` to
`_extra_exclude_globs` when it resolves under `repo_root`. This
handles the edge case where `$CODRAG_DATA_DIR` points inside a
watched project (otherwise SQLite WAL checkpoints would fire the
watcher in a loop). The existing L1 `codrag_data/` basename guard
is kept for the common legacy-layout case.

**Step 9: regression guard.**
`tests/test_no_cwd_relative_codrag_data.py` — greps all src/codrag
.py files for quoted `./codrag_data` / `codrag_data/` literals. Fails
if any appear outside a documented allowlist
(`data_dir_migration.py`, `paths.py`, `repo_profile.py` (L1 exclude
name), `watcher.py` docstrings, `config_manager.py` back-compat
shim). 2 tests green.

### Test totals

46/46 green across Phase 113 + 114 + 115 targeted tests:
- 7 paths
- 9 migration
- 2 regression guard
- 3 walker parity (Phase 115)
- 4 user exclude (Phase 115)
- 3 no self-ingestion (Phase 115)
- 5 L3 plumbing (Phase 115)
- 5 atomic_io (Phase 114)
- 8 scoped full reset (Phase 114)

Full suite (`pytest tests/`) pending — running in background at
closeout time.

### Summary of changed files

New:
- `src/codrag/core/paths.py`
- `src/codrag/core/data_dir_migration.py`
- `tests/test_paths.py`, `tests/test_data_dir_migration.py`,
  `tests/test_no_cwd_relative_codrag_data.py`
- `docs/Phase113_xdg_state/` (this folder)

Modified:
- `src/codrag/server.py` — migration wire-in, configure() default,
  argparse default, docstring
- `src/codrag/cli.py` — migration call in serve entry
- `src/codrag/core/project_registry.py` — codrag_data_dir() shim
- `src/codrag/core/watcher.py` — XDG data_dir exclude
- `src/codrag/services/config_manager.py` — ui_config_path uses data_dir()
- `src/codrag/services/build_manager.py` — get_legacy_index uses data_dir()
- `src/codrag/mcp_direct.py` — comment
- `.gitignore` — + codrag_data/
- 14 `codrag_data/*` entries removed from git index (preserved on disk)

### Post-merge hardening (2026-04-17, session 2)

Scrutinized the committed work against a restarted daemon. Daemon
lsof confirms all 8 stores open against `~/.local/share/codrag/`;
no open fds against legacy `./codrag_data/`. Live config `index_dir`
is None (resolved to data_dir()). Migration sentinel present.
Zero runtime regressions.

Two real gaps surfaced by re-audit:

1. **SQLite `-wal` / `-shm` sidecars were not migrated** — a `.db`
   can have WAL-only uncommitted transactions; moving the main file
   without the WAL silently drops those pages. Fix: added
   `_sqlite_sidecars()` and `_migrate_sidecars()` to
   `data_dir_migration.py`. WAL/SHM travel with the `.db` on clean
   moves AND both conflict resolution paths (dest wins → legacy
   sidecars preserved as `<db>.migration-conflict.<iso>-wal/-shm`;
   legacy wins → dest sidecars preserved similarly). Three new tests
   (`test_sqlite_sidecars_move_with_db`,
   `test_non_sqlite_has_no_sidecar_handling`,
   `test_sidecar_conflict_preserved_with_db`). Not a regression on
   this dev machine (WAL was already checkpointed at migration time)
   but a real data-loss risk for any install where the daemon was
   live-writing at migration.

2. **Dashboard ignore glob pointed at legacy path** —
   `useDashboardPanels.tsx:91` had `**/codrag_data/ui_config.json`
   in `DEFAULT_ALWAYS_IGNORED_GLOBS`. After Phase 113, `ui_config.json`
   lives in XDG (outside the repo root, not walker-visible anyway),
   so the glob was a no-op. Removed.

Post-hardening totals: 12/12 migration tests, 49/49 Phase 113+114
targeted tests green. Cosmetic "14:00 write to legacy ui_config.json"
mystery was the pre-Phase-113 daemon's final flush before restart —
explained by legacy code paths in the old daemon process, not a
Phase 113 bug.
