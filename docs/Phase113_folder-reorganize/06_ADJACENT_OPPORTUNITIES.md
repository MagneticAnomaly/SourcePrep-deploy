# 06 — Adjacent Opportunities (Bundled Into Phase 113)

Phase 113's core work is the `.prep/` reorganization. While doing it we are touching every writer, every path-constructing site, and the startup/shutdown lifecycle. That surface overlaps naturally with a small set of foundation/plumbing improvements that share the property **"the marginal cost of doing this now is materially less than the marginal cost of doing it later"**. This document catalogs the improvements we are bundling, their designs, and where they slot into the implementation plan.

Items that were considered and rejected as out-of-scope are listed at the end for traceability.

## The bundled nine

| # | Item | Where it plugs in |
|---|---|---|
| 1 | Atomic-write helper (`core/atomic_io.py`) | New Step 0c; adopted in Steps 1, 2 |
| 2 | Log rotation + retention | New Step 4b |
| 3 | `.prep/README.md` auto-generation | Step 4 (migrator writes it) |
| 4 | `version` → `version.json` with daemon metadata | Step 4 (migrator writes it) |
| 5 | `codrag doctor` CLI | New Step 5a |
| 6 | Real daemon lockfile (`core/project_lock.py`) | New Step 0d; wired in new Step 2b |
| 7 | Structured (JSONL) pipeline logs | New Step 4b |
| 8 | Checkpoint run-ID gets timestamp prefix | Step 4 (migrator renames existing) |
| 9 | Per-artifact mode/sensitivity metadata | Step 0b (in `project_paths`) |

Each is designed below in enough detail for the implementation step to proceed without re-deriving it. Where an item introduces new open questions, those are cross-referenced into [04_RISKS.md](04_RISKS.md).

---

## 1. Atomic-write helper

### What

A single utility that every writer in the codebase uses to write a file atomically: temp file → flush → fsync → rename. Today this pattern is implemented ad-hoc (e.g., `agents/hr/roster.py:51` does it for the roster file). Most writers just do `path.write_text(...)`, which leaves a half-written file on disk if the daemon is killed mid-write.

### Design

New module `src/codrag/core/atomic_io.py`:

```python
from __future__ import annotations
import os
from pathlib import Path
from typing import Union

DEFAULT_MODE = 0o644
SENSITIVE_MODE = 0o600


def atomic_write_text(
    path: Path,
    content: str,
    mode: int = DEFAULT_MODE,
    encoding: str = "utf-8",
) -> None:
    """Atomically write text to path.

    Writes to a sibling temp file, fsyncs it, then renames over the target.
    On POSIX the rename is atomic; a reader will see either the old content
    or the new content but never a half-written file.

    Raises the original exception on failure after cleaning up the temp file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        with open(tmp, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)  # atomic
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def atomic_write_bytes(path: Path, data: bytes, mode: int = DEFAULT_MODE) -> None:
    """Atomically write bytes to path. See atomic_write_text docstring."""
    # same pattern as atomic_write_text, binary flags
```

### Adoption scope

Every writer whose accessor lives in `project_paths` and whose payload is text/bytes small enough for a full in-memory serialize. Specifically: all JSON, all manifest files, all JSONL files that are rewritten wholesale rather than appended.

**NOT in scope** for atomic replacement:

- JSONL files that are streamed line-by-line (`trace_nodes.jsonl`, `trace_edges.jsonl` — multi-GB, streamed during build). These use their existing write patterns, which are idempotent on failure (you rerun the stage). Document why they're exempt.
- `.npy` files written by numpy — numpy's `save` is not atomic but we trust it.
- SQLite — has its own ACID guarantees.

### Open questions

Q12 (new): which writers currently stream JSONL vs. rewrite whole? Decide exemption set during Step 0a. See [04_RISKS.md](04_RISKS.md).

### Step placement

- **New Step 0c** — introduce the module and unit tests; no adoption.
- **Step 1** — trace writers (non-streaming) switch over as part of routing through `project_paths`.
- **Step 2** — remaining writers switch over.

---

## 2. Log rotation and retention

### What

Today, `pipeline_<ts>.log` files in `logs/` accumulate forever. A single run can also produce an arbitrarily large log if a stage misbehaves. Both are disk-usage hazards.

