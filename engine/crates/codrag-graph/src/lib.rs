//! In-memory trace graph storage and queries for CoDRAG.
//!
//! Provides a compact, arena-friendly graph that stores trace nodes and edges
//! with efficient lookup by ID, name search, and neighbor traversal.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use codrag_parser::{ParsedEdge, ParsedNode};
use codrag_walker::WalkConfig;
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum GraphError {
    #[error("walker error: {0}")]
    Walker(#[from] codrag_walker::WalkerError),
    #[error("parser error: {0}")]
    Parser(#[from] codrag_parser::ParserError),
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("graph validation failed: {0}")]
    Validation(String),
    #[error("trace index not found at {0}")]
    NotFound(PathBuf),
}

/// The in-memory trace graph. Holds all nodes and edges with index structures.
#[derive(Debug)]
pub struct TraceGraph {
    nodes: HashMap<String, ParsedNode>,
    edges: Vec<ParsedEdge>,
    edges_by_source: HashMap<String, Vec<usize>>,
    edges_by_target: HashMap<String, Vec<usize>>,
}

impl TraceGraph {
    /// Create an empty graph.
    pub fn new() -> Self {
        Self {
            nodes: HashMap::new(),
            edges: Vec::new(),
            edges_by_source: HashMap::new(),
            edges_by_target: HashMap::new(),
        }
    }

    /// Build graph from pre-parsed nodes and edges.
    pub fn from_parts(nodes: Vec<ParsedNode>, edges: Vec<ParsedEdge>) -> Self {
        let mut graph = Self::new();
        for node in nodes {
            graph.nodes.insert(node.id.clone(), node);
        }
        for (i, edge) in edges.into_iter().enumerate() {
            graph
                .edges_by_source
                .entry(edge.source.clone())
                .or_default()
                .push(i);
            graph
                .edges_by_target
                .entry(edge.target.clone())
                .or_default()
                .push(i);
            graph.edges.push(edge);
        }
        graph
    }

    /// Number of nodes in the graph.
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    /// Number of edges in the graph.
    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }

    /// Get a node by ID.
    pub fn get_node(&self, id: &str) -> Option<&ParsedNode> {
        self.nodes.get(id)
    }

    /// Search nodes by name (exact > prefix > substring matching).
    pub fn search_nodes(
        &self,
        query: &str,
        kind: Option<&str>,
        limit: usize,
    ) -> Vec<&ParsedNode> {
        let query_lower = query.to_lowercase();
        let mut scored: Vec<(f64, &ParsedNode)> = Vec::new();

        for node in self.nodes.values() {
            if let Some(k) = kind {
                if node.kind != k {
                    continue;
                }
            }

            let name_lower = node.name.to_lowercase();
            let qualname_lower = node
                .metadata
                .qualname
                .as_deref()
                .unwrap_or("")
                .to_lowercase();

            let score = if name_lower == query_lower {
                1.0
            } else if name_lower.starts_with(&query_lower) {
                0.8
            } else if name_lower.contains(&query_lower) {
                0.6
            } else if qualname_lower.contains(&query_lower) {
                0.4
            } else {
                continue;
            };

            scored.push((score, node));
        }

        scored.sort_by(|a, b| {
            b.0.partial_cmp(&a.0)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| a.1.file_path.cmp(&b.1.file_path))
                .then_with(|| a.1.name.cmp(&b.1.name))
        });

        scored.into_iter().take(limit).map(|(_, n)| n).collect()
    }

    /// Get neighboring nodes and edges for a given node.
    pub fn get_neighbors(
        &self,
        node_id: &str,
        direction: &str,
        edge_kinds: Option<&[String]>,
        max_nodes: usize,
    ) -> NeighborResult<'_> {
        let mut in_edges = Vec::new();
        let mut out_edges = Vec::new();

        if direction == "in" || direction == "both" {
            if let Some(indices) = self.edges_by_target.get(node_id) {
                for &i in indices {
                    let edge = &self.edges[i];
                    if let Some(kinds) = edge_kinds {
                        if !kinds.iter().any(|k| k == &edge.kind) {
                            continue;
                        }
                    }
                    in_edges.push(edge);
                    if in_edges.len() >= max_nodes {
                        break;
                    }
                }
            }
        }

        if direction == "out" || direction == "both" {
            if let Some(indices) = self.edges_by_source.get(node_id) {
                for &i in indices {
                    let edge = &self.edges[i];
                    if let Some(kinds) = edge_kinds {
                        if !kinds.iter().any(|k| k == &edge.kind) {
                            continue;
                        }
                    }
                    out_edges.push(edge);
                    if out_edges.len() >= max_nodes {
                        break;
                    }
                }
            }
        }

        let in_nodes: Vec<&ParsedNode> = in_edges
            .iter()
            .filter_map(|e| self.nodes.get(&e.source))
            .collect();
        let out_nodes: Vec<&ParsedNode> = out_edges
            .iter()
            .filter_map(|e| self.nodes.get(&e.target))
            .collect();

        NeighborResult {
            in_edges,
            out_edges,
            in_nodes,
            out_nodes,
        }
    }

    /// Add a node to the graph.
    pub fn add_node(&mut self, node: ParsedNode) {
        self.nodes.insert(node.id.clone(), node);
    }

    /// Add an edge to the graph.
    pub fn add_edge(&mut self, edge: ParsedEdge) {
        let i = self.edges.len();
        self.edges_by_source
            .entry(edge.source.clone())
            .or_default()
            .push(i);
        self.edges_by_target
            .entry(edge.target.clone())
            .or_default()
            .push(i);
        self.edges.push(edge);
    }

    /// Remove all nodes and edges associated with a file path.
    /// Used for incremental rebuilds.
    pub fn remove_file(&mut self, file_path: &str) {
        // Collect node IDs to remove
        let remove_ids: Vec<String> = self
            .nodes
            .values()
            .filter(|n| n.file_path == file_path)
            .map(|n| n.id.clone())
            .collect();

        for id in &remove_ids {
            self.nodes.remove(id);
        }

        // Remove edges referencing removed nodes and rebuild indexes
        let old_edges = std::mem::take(&mut self.edges);
        self.edges_by_source.clear();
        self.edges_by_target.clear();

        for edge in old_edges {
            if remove_ids.contains(&edge.source) || remove_ids.contains(&edge.target) {
                continue;
            }
            self.add_edge(edge);
        }
    }

    /// Resolve path aliases from tsconfig.json/jsconfig.json.
    ///
    /// Finds `external_module` nodes whose names match path alias patterns
    /// (e.g. `@/components/Foo`) and rewrites edges to point to the actual
    /// internal file node (e.g. `file:src/components/Foo.tsx`).
    /// Removes orphaned external_module nodes after rewriting.
    pub fn resolve_path_aliases(&mut self, repo_root: &Path) {
        let aliases = load_path_aliases(repo_root);
        if aliases.is_empty() {
            return;
        }

        // Collect external_module nodes that match an alias pattern
        let mut rewrites: HashMap<String, String> = HashMap::new(); // ext_id -> file_node_id

        let ext_nodes: Vec<(String, String)> = self
            .nodes
            .values()
            .filter(|n| n.kind == "external_module")
            .map(|n| (n.id.clone(), n.name.clone()))
            .collect();

        let extensions = [".ts", ".tsx", ".js", ".jsx", ".css", ".scss", ""];
        let index_files = ["index.ts", "index.tsx", "index.js", "index.jsx"];

        for (ext_id, module_name) in &ext_nodes {
            for (prefix, replacement) in &aliases {
                if !module_name.starts_with(prefix) {
                    continue;
                }
                let rest = &module_name[prefix.len()..];
                let base = format!("{}{}", replacement, rest);

                // Try with extensions
                let mut resolved = None;
                for ext in &extensions {
                    let candidate = format!("{}{}", base, ext);
                    let file_id = codrag_parser::stable_file_node_id(&candidate);
                    if self.nodes.contains_key(&file_id) {
                        resolved = Some(file_id);
                        break;
                    }
                    // Also check filesystem for files not yet in graph
                    if repo_root.join(&candidate).exists() {
                        resolved = Some(file_id);
                        break;
                    }
                }

                // Try as directory with index file
                if resolved.is_none() {
                    for idx in &index_files {
                        let candidate = format!("{}/{}", base.trim_end_matches('/'), idx);
                        let file_id = codrag_parser::stable_file_node_id(&candidate);
                        if self.nodes.contains_key(&file_id) {
                            resolved = Some(file_id);
                            break;
                        }
                        if repo_root.join(&candidate).exists() {
                            resolved = Some(file_id);
                            break;
                        }
                    }
                }

                if let Some(file_id) = resolved {
                    rewrites.insert(ext_id.clone(), file_id);
                    break;
                }
            }
        }

        if rewrites.is_empty() {
            return;
        }

        log::info!(
            "Resolved {} path alias imports to internal files",
            rewrites.len()
        );

        // Rewrite edges: replace ext targets with file targets
        let old_edges = std::mem::take(&mut self.edges);
        self.edges_by_source.clear();
        self.edges_by_target.clear();

        for mut edge in old_edges {
            if let Some(new_target) = rewrites.get(&edge.target) {
                edge.target = new_target.clone();
                // Update edge metadata: no longer external
                edge.metadata.external = None;
                // Regenerate edge ID with new target
                let disambiguator = edge
                    .metadata
                    .import_str
                    .as_ref()
                    .map(|s| format!("{}:{}", s, edge.metadata.line.unwrap_or(0)))
                    .unwrap_or_default();
                edge.id = codrag_parser::stable_edge_id(
                    &edge.kind,
                    &edge.source,
                    &edge.target,
                    &disambiguator,
                );
                // Bump confidence for resolved aliases
                edge.metadata.confidence = 0.9;
            }
            self.add_edge(edge);
        }

        // Remove orphaned external_module nodes (those that were rewritten)
        for ext_id in rewrites.keys() {
            self.nodes.remove(ext_id);
        }
    }

    /// Get all nodes, sorted deterministically.
    pub fn sorted_nodes(&self) -> Vec<&ParsedNode> {
        let mut nodes: Vec<&ParsedNode> = self.nodes.values().collect();
        nodes.sort_by(|a, b| {
            let kind_ord = |k: &str| match k {
                "file" => 0,
                "symbol" => 1,
                "external_module" => 2,
                _ => 99,
            };
            kind_ord(&a.kind)
                .cmp(&kind_ord(&b.kind))
                .then_with(|| a.file_path.cmp(&b.file_path))
                .then_with(|| {
                    let a_line = a.span.as_ref().map(|s| s.start_line).unwrap_or(0);
                    let b_line = b.span.as_ref().map(|s| s.start_line).unwrap_or(0);
                    a_line.cmp(&b_line)
                })
                .then_with(|| a.name.cmp(&b.name))
        });
        nodes
    }

    /// Get all edges, sorted deterministically.
    pub fn sorted_edges(&self) -> Vec<&ParsedEdge> {
        let mut edges: Vec<&ParsedEdge> = self.edges.iter().collect();
        edges.sort_by(|a, b| {
            a.kind
                .cmp(&b.kind)
                .then_with(|| a.source.cmp(&b.source))
                .then_with(|| a.target.cmp(&b.target))
                .then_with(|| a.id.cmp(&b.id))
        });
        edges
    }

    /// Write the graph to JSONL files (same format as Python output).
    pub fn write_jsonl(&self, index_dir: &Path) -> Result<(), GraphError> {
        use std::fs;
        use std::io::Write;

        fs::create_dir_all(index_dir)?;

        // Write nodes
        let nodes_path = index_dir.join("trace_nodes.jsonl");
        let mut nodes_file = fs::File::create(&nodes_path)?;
        for node in self.sorted_nodes() {
            let json = serde_json::to_string(node).map_err(|e| {
                GraphError::Io(std::io::Error::new(std::io::ErrorKind::Other, e))
            })?;
            writeln!(nodes_file, "{}", json)?;
        }
        nodes_file.flush()?;

        // Write edges
        let edges_path = index_dir.join("trace_edges.jsonl");
        let mut edges_file = fs::File::create(&edges_path)?;
        for edge in self.sorted_edges() {
            let json = serde_json::to_string(edge).map_err(|e| {
                GraphError::Io(std::io::Error::new(std::io::ErrorKind::Other, e))
            })?;
            writeln!(edges_file, "{}", json)?;
        }
        edges_file.flush()?;

        Ok(())
    }

    /// Load a graph from existing JSONL files.
    pub fn load_jsonl(index_dir: &Path) -> Result<Self, GraphError> {
        use std::io::BufRead;

        let nodes_path = index_dir.join("trace_nodes.jsonl");
        let edges_path = index_dir.join("trace_edges.jsonl");

        if !nodes_path.exists() || !edges_path.exists() {
            return Err(GraphError::NotFound(index_dir.to_path_buf()));
        }

        let mut nodes = Vec::new();
        let nodes_file = std::fs::File::open(&nodes_path)?;
        for line in std::io::BufReader::new(nodes_file).lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            let node: ParsedNode = serde_json::from_str(&line).map_err(|e| {
                GraphError::Io(std::io::Error::new(std::io::ErrorKind::InvalidData, e))
            })?;
            nodes.push(node);
        }

        let mut edges = Vec::new();
        let edges_file = std::fs::File::open(&edges_path)?;
        for line in std::io::BufReader::new(edges_file).lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            let edge: ParsedEdge = serde_json::from_str(&line).map_err(|e| {
                GraphError::Io(std::io::Error::new(std::io::ErrorKind::InvalidData, e))
            })?;
            edges.push(edge);
        }

        Ok(Self::from_parts(nodes, edges))
    }
}

