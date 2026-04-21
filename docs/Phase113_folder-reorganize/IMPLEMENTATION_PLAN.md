# Implementation Plan

This is the step-by-step plan for executing Phase 113. It covers the core `.prep/` reorganization plus the nine adjacent improvements bundled into scope (see [06_ADJACENT_OPPORTUNITIES.md](06_ADJACENT_OPPORTUNITIES.md)).

Steps are independently shippable, reviewable, and revertable. Each step has an acceptance checklist, verification commands, and an explicit PR boundary. Before starting a step, the open questions in [04_RISKS.md](04_RISKS.md) assigned to it must be resolved.

The revised step set:

| Step | Added-by | Purpose |
|---|---|---|
| 0a | original | Discovery, resolve open questions |
| 0b | original (extended) | `project_paths` module + metadata registry |
| 0c | **new (item 1)** | `atomic_io` helper module |
| 0d | **new (item 6)** | `project_lock` module |
| 1 | original (extended) | Route trace paths; adopt `atomic_write` |
| 2 | original (extended) | Route remaining paths; destroy enumeration; adopt `atomic_write` |
| 2b | **new (item 6)** | Wire daemon lock into startup |
| 3 | original | v1 snapshot test |
| 4 | original (extended) | Layout move + migrator + `version.json` + README + checkpoint rename |
| 4b | **new (items 2, 7)** | Log subsystem: JSONL + rotation + retention |
| 5 | original | Docs + CI grep-gate |
| 5a | **new (item 5)** | `codrag doctor` CLI |
| 6 | original | Phase B trigger |

---

## Step 0a — Discovery and verification (no code changes)

**Goal:** Resolve all open questions in [04_RISKS.md](04_RISKS.md) so every subsequent step starts on confirmed facts.

**Tasks:**

1. **Q1 — `CodeIndex.index_dir` resolution.** Read `core/index.py`, trace one writer end-to-end, record whether the `index/` segment is part of `self.index_dir` or the basename.
2. **Q2 — Dead `.db` stub investigation.** Full-tree grep for `codrag_settings.db`, `settings.db`. Classify each match.
3. **Q3 — `architecture/graph_state.json` purpose.** Find writer + readers. Load-bearing yes/no.
4. **Q4 — Trace-file site cardinality.** Exact count via grep (sizes the Step 1 PR).
5. **Q5 — Watcher path coupling.** Read the watcher for hardcoded paths.
6. **Q6 — Non-Python readers.** Cross-language grep (`packages/`, `src/codrag/dashboard/`, `websites/`).
7. **Q7 — Multiple-project migration safety.** Confirm by reading project-load lifecycle.
8. **Q8 — `pipeline_*.log` consumers.** Search dashboard, CLI, external tooling. Determines whether JSONL format change breaks anything.
9. **Q9 — Checkpoint run-ID cross-references.** Grep for run ID usage outside the checkpoint dir itself (journal, state machine, manifests, logs). Determines whether Step 4's rename needs alias handling.
10. **Q10 — Log retention expectations.** Is anyone expected to access `pipeline_*.log` files older than 30 days / 50 runs? Determines retention policy.
11. **Q11 — Concurrent-daemon assumption.** Does any codepath or deployment pattern assume two daemons can safely share an index? Shapes the lockfile's "blocking vs. refuse" behavior.
12. **Q12 — Streaming vs. wholesale JSONL writers.** Classify each JSONL writer. Sets atomic-write exemption list.
13. **Discovery sweep** — `rg --type=python -e 'idx_dir / "' src/` and related. Cross-check against [01_PATH_INVENTORY.md](01_PATH_INVENTORY.md) and add anything missing.

**Acceptance:**

- All 12 questions answered in writing, appended as a "Resolved Findings" section to this file.
- Inventory updated to reflect any discovered sites, artifacts, or consumers.
- If Q9 reveals run IDs are stored in SQLite, update [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) Step 4 to include a rename-alias layer.

**Output:** Addendum at bottom of this file.

**PR:** None (pure investigation).

---

## Step 0b — Introduce `project_paths` module with metadata registry

**Goal:** Canonical accessor module exists; metadata registry (item 9) exists. No call sites use it yet. Bodies return v1 paths.

