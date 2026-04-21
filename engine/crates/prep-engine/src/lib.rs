//! PyO3 Python bindings for the Prep Rust engine.
//!
//! This crate exposes the Rust engine to Python via PyO3.
//! It provides: file walking, content hashing, multi-language parsing,
//! trace graph building, searching, and neighbor traversal.

use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::IntoPyObjectExt;

// --- Version ---

#[pyfunction]
fn version() -> String {
    format!("prep-engine {}", env!("CARGO_PKG_VERSION"))
}

#[pyfunction]
fn supported_languages() -> Vec<String> {
    prep_parser::supported_languages()
        .iter()
        .map(|s| s.to_string())
        .collect()
}

// --- Walker ---

#[pyfunction]
#[pyo3(signature = (root, include_globs=None, exclude_globs=None, max_file_bytes=None, max_files=None))]
fn walk_repo(
    root: &str,
    include_globs: Option<Vec<String>>,
    exclude_globs: Option<Vec<String>>,
    max_file_bytes: Option<u64>,
    max_files: Option<usize>,
) -> PyResult<Vec<PyFileEntry>> {
    let mut config = prep_walker::WalkConfig::default();
    if let Some(ig) = include_globs {
        config.include_globs = ig;
    }
    if let Some(eg) = exclude_globs {
        config.exclude_globs = eg;
    }
    if let Some(mb) = max_file_bytes {
        config.max_file_bytes = mb;
    }
    if let Some(mf) = max_files {
        config.max_files = mf;
    }

    let entries = prep_walker::walk_repo(&PathBuf::from(root), &config)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    Ok(entries
        .into_iter()
        .map(|e| PyFileEntry {
            path: e.path,
            abs_path: e.abs_path.to_string_lossy().to_string(),
            size: e.size,
            modified_secs: e.modified_secs,
        })
        .collect())
}

#[pyclass]
#[derive(Clone)]
struct PyFileEntry {
    #[pyo3(get)]
    path: String,
    #[pyo3(get)]
    abs_path: String,
    #[pyo3(get)]
    size: u64,
    #[pyo3(get)]
    modified_secs: f64,
}

#[pymethods]
impl PyFileEntry {
    fn __repr__(&self) -> String {
        format!("FileEntry(path='{}', size={})", self.path, self.size)
    }
}

// --- Hashing ---

#[pyfunction]
fn hash_content(content: &str) -> String {
    prep_walker::hash_content(content)
}

#[pyfunction]
fn detect_language(path: &str) -> Option<String> {
    prep_walker::detect_language(path).map(|s| s.to_string())
}

// --- Parser ---

#[pyfunction]
fn parse_file(
    file_path: &str,
    content: &str,
    language: &str,
    repo_root: &str,
) -> PyResult<PyParseResult> {
    let result = prep_parser::parse_file(
        file_path,
        content,
        language,
        &PathBuf::from(repo_root),
    )
    .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    Ok(PyParseResult {
        nodes: result
            .nodes
            .into_iter()
            .map(|n| PyParsedNode::from(n))
            .collect(),
        edges: result
            .edges
            .into_iter()
            .map(|e| PyParsedEdge::from(e))
            .collect(),
        errors: result
            .errors
            .into_iter()
            .map(|e| PyParseError {
                file_path: e.file_path,
                error_type: e.error_type,
                message: e.message,
            })
            .collect(),
    })
}

#[pyclass]
#[derive(Clone)]
struct PyParseResult {
    #[pyo3(get)]
    nodes: Vec<PyParsedNode>,
    #[pyo3(get)]
    edges: Vec<PyParsedEdge>,
    #[pyo3(get)]
    errors: Vec<PyParseError>,
}

