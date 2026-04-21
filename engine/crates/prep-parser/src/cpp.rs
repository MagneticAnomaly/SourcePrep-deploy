//! C/C++ AST analyzer using tree-sitter.
//!
//! Extracts: functions, structs, classes, includes.

use tree_sitter::{Language, Parser, Node};

use crate::{
    stable_edge_id, stable_external_module_id, stable_file_node_id, stable_symbol_node_id,
    EdgeMetadata, NodeMetadata, ParseResult, ParsedEdge, ParsedNode, ParserError, Span,
};

fn get_c_language() -> Language {
    tree_sitter_c::LANGUAGE.into()
}

fn get_cpp_language() -> Language {
    tree_sitter_cpp::LANGUAGE.into()
}

/// Analyze a C or C++ file.
pub fn analyze(
    file_path: &str,
    content: &str,
    language: &str,
) -> Result<ParseResult, ParserError> {
    let mut parser = Parser::new();
    let lang = if language == "cpp" {
        get_cpp_language()
    } else {
        get_c_language()
    };

    parser
        .set_language(&lang)
        .map_err(|e| ParserError::LanguageInit(format!("C/C++: {}", e)))?;

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
            "function_definition" => {
                extract_function(&child, source, file_path, &file_node_id, language, &mut result);
            }
            "declaration" => {
                // Could be a function declaration or struct/class forward decl
                extract_declaration(&child, source, file_path, &file_node_id, language, &mut result);
            }
            "struct_specifier" | "class_specifier" => {
                extract_composite(&child, source, file_path, &file_node_id, language, &mut result);
            }
            "preproc_include" => {
                extract_include(&child, source, file_path, &file_node_id, &mut result);
            }
            // C++ specific
            "class_definition" | "namespace_definition" => {
                extract_composite(&child, source, file_path, &file_node_id, language, &mut result);
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
    language: &str,
    result: &mut ParseResult,
) {
    // The declarator contains the function name
    let declarator = node.child_by_field_name("declarator");
    let name = declarator
        .and_then(|d| {
            // Could be function_declarator > identifier, or just identifier
            d.child_by_field_name("declarator")
                .or(Some(d))
        })
        .map(|n| node_text(&n, source))
        .unwrap_or("");

    // Strip pointer/reference chars and parens
    let name = name
        .trim_start_matches('*')
        .trim_start_matches('&')
        .split('(')
        .next()
        .unwrap_or("")
        .trim();

    if name.is_empty() || name.contains(' ') {
        return;
    }

    let start_line = node.start_position().row + 1;
    let end_line = node.end_position().row + 1;

    let node_id = stable_symbol_node_id(name, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some(language.to_string()),
        metadata: NodeMetadata {
            symbol_type: Some("function".to_string()),
            qualname: Some(name.to_string()),
            is_public: Some(true), // C/C++ doesn't have Python-style visibility
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

fn extract_declaration(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    language: &str,
    result: &mut ParseResult,
) {
    // Look for struct/class/enum type specifiers in declarations
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        match child.kind() {
            "struct_specifier" | "class_specifier" | "enum_specifier" => {
                extract_composite(&child, source, file_path, file_node_id, language, result);
            }
            _ => {}
        }
    }
}

fn extract_composite(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    language: &str,
    result: &mut ParseResult,
) {
    let name = node
        .child_by_field_name("name")
        .map(|n| node_text(&n, source))
        .unwrap_or("");

    if name.is_empty() {
        return;
    }

    let symbol_type = match node.kind() {
        "struct_specifier" => "struct",
        "class_specifier" | "class_definition" => "class",
        "enum_specifier" => "enum",
        "namespace_definition" => "namespace",
        _ => "type",
    };

    let start_line = node.start_position().row + 1;
    let end_line = node.end_position().row + 1;

    let node_id = stable_symbol_node_id(name, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some(language.to_string()),
        metadata: NodeMetadata {
            symbol_type: Some(symbol_type.to_string()),
            qualname: Some(name.to_string()),
            is_public: Some(true),
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

fn extract_include(
    node: &Node,
    source: &[u8],
    _file_path: &str,
    file_node_id: &str,
    result: &mut ParseResult,
) {
    let line = node.start_position().row + 1;

    // Find the path child (system_lib_string or string_literal)
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        if child.kind() == "system_lib_string" || child.kind() == "string_literal" {
            let raw = node_text(&child, source);
            let module = raw
                .trim_matches(|c| c == '"' || c == '<' || c == '>');

            if module.is_empty() {
                continue;
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
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_c(code: &str) -> ParseResult {
        analyze("main.c", code, "c").unwrap()
    }

    fn parse_cpp(code: &str) -> ParseResult {
        analyze("main.cpp", code, "cpp").unwrap()
    }

    #[test]
    fn test_c_function() {
        let result = parse_c("int main(int argc, char** argv) {\n    return 0;\n}\n");
        let funcs: Vec<_> = result.nodes.iter().filter(|n| n.kind == "symbol").collect();
        assert!(!funcs.is_empty());
    }

    #[test]
    fn test_c_include() {
        let result = parse_c("#include <stdio.h>\n#include \"mylib.h\"\n");
        let imports: Vec<_> = result.edges.iter().filter(|e| e.kind == "imports").collect();
        assert_eq!(imports.len(), 2);
    }

    #[test]
    fn test_cpp_class() {
        let code = "class MyClass {\npublic:\n    void doThing();\n};\n";
        let result = parse_cpp(code);
        let classes: Vec<_> = result.nodes.iter().filter(|n| n.metadata.symbol_type.as_deref() == Some("class")).collect();
        assert!(!classes.is_empty());
    }
}
