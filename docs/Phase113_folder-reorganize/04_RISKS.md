# 04 — Risks and Open Questions

## Open questions to resolve in Step 0a (before centralization)

These are factual unknowns the planning pass uncovered. Each must be answered with a code reading or a small empirical check before the centralization PR opens. None are blockers — but they shape what `project_paths.py` declares.

### Q1 — Does `CodeIndex.index_dir` already include `index/`?

**Why it matters:** `INDEX_FILES` lists `"documents.json"` etc. as basenames with no `index/` prefix, but the disk layout shows `.prep/index/documents.json`. Either:

- (a) `CodeIndex.index_dir` is `<idx_dir>/index`, in which case `INDEX_FILES` is correctly basename-only and it's the *destroy function* that's bugged (it does `idx_dir / fname` — i.e., `.prep/documents.json` — and silently no-ops); or
- (b) `CodeIndex.index_dir` is `<idx_dir>` and the writers are putting these files at the root, in which case the disk presence of `.prep/index/documents.json` is from a *different* writer (maybe the Rust engine?) and the Python `INDEX_FILES` is correct.

**How to answer:** Read `core/index.py:130-150` and confirm the value of `self.index_dir`. Trace one writer (e.g., `write_documents()`) end-to-end. Cross-check what the Rust engine writes (`engine/crates/codrag-engine/`) if it touches index files.

**Impact on plan:** If (a), the destroy function is broken and we silently knew it — the centralization step fixes this for free by giving the destroy function the same accessor the writer uses. If (b), the existing `.prep/index/` files on dogfood disk are stale orphans from an earlier version and should be cleaned during migration. Either outcome is recoverable, but the migrator must know which.

### Q2 — Are the empty `.db` stubs truly dead, or merely empty-on-this-disk?

**Why it matters:** `codrag_settings.db` and `settings.db` are 0-byte files at `.prep/` root. The path-mapping pass found references in `server.py:687,758` but no active writers. Possible explanations:

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

### Q6 — Is anything outside the daemon reading `.prep/` paths?

**Why it matters:** Strategy 2 assumes only the Python daemon constructs these paths. If the dashboard, VSCode extension, or external tooling reads `.prep/trace_nodes.jsonl` directly, the move silently breaks them.

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

### Q8 — `pipeline_*.log` consumers (gates item 7: JSONL logs)

**Why it matters:** Step 4b changes the log format from freeform text to JSONL and the extension from `.log` to `.jsonl`. Any consumer that reads these files directly (grep, tail, dashboard file-scanner, external log shipper) breaks.

**How to answer:**
- `rg -e 'pipeline_.*\\.log' src/ packages/ websites/ scripts/`
- Check the dashboard — does it read log files directly or go through an API?
- Check the MCP server — any log-related tools?
- Check any log-shipping config (systemd journal, fluentbit, etc.).

**Impact:** If consumers exist and must keep working, either (a) dual-write text + JSONL for one version, (b) update the consumers as part of Step 4b, or (c) keep text but add structured fields as tag prefixes. Default assumption: there are no external consumers, dashboard reads via API; confirm and proceed with clean JSONL switch.

### Q9 — Checkpoint run-ID cross-references (gates item 8: timestamp prefix)

**Why it matters:** Step 4 renames existing `run-<hex>/` dirs to `run-<ts>-<hex>/`. If the original ID string is stored outside the dir (pipeline journal rows, state-machine metadata, `pipeline_run_metadata.json`, log messages, dashboard history), callers resolving "run X" to its checkpoint dir will miss.

**How to answer:**
- `rg -e 'run-[a-f0-9]{8,}' src/ --type=python`
- Inspect `services/pipeline_journal.py`, `pipeline_history`, `pipeline_run_metadata.json` writers.
- Check the dashboard's run-history view for any direct path construction.

**Impact:** If cross-references exist, the migrator must maintain an alias table (`old_id → new_id` or vice versa) for at least one version, and resolvers must consult it. Simplest: add a `snapshots/checkpoints/_id_aliases.json` managed by the migrator and read by any resolver that accepts pre-v2 IDs. If no cross-references, rename is clean and no alias layer is needed.

### Q10 — Log retention expectations (gates item 2: rotation/retention)

