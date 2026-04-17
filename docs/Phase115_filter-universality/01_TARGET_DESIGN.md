# 01 — Target Design

**Phase:** 115
**Drafted:** 2026-04-17

## Design principles

1. **Single source of truth.** Every walker (Python trace builder, Rust walker, file watcher, self-heal, enrichment re-read) draws the same filter from one canonical place. No callsite may carry its own hardcoded list.
2. **Universality.** Defaults are identical for every project. Per-project `repo_policy.json` can narrow or extend, but the defaults are a floor.
3. **User extension, not replacement.** User-authored exclusions (Knowledge Scope / FolderTree, `trace.ignore_patterns`) **add to** the defaults; they never replace them.
4. **No self-ingestion.** CoDRAG never indexes files CoDRAG wrote. The guarantee is a test-enforced invariant, not a style guideline.
5. **Back-fill on load.** Adding a new default exclude in source must propagate to existing indexes without forcing users to re-profile. Auto-migration already exists for dir globs — extend it to cover file globs too.

## The three filter layers

Already present; this phase reinforces the contract, it doesn't introduce a new layer.

| Layer | Source | Audience |
|-------|--------|----------|
| **L1 — Code defaults** | `DEFAULT_EXCLUDE_DIR_NAMES`, `DEFAULT_EXCLUDE_FILE_GLOBS`, `DEFAULT_EXCLUDE_FILE_NAMES` in `repo_profile.py` | All projects, baked by the CoDRAG build |
| **L2 — Per-project policy** | `repo_policy.json.exclude_globs` | One project, persisted on disk |
| **L3 — User runtime exclusions** | `project.config.trace.ignore_patterns` (via FolderTree UI) | One project, user-editable at runtime |

**Enforcement rule:** every entrypoint that walks files must union all three and must also honor the include list from L1/L2.

Union order (for readability only; set semantics make order irrelevant):

```
effective_exclude = L1.dir_globs
                  | L1.file_globs
                  | L2.exclude_globs
                  | L3.ignore_patterns
```

## The `CODRAG_OUTPUT_*` registry

New concept. Lives in `repo_profile.py` adjacent to the existing default sets.

```python
# Paths that CoDRAG writes. Indexing any of these creates a feedback loop
# in which the LLM reasons about CoDRAG's own state. Every new writer must
# add its path here; the default exclude sets below derive from this.
CODRAG_OUTPUT_DIRS: Set[str] = {
    ".codrag",          # per-project index (embedded mode)
    "codrag_data",      # daemon-wide store (SQLite + telemetry + ui_config)
}

CODRAG_OUTPUT_FILE_GLOBS: Sequence[str] = (
    # AGENTS.md spliced by rules_generator._write_agents_md
    "**/AGENTS.md",
    # CoDRAG-managed CLAUDE.md block; file may also contain user content,
    # but AI agents already have direct access
    "**/CLAUDE.md",
    "**/GEMINI.md",
    # Per-IDE rule writers (rules_generator.py)
    "**/.cursor/rules/*.mdc",
    "**/.cursorrules",
    "**/.cursorignore",
    "**/.windsurfrules",
    "**/.windsurf/rules/*.md",
    "**/.github/copilot-instructions.md",
    "**/.clinerules",
    "**/.clineignore",
    "**/.roorules",
    "**/.qwencoderules",
)
```

### How the existing sets derive from it

```python
DEFAULT_EXCLUDE_DIR_NAMES: Set[str] = (
    CODRAG_OUTPUT_DIRS
    | {
        # VCS
        ".git",
        # Language dep/build dirs
        "node_modules", "__pycache__", ".venv", "venv", "fresh_venv",
        "env", ".env", ".tox", ".pytest_cache", ".mypy_cache",
        ".ruff_cache", "htmlcov", ".coverage",
        "dist", "build", "target",
        # Frontend build/meta dirs (new in Phase 115)
        "storybook-static", "coverage", "out",
        ".next", ".turbo", ".vercel", ".parcel-cache",
        ".svelte-kit", ".astro", ".nuxt",
        ".cache",
        # iOS / mobile
        "Pods", "Carthage", ".gradle", "DerivedData",
        # Cross-ecosystem vendor
        "vendor", "bundle", ".bundle", "bower_components",
        # AI tool dirs (already present)
        ".claude", ".cursor", ".windsurf",
        ".continue", ".cody", ".aider",
    }
)

DEFAULT_EXCLUDE_FILE_GLOBS: Sequence[str] = (
    *CODRAG_OUTPUT_FILE_GLOBS,
    # Build artifacts that look like source (new in Phase 115)
    "**/*.d.ts",        # TypeScript declaration files — generated
    "**/*.min.js",
    "**/*.min.css",
    "**/*.map",         # source maps
)
```