### Design

Two mechanisms, independent:

**Per-file size cap.** Use `logging.handlers.RotatingFileHandler` for each `pipeline_<ts>.log`. Cap: 50 MB per file, 5 rollovers. Unlikely to trigger in normal runs but prevents a runaway log from filling disk.

**Cross-run retention sweep.** On daemon startup, enumerate `logs/pipeline_*.log*` and delete anything older than the retention window. Default: keep last 50 pipeline logs *or* last 30 days' worth, whichever is looser. Exposed as `codrag.log_retention` settings.

`mcp-stdio.log` gets the same size cap (50 MB, 5 rollovers). It's a singleton per daemon so no cross-run sweep needed.

### Implementation location

- Rotation: `services/pipeline_logger.py` — swap `FileHandler` for `RotatingFileHandler`.
- Retention sweep: new helper in `services/log_retention.py`, invoked from the daemon-startup path that's already running the migrator.

### Open questions

Q10 (new): does anyone consume `pipeline_*.log` files post-hoc (audit, dashboard history view, external tail)? If yes, confirm retention policy is acceptable. See [04_RISKS.md](04_RISKS.md).

### Step placement

- **New Step 4b** — implement rotation + retention; ships after the layout move so the `logs_dir()` accessor is pointing at the right place.

---

## 3. `.prep/README.md` auto-generation

### What

A generated README inside the project index directory that explains what each bucket is for. Zero runtime cost; read by any contributor who opens `.prep/` wondering what they're looking at.

### Design

New accessor in `project_paths`:

```python
def codrag_readme_path(idx_dir: Path) -> Path:
    return idx_dir / "README.md"
```

New function in `project_paths`:

```python
def render_readme() -> str:
    """Return the documented layout + per-bucket purpose as a markdown string.

    Sourced from a template + the LAYOUT_VERSION + project_paths accessors
    so the README can never go stale relative to the actual layout.
    """
```

