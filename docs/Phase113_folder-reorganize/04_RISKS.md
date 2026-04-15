# 04 — Risks and Open Questions

## Open questions to resolve in Step 0a (before centralization)

These are factual unknowns the planning pass uncovered. Each must be answered with a code reading or a small empirical check before the centralization PR opens. None are blockers — but they shape what `project_paths.py` declares.

### Q1 — Does `CodeIndex.index_dir` already include `index/`?

**Why it matters:** `INDEX_FILES` lists `"documents.json"` etc. as basenames with no `index/` prefix, but the disk layout shows `.codrag/index/documents.json`. Either:

- (a) `CodeIndex.index_dir` is `<idx_dir>/index`, in which case `INDEX_FILES` is correctly basename-only and it's the *destroy function* that's bugged (it does `idx_dir / fname` — i.e., `.codrag/documents.json` — and silently no-ops); or
- (b) `CodeIndex.index_dir` is `<idx_dir>` and the writers are putting these files at the root, in which case the disk presence of `.codrag/index/documents.json` is from a *different* writer (maybe the Rust engine?) and the Python `INDEX_FILES` is correct.

**How to answer:** Read `core/index.py:130-150` and confirm the value of `self.index_dir`. Trace one writer (e.g., `write_documents()`) end-to-end. Cross-check what the Rust engine writes (`engine/crates/codrag-engine/`) if it touches index files.

**Impact on plan:** If (a), the destroy function is broken and we silently knew it — the centralization step fixes this for free by giving the destroy function the same accessor the writer uses. If (b), the existing `.codrag/index/` files on dogfood disk are stale orphans from an earlier version and should be cleaned during migration. Either outcome is recoverable, but the migrator must know which.

### Q2 — Are the empty `.db` stubs truly dead, or merely empty-on-this-disk?

**Why it matters:** `codrag_settings.db` and `settings.db` are 0-byte files at `.codrag/` root. The path-mapping pass found references in `server.py:687,758` but no active writers. Possible explanations:

- They were used in a prior version, code was removed, files survive as zombies → safe to delete in Phase B.
- They're written by some seldom-run codepath (settings export, project clone, etc.) → must NOT delete.
- They're created on-demand and only filled by certain feature flags → must NOT delete.

**How to answer:** `rg "codrag_settings\\.db|settings\\.db"` across the whole tree (Python, JS/TS, scripts). Inspect any matches that aren't the two known references. Confirm with git log on the references — were they always read-only, or was there a writer that got removed?

**Impact:** Affects Phase B scope. Phase A treats them as opaque files and migrates them as-is (move into `runtime/` if any reference remains, leave at root if truly stale).

### Q3 — Where is `architecture/graph_state.json` written, and is it load-bearing?

**Why it matters:** Destroy omits `architecture/`. Either the dir is dead code, or reset is leaving important state behind that selfheal could resurrect.

**How to answer:** Find writer (`architecture_state.py:25` per path-mapping). Find readers. Confirm whether the file affects pipeline behavior on next run after reset.

**Impact:** If load-bearing, the destroy fix is a real bug fix bundled into Phase A. If dead code, deletes during Phase B.

### Q4 — What's the actual cardinality of trace-file call sites?

**Why it matters:** The "~40 sites" estimate was extrapolated. The centralization PR is sized off this number. If it's actually 80, we split the PR.

**How to answer:**

```
rg --type=python -e 'trace_(nodes|edges|augmented|inferred|epistemic|modules|group_reasoning|manifest|swarm)' src/ | wc -l
rg --type=python -e 'idx_dir / "trace_' src/ | wc -l
rg --type=python -e 'index_dir / "trace_' src/ | wc -l
```

**Impact:** PR sizing.

### Q5 — Does the file watcher key off old paths anywhere?

**Why it matters:** The watcher resurrects state from backups when it sees changes. If it's hardcoded to watch `trace_nodes.jsonl`, moving the file to `trace/nodes.jsonl` could leave the watcher oblivious.

**How to answer:** Inspect `services/file_watcher.py` (or wherever the watcher lives) for path constants.

**Impact:** Watcher may need its own accessor list. Worth knowing before the move.

### Q6 — Is anything outside the daemon reading `.codrag/` paths?

**Why it matters:** Strategy 2 assumes only the Python daemon constructs these paths. If the dashboard, VSCode extension, or external tooling reads `.codrag/trace_nodes.jsonl` directly, the move silently breaks them.

**How to answer:**

```
rg -e '\\.codrag' packages/ src/codrag/dashboard/ websites/
rg -e 'trace_nodes|trace_edges|knowledge_documents' packages/ src/codrag/dashboard/
```

**Impact:** Frontend (TypeScript) shouldn't be reading raw indexed files — it should go through the API. But confirm. Any direct readers must be updated as part of Phase A.1 or routed through the API in advance.

### Q7 — Multiple-project safety

**Why it matters:** A daemon serving multiple projects may have one in v1 layout and one in v2. The migrator must run per-project, not globally.

**How to answer:** Confirm by design — the migrator hook fires when a project is opened/loaded, not at daemon boot. Each project's `version` file is independent.

**Impact:** Already accounted for. Documented for clarity.

## Risks (after the open questions are answered)

### R1 — Missed call site → silent regression

