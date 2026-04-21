//! Go AST analyzer using tree-sitter.
//!
//! Extracts: functions, methods, structs, interfaces, imports.

use tree_sitter::{Language, Parser, Node};

use crate::{
    stable_edge_id, stable_external_module_id, stable_file_node_id, stable_symbol_node_id,
    EdgeMetadata, NodeMetadata, ParseResult, ParsedEdge, ParsedNode, ParserError, Span,
};

fn get_language() -> Language {
    tree_sitter_go::LANGUAGE.into()
}

/// Analyze a Go file.
pub fn analyze(file_path: &str, content: &str) -> Result<ParseResult, ParserError> {
    let mut parser = Parser::new();
    let lang = get_language();
    parser
        .set_language(&lang)
        .map_err(|e| ParserError::LanguageInit(format!("Go: {}", e)))?;

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
            "function_declaration" => {
                extract_function(&child, source, file_path, &file_node_id, &mut result);
            }
            "method_declaration" => {
                extract_method(&child, source, file_path, &file_node_id, &mut result);
            }
            "type_declaration" => {
                extract_type_decl(&child, source, file_path, &file_node_id, &mut result);
            }
            "import_declaration" => {
                extract_imports(&child, source, file_path, &file_node_id, &mut result);
            }
            _ => {}
        }
    }

    Ok(result)
}

fn node_text<'a>(node: &Node, source: &'a [u8]) -> &'a str {
    node.utf8_text(source).unwrap_or("")
}

fn extract_function(
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
    let is_public = name.chars().next().map(|c| c.is_uppercase()).unwrap_or(false);

    let node_id = stable_symbol_node_id(name, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some("go".to_string()),
        metadata: NodeMetadata {
            symbol_type: Some("function".to_string()),
            qualname: Some(name.to_string()),
            is_public: Some(is_public),
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

fn extract_method(
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

    // Extract receiver type for qualname
    let receiver = node
        .child_by_field_name("receiver")
        .and_then(|r| {
            // parameter_list > parameter_declaration > type
            for i in 0..r.child_count() {
                if let Some(ch) = r.child(i) {
                    if ch.kind() == "parameter_declaration" {
                        return Some(ch);
                    }
                }
            }
            None
        })
        .and_then(|pd| pd.child_by_field_name("type"))
        .map(|t| {
            let text = node_text(&t, source);
            text.trim_start_matches('*').to_string()
        })
        .unwrap_or_default();

    if name.is_empty() {
        return;
    }

    let start_line = node.start_position().row + 1;
    let end_line = node.end_position().row + 1;
    let is_public = name.chars().next().map(|c| c.is_uppercase()).unwrap_or(false);

    let qualname = if receiver.is_empty() {
        name.to_string()
    } else {
        format!("{}.{}", receiver, name)
    };

    let node_id = stable_symbol_node_id(&qualname, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some("go".to_string()),
        metadata: NodeMetadata {
            symbol_type: Some("method".to_string()),
            qualname: Some(qualname),
            is_public: Some(is_public),
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

fn extract_type_decl(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    result: &mut ParseResult,
) {
    // type_declaration contains type_spec children
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        if child.kind() == "type_spec" {
            let name = child
                .child_by_field_name("name")
                .map(|n| node_text(&n, source))
                .unwrap_or("");

            if name.is_empty() {
                continue;
            }

            let type_node = child.child_by_field_name("type");
            let symbol_type = type_node
                .map(|t| match t.kind() {
                    "struct_type" => "struct",
                    "interface_type" => "interface",
                    _ => "type_alias",
                })
                .unwrap_or("type_alias");

            let start_line = child.start_position().row + 1;
            let end_line = child.end_position().row + 1;
            let is_public = name.chars().next().map(|c| c.is_uppercase()).unwrap_or(false);

            let node_id = stable_symbol_node_id(name, file_path, start_line);

            result.nodes.push(ParsedNode {
                id: node_id.clone(),
                kind: "symbol".to_string(),
                name: name.to_string(),
                file_path: file_path.to_string(),
                span: Some(Span { start_line, end_line }),
                language: Some("go".to_string()),
                metadata: NodeMetadata {
                    symbol_type: Some(symbol_type.to_string()),
                    qualname: Some(name.to_string()),
                    is_public: Some(is_public),
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
    }
}

fn extract_imports(
    node: &Node,
    source: &[u8],
    _file_path: &str,
    file_node_id: &str,
    result: &mut ParseResult,
) {
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        let import_path = match child.kind() {
            "import_spec" => child
                .child_by_field_name("path")
                .map(|n| node_text(&n, source).trim_matches('"').to_string()),
            "interpreted_string_literal" => {
                Some(node_text(&child, source).trim_matches('"').to_string())
            }
            _ => None,
        };

        if let Some(module) = import_path {
            if module.is_empty() {
                continue;
            }

            let line = child.start_position().row + 1;
            let ext_id = stable_external_module_id(&module);
            let disambiguator = format!("{}:{}", module, line);
            let edge_id = stable_edge_id("imports", file_node_id, &ext_id, &disambiguator);

            result.nodes.push(ParsedNode {
                id: ext_id.clone(),
                kind: "external_module".to_string(),
                name: module.clone(),
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
                    import_str: Some(module),
                    line: Some(line),
                    external: Some(true),
                    ..Default::default()
                },
            });
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_go(code: &str) -> ParseResult {
        analyze("main.go", code).unwrap()
    }

    #[test]
    fn test_go_function() {
        let result = parse_go("package main\n\nfunc Hello() {}\n");
        let funcs: Vec<_> = result.nodes.iter().filter(|n| n.kind == "symbol").collect();
        assert_eq!(funcs.len(), 1);
        assert_eq!(funcs[0].name, "Hello");
        assert_eq!(funcs[0].metadata.symbol_type.as_deref(), Some("function"));
        assert_eq!(funcs[0].metadata.is_public, Some(true));
    }

    #[test]
    fn test_go_private_function() {
        let result = parse_go("package main\n\nfunc helper() {}\n");
        assert_eq!(result.nodes[0].metadata.is_public, Some(false));
    }

    #[test]
    fn test_go_struct() {
        let result = parse_go("package main\n\ntype Server struct {\n\tPort int\n}\n");
        assert_eq!(result.nodes[0].name, "Server");
        assert_eq!(result.nodes[0].metadata.symbol_type.as_deref(), Some("struct"));
    }

    #[test]
    fn test_go_interface() {
        let result = parse_go("package main\n\ntype Reader interface {\n\tRead() error\n}\n");
        assert_eq!(result.nodes[0].name, "Reader");
        assert_eq!(result.nodes[0].metadata.symbol_type.as_deref(), Some("interface"));
    }
}
