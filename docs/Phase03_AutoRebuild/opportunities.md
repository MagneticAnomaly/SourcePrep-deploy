# Opportunities — Phase 03 (Auto-Rebuild)

## Purpose
Track robustness opportunities for keeping indexes fresh without rebuild storms.

## Opportunities (robustness)
- **3-layer storm control**:
  - event dedup window (e.g., suppress duplicate save events within 1–2s)
  - debounce window (e.g., 5s)
  - minimum gap / throttled state when changes never settle
- **Atomic-write handling**: treat rename/move events as “final write”; ignore temp files; avoid indexing partial files.
- **Watcher fallback modes**: OS events first; if watcher setup fails/slow (large repos, network FS), fall back to polling with adaptive interval.
- **Periodic reconciliation sweep**: optional per-project background sweep every N minutes to catch missed file events by re-checking hashes.
- **Two-phase rebuild pipeline**: parse/store quickly; run embeddings as a separate queued phase with backpressure so search stays responsive.
- **Chunk-level diffs**: within changed files, preserve embeddings for unchanged chunks; only re-embed modified/new chunks.
- **Git-aware triggers (optional)**: detect branch switching via `.git/HEAD` changes or offer opt-in git hooks (post-checkout/post-merge/post-commit) to trigger rebuild.
- **Per-file timeout + quarantine list**: skip pathological files, record failures, and propose excludes.
- **Path normalization**: canonicalize paths to avoid macOS `/var` vs `/private/var` mismatch.

## Opportunities (dashboard tools + settings)
- **Watch state inspector**: expose the watch block described in Phase03 as a first-class UI card:
  - enabled
  - state (`disabled|idle|debouncing|building|throttled`)
  - debounce interval
  - pending paths count
  - next rebuild ETA
- **“What changed?” panel**: show a bounded list of pending paths (or top-N directories) collected during the debounce window.
- **Storm control settings (advanced)**:
  - debounce interval
  - minimum gap between rebuilds
  - throttle behavior when changes never settle
  - polling fallback toggle (and polling interval bounds)
- **Loop avoidance controls**:
  - explicit “ignore outputs” UI that shows the resolved ignore list (including `.runprep/**` and `.git/**`)
  - a warning banner when the index directory is inside the watched tree (embedded mode)
- **Manual reconciliation tool**: a “Re-scan for missed changes” action that compares hashes to the manifest and updates staleness state without a full rebuild.

## Opportunities (meaningful visualization)
- **Rebuild cadence chart**: rebuilds per hour/day + average build duration (helps diagnose stormy repos and aggressive settings).
- **Event burst visualization**: small sparkline of file events over time with markers for when builds started/finished.
- **Pending queue gauge**: pending paths count over time; highlight when the system enters `throttled`.
- **Top churn areas**: “most changed directories since last build” (helps users decide what to exclude or split).

## Hazards
- **Rebuild storms and CPU spikes**: continuous edits can trigger constant rebuilding without robust debounce/throttle.
- **Watch loops in embedded mode**: if `.runprep/**` isn’t excluded reliably, the system can rebuild forever.
- **Missed events**: network filesystems, editor save patterns, and OS watcher limits can cause staleness to be wrong.
- **Atomic write edge cases**: indexing temp files or half-written files produces misleading chunks and unstable IDs.
- **Build contention**: multiple builds per project must be serialized; “pending rebuild” must be visible and deterministic.

## References
- ChunkHound real-time indexing service:
  - https://raw.githubusercontent.com/chunkhound/chunkhound/main/chunkhound/services/realtime_indexing_service.py
- ChunkHound issue #168 (non-TTY progress failure)
- `docs/Phase03_AutoRebuild/README.md`
- `docs/WORKFLOW_RESEARCH.md` (A1-J4)
