# 03 — Strategy: Centralize First, Then Move

## The choice

When reorganizing a directory whose paths are referenced from ~70 sites across ~25 source files, there are two shapes the work can take:

**Strategy 1 — Move first, fix call sites in the diff.** Decide the new layout, `git mv` the files, then grep/replace every reference in one big PR. The destroy function gets updated as part of the same change. Faster to start; one large diff to review; every missed call site is a silent regression that surfaces only when that codepath next executes.

**Strategy 2 — Centralize first, then move.** First introduce a `project_paths` module that exposes a named accessor for every artifact (`trace_nodes_path(idx_dir)`, `subdir_atlas(idx_dir)`, etc.), and update all 70 call sites to use those accessors. This is a no-behavior-change refactor that ships independently. *Then* change the bodies of the accessors to point at the new layout, write a one-shot migrator, and ship the layout change as a near-trivial diff.

We are taking Strategy 2.

## Why centralization-first is worth the up-front cost

### 1. The risk surface is the literal sites, not the layout

There are 70-ish places where a `.prep/` path string is constructed. The risk in any reorganization isn't "did we pick the right layout" — that's a design call we can make confidently. The risk is "did we miss one of the 70 sites." Strategy 1 doesn't reduce that risk; it just bundles it with the layout change. Strategy 2 isolates it: the centralization PR's only job is to prove every site has been routed through one place. After that lands, the layout change has zero remaining literal-site risk.

### 2. The accessor module is independently valuable

Even if Phase A.1 (the actual move) never shipped, the centralization PR would still be a net improvement. It:

- Eliminates ~15 scattered string literals for trace files.
- Fixes the implicit `INDEX_FILES` bug (path constants that don't match disk reality — see [00_PROBLEM.md](00_PROBLEM.md) S5 and the open question in [04_RISKS.md](04_RISKS.md)).
- Surfaces (and fixes) the missing `architecture/` in the destroy enumeration.
- Gives every future feature one place to declare a new artifact, rather than another scattered literal.

This means we get value at every checkpoint, even if external pressures cause us to defer Phase A.1.

### 3. The destroy function becomes derivable

`index_destroy_project()` today maintains two hand-curated lists: `ALL_DATA_FILES` (basenames) and an inline list of subdirs. Both lists drift behind reality (F-78 and the missing `architecture/` are both instances of this). With centralization, `project_paths` exposes `all_files(idx_dir)` and `all_dirs(idx_dir)` derived from the same accessors that writers use. Drift becomes structurally impossible: you can't add a writer without adding to `project_paths`, and you can't add to `project_paths` without `all_files()` finding it.

### 4. The migrator becomes a one-file change

In Strategy 2, the migrator does this:

- Reads the old layout's `version` file (or assumes "1" if missing).
- For each artifact, looks up its **old path** (a frozen snapshot of `project_paths` v1) and its **new path** (current `project_paths` v2).
- Atomically renames each (or `shutil.move` for cross-filesystem cases).
- Writes `version` = 2 at the end.

The "old path" snapshot is a static dict baked into the migrator at write time. We don't need any code to know about both layouts simultaneously after the migration completes — the v1 paths only exist as data inside the migrator.

In Strategy 1, by contrast, every reader/writer must either be moved atomically with the rename or know about both paths during a transition window. Either you ship a giant atomic PR (high review burden, high merge-conflict surface) or you have a transition period where bugs live in dual-path logic that's hard to remove later.

### 5. Future work compounds

Phase B (dedupe) needs to delete files. Strategy 1 requires re-checking every reference to confirm a file is unused. Strategy 2 makes "unused" mean "no accessor in `project_paths`" — a one-grep audit.

Future versioning (Phase C) needs migrators. Each one is a snapshot diff of `project_paths` between versions plus a renaming loop. Cheap.

## The trade-off we are accepting

Strategy 2 takes longer in wall-clock terms: two PRs instead of one, and the first PR (centralization) is a tedious touch-many-files refactor with no user-visible benefit. We accept this because the wall-clock cost is small (a few days) and the structural payoff (no silent regressions, valuable refactor as a byproduct, trivial future migrations) is large.

## What we are NOT doing

### Not running both layouts in parallel

There is no dual-write phase. The migrator is one-shot, idempotent, and runs on daemon startup. Either the index is in v1 layout (and gets migrated on next start) or in v2 (and is left alone). No code outside the migrator ever has to know two layouts exist.

### Not building a layout-version compatibility shim

We don't need a runtime that can read v1 layout. The migrator runs early in startup; by the time any reader executes, the layout is v2. If the migrator itself fails, the daemon refuses to serve that project until the failure is resolved. This is correct behavior — half-migrated state is the worst possible outcome.

### Not symlinking old paths to new paths

Tempting for compatibility ("the old `.prep/trace_nodes.jsonl` becomes a symlink to `.prep/trace/nodes.jsonl`"). Rejected because (a) symlinks complicate backups, (b) they hide the migration from anyone inspecting the directory, (c) the `git_evidence` accessor would need to know about and skip them, (d) Windows compatibility — though we're not officially Windows-supported, this is a deliberate choice not to add OS-specific quirks.

### Not changing the SQLite stores under `codrag_data/`

Out of scope. The SQLite stores have their own organization issues, but they're a different surface (tables, schemas, migrations) that needs its own design.

## How the strategy maps to phases and PRs

- **Phase A.0 — Centralize** (1 PR, possibly split into 2-3 if review burden is high)
  - New module `src/codrag/core/project_paths.py`.
  - All 70 call sites routed through accessors.
  - Tests prove no behavior change.

- **Phase A.1 — Move** (1 PR)
  - Change accessor bodies to new layout.
  - Add migrator.
  - Add startup hook that runs migrator if `version` < current.
  - Update destroy to use `project_paths.all_files()` and `all_dirs()`.

- **Phase A.2 — Verify and lock** (small PR + dogfood validation)
  - Snapshot test asserts a fresh build produces the documented layout.
  - Dogfood index migrated; pipeline rebuilt successfully.

- **Phase B — Dedupe** (deferred; see [05_PHASE_B_DEDUPE.md](05_PHASE_B_DEDUPE.md))
  - Delete `index/repo_policy.json` if confirmed unused.
  - Delete the two empty `*.db` stubs at root.
  - Anything else proven orphan during Phase A.

Each PR is independently shippable and reversible. Centralization without the move is a useful refactor on its own; the move without future Phase B work is a useful reorganization on its own.

## Definition of done for the Strategy 2 mindset

Centralization is "done" when:

```
$ rg --type=python -e "\\.prep/" src/codrag/
$ rg --type=python -e "Path\\([^)]+\\) / \"trace_" src/codrag/
$ rg --type=python -e "INDEX_FILES|TRACE_FILES|ALL_DATA_FILES" src/codrag/
```

…the first two return zero matches outside `project_paths.py` and tests, and the third returns matches only in a deprecation shim or has been replaced by `project_paths.all_files()`.

Move is "done" when a fresh `codrag init` followed by a full pipeline run produces a directory tree byte-identical (modulo content) to [02_TARGET_LAYOUT.md](02_TARGET_LAYOUT.md).
