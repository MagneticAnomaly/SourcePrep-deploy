//! Java AST analyzer using tree-sitter.
//!
//! Extracts: classes, interfaces, methods, imports.

use tree_sitter::{Language, Parser, Node};

use crate::{
    stable_edge_id, stable_external_module_id, stable_file_node_id, stable_symbol_node_id,
    EdgeMetadata, NodeMetadata, ParseResult, ParsedEdge, ParsedNode, ParserError, Span,
};

fn get_language() -> Language {
    tree_sitter_java::LANGUAGE.into()
}

/// Analyze a Java file.
pub fn analyze(file_path: &str, content: &str) -> Result<ParseResult, ParserError> {
    let mut parser = Parser::new();
    let lang = get_language();
    parser
        .set_language(&lang)
        .map_err(|e| ParserError::LanguageInit(format!("Java: {}", e)))?;

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
            "class_declaration" => {
                extract_class(&child, source, file_path, &file_node_id, None, &mut result);
            }
            "interface_declaration" => {
                extract_interface(&child, source, file_path, &file_node_id, &mut result);
            }
            "enum_declaration" => {
                extract_simple_type(&child, source, file_path, &file_node_id, "enum", &mut result);
            }
            "import_declaration" => {
                extract_import(&child, source, file_path, &file_node_id, &mut result);
            }
            _ => {}
        }
    }

    Ok(result)
}

fn node_text<'a>(node: &Node, source: &'a [u8]) -> &'a str {
    node.utf8_text(source).unwrap_or("")
}

fn has_modifier(node: &Node, source: &[u8], modifier: &str) -> bool {
    for i in 0..node.child_count() {
        if let Some(ch) = node.child(i) {
            if ch.kind() == "modifiers" {
                for j in 0..ch.child_count() {
                    if let Some(m) = ch.child(j) {
                        if node_text(&m, source) == modifier {
                            return true;
                        }
                    }
                }
            }
        }
    }
    false
}

fn extract_class(
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
    let is_public = has_modifier(node, source, "public");

    let qualname = match parent_qualname {
        Some(parent) => format!("{}.{}", parent, name),
        None => name.to_string(),
    };

    let node_id = stable_symbol_node_id(&qualname, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some("java".to_string()),
        metadata: NodeMetadata {
            symbol_type: Some("class".to_string()),
            qualname: Some(qualname.clone()),
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

    // Extract methods from class body
    if let Some(body) = node.child_by_field_name("body") {
        let mut cursor = body.walk();
        for child in body.children(&mut cursor) {
            match child.kind() {
                "method_declaration" | "constructor_declaration" => {
                    extract_method(&child, source, file_path, file_node_id, &qualname, result);
                }
                "class_declaration" => {
                    extract_class(&child, source, file_path, file_node_id, Some(&qualname), result);
                }
                _ => {}
            }
        }
    }
}

fn extract_method(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    parent_qualname: &str,
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
    let is_public = has_modifier(node, source, "public");
    let qualname = format!("{}.{}", parent_qualname, name);

    let node_id = stable_symbol_node_id(&qualname, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some("java".to_string()),
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

fn extract_interface(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    result: &mut ParseResult,
) {
    extract_simple_type(node, source, file_path, file_node_id, "interface", result);
}

fn extract_simple_type(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    symbol_type: &str,
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
    let is_public = has_modifier(node, source, "public");

    let node_id = stable_symbol_node_id(name, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some("java".to_string()),
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

fn extract_import(
    node: &Node,
    source: &[u8],
    _file_path: &str,
    file_node_id: &str,
    result: &mut ParseResult,
) {
    let line = node.start_position().row + 1;
    let text = node_text(node, source);

    // Extract the import path from "import foo.bar.Baz;" or "import static ..."
    let module = text
        .strip_prefix("import ")
        .unwrap_or(text)
        .strip_prefix("static ")
        .unwrap_or(text.strip_prefix("import ").unwrap_or(text))
        .trim_end_matches(';')
        .trim();

    if module.is_empty() {
        return;
    }

    let ext_id = stable_external_module_id(module);
    let disambiguator = format!("{}:{}", module, line);
    let edge_id = stable_edge_id("imports", file_node_id, &ext_id, &disambiguator);

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

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_java(code: &str) -> ParseResult {
        analyze("Main.java", code).unwrap()
    }

    #[test]
    fn test_java_class() {
        let result = parse_java("public class Main {\n}\n");
        assert_eq!(result.nodes.len(), 1);
        assert_eq!(result.nodes[0].name, "Main");
        assert_eq!(result.nodes[0].metadata.symbol_type.as_deref(), Some("class"));
        assert_eq!(result.nodes[0].metadata.is_public, Some(true));
    }

    #[test]
    fn test_java_interface() {
        let result = parse_java("public interface Runnable {\n    void run();\n}\n");
        assert_eq!(result.nodes[0].name, "Runnable");
        assert_eq!(result.nodes[0].metadata.symbol_type.as_deref(), Some("interface"));
    }

    #[test]
    fn test_java_import() {
        let result = parse_java("import java.util.List;\n\npublic class Main {}\n");
        let imports: Vec<_> = result.edges.iter().filter(|e| e.kind == "imports").collect();
        assert_eq!(imports.len(), 1);
    }
}