#[pyclass]
#[derive(Clone)]
struct PyParsedNode {
    #[pyo3(get)]
    id: String,
    #[pyo3(get)]
    kind: String,
    #[pyo3(get)]
    name: String,
    #[pyo3(get)]
    file_path: String,
    #[pyo3(get)]
    start_line: Option<usize>,
    #[pyo3(get)]
    end_line: Option<usize>,
    #[pyo3(get)]
    language: Option<String>,
    #[pyo3(get)]
    symbol_type: Option<String>,
    #[pyo3(get)]
    qualname: Option<String>,
    #[pyo3(get)]
    is_async: Option<bool>,
    #[pyo3(get)]
    is_public: Option<bool>,
    #[pyo3(get)]
    docstring: Option<String>,
    #[pyo3(get)]
    external: Option<bool>,
    // ── Markdown / doc-specific fields ──
    #[pyo3(get)]
    section_count: Option<usize>,
    #[pyo3(get)]
    ref_count: Option<usize>,
    #[pyo3(get)]
    link_count: Option<usize>,
    #[pyo3(get)]
    line_count: Option<usize>,
    #[pyo3(get)]
    status_markers: Option<Vec<String>>,
    #[pyo3(get)]
    header_depth: Option<usize>,
}

impl From<prep_parser::ParsedNode> for PyParsedNode {
    fn from(n: prep_parser::ParsedNode) -> Self {
        Self {
            id: n.id,
            kind: n.kind,
            name: n.name,
            file_path: n.file_path,
            start_line: n.span.as_ref().map(|s| s.start_line),
            end_line: n.span.as_ref().map(|s| s.end_line),
            language: n.language,
            symbol_type: n.metadata.symbol_type,
            qualname: n.metadata.qualname,
            is_async: n.metadata.is_async,
            is_public: n.metadata.is_public,
            docstring: n.metadata.docstring,
            external: n.metadata.external,
            section_count: n.metadata.section_count,
            ref_count: n.metadata.ref_count,
            link_count: n.metadata.link_count,
            line_count: n.metadata.line_count,
            status_markers: n.metadata.status_markers,
            header_depth: n.metadata.header_depth,
        }
    }
}

#[pymethods]
impl PyParsedNode {
    fn __repr__(&self) -> String {
        format!(
            "ParsedNode(id='{}', kind='{}', name='{}')",
            self.id, self.kind, self.name
        )
    }

    fn to_dict(&self, py: Python<'_>) -> PyResult<PyObject> {
        let dict = PyDict::new(py);
        dict.set_item("id", &self.id)?;
        dict.set_item("kind", &self.kind)?;
        dict.set_item("name", &self.name)?;
        dict.set_item("file_path", &self.file_path)?;
        if let (Some(start), Some(end)) = (self.start_line, self.end_line) {
            let span = PyDict::new(py);
            span.set_item("start_line", start)?;
            span.set_item("end_line", end)?;
            dict.set_item("span", span)?;
        } else {
            dict.set_item("span", py.None())?;
        }
        dict.set_item("language", &self.language)?;
        let meta = PyDict::new(py);
        if let Some(ref st) = self.symbol_type {
            meta.set_item("symbol_type", st)?;
        }
        if let Some(ref qn) = self.qualname {
            meta.set_item("qualname", qn)?;
        }
        if let Some(ia) = self.is_async {
            meta.set_item("is_async", ia)?;
        }
        if let Some(ip) = self.is_public {
            meta.set_item("is_public", ip)?;
        }
        if let Some(ref ds) = self.docstring {
            meta.set_item("docstring", ds)?;
        }
        if let Some(ext) = self.external {
            meta.set_item("external", ext)?;
        }
        if let Some(sc) = self.section_count {
            meta.set_item("section_count", sc)?;
        }
        if let Some(rc) = self.ref_count {
            meta.set_item("ref_count", rc)?;
        }
        if let Some(lc) = self.link_count {
            meta.set_item("link_count", lc)?;
        }
        if let Some(lnc) = self.line_count {
            meta.set_item("line_count", lnc)?;
        }
        if let Some(ref sm) = self.status_markers {
            meta.set_item("status_markers", sm)?;
        }
        if let Some(hd) = self.header_depth {
            meta.set_item("header_depth", hd)?;
        }
        dict.set_item("metadata", meta)?;
        Ok(dict.into())
    }
}

#[pyclass]
#[derive(Clone)]
struct PyParsedEdge {
    #[pyo3(get)]
    id: String,
    #[pyo3(get)]
    kind: String,
    #[pyo3(get)]
    source: String,
    #[pyo3(get)]
    target: String,
    #[pyo3(get)]
    confidence: f64,
    #[pyo3(get)]
    import_str: Option<String>,
    #[pyo3(get)]
    line: Option<usize>,
    #[pyo3(get)]
    external: Option<bool>,
}

