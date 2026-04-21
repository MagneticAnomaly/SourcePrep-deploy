# Prep Manifest Schema

This document defines the schema for manifest files used by Prep indexes.

## Overview

Prep uses JSON manifest files to track metadata about index builds. There are two types:

| File | Purpose |
|------|---------|
| `manifest.json` | Embedding index metadata |
| `trace_manifest.json` | Trace/graph index metadata |

## Index Manifest (`manifest.json`)

**Current Version:** `1.0`

### Schema

```json
{
  "version": "1.0",
  "built_at": "2024-01-15T10:30:00+00:00",
  "model": "nomic-embed-text",
  "embedding_dim": 768,
  "roots": ["src/", "docs/"],
  "count": 1234,
  "build": {
    "mode": "incremental",
    "files_total": 150,
    "files_reused": 120,
    "files_embedded": 30,
    "chunks_total": 1234,
    "chunks_reused": 1000,
    "chunks_embedded": 234
  },
  "config": {
    "include_globs": ["**/*.py", "**/*.md"],
    "exclude_globs": ["**/.git/**", "**/node_modules/**"],
    "max_file_bytes": 400000,
    "role_weights": {
      "code": 1.0,
      "docs": 0.95,
      "tests": 0.98,
      "other": 0.9
    },
    "primer": {
      "enabled": true,
      "filenames": ["AGENTS.md", "PREP_PRIMER.md"],
      "score_boost": 0.25,
      "always_include": false,
      "max_primer_chars": 2000
    }
  }
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Schema version (semver) |
| `built_at` | string | Yes | ISO 8601 timestamp (UTC) |
| `model` | string | Yes | Embedding model name |
| `embedding_dim` | integer | Yes | Vector dimension |
| `roots` | array[string] | Yes | Selected root directories |
| `count` | integer | Yes | Total chunk count |
| `build` | object | Yes | Build statistics |
| `config` | object | Yes | Build configuration snapshot |

### Build Statistics

| Field | Type | Description |
|-------|------|-------------|
| `mode` | string | `"full"` or `"incremental"` |
| `files_total` | integer | Total files processed |
| `files_reused` | integer | Files unchanged from previous build |
| `files_embedded` | integer | Files newly embedded |
| `chunks_total` | integer | Total chunks in index |
| `chunks_reused` | integer | Chunks from previous build |
| `chunks_embedded` | integer | Newly embedded chunks |

### Config Snapshot

The `config` object captures the build parameters for reproducibility:

| Field | Type | Description |
|-------|------|-------------|
| `include_globs` | array[string] | File patterns to include |
| `exclude_globs` | array[string] | File patterns to exclude |
| `max_file_bytes` | integer | Maximum file size |
| `role_weights` | object | Content role scoring weights |
| `primer` | object | Primer file configuration |

## Trace Manifest (`trace_manifest.json`)

**Current Version:** `1.0`

### Schema

```json
{
  "version": "1.0",
  "built_at": "2024-01-15T10:30:00+00:00",
  "counts": {
    "nodes": 500,
    "edges": 1200
  },
  "files_parsed": 150,
  "parse_errors": 2,
  "file_errors": ["src/broken.py"],
  "last_error": null
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Schema version |
| `built_at` | string | Yes | ISO 8601 timestamp (UTC) |
| `counts.nodes` | integer | Yes | Total trace nodes |
| `counts.edges` | integer | Yes | Total trace edges |
| `files_parsed` | integer | Yes | Successfully parsed files |
| `parse_errors` | integer | Yes | Files that failed to parse |
| `file_errors` | array[string] | No | Paths of failed files |
| `last_error` | string | No | Last error message (if any) |

## Versioning Strategy

### Semantic Versioning

Manifest versions follow semver:

- **MAJOR**: Breaking changes (readers must be updated)
- **MINOR**: New fields (backward compatible)
- **PATCH**: Bug fixes (no schema change)

### Version Compatibility

| Reader Version | Can Read |
|----------------|----------|
| 1.x | 1.0, 1.1, 1.2, ... |
| 2.x | 2.0, 2.1, ... (not 1.x) |

### Migration Strategy

When bumping major version:

1. Add migration function in `manifest.py`
2. Reader detects old version and migrates in-memory
3. Next build writes new version

```python
def migrate_manifest(manifest: Dict) -> Dict:
    version = manifest.get("version", "1.0")
    if version.startswith("1."):
        return _migrate_v1_to_v2(manifest)
    return manifest
```

## Validation

### Required Fields Check

```python
REQUIRED_FIELDS = ["version", "built_at", "model", "count"]

def validate_manifest(manifest: Dict) -> bool:
    return all(field in manifest for field in REQUIRED_FIELDS)
```

### Integrity Check

Validate manifest against actual index:

```python
def check_integrity(index_dir: Path) -> bool:
    manifest = read_manifest(index_dir / "manifest.json")
    docs = json.load(open(index_dir / "documents.json"))
    embeddings = np.load(index_dir / "embeddings.npy")
    
    return (
        manifest["count"] == len(docs) == embeddings.shape[0] and
        manifest["embedding_dim"] == embeddings.shape[1]
    )
```

## Usage in Code

### Reading Manifests

```python
from prep.core.manifest import read_manifest

manifest = read_manifest(index_dir / "manifest.json")
model = manifest.get("model", "unknown")
built_at = manifest.get("built_at")
```

### Writing Manifests

```python
from prep.core.manifest import build_manifest, write_manifest, ManifestBuildStats

manifest = build_manifest(
    model="nomic-embed-text",
    embedding_dim=768,
    roots=["src/"],
    count=1234,
    build=ManifestBuildStats(
        mode="full",
        files_total=150,
        files_reused=0,
        files_embedded=150,
        chunks_total=1234,
        chunks_reused=0,
        chunks_embedded=1234,
    ),
    config={"include_globs": ["**/*.py"]},
)
write_manifest(index_dir / "manifest.json", manifest)
```

## Future Considerations

### Per-File Manifests

For very large indexes, consider per-file metadata:

```
index/
├── manifest.json        # Global metadata
├── files/
│   ├── abc123.json     # Per-file chunk metadata
│   └── def456.json
└── embeddings.npy
```

### Streaming Builds

For streaming/incremental updates:

```json
{
  "version": "2.0",
  "stream_mode": true,
  "last_checkpoint": "2024-01-15T10:30:00+00:00",
  "pending_files": ["src/new.py"]
}
```

### Checksum Validation

Add SHA-256 hashes for corruption detection:

```json
{
  "checksums": {
    "documents.json": "abc123...",
    "embeddings.npy": "def456..."
  }
}
```

## Related Documentation

- `docs/ATOMIC_BUILD.md` — Build atomicity and recovery
- `docs/ERROR_CODES.md` — Error handling
- `tests/test_manifest_ids.py` — Manifest ID stability tests
