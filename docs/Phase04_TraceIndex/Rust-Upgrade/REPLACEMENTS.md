# Rust Engine — Python → Rust Replacement Map

**Purpose:** Track what Python code has been replaced by Rust, for future docs/marketing/architecture updates.

**Status:** ✅ Fully integrated and verified. Rust is the default engine when `prep_engine` is installed. Python fallback works seamlessly.

---

## Completed Replacements

### File Walking (`prep-walker`)

| Python | Rust | Status |
|--------|------|--------|
| `os.walk()` in `trace.py:TraceBuilder._enumerate_files()` | `prep_walker::walk_repo()` using `ignore` crate | ✅ Built, tested |
| `hashlib.sha256()` in `ids.py:stable_file_hash()` | `prep_walker::hash_files()` using `blake3` | ✅ Built, tested |
| Glob matching via `fnmatch` in `trace.py:_is_relevant()` | `ignore` crate's built-in override system | ✅ Built, tested |
| `Path(file_path).suffix` in `trace.py:_detect_language()` | `prep_walker::detect_language()` | ✅ Built, tested |

**Performance impact:** Parallel file walking + hashing via `rayon`. Expected 10–50x speedup on repos with 10k+ files.

### Multi-Language Parsing (`prep-parser`)

| Python | Rust | Status |
|--------|------|--------|
| `ast.parse()` in `trace.py:PythonAnalyzer` | `prep_parser::python::analyze()` via tree-sitter | ✅ Built, tested |
| *(not implemented)* TS/JS parsing | `prep_parser::typescript::analyze()` via tree-sitter | ✅ Built, tested |
| *(not implemented)* Go parsing | `prep_parser::go::analyze()` via tree-sitter | ✅ Built, tested |
| *(not implemented)* Rust parsing | `prep_parser::rust_lang::analyze()` via tree-sitter | ✅ Built, tested |
| *(not implemented)* Java parsing | `prep_parser::java::analyze()` via tree-sitter | ✅ Built, tested |
| *(not implemented)* C/C++ parsing | `prep_parser::cpp::analyze()` via tree-sitter | ✅ Built, tested |
| Stable ID generation in `ids.py` | `prep_parser::{stable_file_node_id, stable_symbol_node_id, stable_edge_id, stable_external_module_id}` | ✅ Built, tested |

**Languages gained:** TypeScript, JavaScript, Go, Rust, Java, C, C++ — all with symbol extraction (functions, classes, methods, imports). Python had only file-level nodes for non-Python files before.

### Trace Graph (`prep-graph`)

| Python | Rust | Status |
|--------|------|--------|
| `Dict[str, Dict]` in `trace.py:TraceIndex._nodes` | `prep_graph::TraceGraph` (HashMap-backed) | ✅ Built, tested |
| `trace.py:TraceIndex.search_nodes()` | `prep_graph::TraceGraph::search_nodes()` | ✅ Built, tested |
| `trace.py:TraceIndex.get_neighbors()` | `prep_graph::TraceGraph::get_neighbors()` | ✅ Built, tested |
| `trace.py:TraceBuilder.build()` full pipeline | `prep_graph::build_trace()` (walk→parse→graph→write) | ✅ Built, tested |
| `trace.py:TraceIndex.load()` JSONL reader | `prep_graph::TraceGraph::load_jsonl()` | ✅ Built, tested |
| `trace.py:TraceBuilder._write_atomic()` JSONL writer | `prep_graph::TraceGraph::write_jsonl()` | ✅ Built, tested |
| *(not implemented)* incremental file removal | `prep_graph::TraceGraph::remove_file()` | ✅ Built, tested |

### PyO3 Bridge (`prep-engine`)

| Python API | Rust PyO3 Function | Status |
|-----------|-------------------|--------|
| `TraceBuilder._enumerate_files()` | `prep_engine.walk_repo()` | ✅ Built |
| `ids.stable_file_hash()` | `prep_engine.hash_content()` | ✅ Built |
| `_detect_language()` | `prep_engine.detect_language()` | ✅ Built |
| `PythonAnalyzer.analyze()` | `prep_engine.parse_file()` | ✅ Built |
| `TraceBuilder.build()` | `prep_engine.build_trace()` → `TraceHandle` | ✅ Built |
| `TraceIndex.load()` | `prep_engine.load_trace()` → `TraceHandle` | ✅ Built |
| `TraceIndex.search_nodes()` | `TraceHandle.search()` | ✅ Built |
| `TraceIndex.get_neighbors()` | `TraceHandle.get_neighbors()` | ✅ Built |
| `TraceIndex.status()` | `TraceHandle.status()` | ✅ Built |