impl From<prep_parser::ParsedEdge> for PyParsedEdge {
    fn from(e: prep_parser::ParsedEdge) -> Self {
        Self {
            id: e.id,
            kind: e.kind,
            source: e.source,
            target: e.target,
            confidence: e.metadata.confidence,
            import_str: e.metadata.import_str,
            line: e.metadata.line,
            external: e.metadata.external,
        }
    }
}

#[pymethods]
impl PyParsedEdge {
    fn __repr__(&self) -> String {
        format!(
            "ParsedEdge(id='{}', kind='{}', source='{}', target='{}')",
            self.id, self.kind, self.source, self.target
        )
    }

    fn to_dict(&self, py: Python<'_>) -> PyResult<PyObject> {
        let dict = PyDict::new(py);
        dict.set_item("id", &self.id)?;
        dict.set_item("kind", &self.kind)?;
        dict.set_item("source", &self.source)?;
        dict.set_item("target", &self.target)?;
        let meta = PyDict::new(py);
        meta.set_item("confidence", self.confidence)?;
        if let Some(ref imp) = self.import_str {
            meta.set_item("import", imp)?;
        }
        if let Some(line) = self.line {
            meta.set_item("line", line)?;
        }
        if let Some(ext) = self.external {
            meta.set_item("external", ext)?;
        }
        dict.set_item("metadata", meta)?;
        Ok(dict.into())
    }
}

#[pyclass]
#[derive(Clone)]
struct PyParseError {
    #[pyo3(get)]
    file_path: String,
    #[pyo3(get)]
    error_type: String,
    #[pyo3(get)]
    message: String,
}

/// Parse multiple files in parallel using rayon (Sprint 4).
///
/// Accepts a list of (file_path, content, language) tuples and returns
/// a list of PyParseResult in the same order. Errors for individual
/// files are captured in the errors field rather than raising exceptions.
#[pyfunction]
fn parse_files_parallel(
    entries: Vec<(String, String, String)>,
    repo_root: &str,
) -> PyResult<Vec<PyParseResult>> {
    let root = PathBuf::from(repo_root);
    let results = prep_parser::parse_files_parallel(&entries, &root);

    Ok(results
        .into_iter()
        .map(|r| PyParseResult {
            nodes: r.nodes.into_iter().map(PyParsedNode::from).collect(),
            edges: r.edges.into_iter().map(PyParsedEdge::from).collect(),
            errors: r
                .errors
                .into_iter()
                .map(|e| PyParseError {
                    file_path: e.file_path,
                    error_type: e.error_type,
                    message: e.message,
                })
                .collect(),
        })
        .collect())
}

// --- Trace Graph (opaque handle) ---

#[pyclass]
struct TraceHandle {
    graph: Arc<Mutex<prep_graph::TraceGraph>>,
    manifest: Option<prep_graph::TraceManifest>,
}

#[pyfunction]
#[pyo3(signature = (repo_root, index_dir, include_globs=None, exclude_globs=None, max_file_bytes=None))]
fn build_trace(
    repo_root: &str,
    index_dir: &str,
    include_globs: Option<Vec<String>>,
    exclude_globs: Option<Vec<String>>,
    max_file_bytes: Option<u64>,
) -> PyResult<TraceHandle> {
    let mut config = prep_graph::TraceBuildConfig::default();
    if let Some(ig) = include_globs {
        config.include_globs = ig;
    }
    if let Some(eg) = exclude_globs {
        config.exclude_globs = eg;
    }
    if let Some(mb) = max_file_bytes {
        config.max_file_bytes = mb;
    }

    let (graph, manifest) = prep_graph::build_trace(
        &PathBuf::from(repo_root),
        &PathBuf::from(index_dir),
        &config,
    )
    .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    Ok(TraceHandle {
        graph: Arc::new(Mutex::new(graph)),
        manifest: Some(manifest),
    })
}

#[pyfunction]
fn load_trace(index_dir: &str) -> PyResult<TraceHandle> {
    let graph = prep_graph::TraceGraph::load_jsonl(&PathBuf::from(index_dir))
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    Ok(TraceHandle {
        graph: Arc::new(Mutex::new(graph)),
        manifest: None,
    })
}

