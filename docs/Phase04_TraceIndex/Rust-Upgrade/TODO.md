# Rust Core Upgrade — TODO

## Links
- Design doc: `./README.md`
- Parent phase: `../README.md` (Phase 04 Trace Index)
- Master orchestrator: `../../MASTER_TODO.md`

---

## Phase 0: Scaffolding (Sprint R0, ~1 week)

- [ ] R0-01 Create `engine/` Cargo workspace at repo root
- [ ] R0-02 Create `prep-engine` crate with PyO3 `#[pymodule]` skeleton
- [ ] R0-03 Add `maturin` config (`pyproject.toml` or `Cargo.toml` metadata)
- [ ] R0-04 Smoke test: `from prep_engine import version; assert version()`
- [ ] R0-05 Add `PREP_ENGINE=rust|python` feature flag to `src/prep/core/__init__.py`
- [ ] R0-06 CI: GitHub Actions job that builds Rust wheel + runs Python test suite
- [ ] R0-07 Document dev setup in `engine/README.md` (install Rust, maturin develop, etc.)
- [ ] R0-08 Add `engine/` to root `.gitignore` for build artifacts (`target/`)

## Phase 1: File Walking + Content Hashing (Sprint R1, ~1–2 weeks)

- [ ] R1-01 Create `prep-walker` crate
- [ ] R1-02 Implement `walk_repo(root, include_globs, exclude_globs, max_file_bytes) → Vec<FileEntry>`
  - Use `ignore` crate for parallel traversal + `.gitignore` respect
  - FileEntry: `{ path: String, size: u64, modified_secs: f64 }`
- [ ] R1-03 Implement `hash_files(paths) → HashMap<String, String>`
  - Use `blake3` for content hashing
  - Use `rayon` for parallelism (thread pool capped at `num_cpus / 2`)
- [ ] R1-04 Expose `walk_repo` and `hash_files` via PyO3 in `prep-engine`
- [ ] R1-05 Write Rust unit tests for walker (fixture repo with edge cases: symlinks, binary files, deep nesting)
- [ ] R1-06 Write Rust benchmarks (`criterion`) for walk + hash on synthetic repos (1k, 10k, 50k files)
- [ ] R1-07 Wire `TraceBuilder._enumerate_files()` to call Rust when `PREP_ENGINE=rust`
- [ ] R1-08 Wire `CodeIndex.build()` file enumeration to call Rust when available
- [ ] R1-09 Python parity test: assert Rust walker returns same file set as Python walker
- [ ] R1-10 Benchmark comparison: Python vs Rust walker on the Prep repo itself

## Phase 2: Tree-sitter Multi-Language Parsing (Sprint R2, ~2–3 weeks)

### Core parser infrastructure
- [ ] R2-01 Create `prep-parser` crate
- [ ] R2-02 Define shared output types: `ParseResult { nodes: Vec<TraceNode>, edges: Vec<TraceEdge>, errors: Vec<ParseError> }`
- [ ] R2-03 Implement tree-sitter initialization + grammar loading (compiled into binary)
- [ ] R2-04 Implement `parse_file(path, content, language) → ParseResult` dispatcher

### Language analyzers (priority order)
- [ ] R2-05 Python analyzer: functions, classes, methods, imports (parity with current `PythonAnalyzer`)
  - Parity test: same nodes/edges as Python `ast.parse` analyzer on test fixtures
- [ ] R2-06 Python analyzer: exceed current — nested functions, type annotations, `__all__` exports
- [ ] R2-07 TypeScript analyzer: functions, classes, interfaces, type aliases, imports/exports
- [ ] R2-08 JavaScript analyzer: share TS analyzer with JSX/JS grammar variants
- [ ] R2-09 Go analyzer: functions, methods, structs, interfaces, imports
- [ ] R2-10 Rust analyzer: functions, structs, enums, traits, impls, use statements
- [ ] R2-11 Java analyzer: classes, interfaces, methods, imports
- [ ] R2-12 C/C++ analyzer: functions, structs, classes, includes (best-effort)

### Integration
- [ ] R2-13 Expose `parse_file` via PyO3
- [ ] R2-14 Wire `TraceBuilder.build()` to use Rust parser when `PREP_ENGINE=rust`
- [ ] R2-15 Golden file tests: parse fixture files, compare to expected JSON output
- [ ] R2-16 Benchmark: parse 5,000 mixed-language files, compare to Python baseline

## Phase 3: In-Memory Trace Graph (Sprint R3, ~2 weeks)

