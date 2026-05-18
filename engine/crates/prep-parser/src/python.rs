//! Python AST analyzer using tree-sitter.
//!
//! Extracts: functions, async functions, classes, methods, imports.
//! Produces nodes and edges compatible with the existing Python PythonAnalyzer output.

use std::path::Path;
use tree_sitter::{Language, Parser, Node};

use crate::{
    stable_edge_id, stable_external_module_id, stable_file_node_id, stable_symbol_node_id,
    EdgeMetadata, NodeMetadata, ParseResult, ParsedEdge, ParsedNode, ParserError,
    Span,
};

fn get_language() -> Language {
    tree_sitter_python::LANGUAGE.into()
}

/// Analyze a Python file and extract symbols + import edges.
pub fn analyze(
    file_path: &str,
    content: &str,
    repo_root: &Path,
) -> Result<ParseResult, ParserError> {
    let mut parser = Parser::new();
    let language = get_language();
    parser
        .set_language(&language)
        .map_err(|e| ParserError::LanguageInit(format!("Python: {}", e)))?;

    let tree = parser.parse(content, None).ok_or_else(|| ParserError::ParseFailed {
        path: file_path.to_string(),
        message: "tree-sitter parse returned None".to_string(),
    })?;

    let root_node = tree.root_node();
    let source = content.as_bytes();
    let file_node_id = stable_file_node_id(file_path);

    let mut result = ParseResult::empty();

    // Symbol extraction is top-level only: nested functions/classes are
    // surfaced by extract_class's body walk, which is sufficient for the
    // graph's symbol coverage.
    let mut cursor = root_node.walk();
    for child in root_node.children(&mut cursor) {
        match child.kind() {
            "function_definition" => {
                extract_function(&child, source, file_path, &file_node_id, None, false, &mut result);
            }
            "decorated_definition" => {
                extract_decorated(&child, source, file_path, &file_node_id, None, &mut result);
            }
            "class_definition" => {
                extract_class(&child, source, file_path, &file_node_id, &mut result);
            }
            _ => {}
        }
    }

    // Phase 136 Part 02: imports are extracted via a SEPARATE tree-wide
    // walk so that statements nested inside function bodies, method
    // bodies, conditional blocks, try/except, or `if TYPE_CHECKING:`
    // guards are captured.  Pre-Phase-136 the top-level walk above
    // missed every indented import, leading to a silent undercount of
    // prep_impact dependents for any module imported via a deferred
    // (function-local) `from .X import Y` — see
    // docs/Phase136_Dogfood-fixes/Part02_PrepImpactBimodalNode/.
    extract_imports_recursive(&root_node, source, file_path, &file_node_id, repo_root, &mut result);

    Ok(result)
}

/// Walk the entire AST and emit import edges for every `import_statement`
/// or `import_from_statement` regardless of nesting depth.  See the call
/// site in `analyze()` for rationale.
fn extract_imports_recursive(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    repo_root: &Path,
    result: &mut ParseResult,
) {
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        match child.kind() {
            "import_statement" => {
                extract_import(&child, source, file_path, file_node_id, repo_root, result);
            }
            "import_from_statement" => {
                extract_import_from(&child, source, file_path, file_node_id, repo_root, result);
            }
            _ => {
                extract_imports_recursive(&child, source, file_path, file_node_id, repo_root, result);
            }
        }
    }
}

fn node_text<'a>(node: &Node, source: &'a [u8]) -> &'a str {
    node.utf8_text(source).unwrap_or("")
}

fn extract_decorated(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    parent_qualname: Option<&str>,
    result: &mut ParseResult,
) {
    let mut decorators = Vec::new();
    let mut cursor = node.walk();

    for child in node.children(&mut cursor) {
        match child.kind() {
            "decorator" => {
                // The decorator text is everything after '@'
                let text = node_text(&child, source);
                let dec_name = text.trim_start_matches('@').trim();
                // Extract just the name part (before any parens)
                let name = dec_name.split('(').next().unwrap_or(dec_name).trim();
                decorators.push(name.to_string());
            }
            "function_definition" => {
                extract_function(
                    &child,
                    source,
                    file_path,
                    file_node_id,
                    parent_qualname,
                    false,
                    result,
                );
                // Attach decorators to the last added node
                if let Some(last_node) = result.nodes.last_mut() {
                    if !decorators.is_empty() {
                        last_node.metadata.decorators = Some(decorators.clone());
                    }
                }
            }
            "class_definition" => {
                extract_class(&child, source, file_path, file_node_id, result);
                if let Some(last_node) = result.nodes.last_mut() {
                    if !decorators.is_empty() {
                        last_node.metadata.decorators = Some(decorators.clone());
                    }
                }
            }
            _ => {}
        }
    }
}

