#!/usr/bin/env python
"""
Phase 103 R7 — PostToolUse hook: auto-capture observations from edits.

Designed as a Claude Code PostToolUse hook that runs after Edit / Write
tool invocations. Writes a single minimal observation row to the
CoDRAG observations store.  No daemon dependency (stdlib + sqlite3).

Two invocation modes:

  1. Stdin mode (Claude Code hook):
       echo '{"tool_input":{"file_path":"..."},"tool_response":{...}}' \
         | python scripts/phase103_observe_hook.py

     Parses the Claude Code PostToolUse JSON payload from stdin and
     writes an observation describing the edit.

  2. File-path mode (manual / testing):
       python scripts/phase103_observe_hook.py --file src/codrag/... \
         --tool Edit [--project-id ...]

Exits 0 on success (even when nothing written — hooks must not block
the agent). Prints a single-line status to stderr for observability.
Observation store path defaults to ``codrag_data/codrag_observations.db``
relative to the repo root (auto-detected via CODRAG_DATA_DIR or
fallback to the git toplevel).

.claude/settings.json install snippet::

    {
      "hooks": {
        "PostToolUse": [
          {
            "matcher": "Edit|Write",
            "hooks": [
              { "type": "command",
                "command": "python /path/to/scripts/phase103_observe_hook.py" }
            ]
          }
        ]
      }
    }
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional

# Filter: do not capture edits to agent-artifact files (F0 exclusion policy
# partial; kept narrow for POC — full classifier is out of scope here).
AGENT_ARTIFACT_PREFIXES = (
    ".claude/",
    ".cursor/",
    ".windsurf/",
    ".roo/",
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
    ".gitignore",
)


def resolve_data_dir() -> Path:
    env = os.environ.get("CODRAG_DATA_DIR")
    if env:
        return Path(env)
    # Try git toplevel / codrag_data
    try:
        top = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        candidate = Path(top) / "codrag_data"
        if candidate.exists():
            return candidate
    except Exception:
        pass
    return Path.cwd() / "codrag_data"


def should_skip(file_path: str) -> Optional[str]:
    """Return a reason string to skip, or None to proceed."""
    if not file_path:
        return "no-file"
    fp = file_path.replace("\\", "/")
    for prefix in AGENT_ARTIFACT_PREFIXES:
        if fp.startswith(prefix) or f"/{prefix}" in fp:
            return f"agent-artifact-{prefix.rstrip('/')}"
    return None


def parse_hook_stdin() -> Dict[str, object]:
    """Read Claude Code PostToolUse JSON payload from stdin.
    Returns dict with at minimum a 'file_path' key (may be empty).
    """
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}
    tool_input = payload.get("tool_input", {}) or {}
    tool_name = payload.get("tool_name") or payload.get("tool", "")
    # Edit / Write / NotebookEdit all carry file_path
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    old_str = tool_input.get("old_string") or ""
    new_str = tool_input.get("new_string") or ""
    lines_added = new_str.count("\n") + (1 if new_str and not new_str.endswith("\n") else 0)
    lines_removed = old_str.count("\n") + (1 if old_str and not old_str.endswith("\n") else 0)
    return {
        "file_path": file_path,
        "tool_name": tool_name,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
    }


def build_observation(
    file_path: str,
    tool_name: str,
    project_id: str,
    lines_added: int = 0,
    lines_removed: int = 0,
) -> Dict[str, object]:
    now = time.time()
    key = f"{project_id}|{file_path}|{tool_name}|{int(now)}"
    oid = hashlib.sha1(key.encode()).hexdigest()[:12]
    content = (
        f"{tool_name} on {file_path}"
        + (f" (+{lines_added}/-{lines_removed} lines)" if (lines_added or lines_removed) else "")
        + " [auto-captured by Phase 103 R7 hook]"
    )
    return {
        "id": oid,
        "project_id": project_id,
        "content": content,
        "file_path": file_path,
        "symbol_fqn": None,
        "trace_node_id": None,
        "category": "auto_capture",
        "created_at": now,
        "updated_at": now,
        "stale": 0,
        "stale_reason": None,
        "created_by": "hook:post-edit",
        "visibility": "project",
        "valid_from": now,
        "valid_to": None,
    }


def write_observation(db_path: Path, obs: Dict[str, object]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    # Schema assumed to exist (created by daemon). If not, caller may pre-init.
    conn.execute(
        """
        INSERT OR IGNORE INTO observations
          (id, project_id, content, file_path, symbol_fqn, trace_node_id,
           category, created_at, updated_at, stale, stale_reason,
           created_by, visibility, valid_from, valid_to)
        VALUES (:id, :project_id, :content, :file_path, :symbol_fqn, :trace_node_id,
                :category, :created_at, :updated_at, :stale, :stale_reason,
                :created_by, :visibility, :valid_from, :valid_to)
        """,
        obs,
    )
    conn.commit()
    conn.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--file", help="File path (manual-test mode)")
    p.add_argument("--tool", default="Edit", help="Tool name (manual-test mode)")
    p.add_argument("--project-id", default=os.environ.get(
        "CODRAG_PROJECT_ID", "1d6f0b35-45cb-427b-ae9d-aac3c6371a4b"))
    p.add_argument("--db", type=Path, default=None)
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    if args.file:
        info = {"file_path": args.file, "tool_name": args.tool,
                "lines_added": 0, "lines_removed": 0}
    else:
        info = parse_hook_stdin()

    file_path = info.get("file_path") or ""
    tool_name = info.get("tool_name") or "Edit"

    reason = should_skip(file_path)
    if reason:
        if not args.quiet:
            print(f"[r7-hook] skip: {reason}", file=sys.stderr)
        return 0

    db = args.db or (resolve_data_dir() / "codrag_observations.db")
    obs = build_observation(
        file_path=file_path,
        tool_name=tool_name,
        project_id=args.project_id,
        lines_added=info.get("lines_added", 0),
        lines_removed=info.get("lines_removed", 0),
    )
    try:
        write_observation(db, obs)
    except sqlite3.OperationalError as e:
        # e.g. table missing — observations DB not initialized yet
        if not args.quiet:
            print(f"[r7-hook] write failed: {e}", file=sys.stderr)
        return 0  # never block the agent
    if not args.quiet:
        print(f"[r7-hook] wrote obs {obs['id']} for {file_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