**Why it matters:** The retention sweep defaults to "keep last 50 runs or 30 days, whichever is looser." If anyone expects unbounded retention (compliance, forensic audit, release-note archaeology), this silently deletes their data.

**How to answer:**
- Check with the team: is there a compliance requirement for log retention?
- Check if any feature (audit history, run comparison) walks logs older than 30 days.
- Check release-note / changelog workflow — does it read ancient logs?

**Impact:** If retention must be unbounded by default, leave sweep off by default and expose it as opt-in. Otherwise, default-on is correct — a developer laptop shouldn't accumulate gigabytes of old pipeline logs.

### Q11 — Concurrent-daemon assumption (gates item 6: lockfile)

**Why it matters:** Step 2b refuses to serve a project that another daemon already holds. If there's a workflow where two daemons are expected to co-exist (e.g., a read-only replica, a test harness that spawns a secondary daemon), the lock breaks it.

**How to answer:**
- Grep for multiple `codrag serve` invocations in scripts or docs.
- Check test fixtures — do integration tests spawn multiple daemons against the same index?
- Ask: is there any "read-only mode" in the daemon that would make coexistence safe?

**Impact:** If coexistence is required somewhere, add `--read-only` mode that skips lock acquisition and routes through read-only accessors only. Default assumption: one daemon per index is the only supported mode; confirm and wire accordingly.

### Q12 — Streaming vs. wholesale JSONL writers (gates item 1: atomic-write exemptions)

**Why it matters:** Step 1/2 switches writers to `atomic_write_text/bytes`. Streaming writers (JSONL files built line-by-line during a multi-minute stage) cannot use the helper — the whole file wouldn't be in memory at once. They need an explicit exemption with a code comment.

**How to answer:** For each JSONL writer (`trace_nodes`, `trace_edges`, `trace_augmented`, `trace_inferred_edges`, `trace_epistemic`, `trace_modules`, `trace_group_reasoning`), read the writer and classify:
- **Streaming:** writes one line at a time, potentially over minutes. Exempt.
- **Wholesale:** serializes the whole list and writes once. Use atomic_write.

**Impact:** Wholesale writers switch to atomic_write; streaming writers are documented as exempt with a comment (`# exempt from atomic_write — streamed during stage; rerun on failure`). The line between them may be gray for some writers; prefer exemption when unsure.

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

- Migrator runs each rename as `os.rename` (atomic on the same filesystem; `.prep/` lives entirely on one volume, so this is safe).
- Migrator writes to a temp file `.migration_in_progress` at start and removes it at end. If on next start that temp file exists, refuse to serve and report which step failed.
- Migrator is idempotent: if it sees a file already at the new path and the old path doesn't exist, it skips.
- Daemon refuses to serve a project whose `version` file is unreadable or whose migration failed; user sees a clear error rather than silent broken state.

### R3 — Migrator runs against a foreign-filesystem index