The migrator calls `render_readme()` at the end of its run and writes the result via `atomic_write_text(codrag_readme_path(idx_dir), content)`. On subsequent daemon startups, if the README's content hash doesn't match the current `render_readme()` output, it is rewritten (so a future layout bump automatically refreshes every project's README).

Content of the generated README (condensed):

```markdown
# CoDRAG project index

This directory is managed by CoDRAG. It is gitignored by default.
Do not edit files here by hand — they are rebuilt by the pipeline.

Schema version: 2 (see version.json)

## Layout

- `project.json` — identity pointer
- `repo_policy.json` — file-selection policy
- `runtime/` — pipeline state, markers, daemon lock
- `plans/` — goalposts and roadmap (edit-friendly)
- `agents/` — agent state
- `index/` — search index (code documents)
- `knowledge/` — knowledge index (docs/comments)
- `trace/` — trace graph artifacts
- `atlas/` — codebase atlas and routing
- `stages/` — manifests for SQLite-backed stages
- `architecture/` — graph state
- `audit/` — audit findings and manifest
- `git_evidence/` — git churn/signature cache
- `logs/` — pipeline and MCP logs (rotated + retention-swept)
- `snapshots/` — checkpoints and branch snapshots
- `backups/` — debug-mode backups

See docs/Phase113_folder-reorganize/02_TARGET_LAYOUT.md for details.
```

### Step placement

- **Step 0b** — add `codrag_readme_path()` accessor and `render_readme()` stub.
- **Step 4** — migrator writes the README as its last step.
- **Step 5** — daemon startup keeps the README in sync (writes if content hash mismatches).

---

## 4. `version.json` with daemon metadata

### What

Originally planned as a bare `version` file containing an integer. Bumping to JSON costs nothing and lets us record which daemon version performed the migration, when it was created, and when it was last migrated. That's useful diagnostic data when something goes wrong.

### Design

File renamed from `version` to `version.json`. Schema:

```json
{
  "layout_version": 2,
  "daemon_version": "0.42.0",
  "created_at": "2026-04-10T09:00:00Z",
  "last_migrated_at": "2026-04-15T14:00:00Z",
  "migrator_report": {
    "from_version": 1,
    "files_moved": 31,
    "dirs_moved": 4,
    "files_skipped": 2,
    "unrecognized": []
  }
}
```

- `layout_version` — the integer used by `needs_migration()` comparisons. Authoritative.
- `daemon_version` — `codrag.__version__` at write time.
- `created_at` — set once, on first write; never changes.
- `last_migrated_at` — updated on every successful migration.
- `migrator_report` — last migration's report, kept for diagnostics.

Accessor:

```python
def version_marker_path(idx_dir: Path) -> Path:
    return idx_dir / "version.json"
```

### Step placement

- **Step 0b** — accessor.
- **Step 4** — migrator reads/writes this file.

---

## 5. `codrag doctor` CLI

### What

A command that inspects a project index directory and reports:

- Files/dirs expected by `project_paths` and present (OK)
- Files/dirs expected and missing (likely normal for stages that haven't run, but flagged)
- Files/dirs present but not declared in `project_paths` (**unknown — investigation needed**)
- Files whose on-disk mode does not match the declared `ArtifactMeta.mode` (**mode drift**)
- Whether `version.json` matches `LAYOUT_VERSION`

Exits non-zero if any unknown or mode-drift items are found. Output is human-readable by default, `--json` for machine use (CI).

### Design

New Typer command in `src/codrag/cli.py`:

```python
@app.command()
def doctor(
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Audit a project index directory against the declared layout."""
    ...
```

Implementation:

1. Resolve project via registry (or active-project signal if `--project` omitted).
2. Compute `expected_files = set(project_paths.all_files(idx_dir))`.
3. Compute `expected_dirs = set(project_paths.all_dirs(idx_dir))`.
4. Walk `idx_dir` and collect actual files and subdirs.
5. Compute set differences and mode drift.
6. Format report.

This is the regression guard for Phase B (nothing gets silently orphaned) and for future accretion (new code adding an artifact without a `project_paths` accessor is caught by CI running `codrag doctor --json` against a fixture).

### Step placement

- **New Step 5a** — implement the command and add a CI invocation against a fixture project.

---

## 6. Daemon lockfile for concurrent-daemon safety

### What

Today two daemons can be pointed at the same project index and will race for writes. `.reset_barrier` is a half-baked lock for one specific scenario (a reset is in progress) but does not prevent generic concurrent-daemon corruption. We add a real advisory lock, held for the lifetime of the daemon, specific to a project index directory.

### Design

New module `src/codrag/core/project_lock.py`:

```python
from __future__ import annotations
import errno
import fcntl
import json
import os
import socket
from contextlib import contextmanager
from pathlib import Path


class LockAcquisitionError(Exception):
    """Another daemon holds the lock for this project index."""
    def __init__(self, holder_info: dict):
        super().__init__(f"Project locked by: {holder_info}")
        self.holder_info = holder_info


@contextmanager
def acquire_project_lock(lock_path: Path, *, blocking: bool = False):
    """Acquire a per-project advisory lock (fcntl.flock).

    Writes holder metadata (pid, hostname, started_at) into the lockfile
    so diagnostics can report who holds it. Releases on context exit.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        op = fcntl.LOCK_EX if blocking else (fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            fcntl.flock(fd, op)
        except OSError as e:
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                holder = _read_holder(lock_path)
                raise LockAcquisitionError(holder) from e
            raise
        holder_info = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "started_at": _now_iso(),
        }
        os.ftruncate(fd, 0)
        os.write(fd, json.dumps(holder_info).encode())
        os.fsync(fd)
        try:
            yield holder_info
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
```

Accessor:

```python
def daemon_lock_path(idx_dir: Path) -> Path:
    return idx_dir / "runtime" / "daemon.lock"
```

Wire-in: the daemon's project-serving startup path acquires the lock before any reader/writer runs, and holds it for the process lifetime. Refuses to serve (with a clear error) if another daemon holds it. The lockfile's mode is 0o600 (holder info is diagnostic, not secret, but matches our sensitive-file convention).

### Platform note

`fcntl.flock` is POSIX-only. macOS + Linux, which is all we officially support. If a Windows implementation is ever needed, use `msvcrt.locking` in an alternate branch. Document in the module.

### Step placement

- **New Step 0d** — introduce the module and tests.
- **New Step 2b** — wire the lock acquisition into daemon startup. Temporarily operates on the v1-layout path `runtime/daemon.lock` doesn't exist yet, so the accessor body returns `idx_dir / ".daemon.lock"` at that time and is updated to `runtime/daemon.lock` in Step 4.

---

## 7. Structured (JSONL) pipeline logs

### What

`pipeline_<ts>.log` becomes `pipeline_<ts>.jsonl` with each line a JSON object:

```json
{"ts": "2026-04-15T14:30:22.123Z", "level": "INFO", "logger": "pipeline.augmenter", "stage": "augment", "run_id": "run-...", "msg": "Augmentation complete", "n_nodes": 9418}
```

Upside: downstream tooling (dashboard run-history, external log processors) can query without parsing freeform text. Severity and structured fields are first-class.

### Design

`services/pipeline_logger.py`: swap the text formatter for a `JsonFormatter` (either implement inline or use `python-json-logger`).

Fields included:

- `ts` (ISO-8601 with ms, UTC)
- `level` (INFO, WARN, etc.)
- `logger` (python logger name)
- `msg` (the message)
- `stage`, `run_id`, `project_id` when set via logger extra
- Exception info as nested `exc` object when applicable

File rename: `pipeline_<ts>.log` → `pipeline_<ts>.jsonl`. `logs_dir()` returns the same path; file naming convention changes.

### Compat concerns

- `mcp-stdio.log` — keep as freeform text (it is raw stdio from MCP clients, not structured).
- Dashboard — if it reads logs directly (Q8), update reader. If it reads via the pipeline history API, no change.
- External consumers (grep'ing a log file) — this is a breaking change for them. Document it in release notes.

### Open question

Q8 (new): who consumes `pipeline_*.log` files and in what way? See [04_RISKS.md](04_RISKS.md).

### Step placement

- **New Step 4b** — implement the format change at the same time as rotation/retention (one touch of `pipeline_logger.py`).

---

## 8. Checkpoint run-ID timestamp prefix

### What

Today checkpoint dirs look like `run-a4f3f2b595f0`. Listing them gives random ordering. Adding a timestamp prefix makes `ls snapshots/checkpoints/` chronologically sortable, which matters for diagnostics ("what was the last run?") and for the retention sweep.

### Design

New format: `run-<YYYYMMDDTHHMMSSZ>-<short-hash>` — e.g., `run-20260415T143200Z-a4f3f2b5`.

Where minted: wherever run IDs are generated (likely `services/pipeline_checkpoint.py` or the orchestrator). Change the ID format; everything downstream accepts it as an opaque string.

Migration: existing `run-<hex>/` dirs get renamed by the migrator. Timestamp source: the `created_at` of the run (if a metadata file inside says so) or the dir's `stat().st_mtime` as fallback. Hash prefix preserved from the original ID's first 8 chars.

### Open question

Q9 (new): is the run ID referenced anywhere outside the checkpoint dir itself? Pipeline journal, SQLite stores, logs, run-metadata manifest? If yes, the migrator needs an alias table or a cross-reference update. See [04_RISKS.md](04_RISKS.md).

### Step placement

- **Step 0a** — Q9 resolved during discovery.
- **Step 4** — migrator renames existing dirs; new-format IDs start being minted.

---

## 9. Per-artifact mode and sensitivity metadata

### What

Today `hr_roster.json` is 0o600 because the writer happens to call `os.chmod`. There's no declaration anywhere that says "this artifact is sensitive." Adding structured metadata per accessor lets the atomic-write helper enforce modes centrally, lets `codrag doctor` detect drift, and documents the intent.

### Design

Add a metadata registry in `project_paths`:

```python
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ArtifactMeta:
    mode: int = 0o644
    sensitive: bool = False
    description: str = ""


# Keyed by short artifact name; the accessor function's suffix
ARTIFACT_METADATA: dict[str, ArtifactMeta] = {
    "hr_roster": ArtifactMeta(
        mode=0o600,
        sensitive=True,
        description="HR agent roster; contains contact info and tokens.",
    ),
    "daemon_lock": ArtifactMeta(
        mode=0o600,
        sensitive=True,
        description="Per-project advisory lock; holder metadata only.",
    ),
    # everything else defaults — no entry needed
}


def artifact_mode(name: str) -> int:
    return ARTIFACT_METADATA.get(name, ArtifactMeta()).mode


def is_sensitive(name: str) -> bool:
    return ARTIFACT_METADATA.get(name, ArtifactMeta()).sensitive
```

Convention: each accessor function named `X_path` has a metadata key `"X"` (if it deviates from defaults). Default metadata (`0o644`, non-sensitive) is implicit — no registry entry required for 95% of files.

Consumers:

- `atomic_write_text/bytes` take an optional `name` kwarg; when given, look up mode from the registry so callers can't accidentally write a sensitive file with the wrong mode.
- `codrag doctor` reports mode drift by comparing declared vs. actual.
- Migrator preserves mode on every move (for sensitive files, applies the declared mode).

### Step placement

- **Step 0b** — introduce `ArtifactMeta` and `ARTIFACT_METADATA` in `project_paths`.
- **Step 1/2** — when switching writers to `atomic_write`, pass the artifact name so mode is enforced.
- **Step 4** — migrator reads metadata to preserve/apply modes.
- **Step 5a** — `codrag doctor` uses metadata to detect drift.

---

## Cross-cutting: new open questions for Step 0a

The nine items above introduce four additional open questions that Step 0a must answer before the implementation PRs begin. These are reflected in [04_RISKS.md](04_RISKS.md):

- **Q8** — Who consumes `pipeline_*.log` files and in what way? (gates item 7)
- **Q9** — Is the checkpoint run ID referenced outside the checkpoint dir itself? (gates item 8)
- **Q10** — Does anyone expect unlimited retention of `pipeline_*.log`? (gates item 2)
- **Q11** — Is there an existing assumption that two daemons against one index is safe? (gates item 6)
- **Q12** — Which JSONL writers stream vs. rewrite whole? (gates atomic-write exemptions for item 1)

---

## Explicitly out of scope (documented for traceability)

These were considered during the planning pass and deliberately excluded from Phase 113. Each is tracked to its appropriate future home. They do not block Phase 113 acceptance.

| Item | Why out | Home |
|---|---|---|
| SQLite WAL → DELETE auto-detect for USB drives | DB layer, not filesystem layout | Separate issue (memory note exists) |
| Generic migration framework (N-to-N versions) | YAGNI until there are 3+ migrations | Revisit after Phase C |
| Pipeline resume reliability (F-66/67/68/75) | State machine, not plumbing | Phase 107_Pipeline-Stability |
| Manifest JSON schema standardization | Large design effort | Unassigned |
| File-watcher event coalescing | Watcher behavior, orthogonal | Unassigned |
| shanraisshan-style `.claude/` patterns | Different surface (agent harness) | Phase 103_AgentOptimizations |
| Dashboard view of `.prep/` contents | UI feature, not plumbing | Unassigned |
| Splitting embedded vs. standalone layouts | Both share layout by design; splitting them removes a valuable property | Not planned |
| Layout-version compatibility shim (dual-path readers) | Migrator is one-shot; shim adds long-lived complexity | Rejected in [03_STRATEGY.md](03_STRATEGY.md) |
| Cross-filesystem atomic moves | EXDEV fallback via `shutil.move` is sufficient | Already covered in [04_RISKS.md](04_RISKS.md) R3 |

---

## Bundled item → step mapping (summary)

| Item | 0a | 0b | 0c | 0d | 1 | 2 | 2b | 3 | 4 | 4b | 5 | 5a |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. atomic_io | Q12 | | ✓ new | | adopt | adopt | | | | | | |
| 2. log rotation/retention | Q10 | | | | | | | | | ✓ new | | |
| 3. `.prep/README.md` | | ✓ stub | | | | | | | ✓ write | | keep-synced | |
| 4. `version.json` | | ✓ | | | | | | | ✓ write | | | |
| 5. `codrag doctor` | | | | | | | | | | | | ✓ new |
| 6. daemon lockfile | Q11 | accessor | | ✓ new | | | ✓ wire | | body→v2 | | | |
| 7. JSONL logs | Q8 | | | | | | | | | ✓ | | |
| 8. checkpoint timestamp | Q9 | | | | | | | | ✓ rename | | | |
| 9. artifact metadata | | ✓ | | | use | use | | | preserve | | | use |

"✓ new" = new step created to hold this work. "adopt" = existing step gains a task to adopt the helper.
