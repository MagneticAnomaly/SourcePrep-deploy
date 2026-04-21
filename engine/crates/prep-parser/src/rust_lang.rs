//! Rust AST analyzer using tree-sitter.
//!
//! Extracts: functions, structs, enums, traits, impls, use statements.

use tree_sitter::{Language, Parser, Node};

use crate::{
    stable_edge_id, stable_external_module_id, stable_file_node_id, stable_symbol_node_id,
    EdgeMetadata, NodeMetadata, ParseResult, ParsedEdge, ParsedNode, ParserError, Span,
};

fn get_language() -> Language {
    tree_sitter_rust::LANGUAGE.into()
}

/// Analyze a Rust file.
pub fn analyze(file_path: &str, content: &str) -> Result<ParseResult, ParserError> {
    let mut parser = Parser::new();
    let lang = get_language();
    parser
        .set_language(&lang)
        .map_err(|e| ParserError::LanguageInit(format!("Rust: {}", e)))?;

    let tree = parser.parse(content, None).ok_or_else(|| ParserError::ParseFailed {
        path: file_path.to_string(),
        message: "tree-sitter parse returned None".to_string(),
    })?;

    let root = tree.root_node();
    let source = content.as_bytes();
    let file_node_id = stable_file_node_id(file_path);

    let mut result = ParseResult::empty();

    let mut cursor = root.walk();
    for child in root.children(&mut cursor) {
        match child.kind() {
            "function_item" => {
                extract_function(&child, source, file_path, &file_node_id, None, &mut result);
            }
            "struct_item" => {
                extract_struct(&child, source, file_path, &file_node_id, &mut result);
            }
            "enum_item" => {
                extract_enum(&child, source, file_path, &file_node_id, &mut result);
            }
            "trait_item" => {
                extract_trait(&child, source, file_path, &file_node_id, &mut result);
            }
            "impl_item" => {
                extract_impl(&child, source, file_path, &file_node_id, &mut result);
            }
            "use_declaration" => {
                extract_use(&child, source, file_path, &file_node_id, &mut result);
            }
            _ => {}
        }
    }

    Ok(result)
}

fn node_text<'a>(node: &Node, source: &'a [u8]) -> &'a str {
    node.utf8_text(source).unwrap_or("")
}

fn is_pub(node: &Node, _source: &[u8]) -> bool {
    for i in 0..node.child_count() {
        if let Some(ch) = node.child(i) {
            if ch.kind() == "visibility_modifier" {
                return true;
            }
        }
    }
    false
}

fn extract_function(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    parent_qualname: Option<&str>,
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
    let public = is_pub(node, source);

    let qualname = match parent_qualname {
        Some(parent) => format!("{}::{}", parent, name),
        None => name.to_string(),
    };

    let symbol_type = if parent_qualname.is_some() { "method" } else { "function" };

    // Check for async
    let is_async = {
        let mut found = false;
        for i in 0..node.child_count() {
            if let Some(ch) = node.child(i) {
                if node_text(&ch, source) == "async" {
                    found = true;
                    break;
                }
            }
        }
        found
    };

    let node_id = stable_symbol_node_id(&qualname, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some("rust".to_string()),
        metadata: NodeMetadata {
            symbol_type: Some(symbol_type.to_string()),
            qualname: Some(qualname),
            is_async: Some(is_async),
            is_public: Some(public),
            ..Default::default()
        },
    });

    let edge_id = stable_edge_id("contains", file_node_id, &node_id, "");
    result.edges.push(ParsedEdge {
        id: edge_id,
        kind: "contains".to_string(),
        source: file_node_id.to_string(),
        target: node_id,
        metadata: EdgeMetadata { confidence: 1.0, ..Default::default() },
    });
}

fn extract_struct(
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
    let public = is_pub(node, source);

    let node_id = stable_symbol_node_id(name, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some("rust".to_string()),
        metadata: NodeMetadata {
            symbol_type: Some("struct".to_string()),
            qualname: Some(name.to_string()),
            is_public: Some(public),
            ..Default::default()
        },
    });

    let edge_id = stable_edge_id("contains", file_node_id, &node_id, "");
    result.edges.push(ParsedEdge {
        id: edge_id,
        kind: "contains".to_string(),
        source: file_node_id.to_string(),
        target: node_id,
        metadata: EdgeMetadata { confidence: 1.0, ..Default::default() },
    });
}

fn extract_enum(
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
    let public = is_pub(node, source);

    let node_id = stable_symbol_node_id(name, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some("rust".to_string()),
        metadata: NodeMetadata {
            symbol_type: Some("enum".to_string()),
            qualname: Some(name.to_string()),
            is_public: Some(public),
            ..Default::default()
        },
    });

    let edge_id = stable_edge_id("contains", file_node_id, &node_id, "");
    result.edges.push(ParsedEdge {
        id: edge_id,
        kind: "contains".to_string(),
        source: file_node_id.to_string(),
        target: node_id,
        metadata: EdgeMetadata { confidence: 1.0, ..Default::default() },
    });
}

