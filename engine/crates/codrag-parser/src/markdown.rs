//! Markdown document analyzer — pure regex, no tree-sitter dependency.
//!
//! Extracts: sections (headers), backtick file references, markdown links,
//! status markers. Produces section nodes with spans and importance-ranked
//! metadata for strategic snippet selection by the LLM augmenter.

use crate::{
    stable_edge_id, stable_file_node_id,
    EdgeMetadata, NodeMetadata, ParseResult, ParsedEdge, ParsedNode, Span,
};

/// Analyze a markdown file and extract structural information.
///
/// Unlike language analyzers, this does not use tree-sitter. It scans lines
/// with simple patterns to extract headers, file references, and links.
/// Returns section nodes with `contains` edges from the file node, plus
/// `references` and `links_to` edges for cross-file connections.
pub fn analyze(file_path: &str, content: &str) -> ParseResult {
    let file_node_id = stable_file_node_id(file_path);
    let file_dir = std::path::Path::new(file_path)
        .parent()
        .unwrap_or(std::path::Path::new(""));
    let lines: Vec<&str> = content.lines().collect();
    let line_count = lines.len();

    let mut result = ParseResult::empty();

    // ── Phase 1: Extract headers → section nodes ──────────────────────

    let mut sections: Vec<SectionInfo> = Vec::new();

    for (i, line) in lines.iter().enumerate() {
        if let Some(header) = parse_header(line) {
            sections.push(SectionInfo {
                name: header.text.clone(),
                depth: header.depth,
                start_line: i + 1, // 1-indexed
                end_line: 0,       // filled in below
                ref_count: 0,
                link_count: 0,
                status_markers: Vec::new(),
            });
        }
    }

    // Compute end_line for each section (ends where next same-or-higher-level header starts)
    for i in 0..sections.len() {
        let _current_depth = sections[i].depth;
        let start = sections[i].start_line;
        let end = if i + 1 < sections.len() {
            // End at the line before the next section starts
            sections[i + 1].start_line - 1
        } else {
            line_count
        };
        sections[i].end_line = end.max(start);
    }

    // ── Phase 2: Scan for backtick file references + markdown links ───

    let mut all_file_refs: Vec<FileRef> = Vec::new();
    let mut all_links: Vec<MdLink> = Vec::new();
    let mut all_status_markers: Vec<String> = Vec::new();

    for (i, line) in lines.iter().enumerate() {
        let line_num = i + 1; // 1-indexed

        // Backtick file references: `path/to/file.ext`
        for ref_path in extract_backtick_refs(line) {
            all_file_refs.push(FileRef {
                path: ref_path,
                line: line_num,
            });
        }

        // Markdown links: [text](path/to/file.ext)
        for (text, path) in extract_md_links(line) {
            all_links.push(MdLink {
                text,
                path,
                line: line_num,
            });
        }

        // Status markers
        for marker in extract_status_markers(line) {
            if !all_status_markers.contains(&marker) {
                all_status_markers.push(marker);
            }
        }
    }

    // ── Phase 3: Attribute refs/links to sections ─────────────────────

    for file_ref in &all_file_refs {
        if let Some(sec) = find_containing_section(&mut sections, file_ref.line) {
            sec.ref_count += 1;
        }
    }

    for link in &all_links {
        if let Some(sec) = find_containing_section(&mut sections, link.line) {
            sec.link_count += 1;
        }
    }

    // Attribute status markers to sections
    for (i, line) in lines.iter().enumerate() {
        let line_num = i + 1;
        let markers = extract_status_markers(line);
        if !markers.is_empty() {
            if let Some(sec) = find_containing_section(&mut sections, line_num) {
                for m in markers {
                    if !sec.status_markers.contains(&m) {
                        sec.status_markers.push(m);
                    }
                }
            }
        }
    }

    // ── Phase 4: Build nodes and edges ────────────────────────────────

    let total_ref_count = all_file_refs.len();
    let total_link_count = all_links.len();

    // Section nodes + contains edges
    for (idx, sec) in sections.iter().enumerate() {
        let section_id = format!("sec:{}@{}:{}", sanitize_id(&sec.name), file_path, sec.start_line);

        result.nodes.push(ParsedNode {
            id: section_id.clone(),
            kind: "section".to_string(),
            name: sec.name.clone(),
            file_path: file_path.to_string(),
            span: Some(Span {
                start_line: sec.start_line,
                end_line: sec.end_line,
            }),
            language: Some("markdown".to_string()),
            metadata: NodeMetadata {
                symbol_type: Some(format!("h{}", sec.depth)),
                qualname: Some(sec.name.clone()),
                header_depth: Some(sec.depth),
                ref_count: Some(sec.ref_count),
                link_count: Some(sec.link_count),
                status_markers: if sec.status_markers.is_empty() {
                    None
                } else {
                    Some(sec.status_markers.clone())
                },
                ..Default::default()
            },
        });

        // File → section contains edge
        let edge_id = stable_edge_id(
            "contains",
            &file_node_id,
            &section_id,
            &idx.to_string(),
        );
        result.edges.push(ParsedEdge {
            id: edge_id,
            kind: "contains".to_string(),
            source: file_node_id.clone(),
            target: section_id,
            metadata: EdgeMetadata {
                confidence: 1.0,
                ..Default::default()
            },
        });
    }

    // Reference edges (backtick file refs → target file nodes)
    for (idx, file_ref) in all_file_refs.iter().enumerate() {
        let resolved = resolve_path(file_dir, &file_ref.path);
        let target_file_id = stable_file_node_id(&resolved);
        let edge_id = stable_edge_id(
            "references",
            &file_node_id,
            &target_file_id,
            &format!("ref:{}", idx),
        );
        result.edges.push(ParsedEdge {
            id: edge_id,
            kind: "references".to_string(),
            source: file_node_id.clone(),
            target: target_file_id,
            metadata: EdgeMetadata {
                confidence: 0.9,
                line: Some(file_ref.line),
                ..Default::default()
            },
        });
    }

    // Link edges (markdown links → target file nodes)
    for (idx, link) in all_links.iter().enumerate() {
        let resolved = resolve_path(file_dir, &link.path);
        let target_file_id = stable_file_node_id(&resolved);
        let edge_id = stable_edge_id(
            "links_to",
            &file_node_id,
            &target_file_id,
            &format!("link:{}", idx),
        );
        result.edges.push(ParsedEdge {
            id: edge_id,
            kind: "links_to".to_string(),
            source: file_node_id.clone(),
            target: target_file_id,
            metadata: EdgeMetadata {
                confidence: 1.0,
                line: Some(link.line),
                import_str: Some(link.text.clone()),
                ..Default::default()
            },
        });
    }

    // ── Phase 5: Update file node metadata (caller must merge) ────────
    // We return a "patch" node with the same file ID so the graph can
    // update the file node's metadata. The graph's add_node replaces by ID.
    result.nodes.push(ParsedNode {
        id: file_node_id.clone(),
        kind: "file".to_string(),
        name: std::path::Path::new(file_path)
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string(),
        file_path: file_path.to_string(),
        span: None,
        language: Some("markdown".to_string()),
        metadata: NodeMetadata {
            section_count: Some(sections.len()),
            ref_count: Some(total_ref_count),
            link_count: Some(total_link_count),
            line_count: Some(line_count),
            status_markers: if all_status_markers.is_empty() {
                None
            } else {
                Some(all_status_markers)
            },
            ..Default::default()
        },
    });

    result
}