- [ ] R3-01 Create `prep-graph` crate
- [ ] R3-02 Implement in-memory graph (arena-allocated nodes/edges, adjacency lists)
- [ ] R3-03 Implement JSONL reader/writer (same format as current Python output)
- [ ] R3-04 Implement `build_trace(root, config) → TraceHandle` (walk + parse + graph build, all in Rust)
- [ ] R3-05 Implement `load_trace(index_dir) → TraceHandle` (load from JSONL)
- [ ] R3-06 Implement `search_trace(handle, query, kind, limit) → Vec<TraceNode>`
  - Ranking: exact > prefix > substring (same as current Python)
- [ ] R3-07 Implement `get_neighbors(handle, node_id, direction, edge_kinds, max_nodes) → NeighborResult`
- [ ] R3-08 Implement `trace_status(handle) → TraceStatus`
- [ ] R3-09 Expose all via PyO3 with opaque `TraceHandle`
- [ ] R3-10 Wire `TraceIndex` Python class to delegate to Rust handle when available
- [ ] R3-11 Memory benchmark: load 200k-node graph, measure RSS (target < 50 MB)
- [ ] R3-12 Latency benchmark: search + neighbors on 200k-node graph (target < 1ms)
- [ ] R3-13 Parity test: full trace build with both engines, assert identical JSONL output

## Phase 4: Incremental Rebuild (Sprint R4, ~1–2 weeks)

- [ ] R4-01 Add per-file content hash storage to trace manifest
- [ ] R4-02 Implement `incremental_rebuild(handle, changed_paths) → RebuildResult`
  - Re-hash changed files
  - Remove stale nodes/edges for changed files
  - Re-parse changed files
  - Insert new nodes/edges
  - Atomic JSONL write
- [ ] R4-03 Expose via PyO3
- [ ] R4-04 Wire into `TraceBuilder.build(changed_paths=...)` 
- [ ] R4-05 Wire into watcher callback (file change → incremental rebuild)
- [ ] R4-06 Test: modify 1 file in 50k-file repo, assert only that file's nodes/edges change
- [ ] R4-07 Benchmark: incremental rebuild (1 file changed) < 200ms on 50k-file repo

## Phase 5: Rust File Watcher (Sprint R5, optional, ~1 week)

- [ ] R5-01 Evaluate `notify` crate vs keeping Python `watchdog`
- [ ] R5-02 If proceeding: implement Rust watcher with debounce + batching
- [ ] R5-03 Expose watcher start/stop/status via PyO3
- [ ] R5-04 Wire into existing watcher API endpoints
- [ ] R5-05 Benchmark: idle CPU usage comparison (Rust `notify` vs Python `watchdog`)

## Phase 6: Vector Search Acceleration (Sprint R6, optional, ~1 week)

- [ ] R6-01 Evaluate `usearch` vs `hnswlib` Rust bindings
- [ ] R6-02 If proceeding: implement HNSW index build + search
- [ ] R6-03 Expose via PyO3
- [ ] R6-04 Wire into `CodeIndex.search()` for indexes > 50k chunks
- [ ] R6-05 Benchmark: search latency + recall comparison vs NumPy brute-force

---

## Cross-cutting concerns

- [ ] RC-01 Pre-built wheel CI for: macOS arm64, macOS x86_64, Linux x86_64, Windows x86_64
- [ ] RC-02 Pure-Python fallback with warning when Rust extension unavailable
- [ ] RC-03 Thread pool configuration: default `num_cpus / 2`, min 2, max 8, configurable via env var
- [ ] RC-04 Memory budget enforcement: hard cap on graph size, drop large intermediates after build
- [ ] RC-05 Error handling: Rust panics must not crash the Python process (catch_unwind at FFI boundary)
- [ ] RC-06 Logging: Rust `tracing` crate bridged to Python `logging` via PyO3

---

## Milestone summary

| Milestone | Sprint | Core deliverable | Languages |
|-----------|--------|-----------------|-----------|
| M0 | R0 | Build infrastructure | — |
| M1 | R0+R1 | 10x faster file walking | — |
| M2 | R0–R2 | Multi-language symbol extraction | Python, TS, Go, Rust, Java, C/C++ |
| M3 | R0–R3 | Full Rust trace engine | All above |
| M4 | R0–R4 | Sub-200ms incremental rebuild | All above |
| M5 | R0–R5 | Low-overhead native watcher | All above |
| M6 | R0–R6 | HNSW vector search | All above |

**Estimated total: 8–12 weeks for M0–M4 (core value). M5–M6 are stretch goals.**
