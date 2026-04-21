//! TypeScript/JavaScript AST analyzer using tree-sitter.
//!
//! Extracts: functions, classes, interfaces, type aliases, imports/exports.

use tree_sitter::{Language, Parser, Node};

use crate::{
    stable_edge_id, stable_external_module_id, stable_file_node_id, stable_symbol_node_id,
    EdgeMetadata, NodeMetadata, ParseResult, ParsedEdge, ParsedNode, ParserError,
    Span,
};

fn get_ts_language() -> Language {
    tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into()
}

fn get_js_language() -> Language {
    tree_sitter_javascript::LANGUAGE.into()
}

/// Analyze a TypeScript or JavaScript file.
pub fn analyze(
    file_path: &str,
    content: &str,
    language: &str,
) -> Result<ParseResult, ParserError> {
    let mut parser = Parser::new();
    let lang = if language == "typescript" || file_path.ends_with(".ts") || file_path.ends_with(".tsx") {
        get_ts_language()
    } else {
        get_js_language()
    };

    parser
        .set_language(&lang)
        .map_err(|e| ParserError::LanguageInit(format!("TS/JS: {}", e)))?;

    let tree = parser.parse(content, None).ok_or_else(|| ParserError::ParseFailed {
        path: file_path.to_string(),
        message: "tree-sitter parse returned None".to_string(),
    })?;

    let root = tree.root_node();
    let source = content.as_bytes();
    let file_node_id = stable_file_node_id(file_path);
    let lang_str = language.to_string();

    let mut result = ParseResult::empty();

    let mut cursor = root.walk();
    for child in root.children(&mut cursor) {
        extract_top_level(&child, source, file_path, &file_node_id, &lang_str, &mut result);
    }

    // TG-4: Second pass — extract intra-file call chains
    // Collect all symbol names defined in this file, then scan function bodies
    // for call expressions that reference those symbols.
    extract_call_edges(&root, source, file_path, &result.nodes, &mut result.edges);

    Ok(result)
}

fn node_text<'a>(node: &Node, source: &'a [u8]) -> &'a str {
    node.utf8_text(source).unwrap_or("")
}

fn extract_imported_names(node: &Node, source: &[u8]) -> Option<Vec<String>> {
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        if child.kind() != "import_clause" {
            continue;
        }

        let mut names: Vec<String> = Vec::new();
        let mut clause_cursor = child.walk();
        for ch in child.children(&mut clause_cursor) {
            match ch.kind() {
                "identifier" => names.push("default".to_string()),
                "namespace_import" => names.push("*".to_string()),
                "named_imports" => {
                    let mut named_cursor = ch.walk();
                    for spec in ch.children(&mut named_cursor) {
                        if spec.kind() != "import_specifier" {
                            continue;
                        }
                        let name = spec
                            .child_by_field_name("name")
                            .map(|n| node_text(&n, source))
                            .unwrap_or("");
                        if !name.is_empty() {
                            names.push(name.to_string());
                        }
                    }
                }
                _ => {}
            }
        }

        if names.is_empty() {
            return None;
        }

        let mut deduped: Vec<String> = Vec::new();
        for n in names {
            if !deduped.iter().any(|x| x == &n) {
                deduped.push(n);
            }
        }
        return Some(deduped);
    }

    None
}

fn extract_re_exported_names(node: &Node, source: &[u8]) -> Vec<String> {
    let mut names: Vec<String> = Vec::new();

    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        if child.kind() == "namespace_export" {
            let name = child
                .child_by_field_name("name")
                .or_else(|| child.child_by_field_name("identifier"))
                .or_else(|| child.child(0))
                .map(|n| node_text(&n, source))
                .unwrap_or("");
            if !name.is_empty() {
                names.push(name.to_string());
            }
            if !names.is_empty() {
                return names;
            }
        }
    }

    let mut stack: Vec<Node> = vec![*node];
    while let Some(cur) = stack.pop() {
        if cur.kind() == "export_specifier" {
            let exported = cur
                .child_by_field_name("alias")
                .or_else(|| cur.child_by_field_name("name"))
                .or_else(|| cur.child(0))
                .map(|n| node_text(&n, source))
                .unwrap_or("");
            if !exported.is_empty() {
                names.push(exported.to_string());
            }
            continue;
        }

        if cur.kind() == "*" {
            names.push("*".to_string());
            continue;
        }

        let mut c = cur.walk();
        for ch in cur.children(&mut c) {
            stack.push(ch);
        }
    }

    if names.is_empty() {
        names.push("*".to_string());
    }

    let mut deduped: Vec<String> = Vec::new();
    for n in names {
        if !deduped.iter().any(|x| x == &n) {
            deduped.push(n);
        }
    }
    deduped
}