**Tasks:**

1. Create `src/codrag/core/project_paths.py`. Accessors for every artifact in [01_PATH_INVENTORY.md](01_PATH_INVENTORY.md). Bodies return **v1 paths** (current on-disk layout).

2. Add `ArtifactMeta` dataclass and `ARTIFACT_METADATA` registry (see [06_ADJACENT_OPPORTUNITIES.md](06_ADJACENT_OPPORTUNITIES.md) item 9):

   ```python
   @dataclass(frozen=True)
   class ArtifactMeta:
       mode: int = 0o644
       sensitive: bool = False
       description: str = ""

   ARTIFACT_METADATA: dict[str, ArtifactMeta] = {
       "hr_roster": ArtifactMeta(mode=0o600, sensitive=True, description="..."),
       "daemon_lock": ArtifactMeta(mode=0o600, sensitive=True, description="..."),
   }

   def artifact_mode(name: str) -> int: ...
   def is_sensitive(name: str) -> bool: ...
   ```

3. Add `codrag_readme_path()` accessor and stub `render_readme()` function (item 3). The stub returns a placeholder string; the full implementation lands in Step 4.

4. Add `daemon_lock_path()` accessor (item 6). Body in v1 returns `idx_dir / ".daemon.lock"` so it can be used before the layout move; bumps to `idx_dir / "runtime" / "daemon.lock"` in Step 4.

5. Add `version_marker_path()` returning `idx_dir / "version.json"` (item 4). File doesn't exist under v1; the migrator creates it.

6. Constant `LAYOUT_VERSION = 1` for now. Bumps to 2 in Step 4.

7. `all_files()` and `all_dirs()` enumeration helpers that return every path the module currently knows about.

8. Write unit tests pinning every accessor to its v1 path. Metadata-registry tests assert `artifact_mode("hr_roster") == 0o600` etc.

**Acceptance:**

- Module exists; tests pass.
- No call sites changed; nothing imports `project_paths` yet.

**Verification:**

```bash
.venv/bin/pytest tests/test_project_paths.py -v
.venv/bin/ruff check src/codrag/core/project_paths.py
.venv/bin/mypy src/codrag/core/project_paths.py
```

**PR:** "Phase 113 Step 0b — project_paths module (unused)". Pure addition.

---

## Step 0c — Introduce `atomic_io` helper (item 1)

**Goal:** Atomic-write utility exists and is tested. No call sites adopt it yet.

**Tasks:**