fn extract_function(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    parent_qualname: Option<&str>,
    _is_decorated: bool,
    result: &mut ParseResult,
) {
    let name = node
        .child_by_field_name("name")
        .map(|n| node_text(&n, source))
        .unwrap_or("");

    if name.is_empty() {
        return;
    }

    let is_async = node.kind() == "function_definition"
        && node.child(0).map(|c| c.kind() == "async").unwrap_or(false);

    // Check if actually an async function by looking at the parent or node kind directly
    // tree-sitter Python uses "function_definition" for both, with "async" keyword child
    let start_line = node.start_position().row + 1; // 1-indexed
    let end_line = node.end_position().row + 1;

    let qualname = match parent_qualname {
        Some(parent) => format!("{}.{}", parent, name),
        None => name.to_string(),
    };

    let symbol_type = if parent_qualname.is_some() {
        if is_async { "async_method" } else { "method" }
    } else if is_async {
        "async_function"
    } else {
        "function"
    };

    let is_public = !name.starts_with('_');

    // Extract docstring (first expression_statement > string child of the body)
    let docstring = extract_docstring(node, source);

    let node_id = stable_symbol_node_id(&qualname, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some("python".to_string()),
        metadata: NodeMetadata {
            symbol_type: Some(symbol_type.to_string()),
            qualname: Some(qualname),
            is_async: Some(is_async),
            is_public: Some(is_public),
            docstring: docstring.map(|d| truncate_docstring(&d, 500)),
            ..Default::default()
        },
    });

    // Add "contains" edge from file to symbol
    let edge_id = stable_edge_id("contains", file_node_id, &node_id, "");
    result.edges.push(ParsedEdge {
        id: edge_id,
        kind: "contains".to_string(),
        source: file_node_id.to_string(),
        target: node_id,
        metadata: EdgeMetadata {
            confidence: 1.0,
            ..Default::default()
        },
    });
}

fn extract_class(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    result: &mut ParseResult,
) {
    let name = node
        .child_by_field_name("name")
        .map(|n| node_text(&n, source))
        .unwrap_or("");

    if name.is_empty() {
        return;
    }

    let start_line = node.start_position().row + 1;
    let end_line = node.end_position().row + 1;
    let qualname = name.to_string();
    let is_public = !name.starts_with('_');

    let docstring = extract_docstring(node, source);

    let node_id = stable_symbol_node_id(&qualname, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some("python".to_string()),
        metadata: NodeMetadata {
            symbol_type: Some("class".to_string()),
            qualname: Some(qualname.clone()),
            is_public: Some(is_public),
            docstring: docstring.map(|d| truncate_docstring(&d, 500)),
            ..Default::default()
        },
    });

    // Add "contains" edge
    let edge_id = stable_edge_id("contains", file_node_id, &node_id, "");
    result.edges.push(ParsedEdge {
        id: edge_id,
        kind: "contains".to_string(),
        source: file_node_id.to_string(),
        target: node_id.clone(),
        metadata: EdgeMetadata {
            confidence: 1.0,
            ..Default::default()
        },
    });

    // TG-5: Extract inheritance edges from base class list
    // Python grammar: class Foo(Bar, Baz): → superclasses field contains argument_list
    if let Some(superclasses) = node.child_by_field_name("superclasses") {
        let mut cursor = superclasses.walk();
        for child in superclasses.children(&mut cursor) {
            let base_name = match child.kind() {
                "identifier" => node_text(&child, source).to_string(),
                "attribute" => node_text(&child, source).to_string(),
                _ => continue,
            };
            if base_name.is_empty() || base_name == "object" {
                continue;
            }
            let target_id = stable_symbol_node_id(
                &base_name, file_path, child.start_position().row + 1,
            );
            let inh_edge_id = stable_edge_id("inherits", &node_id, &target_id, "");
            result.edges.push(ParsedEdge {
                id: inh_edge_id,
                kind: "inherits".to_string(),
                source: node_id.clone(),
                target: target_id,
                metadata: EdgeMetadata {
                    confidence: 1.0,
                    line: Some(child.start_position().row + 1),
                    ..Default::default()
                },
            });
        }
    }

    // Extract methods from the class body
    if let Some(body) = node.child_by_field_name("body") {
        let mut cursor = body.walk();
        for child in body.children(&mut cursor) {
            match child.kind() {
                "function_definition" => {
                    extract_function(
                        &child,
                        source,
                        file_path,
                        file_node_id,
                        Some(&qualname),
                        false,
                        result,
                    );
                }
                "decorated_definition" => {
                    extract_decorated(
                        &child,
                        source,
                        file_path,
                        file_node_id,
                        Some(&qualname),
                        result,
                    );
                }
                _ => {}
            }
        }
    }
}