/// Result of a neighbor query.
pub struct NeighborResult<'a> {
    pub in_edges: Vec<&'a ParsedEdge>,
    pub out_edges: Vec<&'a ParsedEdge>,
    pub in_nodes: Vec<&'a ParsedNode>,
    pub out_nodes: Vec<&'a ParsedNode>,
}

/// Build manifest matching Python's trace_manifest.json format.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TraceManifest {
    pub version: String,
    pub built_at: String,
    pub project: ManifestProject,
    pub config: ManifestConfig,
    pub counts: ManifestCounts,
    pub file_errors: Vec<ManifestFileError>,
    pub last_error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManifestProject {
    pub repo_root: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManifestConfig {
    pub include_globs: Vec<String>,
    pub exclude_globs: Vec<String>,
    pub max_file_bytes: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManifestCounts {
    pub nodes: usize,
    pub edges: usize,
    pub files_parsed: usize,
    pub files_failed: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManifestFileError {
    pub file_path: String,
    pub error_type: String,
    pub message: String,
}

/// Load path aliases from tsconfig.json or jsconfig.json.
///
/// Returns a map of alias prefix (e.g. "@/") to replacement directory (e.g. "src/").
fn load_path_aliases(repo_root: &Path) -> HashMap<String, String> {
    let mut aliases = HashMap::new();
    for config_name in &["tsconfig.json", "jsconfig.json"] {
        let config_path = repo_root.join(config_name);
        let content = match std::fs::read_to_string(&config_path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let data: serde_json::Value = match serde_json::from_str(&content) {
            Ok(v) => v,
            Err(_) => continue,
        };
        let paths = match data
            .get("compilerOptions")
            .and_then(|co| co.get("paths"))
            .and_then(|p| p.as_object())
        {
            Some(p) => p,
            None => continue,
        };
        let base_url = data
            .get("compilerOptions")
            .and_then(|co| co.get("baseUrl"))
            .and_then(|b| b.as_str())
            .unwrap_or(".");

        for (pattern, targets) in paths {
            if !pattern.ends_with("/*") {
                continue;
            }
            let prefix = &pattern[..pattern.len() - 1]; // "@/*" → "@/"
            let target = match targets.as_array().and_then(|a| a.first()).and_then(|t| t.as_str()) {
                Some(t) => t,
                None => continue,
            };
            let mut resolved = target.to_string();
            if resolved.ends_with("/*") {
                resolved = resolved[..resolved.len() - 1].to_string(); // "./src/*" → "./src/"
            }
            // Strip leading "./"
            if resolved.starts_with("./") {
                resolved = resolved[2..].to_string();
            }
            if !resolved.ends_with('/') {
                resolved.push('/');
            }
            if base_url != "." {
                resolved = format!("{}/{}", base_url.trim_end_matches('/'), resolved);
            }
            aliases.insert(prefix.to_string(), resolved);
        }
        break; // Use first config found
    }
    aliases
}

/// Configuration for a full trace build.
#[derive(Debug, Clone)]
pub struct TraceBuildConfig {
    pub include_globs: Vec<String>,
    pub exclude_globs: Vec<String>,
    pub max_file_bytes: u64,
    pub max_files: usize,
    pub max_failures: usize,
}

impl Default for TraceBuildConfig {
    fn default() -> Self {
        let walk = WalkConfig::default();
        Self {
            include_globs: walk.include_globs,
            exclude_globs: walk.exclude_globs,
            max_file_bytes: walk.max_file_bytes,
            max_files: walk.max_files,
            max_failures: 50,
        }
    }
}

/// Build a complete trace index: walk → parse → graph → write.
///
/// This is the main entry point that replaces Python's `TraceBuilder.build()`.
pub fn build_trace(
    repo_root: &Path,
    index_dir: &Path,
    config: &TraceBuildConfig,
) -> Result<(TraceGraph, TraceManifest), GraphError> {
    let walk_config = WalkConfig {
        include_globs: config.include_globs.clone(),
        exclude_globs: config.exclude_globs.clone(),
        max_file_bytes: config.max_file_bytes,
        max_files: config.max_files,
        ..Default::default()
    };

    // Phase 1: Walk
    let entries = codrag_walker::walk_repo(repo_root, &walk_config)?;

    // Phase 2: Parse each file
    let mut graph = TraceGraph::new();
    let mut files_parsed = 0usize;
    let mut files_failed = 0usize;
    let mut file_errors = Vec::new();

    for entry in &entries {
        // Add file node
        let file_node_id = codrag_parser::stable_file_node_id(&entry.path);
        let language = codrag_walker::detect_language(&entry.path);

        graph.add_node(ParsedNode {
            id: file_node_id.clone(),
            kind: "file".to_string(),
            name: Path::new(&entry.path)
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string(),
            file_path: entry.path.clone(),
            span: None,
            language: language.map(|l| l.to_string()),
            metadata: Default::default(),
        });

        // Parse if language is supported
        if let Some(lang) = language {
            let content = match std::fs::read_to_string(&entry.abs_path) {
                Ok(c) => c,
                Err(e) => {
                    files_failed += 1;
                    if file_errors.len() < config.max_failures {
                        file_errors.push(ManifestFileError {
                            file_path: entry.path.clone(),
                            error_type: "ReadError".to_string(),
                            message: e.to_string(),
                        });
                    }
                    continue;
                }
            };

            match codrag_parser::parse_file(&entry.path, &content, lang, repo_root) {
                Ok(result) => {
                    for node in result.nodes {
                        graph.add_node(node);
                    }
                    for edge in result.edges {
                        graph.add_edge(edge);
                    }
                    files_parsed += 1;
                }
                Err(e) => {
                    files_failed += 1;
                    if file_errors.len() < config.max_failures {
                        file_errors.push(ManifestFileError {
                            file_path: entry.path.clone(),
                            error_type: "ParseError".to_string(),
                            message: e.to_string(),
                        });
                    }
                    files_parsed += 1; // still counted as processed
                }
            }
        } else {
            files_parsed += 1;
        }
    }

    // Phase 2.5: Resolve path aliases (e.g. @/ → src/) from tsconfig/jsconfig
    graph.resolve_path_aliases(repo_root);

    // Phase 3: Write
    graph.write_jsonl(index_dir)?;

    let manifest = TraceManifest {
        version: "1.0".to_string(),
        built_at: chrono_now_utc(),
        project: ManifestProject {
            repo_root: repo_root.to_string_lossy().to_string(),
        },
        config: ManifestConfig {
            include_globs: config.include_globs.clone(),
            exclude_globs: config.exclude_globs.clone(),
            max_file_bytes: config.max_file_bytes,
        },
        counts: ManifestCounts {
            nodes: graph.node_count(),
            edges: graph.edge_count(),
            files_parsed,
            files_failed,
        },
        file_errors,
        last_error: None,
    };

    // Write manifest
    let manifest_json = serde_json::to_string_pretty(&manifest).map_err(|e| {
        GraphError::Io(std::io::Error::new(std::io::ErrorKind::Other, e))
    })?;
    std::fs::write(index_dir.join("trace_manifest.json"), manifest_json)?;

    Ok((graph, manifest))
}

/// Input for an LLM-hypothesized relationship to be validated by Rust.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferredEdgeInput {
    pub source_node_id: String,
    pub target_file_path: String,
    pub relationship: String,
    pub confidence: f64,
}

/// Result of incorporating inferred edges.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferredEdgeResult {
    pub accepted: usize,
    pub rejected_missing_source: usize,
    pub rejected_missing_target: usize,
    pub rejected_low_confidence: usize,
    pub rejected_duplicate: usize,
    pub boosted: usize,
}

impl TraceGraph {
    /// Validate LLM-hypothesized relationships and add them as inferred edges.
    ///
    /// For each hypothesis:
    /// 1. Check source node exists in graph
    /// 2. Resolve target_file_path to a file node ID, check it exists
    /// 3. Reject if confidence < min_confidence
    /// 4. Reject if an identical edge already exists
    /// 5. If a structural "references" edge already exists between the same
    ///    endpoints, boost the inferred confidence to 1.0 (mutual confirmation)
    /// 6. Add as edge with kind "inferred"
    ///
    /// Returns statistics about accepted/rejected edges.
    pub fn incorporate_inferred_edges(
        &mut self,
        hypotheses: &[InferredEdgeInput],
        min_confidence: f64,
    ) -> InferredEdgeResult {
        let mut result = InferredEdgeResult {
            accepted: 0,
            rejected_missing_source: 0,
            rejected_missing_target: 0,
            rejected_low_confidence: 0,
            rejected_duplicate: 0,
            boosted: 0,
        };

        for hyp in hypotheses {
            // 1. Source must exist
            if !self.nodes.contains_key(&hyp.source_node_id) {
                result.rejected_missing_source += 1;
                continue;
            }

            // 2. Resolve target file path to node ID
            let target_id = codrag_parser::stable_file_node_id(&hyp.target_file_path);
            if !self.nodes.contains_key(&target_id) {
                result.rejected_missing_target += 1;
                continue;
            }

            // 3. Confidence gate
            if hyp.confidence < min_confidence {
                result.rejected_low_confidence += 1;
                continue;
            }

            // 4. Check for duplicate inferred edge
            let edge_id = codrag_parser::stable_edge_id(
                "inferred",
                &hyp.source_node_id,
                &target_id,
                &hyp.relationship,
            );
            let is_duplicate = self.edges.iter().any(|e| e.id == edge_id);
            if is_duplicate {
                result.rejected_duplicate += 1;
                continue;
            }

            // 5. Check for mutual confirmation with structural edges
            let mut final_confidence = hyp.confidence;
            let has_structural = self.edges.iter().any(|e| {
                (e.source == hyp.source_node_id && e.target == target_id
                    && (e.kind == "references" || e.kind == "links_to" || e.kind == "imports"))
                || (e.source == target_id && e.target == hyp.source_node_id
                    && (e.kind == "references" || e.kind == "links_to" || e.kind == "imports"))
            });
            if has_structural {
                final_confidence = 1.0;
                result.boosted += 1;
            }

            // 6. Add inferred edge
            self.add_edge(ParsedEdge {
                id: edge_id,
                kind: "inferred".to_string(),
                source: hyp.source_node_id.clone(),
                target: target_id,
                metadata: codrag_parser::EdgeMetadata {
                    confidence: final_confidence,
                    import_str: Some(hyp.relationship.clone()),
                    ..Default::default()
                },
            });
            result.accepted += 1;
        }

        result
    }

    /// Write only inferred edges to a separate JSONL file.
    pub fn write_inferred_edges_jsonl(&self, index_dir: &Path) -> Result<(), GraphError> {
        use std::fs;
        use std::io::Write;

        let path = index_dir.join("trace_inferred_edges.jsonl");
        let mut file = fs::File::create(&path)?;
        for edge in &self.edges {
            if edge.kind == "inferred" {
                let json = serde_json::to_string(edge).map_err(|e| {
                    GraphError::Io(std::io::Error::new(std::io::ErrorKind::Other, e))
                })?;
                writeln!(file, "{}", json)?;
            }
        }
        file.flush()?;
        Ok(())
    }

    /// Count inferred edges in the graph.
    pub fn inferred_edge_count(&self) -> usize {
        self.edges.iter().filter(|e| e.kind == "inferred").count()
    }
}

fn chrono_now_utc() -> String {
    // Simple UTC timestamp without chrono dependency
    use std::time::SystemTime;
    let dur = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or_default();
    // ISO 8601 approximation
    let secs = dur.as_secs();
    let days = secs / 86400;
    let time_secs = secs % 86400;
    let hours = time_secs / 3600;
    let mins = (time_secs % 3600) / 60;
    let s = time_secs % 60;
    // Rough date calc (good enough for timestamps, not calendar-accurate)
    let mut y = 1970u64;
    let mut remaining_days = days;
    loop {
        let days_in_year = if y % 4 == 0 && (y % 100 != 0 || y % 400 == 0) { 366 } else { 365 };
        if remaining_days < days_in_year { break; }
        remaining_days -= days_in_year;
        y += 1;
    }
    let month_days = [31, if y % 4 == 0 && (y % 100 != 0 || y % 400 == 0) { 29 } else { 28 }, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    let mut m = 0;
    for md in &month_days {
        if remaining_days < *md as u64 { break; }
        remaining_days -= *md as u64;
        m += 1;
    }
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
        y, m + 1, remaining_days + 1, hours, mins, s
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use codrag_parser::Span;

    #[test]
    fn test_graph_basic() {
        let mut graph = TraceGraph::new();

        graph.add_node(ParsedNode {
            id: "file:main.py".to_string(),
            kind: "file".to_string(),
            name: "main.py".to_string(),
            file_path: "main.py".to_string(),
            span: None,
            language: Some("python".to_string()),
            metadata: Default::default(),
        });

        graph.add_node(ParsedNode {
            id: "sym:hello@main.py:1".to_string(),
            kind: "symbol".to_string(),
            name: "hello".to_string(),
            file_path: "main.py".to_string(),
            span: Some(Span { start_line: 1, end_line: 3 }),
            language: Some("python".to_string()),
            metadata: codrag_parser::NodeMetadata {
                symbol_type: Some("function".to_string()),
                qualname: Some("hello".to_string()),
                ..Default::default()
            },
        });

        graph.add_edge(ParsedEdge {
            id: "edge:contains:file:main.py:sym:hello@main.py:1".to_string(),
            kind: "contains".to_string(),
            source: "file:main.py".to_string(),
            target: "sym:hello@main.py:1".to_string(),
            metadata: codrag_parser::EdgeMetadata { confidence: 1.0, ..Default::default() },
        });

        assert_eq!(graph.node_count(), 2);
        assert_eq!(graph.edge_count(), 1);

        // Search
        let results = graph.search_nodes("hello", None, 10);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].name, "hello");

        // Neighbors
        let neighbors = graph.get_neighbors("file:main.py", "out", None, 10);
        assert_eq!(neighbors.out_edges.len(), 1);
        assert_eq!(neighbors.out_nodes.len(), 1);
    }

    #[test]
    fn test_graph_remove_file() {
        let mut graph = TraceGraph::new();

        graph.add_node(ParsedNode {
            id: "file:a.py".to_string(),
            kind: "file".to_string(),
            name: "a.py".to_string(),
            file_path: "a.py".to_string(),
            span: None,
            language: Some("python".to_string()),
            metadata: Default::default(),
        });

        graph.add_node(ParsedNode {
            id: "sym:foo@a.py:1".to_string(),
            kind: "symbol".to_string(),
            name: "foo".to_string(),
            file_path: "a.py".to_string(),
            span: Some(Span { start_line: 1, end_line: 2 }),
            language: Some("python".to_string()),
            metadata: Default::default(),
        });

        graph.add_node(ParsedNode {
            id: "file:b.py".to_string(),
            kind: "file".to_string(),
            name: "b.py".to_string(),
            file_path: "b.py".to_string(),
            span: None,
            language: Some("python".to_string()),
            metadata: Default::default(),
        });

        graph.add_edge(ParsedEdge {
            id: "edge:contains:file:a.py:sym:foo@a.py:1".to_string(),
            kind: "contains".to_string(),
            source: "file:a.py".to_string(),
            target: "sym:foo@a.py:1".to_string(),
            metadata: codrag_parser::EdgeMetadata { confidence: 1.0, ..Default::default() },
        });

        assert_eq!(graph.node_count(), 3);
        assert_eq!(graph.edge_count(), 1);

        graph.remove_file("a.py");

        assert_eq!(graph.node_count(), 1); // only b.py remains
        assert_eq!(graph.edge_count(), 0); // edge removed
    }

    #[test]
    fn test_jsonl_roundtrip() {
        let dir = tempfile::tempdir().unwrap();
        let mut graph = TraceGraph::new();

        graph.add_node(ParsedNode {
            id: "file:test.py".to_string(),
            kind: "file".to_string(),
            name: "test.py".to_string(),
            file_path: "test.py".to_string(),
            span: None,
            language: Some("python".to_string()),
            metadata: Default::default(),
        });

        graph.write_jsonl(dir.path()).unwrap();

        let loaded = TraceGraph::load_jsonl(dir.path()).unwrap();
        assert_eq!(loaded.node_count(), 1);
        assert!(loaded.get_node("file:test.py").is_some());
    }

    fn make_test_graph_for_inferred() -> TraceGraph {
        let mut graph = TraceGraph::new();
        // Add file nodes
        for (path, lang) in &[
            ("src/main.py", "python"),
            ("src/utils.py", "python"),
            ("docs/README.md", "markdown"),
        ] {
            graph.add_node(ParsedNode {
                id: format!("file:{}", path),
                kind: "file".to_string(),
                name: std::path::Path::new(path).file_name().unwrap().to_string_lossy().to_string(),
                file_path: path.to_string(),
                span: None,
                language: Some(lang.to_string()),
                metadata: Default::default(),
            });
        }
        // Add a structural "references" edge: README.md → main.py
        graph.add_edge(ParsedEdge {
            id: "edge:references:file:docs/README.md:file:src/main.py:ref:0".to_string(),
            kind: "references".to_string(),
            source: "file:docs/README.md".to_string(),
            target: "file:src/main.py".to_string(),
            metadata: codrag_parser::EdgeMetadata { confidence: 0.9, ..Default::default() },
        });
        graph
    }

    #[test]
    fn test_inferred_accept_valid() {
        let mut graph = make_test_graph_for_inferred();
        let hyps = vec![InferredEdgeInput {
            source_node_id: "file:src/main.py".to_string(),
            target_file_path: "src/utils.py".to_string(),
            relationship: "uses".to_string(),
            confidence: 0.8,
        }];
        let r = graph.incorporate_inferred_edges(&hyps, 0.7);
        assert_eq!(r.accepted, 1);
        assert_eq!(graph.inferred_edge_count(), 1);
    }

    #[test]
    fn test_inferred_reject_missing_source() {
        let mut graph = make_test_graph_for_inferred();
        let hyps = vec![InferredEdgeInput {
            source_node_id: "file:nonexistent.py".to_string(),
            target_file_path: "src/utils.py".to_string(),
            relationship: "uses".to_string(),
            confidence: 0.9,
        }];
        let r = graph.incorporate_inferred_edges(&hyps, 0.7);
        assert_eq!(r.rejected_missing_source, 1);
        assert_eq!(r.accepted, 0);
    }

    #[test]
    fn test_inferred_reject_missing_target() {
        let mut graph = make_test_graph_for_inferred();
        let hyps = vec![InferredEdgeInput {
            source_node_id: "file:src/main.py".to_string(),
            target_file_path: "src/nonexistent.py".to_string(),
            relationship: "uses".to_string(),
            confidence: 0.9,
        }];
        let r = graph.incorporate_inferred_edges(&hyps, 0.7);
        assert_eq!(r.rejected_missing_target, 1);
        assert_eq!(r.accepted, 0);
    }

    #[test]
    fn test_inferred_reject_low_confidence() {
        let mut graph = make_test_graph_for_inferred();
        let hyps = vec![InferredEdgeInput {
            source_node_id: "file:src/main.py".to_string(),
            target_file_path: "src/utils.py".to_string(),
            relationship: "uses".to_string(),
            confidence: 0.5, // below 0.7 threshold
        }];
        let r = graph.incorporate_inferred_edges(&hyps, 0.7);
        assert_eq!(r.rejected_low_confidence, 1);
        assert_eq!(r.accepted, 0);
    }

    #[test]
    fn test_inferred_reject_duplicate() {
        let mut graph = make_test_graph_for_inferred();
        let hyps = vec![InferredEdgeInput {
            source_node_id: "file:src/main.py".to_string(),
            target_file_path: "src/utils.py".to_string(),
            relationship: "uses".to_string(),
            confidence: 0.8,
        }];
        // First call: accepted
        let r1 = graph.incorporate_inferred_edges(&hyps, 0.7);
        assert_eq!(r1.accepted, 1);
        // Second call: duplicate
        let r2 = graph.incorporate_inferred_edges(&hyps, 0.7);
        assert_eq!(r2.rejected_duplicate, 1);
        assert_eq!(r2.accepted, 0);
        assert_eq!(graph.inferred_edge_count(), 1); // still just one
    }

    #[test]
    fn test_inferred_boost_on_structural_match() {
        let mut graph = make_test_graph_for_inferred();
        // README.md already has a structural "references" edge to main.py
        let hyps = vec![InferredEdgeInput {
            source_node_id: "file:docs/README.md".to_string(),
            target_file_path: "src/main.py".to_string(),
            relationship: "documents".to_string(),
            confidence: 0.75,
        }];
        let r = graph.incorporate_inferred_edges(&hyps, 0.7);
        assert_eq!(r.accepted, 1);
        assert_eq!(r.boosted, 1);
        // The inferred edge should have confidence 1.0 (boosted)
        let inferred = graph.edges.iter().find(|e| e.kind == "inferred").unwrap();
        assert_eq!(inferred.metadata.confidence, 1.0);
    }

    #[test]
    fn test_inferred_write_jsonl() {
        let dir = tempfile::tempdir().unwrap();
        let mut graph = make_test_graph_for_inferred();
        let hyps = vec![
            InferredEdgeInput {
                source_node_id: "file:src/main.py".to_string(),
                target_file_path: "src/utils.py".to_string(),
                relationship: "uses".to_string(),
                confidence: 0.85,
            },
            InferredEdgeInput {
                source_node_id: "file:docs/README.md".to_string(),
                target_file_path: "src/main.py".to_string(),
                relationship: "documents".to_string(),
                confidence: 0.9,
            },
        ];
        graph.incorporate_inferred_edges(&hyps, 0.7);
        graph.write_inferred_edges_jsonl(dir.path()).unwrap();

        // Read back and verify
        let path = dir.path().join("trace_inferred_edges.jsonl");
        assert!(path.exists());
        let content = std::fs::read_to_string(&path).unwrap();
        let lines: Vec<&str> = content.lines().filter(|l| !l.is_empty()).collect();
        assert_eq!(lines.len(), 2);
    }
}
