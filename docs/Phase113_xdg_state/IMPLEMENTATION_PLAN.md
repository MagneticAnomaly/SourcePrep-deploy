# Phase 113 — Implementation Plan

10 steps, ordered so the repo is kept runnable at every checkpoint.
Each step has a concrete exit test; none is "refactor and hope."

## Step 1 — `codrag.core.paths` module

- Create `src/codrag/core/paths.py` with `data_dir()`.
- Resolution: `$CODRAG_DATA_DIR` (must be absolute) → `~/.local/share/prep/`.
- `mkdir(parents=True, exist_ok=True)` before return.
- Unit tests: env precedence, absolute-path enforcement, default resolution.
- **Exit:** `tests/test_paths.py` green; no callers yet.

## Step 2 — `project_registry.codrag_data_dir()` delegates to `paths.data_dir()`

- Keep the existing function as a thin wrapper; flag it as deprecated
  in a docstring (do **not** delete — 6 call sites still use it).
- **Exit:** existing project-registry tests still green.

## Step 3 — Daemon startup migration helper

- New file: `src/codrag/core/data_dir_migration.py`.
- Exposes `migrate_legacy_data_dir(cwd: Path | None = None) -> MigrationResult`.
- Logic per TARGET_DESIGN §Migration strategy.
- Idempotent via `<data_dir>/.migrated_from_cwd` sentinel.
- **Exit:** `tests/test_data_dir_migration.py` green (5 scenarios).

## Step 4 — Wire migration into daemon startup

- Call `migrate_legacy_data_dir()` once, early in `server.py`'s
  startup (before stores are opened). Log the result.
- Also call from `cli.py serve` entry point (covers the non-FastAPI
  launch path).
- **Exit:** start daemon on a copy of the current `./codrag_data/`,
  verify everything lands in XDG on first run, nothing on second.

## Step 5 — Flip defaults on `index_dir`

Four call sites currently default to `"./codrag_data"`:
- `services/config_manager.py:232`
- `services/build_manager.py:574`
- `server.py:716, 1091`
- (plus `mcp_direct.py:71` comment — update comment only)

Replace each with `str(paths.data_dir())`. Keep the CLI `--index-dir`
flag functional (explicit override wins).
- **Exit:** fresh daemon with no `CODRAG_DATA_DIR` and no legacy
  `codrag_data/` writes to XDG. Existing daemon args still work.

## Step 6 — SQLite stores use `paths.data_dir()` directly

Audit the 7 store modules and switch each off `index_dir` args that
were really "daemon-wide":
- `services/antibody_store.py`
- `services/concept_store.py`
- `services/observation_store.py` (if present)
- `services/pipeline/journal.py` (+ history module if separate)
- `services/telemetry/*` (token telemetry)
- `services/config_manager.py` (codrag_settings.db)
- `api/routers/system.py` `_load_ui_config` path

Each store picks its own filename under `data_dir()`. No more
"stores tag along with whatever index_dir the daemon booted with."
- **Exit:** full pytest green; `pytest tests/test_scoped_full_reset.py -v`
  still green.

## Step 7 — Move `ui_config.json` to XDG

- Update the loader/writer to use `paths.data_dir() / "ui_config.json"`.
- Add a .gitignore entry for `codrag_data/` (whole tree).
- Remove tracked copy on this branch: `git rm codrag_data/ui_config.json`.
- **Exit:** daemon boots with no tracked ui_config; XDG copy is
  created/read.

## Step 8 — Watcher + self-ingestion guard sync

- `core/watcher.py` L1 exclude list references `codrag_data` — keep
  it (legacy-user safety) but add `paths.data_dir()` as an exclude
  too so the watcher never re-indexes the new location either.
- Same for `repo_profile.py` `_DEFAULT_EXCLUDES`.
- **Exit:** `tests/test_no_self_ingestion.py` + `test_walker_parity.py`
  still green; new assertion that `data_dir()` is in the Python L1 set.

## Step 9 — Regression guard

- New test: `tests/test_no_cwd_relative_codrag_data.py`
- Greps `src/codrag/**/*.py` for `"./codrag_data"` and
  `r"codrag_data/"` string literals.
- Allowed exceptions (allowlist):
  - `core/data_dir_migration.py` (by design)
  - `core/paths.py` if it references legacy layout for migration docs
  - `core/repo_profile.py` / `core/watcher.py` L1 exclude strings
- **Exit:** test green; CI prevents regression.

## Step 10 — Manual smoke + docs

- `scripts/dev.sh` smoke test: kill daemon, move legacy
  `./codrag_data/` sideways (rename), start fresh, confirm XDG
  population, start a rebuild, verify telemetry/concept/pipeline
  writes land in XDG.
- Add a short note to `CLAUDE.md` §Key Ports-ish section:
  "Daemon state lives at `$CODRAG_DATA_DIR` (default
  `~/.local/share/prep/`). Legacy `./codrag_data/` is
  auto-migrated on first run."
- **Exit:** PROGRESS.md closeout + final PR.

## Risk register

| Risk | Mitigation |
|---|---|
| Migration crashes mid-run, leaves files half-moved | Sentinel only written at end; re-run resumes untouched files; nothing deleted. |
| User has custom `--index-dir` pointing to `./codrag_data` | Flag still honored; migration only fires when default path is used. Deprecation log line. |
| `audit_log.db` (32 MB) already in XDG — migration logic mustn't touch it | Migration only considers files present in `./codrag_data/`; XDG-only stores are untouched. |
| `codrag_settings.db` both-active case picks the wrong one | Row-count heuristic + `.migration-conflict` backup means the user can recover either way. |
| Tests rely on `./codrag_data/` implicitly | `$CODRAG_DATA_DIR` override per-test via tmp_path. Add a pytest fixture in `conftest.py`. |
| pytest runs for other devs still pollute XDG | Same fixture: **all** tests set `CODRAG_DATA_DIR=tmp_path` in autouse. |
| Phase 115 self-ingestion tests tied to `codrag_data` hardcoded literal | Keep the literal in L1 exclude; Phase 115 tests continue to pass. |

## What we are explicitly NOT doing

- Not adding a user-facing "change my data dir" UI.
- Not encrypting stores.
- Not touching embedded `.prep/` layouts.
- Not removing the `--index-dir` CLI flag.
- Not renaming DB files (`codrag_antibodies.db` stays
  `codrag_antibodies.db`, not `antibodies.db`) — out of scope churn.