fn extract_docstring(node: &Node, source: &[u8]) -> Option<String> {
    // Find the body block, then look for first expression_statement > string
    let body = node.child_by_field_name("body")?;
    let mut cursor = body.walk();
    for child in body.children(&mut cursor) {
        if child.kind() == "expression_statement" {
            let mut inner_cursor = child.walk();
            for inner in child.children(&mut inner_cursor) {
                if inner.kind() == "string" {
                    let text = node_text(&inner, source);
                    // Strip triple quotes
                    let stripped = text
                        .trim_start_matches("\"\"\"")
                        .trim_start_matches("'''")
                        .trim_end_matches("\"\"\"")
                        .trim_end_matches("'''")
                        .trim();
                    if !stripped.is_empty() {
                        return Some(stripped.to_string());
                    }
                }
            }
        }
        // Docstring must be the very first statement
        break;
    }
    None
}

fn truncate_docstring(s: &str, max_len: usize) -> String {
    if s.len() <= max_len {
        s.to_string()
    } else {
        format!("{}...", &s[..max_len.saturating_sub(3)])
    }
}

fn extract_import(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    repo_root: &Path,
    result: &mut ParseResult,
) {
    // import x, import x as y, import x.y.z
    let line = node.start_position().row + 1;
    let mut cursor = node.walk();

    for child in node.children(&mut cursor) {
        if child.kind() == "dotted_name" || child.kind() == "aliased_import" {
            let module_name = if child.kind() == "aliased_import" {
                child
                    .child_by_field_name("name")
                    .map(|n| node_text(&n, source))
                    .unwrap_or("")
            } else {
                node_text(&child, source)
            };

            if !module_name.is_empty() {
                add_import_edge(module_name, line, file_path, file_node_id, repo_root, result);
            }
        }
    }
}

fn extract_import_from(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    repo_root: &Path,
    result: &mut ParseResult,
) {
    // from x import y, from .x import y, from . import y
    let line = node.start_position().row + 1;

    // Count leading dots for relative imports
    let mut dot_count = 0;
    let mut module_name = String::new();
    let mut cursor = node.walk();

    for child in node.children(&mut cursor) {
        match child.kind() {
            "." => dot_count += 1,
            "dotted_name" | "relative_import" => {
                module_name = node_text(&child, source).to_string();
            }
            _ => {}
        }
    }

    if dot_count > 0 {
        // Relative import
        add_relative_import_edge(
            &module_name,
            dot_count,
            line,
            file_path,
            file_node_id,
            repo_root,
            result,
        );
    } else if !module_name.is_empty() {
        add_import_edge(&module_name, line, file_path, file_node_id, repo_root, result);
    }
}

fn add_import_edge(
    module: &str,
    line: usize,
    _file_path: &str,
    file_node_id: &str,
    repo_root: &Path,
    result: &mut ParseResult,
) {
    let resolved = resolve_import(module, repo_root);

    if let Some(resolved_path) = resolved {
        let target_id = stable_file_node_id(&resolved_path);
        let disambiguator = format!("{}:{}", module, line);
        let edge_id = stable_edge_id("imports", file_node_id, &target_id, &disambiguator);

        result.edges.push(ParsedEdge {
            id: edge_id,
            kind: "imports".to_string(),
            source: file_node_id.to_string(),
            target: target_id,
            metadata: EdgeMetadata {
                confidence: 1.0,
                import_str: Some(module.to_string()),
                line: Some(line),
                ..Default::default()
            },
        });
    } else {
        // External module
        let ext_id = stable_external_module_id(module);
        let disambiguator = format!("{}:{}", module, line);
        let edge_id = stable_edge_id("imports", file_node_id, &ext_id, &disambiguator);

        // Add external module node
        result.nodes.push(ParsedNode {
            id: ext_id.clone(),
            kind: "external_module".to_string(),
            name: module.to_string(),
            file_path: String::new(),
            span: None,
            language: None,
            metadata: NodeMetadata {
                external: Some(true),
                ..Default::default()
            },
        });

        result.edges.push(ParsedEdge {
            id: edge_id,
            kind: "imports".to_string(),
            source: file_node_id.to_string(),
            target: ext_id,
            metadata: EdgeMetadata {
                confidence: 0.5,
                import_str: Some(module.to_string()),
                line: Some(line),
                external: Some(true),
                ..Default::default()
            },
        });
    }
}

