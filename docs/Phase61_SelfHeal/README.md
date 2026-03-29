# Phase 61 — Self-Heal: Uncategorized File Checker

## Rationale
CoDRAG processes files through an 11-stage deep enrichment pipeline. As the codebase evolves, files are added, moved, and modified. While features like Continuous Deepening and the AutoRebuildWatcher handle most incremental processing and self-healing, there is a need for a fast, read-only diagnostic tool to verify the integrity of the pipeline data against the current filesystem state.

The existing Python-based `coverage.py` script is slow on large repositories and only checks the initial structural trace (Stage 1). The goal of Phase 61 is to build a high-performance Rust CLI tool that cross-references the filesystem with all major pipeline checkpoints.

## Architecture: `codrag-selfheal`

`codrag-selfheal` is a standalone Rust binary integrated into the `codrag-engine` workspace. It leverages the lightning-fast `codrag-walker` crate to scan the filesystem and compares the discovered files against the pipeline's JSONL data files.

### Checkpoints Monitored

1. **Traced (`trace_nodes.jsonl`)**: Structural Graph (Stage 1)
2. **Augmented (`trace_augmented.jsonl`)**: Fast Catalogue (Stage 3)
3. **Enriched (`trace_epistemic.jsonl`)**: Deep Enrichment (Stages 6 & 10)
4. **Clustered (`trace_modules.jsonl`)**: Module Synthesis (Stage 8)

### Execution Flow

1. **Policy Loading**: Reads `.codrag/repo_policy.json` to respect the project's custom include/exclude globs.
2. **Filesystem Walk**: Uses `codrag-walker` to find all eligible code files on disk (typically takes <100ms).
3. **Pipeline Data Loading**: Parses the `file_path` fields from the respective JSONL files in the `.codrag` index directory.
4. **Diff Analysis**: Computes the set subtraction (`filesystem_files - pipeline_files`) for each checkpoint.
5. **Reporting**: Outputs a JSON diagnostic report detailing coverage percentages and exactly which files are missing at each stage.

## Usage

```bash
# General usage
cargo run -p codrag-selfheal -- /path/to/repo /path/to/repo/.codrag

# Example output
{
  "repo_root": "/path/to/repo",
  "index_dir": "/path/to/repo/.codrag",
  "scanned_at": "2026-03-29T10:00:00Z",
  "disk_files": 1143,
  "checkpoints": {
    "traced": {
      "covered": 1143,
      "missing": []
    },
    "augmented": {
      "covered": 1140,
      "missing": ["src/new_feature.ts"]
    }
  },
  "summary": {
    "fully_healed": false,
    "worst_gap": "augmented",
    "worst_gap_pct": 99.7,
    "rogue_files": 3
  }
}
```

This read-only tool is safe to run at any time and provides the necessary telemetry to ensure the AI pipeline maintains complete visibility over the codebase.