// ── Internal types ──────────────────────────────────────────────────

struct SectionInfo {
    name: String,
    depth: usize,
    start_line: usize,
    end_line: usize,
    ref_count: usize,
    link_count: usize,
    status_markers: Vec<String>,
}

struct HeaderMatch {
    text: String,
    depth: usize,
}

struct FileRef {
    path: String,
    line: usize,
}

struct MdLink {
    text: String,
    path: String,
    line: usize,
}

// ── Extraction helpers ──────────────────────────────────────────────

/// Parse a markdown header line: "## Foo Bar" → HeaderMatch { depth: 2, text: "Foo Bar" }
fn parse_header(line: &str) -> Option<HeaderMatch> {
    let trimmed = line.trim_start();
    if !trimmed.starts_with('#') {
        return None;
    }
    let depth = trimmed.chars().take_while(|c| *c == '#').count();
    if depth > 6 {
        return None;
    }
    let rest = &trimmed[depth..];
    // Must have a space after the hashes (standard markdown)
    if !rest.starts_with(' ') && !rest.is_empty() {
        return None;
    }
    let text = rest.trim().to_string();
    if text.is_empty() {
        return None;
    }
    Some(HeaderMatch { text, depth })
}

/// Extract backtick-wrapped file references from a line.
/// Matches: `path/to/file.ext` where path contains a dot and looks like a file path.
fn extract_backtick_refs(line: &str) -> Vec<String> {
    let mut refs = Vec::new();
    let mut chars = line.char_indices();
    let mut in_backtick = false;
    let mut start = 0;

    while let Some((i, c)) = chars.next() {
        if c == '`' {
            if in_backtick {
                // End of backtick span
                let content = &line[start..i];
                if looks_like_file_path(content) {
                    refs.push(normalize_path(content));
                }
                in_backtick = false;
            } else {
                // Start of backtick span (skip double backticks / code blocks)
                if line[i..].starts_with("```") {
                    break; // code fence, stop scanning
                }
                in_backtick = true;
                start = i + 1;
            }
        }
    }
    refs
}

