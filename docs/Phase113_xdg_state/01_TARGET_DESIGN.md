# Phase 113 — Target Design

## One canonical data dir

```
$CODRAG_DATA_DIR  (if set)
        │
        ▼
~/.local/share/prep/                        ← default (Linux/macOS)
%LOCALAPPDATA%\codrag\                        ← default (Windows, future)
```

Resolution helper lives in `codrag.core.paths` (new module) and is the
**only** place that decides where daemon-wide state goes. Every
caller — CLI, server, config_manager, build_manager, every SQLite
store — imports from here.

```python
# codrag/core/paths.py
def data_dir() -> Path:
    """Canonical daemon-wide data directory.

    Precedence:
      1. $CODRAG_DATA_DIR env var (absolute path, used for test
         isolation and user overrides)
      2. Platform XDG default (~/.local/share/prep on *nix)

    The returned path is guaranteed to exist (mkdir parents=True).
    """
```

## Store layout inside `data_dir()`

```
<data_dir>/
├── registry.db                  project registry (already here)
├── active_project.json          active-project signal (already here)
├── audit_log.db                 SARIF audit log (already here)
├── codrag_antibodies.db         → moved from ./codrag_data
├── codrag_concepts.db           → moved from ./codrag_data
├── codrag_observations.db       → moved from ./codrag_data
├── codrag_pipeline_journal.db   → moved from ./codrag_data
├── codrag_pipeline_history.db   → moved from ./codrag_data
├── codrag_token_telemetry.db    → moved from ./codrag_data
├── codrag_settings.db           ← consolidates the two copies
├── ui_config.json               → moved from ./codrag_data
└── projects/                    embedded standalone-mode indexes (already here)
```

**Deliberately removed:**

- `./codrag_data/projects.db` — legacy, 0-byte/32-KB dregs; replaced by
  `registry.db` long ago.
- `./codrag_data/registry.db` — stale 0-byte shadow of the XDG one.
- `./codrag_data/codrag_settings.db.corrupt.bak*` — leftovers from a
  past WAL-on-USB incident; migrator will warn but not auto-delete.

## Migration strategy

Run on daemon startup, in a dedicated helper `migrate_legacy_data_dir()`.

### Preconditions checked

1. `CWD/codrag_data/` exists AND is non-empty of recognized files.
2. `data_dir()` resolves to a different path than `CWD/codrag_data/`.
3. No migration sentinel (`<data_dir>/.migrated_from_cwd`) exists yet.

### Behavior

For each recognized file/dir in `CWD/codrag_data/`:
- If the destination path in `data_dir()` **does not exist** or is
  **0 bytes**: move the legacy file (atomic `os.replace` when on the
  same filesystem; otherwise copy+fsync+unlink).
- If the destination **exists and is non-empty**: prefer the **larger**
  file (heuristic: larger = more history / more real data). Log the
  decision. Keep the loser at `<data_dir>/<name>.migration-conflict`
  so nothing is destroyed.
- For `codrag_settings.db` specifically (where we know both are active):
  introspect via `sqlite3` — pick the one with more rows in the
  `settings` table; stash the loser as `.migration-conflict`.

After every file is handled:
- Write `<data_dir>/.migrated_from_cwd` with a JSON record of the
  source path, timestamp, files moved, conflicts, hostname.
- Log a prominent one-liner so the user notices.

### Idempotence

The migration only runs if the sentinel is absent. Re-running the
daemon after migration is a no-op. If a user nukes the sentinel to
force a re-migration they're on their own (we warn and rerun).

### Safety

- No file is ever deleted. "Moved" means rename-on-same-fs or
  copy-then-unlink-original. Conflicts land at `.migration-conflict`
  suffixes, not overwritten.
- Corrupt-backup files (`*.corrupt.bak*`) are **not migrated** —
  they're local incident artifacts.
- The migration step is wrapped in a broad try/except; if it fails
  the daemon logs but still starts (stale-state is better than
  daemon-won't-start).

## ui_config.json — the one tricky file

Options considered:

**A. Move to XDG, stop tracking in git.** Cleanest. Requires the app
to write its default schema on first launch (mostly already true —
`_load_ui_config` has defaults). Users lose the "check in my layout"
option but gain "my layout doesn't churn the repo."

**B. Keep repo-local at `codrag_data/ui_config.json` and .gitignore
it.** Preserves status quo for single-user self-hosted installs.
Forces the daemon to *still* know about the CWD path, which
re-introduces exactly the ambiguity Phase 113 is trying to kill.

**C. Split: a small `schema.json` with defaults in the repo, plus a
user-state `ui_config.json` in XDG.** Overengineered.

**Chosen: A.** Move to XDG. The .gitignore pattern for
`codrag_data/` becomes a belt-and-suspenders guard during the
transition and can be tightened later.

## Env-var override

`CODRAG_DATA_DIR=/some/absolute/path` replaces the default.
Used by:
- Test suite (per-test tmpdir, no pollution of real XDG)
- Portable installs on shared machines
- Users who want to keep state on a specific drive (relevant to this
  repo's 4TB-BAD-USB setup)

If the env var is set to a relative path, raise at startup — "data
dir must be absolute" — to prevent the exact CWD-drift bug we're
fixing.

## CLI behavior

`codrag serve --index-dir` and friends: **kept but deprecated.**
- If passed, still honored (overrides env + default) with a
  deprecation log line pointing at `$CODRAG_DATA_DIR`.
- If not passed, uses `paths.data_dir()`.
- Phase 113 does **not** remove the flag — some users have scripts
  that pass it. Removal is a future phase.

## Self-ingestion guard cleanup

After migration, `codrag_data` as an L1 exclude default becomes
load-bearing only while legacy layouts still exist in the wild.
Plan:
- Leave it in L1 for this release — users on old layouts need it.
- Add a log-line exclude-hit counter (future work) so we can see when
  nobody triggers it anymore and can remove it in a later phase.

## Non-goals for this phase

- Windows support (`%LOCALAPPDATA%`). Helper is shaped to allow it,
  but this phase only tests the *nix path.
- Encrypted-at-rest stores. Out of scope.
- Multi-user / multi-install isolation (e.g. `~/.local/share/prep-dev`
  vs `-prod`). The env var covers it for now.

## Test strategy

Real `TestClient(app)` pattern where possible (consistent with
`tests/test_scoped_full_reset.py`). Specifically:

1. `tests/test_paths.py` — unit tests for `paths.data_dir()`:
   env-var precedence, absolute-path enforcement, default resolution.
2. `tests/test_data_dir_migration.py` — integration tests for
   `migrate_legacy_data_dir()`:
   - fresh install (no legacy dir) → no-op, no sentinel written
   - legacy dir with disjoint files → moved, sentinel written
   - legacy dir with conflicts → larger wins, loser saved as
     `.migration-conflict`
   - sentinel present → no-op
   - partial state (migration crashed mid-run) → recoverable: re-run
     without sentinel resumes for un-migrated files
3. `tests/test_no_cwd_relative_codrag_data.py` — regression guard:
   grep the src tree for `"./codrag_data"` / `"codrag_data/"` string
   literals and fail the test if any remain outside the migration
   helper and docs. Same spirit as `test_no_self_ingestion.py`.
