# 04 — Integration: TODO Churn Gating

The single Phase 105 integration. Replaces the larger
`04_INTEGRATION_ROADMAP.md` document from the initial brainstorm.

## Where it goes

`src/codrag/core/todo_scanner.py`, in `scan_todos()`, after the
annotation-pattern matching loop produces `RoadmapNode`s and before
`scan_todos` returns them.

## Logic

```python
# After the existing scan loop produces `nodes: List[RoadmapNode]`:
try:
    from codrag.services.git_evidence_service import get_git_evidence
    evidence = get_git_evidence(project_root)
except Exception:
    evidence = None   # Not a git repo, shallow clone fallback, etc.

if evidence is not None:
    churn = evidence.recent_churn_by_file(window_days=180)

    for node in nodes:
        # source_ref shape for todo_scan nodes is "file:<path>:<line>"
        path = _path_from_source_ref(node.source_ref)
        if path is None:
            continue
        if path not in churn:
            node.priority = "P3"
            suffix = " [stale: file not touched in 180d]"
            if suffix not in node.description:
                node.description = (node.description or "") + suffix
```

That is the whole change.

## What the helper parses

`source_ref` for `todo_scan` nodes today looks like `"file:<path>:<line>"`.
Implementation will parse the middle segment. Verify the exact
format during implementation; adjust accordingly. If a node's
`source_ref` does not match the expected shape, skip gating for that
node (safe default — no change in behavior).

## Configuration

| Setting | Default | Configurable via |
|---------|---------|------------------|
| `window_days` | 180 | `settings.git_evidence.todo_stale_window_days` |
| Demotion target priority | `P3` | Hardcoded in v1; configurable later if needed |
| Description suffix | `[stale: file not touched in Nd]` | Hardcoded; templated |

Defaults chosen:

- **180 days** — generous. A TODO in a file touched in the last six
  months is "live enough." Shorter windows increase false-demotion
  risk on slow-moving but valid code (e.g., stable infrastructure
  files with legitimate pending TODOs).
- **P3** not "drop" — a demoted TODO still exists, just doesn't
  dominate ranking. Users can still find and act on it.

## Guard rails

1. **Fail-open.** If the evidence module raises or returns `None`,
   skip gating entirely. Scanner returns today's output.
2. **Not a git repo.** Evidence module returns `None` quickly; same
   fail-open path.
3. **Shallow clone.** If `git rev-parse --is-shallow-repository` is
   `true`, the evidence module logs a one-time warning and returns
   `None` for churn queries that would need depth. Gating is skipped.
4. **Shared path with the scanner's own `_SKIP_DIRS`.** The evidence
   module's exclusions must be a superset of or compatible with the
   scanner's. Both should read from
   `repo_profile.DEFAULT_EXCLUDE_DIR_NAMES`.
5. **CoDRAG-managed files.** Exclude `AGENTS.md`, `CLAUDE.md`,
   `.prep/**`, `.cursor/**` from churn evaluation. If a TODO lives in
   one of those files, skip gating for it (per-memory: auto-regenerated
   files pollute signals).

## What does not change

- `todo_scanner.py`'s scan patterns (TODO, FIXME, HACK, …).
- `todo_scanner.py`'s directory exclusions.
- The `source` value on the produced nodes (`"todo_scan"` still).
- The `id` hash of the produced nodes (source_ref and title drive it —
  we don't modify either).
- The router, the UI, the atlas, the watcher, the pipeline.

## Testing

1. **Fixture repo test — touched recently.** Create a fixture git repo,
   commit a file with a TODO yesterday, run scanner. Assert node
   priority is **not** `P3`.
2. **Fixture repo test — untouched in window.** Commit the same file
   with a TODO, then simulate time passage (or use a long window like
   10 days with a commit dated 30 days ago). Assert node priority
   **is** `P3` and description contains `[stale:`.
3. **Non-git dir.** Run scanner in a directory with no `.git/`. Assert
   no exceptions, no demotions, same node count.
4. **Excluded file.** TODO in `AGENTS.md` (or equivalent). Assert not
   demoted even if "untouched."
5. **source_ref with unexpected shape.** Inject a malformed source_ref.
   Assert skip, no exception.
6. **End-to-end dogfood.** Run against this repo. Eyeball the
   demoted-node list. Expect at least one genuine stale-file demotion;
   expect zero demotions on files I (Eric) recognize as actively-worked.

## Rollback plan

Single-flag: if `settings.git_evidence.enabled` is `false`, the scanner
skips the gating block entirely. Default `true` after the phase ships.

This lets us turn the feature off instantly if dogfood surfaces a
problem without reverting the PR.