/// Extract markdown links: [text](path) where path looks like a file path.
fn extract_md_links(line: &str) -> Vec<(String, String)> {
    let mut links = Vec::new();
    let bytes = line.as_bytes();
    let len = bytes.len();
    let mut i = 0;

    while i < len {
        // Look for '['
        if bytes[i] == b'[' {
            let text_start = i + 1;
            // Find matching ']'
            if let Some(text_end) = find_closing_bracket(line, text_start) {
                // Check for '(' immediately after ']'
                let paren_start = text_end + 1;
                if paren_start < len && bytes[paren_start] == b'(' {
                    let path_start = paren_start + 1;
                    if let Some(path_end) = line[path_start..].find(')') {
                        let text = line[text_start..text_end].to_string();
                        let path = line[path_start..path_start + path_end].trim().to_string();
                        // Only include if it looks like a file path (not a URL)
                        if looks_like_file_path(&path) && !path.starts_with("http") {
                            links.push((text, normalize_path(&path)));
                        }
                        i = path_start + path_end + 1;
                        continue;
                    }
                }
                i = text_end + 1;
                continue;
            }
        }
        i += 1;
    }
    links
}

/// Extract status markers from a line.
fn extract_status_markers(line: &str) -> Vec<String> {
    let mut markers = Vec::new();

    // Unicode markers
    if line.contains('\u{2705}') {
        markers.push("\u{2705}".to_string());
    } // ✅
    if line.contains('\u{23F3}') {
        markers.push("\u{23F3}".to_string());
    } // ⏳
    if line.contains('\u{274C}') {
        markers.push("\u{274C}".to_string());
    } // ❌
    if line.contains('\u{26A0}') {
        markers.push("\u{26A0}".to_string());
    } // ⚠
    if line.contains('\u{1F6A7}') {
        markers.push("\u{1F6A7}".to_string());
    } // 🚧

    // Text markers
    let lower = line.to_lowercase();
    if lower.contains("**status**:") || lower.contains("**status:**") {
        // Extract the status value after the marker
        if let Some(pos) = lower.find("**status**") {
            let after = &line[pos..];
            if let Some(colon_pos) = after.find(':') {
                let value = after[colon_pos + 1..].trim();
                // Take up to the next ** or end of line
                let end = value.find("**").unwrap_or(value.len());
                let status_text = value[..end].trim();
                if !status_text.is_empty() {
                    markers.push(format!("status:{}", status_text));
                }
            }
        }
    }

    markers
}

// ── Utility helpers ─────────────────────────────────────────────────