#[pymethods]
impl TraceHandle {
    fn node_count(&self) -> PyResult<usize> {
        let graph = self.graph.lock().map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        Ok(graph.node_count())
    }

    fn edge_count(&self) -> PyResult<usize> {
        let graph = self.graph.lock().map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        Ok(graph.edge_count())
    }

    fn get_node(&self, node_id: &str) -> PyResult<Option<PyParsedNode>> {
        let graph = self.graph.lock().map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        Ok(graph.get_node(node_id).map(|n| PyParsedNode::from(n.clone())))
    }

    #[pyo3(signature = (query, kind=None, limit=50))]
    fn search(&self, query: &str, kind: Option<&str>, limit: usize) -> PyResult<Vec<PyParsedNode>> {
        let graph = self.graph.lock().map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        let results = graph.search_nodes(query, kind, limit);
        Ok(results.into_iter().map(|n| PyParsedNode::from(n.clone())).collect())
    }

    #[pyo3(signature = (node_id, direction="both", edge_kinds=None, max_nodes=50))]
    fn get_neighbors(
        &self,
        node_id: &str,
        direction: &str,
        edge_kinds: Option<Vec<String>>,
        max_nodes: usize,
    ) -> PyResult<PyNeighborResult> {
        let graph = self.graph.lock().map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        let result = graph.get_neighbors(
            node_id,
            direction,
            edge_kinds.as_deref(),
            max_nodes,
        );

        Ok(PyNeighborResult {
            in_edges: result.in_edges.into_iter().map(|e| PyParsedEdge::from(e.clone())).collect(),
            out_edges: result.out_edges.into_iter().map(|e| PyParsedEdge::from(e.clone())).collect(),
            in_nodes: result.in_nodes.into_iter().map(|n| PyParsedNode::from(n.clone())).collect(),
            out_nodes: result.out_nodes.into_iter().map(|n| PyParsedNode::from(n.clone())).collect(),
        })
    }

    fn status(&self, py: Python<'_>) -> PyResult<PyObject> {
        let graph = self.graph.lock().map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        let dict = PyDict::new(py);
        dict.set_item("enabled", true)?;
        dict.set_item("exists", true)?;
        dict.set_item("building", false)?;
        let counts = PyDict::new(py);
        counts.set_item("nodes", graph.node_count())?;
        counts.set_item("edges", graph.edge_count())?;
        dict.set_item("counts", counts)?;

        if let Some(ref m) = self.manifest {
            dict.set_item("last_build_at", &m.built_at)?;
            dict.set_item("last_error", &m.last_error)?;
        } else {
            dict.set_item("last_build_at", py.None())?;
            dict.set_item("last_error", py.None())?;
        }

        Ok(dict.into())
    }

    /// Validate LLM-hypothesized relationships and add them as inferred edges.
    ///
    /// edges_json: list of dicts with keys: source_node_id, target_file_path, relationship, confidence
    /// min_confidence: minimum confidence threshold (default 0.7)
    ///
    /// Returns dict with counts: accepted, rejected_missing_source, rejected_missing_target,
    /// rejected_low_confidence, rejected_duplicate, boosted
    #[pyo3(signature = (edges_json, min_confidence=0.7))]
    fn incorporate_inferred_edges(
        &self,
        py: Python<'_>,
        edges_json: Vec<PyObject>,
        min_confidence: f64,
    ) -> PyResult<PyObject> {
        let mut hypotheses = Vec::new();
        for obj in &edges_json {
            let dict = obj.downcast_bound::<PyDict>(py)
                .map_err(|_| PyRuntimeError::new_err("Each edge must be a dict"))?;
            let source = dict.get_item("source_node_id")?
                .ok_or_else(|| PyRuntimeError::new_err("Missing source_node_id"))?
                .extract::<String>()?;
            let target = dict.get_item("target_file_path")?
                .ok_or_else(|| PyRuntimeError::new_err("Missing target_file_path"))?
                .extract::<String>()?;
            let rel = dict.get_item("relationship")?
                .ok_or_else(|| PyRuntimeError::new_err("Missing relationship"))?
                .extract::<String>()?;
            let conf = dict.get_item("confidence")?
                .ok_or_else(|| PyRuntimeError::new_err("Missing confidence"))?
                .extract::<f64>()?;
            hypotheses.push(prep_graph::InferredEdgeInput {
                source_node_id: source,
                target_file_path: target,
                relationship: rel,
                confidence: conf,
            });
        }

        let mut graph = self.graph.lock()
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        let result = graph.incorporate_inferred_edges(&hypotheses, min_confidence);

        let dict = PyDict::new(py);
        dict.set_item("accepted", result.accepted)?;
        dict.set_item("rejected_missing_source", result.rejected_missing_source)?;
        dict.set_item("rejected_missing_target", result.rejected_missing_target)?;
        dict.set_item("rejected_low_confidence", result.rejected_low_confidence)?;
        dict.set_item("rejected_duplicate", result.rejected_duplicate)?;
        dict.set_item("boosted", result.boosted)?;
        Ok(dict.into())
    }