**Probability:** Low for embedded mode (everything's on the same volume); higher for standalone mode if `~/.local/share/prep/projects/` happens to be on a different mount than the user's `$HOME`.
**Severity:** Medium. `os.rename` fails with `EXDEV` across filesystems.

**Mitigation:** Use `shutil.move()` which falls back to copy+delete on `EXDEV`. Document that during the cross-filesystem case, the migration is no longer atomic.

### R4 — Watcher race during migration

**Probability:** Medium.
**Severity:** Medium. The file watcher fires on every move, potentially triggering rebuilds while we're mid-migration.

**Mitigation:** Migration runs *before* the watcher is started. The startup sequence is:

1. Resolve `project_index_dir`.
2. **Acquire daemon lock** (new in Step 2b) — prevents a second daemon from racing.
3. If `version.json.layout_version` < current, run migrator (no watcher running).
4. Sweep old log files (new in Step 4b retention).
5. Keep-README-synced check (new in Step 5).
6. Start watcher.
7. Begin serving.

This ordering must be enforced explicitly in startup code. Each new step inserts at the correct position.

### R5 — Tests reference old paths

**Probability:** High.
**Severity:** Low (tests fail loudly, not silently).

**Mitigation:**

- Use `project_paths` accessors in tests too, so they auto-update with the layout.
- Test fixtures that create fake `.prep/` trees use the accessors to know where to write.
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
- **`codrag doctor`** (Step 5a) acts as a continuous audit — every first-run after Phase A ships reports drift between disk and `project_paths`.

## Risks introduced by bundled adjacent work

These are new risks specific to the Phase 113 bundle (not the core reorg). Each is tied to its adjacent item per [06_ADJACENT_OPPORTUNITIES.md](06_ADJACENT_OPPORTUNITIES.md).

### R11 — Atomic-write helper misapplied to streaming writers

**Probability:** Medium during Step 1/2 review.
**Severity:** High. Buffering a multi-GB JSONL in memory to satisfy atomic-write would OOM the daemon.

**Mitigation:** Q12 answered explicitly in Step 0a. Each streaming writer gets an exemption comment. Code review checks for `atomic_write_*(…, content=json.dumps(huge_list))` patterns specifically.

### R12 — Lock acquisition deadlocks on crashed-daemon leftover

**Probability:** Low (fcntl.flock is released on process death).
**Severity:** Medium (user can't restart daemon).

**Mitigation:** `fcntl.flock` is released automatically when the holding process dies (kernel frees it). This handles kill -9. If the lockfile metadata (pid, hostname) references a dead PID, the replacement daemon acquires successfully and overwrites the holder info. Test: kill the daemon, immediately start a new one, confirm success.

### R13 — JSONL log format change breaks downstream consumer silently

**Probability:** Medium unless Q8 is answered thoroughly.
**Severity:** Medium (a dashboard view goes blank, logs don't ship to observability).

**Mitigation:** Q8 answered in Step 0a. All confirmed consumers updated before or as part of Step 4b. Release note explicit about the format change.

### R14 — Log retention sweep deletes something valuable

**Probability:** Low.
**Severity:** Medium (user anger if they were mid-forensic-audit).

**Mitigation:** Q10 answered. Defaults are conservative (keep 50 runs OR 30 days, whichever is looser — union, not intersection). Settings exposed for opt-out. First run logs what would be deleted (dry-run) unless a `--sweep-now` flag is set; confirm with user before enabling destructive default. (Decision point for Step 4b.)

### R15 — Checkpoint rename invalidates cross-reference in SQLite

**Probability:** Depends on Q9.
**Severity:** High (resume/restore logic points at a no-longer-existing dir).

**Mitigation:** Q9 answered. If cross-references exist, migrator writes `snapshots/checkpoints/_id_aliases.json` keyed old→new, and every resolver consults it for pre-v2 IDs. Aliases retained for at least one version before removal.

### R16 — `version.json` schema evolves and old readers can't parse

**Probability:** Low.
**Severity:** Low (only breaks if we add required fields and the old code requires them).

**Mitigation:** Readers MUST only rely on `layout_version` being present. All other fields are optional diagnostics. Document this as an invariant in the `version.json` reader code.

### R17 — `.prep/README.md` overwrites user edits

**Probability:** Low (we're explicit that the file is managed).
**Severity:** Low (README content is trivially regeneratable).

**Mitigation:** README header includes "This file is managed by CoDRAG. Edits will be overwritten." A user who edits anyway is acting against a clear sign; we accept that trade. If we ever want to preserve user additions, add `<!-- codrag-managed-start/end -->` markers like `rules_generator.py` does for `AGENTS.md`.

### R18 — `codrag doctor` false-positives on new artifacts added without accessor update

**Probability:** Medium (developers will forget).
**Severity:** Low (loud CI failure is the point).

**Mitigation:** CI job runs `codrag doctor --json` against a fresh fixture. Failing CI forces the PR author to add the accessor. This is a feature, not a bug.

## Latent bugs surfaced (that we will fix incidentally)

These are existing bugs the planning pass uncovered. We fix them as part of the centralization or the move, not as separate Phase B work.

1. **`INDEX_FILES` mismatches disk reality** (Q1). Centralization forces resolution; whichever way Q1 resolves, the result is correct.
2. **Destroy omits `architecture/`** (00_PROBLEM.md S6). Fixed when destroy switches to `project_paths.all_dirs()`.
3. **Destroy may also be omitting per-Q1 outcome**. Fixed same way.
4. **Marker dotfiles invisible to anyone debugging by `ls`**. Fixed by renaming to `.flag` files in `runtime/`.
5. **Two empty `.db` stubs sitting at root**. Migrated as-is in Phase A, deleted in Phase B once Q2 is answered.