fn extract_top_level(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    language: &str,
    result: &mut ParseResult,
) {
    match node.kind() {
        "function_declaration" | "generator_function_declaration" => {
            extract_function(node, source, file_path, file_node_id, language, None, result);
        }
        "class_declaration" => {
            extract_class(node, source, file_path, file_node_id, language, result);
        }
        "interface_declaration" => {
            extract_interface(node, source, file_path, file_node_id, language, result);
        }
        "type_alias_declaration" => {
            extract_type_alias(node, source, file_path, file_node_id, language, result);
        }
        "enum_declaration" => {
            extract_enum(node, source, file_path, file_node_id, language, result);
        }
        "import_statement" => {
            extract_import(node, source, file_path, file_node_id, result);
        }
        "export_statement" => {
            extract_export_from(node, source, file_node_id, result);

            let mut cursor = node.walk();
            for child in node.children(&mut cursor) {
                extract_top_level(&child, source, file_path, file_node_id, language, result);
            }
        }
        "lexical_declaration" => {
            // const/let/var with arrow functions or class expressions
            extract_lexical_functions(node, source, file_path, file_node_id, language, result);
        }
        _ => {}
    }
}

fn extract_export_from(
    node: &Node,
    source: &[u8],
    file_node_id: &str,
    result: &mut ParseResult,
) {
    let line = node.start_position().row + 1;
    let re_exported_names = extract_re_exported_names(node, source);

    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        if child.kind() == "string" {
            let raw = node_text(&child, source);
            let module = raw.trim_matches(|c| c == '\'' || c == '"');

            if !module.is_empty() {
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
                        re_exported_names: Some(re_exported_names.clone()),
                        line: Some(line),
                        external: Some(true),
                        ..Default::default()
                    },
                });
            }
        }
    }
}

