# Phase 58: Rust Improvements – Implementation Plan

> Migrate CPU-bound text processing from Python to Rust via new crates, exposed through the existing PyO3 `codrag_engine` module.

## Background

The CoDRAG Rust engine currently provides file walking (`codrag-walker`), AST parsing (`codrag-parser`), and graph storage/queries (`codrag-graph`). Three Python modules sit on hot paths that are purely CPU-bound text processing — ideal Rust migration candidates:

| Module | Size | Hot Path | Callers |
|--------|------|----------|---------|
| `content_sanitizer.py` | 442 lines, 13 functions | Every LLM call + MCP response | `llm_client.py` (6 sites), `index.py`, `layered_index.py`, `security_health.py` |
| `chunking.py` | 274 lines, 3 functions | Every index build | `index.py`, `build_manager.py`, `batch_strategy.py` |
| `lod_extractor.py` | 534 lines, 1 class + 1 fn | Every MCP search result | `search.py` (3 sites) |

## User Review Required

> [!IMPORTANT]
> **Migration strategy**: We use a "Rust-first, Python-fallback" pattern. The Python modules remain untouched. Each caller gets a `try: from codrag_engine import rust_fn; except: from .python_module import python_fn` wrapper. This means:
> - Zero risk of breakage — if Rust build fails, Python code still works.
> - Existing Python tests remain valid as the correctness baseline.
> - We can A/B compare outputs during development.

> [!WARNING]
> **DLP/audit-log functions stay in Python**. The content sanitizer contains `is_file_blocked_by_dlp`, `is_provider_approved_for_data`, `check_dlp_before_llm_call`, and `redact_secrets_in_content` which rely on Python `logging`, `audit_log`, and `fnmatch`/`PurePath`. These are **not on critical hot paths** and their tight coupling to Python logging makes migration cost > benefit. Only the 5 text-processing functions move to Rust.

---

## Proposed Changes

### Sprint 1: Content Sanitizer (`codrag-sanitize`)

The simplest, lowest-risk migration. Pure functions, no state, comprehensive existing tests.

#### Functions to port to Rust:

| Python Function | Rust Equivalent | Logic |
|----------------|-----------------|-------|
| `sanitize_code_fence_content(str) → str` | `sanitize_code_fences(text: &str) → String` | Regex: replace runs of 3+ backticks |
| `strip_invisible_unicode(str) → str` | `strip_invisible_unicode(text: &str) → String` | Character-class removal (24 chars + Plane 14) |
| `detect_invisible_unicode(str) → bool` | `has_invisible_unicode(text: &str) → bool` | Character-class search |
| `normalize_nfkc(str) → str` | `normalize_nfkc(text: &str) → String` | NFKC normalization |
| `detect_secrets(str) → list[str]` | `detect_secrets(text: &str) → Vec<String>` | 12 compiled regex patterns |

#### [NEW] [Cargo.toml](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/engine/crates/codrag-sanitize/Cargo.toml)

New crate `codrag-sanitize` in the workspace.

Dependencies: `regex`, `unicode-normalization`, `once_cell` (for compiled regex caching).

---

#### [MODIFY] [Cargo.toml](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/engine/Cargo.toml)

Add `"crates/codrag-sanitize"` to `[workspace.members]`.
Add `regex = "1"`, `unicode-normalization = "0.1"`, `once_cell = "1"` to `[workspace.dependencies]`.

---

#### [NEW] [lib.rs](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/engine/crates/codrag-sanitize/src/lib.rs)

Pure Rust library implementing all 5 functions:
- `sanitize_code_fences`: uses compiled `Regex` for `` ` `` ` `` ` `` `{3,}` matching, replaces with curly quotes.
- `strip_invisible_unicode`: iterates chars, filters against hardcoded set + U+E0000..U+E007F range.
- `has_invisible_unicode`: short-circuit search version of above.
- `normalize_nfkc`: wraps `unicode-normalization` crate's `nfkc()`.
- `detect_secrets`: 12 compiled `Regex` patterns via `once_cell::sync::Lazy`, returns matched pattern prefixes.

Includes `#[cfg(test)] mod tests` with Rust unit tests ported from the 380-line Python test suite.

---

#### [MODIFY] [codrag-engine Cargo.toml](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/engine/crates/codrag-engine/Cargo.toml)

Add dependency: `codrag-sanitize = { path = "../codrag-sanitize" }`.

---

#### [MODIFY] [codrag-engine lib.rs](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/engine/crates/codrag-engine/src/lib.rs)

- Add PyO3 `#[pyfunction]` wrappers for all 5 sanitizer functions.
- Register them in the `codrag_engine` pymodule.

---

### Sprint 2: Chunking (`codrag-chunking`)

#### Functions to port:

| Python Function | Rust Equivalent |
|----------------|-----------------|
| `chunk_markdown(text, path, xref_id, name, max, min) → [Chunk]` | `chunk_markdown(text, path, xref_id, name, max, min) → Vec<PyChunk>` |
| `chunk_code(text, path, max, overlap) → [Chunk]` | `chunk_code(text, path, max, overlap) → Vec<PyChunk>` |

The `Chunk` dataclass maps to a `#[pyclass] PyChunk` with `chunk_id`, `content`, `metadata` fields.

**Key dependency**: The chunk ID functions in `ids.py` (`stable_markdown_chunk_id`, `stable_code_chunk_id`) must produce identical output. We'll implement the same SHA-256 truncation in Rust using the `sha2` crate, with cross-validation tests.

#### [NEW] [Cargo.toml](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/engine/crates/codrag-chunking/Cargo.toml)

Dependencies: `regex`, `sha2`, `serde`, `serde_json`.

---

#### [NEW] [lib.rs](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/engine/crates/codrag-chunking/src/lib.rs)