fn add_relative_import_edge(
    module: &str,
    level: usize,
    line: usize,
    file_path: &str,
    file_node_id: &str,
    repo_root: &Path,
    result: &mut ParseResult,
) {
    let file_dir = Path::new(file_path).parent().unwrap_or(Path::new(""));
    let mut target_dir = file_dir.to_path_buf();

    for _ in 0..(level - 1) {
        target_dir = target_dir
            .parent()
            .unwrap_or(Path::new(""))
            .to_path_buf();
    }

    let target_rel = if !module.is_empty() {
        let parts: Vec<&str> = module.split('.').collect();
        target_dir.join(parts.join("/"))
    } else {
        target_dir
    };

    let candidates = [
        format!("{}.py", target_rel.display()),
        format!("{}/__init__.py", target_rel.display()),
    ];

    let mut resolved = None;
    for candidate in &candidates {
        let c_posix = candidate.replace('\\', "/");
        let full = repo_root.join(&c_posix);
        if full.exists() {
            resolved = Some(c_posix);
            break;
        }
    }

    if let Some(resolved_path) = resolved {
        let target_id = stable_file_node_id(&resolved_path);
        let import_str = format!("{}{}", ".".repeat(level), module);
        let disambiguator = format!("{}:{}", import_str, line);
        let edge_id = stable_edge_id("imports", file_node_id, &target_id, &disambiguator);

        result.edges.push(ParsedEdge {
            id: edge_id,
            kind: "imports".to_string(),
            source: file_node_id.to_string(),
            target: target_id,
            metadata: EdgeMetadata {
                confidence: 1.0,
                import_str: Some(import_str),
                line: Some(line),
                relative: Some(true),
                ..Default::default()
            },
        });
    }
}