fn extract_function(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    language: &str,
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

    let qualname = match parent_qualname {
        Some(parent) => format!("{}.{}", parent, name),
        None => name.to_string(),
    };

    let is_async = node.kind().contains("async") || {
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

    let symbol_type = if parent_qualname.is_some() {
        if is_async { "async_method" } else { "method" }
    } else if node.kind().contains("generator") {
        "generator_function"
    } else if is_async {
        "async_function"
    } else {
        "function"
    };

    let is_public = !name.starts_with('_');

    let node_id = stable_symbol_node_id(&qualname, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some(language.to_string()),
        metadata: NodeMetadata {
            symbol_type: Some(symbol_type.to_string()),
            qualname: Some(qualname),
            is_async: Some(is_async),
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

    let start_line = node.start_position().row + 1;
    let end_line = node.end_position().row + 1;
    let qualname = name.to_string();

    let node_id = stable_symbol_node_id(&qualname, file_path, start_line);

    result.nodes.push(ParsedNode {
        id: node_id.clone(),
        kind: "symbol".to_string(),
        name: name.to_string(),
        file_path: file_path.to_string(),
        span: Some(Span { start_line, end_line }),
        language: Some(language.to_string()),
        metadata: NodeMetadata {
            symbol_type: Some("class".to_string()),
            qualname: Some(qualname.clone()),
            is_public: Some(!name.starts_with('_')),
            ..Default::default()
        },
    });

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

    // TG-5: Extract inheritance (extends) and implementation (implements) edges
    {
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            let edge_kind = match child.kind() {
                "class_heritage" => {
                    // In tree-sitter-typescript, class_heritage contains
                    // extends_clause and implements_clause children
                    let mut hc = child.walk();
                    for hchild in child.children(&mut hc) {
                        let ek = match hchild.kind() {
                            "extends_clause" => "inherits",
                            "implements_clause" => "implements",
                            _ => continue,
                        };
                        // Extract type names from the clause
                        let mut tc = hchild.walk();
                        for tnode in hchild.children(&mut tc) {
                            if tnode.kind() == "type_identifier" || tnode.kind() == "identifier" {
                                let parent_name = node_text(&tnode, source);
                                if !parent_name.is_empty() {
                                    let target_id = stable_symbol_node_id(parent_name, file_path, tnode.start_position().row + 1);
                                    let inh_edge_id = stable_edge_id(ek, &node_id, &target_id, "");
                                    result.edges.push(ParsedEdge {
                                        id: inh_edge_id,
                                        kind: ek.to_string(),
                                        source: node_id.clone(),
                                        target: target_id,
                                        metadata: EdgeMetadata {
                                            confidence: 1.0,
                                            line: Some(tnode.start_position().row + 1),
                                            ..Default::default()
                                        },
                                    });
                                }
                            }
                        }
                        let _ = ek;
                    }
                    continue;
                }
                "extends_clause" => "inherits",
                "implements_clause" => "implements",
                _ => continue,
            };
            // Direct extends/implements clauses (JS grammar)
            let mut tc = child.walk();
            for tnode in child.children(&mut tc) {
                if tnode.kind() == "type_identifier" || tnode.kind() == "identifier" {
                    let parent_name = node_text(&tnode, source);
                    if !parent_name.is_empty() {
                        let target_id = stable_symbol_node_id(parent_name, file_path, tnode.start_position().row + 1);
                        let inh_edge_id = stable_edge_id(edge_kind, &node_id, &target_id, "");
                        result.edges.push(ParsedEdge {
                            id: inh_edge_id,
                            kind: edge_kind.to_string(),
                            source: node_id.clone(),
                            target: target_id,
                            metadata: EdgeMetadata {
                                confidence: 1.0,
                                line: Some(tnode.start_position().row + 1),
                                ..Default::default()
                            },
                        });
                    }
                }
            }
        }
    }

    // Extract methods from class body
    if let Some(body) = node.child_by_field_name("body") {
        let mut cursor = body.walk();
        for child in body.children(&mut cursor) {
            if child.kind() == "method_definition" {
                extract_function(&child, source, file_path, file_node_id, language, Some(&qualname), result);
            }
        }
    }
}

fn extract_interface(
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
            symbol_type: Some("interface".to_string()),
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
        metadata: EdgeMetadata {
            confidence: 1.0,
            ..Default::default()
        },
    });
}

fn extract_type_alias(
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
            symbol_type: Some("type_alias".to_string()),
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
        metadata: EdgeMetadata {
            confidence: 1.0,
            ..Default::default()
        },
    });
}

fn extract_enum(
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
            symbol_type: Some("enum".to_string()),
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
        metadata: EdgeMetadata {
            confidence: 1.0,
            ..Default::default()
        },
    });
}

fn extract_lexical_functions(
    node: &Node,
    source: &[u8],
    file_path: &str,
    file_node_id: &str,
    language: &str,
    result: &mut ParseResult,
) {
    // Handle: const foo = () => {}, const foo = function() {}
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        if child.kind() == "variable_declarator" {
            let name = child
                .child_by_field_name("name")
                .map(|n| node_text(&n, source))
                .unwrap_or("");

            let value = child.child_by_field_name("value");
            if let Some(val) = value {
                if val.kind() == "arrow_function" || val.kind() == "function" {
                    if !name.is_empty() {
                        let start_line = node.start_position().row + 1;
                        let end_line = node.end_position().row + 1;

                        let is_async = {
                            let mut found = false;
                            for i in 0..val.child_count() {
                                if let Some(ch) = val.child(i) {
                                    if node_text(&ch, source) == "async" {
                                        found = true;
                                        break;
                                    }
                                }
                            }
                            found
                        };

                        let symbol_type = if is_async { "async_function" } else { "function" };

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
                                is_async: Some(is_async),
                                is_public: Some(!name.starts_with('_')),
                                ..Default::default()
                            },
                        });

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
                }
            }
        }
    }
}

fn extract_import(
    node: &Node,
    source: &[u8],
    _file_path: &str,
    file_node_id: &str,
    result: &mut ParseResult,
) {
    let line = node.start_position().row + 1;
    let imported_names = extract_imported_names(node, source);

    // Find the source string (the import path)
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        if child.kind() == "string" {
            let raw = node_text(&child, source);
            let module = raw.trim_matches(|c| c == '\'' || c == '"');

            if !module.is_empty() {
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
                        imported_names: imported_names.clone(),
                        line: Some(line),
                        external: Some(true),
                        ..Default::default()
                    },
                });
            }
        }
    }
}