    /// Write inferred edges to trace_inferred_edges.jsonl in the given directory.
    fn write_inferred_edges(&self, index_dir: &str) -> PyResult<usize> {
        let graph = self.graph.lock()
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        graph.write_inferred_edges_jsonl(&PathBuf::from(index_dir))
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        Ok(graph.inferred_edge_count())
    }

    /// Get the count of inferred edges in the graph.
    fn inferred_edge_count(&self) -> PyResult<usize> {
        let graph = self.graph.lock()
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        Ok(graph.inferred_edge_count())
    }

    fn __repr__(&self) -> String {
        match self.graph.lock() {
            Ok(graph) => format!(
                "TraceHandle(nodes={}, edges={})",
                graph.node_count(),
                graph.edge_count()
            ),
            Err(_) => "TraceHandle(<poisoned lock>)".to_string()
        }
    }
}

#[pyclass]
#[derive(Clone)]
struct PyNeighborResult {
    #[pyo3(get)]
    in_edges: Vec<PyParsedEdge>,
    #[pyo3(get)]
    out_edges: Vec<PyParsedEdge>,
    #[pyo3(get)]
    in_nodes: Vec<PyParsedNode>,
    #[pyo3(get)]
    out_nodes: Vec<PyParsedNode>,
}

// --- Module definition ---

// ── Sanitizer bindings ───────────────────────────────────────────────────────

#[pyfunction]
fn sanitize_code_fences(content: &str) -> String {
    prep_sanitize::sanitize_code_fences(content)
}

#[pyfunction]
fn strip_invisible_unicode(text: &str) -> String {
    prep_sanitize::strip_invisible_unicode(text)
}

#[pyfunction]
fn has_invisible_unicode(text: &str) -> bool {
    prep_sanitize::has_invisible_unicode(text)
}

#[pyfunction]
fn normalize_nfkc(text: &str) -> String {
    prep_sanitize::normalize_nfkc(text)
}

#[pyfunction]
fn detect_secrets(content: &str) -> Vec<String> {
    prep_sanitize::detect_secrets(content)
}

// ── Chunking bindings ────────────────────────────────────────────────────────

#[pyclass]
struct PyChunk {
    #[pyo3(get)]
    chunk_id: String,
    #[pyo3(get)]
    content: String,
    #[pyo3(get)]
    metadata: PyObject,
}

#[pymethods]
impl PyChunk {
    fn __repr__(&self) -> String {
        format!("Chunk(id='{}', len={})", self.chunk_id, self.content.len())
    }
}

fn chunk_to_pychunk(py: Python<'_>, chunk: prep_chunking::Chunk) -> PyResult<PyChunk> {
    let meta_json = serde_json::to_string(&chunk.metadata)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    let json_mod = py.import("json")?;
    let meta_obj = json_mod.call_method1("loads", (meta_json,))?;
    Ok(PyChunk {
        chunk_id: chunk.chunk_id,
        content: chunk.content,
        metadata: meta_obj.into_py_any(py)?,
    })
}

