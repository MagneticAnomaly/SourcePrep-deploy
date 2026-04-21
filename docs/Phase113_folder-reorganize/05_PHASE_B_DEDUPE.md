# 05 — Phase B (Deferred): Dedupe and Cleanup

Phase A is "tidy and bucket without breaking anything." Phase B is "delete what's confirmed unused." We are explicitly deferring Phase B because each candidate deletion has a verification cost (read code, confirm no writers, confirm no readers), and deferring lets us:

1. Ship the layout reorganization without coupling it to investigations.
2. Use the new layout (where each artifact's accessor in `project_paths` is the source of truth) to make "unused" mean a one-grep audit.
3. Delete in a small, easy-to-revert PR.

## Phase B candidates

### B1 — Delete `index/repo_policy.json` (the duplicate)

**Status:** Likely safe.
**Verification cost:** Low (1-2 file reads, 1 grep).

**Investigation needed:**

- Confirm no writer ever creates `index/repo_policy.json`. The known writer (`repo_policy.write_repo_policy()`) writes to root.
- Confirm no reader ever reads it. The known consumers go through `policy_path_for_index()` which targets root.
- Check git log on `INDEX_FILES` — when was `repo_policy.json` added to it, and was there ever a writer at that path?

**Action if confirmed:** Remove from `INDEX_FILES`. Delete the on-disk file during Phase B migration (or leave it; reset will eventually catch it).

### B2 — Delete `codrag_settings.db` and `settings.db` (empty stubs)

**Status:** Suspect dead code.
**Verification cost:** Medium (full-tree grep, possibly cross-language).

**Investigation needed:** See [04_RISKS.md](04_RISKS.md) Q2.

- Trace every reference. Confirm no writers. Confirm no readers in any feature flag or rare code path.
- Check git log: when were they introduced? Did they ever have content? When was the writer removed?

**Action if confirmed:** Delete the files. Remove any references in `server.py`. If they cannot be confirmed dead but are confirmed empty, leave them in place and document why.

### B3 — Audit any orphaned files surfaced by Phase A migrator

**Status:** TBD until Phase A runs.

The Phase A.1 migrator includes an "unrecognized files" sweep — anything in the v1 layout without a known migration mapping gets logged and left in place. After Phase A ships and we run it on the dogfood index plus any other live indexes, the log will name every file that the centralization pass missed or that exists for unknown reasons. Each one is a Phase B candidate.

**Action:** Triage each surfaced file. For each, decide: (a) add to `project_paths` and migrate (was a real artifact we missed), (b) delete (orphan), (c) leave + document (legitimately unmanaged).

### B4 — Audit subdir contents

After Phase A, walk each subdir and confirm every file inside is accounted for:

- `index/` — the four documented files plus nothing else.
- `knowledge/` — the three documented files plus nothing else.
- `trace/` — the documented set; flag any extras.
- `atlas/` — the documented set + `segments/` + `roles/`; flag any extras.
- `audit/` — `manifest.json`, `spaghetti.json`; flag any extras.
- `git_evidence/` — `churn_60.json`, `signature_60.json`; flag any extras.
- `architecture/` — `graph_state.json`; flag any extras.
- `logs/` — `pipeline_*.log`, `mcp-stdio.log`; nothing else expected.
- `backups/` — `*_<ts>/` subdirs; flag any loose files.
- `snapshots/checkpoints/` — `_golden/` + `run-*/` subdirs.
- `snapshots/branches/` — `_branch_state.json` + `<branch>/` subdirs.
- `runtime/` — three documented files only.
- `plans/` — two documented files only.
- `agents/` — `hr_roster.json` only.
- `stages/` — four documented files only.

**Action:** Each unaccounted file becomes a B3-style triage item.

### B5 — Consider consolidating `runtime/clean_shutdown.flag` into `runtime/state.json`

After Phase A, the `runtime/` dir holds `pipeline_state.json` (a JSON document) plus two `.flag` files (zero-byte markers whose existence is the signal). It might be cleaner to fold the flags into the JSON document as boolean fields:

```json
{
  "pipeline": { ... },
  "clean_shutdown": true,
  "reset_barrier": { "active": false, "reason": "..." }
}
```

**Status:** Optional. Defer until we have other reasons to touch the recovery code.
**Risk:** Recovery semantics are sensitive. Don't make this change casually.

## Out of scope for both Phase A and Phase B

These are tracked separately because they're bigger than file reorganization:

- **SQLite store reorganization.** `codrag_data/*.db` files are their own design problem.
- **Cross-version migration framework.** Each future schema change can be a one-shot migrator following the Phase A.1 pattern. A general framework is YAGNI until we have 3+ migrations.
- **Standalone-mode global file restructuring.** `~/.local/share/prep/{registry.db, active_project.json, ...}` is its own layout question.
- **Splitting embedded vs. standalone layouts.** They share a layout today; we keep them shared.

## Phase B trigger

We start Phase B when:

1. Phase A has been merged and stable on dogfood for at least one week.
2. The Phase A.1 migrator's "unrecognized files" log has been collected from at least one full pipeline run.
3. The verification pass for each B-candidate has produced a clear yes/no.

Phase B is one PR. Total expected diff: <100 lines (mostly deletes).