1. Create `src/codrag/core/atomic_io.py`:

   ```python
   def atomic_write_text(path: Path, content: str, mode: int = 0o644, *, name: str | None = None, encoding: str = "utf-8") -> None: ...
   def atomic_write_bytes(path: Path, data: bytes, mode: int = 0o644, *, name: str | None = None) -> None: ...
   ```

   If `name` is supplied, mode is looked up via `project_paths.artifact_mode(name)` (overrides explicit `mode` argument when both given? pick one — default: `name` wins because it's the declarative source).

2. Write unit tests:
   - `test_atomic_write_text_creates_file`
   - `test_atomic_write_text_overwrites_atomically` (kill a process mid-write via a failure injection; confirm file is never half-written)
   - `test_atomic_write_text_removes_tmp_on_failure`
   - `test_atomic_write_text_applies_mode` (0o644 default, 0o600 for sensitive)
   - `test_atomic_write_text_respects_name_metadata` (pass `name="hr_roster"`, assert 0o600)
   - `test_atomic_write_bytes_equivalent`
   - `test_atomic_write_creates_parent_dirs`

**Acceptance:**

- Module exists; tests pass; no adopters yet.

**PR:** "Phase 113 Step 0c — introduce atomic_io helper". Pure addition.

---

## Step 0d — Introduce `project_lock` helper (item 6)

**Goal:** Advisory-lock utility exists and is tested. Not yet wired into daemon startup.

**Tasks:**

1. Create `src/codrag/core/project_lock.py` per the design in [06_ADJACENT_OPPORTUNITIES.md](06_ADJACENT_OPPORTUNITIES.md) item 6.

2. Tests:
   - `test_acquire_lock_succeeds_when_unlocked`
   - `test_acquire_lock_writes_holder_info`
   - `test_acquire_lock_refuses_when_held` (fork/subprocess holds lock; main attempt raises `LockAcquisitionError`)
   - `test_release_on_context_exit`
   - `test_release_on_exception`
   - `test_holder_info_contains_pid_hostname_started_at`

3. Document POSIX-only nature in module docstring. If run on an unsupported platform (Windows), raise a clear error.

**Acceptance:**

- Module exists; tests pass; not yet wired.

**PR:** "Phase 113 Step 0d — introduce project_lock helper". Pure addition.

---

## Step 1 — Route trace-file call sites + adopt atomic_write for trace writers

**Goal:** Every reader/writer of trace files goes through `project_paths`. Non-streaming trace writers also switch to `atomic_write_text/bytes`.

**Tasks:**

1. Replace `idx_dir / "trace_X"` literals with `project_paths.trace_X_path(idx_dir)` in:
   - `core/trace/builder.py`
   - `core/augmenter.py`
   - `core/inferred_edges.py`
   - `core/epistemic_enrichment.py`
   - `core/group_reasoning.py`
   - `core/atlas/generator.py` (trace-related writes only)
   - The modules stage
   - Any readers in `api/routers/trace_routes/*` and `services/pipeline/*`

2. For every non-streaming writer touched above, switch to `atomic_write_text`/`atomic_write_bytes`. Streaming writers (large JSONL built line-by-line during a stage) remain on their existing pattern; document the exemption in a code comment at each exempted call site.

3. Update `TRACE_FILES` in `api/routers/trace_routes/shared.py` to derive from `project_paths.all_files()` filtered to trace-namespace.

4. Update any tests that referenced old path constants or wrote trace files by hand.

**Acceptance:**

- Grep gate: `rg --type=python -e 'idx_dir / "trace_' src/` returns zero matches outside `project_paths.py` and the migrator.
- All tests pass.
- Full pipeline run on dogfood index completes.

**Verification:**

```bash
.venv/bin/pytest tests/ -v
rg --type=python -e 'idx_dir / "trace_' src/ | rg -v 'project_paths\\.py|migrator'
# ↑ expected empty
.venv/bin/codrag serve  # smoke
# manual: full pipeline run; confirm completion
```

**PR:** "Phase 113 Step 1 — route trace files through project_paths; atomic_write adoption for trace writers".

---

## Step 2 — Route remaining call sites + destroy enumeration + adopt atomic_write everywhere

**Goal:** Every remaining path-constructing site routed. Destroy enumerates from `project_paths`. All non-streaming writers use `atomic_write`.

**Tasks:**

1. Route remaining groups (knowledge, index, atlas, plans, agents, runtime, stage manifests, existing subdirs). Addressed groups per [01_PATH_INVENTORY.md](01_PATH_INVENTORY.md) §Cross-cutting.

2. Update `INDEX_FILES` and `ALL_DATA_FILES` in `shared.py` to derive from `project_paths.all_files()`.

3. **Rewrite `index_destroy_project()` in `enrichment.py`** to use `project_paths.all_files(idx_dir)` and `project_paths.all_dirs(idx_dir)`. This closes:
   - The `architecture/` omission (S6).
   - Any gap revealed by Q1.
   - Any future-added artifact (drift becomes structurally impossible).

4. Switch remaining non-streaming writers to `atomic_write_*`, passing `name=` when metadata applies. Especially: `hr_roster` writer (already atomic by hand; convert to helper), all manifest writers, `goalposts`/`roadmap`.

5. Update tests.

**Acceptance:**

- Grep gate: `rg --type=python -e 'idx_dir / "' src/ | rg -v 'project_paths\\.py|migrator|test_'` returns empty.
- All tests pass.
- Full reset on dogfood now removes `architecture/graph_state.json` (verifying S6 fix).
- Pipeline runs to completion.

**Verification:**

```bash
.venv/bin/pytest tests/ -v
rg --type=python -e 'idx_dir / "' src/ | rg -v 'project_paths\\.py|migrator|test_'
rg --type=python -e 'INDEX_FILES|TRACE_FILES|ALL_DATA_FILES' src/
# ↑ should only match project_paths-derived helpers
# manual:
ls .prep/architecture/  # present before reset
curl -X DELETE ...destroy  # trigger reset
ls .prep/architecture/ 2>&1  # expect "No such file"
```

**PR:** "Phase 113 Step 2 — route remaining paths; derive destroy from project_paths; atomic_write adoption".

---

## Step 2b — Wire daemon lock into startup (item 6)

**Goal:** Every daemon-serving codepath acquires the project lock before any reader/writer touches the index.

**Tasks:**

1. Identify the project-serving lifecycle entry point (likely `server.py` project-load or the FastAPI startup for per-project endpoints).

2. Add lock acquisition:

   ```python
   from codrag.core.project_lock import acquire_project_lock, LockAcquisitionError
   from codrag.core import project_paths

   idx_dir = project_index_dir(proj)
   lock_ctx = acquire_project_lock(project_paths.daemon_lock_path(idx_dir))
   _project_locks[proj.id] = lock_ctx  # held for daemon lifetime
   ```

3. On startup failure to acquire: return a clear HTTP 503 with holder info (pid, hostname, started_at) so the operator sees who's holding it.

4. On daemon shutdown: release locks explicitly.

5. Tests:
   - `test_startup_acquires_lock`
   - `test_startup_refuses_when_lock_held_by_another_process`
   - `test_shutdown_releases_lock`
   - Integration: spawn two daemons against the same test fixture; second must fail clearly.

**Acceptance:**

- Daemon acquires `runtime/daemon.lock` (or temporarily `.daemon.lock` in v1) at startup.
- Second daemon against same index fails loudly.
- Tests pass.

**Verification:**

```bash
# manual: start daemon, then try to start another
.venv/bin/codrag serve &
.venv/bin/codrag serve  # expect clean error with PID of first
kill %1
```

**PR:** "Phase 113 Step 2b — daemon lockfile wired into startup".

---

## Step 3 — v1 layout snapshot test

**Goal:** Lock in the current layout via a test so Step 4's migration has a verifiable before-state.

**Tasks:**

1. Add `tests/test_project_layout.py`:
   - `test_v1_layout_expected_paths`: Given a fixture populated by a known pipeline run, assert every file is at its expected v1 path.
   - `test_destroy_enumerates_everything`: Populate fixture, call destroy, assert directory is empty of known artifacts.

2. Fixture builder uses `project_paths` accessors.

**Acceptance:** Test passes against v1 bodies.

**PR:** "Phase 113 Step 3 — v1 layout snapshot test". Tests-only.

---

## Step 4 — The move (layout v2) + migrator + adjacent writes

**Goal:** Change accessor bodies to v2 layout. Migrator moves existing indexes. `version.json` and `.prep/README.md` written. Checkpoints renamed with timestamp prefix.

**Tasks:**

1. **Update `project_paths.py` accessor bodies** to v2 paths per [02_TARGET_LAYOUT.md](02_TARGET_LAYOUT.md).

2. **Bump `LAYOUT_VERSION` to 2.**

3. **Update `all_files()` / `all_dirs()`** to enumerate v2.

4. **Implement `render_readme()`** (item 3) to produce the full README content including the bucket table, schema version line, and "managed by CoDRAG, don't edit" disclaimer.

5. **Write the migrator** at `src/codrag/core/project_paths_migrator.py`:

   ```python
   V1_TO_V2_MAPPING: dict[Path, Path] = {
       # hand-maintained snapshot; v1 paths are frozen here as data
   }

   def needs_migration(idx_dir: Path) -> bool: ...

   @dataclass
   class MigrationReport:
       from_version: int
       files_moved: int
       dirs_moved: int
       files_skipped: int
       unrecognized: list[str]
       errors: list[str]

   def migrate(idx_dir: Path) -> MigrationReport:
       # 1. Refuse if .migration_in_progress exists
       # 2. Write .migration_in_progress
       # 3. Move files per V1_TO_V2_MAPPING (shutil.move, preserve mode)
       #    For sensitive files (hr_roster, daemon_lock), apply project_paths.artifact_mode(name)
       # 4. Rename checkpoint dirs: read old mtime or metadata for timestamp, rewrite as run-<ts>-<short>
       # 5. Write version.json with layout_version, daemon_version, created_at, last_migrated_at, migrator_report
       # 6. Render and atomic_write_text(codrag_readme_path(idx_dir), render_readme())
       # 7. Sweep for unrecognized files/dirs; log; leave in place
       # 8. Remove .migration_in_progress
       # 9. Return report
   ```

6. **Checkpoint rename inside migrator (item 8):** For each existing `run-<hex>/` dir:
   - Prefer a timestamp from a metadata file inside if present.
   - Fall back to `dir.stat().st_mtime`.
   - New name: `run-<YYYYMMDDTHHMMSSZ>-<hex[:8]>`.
   - If Q9 revealed run-ID cross-references (SQLite, etc.), the migrator also writes to an alias table so old run IDs remain resolvable for one version.

7. **`version.json` (item 4)** — migrator writes it at end of run with the full schema from [06_ADJACENT_OPPORTUNITIES.md](06_ADJACENT_OPPORTUNITIES.md) item 4. `created_at` preserved if a previous `version` file existed; otherwise set to now.

8. **Startup hook** — wherever the project is loaded (after lock acquisition from Step 2b, before any reader/writer fires):

   ```python
   if needs_migration(idx_dir):
       report = migrate(idx_dir)
       logger.info("Migrated %s to layout v%s: %s", proj.id, LAYOUT_VERSION, report)
   ```

9. **Migrator tests:**
   - `test_migrate_dogfood_fixture`: v1 → v2 full rename; assert every expected new path exists.
   - `test_migrate_idempotent`: run twice; second is a no-op.
   - `test_migrate_partial_resume`: hand-build half-migrated state; migrator completes.
   - `test_migrate_preserves_hr_roster_mode`: asserts 0o600.
   - `test_migrate_preserves_daemon_lock_mode`: asserts 0o600.
   - `test_migrate_unrecognized_files_logged_and_preserved`.
   - `test_migrate_refuses_on_in_progress_marker`.
   - `test_migrate_writes_version_json_with_full_schema`.
   - `test_migrate_writes_readme_md`.
   - `test_migrate_renames_checkpoints_with_timestamp`.
   - `test_migrate_applies_mode_from_artifact_metadata`.
   - `test_migrate_sets_created_at_only_once` (carries over if already present).

10. **Manual dogfood validation:**
    - `tar -czf /tmp/codrag-dogfood-pre-migration.tgz .prep/`
    - Start daemon. Inspect migration log.
    - Verify `.prep/` tree matches [02_TARGET_LAYOUT.md](02_TARGET_LAYOUT.md).
    - Verify `version.json` and `README.md` contents.
    - Verify checkpoint dirs renamed.
    - Trigger full pipeline run; confirm completion.
    - Trigger full reset; confirm true blank state.

11. **Rollback plan:** if anything goes wrong on dogfood, `rm -rf .prep/ && tar -xzf /tmp/codrag-dogfood-pre-migration.tgz`. Do not merge.

**Acceptance:**

- All tests pass.
- Dogfood index migrated successfully.
- Fresh build produces documented layout exactly.
- Full reset wipes everything.
- `version.json` and `.prep/README.md` present.

**PR:** "Phase 113 Step 4 — migrate to layout v2 (paths, version.json, README.md, checkpoint renames)".

---

## Step 4b — Log subsystem refresh (items 2, 7)

**Goal:** Pipeline logs become structured (JSONL); rotation and retention sweep prevent unbounded disk growth.

**Tasks:**

1. **Structured logs (item 7):**
   - Modify `services/pipeline_logger.py` to use a `JsonFormatter`.
   - Rename `pipeline_<ts>.log` → `pipeline_<ts>.jsonl`. (The extension is part of the `pipeline_log_path()` accessor — one-line change.)
   - Include fields: `ts` (ISO-8601 UTC with ms), `level`, `logger`, `msg`, `stage`, `run_id`, `project_id`, `exc`.
   - `mcp-stdio.log` stays freeform (it's raw MCP stdio).

2. **Size-based rotation (item 2, first half):**
   - Replace `FileHandler` with `RotatingFileHandler` for both `pipeline_<ts>.jsonl` and `mcp-stdio.log`.
   - Cap: 50 MB, 5 backups.

3. **Cross-run retention sweep (item 2, second half):**
   - New helper `services/log_retention.py` with `sweep_old_logs(logs_dir, keep_last_n=50, older_than_days=30)`.
   - Retain last 50 runs OR last 30 days, whichever keeps more.
   - Invoked from daemon startup after lock + migration, before any new log is opened.
   - Expose `codrag.log_retention.{keep_last_n, older_than_days}` as settings for power users.

4. **Tests:**
   - `test_json_formatter_emits_valid_jsonl_with_required_fields`.
   - `test_rotation_triggers_at_size_cap` (force a 60MB write, assert rollover).
   - `test_retention_keeps_last_n`.
   - `test_retention_keeps_within_age_window`.
   - `test_retention_is_union_not_intersection` (keeps the looser of the two).
   - `test_mcp_stdio_log_not_converted_to_jsonl`.

5. **Dashboard update** — if Q8 revealed log consumers, update them to parse JSONL. If the dashboard only reads via the pipeline-history API, nothing to do.

6. **Release note** — document the log format change (text → JSONL for `pipeline_*`) as breaking for any external log consumers.

**Acceptance:**

- New runs produce `pipeline_<ts>.jsonl` with structured lines.
- Rotation triggers on oversize.
- Startup sweep deletes stale logs.
- Tests pass.

**Verification:**

```bash
.venv/bin/pytest tests/test_log_retention.py tests/test_pipeline_logger.py -v
.venv/bin/codrag serve  # trigger a run
head -n 3 .prep/logs/pipeline_*.jsonl | jq .  # valid JSON per line
```

**PR:** "Phase 113 Step 4b — structured pipeline logs + rotation + retention".

---

## Step 5 — Documentation and CI lockdown

**Goal:** Update docs; enforce the grep gate in CI so regressions can't re-introduce scattered literals.

**Tasks:**

1. Update `CLAUDE.md` and `AGENTS.md` sections that reference `.prep/` paths if any. Add a short "Project paths must flow through `project_paths`" note to the project-internals doc.

2. Add `docs/architecture/project_paths.md` (or similar) documenting `project_paths` as the canonical resolver and how to add a new artifact (accessor + metadata + update `all_files`/`all_dirs`).

3. **CI grep gate:**
   - Add a CI check (pre-commit hook or CI step) that runs:
     ```
     rg --type=python -e 'idx_dir / "' src/ | rg -v 'project_paths\\.py|project_paths_migrator\\.py|test_'
     rg --type=python -e 'Path\\([^)]+\\) / "trace_|knowledge_|atlas_' src/ | rg -v 'project_paths\\.py|project_paths_migrator\\.py|test_'
     ```
   - Fails the build on non-empty output.

4. **Keep-README-synced hook (item 3):** daemon startup, after lock + migration, compares current `render_readme()` output to the on-disk `.prep/README.md` content hash; rewrites if mismatched. Small helper invoked once per startup.

5. Update [README.md](README.md) Phase 113 status to "Phase A complete".

**Acceptance:**

- Docs updated.
- CI grep gate active.
- README auto-syncs on startup.

**PR:** "Phase 113 Step 5 — docs + CI grep gate + README sync".

---

## Step 5a — `codrag doctor` CLI (item 5)

**Goal:** An operator-facing command that audits a project index against `project_paths` and flags drift.

**Tasks:**

1. Add Typer command in `src/codrag/cli.py`:

   ```python
   @app.command()
   def doctor(
       project: Optional[str] = typer.Option(None, "--project", "-p"),
       json_output: bool = typer.Option(False, "--json"),
       strict: bool = typer.Option(False, "--strict", help="Exit non-zero on warnings, not just errors"),
   ) -> None: ...
   ```

2. Implementation:
   - Resolve project (via registry, or active-project signal if omitted).
   - `expected = project_paths.all_files(idx_dir) | project_paths.all_dirs(idx_dir)`.
   - Walk `idx_dir`; compute `actual = set of relative paths`.
   - Report:
     - `OK`: declared + present + mode matches.
     - `MISSING`: declared, not present (usually fine — stage hasn't run).
     - `UNKNOWN`: present, not declared (investigate or add accessor).
     - `MODE_DRIFT`: declared sensitive mode, on-disk mode differs.
     - `STALE_VERSION`: `version.json.layout_version != LAYOUT_VERSION`.
   - Default exit: 0 unless UNKNOWN or MODE_DRIFT present.
   - `--strict`: exit non-zero if MISSING is present for artifacts whose corresponding stage is expected to have run (heuristic: check `pipeline_run_metadata.json`).

3. Tests:
   - `test_doctor_reports_ok_on_clean_fixture`.
   - `test_doctor_flags_unknown_files`.
   - `test_doctor_flags_mode_drift_for_sensitive`.
   - `test_doctor_flags_stale_version_json`.
   - `test_doctor_json_output_is_parseable`.
   - `test_doctor_exits_nonzero_on_unknown`.

4. CI integration: add a job that runs `codrag doctor --json` against a fresh-built fixture and asserts zero drift. This catches any future PR that adds a file without a corresponding `project_paths` accessor.

**Acceptance:**

- Command works against dogfood index with zero findings.
- Tests pass.
- CI job added.

**Verification:**

```bash
.venv/bin/codrag doctor --json | jq .
# expect: all OK, no UNKNOWN, no MODE_DRIFT
```

**PR:** "Phase 113 Step 5a — codrag doctor CLI".

---

## Step 6 — Phase B trigger (separate phase)

After Phase A is stable on dogfood for a week, kick off Phase B per [05_PHASE_B_DEDUPE.md](05_PHASE_B_DEDUPE.md). `codrag doctor`'s UNKNOWN list from the first week of running is the input to Phase B's triage.

---

## Summary table (revised)

| Step | Type | PR size | Risk | Adjacent items |
|---|---|---|---|---|
| 0a | Investigation | None | n/a | — (answers Q8–Q12 for items 1, 2, 6, 7, 8) |
| 0b | Pure addition | Medium | LOW | 3, 4, 6, 9 (accessors + metadata) |
| 0c | Pure addition | Small | LOW | 1 (atomic_io) |
| 0d | Pure addition | Small | LOW | 6 (project_lock) |
| 1 | Refactor + adoption | Medium | MED | 1 (atomic_write for trace) |
| 2 | Refactor + adoption | Medium | MED | 1 (atomic_write for rest), 9 (destroy uses metadata) |
| 2b | Feature addition | Small | MED | 6 (lock wire-in) |
| 3 | Test addition | Small | LOW | — |
| 4 | Move + migrator | Medium-Large | HIGH | 3, 4, 8 (README, version.json, checkpoint rename) |
| 4b | Feature addition | Medium | MED | 2, 7 (logs) |
| 5 | Docs + CI | Small | LOW | 3 (README sync) |
| 5a | Feature addition | Small | LOW | 5 (doctor) |
| 6 | Trigger | n/a | n/a | — |

**Total estimated wall time:** 4-6 days of focused work across ~2 weeks, with review and dogfood validation between PRs. The adjacent-opportunity work adds roughly a day beyond the base 2-3 days.

---

## Step 0a — Resolved Findings

*Filled in during Step 0a. Each question gets a short answer with file:line citations and any updates to the inventory.*

### Q1 — `CodeIndex.index_dir`

*[pending]*

### Q2 — Empty `.db` stubs

*[pending]*

### Q3 — `architecture/` purpose

*[pending]*

### Q4 — Trace site cardinality

*[pending]*

### Q5 — Watcher path coupling

*[pending]*

### Q6 — Non-Python readers

*[pending]*

### Q7 — Multi-project safety

*[pending]*

### Q8 — `pipeline_*.log` consumers

*[pending]*

### Q9 — Checkpoint run-ID cross-references

*[pending]*

### Q10 — Log retention expectations

*[pending]*

### Q11 — Concurrent-daemon assumption

*[pending]*

### Q12 — Streaming vs. wholesale JSONL writers

*[pending]*

### Discovery sweep additions

*[pending]*
