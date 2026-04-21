# Atomic Build & Recovery Contract

This document defines the atomic build mechanism used by Prep to ensure index integrity during builds.

## Overview

Prep uses an **atomic swap strategy** to ensure that index builds either complete fully or leave the previous index intact. This prevents corrupted or partial indexes from being served.

## Build Artifacts

A complete index consists of these files in the `index_dir`:

| File | Description |
|------|-------------|
| `documents.json` | Chunk metadata (paths, spans, content, roles) |
| `embeddings.npy` | NumPy array of embedding vectors |
| `manifest.json` | Build metadata (model, counts, timestamps, config) |
| `fts.sqlite3` | Full-text search index (optional, graceful degradation) |

## Atomic Build Process

### 1. Temporary Directory Creation

```
{index_dir.parent}/.index_build_{uuid}
```

A unique temporary directory is created adjacent to the target index directory.

### 2. Write Phase

All artifacts are written to the temporary directory:

```python
temp_dir / "documents.json"   # Chunk metadata
temp_dir / "embeddings.npy"   # Embedding vectors
temp_dir / "manifest.json"    # Build manifest
temp_dir / "fts.sqlite3"      # FTS index (optional)
```

### 3. Atomic Swap

```python
def _swap_index_dir(self, new_dir: Path) -> None:
    backup_dir = self.index_dir.parent / f".index_backup_{uuid}"
    
    # Step 1: Backup existing index (if any)
    if self.index_dir.exists():
        self.index_dir.rename(backup_dir)
    
    # Step 2: Move new index into place
    new_dir.rename(self.index_dir)
    
    # Step 3: Delete backup
    if backup_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)
```

### 4. Failure Cleanup

If any step fails, the temporary directory is removed:

```python
except Exception:
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    raise
```

## Directory Naming Convention

| Pattern | Purpose |
|---------|---------|
| `.index_build_{uuid}` | In-progress build (temporary) |
| `.index_backup_{uuid}` | Previous index during swap (transient) |

These directories are hidden (dot-prefixed) and should never persist beyond a few seconds during normal operation.

## Stale Build Cleanup

On `CodeIndex` initialization, stale temporary directories are cleaned up:

```python
def _cleanup_stale_builds(self) -> None:
    for item in self.index_dir.parent.iterdir():
        if item.name.startswith(".index_build_") or \
           item.name.startswith(".index_backup_"):
            # Delete if older than 1 hour
            if age > 3600:
                shutil.rmtree(item, ignore_errors=True)
```

**Threshold:** 1 hour

This handles:
- Crashed builds
- Interrupted processes
- Orphaned backups

## Recovery Scenarios

### Scenario 1: Build Fails Mid-Write

**Symptoms:** `.index_build_*` directory exists with partial files

**Recovery:**
- Original index remains intact
- Temp directory cleaned up on failure
- Stale cleanup removes any orphans on next init

### Scenario 2: Process Crashes During Swap

**Symptoms:** Both `.index_backup_*` and new index exist

**Recovery:**
- Most likely: new index is complete (swap succeeded before crash)
- Stale cleanup removes orphaned backup on next init
- If swap failed mid-rename: original backup can be manually restored

### Scenario 3: Disk Full During Build

**Symptoms:** Partial files in temp directory

**Recovery:**
- Build raises exception
- Temp directory cleaned up
- Original index preserved

## Detecting Partial Builds

A complete index can be validated by checking:

```python
def is_complete(index_dir: Path) -> bool:
    return all([
        (index_dir / "documents.json").exists(),
        (index_dir / "embeddings.npy").exists(),
        (index_dir / "manifest.json").exists(),
    ])
```

**Note:** `fts.sqlite3` is optional; its absence is not a corruption indicator.

## Manifest Validation

The `manifest.json` can be used to validate index consistency:

```python
def validate_index(index_dir: Path) -> bool:
    with open(index_dir / "manifest.json") as f:
        manifest = json.load(f)
    
    with open(index_dir / "documents.json") as f:
        docs = json.load(f)
    
    embeddings = np.load(index_dir / "embeddings.npy")
    
    # Check counts match
    expected_count = manifest.get("count", 0)
    return len(docs) == expected_count == embeddings.shape[0]
```

## Trace Index

The trace index (`TraceIndex`) uses the same atomic pattern:

```python
def _write_atomic(self, nodes, edges) -> None:
    temp_dir = self.index_dir / f".trace_build_{uuid}"
    try:
        # Write nodes.json, edges.json
        # Atomic swap
    except:
        shutil.rmtree(temp_dir)
        raise
```

## Test Coverage

Atomic build behavior is tested in `tests/test_atomic_build.py`:

| Test | Description |
|------|-------------|
| `test_atomic_build_success` | Verifies successful build creates all files |
| `test_atomic_build_failure_cleanup` | Verifies temp cleanup on failure |
| `test_cleanup_stale_builds` | Verifies stale directory cleanup |
| `test_swap_replaces_existing` | Verifies atomic replacement works |

## Limitations

### Non-Atomic Operations

These operations are **not** atomic:
- FTS rebuild (graceful degradation on failure)
- Manifest field updates (rare, low risk)
- Config file writes (outside index dir)

### Filesystem Assumptions

The atomic swap assumes:
- `rename()` is atomic within the same filesystem
- Parent directory is writable
- No other process is actively reading during swap

### No Journaling

Unlike databases, there's no write-ahead log. Recovery relies on:
- Complete temp directory cleanup
- Backup preservation during swap window
- Stale cleanup on init

## Future Improvements

1. **Checksum validation**: Store SHA-256 hashes in manifest
2. **Incremental backup**: Keep N previous indexes
3. **Lock file**: Prevent concurrent builds
4. **Recovery CLI**: `prep index repair` command