- `struct Chunk { chunk_id, content, metadata }` 
- `chunk_markdown()`: heading-based markdown splitting with min/max size limits and pending-section merging.
- `chunk_code()`: size-based code splitting with overlap.
- Internal `stable_sha256()`, `stable_markdown_chunk_id()`, `stable_code_chunk_id()` matching `ids.py` exactly.

---

#### [MODIFY] [codrag-engine Cargo.toml](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/engine/crates/codrag-engine/Cargo.toml)

Add `codrag-chunking` dependency.

---

#### [MODIFY] [codrag-engine lib.rs](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/engine/crates/codrag-engine/src/lib.rs)

- Add `#[pyclass] PyChunk` and `#[pyfunction]` wrappers for `chunk_markdown` and `chunk_code`.
- Register in pymodule.

---

### Sprint 3: LOD Extractor (embed in `codrag-graph`)

This is the most complex migration. The LOD extractor needs access to trace graph nodes and source file content, which are already in `codrag-graph`.

#### Functions to port:

| Python | Rust |
|--------|------|
| `LODExtractor.extract(file_path, lod, nodes, repo_root, augmented_data?) → LODResult` | `TraceHandle.extract_lod(file_path, lod) → PyLODResult` |
| `assign_lod(score, is_trace_expanded?) → int` | `assign_lod(score, is_trace_expanded) → u8` |

**Key insight**: Instead of a separate crate, we add LOD extraction directly to `codrag-graph` since it needs graph node data. The `TraceHandle` PyO3 class already exposes graph queries — we add `extract_lod()` as a method.

#### [MODIFY] [codrag-graph lib.rs](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/engine/crates/codrag-graph/src/lib.rs)

Add `pub mod lod;` containing:
- LOD 0: read file, return as-is
- LOD 1: strip comments (language-aware regex)
- LOD 2: signatures + docstrings + `...` (uses `ParsedNode` spans from graph)
- LOD 3: class skeletons only (filter to class-kind nodes)
- LOD 4: imports + first line of each symbol
- LOD 5: file path + exported symbol names + augmented summary

---

#### [MODIFY] [codrag-engine lib.rs](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/engine/crates/codrag-engine/src/lib.rs)

- Add `#[pyclass] PyLODResult` with `content`, `lod`, `input_chars`, `output_chars`, `compression_ratio`, `fallback`, `error`.
- Add `extract_lod()` method to `TraceHandle`.
- Add standalone `#[pyfunction] assign_lod(score, is_trace?)`.

---

### Sprint 4: Python Integration Wiring

#### [MODIFY] [content_sanitizer.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/content_sanitizer.py)

At the top of the module, add Rust-first imports with Python fallback:

```python
try:
    from codrag_engine import (
        sanitize_code_fences as sanitize_code_fence_content,
        strip_invisible_unicode,
        has_invisible_unicode as detect_invisible_unicode,
        normalize_nfkc,
        detect_secrets,
    )
    _USING_RUST_SANITIZER = True
except ImportError:
    _USING_RUST_SANITIZER = False
    # Keep existing Python implementations as fallback
```

The higher-level functions (`sanitize_llm_input`, `sanitize_output`, `validate_llm_output`) stay in Python but call the Rust primitives when available.

---

#### [MODIFY] [chunking.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/chunking.py)

Same pattern — try Rust `chunk_markdown`/`chunk_code` first, fall back to Python.

---

#### [MODIFY] [lod_extractor.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/lod_extractor.py)

`LODExtractor.extract()` tries `self._trace_handle.extract_lod()` first, falls back to Python implementation.

---

## Verification Plan

### Automated Tests

**1. Rust unit tests** (run each sprint):
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/engine
cargo test -p codrag-sanitize   # Sprint 1
cargo test -p codrag-chunking   # Sprint 2
cargo test -p codrag-graph      # Sprint 3 (LOD tests)
cargo test                      # Full workspace
```

**2. Existing Python test suites** (must pass unchanged after Sprint 4):
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
python -m pytest tests/test_content_sanitizer.py -v   # 380 lines, 9 test classes
python -m pytest tests/test_lod_extractor.py -v        # 653 lines, 12 test classes
```

**3. New cross-validation test** (add in Sprint 4):
```bash
python -m pytest tests/test_rust_parity.py -v
```

This test will call both Python and Rust implementations side-by-side and assert identical output for a diverse set of inputs. Covers:
- Unicode edge cases (CJK, emoji, combining characters, Plane 14)
- Adversarial inputs (nested backticks, mixed invisible chars)
- Chunk ID determinism (SHA-256 output must match exactly)
- LOD level output parity across Python/Rust implementations

**4. Build integration**:
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/engine
maturin develop --release   # Build and install the PyO3 module
python -c "import codrag_engine; print(codrag_engine.version())"
```

### Manual Verification

After Sprint 4 wiring:
1. Run the full pipeline on a test project and verify MCP search results are identical
2. Spot-check LOD output at levels 0, 2, 4, 5 via the dashboard
3. Verify `_USING_RUST_SANITIZER` flag is `True` in a running instance

---

## Sprint Order Rationale

```
Sprint 1 (Sanitizer)  →  Sprint 2 (Chunking)  →  Sprint 3 (LOD)  →  Sprint 4 (Wiring)
     Easy / Low risk         Medium / Low risk       Complex / Med risk    Integration
```

- **Sanitizer first**: Simplest pure functions, builds confidence in the Rust→PyO3 pipeline.
- **Chunking second**: Medium complexity, introduces `PyChunk` return type pattern.
- **LOD third**: Most complex, needs graph data access, benefits from lessons learned.
- **Wiring last**: Single integration pass avoids back-and-forth between Python and Rust.
