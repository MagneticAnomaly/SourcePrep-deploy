//! Tree-sitter multi-language AST parsing for CoDRAG.
//!
//! Replaces Python's `ast.parse()` with tree-sitter for multi-language support.
//! Currently supports: Python, TypeScript, JavaScript, Go, Rust, Java, C, C++.

pub mod python;
pub mod typescript;
pub mod go;
pub mod rust_lang;
pub mod java;
pub mod cpp;
pub mod markdown;

use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ParserError {
    #[error("unsupported language: {0}")]
    UnsupportedLanguage(String),
    #[error("parse failed for {path}: {message}")]
    ParseFailed { path: String, message: String },
    #[error("tree-sitter language init failed: {0}")]
    LanguageInit(String),
}

/// A parsed symbol node extracted from source code.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParsedNode {
    /// Stable ID: "sym:{qualname}@{file_path}:{start_line}" or "file:{file_path}"
    pub id: String,
    /// Node kind: "file", "symbol", "external_module"
    pub kind: String,
    /// Symbol or file name
    pub name: String,
    /// Repo-relative file path (POSIX separators)
    pub file_path: String,
    /// Line span (1-indexed)
    pub span: Option<Span>,
    /// Detected language
    pub language: Option<String>,
    /// Additional metadata
    pub metadata: NodeMetadata,
}

/// Line span for a symbol.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Span {
    pub start_line: usize,
    pub end_line: usize,
}

/// Metadata for a parsed node.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct NodeMetadata {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub symbol_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub qualname: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_async: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_public: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decorators: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub docstring: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub external: Option<bool>,
    // ── Markdown / doc-specific fields ──
    #[serde(skip_serializing_if = "Option::is_none")]
    pub section_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ref_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub link_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub line_count: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status_markers: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub header_depth: Option<usize>,
}

/// A parsed edge (relationship) extracted from source code.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParsedEdge {
    /// Stable ID: "edge:{kind}:{source}:{target}:{disambiguator}"
    pub id: String,
    /// Edge kind: "contains", "imports"
    pub kind: String,
    /// Source node ID
    pub source: String,
    /// Target node ID
    pub target: String,
    /// Additional metadata
    pub metadata: EdgeMetadata,
}

/// Metadata for a parsed edge.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct EdgeMetadata {
    pub confidence: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub import_str: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub line: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub external: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub relative: Option<bool>,
}

/// A parse error for a single file (non-fatal).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParseFileError {
    pub file_path: String,
    pub error_type: String,
    pub message: String,
}

/// Result of parsing a single file.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ParseResult {
    pub nodes: Vec<ParsedNode>,
    pub edges: Vec<ParsedEdge>,
    pub errors: Vec<ParseFileError>,
}

impl ParseResult {
    pub fn empty() -> Self {
        Self {
            nodes: Vec::new(),
            edges: Vec::new(),
            errors: Vec::new(),
        }
    }

    pub fn merge(&mut self, other: ParseResult) {
        self.nodes.extend(other.nodes);
        self.edges.extend(other.edges);
        self.errors.extend(other.errors);
    }
}

// --- Stable ID generation (mirrors Python ids.py) ---

/// Generate a stable file node ID.
pub fn stable_file_node_id(file_path: &str) -> String {
    format!("file:{}", file_path)
}

/// Generate a stable symbol node ID.
pub fn stable_symbol_node_id(qualname: &str, file_path: &str, start_line: usize) -> String {
    format!("sym:{}@{}:{}", qualname, file_path, start_line)
}

/// Generate a stable external module ID.
pub fn stable_external_module_id(module_name: &str) -> String {
    format!("ext:{}", module_name)
}

/// Generate a stable edge ID.
pub fn stable_edge_id(kind: &str, source: &str, target: &str, disambiguator: &str) -> String {
    if disambiguator.is_empty() {
        format!("edge:{}:{}:{}", kind, source, target)
    } else {
        format!("edge:{}:{}:{}:{}", kind, source, target, disambiguator)
    }
}


/// Parse a file given its content and language.
///
/// This is the main entry point for parsing. It dispatches to the
/// appropriate language-specific analyzer based on the language string.
pub fn parse_file(
    file_path: &str,
    content: &str,
    language: &str,
    repo_root: &std::path::Path,
) -> Result<ParseResult, ParserError> {
    match language {
        "python" => python::analyze(file_path, content, repo_root),
        "typescript" | "javascript" => typescript::analyze(file_path, content, language),
        "go" => go::analyze(file_path, content),
        "rust" => rust_lang::analyze(file_path, content),
        "java" => java::analyze(file_path, content),
        "c" | "cpp" => cpp::analyze(file_path, content, language),
        "markdown" => Ok(markdown::analyze(file_path, content)),
        // Languages with file-level support but no dedicated tree-sitter parser yet.
        // Return empty ParseResult so the graph layer still creates a file node.
        "swift" | "kotlin" | "csharp" | "ruby" | "php" | "dart" | "scala"
        | "shell" | "lua" | "zig" | "elixir" => Ok(ParseResult::default()),
        _ => Err(ParserError::UnsupportedLanguage(language.to_string())),
    }
}

/// Get the list of supported languages.
pub fn supported_languages() -> &'static [&'static str] {
    &[
        "python", "typescript", "javascript", "go", "rust", "java", "c", "cpp",
        "markdown", "swift", "kotlin", "csharp", "ruby", "php", "dart", "scala",
        "shell", "lua", "zig", "elixir",
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_stable_file_node_id() {
        assert_eq!(stable_file_node_id("src/main.py"), "file:src/main.py");
    }

    #[test]
    fn test_stable_symbol_node_id() {
        assert_eq!(
            stable_symbol_node_id("MyClass.method", "src/main.py", 42),
            "sym:MyClass.method@src/main.py:42"
        );
    }

    #[test]
    fn test_stable_edge_id() {
        assert_eq!(
            stable_edge_id("contains", "file:a.py", "sym:foo@a.py:1", ""),
            "edge:contains:file:a.py:sym:foo@a.py:1"
        );
        assert_eq!(
            stable_edge_id("imports", "file:a.py", "file:b.py", "os:3"),
            "edge:imports:file:a.py:file:b.py:os:3"
        );
    }

    #[test]
    fn test_supported_languages() {
        let langs = supported_languages();
        assert!(langs.contains(&"python"));
        assert!(langs.contains(&"typescript"));
        assert!(langs.contains(&"go"));
        assert!(langs.contains(&"rust"));
        assert!(langs.contains(&"java"));
        assert!(langs.contains(&"c"));
        assert!(langs.contains(&"cpp"));
    }
}
