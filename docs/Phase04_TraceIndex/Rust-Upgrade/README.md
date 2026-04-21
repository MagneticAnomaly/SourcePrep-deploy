# Rust Core Upgrade — Design Document

**Status:** Proposed  
**Created:** 2025-02-07  
**Authors:** Prep Team  
**Related:** `../README.md` (Phase 04 Trace Index), `../DETERMINISTIC_TRACE_BUILD_PLAN.md`

---

## Executive Summary

Prep's indexing engine (trace index + embedding index) is currently implemented in pure Python. This document proposes migrating the performance-critical core — file walking, content hashing, AST parsing, trace graph storage, and vector search — to Rust, exposed to the existing Python daemon via PyO3. The goal is 10–50x speedups on hot paths while keeping the Python API/CLI/dashboard layer intact during migration.

This is not a rewrite-the-world proposal. It is a surgical upgrade of the engine internals, designed for a standalone desktop tool that must run efficiently on regular developer machines.

---

## Table of Contents

1. [Why Now](#1-why-now)
2. [Current Architecture (Python)](#2-current-architecture-python)
3. [What's Actually Slow](#3-whats-actually-slow)
4. [What Rust Buys Us](#4-what-rust-buys-us)
5. [What Rust Does NOT Help With](#5-what-rust-does-not-help-with)
6. [Target Environment: Developer Machines](#6-target-environment-developer-machines)
7. [Architecture: PyO3 Bridge](#7-architecture-pyo3-bridge)
8. [Risk Analysis](#8-risk-analysis)
9. [Alternative Approaches Considered](#9-alternative-approaches-considered)
10. [Phased Implementation Plan](#10-phased-implementation-plan)
11. [Crate Structure](#11-crate-structure)
12. [Testing Strategy](#12-testing-strategy)
13. [Build & Distribution](#13-build--distribution)
14. [Success Metrics](#14-success-metrics)
15. [Open Questions](#15-open-questions)
16. [Decision Log](#16-decision-log)

---

## 1. Why Now

### The Python ceiling is real

The current Python implementation works for small-to-medium repos (< 5k files). But Prep's value proposition — "structural context for AI tools" — demands that it handle **real production codebases** (10k–200k+ files) with:

- **Sub-second rebuild** after a file save (incremental)
- **< 100ms search** across the full trace graph
- **Real-time file watching** with negligible CPU overhead at idle
- **Multi-language symbol extraction** (Python, TypeScript, Go, Rust, Java, C/C++)

Python's GIL, startup overhead, and memory model make these targets unreachable without heroic workarounds (multiprocessing, Cython, etc.) that add complexity without solving the fundamental issue.

### Multi-language parsing is the forcing function

Today, Prep only extracts symbols from Python files (via `ast.parse()`). TypeScript, Go, Rust, Java, and C/C++ files get **file-level nodes only** — no symbols, no import edges, no structural value. This is the single biggest gap in the product.

Tree-sitter is the industry-standard solution for multi-language parsing. It's a C library with **first-class Rust bindings** (`tree-sitter` crate). The Python tree-sitter bindings exist but are:

- Awkward to distribute (C compilation at install time)
- Missing some language grammars
- Slower than the Rust path due to FFI overhead per node visit

Building the parser layer in Rust gives us tree-sitter for free, with the best performance and the cleanest distribution story (single compiled binary, no C toolchain needed on user machines).

### Standalone desktop tool constraint

Prep is a **local-first desktop tool**, not a cloud service. It runs on the developer's machine alongside their IDE, compiler, browser, Docker, etc. Every watt of CPU and megabyte of RAM we use is CPU and RAM the developer can't use for their actual work.

Rust's zero-cost abstractions, lack of GC pauses, and predictable memory usage make it the right choice for a background tool that must be invisible when idle and fast when active.

---

## 2. Current Architecture (Python)

```
src/prep/core/
├── trace.py          # TraceBuilder, TraceIndex, PythonAnalyzer (~833 lines)
├── index.py          # CodeIndex: embedding build, search, context assembly (~1029 lines)
├── chunking.py       # Markdown + code chunking (~200 lines)
├── embedder.py       # Ollama HTTP client (~141 lines)
├── ids.py            # Stable ID generation (~38 lines)
├── manifest.py       # Build manifest schema (~50 lines)
├── watcher.py        # File watcher (watchdog) (~300 lines)
├── repo_policy.py    # Include/exclude/weight config (~130 lines)
├── repo_profile.py   # Repo auto-detection (~180 lines)
├── project_registry.py # Multi-project management (~200 lines)
└── team_config.py    # Team settings (~140 lines)
```

**Key observations:**

| Component | Lines | Perf-critical? | Language-dependent? |
|-----------|-------|----------------|---------------------|
| `trace.py` (TraceBuilder) | ~500 | **Yes** — file walk, AST parse, graph build | **Yes** — only Python today |
| `trace.py` (TraceIndex) | ~180 | **Yes** — in-memory graph queries | No |
| `index.py` (build) | ~250 | **Yes** — file walk, hash, chunk, embed | No (embedding is I/O-bound) |
| `index.py` (search) | ~200 | **Yes** — vector math + scoring | No |
| `chunking.py` | ~200 | Moderate | No |
| `watcher.py` | ~300 | **Yes** — must be low-overhead | No |
| `embedder.py` | ~141 | No (I/O-bound) | No |
| `ids.py` | ~38 | No | No |
| Everything else | ~500 | No | No |

**Conclusion:** ~1,100 lines of Python are performance-critical and would benefit from Rust. The remaining ~1,800 lines (API layer, config, embedder HTTP calls) are fine in Python.

---

## 3. What's Actually Slow

Profiled on a ~15k file TypeScript monorepo (realistic mid-size target):

| Operation | Current (Python) | Target (Rust) | Bottleneck |
|-----------|-----------------|---------------|------------|
| File enumeration (`os.walk` + glob filter) | ~2.5s | < 100ms | Syscall overhead, no parallelism |
| Content hashing (SHA-256, all files) | ~1.8s | < 200ms | Python `hashlib` loop overhead |
| Python AST parse (500 `.py` files) | ~0.8s | < 100ms | `ast.parse()` per file |
| TS/JS symbol extraction | **Not implemented** | < 500ms | N/A — tree-sitter needed |
| Trace graph write (JSONL) | ~0.3s | < 50ms | JSON serialization |
| Vector search (10k chunks, brute force) | ~15ms | < 5ms | NumPy is already fast; marginal |
| Incremental rebuild (1 file changed) | **Full rebuild (~5s)** | < 200ms | No incremental impl |

**Total full build: ~5.5s (Python) → target < 1s (Rust)**  
**Incremental rebuild: ~5.5s (Python) → target < 200ms (Rust)**

---

## 4. What Rust Buys Us

### 4.1 Multi-language AST parsing (tree-sitter)

This is the **primary** motivator. Tree-sitter gives us:

- **Python** — functions, classes, methods, imports, decorators
- **TypeScript/JavaScript** — functions, classes, interfaces, type aliases, imports/exports
- **Go** — functions, methods, structs, interfaces, imports
- **Rust** — functions, structs, enums, traits, impls, use statements
- **Java** — classes, methods, interfaces, imports
- **C/C++** — functions, structs, classes, includes

All from a single, well-maintained parsing framework. The Rust `tree-sitter` crate compiles grammars into the binary — no runtime grammar downloads, no C toolchain on the user's machine.

### 4.2 Parallel file walking and hashing

The `ignore` crate (used by ripgrep) provides:

- Parallel directory traversal
- Built-in `.gitignore` respect
- Symlink handling
- Cross-platform path normalization

Combined with `rayon` for parallel content hashing, we can enumerate and hash a 100k-file repo in < 500ms on a modern SSD.

### 4.3 Incremental rebuild with content-addressed caching

Rust's `HashMap` with content hashes enables:

- Hash every file on walk (cheap with `xxhash` or `blake3`)
- Compare to previous build's hash map
- Only re-parse changed files
- Surgically update the graph (remove old nodes/edges, insert new ones)

### 4.4 Memory-efficient graph storage

The current Python implementation loads the entire trace graph into Python dicts. For a 200k-node graph:

- **Python:** ~800MB (dict overhead, string interning misses, pointer chasing)
- **Rust:** ~40MB (arena-allocated, compact string storage, cache-friendly layout)

This matters because Prep runs alongside the developer's IDE, compiler, and browser.

### 4.5 Predictable latency

No GC pauses. No GIL contention. Search queries return in microseconds, not milliseconds. File watcher callbacks fire immediately, not after the GIL is released.

---

## 5. What Rust Does NOT Help With

| Component | Why Python is fine |
|-----------|-------------------|
| **Embedding generation** | Network I/O to Ollama; language irrelevant |
| **FastAPI server** | HTTP framework overhead is not the bottleneck |
| **Dashboard (Vite/React)** | Separate process entirely |
| **CLI (Typer)** | User-facing commands; startup time irrelevant |
| **Config/policy management** | Read-once JSON files |
| **Team config / project registry** | Low-frequency operations |

**These stay in Python.** The Rust core is a library, not a replacement for the entire application.

---

## 6. Target Environment: Developer Machines

Prep is a standalone desktop tool. It must run well on:

### Minimum viable hardware

| Spec | Minimum | Typical Target |
|------|---------|----------------|
| **CPU** | 4 cores (2018+ laptop) | 8+ cores (2021+ desktop/laptop) |
| **RAM** | 8 GB total system | 16–32 GB |
| **Disk** | SATA SSD | NVMe SSD |
| **OS** | macOS 12+, Ubuntu 22.04+, Windows 10+ | macOS 14+, Ubuntu 24.04 |

### Resource budget

Prep should use **no more than:**

| Resource | Idle (watching) | Active (building) | Searching |
|----------|----------------|-------------------|-----------|
| **CPU** | < 1% | Up to 50% (2-4 cores) | < 5% (burst) |
| **RAM** | < 100 MB resident | < 500 MB peak | < 200 MB |
| **Disk I/O** | Negligible | Burst (write index) | Read-only |

### Design implications

- **No background GC pauses** — Rust's ownership model eliminates this
- **Bounded memory** — Arena allocators with hard caps; drop large structures after build
- **Parallel but polite** — Use `rayon` with a capped thread pool (e.g., `num_cpus / 2`) so we don't starve the developer's IDE
- **Lazy loading** — Don't load the full graph into memory for simple status checks
- **Compile for the user's arch** — Distribute pre-built wheels for `x86_64` and `aarch64` on macOS, Linux, Windows

---

## 7. Architecture: PyO3 Bridge

### Why PyO3, not a separate Rust binary?

| Option | Pros | Cons |
|--------|------|------|
| **PyO3 (Rust → Python extension)** | Single process, shared memory, no IPC overhead, Python tests work, gradual migration | Must match Python version, maturin build step |
| **Separate Rust daemon + HTTP/gRPC** | Language-independent, can replace Python entirely later | IPC overhead, two processes to manage, deployment complexity |
| **Rust CLI binary called via subprocess** | Simplest integration | Startup overhead per call, no shared state, serialization costs |

**Decision: PyO3 via `maturin`.** It lets us replace Python functions one at a time with zero-copy Rust implementations, while keeping the existing FastAPI server, CLI, and test suite working throughout the migration.

### Interface design

```
Python (FastAPI + CLI)
  │
  ├── prep.core.index      (Python — orchestration, embedding calls)
  ├── prep.core.trace      (Python — thin wrapper)
  │     │
  │     └── prep_engine     (Rust via PyO3)
  │           ├── walk()           → List[FileEntry]
  │           ├── hash_files()     → Dict[str, str]
  │           ├── parse_file()     → ParseResult (nodes + edges)
  │           ├── build_trace()    → TraceManifest
  │           ├── load_trace()     → TraceHandle (opaque)
  │           ├── search_trace()   → List[TraceNode]
  │           ├── get_neighbors()  → NeighborResult
  │           ├── chunk_file()     → List[Chunk]
  │           └── vector_search()  → List[SearchResult]
  │
  ├── prep.core.embedder   (Python — HTTP calls to Ollama, unchanged)
  ├── prep.api.*           (Python — FastAPI routes, unchanged)
  └── prep.cli             (Python — Typer CLI, unchanged)
```

### Key principle: opaque handles

The Rust trace graph lives in Rust memory. Python gets an opaque `TraceHandle` that it passes back to Rust for queries. This avoids serializing the entire graph across the FFI boundary.

```python
# Python side
from prep_engine import build_trace, search_trace, get_neighbors

handle = build_trace(repo_root="/path/to/repo", config={...})
results = search_trace(handle, query="build_project", kind="symbol", limit=20)
neighbors = get_neighbors(handle, node_id="sym:build_project@server.py:42", direction="both")
```

### Data flow for incremental rebuild

```
File watcher detects change (Python watchdog or Rust notify)
  │
  └── changed_paths: Set[str]
        │
        └── prep_engine.incremental_rebuild(handle, changed_paths)
              │
              ├── Re-hash changed files (Rust, parallel)
              ├── Re-parse changed files (Rust, tree-sitter)
              ├── Remove stale nodes/edges from graph
              ├── Insert new nodes/edges
              ├── Write updated JSONL + manifest (atomic)
              └── Return updated TraceManifest
```

---

## 8. Risk Analysis

### 8.1 Low risk

| Risk | Mitigation |
|------|------------|
| **Tree-sitter grammar quality varies** | Start with Python + TypeScript (most mature). Add languages incrementally. Fall back to file-only nodes for unsupported languages (same as today). |
| **PyO3 API stability** | PyO3 is mature (v0.20+), widely used (polars, pydantic-core, ruff). API is stable. |
| **Cross-platform compilation** | `maturin` handles this. Pre-built wheels for major platforms. Fallback: `pip install` compiles from source (requires Rust toolchain). |

### 8.2 Medium risk

| Risk | Mitigation |
|------|------------|
| **Increased build complexity** | `maturin` integrates with `pip`. CI builds Rust + Python in one step. Document the dev setup clearly. |
| **Rust learning curve** | Start with file walking + hashing (straightforward Rust). Parser layer is more complex but tree-sitter handles the hard parts. |
| **Python ↔ Rust data conversion overhead** | Use opaque handles for the graph. Only serialize search results (small). Benchmark the FFI boundary early. |
| **Keeping Python fallback working** | Maintain the pure-Python `PythonAnalyzer` as a fallback during migration. Feature flag: `PREP_ENGINE=rust|python`. |

### 8.3 High risk (mitigated)

| Risk | Mitigation |
|------|------------|
| **Scope creep: "rewrite everything in Rust"** | Strict phase boundaries. Only move perf-critical code. FastAPI, CLI, embedder, dashboard stay in Python. The TODO enforces this. |
| **Delayed shipping** | Phase 1 (file walk + hash) is useful standalone and shippable in 1–2 weeks. Each phase delivers independent value. |
| **Binary distribution size** | Tree-sitter grammars compile in. Estimate: 15–25 MB for the Rust wheel with 6 languages. Acceptable for a desktop tool. |

### 8.4 Risk we explicitly accept

| Risk | Why we accept it |
|------|-----------------|
| **Two-language codebase** | The boundary is clean (engine vs. application). Polars, Ruff, and pydantic-core prove this pattern works at scale. |
| **Requires Rust toolchain for contributors** | Only for engine development. Python-only contributors can work on API, CLI, dashboard, tests without touching Rust. |

---

## 9. Alternative Approaches Considered

### 9.1 Stay pure Python, optimize with Cython/C extensions

- **Pros:** No new language, smaller contributor barrier
- **Cons:** Still single-threaded (GIL), no tree-sitter advantage, Cython is painful to maintain, doesn't solve the multi-language parsing problem
- **Verdict:** Rejected. Doesn't solve the core issue.

### 9.2 Use tree-sitter Python bindings only

- **Pros:** No Rust needed
- **Cons:** C compilation at install time, slower than Rust bindings, distribution headaches on Windows, still have GIL for file walking/hashing
- **Verdict:** Rejected. Distribution is the dealbreaker for a desktop tool.

### 9.3 Full Rust rewrite (Axum server, no Python)

- **Pros:** Maximum performance, single binary distribution
- **Cons:** Massive effort, lose FastAPI ecosystem, lose Python test infrastructure, all-or-nothing delivery
- **Verdict:** Rejected for now. Could be a Phase 3+ evolution if the product succeeds, but premature today.

### 9.4 Go instead of Rust

- **Pros:** Easier learning curve, good concurrency, fast compilation
- **Cons:** GC pauses (bad for background daemon), no tree-sitter Rust-quality bindings, worse memory efficiency, Python interop is painful (cgo + ctypes)
- **Verdict:** Rejected. Rust's memory model is the right fit for a background desktop tool.

### 9.5 Node.js/Bun with tree-sitter WASM

- **Pros:** Same language as dashboard
- **Cons:** WASM tree-sitter is slower, V8 memory overhead, no advantage for file I/O, adds another runtime dependency
- **Verdict:** Rejected.

---

## 10. Phased Implementation Plan

Each phase is independently shippable and testable. The Python fallback remains available throughout.

### Phase 0: Scaffolding (1 week)

**Goal:** Rust crate structure, PyO3 skeleton, maturin build, CI integration.

- Create `engine/` directory at repo root with Cargo workspace
- `prep-engine` crate with PyO3 module skeleton
- `maturin` config for building Python wheels
- CI: build + test Rust crate, build wheel, run Python tests with Rust engine
- Feature flag: `PREP_ENGINE=rust|python` (default: `python` during migration)
- Smoke test: `from prep_engine import hello; assert hello() == "prep-engine 0.1.0"`

**Deliverable:** `pip install -e .` builds and imports the Rust extension.

### Phase 1: File Walking + Content Hashing (1–2 weeks)

**Goal:** Replace `os.walk` + `hashlib` with Rust `ignore` + `blake3`.

Rust functions exposed:
- `walk_repo(root, include_globs, exclude_globs, max_file_bytes) → List[FileEntry]`
- `hash_files(paths) → Dict[str, str]`

Where `FileEntry = { path: str, size: int, modified: float }`.

**Benchmark target:** 10x faster than Python on a 50k-file repo.

**Integration:** `TraceBuilder._enumerate_files()` and `CodeIndex.build()` call Rust when available, fall back to Python otherwise.

### Phase 2: Tree-sitter Multi-Language Parsing (2–3 weeks)

**Goal:** Replace `PythonAnalyzer` (ast.parse) with tree-sitter, add TypeScript + Go + Rust + Java.

Rust functions exposed:
- `parse_file(path, content, language) → ParseResult`

Where `ParseResult = { nodes: List[TraceNode], edges: List[TraceEdge], errors: List[ParseError] }`.

Language support (priority order):
1. **Python** — parity with current `PythonAnalyzer`, then exceed it (nested functions, comprehension scopes, type annotations)
2. **TypeScript/JavaScript** — functions, classes, interfaces, imports/exports, type aliases
3. **Go** — functions, methods, structs, interfaces, imports
4. **Rust** — functions, structs, enums, traits, impls, use statements
5. **Java** — classes, interfaces, methods, imports
6. **C/C++** — functions, structs, classes, includes (best-effort)

Each language gets its own analyzer module in Rust with shared node/edge output types.

**Benchmark target:** Parse 5,000 mixed-language files in < 2s total.

### Phase 3: In-Memory Trace Graph (2 weeks)

**Goal:** Replace Python dict-based `TraceIndex` with a Rust in-memory graph. Expose via opaque handle.

Rust functions exposed:
- `build_trace(root, config) → TraceHandle`
- `load_trace(index_dir) → TraceHandle`
- `search_trace(handle, query, kind, limit) → List[TraceNode]`
- `get_neighbors(handle, node_id, direction, edge_kinds, max_nodes) → NeighborResult`
- `trace_status(handle) → TraceStatus`

Graph implementation:
- `petgraph` or custom adjacency list with arena-allocated strings
- Serialization: read/write JSONL (same format, backward compatible)
- Memory: < 50 MB for 200k-node graph

**Benchmark target:** `search_trace` < 1ms for 200k nodes. `get_neighbors` < 100μs.

### Phase 4: Incremental Rebuild (1–2 weeks)

**Goal:** When files change, update the trace graph without full rebuild.

Rust functions exposed:
- `incremental_rebuild(handle, changed_paths) → RebuildResult`

Implementation:
- Compare content hashes of changed files against stored hashes
- Remove nodes/edges belonging to changed files
- Re-parse changed files
- Insert new nodes/edges
- Update manifest
- Atomic write of updated JSONL

**Benchmark target:** Single-file change rebuild < 200ms on a 50k-file repo.

### Phase 5: Rust File Watcher (optional, 1 week)

**Goal:** Replace Python `watchdog` with Rust `notify` crate for lower overhead.

This is optional because `watchdog` works fine. But if we're already in Rust, `notify` is:
- Lower CPU at idle (kernel-level events, no polling)
- Cross-platform (inotify, FSEvents, ReadDirectoryChanges)
- Directly wired to the incremental rebuild in Rust (no Python GIL roundtrip)

### Phase 6: Vector Search Acceleration (optional, 1 week)

**Goal:** Replace NumPy brute-force with HNSW for repos with > 50k chunks.

Options:
- `usearch` (Rust bindings, HNSW)
- `hnsw` crate
- Keep NumPy for small indexes, Rust HNSW for large ones

This is a nice-to-have. NumPy brute-force is already fast for < 50k chunks.

---

## 11. Crate Structure

```
engine/
├── Cargo.toml                 # Workspace root
├── crates/
│   ├── prep-walker/         # File walking + hashing
│   │   ├── src/lib.rs
│   │   └── Cargo.toml         # deps: ignore, blake3, rayon
│   │
│   ├── prep-parser/         # Tree-sitter multi-language parsing
│   │   ├── src/
│   │   │   ├── lib.rs
│   │   │   ├── python.rs
│   │   │   ├── typescript.rs
│   │   │   ├── go.rs
│   │   │   ├── rust_lang.rs
│   │   │   ├── java.rs
│   │   │   └── cpp.rs
│   │   └── Cargo.toml         # deps: tree-sitter, tree-sitter-{lang}
│   │
│   ├── prep-graph/          # In-memory trace graph + queries
│   │   ├── src/lib.rs
│   │   └── Cargo.toml         # deps: petgraph or custom, serde
│   │
│   ├── prep-index/          # Chunking, vector search
│   │   ├── src/lib.rs
│   │   └── Cargo.toml         # deps: serde, optional: usearch
│   │
│   └── prep-engine/         # PyO3 wrapper (the Python extension module)
│       ├── src/lib.rs         # #[pymodule] exposing all public APIs
│       └── Cargo.toml         # deps: pyo3, all prep-* crates
│
├── tests/                     # Rust integration tests
│   ├── fixtures/              # Shared test repos
│   └── test_*.rs
│
└── benches/                   # Criterion benchmarks
    ├── bench_walker.rs
    ├── bench_parser.rs
    └── bench_graph.rs
```

### Key Rust dependencies

| Crate | Purpose | Maturity |
|-------|---------|----------|
| `pyo3` | Python ↔ Rust FFI | Stable (v0.20+) |
| `maturin` | Build Python wheels from Rust | Stable |
| `ignore` | Fast parallel file walking (from ripgrep) | Stable |
| `blake3` | Fast content hashing | Stable |
| `rayon` | Parallel iterators | Stable |
| `tree-sitter` | Multi-language AST parsing | Stable |
| `tree-sitter-python` | Python grammar | Stable |
| `tree-sitter-typescript` | TS/JS grammar | Stable |
| `tree-sitter-go` | Go grammar | Stable |
| `tree-sitter-rust` | Rust grammar | Stable |
| `tree-sitter-java` | Java grammar | Stable |
| `tree-sitter-cpp` | C/C++ grammar | Stable |
| `serde` + `serde_json` | Serialization | Stable |
| `petgraph` | Graph data structure | Stable |

---

## 12. Testing Strategy

### Rust-side tests

- **Unit tests** per crate (standard `#[cfg(test)]` modules)
- **Integration tests** in `engine/tests/` using fixture repos
- **Benchmarks** in `engine/benches/` using Criterion
- **Golden file tests**: parse fixture files, compare output to expected JSON

### Python-side tests (unchanged, extended)

- Existing tests in `tests/` continue to work against the Python fallback
- Add parametrized tests that run against both `python` and `rust` engines:

```python
@pytest.mark.parametrize("engine", ["python", "rust"])
def test_trace_build(engine, tmp_path, mini_repo):
    ...
```

- **Parity tests**: Build trace with both engines, assert identical output (same nodes, edges, manifest — ignoring `built_at`)

### CI matrix

| Platform | Python | Rust | Test |
|----------|--------|------|------|
| macOS (arm64) | 3.11, 3.12 | stable | unit + integration |
| macOS (x86_64) | 3.11, 3.12 | stable | unit + integration |
| Ubuntu (x86_64) | 3.11, 3.12 | stable | unit + integration |
| Windows (x86_64) | 3.11, 3.12 | stable | unit + integration |

---

## 13. Build & Distribution

### Development

```bash
# Install Rust (if not already)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Build the Rust extension in development mode
cd engine
maturin develop --release

# Now Python can import it
python -c "from prep_engine import hello; print(hello())"
```

### Release

```bash
# Build wheels for current platform
maturin build --release

# Build wheels for all platforms (CI)
maturin build --release --target x86_64-apple-darwin
maturin build --release --target aarch64-apple-darwin
maturin build --release --target x86_64-unknown-linux-gnu
maturin build --release --target x86_64-pc-windows-msvc
```

### Fallback for users without Rust

If the Rust extension is not available (e.g., unsupported platform, build failure), Prep falls back to the pure-Python implementation with a warning:

```
⚠ prep-engine not available; using Python fallback (slower for large repos)
```

This is controlled by `PREP_ENGINE=python` or automatic detection:

```python
try:
    import prep_engine
    ENGINE = "rust"
except ImportError:
    ENGINE = "python"
```

---

## 14. Success Metrics

### Performance (measured on a 20k-file TypeScript monorepo)

| Metric | Current (Python) | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|-----------------|---------|---------|---------|---------|
| Full build (trace only) | ~5s | ~2s | ~1.5s | ~1s | ~1s |
| Incremental rebuild (1 file) | ~5s | ~5s | ~5s | ~5s | < 200ms |
| Symbol search (200k nodes) | ~50ms | ~50ms | ~50ms | < 1ms | < 1ms |
| Languages with symbol extraction | 1 (Python) | 1 | 6 | 6 | 6 |
| Idle memory (loaded graph) | ~200 MB | ~200 MB | ~200 MB | < 50 MB | < 50 MB |
| Idle CPU | < 1% | < 1% | < 1% | < 1% | < 0.5% |

### Quality

- Zero regressions in existing Python test suite
- Parity tests pass: Rust engine produces identical trace output to Python engine (for Python files)
- Tree-sitter parser handles malformed files gracefully (no panics, no crashes)

### Distribution

- Pre-built wheels available for macOS (arm64 + x86_64), Linux (x86_64), Windows (x86_64)
- `pip install prep` "just works" on supported platforms
- Pure-Python fallback works on all platforms

---

## 15. Open Questions

| ID | Question | Status |
|----|----------|--------|
| RU-Q1 | Should the Rust engine also handle chunking, or keep that in Python? | **Leaning Rust** — chunking is simple but runs on every file; moving it to Rust avoids a Python roundtrip per file during build. |
| RU-Q2 | Should we use `notify` (Rust) or keep `watchdog` (Python) for file watching? | **Defer to Phase 5.** Watchdog works. Evaluate after Phase 4. |
| RU-Q3 | Should the JSONL trace format change, or must it be identical to current output? | **Identical for now.** Same format = backward compatible. We can add acceleration files (e.g., binary graph cache) alongside JSONL later. |
| RU-Q4 | Where does the `engine/` directory live relative to the Python package? | **Repo root.** `engine/` is a Cargo workspace. `maturin` builds a wheel that installs as `prep_engine` Python package. |
| RU-Q5 | How do we handle tree-sitter grammars that need updates (e.g., new TS syntax)? | Grammars are pinned versions in `Cargo.toml`. Update = bump version + rebuild. No runtime grammar fetching. |
| RU-Q6 | Should the Rust engine expose a C API too (for future Tauri integration)? | **Yes, plan for it.** The `prep-graph` and `prep-parser` crates should be usable from both PyO3 and a future C/FFI layer. Keep PyO3-specific code in `prep-engine` only. |
| RU-Q7 | Thread pool size for parallel operations? | **Default: `num_cpus / 2`, min 2, max 8.** Configurable. Polite to other processes. |

---

## 16. Decision Log

| ID | Decision | Rationale | Date |
|----|----------|-----------|------|
| RU-D1 | Use PyO3 + maturin, not a separate Rust daemon | Single process, shared memory, gradual migration, proven pattern (polars, ruff, pydantic-core) | 2025-02-07 |
| RU-D2 | Tree-sitter for multi-language parsing | Industry standard, compiled grammars, no runtime deps, Rust-native bindings | 2025-02-07 |
| RU-D3 | Phase the migration (walk → parse → graph → incremental) | Each phase delivers value independently; de-risks the project | 2025-02-07 |
| RU-D4 | Maintain Python fallback throughout | Users on unsupported platforms still work; safety net during migration | 2025-02-07 |
| RU-D5 | Target developer machines, not cloud | Resource budgets, polite CPU/RAM usage, no background GC | 2025-02-07 |
| RU-D6 | Keep JSONL trace format unchanged | Backward compatibility, diffable, transparent | 2025-02-07 |
| RU-D7 | Separate Cargo workspace crates (walker, parser, graph, engine) | Clean boundaries, independent testing, reusable from Tauri later | 2025-02-07 |
