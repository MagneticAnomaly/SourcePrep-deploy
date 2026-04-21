//! Document chunking for Prep.
//!
//! Provides heading-based markdown chunking and size-based code chunking,
//! with stable SHA-256 chunk IDs matching the Python `ids.py` implementation.

use once_cell::sync::Lazy;
use regex::Regex;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;

// ── Stable ID generation (must match Python ids.py exactly) ──────────────────

fn stable_sha256(text: &str, length: usize) -> String {
    let hash = Sha256::digest(text.as_bytes());
    let hex = format!("{:x}", hash);
    hex[..length.min(hex.len())].to_string()
}

fn stable_markdown_chunk_id(source_path: &str, section: &str, idx: usize) -> String {
    stable_sha256(&format!("{}:{}:{}", source_path, section, idx), 16)
}

fn stable_code_chunk_id(source_path: &str, idx: usize) -> String {
    stable_sha256(&format!("{}:{}", source_path, idx), 16)
}

// ── Chunk type ───────────────────────────────────────────────────────────────

/// A document chunk with content and metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Chunk {
    pub chunk_id: String,
    pub content: String,
    pub metadata: HashMap<String, serde_json::Value>,
}

// ── Markdown chunking ────────────────────────────────────────────────────────

static HEADING_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"^(#{1,6})\s+(.*)$").unwrap());

struct MarkdownSection {
    headings: Vec<String>,
    text: String,
    start_line: usize,
    end_line: usize,
}

fn iter_markdown_sections(text: &str) -> Vec<MarkdownSection> {
    let lines: Vec<&str> = text.split('\n').collect();
    let mut sections = Vec::new();
    let mut headings: Vec<String> = Vec::new();
    let mut current_lines: Vec<&str> = Vec::new();
    let mut current_start_line: Option<usize> = None;
    let mut current_end_line: Option<usize> = None;

    for (line_no_0, line) in lines.iter().enumerate() {
        let line_no = line_no_0 + 1; // 1-indexed
        if let Some(caps) = HEADING_RE.captures(line) {
            if !current_lines.is_empty() {
                let text = current_lines.join("\n").trim().to_string();
                sections.push(MarkdownSection {
                    headings: headings.clone(),
                    text,
                    start_line: current_start_line.unwrap_or(1),
                    end_line: current_end_line.unwrap_or(line_no.saturating_sub(1).max(1)),
                });
                current_lines.clear();
                current_start_line = None;
                current_end_line = None;
            }

            let level = caps[1].len();
            let title = caps[2].trim().to_string();

            while headings.len() >= level {
                headings.pop();
            }
            headings.push(title);
        } else {
            if current_start_line.is_none() {
                current_start_line = Some(line_no);
            }
            current_end_line = Some(line_no);
            current_lines.push(line);
        }
    }

    if !current_lines.is_empty() {
        let text = current_lines.join("\n").trim().to_string();
        sections.push(MarkdownSection {
            headings: headings.clone(),
            text,
            start_line: current_start_line.unwrap_or(1),
            end_line: current_end_line.unwrap_or(lines.len().max(1)),
        });
    }

    sections
}

fn split_long_text(text: &str, max_chars: usize) -> Vec<String> {
    if text.len() <= max_chars {
        return vec![text.to_string()];
    }

    let paragraphs: Vec<&str> = text.split("\n\n").collect();
    let mut chunks: Vec<String> = Vec::new();
    let mut current: Vec<&str> = Vec::new();
    let mut current_len: usize = 0;

    for para in &paragraphs {
        let para_len = para.len();
        if current_len + para_len + 2 > max_chars && !current.is_empty() {
            chunks.push(current.join("\n\n"));
            current.clear();
            current_len = 0;
        }

        if para_len > max_chars {
            if !current.is_empty() {
                chunks.push(current.join("\n\n"));
                current.clear();
                current_len = 0;
            }
            let mut i = 0;
            while i < para_len {
                let end = (i + max_chars).min(para_len);
                chunks.push(para[i..end].to_string());
                i = end;
            }
        } else {
            current.push(para);
            current_len += para_len + 2;
        }
    }

    if !current.is_empty() {
        chunks.push(current.join("\n\n"));
    }

    chunks
}