---

## Not Replaced (Stays in Python)

| Component | File | Reason |
|-----------|------|--------|
| FastAPI server | `src/prep/api/*` | HTTP framework, not performance-critical |
| CLI (Typer) | `src/prep/cli.py` | User-facing commands, startup time irrelevant |
| Embedder (Ollama HTTP) | `src/prep/core/embedder.py` | Network I/O bound, language irrelevant |
| CodeIndex (embedding build/search) | `src/prep/core/index.py` | Orchestration + NumPy, partially I/O-bound |
| Chunking | `src/prep/core/chunking.py` | Simple string ops, could move later |
| Project registry | `src/prep/core/project_registry.py` | SQLite, low-frequency |
| Repo policy/profile | `src/prep/core/repo_policy.py` | Config parsing, one-time |
| Team config | `src/prep/core/team_config.py` | Config parsing, low-frequency |
| Watcher | `src/prep/core/watcher.py` | `watchdog` works; Rust `notify` is Phase 5 stretch |
| Dashboard (Vite/React) | `src/prep/dashboard/*` | Separate process |

---

## Framework Integration

| Integration Point | File | Status |
|-------------------|------|--------|
| Engine detection | `src/prep/core/__init__.py` | ✅ `PREP_ENGINE=rust\|python\|auto` env var |
| TraceBuilder.build() | `src/prep/core/trace.py` | ✅ Delegates to `_build_rust()` when ENGINE=rust |
| TraceIndex.load() | `src/prep/core/trace.py` | ✅ Uses Rust `TraceHandle` for all queries |
| TraceIndex.search_nodes() | `src/prep/core/trace.py` | ✅ Delegates to `TraceHandle.search()` |
| TraceIndex.get_neighbors() | `src/prep/core/trace.py` | ✅ Delegates to `TraceHandle.get_neighbors()` |
| TraceIndex.node_degree() | `src/prep/core/trace.py` | ✅ New method — works with both backends |
| TraceIndex.status() | `src/prep/core/trace.py` | ✅ Delegates to `TraceHandle.status()` |
| API: `/trace/status` | `src/prep/server.py` | ✅ Uses TraceIndex (auto-delegates) |
| API: `/trace/search` | `src/prep/server.py` | ✅ Uses TraceIndex (auto-delegates) |
| API: `/trace/node/{id}` | `src/prep/server.py` | ✅ Fixed: uses `node_degree()` instead of internal dicts |
| API: `/trace/neighbors/{id}` | `src/prep/server.py` | ✅ Uses TraceIndex (auto-delegates) |
| Watcher rebuild | `src/prep/server.py` | ✅ Calls TraceBuilder.build() — auto-delegates |
| Python fallback | `src/prep/core/trace.py` | ✅ Works when `prep_engine` not installed |

---

## Test Results

### Rust Tests (cargo test)

| Crate | Tests | Status |
|-------|-------|--------|
| `prep-walker` | 6 | ✅ All pass |
| `prep-parser` | 32 | ✅ All pass |
| `prep-graph` | 3 | ✅ All pass |
| **Total** | **41** | **✅ All pass, 0 warnings** |

### Python Tests (pytest)

| Suite | ENGINE=rust | ENGINE=python |
|-------|-------------|---------------|
| Full test suite | 76 passed, 36 skipped | 76 passed, 36 skipped |
| Trace endpoint tests | 2/2 passed | 2/2 passed |

### Performance (Prep src/ — 41 files)

| Operation | Time |
|-----------|------|
| Full trace build (547 nodes, 656 edges) | **72ms** |
| Load from JSONL | **1ms** |
| Search/neighbors | **sub-ms** |

---

## Marketing/Docs Implications

When the Rust engine becomes the primary path, update:

1. **Marketing copy** — "Built with Rust for speed" / "Multi-language structural index"
2. **Pricing page** — highlight 8-language support as a Pro/Starter feature
3. **Security page** — "No garbage collector pauses, predictable performance"
4. **Download page** — platform-specific pre-built binaries
5. **Architecture docs** — update `ARCHITECTURE.md` to reflect the Rust engine layer
6. **README** — mention Rust core in the tech stack section

---

*Last updated: 2026-02-07*