The two registries (`CODRAG_OUTPUT_DIRS`, `CODRAG_OUTPUT_FILE_GLOBS`) are **subsets** of the full default exclude lists. Other defaults (`node_modules`, `.git`, etc.) are not CoDRAG outputs — they're ecosystem standards — and stay in the main set.

## Contract for every walker / reader

Any function that visits files on disk or iterates trace nodes **must** resolve its effective filter through a single helper:

```python
# Proposed: core/repo_policy.py
def effective_excludes(
    *,
    index_dir: Path,
    repo_root: Path,
    trace_ignore_patterns: Optional[List[str]] = None,
) -> Set[str]:
    """Union L1 (code defaults), L2 (repo_policy.json), L3 (trace.ignore_patterns)."""
    policy = ensure_repo_policy(index_dir, repo_root)
    out: Set[str] = set()
    out.update(policy.get("exclude_globs") or [])
    out.update(f"**/{d}/**" for d in DEFAULT_EXCLUDE_DIR_NAMES)
    out.update(DEFAULT_EXCLUDE_FILE_GLOBS)
    if trace_ignore_patterns:
        out.update(trace_ignore_patterns)
    return out
```

Callsites to migrate to this helper:

- `core/trace/builder.py::TraceBuilder.__init__` (replace hardcoded lists)
- `core/epistemic_enrichment.py::load_trace_nodes` (add filter pass)
- `api/routers/trace_routes/query.py` (already merges; keep as reference for the pattern)
- `services/watcher.py` (verify; fix if L3 missing)

Rust side gets its equivalent on the Rust half of the seam (see below).

## Python↔Rust parity

The Rust walker needs the same filter. Options:

- **(a) Generate `WalkConfig::default()` from Python at build time.** One canonical JSON file, emitted by a helper, read by both sides.
- **(b) Pass the resolved filter set from Python every call.** Rust walker's default becomes minimal (or empty); the caller (Python) supplies a fully-resolved list.

Option (b) is smaller-blast-radius — Rust defaults can stay as a safety net, but the trusted filter comes from the Python caller. Selfheal (which runs as its own Rust binary without a Python driver) is the exception and must build the filter itself from `repo_policy.json` + `project.config.trace.ignore_patterns`.

**Decision:** (b) for the Python-driven path (walker called from the daemon); Rust selfheal also reads `repo_policy.json` + project config on its own. Two implementations, one test (parity assertion in Step 9).

## Cache-busting behaviour for the policy back-fill

When `ensure_repo_policy()` adds a new default glob, two things happen now that don't happen today:

1. The `repo_policy.json` on disk is rewritten with the merged set (already happens for dir globs; extend to file globs).
2. Nothing else is invalidated. `trace_nodes.jsonl` and downstream manifests may still contain paths that are now excluded.

**Design decision:** back-fill does not auto-invalidate. Any file that entered the graph before the filter fix remains until the next trace rebuild. Operator workflow:

- On daemon start: auto-migration writes the expanded `exclude_globs` to disk (operator sees new entries).
- On next rebuild (manual or auto): new walk excludes the new paths; trace nodes/edges get regenerated cleanly.

Invalidation-on-migration is out of scope. Rationale: filter changes are additive and the next rebuild is cheap (Fast Sync path).

## The self-ingestion regression test

A project-level integration test that runs after rebuild:

```python
# tests/test_no_self_ingestion.py
def test_no_codrag_outputs_in_trace_nodes(dogfood_index):
    nodes = read_jsonl(dogfood_index / "trace_nodes.jsonl")
    offenders = [
        n["path"] for n in nodes
        if any(n["path"].startswith(d + "/") or f"/{d}/" in n["path"]
               for d in CODRAG_OUTPUT_DIRS)
    ]
    assert offenders == [], (
        f"CoDRAG output paths leaked into trace graph: {offenders}"
    )
```

This is the load-bearing test for Principle 4. If a future writer adds a new output directory and forgets to register it, this test fails.

## What Phase 115 does **not** change

- No new filter layer. L1/L2/L3 stays.
- No change to per-language presets in `STACK_PRESETS`.
- No change to the Knowledge Scope UI or `/trace/ignore` endpoint contract.
- No reorganization of on-disk layout (that is Phase 113).
- No migration of `codrag_data/` to `~/.local/share/codrag/` (tracked separately).

## Interaction with Phase 113

Phase 113 will rename many paths inside `.codrag/` (`trace/nodes.jsonl` instead of `trace_nodes.jsonl`, etc.). That changes the *shape* of `CODRAG_OUTPUT_DIRS` for `.codrag/` internals but not the set membership — `.codrag/` stays in the registry regardless. Phase 113 migration should:

- Keep `.codrag` in `CODRAG_OUTPUT_DIRS` as-is (it's a dir, not a path into it).
- Not introduce new top-level paths outside `.codrag/`.

No merge conflict expected. Phase 115 lands first.