**Probability:** Medium without centralization, low with it.
**Severity:** High. A missed call site silently writes/reads from the wrong path. Worst case it gets backfilled by selfheal from the *correct* path (if the correct path exists) and works; common case is an empty file or a 404.

**Mitigation:** Strategy 2 itself. After centralization:

- Grep gates (see [03_STRATEGY.md](03_STRATEGY.md) "Definition of done").
- Snapshot test that compares a fresh-build directory tree to the documented layout.
- Dogfood validation: full reset + full rebuild on the working repo before merge.

### R2 — Migrator failure mid-flight

**Probability:** Low; the migrator is mostly atomic renames.
**Severity:** High. Half-migrated state can break recovery in weird ways.

**Mitigation:**

- Migrator runs each rename as `os.rename` (atomic on the same filesystem; `.codrag/` lives entirely on one volume, so this is safe).
- Migrator writes to a temp file `.migration_in_progress` at start and removes it at end. If on next start that temp file exists, refuse to serve and report which step failed.
- Migrator is idempotent: if it sees a file already at the new path and the old path doesn't exist, it skips.
- Daemon refuses to serve a project whose `version` file is unreadable or whose migration failed; user sees a clear error rather than silent broken state.

### R3 — Migrator runs against a foreign-filesystem index

**Probability:** Low for embedded mode (everything's on the same volume); higher for standalone mode if `~/.local/share/codrag/projects/` happens to be on a different mount than the user's `$HOME`.
**Severity:** Medium. `os.rename` fails with `EXDEV` across filesystems.

**Mitigation:** Use `shutil.move()` which falls back to copy+delete on `EXDEV`. Document that during the cross-filesystem case, the migration is no longer atomic.

### R4 — Watcher race during migration

**Probability:** Medium.
**Severity:** Medium. The file watcher fires on every move, potentially triggering rebuilds while we're mid-migration.

**Mitigation:** Migration runs *before* the watcher is started. The startup sequence is:

1. Resolve `project_index_dir`.
2. If `version` < current, run migrator (no watcher running).
3. Start watcher.
4. Begin serving.

This ordering needs to be enforced explicitly in startup code.

### R5 — Tests reference old paths

**Probability:** High.
**Severity:** Low (tests fail loudly, not silently).

**Mitigation:**

- Use `project_paths` accessors in tests too, so they auto-update with the layout.
- Test fixtures that create fake `.codrag/` trees use the accessors to know where to write.
- Keep one explicit migrator test that hand-builds a v1 layout, runs the migrator, asserts v2 layout — this test must NOT use the accessors for the "before" side.

### R6 — Backward-incompatible for older daemons

**Probability:** N/A (we control daemon distribution).
**Severity:** N/A.

**Mitigation:** None needed. We migrate forward, never backward. If a user downgrades the daemon, they need to either stay on the old version or rebuild.

### R7 — `hr_roster.json` permissions lost during move

**Probability:** Medium if we use a naive `shutil.move`.
**Severity:** Medium (file leak, not data loss).

**Mitigation:** Migrator preserves mode bits explicitly. After every move, `os.chmod(new_path, 0o600)` for sensitive files. Add a smoke test.

### R8 — `index_destroy_project()` derivation misses something

**Probability:** Low *if* we derive from `project_paths`; high if we maintain a parallel list.
**Severity:** High (this is exactly the F-78 class of bug).

**Mitigation:** Don't maintain a parallel list. `project_paths` exposes `all_files(idx_dir)` and `all_dirs(idx_dir)`. Destroy uses those exclusively. New artifacts added later automatically participate in destroy.

### R9 — Migration on an in-flight pipeline

**Probability:** Low (user would have to restart daemon mid-build).
**Severity:** High (mid-write file moved out from under a writer = corruption).

**Mitigation:** Migrator runs at startup, before any pipeline can be running for that project. Refuse to migrate if the orchestrator reports a build in progress (shouldn't happen at startup but check anyway).

### R10 — The plan misses an artifact entirely

**Probability:** Medium. The path-mapping pass found a lot, but is unlikely to be exhaustive.
**Severity:** Low if discovered during dev (just add to `project_paths`); medium if discovered post-merge (a stage's first run after migration writes to an unmigrated path).

**Mitigation:**

- Step 0a includes a discovery pass: `rg --type=python -e 'idx_dir / "' src/` and similar.
- The destroy function being derived from `project_paths` means any artifact missed from `project_paths` will never be cleaned up by reset — running a full reset and re-checking the directory after will surface anything orphaned.
- Migrator includes an "unrecognized files" sweep: anything in the v1 layout that doesn't have a known migration path gets logged + left in place + flagged in startup output. Operator can decide.

## Latent bugs surfaced (that we will fix incidentally)

These are existing bugs the planning pass uncovered. We fix them as part of the centralization or the move, not as separate Phase B work.

1. **`INDEX_FILES` mismatches disk reality** (Q1). Centralization forces resolution; whichever way Q1 resolves, the result is correct.
2. **Destroy omits `architecture/`** (00_PROBLEM.md S6). Fixed when destroy switches to `project_paths.all_dirs()`.
3. **Destroy may also be omitting per-Q1 outcome**. Fixed same way.
4. **Marker dotfiles invisible to anyone debugging by `ls`**. Fixed by renaming to `.flag` files in `runtime/`.
5. **Two empty `.db` stubs sitting at root**. Migrated as-is in Phase A, deleted in Phase B once Q2 is answered.
