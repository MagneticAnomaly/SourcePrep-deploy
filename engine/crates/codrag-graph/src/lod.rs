//! Level of Detail (LOD) extraction for source code files.
//!
//! Provides structural compression of source code at 6 LOD levels:
//! - LOD 0: Full source (passthrough)
//! - LOD 1: Strip comments
//! - LOD 2: Signatures + docstrings (bodies replaced with `...`)
//! - LOD 3: Class skeletons only
//! - LOD 4: Imports + first line of each symbol
//! - LOD 5: File summary (path + exported names)

use once_cell::sync::Lazy;
use regex::Regex;
use std::path::Path;

/// Result of LOD extraction for a single file.
#[derive(Debug, Clone)]
pub struct LODResult {
    pub content: String,
    pub lod: u8,
    pub input_chars: usize,
    pub output_chars: usize,
    pub fallback: bool,
    pub error: Option<String>,
}

impl LODResult {
    pub fn compression_ratio(&self) -> f64 {
        let denom = self.output_chars.max(1);
        self.input_chars as f64 / denom as f64
    }
}

/// Minimal symbol info needed for LOD extraction.
#[derive(Debug, Clone)]
pub struct SymbolInfo {
    pub name: String,
    pub kind: String,          // "function", "method", "class", "async_method"
    pub qualname: String,
    pub start_line: usize,     // 1-indexed
    pub end_line: usize,       // 1-indexed, inclusive
    pub docstring: Option<String>,
    pub is_public: bool,
}

/// Augmented data for a file node (summary, role, etc.)
#[derive(Debug, Clone, Default)]
pub struct AugmentedInfo {
    pub summary: Option<String>,
    pub role: Option<String>,
}

// ── Comment-stripping regexes ────────────────────────────────────────────────

static _HASH_COMMENT_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"^\s*#[^!].*$").unwrap());
static HASH_COMMENT_FULL_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"^\s*#.*$").unwrap());
static SLASH_COMMENT_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"^\s*//.*$").unwrap());
static IMPORT_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(?m)^(?:import\s|from\s|use\s|require\(|const\s.*=\s*require\(|export\s)").unwrap()
});

/// Determine the LOD level to assign based on a relevance score.
///
/// Matches the Python `assign_lod()` function exactly.
pub fn assign_lod(score: f64, is_trace_expanded: bool) -> u8 {
    if is_trace_expanded {
        return 4;
    }
    if score >= 0.50 {
        0
    } else if score >= 0.35 {
        2
    } else if score >= 0.20 {
        4
    } else {
        5
    }
}

/// Extract source code at a given LOD level.
///
/// # Arguments
/// * `file_path` - Relative path to the file within the repo
/// * `lod` - LOD level (0-5)
/// * `symbols` - Symbol information from the trace graph
/// * `repo_root` - Absolute path to the repository root
/// * `augmented` - Optional augmented data for LOD 5
pub fn extract_lod(
    file_path: &str,
    lod: u8,
    symbols: &[SymbolInfo],
    repo_root: &Path,
    augmented: Option<&AugmentedInfo>,
) -> LODResult {
    // Read the source file
    let abs_path = repo_root.join(file_path);
    let source = match std::fs::read_to_string(&abs_path) {
        Ok(s) => s,
        Err(e) => {
            return LODResult {
                content: String::new(),
                lod,
                input_chars: 0,
                output_chars: 0,
                fallback: false,
                error: Some(format!("Failed to read {}: {}", file_path, e)),
            };
        }
    };

    let input_chars = source.len();

    let (content, used_lod, fallback) = match lod {
        0 => (source.clone(), 0u8, false),
        1 => (extract_lod1(&source, file_path), 1, false),
        2 => {
            if symbols.is_empty() {
                // Fallback to LOD 0 when no symbols
                (source.clone(), 0, true)
            } else {
                (extract_lod2(&source, symbols), 2, false)
            }
        }
        3 => {
            if symbols.is_empty() {
                (source.clone(), 0, true)
            } else {
                (extract_lod3(&source, symbols), 3, false)
            }
        }
        4 => {
            if symbols.is_empty() {
                (source.clone(), 0, true)
            } else {
                (extract_lod4(&source, file_path, symbols), 4, false)
            }
        }
        5 => (extract_lod5(file_path, symbols, augmented), 5, false),
        _ => (source.clone(), 0, true),
    };

    let output_chars = content.len();

    LODResult {
        content,
        lod: used_lod,
        input_chars,
        output_chars,
        fallback,
        error: None,
    }
}