// ── TG-4: Intra-file call chain extraction ─────────────────────────

/// Extract `calls` edges between symbols defined in the same file.
///
/// Walks the AST looking for `call_expression` nodes inside function/method
/// bodies, then matches the callee name against known symbols in this file.
/// Only emits edges for calls to symbols defined in the same file (intra-file).
fn extract_call_edges(
    root: &Node,
    source: &[u8],
    file_path: &str,
    nodes: &[ParsedNode],
    edges: &mut Vec<ParsedEdge>,
) {
    use std::collections::{HashMap, HashSet};

    // Build lookup: symbol_name → node_id for symbols in this file
    let mut name_to_id: HashMap<&str, &str> = HashMap::new();
    // Also track qualified names: "Class.method" → node_id
    for n in nodes {
        if n.kind == "symbol" && n.file_path == file_path {
            name_to_id.insert(&n.name, &n.id);
            if let Some(ref qn) = n.metadata.qualname {
                if qn != &n.name {
                    name_to_id.insert(qn, &n.id);
                }
            }
        }
    }

    if name_to_id.len() < 2 {
        return; // Need at least 2 symbols for a call edge
    }

    // Build a set of (caller_id, callee_id) to avoid duplicates
    let mut seen: HashSet<(String, String)> = HashSet::new();

    // Walk function declarations/methods and scan their bodies for calls
    walk_for_calls(root, source, file_path, &name_to_id, None, edges, &mut seen);
}

/// Recursively walk AST to find function bodies and extract call expressions.
fn walk_for_calls<'a>(
    node: &Node,
    source: &[u8],
    file_path: &str,
    name_to_id: &std::collections::HashMap<&str, &str>,
    current_fn_id: Option<&str>,
    edges: &mut Vec<ParsedEdge>,
    seen: &mut std::collections::HashSet<(String, String)>,
) {
    match node.kind() {
        "function_declaration" | "generator_function_declaration" | "method_definition" => {
            // Determine this function's symbol ID
            let fn_name = node
                .child_by_field_name("name")
                .map(|n| node_text(&n, source))
                .unwrap_or("");
            if !fn_name.is_empty() {
                let start_line = node.start_position().row + 1;
                // Try to find this function's node ID in the lookup
                // For methods, try "Class.method" format
                let qualname = fn_name;
                let fn_id_str = format!("sym:{}@{}:{}", qualname, file_path, start_line);

                // Scan the body for call expressions
                if let Some(body) = node.child_by_field_name("body") {
                    scan_calls_in_body(&body, source, file_path, name_to_id, &fn_id_str, edges, seen);
                }
            }
            // Don't recurse further into nested functions from here
            return;
        }
        "arrow_function" => {
            // Arrow functions assigned to const — handled via lexical_declaration
            return;
        }
        _ => {}
    }

    // Recurse into children to find function declarations
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        walk_for_calls(&child, source, file_path, name_to_id, current_fn_id, edges, seen);
    }
}