/// Chunk markdown text by headings with size limits.
///
/// Returns a list of Chunk objects with stable IDs matching the Python implementation.
pub fn chunk_markdown(
    text: &str,
    source_path: &str,
    xref_id: Option<&str>,
    name: Option<&str>,
    max_chars: usize,
    min_chars: usize,
) -> Vec<Chunk> {
    let mut parts: Vec<Chunk> = Vec::new();
    let mut idx: usize = 0;

    let mut pending: Vec<String> = Vec::new();
    let mut pending_section: String = String::new();
    let mut pending_start_line: Option<usize> = None;
    let mut pending_end_line: Option<usize> = None;

    let sections = iter_markdown_sections(text);

    let make_meta = |headings: &[String], start_line: usize, end_line: usize| -> HashMap<String, serde_json::Value> {
        let mut meta = HashMap::new();
        meta.insert("source_path".to_string(), serde_json::json!(source_path));
        meta.insert("xref_id".to_string(), serde_json::json!(xref_id.unwrap_or("")));
        meta.insert("name".to_string(), serde_json::json!(name.unwrap_or("")));
        let section = if headings.is_empty() {
            String::new()
        } else {
            headings.join(" > ")
        };
        meta.insert("section".to_string(), serde_json::json!(section));
        meta.insert("span".to_string(), serde_json::json!({
            "start_line": start_line,
            "end_line": end_line,
        }));
        meta
    };

    let mut emit = |content: &str, section: &str, meta: HashMap<String, serde_json::Value>, idx: &mut usize| {
        let content = content.trim();
        if content.is_empty() {
            return;
        }
        let chunk_id = stable_markdown_chunk_id(source_path, section, *idx);
        parts.push(Chunk {
            chunk_id,
            content: content.to_string(),
            metadata: meta,
        });
        *idx += 1;
    };

    for sec in &sections {
        if sec.text.is_empty() {
            continue;
        }

        let section_str = if sec.headings.is_empty() {
            String::new()
        } else {
            sec.headings.join(" > ")
        };

        if !pending.is_empty() {
            let candidate_parts: Vec<&str> = pending.iter().map(|s| s.as_str()).collect();
            let mut candidate = candidate_parts.join("\n\n");
            candidate.push_str("\n\n");
            candidate.push_str(&sec.text);

            if candidate.len() <= max_chars {
                pending.push(sec.text.clone());
                pending_section = section_str;
                pending_end_line = Some(sec.end_line);
                continue;
            }

            let combined = pending.join("\n\n");
            let combined = combined.trim();
            if !combined.is_empty() {
                let mut meta = make_meta(&sec.headings, pending_start_line.unwrap_or(1), pending_end_line.unwrap_or(1));
                if let (Some(sl), Some(el)) = (pending_start_line, pending_end_line) {
                    meta.insert("span".to_string(), serde_json::json!({
                        "start_line": sl,
                        "end_line": el,
                    }));
                }
                emit(combined, &pending_section, meta, &mut idx);
            }
            pending.clear();
            pending_section.clear();
            pending_start_line = None;
            pending_end_line = None;
        }

        if sec.text.len() < min_chars {
            pending = vec![sec.text.clone()];
            pending_section = section_str;
            pending_start_line = Some(sec.start_line);
            pending_end_line = Some(sec.end_line);
            continue;
        }

        if sec.text.len() <= max_chars {
            let meta = make_meta(&sec.headings, sec.start_line, sec.end_line);
            emit(&sec.text, &section_str, meta, &mut idx);
            continue;
        }

        for part in split_long_text(&sec.text, max_chars) {
            let meta = make_meta(&sec.headings, sec.start_line, sec.end_line);
            emit(&part, &section_str, meta, &mut idx);
        }
    }

    if !pending.is_empty() {
        let combined = pending.join("\n\n");
        let combined = combined.trim();
        if !combined.is_empty() {
            let mut meta = HashMap::new();
            meta.insert("source_path".to_string(), serde_json::json!(source_path));
            meta.insert("xref_id".to_string(), serde_json::json!(xref_id.unwrap_or("")));
            meta.insert("name".to_string(), serde_json::json!(name.unwrap_or("")));
            meta.insert("section".to_string(), serde_json::json!(&pending_section));
            if let (Some(sl), Some(el)) = (pending_start_line, pending_end_line) {
                meta.insert("span".to_string(), serde_json::json!({
                    "start_line": sl,
                    "end_line": el,
                }));
            }
            emit(combined, &pending_section, meta, &mut idx);
        }
    }

    parts
}