#[pyfunction]
#[pyo3(signature = (text, source_path, xref_id=None, name=None, max_chars=1800, min_chars=350))]
fn chunk_markdown(
    py: Python<'_>,
    text: &str,
    source_path: &str,
    xref_id: Option<&str>,
    name: Option<&str>,
    max_chars: usize,
    min_chars: usize,
) -> PyResult<Vec<PyChunk>> {
    let chunks = prep_chunking::chunk_markdown(text, source_path, xref_id, name, max_chars, min_chars);
    chunks
        .into_iter()
        .map(|c| chunk_to_pychunk(py, c))
        .collect()
}

#[pyfunction]
#[pyo3(signature = (text, source_path, max_chars=2000, overlap_chars=200))]
fn chunk_code(
    py: Python<'_>,
    text: &str,
    source_path: &str,
    max_chars: usize,
    overlap_chars: usize,
) -> PyResult<Vec<PyChunk>> {
    let chunks = prep_chunking::chunk_code(text, source_path, max_chars, overlap_chars);
    chunks
        .into_iter()
        .map(|c| chunk_to_pychunk(py, c))
        .collect()
}

// ── LOD bindings ─────────────────────────────────────────────────────────────

#[pyclass]
#[derive(Clone)]
struct PyLODResult {
    #[pyo3(get)]
    content: String,
    #[pyo3(get)]
    lod: u8,
    #[pyo3(get)]
    input_chars: usize,
    #[pyo3(get)]
    output_chars: usize,
    #[pyo3(get)]
    compression_ratio: f64,
    #[pyo3(get)]
    fallback: bool,
    #[pyo3(get)]
    error: Option<String>,
}

#[pymethods]
impl PyLODResult {
    fn __repr__(&self) -> String {
        format!("LODResult(lod={}, ratio={:.1}x)", self.lod, self.compression_ratio)
    }
}

#[pyclass]
#[derive(Clone)]
struct PySymbolInfo {
    #[pyo3(get)]
    name: String,
    #[pyo3(get)]
    kind: String,
    #[pyo3(get)]
    qualname: String,
    #[pyo3(get)]
    start_line: usize,
    #[pyo3(get)]
    end_line: usize,
    #[pyo3(get)]
    docstring: Option<String>,
    #[pyo3(get)]
    is_public: bool,
}

#[pymethods]
impl PySymbolInfo {
    #[new]
    #[pyo3(signature = (name, kind, qualname, start_line, end_line, docstring=None, is_public=true))]
    fn new(
        name: String,
        kind: String,
        qualname: String,
        start_line: usize,
        end_line: usize,
        docstring: Option<String>,
        is_public: bool,
    ) -> Self {
        PySymbolInfo {
            name,
            kind,
            qualname,
            start_line,
            end_line,
            docstring,
            is_public,
        }
    }
}

#[pyfunction]
#[pyo3(signature = (file_path, lod, symbols, repo_root, augmented_summary=None, augmented_role=None))]
fn extract_lod(
    file_path: &str,
    lod: u8,
    symbols: Vec<PySymbolInfo>,
    repo_root: &str,
    augmented_summary: Option<&str>,
    augmented_role: Option<&str>,
) -> PyLODResult {
    let sym_infos: Vec<prep_graph::lod::SymbolInfo> = symbols
        .iter()
        .map(|s| prep_graph::lod::SymbolInfo {
            name: s.name.clone(),
            kind: s.kind.clone(),
            qualname: s.qualname.clone(),
            start_line: s.start_line,
            end_line: s.end_line,
            docstring: s.docstring.clone(),
            is_public: s.is_public,
        })
        .collect();

    let augmented = if augmented_summary.is_some() || augmented_role.is_some() {
        Some(prep_graph::lod::AugmentedInfo {
            summary: augmented_summary.map(|s| s.to_string()),
            role: augmented_role.map(|s| s.to_string()),
        })
    } else {
        None
    };

    let result = prep_graph::lod::extract_lod(
        file_path,
        lod,
        &sym_infos,
        &std::path::PathBuf::from(repo_root),
        augmented.as_ref(),
    );

    let compression_ratio = result.compression_ratio();

    PyLODResult {
        content: result.content,
        lod: result.lod,
        input_chars: result.input_chars,
        output_chars: result.output_chars,
        compression_ratio,
        fallback: result.fallback,
        error: result.error,
    }
}