// ── LOD 1: Strip comments ────────────────────────────────────────────────────

fn extract_lod1(source: &str, file_path: &str) -> String {
    let lines: Vec<&str> = source.lines().collect();
    let ext = Path::new(file_path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("");

    let is_hash_lang = matches!(ext, "py" | "rb" | "sh" | "bash" | "yaml" | "yml" | "toml");
    let is_slash_lang = matches!(ext, "js" | "ts" | "jsx" | "tsx" | "rs" | "go" | "java" | "c" | "cpp" | "h" | "hpp" | "cs" | "swift" | "kt");

    let filtered: Vec<&str> = lines
        .into_iter()
        .filter(|line| {
            if is_hash_lang && HASH_COMMENT_FULL_RE.is_match(line) {
                // Keep shebang lines
                return line.starts_with("#!");
            }
            if is_slash_lang && SLASH_COMMENT_RE.is_match(line) {
                return false;
            }
            true
        })
        .collect();

    let result = filtered.join("\n");
    // Collapse multiple blank lines
    collapse_blank_lines(&result)
}

fn collapse_blank_lines(text: &str) -> String {
    let mut result = String::with_capacity(text.len());
    let mut blank_count = 0;
    for line in text.lines() {
        if line.trim().is_empty() {
            blank_count += 1;
            if blank_count <= 2 {
                result.push('\n');
            }
        } else {
            blank_count = 0;
            result.push_str(line);
            result.push('\n');
        }
    }
    // Trim trailing newlines to match Python behavior
    while result.ends_with('\n') && result.len() > 1 {
        let trimmed = result.trim_end_matches('\n');
        if trimmed.is_empty() {
            break;
        }
        result = format!("{}\n", trimmed);
        break;
    }
    result
}

// ── LOD 2: Signatures + docstrings ───────────────────────────────────────────

fn extract_lod2(source: &str, symbols: &[SymbolInfo]) -> String {
    let lines: Vec<&str> = source.lines().collect();
    let mut output_lines: Vec<String> = Vec::new();
    let mut covered_lines: Vec<bool> = vec![false; lines.len()];

    // First, collect import lines (always preserved)
    for (i, line) in lines.iter().enumerate() {
        if IMPORT_RE.is_match(line) {
            output_lines.push(line.to_string());
            covered_lines[i] = true;
        }
    }

    // Add blank line after imports if any
    if !output_lines.is_empty() {
        output_lines.push(String::new());
    }

    // Sort symbols by start_line
    let mut sorted_symbols: Vec<&SymbolInfo> = symbols.iter().collect();
    sorted_symbols.sort_by_key(|s| s.start_line);

    for sym in &sorted_symbols {
        if sym.start_line == 0 || sym.end_line == 0 {
            continue;
        }
        let start_idx = sym.start_line.saturating_sub(1); // to 0-indexed
        let end_idx = sym.end_line.min(lines.len());       // inclusive, but cap

        if start_idx >= lines.len() {
            continue;
        }

        // Get the definition/signature line
        let sig_line = lines[start_idx];
        output_lines.push(sig_line.to_string());

        // Add docstring if present
        if let Some(ref doc) = sym.docstring {
            let indent = get_indent(sig_line);
            let inner_indent = format!("{}    ", indent);
            output_lines.push(format!("{}\"\"\"{}\"\"\"", inner_indent, doc));
        }

        // Add body placeholder
        let indent = get_indent(sig_line);
        output_lines.push(format!("{}    ...", indent));
        output_lines.push(String::new());

        // Mark these lines as covered
        for i in start_idx..end_idx {
            if i < covered_lines.len() {
                covered_lines[i] = true;
            }
        }
    }

    output_lines.join("\n")
}

fn get_indent(line: &str) -> String {
    let trimmed = line.trim_start();
    line[..line.len() - trimmed.len()].to_string()
}

// ── LOD 3: Class skeletons only ──────────────────────────────────────────────

fn extract_lod3(source: &str, symbols: &[SymbolInfo]) -> String {
    let lines: Vec<&str> = source.lines().collect();
    let mut output_lines: Vec<String> = Vec::new();

    // Collect imports
    for line in &lines {
        if IMPORT_RE.is_match(line) {
            output_lines.push(line.to_string());
        }
    }
    if !output_lines.is_empty() {
        output_lines.push(String::new());
    }

    // Only include class-kind symbols and their methods
    let classes: Vec<&SymbolInfo> = symbols
        .iter()
        .filter(|s| s.kind == "class")
        .collect();

    let methods: Vec<&SymbolInfo> = symbols
        .iter()
        .filter(|s| s.kind == "method" || s.kind == "async_method")
        .collect();

    for cls in &classes {
        if cls.start_line == 0 || cls.start_line > lines.len() {
            continue;
        }
        let sig_line = lines[cls.start_line - 1];
        output_lines.push(sig_line.to_string());

        if let Some(ref doc) = cls.docstring {
            let indent = get_indent(sig_line);
            output_lines.push(format!("{}    \"\"\"{}\"\"\"", indent, doc));
        }

        // Add method signatures within this class
        for method in &methods {
            if method.start_line >= cls.start_line && method.end_line <= cls.end_line {
                if method.start_line > 0 && method.start_line <= lines.len() {
                    output_lines.push(String::new());
                    let method_line = lines[method.start_line - 1];
                    output_lines.push(method_line.to_string());
                    if let Some(ref doc) = method.docstring {
                        let indent = get_indent(method_line);
                        output_lines.push(format!("{}    \"\"\"{}\"\"\"", indent, doc));
                    }
                    output_lines.push(format!("{}    ...", get_indent(method_line)));
                }
            }
        }

        output_lines.push(String::new());
    }

    output_lines.join("\n")
}

// ── LOD 4: Imports + first line of each symbol ───────────────────────────────

fn extract_lod4(source: &str, _file_path: &str, symbols: &[SymbolInfo]) -> String {
    let lines: Vec<&str> = source.lines().collect();
    let mut output_lines: Vec<String> = Vec::new();

    // Import lines
    for line in &lines {
        if IMPORT_RE.is_match(line) {
            output_lines.push(line.to_string());
        }
    }
    if !output_lines.is_empty() {
        output_lines.push(String::new());
    }

    // First line of each symbol
    let mut sorted_symbols: Vec<&SymbolInfo> = symbols.iter().collect();
    sorted_symbols.sort_by_key(|s| s.start_line);

    for sym in &sorted_symbols {
        if sym.start_line == 0 || sym.start_line > lines.len() {
            continue;
        }
        output_lines.push(lines[sym.start_line - 1].to_string());
    }

    output_lines.join("\n")
}

// ── LOD 5: File summary ─────────────────────────────────────────────────────

fn extract_lod5(
    file_path: &str,
    symbols: &[SymbolInfo],
    augmented: Option<&AugmentedInfo>,
) -> String {
    let mut parts: Vec<String> = vec![format!("# {}", file_path)];

    // Add augmented info if available
    if let Some(aug) = augmented {
        if let Some(ref summary) = aug.summary {
            parts.push(format!("Summary: {}", summary));
        }
        if let Some(ref role) = aug.role {
            parts.push(format!("Role: {}", role));
        }
    }

    // List exported/public symbol names
    let public_names: Vec<&str> = symbols
        .iter()
        .filter(|s| s.is_public && (s.kind == "function" || s.kind == "class" || s.kind == "method" || s.kind == "async_method"))
        .map(|s| s.name.as_str())
        .collect();

    if !public_names.is_empty() {
        parts.push(format!("Exports: {}", public_names.join(", ")));
    }

    parts.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn make_temp_repo() -> (tempfile::TempDir, Vec<SymbolInfo>) {
        let dir = tempfile::tempdir().unwrap();
        let src_dir = dir.path().join("src");
        fs::create_dir_all(&src_dir).unwrap();

        let source = r#"import os
import sys
from pathlib import Path

CONSTANT = 42

def standalone_function(x: int, y: int) -> int:
    """Return the sum of x and y."""
    result = x + y
    return result


class MyClass:
    """A sample class."""

    class_var: str = "hello"

    def __init__(self, name: str) -> None:
        """Initialize MyClass."""
        self.name = name
        self._data: List[int] = []

    def method_one(self, value: int) -> bool:
        """Check if value is positive."""
        if value > 0:
            return True
        return False

    async def async_method(self) -> str:
        """Return the name asynchronously."""
        return self.name
"#;

        fs::write(src_dir.join("example.py"), source).unwrap();

        let symbols = vec![
            SymbolInfo {
                name: "standalone_function".to_string(),
                kind: "function".to_string(),
                qualname: "standalone_function".to_string(),
                start_line: 7,
                end_line: 10,
                docstring: Some("Return the sum of x and y.".to_string()),
                is_public: true,
            },
            SymbolInfo {
                name: "MyClass".to_string(),
                kind: "class".to_string(),
                qualname: "MyClass".to_string(),
                start_line: 13,
                end_line: 31,
                docstring: Some("A sample class.".to_string()),
                is_public: true,
            },
            SymbolInfo {
                name: "__init__".to_string(),
                kind: "method".to_string(),
                qualname: "MyClass.__init__".to_string(),
                start_line: 18,
                end_line: 21,
                docstring: Some("Initialize MyClass.".to_string()),
                is_public: false,
            },
            SymbolInfo {
                name: "method_one".to_string(),
                kind: "method".to_string(),
                qualname: "MyClass.method_one".to_string(),
                start_line: 23,
                end_line: 27,
                docstring: Some("Check if value is positive.".to_string()),
                is_public: true,
            },
            SymbolInfo {
                name: "async_method".to_string(),
                kind: "async_method".to_string(),
                qualname: "MyClass.async_method".to_string(),
                start_line: 29,
                end_line: 31,
                docstring: Some("Return the name asynchronously.".to_string()),
                is_public: true,
            },
        ];

        (dir, symbols)
    }

    #[test]
    fn test_lod0_full_source() {
        let (dir, _symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 0, &[], dir.path(), None);
        assert_eq!(result.lod, 0);
        assert!(!result.fallback);
        assert!(result.content.contains("import os"));
        assert!(result.content.contains("standalone_function"));
        assert!(result.error.is_none());
    }

    #[test]
    fn test_lod0_compression_ratio_is_one() {
        let (dir, _symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 0, &[], dir.path(), None);
        assert!((result.compression_ratio() - 1.0).abs() < 0.05);
    }

    #[test]
    fn test_lod0_missing_file() {
        let (dir, _symbols) = make_temp_repo();
        let result = extract_lod("src/nonexistent.py", 0, &[], dir.path(), None);
        assert!(result.error.is_some());
        assert_eq!(result.content, "");
    }

    #[test]
    fn test_lod1_strips_comments() {
        let (dir, _symbols) = make_temp_repo();
        // Create a file with comments
        let src = "# module comment\nimport os\n# another comment\nX = 1\n";
        let src_dir = dir.path().join("src");
        fs::write(src_dir.join("commented.py"), src).unwrap();

        let result = extract_lod("src/commented.py", 1, &[], dir.path(), None);
        assert!(!result.content.contains("# module comment"));
        assert!(result.content.contains("import os"));
        assert!(result.content.contains("X = 1"));
    }

    #[test]
    fn test_lod2_contains_signatures() {
        let (dir, symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 2, &symbols, dir.path(), None);
        assert_eq!(result.lod, 2);
        assert!(!result.fallback);
        assert!(result.content.contains("def standalone_function(x: int, y: int) -> int:"));
        assert!(result.content.contains("class MyClass:"));
        assert!(result.content.contains("def method_one"));
    }

    #[test]
    fn test_lod2_contains_docstrings() {
        let (dir, symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 2, &symbols, dir.path(), None);
        assert!(result.content.contains("Return the sum of x and y."));
    }

    #[test]
    fn test_lod2_body_replaced() {
        let (dir, symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 2, &symbols, dir.path(), None);
        assert!(result.content.contains("..."));
        assert!(!result.content.contains("result = x + y"));
    }

    #[test]
    fn test_lod2_fallback_no_symbols() {
        let (dir, _symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 2, &[], dir.path(), None);
        assert!(result.fallback);
        assert_eq!(result.lod, 0);
    }

    #[test]
    fn test_lod2_imports_preserved() {
        let (dir, symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 2, &symbols, dir.path(), None);
        assert!(result.content.contains("import os"));
        assert!(result.content.contains("import sys"));
        assert!(result.content.contains("from pathlib import Path"));
    }

    #[test]
    fn test_lod3_class_retained() {
        let (dir, symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 3, &symbols, dir.path(), None);
        assert!(result.content.contains("class MyClass:"));
    }

    #[test]
    fn test_lod3_method_signatures_retained() {
        let (dir, symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 3, &symbols, dir.path(), None);
        assert!(result.content.contains("def method_one"));
    }

    #[test]
    fn test_lod3_smaller_than_lod2() {
        let (dir, symbols) = make_temp_repo();
        let r2 = extract_lod("src/example.py", 2, &symbols, dir.path(), None);
        let r3 = extract_lod("src/example.py", 3, &symbols, dir.path(), None);
        assert!(r3.output_chars <= r2.output_chars);
    }

    #[test]
    fn test_lod4_imports_preserved() {
        let (dir, symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 4, &symbols, dir.path(), None);
        assert!(result.content.contains("import os"));
        assert!(result.content.contains("import sys"));
    }

    #[test]
    fn test_lod4_symbol_first_lines() {
        let (dir, symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 4, &symbols, dir.path(), None);
        assert!(result.content.contains("def standalone_function"));
        assert!(result.content.contains("class MyClass"));
    }

    #[test]
    fn test_lod4_bodies_absent() {
        let (dir, symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 4, &symbols, dir.path(), None);
        assert!(!result.content.contains("result = x + y"));
    }

    #[test]
    fn test_lod4_smaller_than_lod2() {
        let (dir, symbols) = make_temp_repo();
        let r2 = extract_lod("src/example.py", 2, &symbols, dir.path(), None);
        let r4 = extract_lod("src/example.py", 4, &symbols, dir.path(), None);
        assert!(r4.output_chars < r2.output_chars);
    }

    #[test]
    fn test_lod5_contains_file_path() {
        let (dir, symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 5, &symbols, dir.path(), None);
        assert!(result.content.contains("src/example.py"));
    }

    #[test]
    fn test_lod5_contains_exported_names() {
        let (dir, symbols) = make_temp_repo();
        let result = extract_lod("src/example.py", 5, &symbols, dir.path(), None);
        assert!(result.content.contains("standalone_function"));
        assert!(result.content.contains("MyClass"));
    }

    #[test]
    fn test_lod5_with_augmented_data() {
        let (dir, symbols) = make_temp_repo();
        let aug = AugmentedInfo {
            summary: Some("Core utility module for arithmetic and OOP examples.".to_string()),
            role: Some("utility".to_string()),
        };
        let result = extract_lod("src/example.py", 5, &symbols, dir.path(), Some(&aug));
        assert!(result.content.contains("Core utility module"));
        assert!(result.content.contains("utility"));
    }

    #[test]
    fn test_lod5_smallest() {
        let (dir, symbols) = make_temp_repo();
        let r4 = extract_lod("src/example.py", 4, &symbols, dir.path(), None);
        let r5 = extract_lod("src/example.py", 5, &symbols, dir.path(), None);
        assert!(r5.output_chars < r4.output_chars);
    }

    #[test]
    fn test_monotonicity() {
        let (dir, symbols) = make_temp_repo();
        let sizes: Vec<usize> = (0..6)
            .map(|lod| {
                extract_lod("src/example.py", lod, &symbols, dir.path(), None).output_chars
            })
            .collect();

        // LOD 0 >= LOD 2 >= LOD 4 >= LOD 5
        assert!(sizes[0] >= sizes[2], "LOD0 ({}) < LOD2 ({})", sizes[0], sizes[2]);
        assert!(sizes[2] >= sizes[4], "LOD2 ({}) < LOD4 ({})", sizes[2], sizes[4]);
        assert!(sizes[4] >= sizes[5], "LOD4 ({}) < LOD5 ({})", sizes[4], sizes[5]);
    }

    // ── assign_lod tests ─────────────────────────────────────

    #[test]
    fn test_assign_lod_high_score() {
        assert_eq!(assign_lod(0.75, false), 0);
        assert_eq!(assign_lod(0.50, false), 0);
    }

    #[test]
    fn test_assign_lod_mid_score() {
        assert_eq!(assign_lod(0.49, false), 2);
        assert_eq!(assign_lod(0.35, false), 2);
    }

    #[test]
    fn test_assign_lod_low_score() {
        assert_eq!(assign_lod(0.34, false), 4);
        assert_eq!(assign_lod(0.20, false), 4);
    }

    #[test]
    fn test_assign_lod_very_low() {
        assert_eq!(assign_lod(0.19, false), 5);
        assert_eq!(assign_lod(0.00, false), 5);
    }

    #[test]
    fn test_assign_lod_trace_expanded() {
        assert_eq!(assign_lod(0.10, true), 4);
        assert_eq!(assign_lod(0.80, true), 4);
    }

    #[test]
    fn test_lod_result_compression_ratio() {
        let r = LODResult {
            content: "abc".to_string(),
            lod: 2,
            input_chars: 300,
            output_chars: 100,
            fallback: false,
            error: None,
        };
        assert!((r.compression_ratio() - 3.0).abs() < 0.01);
    }

    #[test]
    fn test_lod_result_no_zero_division() {
        let r = LODResult {
            content: String::new(),
            lod: 5,
            input_chars: 500,
            output_chars: 0,
            fallback: false,
            error: None,
        };
        assert!(r.compression_ratio() > 0.0);
    }
}