/// Check if a string looks like a file path (has an extension, no spaces at start).
fn looks_like_file_path(s: &str) -> bool {
    let s = s.trim();
    if s.is_empty() || s.len() > 200 {
        return false;
    }
    // Must contain a dot for the extension
    if !s.contains('.') {
        return false;
    }
    // Must not be just a number or common non-path pattern
    if s.parse::<f64>().is_ok() {
        return false;
    }
    // Must not contain obvious non-path characters
    if s.contains(' ') && !s.contains('/') && !s.contains('\\') {
        return false;
    }
    // Check the extension looks real
    if let Some(ext_pos) = s.rfind('.') {
        let ext = &s[ext_pos + 1..];
        if ext.is_empty() || ext.len() > 10 {
            return false;
        }
        // Must be alphanumeric extension
        if !ext.chars().all(|c| c.is_alphanumeric()) {
            return false;
        }
        return true;
    }
    false
}

/// Normalize a path: trim whitespace, remove leading `./`
fn normalize_path(path: &str) -> String {
    let mut p = path.trim().to_string();
    if p.starts_with("./") {
        p = p[2..].to_string();
    }
    p
}

/// Resolve a referenced path relative to the markdown file's directory.
/// E.g., file at "docs/Phase22/README.md" referencing "PATH_FORWARD.md"
/// resolves to "docs/Phase22/PATH_FORWARD.md".
/// Absolute-looking paths (starting with src/, docs/, etc.) pass through unchanged.
fn resolve_path(file_dir: &std::path::Path, ref_path: &str) -> String {
    // If the ref already contains a directory separator, it's likely repo-relative
    if ref_path.contains('/') {
        // Normalize: join with file_dir only if it looks relative (starts with ./ or ../)
        if ref_path.starts_with("../") || ref_path.starts_with("./") {
            let joined = file_dir.join(ref_path);
            normalize_joined_path(&joined)
        } else {
            ref_path.to_string()
        }
    } else {
        // Bare filename like "PATH_FORWARD.md" → resolve relative to file's directory
        let joined = file_dir.join(ref_path);
        normalize_joined_path(&joined)
    }
}

/// Normalize a joined path: collapse ".." components, convert to POSIX string.
fn normalize_joined_path(path: &std::path::Path) -> String {
    let mut components = Vec::new();
    for comp in path.components() {
        match comp {
            std::path::Component::ParentDir => { components.pop(); }
            std::path::Component::CurDir => {}
            std::path::Component::Normal(s) => {
                components.push(s.to_string_lossy().to_string());
            }
            _ => {}
        }
    }
    components.join("/")
}

/// Sanitize a string for use in a node ID (replace spaces/special chars).
fn sanitize_id(s: &str) -> String {
    s.chars()
        .map(|c| {
            if c.is_alphanumeric() || c == '_' || c == '-' {
                c
            } else {
                '_'
            }
        })
        .collect::<String>()
        .to_lowercase()
}

/// Find the closing ']' bracket, handling nesting.
fn find_closing_bracket(s: &str, start: usize) -> Option<usize> {
    let bytes = s.as_bytes();
    let mut depth = 1;
    let mut i = start;
    while i < bytes.len() {
        match bytes[i] {
            b'[' => depth += 1,
            b']' => {
                depth -= 1;
                if depth == 0 {
                    return Some(i);
                }
            }
            _ => {}
        }
        i += 1;
    }
    None
}

/// Find which section contains a given line number.
fn find_containing_section(sections: &mut [SectionInfo], line: usize) -> Option<&mut SectionInfo> {
    // Find the last section whose start_line <= line
    sections
        .iter_mut()
        .rev()
        .find(|sec| sec.start_line <= line && sec.end_line >= line)
}