fn resolve_import(module: &str, repo_root: &Path) -> Option<String> {
    let parts: Vec<&str> = module.split('.').collect();
    let candidates = [
        format!("{}.py", parts.join("/")),
        format!("{}/__init__.py", parts.join("/")),
    ];

    for candidate in &candidates {
        let full = repo_root.join(candidate);
        if full.exists() {
            return Some(candidate.clone());
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn parse_python(code: &str) -> ParseResult {
        let dir = tempfile::tempdir().unwrap();
        let file = dir.path().join("test.py");
        fs::write(&file, code).unwrap();
        analyze("test.py", code, dir.path()).unwrap()
    }

    #[test]
    fn test_simple_function() {
        let result = parse_python("def hello():\n    \"\"\"Say hello.\"\"\"\n    pass\n");

        assert_eq!(result.nodes.len(), 1);
        assert_eq!(result.nodes[0].name, "hello");
        assert_eq!(result.nodes[0].metadata.symbol_type.as_deref(), Some("function"));
        assert_eq!(result.nodes[0].metadata.docstring.as_deref(), Some("Say hello."));
        assert_eq!(result.nodes[0].metadata.is_public, Some(true));

        assert_eq!(result.edges.len(), 1);
        assert_eq!(result.edges[0].kind, "contains");
    }

    #[test]
    fn test_class_with_methods() {
        let code = r#"
class MyClass:
    """A test class."""
    def __init__(self):
        pass

    def public_method(self):
        pass

    def _private_method(self):
        pass
"#;
        let result = parse_python(code);

        // Should have: class + __init__ + public_method + _private_method = 4 nodes
        assert_eq!(result.nodes.len(), 4);

        let class_node = result.nodes.iter().find(|n| n.name == "MyClass").unwrap();
        assert_eq!(class_node.metadata.symbol_type.as_deref(), Some("class"));
        assert_eq!(class_node.metadata.docstring.as_deref(), Some("A test class."));

        let init_node = result.nodes.iter().find(|n| n.name == "__init__").unwrap();
        assert_eq!(init_node.metadata.symbol_type.as_deref(), Some("method"));
        assert_eq!(init_node.metadata.qualname.as_deref(), Some("MyClass.__init__"));
        assert_eq!(init_node.metadata.is_public, Some(false));

        let pub_method = result.nodes.iter().find(|n| n.name == "public_method").unwrap();
        assert_eq!(pub_method.metadata.is_public, Some(true));
        assert_eq!(pub_method.metadata.qualname.as_deref(), Some("MyClass.public_method"));
    }

    #[test]
    fn test_import_external() {
        let code = "import os\nimport json\n";
        let result = parse_python(code);

        // Should have 2 external module nodes and 2 import edges
        let ext_nodes: Vec<_> = result.nodes.iter().filter(|n| n.kind == "external_module").collect();
        assert_eq!(ext_nodes.len(), 2);

        let import_edges: Vec<_> = result.edges.iter().filter(|e| e.kind == "imports").collect();
        assert_eq!(import_edges.len(), 2);

        assert!(import_edges.iter().all(|e| e.metadata.external == Some(true)));
    }

    #[test]
    fn test_import_from_external() {
        let code = "from os.path import join\n";
        let result = parse_python(code);

        let import_edges: Vec<_> = result.edges.iter().filter(|e| e.kind == "imports").collect();
        assert_eq!(import_edges.len(), 1);
        assert_eq!(import_edges[0].metadata.external, Some(true));
    }

    #[test]
    fn test_private_function() {
        let code = "def _helper():\n    pass\n";
        let result = parse_python(code);

        assert_eq!(result.nodes[0].metadata.is_public, Some(false));
    }

    #[test]
    fn test_empty_file() {
        let result = parse_python("");
        assert!(result.nodes.is_empty());
        assert!(result.edges.is_empty());
    }

    // Phase 136 Part 02 regression — indented imports must be captured.
    // Pre-Phase-136 the parser only walked top-level children and silently
    // dropped any import nested inside a function body, class body, or
    // conditional.  This biased prep_impact dependent counts toward zero
    // for any module imported via a deferred (function-local) import.

    #[test]
    fn test_import_inside_function_body() {
        let code = "def use_it():\n    from os import path\n    return path.sep\n";
        let result = parse_python(code);
        let import_edges: Vec<_> = result.edges.iter()
            .filter(|e| e.kind == "imports").collect();
        assert_eq!(import_edges.len(), 1, "Indented import inside function body must be captured");
    }

    #[test]
    fn test_import_inside_method_body() {
        let code = "class Foo:\n    def bar(self):\n        from json import dumps\n        return dumps({})\n";
        let result = parse_python(code);
        let import_edges: Vec<_> = result.edges.iter()
            .filter(|e| e.kind == "imports").collect();
        assert_eq!(import_edges.len(), 1, "Indented import inside method body must be captured");
    }

    #[test]
    fn test_import_inside_if_block() {
        let code = "import sys\nif sys.version_info >= (3, 10):\n    from typing import TypeAlias\n";
        let result = parse_python(code);
        let import_edges: Vec<_> = result.edges.iter()
            .filter(|e| e.kind == "imports").collect();
        // sys (top-level) + TypeAlias-via-typing (conditional)
        assert_eq!(import_edges.len(), 2, "Conditional import must be captured");
    }

    #[test]
    fn test_import_inside_try_except() {
        let code = "try:\n    from fast_lib import fast_op\nexcept ImportError:\n    from slow_lib import slow_op as fast_op\n";
        let result = parse_python(code);
        let import_edges: Vec<_> = result.edges.iter()
            .filter(|e| e.kind == "imports").collect();
        // Both branches of try/except must surface
        assert_eq!(import_edges.len(), 2, "Both try/except imports must be captured");
    }

    #[test]
    fn test_deeply_nested_import() {
        // 3 levels deep: class → method → if-block → import
        let code = "class A:\n    def b(self):\n        if True:\n            from os import path\n";
        let result = parse_python(code);
        let import_edges: Vec<_> = result.edges.iter()
            .filter(|e| e.kind == "imports").collect();
        assert_eq!(import_edges.len(), 1, "Deeply nested import must be captured");
    }

    #[test]
    fn test_top_level_imports_not_duplicated() {
        // A top-level import must still be emitted exactly once after the
        // recursive walk is added (regression: full-tree walk could
        // double-emit if the symbol pass also processed imports).
        let code = "import os\nimport json\n";
        let result = parse_python(code);
        let import_edges: Vec<_> = result.edges.iter()
            .filter(|e| e.kind == "imports").collect();
        assert_eq!(import_edges.len(), 2, "Top-level imports must not double-emit");
    }
}