fn extract_trait(
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
    let public = is_pub(node, source);

    let node_id = stable_symbol_node_id(name, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some("rust".to_string()),
        metadata: NodeMetadata {
            symbol_type: Some("trait".to_string()),
            qualname: Some(name.to_string()),
            is_public: Some(public),
            ..Default::default()
        },
    });

    let edge_id = stable_edge_id("contains", file_node_id, &node_id, "");
    result.edges.push(ParsedEdge {
        id: edge_id,
        kind: "contains".to_string(),
        source: file_node_id.to_string(),
        target: node_id,
        metadata: EdgeMetadata { confidence: 1.0, ..Default::default() },
    });
}

fn extract_impl(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    result: &mut ParseResult,
) {
    // Get the type being implemented
    let type_name = node
        .child_by_field_name("type")
        .map(|n| node_text(&n, source).to_string())
        .unwrap_or_default();

    // Check for trait impl: impl Trait for Type
    let trait_name = node
        .child_by_field_name("trait")
        .map(|n| node_text(&n, source).to_string());

    let parent_qualname = if let Some(ref trait_n) = trait_name {
        format!("<{} as {}>", type_name, trait_n)
    } else {
        type_name.clone()
    };

    // Extract methods from the impl body
    if let Some(body) = node.child_by_field_name("body") {
        let mut cursor = body.walk();
        for child in body.children(&mut cursor) {
            if child.kind() == "function_item" {
                extract_function(&child, source, file_path, file_node_id, Some(&parent_qualname), result);
            }
        }
    }
}

fn extract_use(
    node: &Node,
    source: &[u8],
    _file_path: &str,
    file_node_id: &str,
    result: &mut ParseResult,
) {
    let line = node.start_position().row + 1;
    let text = node_text(node, source);

    // Extract the use path (simplified — just get the full text minus "use " and ";")
    let module = text
        .strip_prefix("use ")
        .or_else(|| text.strip_prefix("pub use "))
        .unwrap_or(text)
        .trim_end_matches(';')
        .trim();

    // Simplify: take the crate/module portion (before any { or ::*)
    let base_module = module
        .split('{')
        .next()
        .unwrap_or(module)
        .trim_end_matches("::")
        .trim();

    if base_module.is_empty() || base_module == "self" || base_module == "super" || base_module == "crate" {
        return;
    }

    let ext_id = stable_external_module_id(base_module);
    let disambiguator = format!("{}:{}", base_module, line);
    let edge_id = stable_edge_id("imports", file_node_id, &ext_id, &disambiguator);

    result.nodes.push(ParsedNode {
        id: ext_id.clone(),
        kind: "external_module".to_string(),
        name: base_module.to_string(),
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
            import_str: Some(base_module.to_string()),
            line: Some(line),
            external: Some(true),
            ..Default::default()
        },
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_rust(code: &str) -> ParseResult {
        analyze("src/lib.rs", code).unwrap()
    }

    #[test]
    fn test_rust_function() {
        let result = parse_rust("pub fn hello() {}\n");
        assert_eq!(result.nodes.len(), 1);
        assert_eq!(result.nodes[0].name, "hello");
        assert_eq!(result.nodes[0].metadata.symbol_type.as_deref(), Some("function"));
        assert_eq!(result.nodes[0].metadata.is_public, Some(true));
    }

    #[test]
    fn test_rust_private_fn() {
        let result = parse_rust("fn helper() {}\n");
        assert_eq!(result.nodes[0].metadata.is_public, Some(false));
    }

    #[test]
    fn test_rust_struct() {
        let result = parse_rust("pub struct Config {\n    pub port: u16,\n}\n");
        assert_eq!(result.nodes[0].name, "Config");
        assert_eq!(result.nodes[0].metadata.symbol_type.as_deref(), Some("struct"));
    }

    #[test]
    fn test_rust_enum() {
        let result = parse_rust("pub enum Direction {\n    Up,\n    Down,\n}\n");
        assert_eq!(result.nodes[0].name, "Direction");
        assert_eq!(result.nodes[0].metadata.symbol_type.as_deref(), Some("enum"));
    }

    #[test]
    fn test_rust_trait() {
        let result = parse_rust("pub trait Analyzer {\n    fn analyze(&self);\n}\n");
        assert_eq!(result.nodes[0].name, "Analyzer");
        assert_eq!(result.nodes[0].metadata.symbol_type.as_deref(), Some("trait"));
    }

    #[test]
    fn test_rust_impl() {
        let code = "struct Foo {}\nimpl Foo {\n    pub fn bar(&self) {}\n    fn baz(&self) {}\n}\n";
        let result = parse_rust(code);
        let methods: Vec<_> = result.nodes.iter().filter(|n| n.metadata.symbol_type.as_deref() == Some("method")).collect();
        assert_eq!(methods.len(), 2);
        assert_eq!(methods[0].metadata.qualname.as_deref(), Some("Foo::bar"));
        assert_eq!(methods[1].metadata.qualname.as_deref(), Some("Foo::baz"));
    }
}