// ── Tests ───────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_header() {
        let h = parse_header("## Hello World").unwrap();
        assert_eq!(h.depth, 2);
        assert_eq!(h.text, "Hello World");

        let h = parse_header("# Top Level").unwrap();
        assert_eq!(h.depth, 1);
        assert_eq!(h.text, "Top Level");

        let h = parse_header("### Sub Section").unwrap();
        assert_eq!(h.depth, 3);
        assert_eq!(h.text, "Sub Section");

        assert!(parse_header("Not a header").is_none());
        assert!(parse_header("#nospace").is_none());
        assert!(parse_header("").is_none());
        assert!(parse_header("#").is_none());
        assert!(parse_header("####### too deep").is_none());
    }

    #[test]
    fn test_extract_backtick_refs() {
        let refs = extract_backtick_refs("See `src/main.py` and `lib/utils.rs` for details");
        assert_eq!(refs, vec!["src/main.py", "lib/utils.rs"]);

        let refs = extract_backtick_refs("Use `AdManager.swift` here");
        assert_eq!(refs, vec!["AdManager.swift"]);

        // Should not match non-file backticks
        let refs = extract_backtick_refs("Use `someVariable` here");
        assert!(refs.is_empty());

        // Should not match code fences
        let refs = extract_backtick_refs("```python");
        assert!(refs.is_empty());
    }

    #[test]
    fn test_extract_md_links() {
        let links = extract_md_links("See [the readme](README.md) for more");
        assert_eq!(links.len(), 1);
        assert_eq!(links[0].0, "the readme");
        assert_eq!(links[0].1, "README.md");

        let links = extract_md_links("Check [docs](./docs/API.md) and [src](src/lib.rs)");
        assert_eq!(links.len(), 2);
        assert_eq!(links[0].1, "docs/API.md"); // normalized away ./
        assert_eq!(links[1].1, "src/lib.rs");

        // Should not match URLs
        let links = extract_md_links("[link](https://example.com)");
        assert!(links.is_empty());
    }

    #[test]
    fn test_extract_status_markers() {
        let m = extract_status_markers("✅ Complete");
        assert!(m.contains(&"\u{2705}".to_string()));

        let m = extract_status_markers("⏳ In progress");
        assert!(m.contains(&"\u{23F3}".to_string()));

        let m = extract_status_markers("**Status**: Active");
        assert!(m.iter().any(|s| s.contains("Active")));

        let m = extract_status_markers("Nothing here");
        assert!(m.is_empty());
    }

    #[test]
    fn test_looks_like_file_path() {
        assert!(looks_like_file_path("src/main.py"));
        assert!(looks_like_file_path("README.md"));
        assert!(looks_like_file_path("AdManager.swift"));
        assert!(looks_like_file_path("lib/utils.rs"));
        assert!(!looks_like_file_path("someVariable"));
        assert!(!looks_like_file_path("3.14"));
        assert!(!looks_like_file_path(""));
        assert!(!looks_like_file_path("hello world"));
    }

    #[test]
    fn test_analyze_basic() {
        let content = "\
# My Project

Overview of the project.

## Architecture

See `src/main.py` and `src/utils.py` for the core logic.

Check [API docs](docs/API.md) for the API reference.

### Status

✅ Framework complete
⏳ Backend integration pending

## References

- [README](README.md)
- `config.toml`
";

        let result = analyze("docs/OVERVIEW.md", content);

        // Should have sections: "My Project", "Architecture", "Status", "References"
        let section_nodes: Vec<_> = result.nodes.iter().filter(|n| n.kind == "section").collect();
        assert_eq!(section_nodes.len(), 4);

        // Should have file refs: src/main.py, src/utils.py, config.toml
        let ref_edges: Vec<_> = result.edges.iter().filter(|e| e.kind == "references").collect();
        assert_eq!(ref_edges.len(), 3);

        // Should have link edges: docs/API.md, README.md
        let link_edges: Vec<_> = result.edges.iter().filter(|e| e.kind == "links_to").collect();
        assert_eq!(link_edges.len(), 2);

        // Should have contains edges (file → section)
        let contains_edges: Vec<_> = result.edges.iter().filter(|e| e.kind == "contains").collect();
        assert_eq!(contains_edges.len(), 4);

        // File node should have updated metadata
        let file_node = result.nodes.iter().find(|n| n.kind == "file").unwrap();
        assert_eq!(file_node.metadata.section_count, Some(4));
        assert_eq!(file_node.metadata.ref_count, Some(3));
        assert_eq!(file_node.metadata.link_count, Some(2));
        assert!(file_node.metadata.status_markers.is_some());
    }

    #[test]
    fn test_section_spans() {
        let content = "\
# Top

Some text.

## Section A

Content of A.
More content.

## Section B

Content of B.
";

        let result = analyze("test.md", content);
        let sections: Vec<_> = result.nodes.iter()
            .filter(|n| n.kind == "section")
            .collect();

        assert_eq!(sections.len(), 3);

        // "Top" should span from line 1 to line 4 (before "Section A")
        let top = sections.iter().find(|n| n.name == "Top").unwrap();
        assert_eq!(top.span.as_ref().unwrap().start_line, 1);
        assert_eq!(top.span.as_ref().unwrap().end_line, 4);

        // "Section A" should span from line 5 to line 9
        let sec_a = sections.iter().find(|n| n.name == "Section A").unwrap();
        assert_eq!(sec_a.span.as_ref().unwrap().start_line, 5);

        // "Section B" should extend to end of file
        let sec_b = sections.iter().find(|n| n.name == "Section B").unwrap();
        assert_eq!(sec_b.span.as_ref().unwrap().end_line, 12);
    }

    #[test]
    fn test_ref_count_per_section() {
        let content = "\
# Top

## Code Files

See `src/a.py`, `src/b.py`, and `src/c.py`.

## Other

No code refs here, just text.
";

        let result = analyze("test.md", content);
        let sections: Vec<_> = result.nodes.iter()
            .filter(|n| n.kind == "section")
            .collect();

        let code_sec = sections.iter().find(|n| n.name == "Code Files").unwrap();
        assert_eq!(code_sec.metadata.ref_count, Some(3));

        let other_sec = sections.iter().find(|n| n.name == "Other").unwrap();
        assert_eq!(other_sec.metadata.ref_count, Some(0));
    }

    #[test]
    fn test_empty_file() {
        let result = analyze("empty.md", "");
        assert_eq!(result.nodes.len(), 1); // just the file node
        assert_eq!(result.edges.len(), 0);
    }

    #[test]
    fn test_path_resolution() {
        // Bare filename resolves relative to file's directory
        let dir = std::path::Path::new("docs/Phase22");
        assert_eq!(resolve_path(dir, "README.md"), "docs/Phase22/README.md");

        // Paths with slashes that don't start with ./ or ../ pass through
        assert_eq!(resolve_path(dir, "src/main.py"), "src/main.py");

        // Relative paths with ./ resolve
        assert_eq!(resolve_path(dir, "./OTHER.md"), "docs/Phase22/OTHER.md");

        // Relative paths with ../ resolve
        assert_eq!(resolve_path(dir, "../API.md"), "docs/API.md");

        // Root-level file
        let root = std::path::Path::new("");
        assert_eq!(resolve_path(root, "README.md"), "README.md");
    }

    #[test]
    fn test_analyze_resolves_refs() {
        let content = "\
# Doc

See `PATH_FORWARD.md` and `src/main.py` for details.
Check [link](./OTHER.md) here.
";
        let result = analyze("docs/Phase22/README.md", content);

        let ref_edges: Vec<_> = result.edges.iter().filter(|e| e.kind == "references").collect();
        // PATH_FORWARD.md should resolve to docs/Phase22/PATH_FORWARD.md
        assert!(ref_edges.iter().any(|e| e.target == "file:docs/Phase22/PATH_FORWARD.md"));
        // src/main.py has a slash, so it passes through as-is
        assert!(ref_edges.iter().any(|e| e.target == "file:src/main.py"));

        let link_edges: Vec<_> = result.edges.iter().filter(|e| e.kind == "links_to").collect();
        // ./OTHER.md should resolve to docs/Phase22/OTHER.md
        assert!(link_edges.iter().any(|e| e.target == "file:docs/Phase22/OTHER.md"));
    }
}
