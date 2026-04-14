# R7 — Automatic Observation Capture (POC)

**Date:** 2026-04-14
**Goal:** Close the write-starvation problem of the knowledge graph. Agents read `codrag_*` tools all day but rarely call `codrag_observe`. A PostToolUse hook writes a minimal observation per Edit/Write automatically — no agent initiative required.
**Status:** Hook script written, tested (manual + stdin modes + exclusion filters + latency), POC DB populated with captured observations.

## What shipped

`scripts/phase103_observe_hook.py` — ~175 lines, stdlib + sqlite3 only. Two invocation modes:

1. **Stdin mode (Claude Code PostToolUse hook):** reads the hook JSON payload, extracts `tool_name`, `file_path`, and edit diff sizes, writes one observation row.
2. **Manual mode (`--file ... --tool ...`):** lets humans / tests invoke the hook without going through the hook machinery.

## Write path

Hook writes to `codrag_data/codrag_observations.db` (via `CODRAG_DATA_DIR` env var, otherwise auto-detected from git root). Schema matches the existing `observations` table already present in the CoDRAG concept-layer DB family — no schema migration needed.

Each observation captures:

```
id             sha1-short(project + file + tool + epoch)[:12]
project_id     default CoDRAG UUID; overridable via env or flag
content        "{tool} on {file} (+N/-M lines) [auto-captured by Phase 103 R7 hook]"
file_path      the edited file
category       "auto_capture"
created_at     time.time()
created_by     "hook:post-edit"
visibility     "project"
valid_from     time.time()
```

Other columns left NULL by default (`symbol_fqn`, `trace_node_id`, `stale_reason`).

## Exclusion filter (F0 partial)

Agent-artifact files are skipped before any write. Prefixes excluded:

- `.claude/`, `.cursor/`, `.windsurf/`, `.roo/`
- `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.gitignore` at any depth

This is a deliberately narrow slice of F0's exclusion policy — full classifier is out of scope for R7. Rationale: auto-capturing edits to CoDRAG-generated files creates the same circular authority problem F0 guards against in the indexer. Keep the exclusion here so R7 is safe to ship before F0 lands in full.

## Verification

Four test invocations on the isolated POC observation store:

```
=== 1. manual mode on a real source file ===
[r7-hook] wrote obs ebd8f345d640 for src/codrag/core/auth.py

=== 2. stdin JSON mode (Claude Code hook payload) ===
[r7-hook] wrote obs 98a0992f1177 for src/codrag/core/sarif.py

=== 3. exclusion filter: .claude/agents/security.md ===
[r7-hook] skip: agent-artifact-.claude

=== 4. exclusion filter: AGENTS.md ===
[r7-hook] skip: agent-artifact-AGENTS.md

Observations table (POC DB):
  ebd8f345d640  auto_capture  by=hook:post-edit  src/codrag/core/auth.py
    → Edit on src/codrag/core/auth.py [auto-captured by Phase 103 R7 hook]
  98a0992f1177  auto_capture  by=hook:post-edit  src/codrag/core/sarif.py
    → Edit on src/codrag/core/sarif.py (+4/-3 lines) [auto-captured by Phase 103 R7 hook]

total rows: 2
```

- Stdin mode correctly extracts `+4/-3 lines` from the JSON payload's `old_string`/`new_string` diff.
- Exclusion filter correctly skips agent artifacts.
- Two real edits → two captured observations.

## Latency

10 invocations manual mode, cold subprocess each time:

```
run 1:  50.4 ms
run 2:  50.3 ms
run 3:  49.1 ms
run 4:  51.3 ms
run 5:  49.2 ms
...
run 10: 49.2 ms
```

**p95 ≈ 51ms.** Well under the R7 design doc's 100ms target. Most of that is Python interpreter startup; the actual sqlite INSERT is sub-millisecond. Fine for a PostToolUse hook that runs on every edit.

## Installation (user-facing)

Add to `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python /absolute/path/to/scripts/phase103_observe_hook.py"
          }
        ]
      }
    ]
  }
}
```

The command must be an absolute path. Use `--quiet` for cleaner terminal output.

**Explicitly opt-in.** Not installed by default. When we ship this broadly (Phase 103d), install should be gated behind a dashboard toggle or CLI flag.

## Privacy / retention

POC defers both:

- **No retention policy yet.** Observations accumulate indefinitely. The R7 design doc proposed 30-day default; a future cleanup job should implement that.
- **No per-user scoping yet.** All observations go to project-visible store. Multi-user scenarios (future) need per-user private + selectively-shared, matching the Collaborative Memory paper (arxiv 2505.18279) — out of scope now.

## What this unlocks

### The flywheel starts turning

Before R7: seeds stayed at 0 active because the graph had no writes. R5 flipped 10 to active manually. R7 adds a steady observation stream that — when paired with future clustering logic — becomes seed candidates automatically. The pipeline is:

```
edits → auto-observation (R7) → clusters → seed candidates → promotion (R5 script)
```

R7 closes the top of that pipeline. Clustering (observation → seed candidate) is future work.

### F12 temporal staleness detection (Phase 103d)

When a concept's anchor file accumulates observations, the concept's `review_status` can flip to `needs_review` (R6 schema). Direct integration: the staleness detector queries observations grouped by `file_path`, then joins against concept anchors.

### Dashboard observability

Observations are already queryable via existing CoDRAG APIs (`codrag_observe` tool). Adding a "recent edits" view to the dashboard becomes a simple `SELECT ORDER BY created_at DESC`.

## Design decisions

1. **Hook never blocks the agent.** Any write failure (missing table, locked DB, permission issue) exits 0 with a stderr note. PostToolUse hooks that fail hard would interrupt the user's workflow — not worth the risk for a non-essential telemetry feature.
2. **Stdlib only.** No pip dependencies. Runs cold-started from any Python 3 install.
3. **Minimal payload.** One row per edit. Full diffs stay in git; observations carry the pattern signal (file + tool sequence + line-delta summary).
4. **`INSERT OR IGNORE`.** If the hash collides (same project+file+tool within the same second), we silently skip. No noise.
5. **Absolute path to the script required in settings.json.** No `.` or `~` expansion. Keeps the install surface unambiguous.
6. **Quiet flag (`--quiet`).** Allows piping into `.claude/settings.json` without cluttering the agent's visible transcript.

## Out of scope (explicitly deferred)

- **Cluster-to-seed promotion.** The R7 design doc's clustering step (grouping observations by file, tool-sequence, session) becomes its own script/phase. R7 provides the raw data.
- **Scheduled retention cleanup.** 30-day default is documented; implementation pending.
- **Session-id tracking.** Claude Code's PostToolUse payload includes a session identifier; we aren't capturing it yet. Trivial to add when needed.
- **Broader F0 exclusion.** The current filter handles the obvious AGENT_DIRECT patterns. Full classifier (F0 full) is Phase 103b work.
- **Integration with the eval harness.** The hook writes to a live DB; eval reads from that DB. Natural path; not wired explicitly.

## Success criteria — met

| Criterion | Target | Actual |
|---|---|---|
| Hook implemented | yes | ✅ `scripts/phase103_observe_hook.py` |
| Stdin + manual invocation modes | yes | ✅ both |
| Writes to observations table | yes | ✅ 2 test rows |
| Exclusion filter for agent artifacts | yes | ✅ `.claude/*`, `AGENTS.md` etc. |
| p95 latency | <100ms | ✅ ~51ms |
| Never blocks agent | yes | ✅ exits 0 on all failure paths |
| Install instructions documented | yes | ✅ .claude/settings.json snippet |
| Main-tree DB untouched | yes | ✅ wrote to POC copy only |

## Running on a real project

```bash
# 1. Ensure observations table exists (daemon creates this normally)
python -c "import sqlite3; c=sqlite3.connect('codrag_data/codrag_observations.db'); c.execute('CREATE TABLE IF NOT EXISTS observations (id TEXT PRIMARY KEY, project_id TEXT, content TEXT, file_path TEXT, symbol_fqn TEXT, trace_node_id TEXT, category TEXT, created_at REAL, updated_at REAL, stale INTEGER DEFAULT 0, stale_reason TEXT, created_by TEXT, visibility TEXT DEFAULT \"project\", valid_from REAL, valid_to REAL)'); c.commit()"

# 2. Wire hook into Claude Code settings
# Edit .claude/settings.json per the snippet above

# 3. Make some edits via Claude Code — observations accumulate automatically

# 4. Inspect
sqlite3 codrag_data/codrag_observations.db "SELECT file_path, created_at FROM observations ORDER BY created_at DESC LIMIT 10"
```

That's R7 end-to-end.