/// Scan a function body for call_expression nodes and emit `calls` edges.
fn scan_calls_in_body(
    node: &Node,
    source: &[u8],
    file_path: &str,
    name_to_id: &std::collections::HashMap<&str, &str>,
    caller_id: &str,
    edges: &mut Vec<ParsedEdge>,
    seen: &mut std::collections::HashSet<(String, String)>,
) {
    if node.kind() == "call_expression" {
        // Extract the callee name
        if let Some(func_node) = node.child_by_field_name("function") {
            let callee_name = match func_node.kind() {
                "identifier" => node_text(&func_node, source),
                "member_expression" => {
                    // For this.method() or obj.method(), extract the method name
                    func_node.child_by_field_name("property")
                        .map(|p| node_text(&p, source))
                        .unwrap_or("")
                }
                _ => "",
            };

            if !callee_name.is_empty() {
                if let Some(&callee_id) = name_to_id.get(callee_name) {
                    // Don't create self-calls or duplicates
                    if callee_id != caller_id {
                        let pair = (caller_id.to_string(), callee_id.to_string());
                        if !seen.contains(&pair) {
                            seen.insert(pair);
                            let edge_id = stable_edge_id(
                                "calls", caller_id, callee_id,
                                &format!("{}", node.start_position().row + 1),
                            );
                            edges.push(ParsedEdge {
                                id: edge_id,
                                kind: "calls".to_string(),
                                source: caller_id.to_string(),
                                target: callee_id.to_string(),
                                metadata: EdgeMetadata {
                                    confidence: 0.9,
                                    line: Some(node.start_position().row + 1),
                                    ..Default::default()
                                },
                            });
                        }
                    }
                }
            }
        }
    }

    // Recurse into children (but skip nested function declarations)
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        match child.kind() {
            "function_declaration" | "arrow_function" | "function" => continue,
            _ => scan_calls_in_body(&child, source, file_path, name_to_id, caller_id, edges, seen),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_ts(code: &str) -> ParseResult {
        analyze("test.ts", code, "typescript").unwrap()
    }

    fn parse_js(code: &str) -> ParseResult {
        analyze("test.js", code, "javascript").unwrap()
    }

    #[test]
    fn test_ts_function() {
        let result = parse_ts("function hello(): void {}\n");
        assert_eq!(result.nodes.len(), 1);
        assert_eq!(result.nodes[0].name, "hello");
        assert_eq!(result.nodes[0].metadata.symbol_type.as_deref(), Some("function"));
    }

    #[test]
    fn test_ts_class() {
        let result = parse_ts("class MyComponent {\n  render() {}\n}\n");
        let class_node = result.nodes.iter().find(|n| n.name == "MyComponent").unwrap();
        assert_eq!(class_node.metadata.symbol_type.as_deref(), Some("class"));
    }

    #[test]
    fn test_ts_interface() {
        let result = parse_ts("interface Props {\n  name: string;\n}\n");
        assert_eq!(result.nodes.len(), 1);
        assert_eq!(result.nodes[0].name, "Props");
        assert_eq!(result.nodes[0].metadata.symbol_type.as_deref(), Some("interface"));
    }

    #[test]
    fn test_ts_import() {
        let result = parse_ts("import { foo } from './bar';\n");
        let import_edges: Vec<_> = result.edges.iter().filter(|e| e.kind == "imports").collect();
        assert_eq!(import_edges.len(), 1);
        assert_eq!(import_edges[0].metadata.import_str.as_deref(), Some("./bar"));
        let expected = vec!["foo".to_string()];
        assert_eq!(import_edges[0].metadata.imported_names.as_ref(), Some(&expected));
    }

    #[test]
    fn test_ts_re_export_from() {
        let result = parse_ts("export { foo } from './bar';\n");
        let import_edges: Vec<_> = result.edges.iter().filter(|e| e.kind == "imports").collect();
        assert_eq!(import_edges.len(), 1);
        assert_eq!(import_edges[0].metadata.import_str.as_deref(), Some("./bar"));
        let expected = vec!["foo".to_string()];
        assert_eq!(import_edges[0].metadata.re_exported_names.as_ref(), Some(&expected));
    }

    #[test]
    fn test_ts_export_star_from() {
        let result = parse_ts("export * from './bar';\n");
        let import_edges: Vec<_> = result.edges.iter().filter(|e| e.kind == "imports").collect();
        assert_eq!(import_edges.len(), 1);
        assert_eq!(import_edges[0].metadata.import_str.as_deref(), Some("./bar"));
        let expected = vec!["*".to_string()];
        assert_eq!(import_edges[0].metadata.re_exported_names.as_ref(), Some(&expected));
    }

    #[test]
    fn test_js_arrow_function() {
        let result = parse_js("const greet = () => {};\n");
        assert_eq!(result.nodes.len(), 1);
        assert_eq!(result.nodes[0].name, "greet");
        assert_eq!(result.nodes[0].metadata.symbol_type.as_deref(), Some("function"));
    }

    #[test]
    fn test_ts_enum() {
        let result = parse_ts("enum Direction {\n  Up,\n  Down,\n}\n");
        assert_eq!(result.nodes.len(), 1);
        assert_eq!(result.nodes[0].name, "Direction");
        assert_eq!(result.nodes[0].metadata.symbol_type.as_deref(), Some("enum"));
    }
}