/// Chunk code files by size with overlap.
///
/// Returns a list of Chunk objects with stable IDs matching the Python implementation.
pub fn chunk_code(
    text: &str,
    source_path: &str,
    max_chars: usize,
    overlap_chars: usize,
) -> Vec<Chunk> {
    if text.len() <= max_chars {
        let end_line = text.lines().count().max(1);
        let chunk_id = stable_code_chunk_id(source_path, 0);
        let mut metadata = HashMap::new();
        metadata.insert("source_path".to_string(), serde_json::json!(source_path));
        metadata.insert("chunk_index".to_string(), serde_json::json!(0));
        metadata.insert("span".to_string(), serde_json::json!({
            "start_line": 1,
            "end_line": end_line,
        }));
        return vec![Chunk {
            chunk_id,
            content: text.to_string(),
            metadata,
        }];
    }

    let mut chunks: Vec<Chunk> = Vec::new();
    let mut start: usize = 0;
    let mut idx: usize = 0;
    let step = max_chars.saturating_sub(overlap_chars);

    while start < text.len() {
        let end = (start + max_chars).min(text.len());
        let chunk_text = &text[start..end];

        let start_line = text[..start].matches('\n').count() + 1;
        let mut end_line = text[..end].matches('\n').count() + 1;
        if end > 0 && text.as_bytes().get(end - 1) == Some(&b'\n') {
            end_line = end_line.saturating_sub(1);
        }
        if end_line < 1 {
            end_line = 1;
        }

        let chunk_id = stable_code_chunk_id(source_path, idx);
        let mut metadata = HashMap::new();
        metadata.insert("source_path".to_string(), serde_json::json!(source_path));
        metadata.insert("chunk_index".to_string(), serde_json::json!(idx));
        metadata.insert("span".to_string(), serde_json::json!({
            "start_line": start_line,
            "end_line": end_line,
        }));

        chunks.push(Chunk {
            chunk_id,
            content: chunk_text.to_string(),
            metadata,
        });

        start += step;
        idx += 1;
    }

    chunks
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── Stable ID tests ──────────────────────────────────────

    #[test]
    fn test_stable_sha256_deterministic() {
        let a = stable_sha256("test:input:0", 16);
        let b = stable_sha256("test:input:0", 16);
        assert_eq!(a, b);
        assert_eq!(a.len(), 16);
    }

    #[test]
    fn test_stable_sha256_different_inputs() {
        let a = stable_sha256("test:0", 16);
        let b = stable_sha256("test:1", 16);
        assert_ne!(a, b);
    }

    // ── Markdown chunking tests ──────────────────────────────

    #[test]
    fn test_single_section_no_heading() {
        let text = "Just some plain text\nwith multiple lines\n";
        let chunks = chunk_markdown(text, "test.md", None, None, 1800, 350);
        assert_eq!(chunks.len(), 1);
        assert!(chunks[0].content.contains("Just some plain text"));
    }

    #[test]
    fn test_multiple_headings() {
        let text = "# Heading 1\n\nContent under heading 1.\n\n# Heading 2\n\nContent under heading 2.\n";
        let chunks = chunk_markdown(text, "test.md", None, None, 1800, 10);
        assert!(chunks.len() >= 2);
    }

    #[test]
    fn test_small_sections_merged() {
        let text = "# A\n\nShort.\n\n# B\n\nAlso short.\n";
        // min_chars = 350 means both sections are below minimum and should merge
        let chunks = chunk_markdown(text, "test.md", None, None, 1800, 350);
        assert_eq!(chunks.len(), 1);
    }

    #[test]
    fn test_metadata_has_source_path() {
        let text = "Some content here.";
        let chunks = chunk_markdown(text, "docs/readme.md", Some("xref-1"), Some("README"), 1800, 10);
        assert!(!chunks.is_empty());
        assert_eq!(chunks[0].metadata["source_path"], "docs/readme.md");
        assert_eq!(chunks[0].metadata["xref_id"], "xref-1");
        assert_eq!(chunks[0].metadata["name"], "README");
    }

    // ── Code chunking tests ──────────────────────────────────

    #[test]
    fn test_small_code_single_chunk() {
        let text = "def hello():\n    return 'world'\n";
        let chunks = chunk_code(text, "test.py", 2000, 200);
        assert_eq!(chunks.len(), 1);
        assert_eq!(chunks[0].content, text);
        assert_eq!(chunks[0].metadata["chunk_index"], 0);
    }

    #[test]
    fn test_large_code_multiple_chunks() {
        let text = "x\n".repeat(2000); // 4000 bytes
        let chunks = chunk_code(&text, "big.py", 2000, 200);
        assert!(chunks.len() >= 2);
        // First chunk starts at line 1
        assert_eq!(chunks[0].metadata["span"]["start_line"], 1);
    }

    #[test]
    fn test_code_chunk_ids_stable() {
        let text = "a\n".repeat(3000);
        let chunks_a = chunk_code(&text, "test.py", 2000, 200);
        let chunks_b = chunk_code(&text, "test.py", 2000, 200);
        for (a, b) in chunks_a.iter().zip(chunks_b.iter()) {
            assert_eq!(a.chunk_id, b.chunk_id);
        }
    }

    #[test]
    fn test_code_chunk_overlap() {
        let text = "a".repeat(3000);
        let chunks = chunk_code(&text, "test.py", 2000, 200);
        assert!(chunks.len() >= 2);
        // Second chunk should start earlier than where first ends (overlap)
        let _first_end = 2000;
        let second_start = 2000 - 200;
        assert_eq!(chunks[1].content.len(), text.len() - second_start);
        // Verify overlap exists
        assert!(chunks[0].content.len() + chunks[1].content.len() > text.len());
    }

    #[test]
    fn test_empty_code() {
        let chunks = chunk_code("", "empty.py", 2000, 200);
        assert_eq!(chunks.len(), 1);
        assert_eq!(chunks[0].content, "");
    }
}