#[pyfunction]
#[pyo3(signature = (score, is_trace_expanded=false))]
fn assign_lod(score: f64, is_trace_expanded: bool) -> u8 {
    prep_graph::lod::assign_lod(score, is_trace_expanded)
}

// ── Phase 64D: Rust role projection scoring ──────────────────────────────────

/// Score all files in a project index against a role vector.
///
/// This is the Rust fast path for role projection. It replaces the Python
/// JSONL loading + scoring loop with in-memory Rust scoring.
///
/// Args:
///     index_dir: Path to the project's index directory (containing trace_epistemic.jsonl
///                and trace_edges.jsonl).
///     role_json: JSON-serialized RoleVector (from Python's `role.to_dict()`).
///
/// Returns:
///     List of dicts with keys: file_path, score, architecture_layer,
///     domain_tags, epistemic_confidence, extended_summary.
///     Sorted by relevance score descending.
#[pyfunction]
fn score_files_for_role(
    py: Python<'_>,
    index_dir: &str,
    role_json: &str,
) -> PyResult<PyObject> {
    // Deserialize the role vector from JSON
    let role: prep_graph::role_projection::RoleVector =
        serde_json::from_str(role_json).map_err(|e| {
            PyRuntimeError::new_err(format!("Failed to parse role JSON: {}", e))
        })?;

    // Run the Rust scoring engine
    let scored = prep_graph::role_projection::score_files_for_role(
        &std::path::PathBuf::from(index_dir),
        &role,
    );

    // Convert results to Python list of dicts
    let results = pyo3::types::PyList::empty(py);
    for sf in &scored {
        let dict = PyDict::new(py);
        dict.set_item("file_path", &sf.file_path)?;
        dict.set_item("score", sf.score)?;
        dict.set_item("architecture_layer", &sf.architecture_layer)?;
        dict.set_item("domain_tags", &sf.domain_tags)?;
        dict.set_item("epistemic_confidence", sf.epistemic_confidence)?;
        dict.set_item("extended_summary", &sf.extended_summary)?;
        results.append(dict)?;
    }

    Ok(results.into_py_any(py)?)
}

#[pymodule]
fn prep_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(supported_languages, m)?)?;
    m.add_function(wrap_pyfunction!(walk_repo, m)?)?;
    m.add_function(wrap_pyfunction!(hash_content, m)?)?;
    m.add_function(wrap_pyfunction!(detect_language, m)?)?;
    m.add_function(wrap_pyfunction!(parse_file, m)?)?;
    m.add_function(wrap_pyfunction!(parse_files_parallel, m)?)?;
    m.add_function(wrap_pyfunction!(build_trace, m)?)?;
    m.add_function(wrap_pyfunction!(load_trace, m)?)?;
    m.add_class::<PyFileEntry>()?;
    m.add_class::<PyParsedNode>()?;
    m.add_class::<PyParsedEdge>()?;
    m.add_class::<PyParseResult>()?;
    m.add_class::<PyParseError>()?;
    m.add_class::<TraceHandle>()?;
    m.add_class::<PyNeighborResult>()?;

    // ── Phase 58: Rust-accelerated functions ──
    // Sanitizer
    m.add_function(wrap_pyfunction!(sanitize_code_fences, m)?)?;
    m.add_function(wrap_pyfunction!(strip_invisible_unicode, m)?)?;
    m.add_function(wrap_pyfunction!(has_invisible_unicode, m)?)?;
    m.add_function(wrap_pyfunction!(normalize_nfkc, m)?)?;
    m.add_function(wrap_pyfunction!(detect_secrets, m)?)?;
    // Chunking
    m.add_function(wrap_pyfunction!(chunk_markdown, m)?)?;
    m.add_function(wrap_pyfunction!(chunk_code, m)?)?;
    m.add_class::<PyChunk>()?;
    // LOD
    m.add_function(wrap_pyfunction!(extract_lod, m)?)?;
    m.add_function(wrap_pyfunction!(assign_lod, m)?)?;
    m.add_class::<PyLODResult>()?;
    m.add_class::<PySymbolInfo>()?;

    // ── Phase 64D: Role projection ──
    m.add_function(wrap_pyfunction!(score_files_for_role, m)?)?;

    Ok(())
}
