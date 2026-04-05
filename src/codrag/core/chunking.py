"""
Chunking strategies for CoDRAG.

Provides heading-based markdown chunking and size-based code chunking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional, Tuple

from .ids import stable_code_chunk_id, stable_markdown_chunk_id


@dataclass
class Chunk:
    """A document chunk with content and metadata."""
    chunk_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def _iter_markdown_sections(text: str) -> Generator[Tuple[List[str], str, int, int], None, None]:
    """
    Iterate over markdown sections, yielding (headings_stack, section_text).
    
    Headings stack tracks the current heading hierarchy.
    """
    lines = text.split("\n")
    headings: List[str] = []
    current_lines: List[str] = []
    current_start_line: Optional[int] = None
    current_end_line: Optional[int] = None

    heading_re = re.compile(r"^(#{1,6})\s+(.*)$")

    for line_no, line in enumerate(lines, start=1):
        m = heading_re.match(line)
        if m:
            if current_lines:
                yield (
                    list(headings),
                    "\n".join(current_lines).strip(),
                    int(current_start_line or 1),
                    int(current_end_line or (line_no - 1) or 1),
                )
                current_lines = []
                current_start_line = None
                current_end_line = None

            level = len(m.group(1))
            title = m.group(2).strip()

            while len(headings) >= level:
                headings.pop()
            headings.append(title)
        else:
            if current_start_line is None:
                current_start_line = line_no
            current_end_line = line_no
            current_lines.append(line)

    if current_lines:
        yield (
            list(headings),
            "\n".join(current_lines).strip(),
            int(current_start_line or 1),
            int(current_end_line or (len(lines) or 1)),
        )


def _split_long_text(text: str, max_chars: int) -> List[str]:
    """Split long text into chunks at paragraph boundaries."""
    if len(text) <= max_chars:
        return [text]

    paragraphs = re.split(r"\n\n+", text)
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len + 2 > max_chars and current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0

        if para_len > max_chars:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            for i in range(0, para_len, max_chars):
                chunks.append(para[i : i + max_chars])
        else:
            current.append(para)
            current_len += para_len + 2

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def chunk_markdown(
    text: str,
    source_path: str,
    xref_id: Optional[str] = None,
    name: Optional[str] = None,
    max_chars: int = 1800,
    min_chars: int = 350,
) -> List[Chunk]:
    """
    Chunk markdown text by headings with size limits.

    Args:
        text: Raw markdown content
        source_path: Path to the source file (for metadata)
        xref_id: Optional cross-reference ID
        name: Optional document name
        max_chars: Maximum chunk size
        min_chars: Minimum chunk size (smaller sections are merged)

    Returns:
        List of Chunk objects
    """
    parts: List[Chunk] = []

    def make_meta(headings: List[str], start_line: int, end_line: int) -> Dict[str, Any]:
        return {
            "source_path": source_path,
            "xref_id": xref_id or "",
            "name": name or "",
            "section": " > ".join(headings) if headings else "",
            "span": {"start_line": int(start_line), "end_line": int(end_line)},
        }

    def emit(content: str, meta: Dict[str, Any], idx: int) -> None:
        content = content.strip()
        if not content:
            return

        chunk_id = stable_markdown_chunk_id(source_path, str(meta.get("section") or ""), idx)

        parts.append(Chunk(chunk_id=chunk_id, content=content, metadata=dict(meta)))

    pending: List[str] = []
    pending_meta: Dict[str, Any] = {}
    pending_start_line: Optional[int] = None
    pending_end_line: Optional[int] = None
    idx = 0

    for headings, section_text, start_line, end_line in _iter_markdown_sections(text):
        if not section_text:
            continue

        section_meta = make_meta(headings, start_line, end_line)

        if pending:
            candidate = "\n\n".join(pending + [section_text])
            if len(candidate) <= max_chars:
                pending.append(section_text)
                pending_meta = section_meta
                pending_end_line = int(end_line)
                continue

            combined = "\n\n".join(pending).strip()
            if combined:
                meta = dict(pending_meta or section_meta)
                if pending_start_line is not None and pending_end_line is not None:
                    meta["span"] = {"start_line": int(pending_start_line), "end_line": int(pending_end_line)}
                emit(combined, meta, idx)
                idx += 1
            pending = []
            pending_meta = {}
            pending_start_line = None
            pending_end_line = None

        if len(section_text) < min_chars:
            pending = [section_text]
            pending_meta = section_meta
            pending_start_line = int(start_line)
            pending_end_line = int(end_line)
            continue

        if len(section_text) <= max_chars:
            emit(section_text, section_meta, idx)
            idx += 1
            continue

        for part in _split_long_text(section_text, max_chars):
            emit(part, section_meta, idx)
            idx += 1

    if pending:
        combined = "\n\n".join(pending).strip()
        if combined:
            meta = dict(pending_meta)
            if pending_start_line is not None and pending_end_line is not None:
                meta["span"] = {"start_line": int(pending_start_line), "end_line": int(pending_end_line)}
            emit(combined, meta, idx)

    return parts


def chunk_code(
    text: str,
    source_path: str,
    max_chars: int = 2000,
    overlap_chars: int = 200,
) -> List[Chunk]:
    """
    Chunk code files by size with overlap.

    Args:
        text: Raw code content
        source_path: Path to the source file
        max_chars: Maximum chunk size
        overlap_chars: Number of characters to overlap between chunks

    Returns:
        List of Chunk objects
    """
    if len(text) <= max_chars:
        end_line = len(text.splitlines()) or 1
        chunk_id = stable_code_chunk_id(source_path, 0)
        return [
            Chunk(
                chunk_id=chunk_id,
                content=text,
                metadata={
                    "source_path": source_path,
                    "chunk_index": 0,
                    "span": {"start_line": 1, "end_line": int(end_line)},
                },
            )
        ]

    chunks: List[Chunk] = []
    start = 0
    idx = 0
    step = max_chars - overlap_chars

    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk_text = text[start:end]

        start_line = text.count("\n", 0, start) + 1
        end_line = text.count("\n", 0, end) + 1
        if end > 0 and text[end - 1] == "\n":
            end_line -= 1
        if end_line < 1:
            end_line = 1

        chunk_id = stable_code_chunk_id(source_path, idx)
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                content=chunk_text,
                metadata={
                    "source_path": source_path,
                    "chunk_index": idx,
                    "span": {"start_line": int(start_line), "end_line": int(end_line)},
                },
            )
        )

        start += step
        idx += 1

    return chunks


def extract_file_synopsis(text: str, source_path: str, max_chars: int = 1500) -> str:
    """Extract a structural synopsis of a file for use as a meta-chunk.

    Pulls out the module docstring, class names with docstrings, and
    public function/method names. Returns a compact text summary suitable
    for embedding so that structural queries match the file's identity.

    Args:
        text: Raw file content.
        source_path: Relative path to the file.
        max_chars: Maximum length of the returned synopsis.

    Returns:
        A newline-separated synopsis string.
    """
    parts: List[str] = [f"File: {source_path}"]

    # 1. Module docstring (first triple-quoted string at the start of the file)
    mod_doc_match = re.match(r'\s*(?:\'\'\'|""")(.+?)(?:\'\'\'|""")', text, re.DOTALL)
    if mod_doc_match:
        purpose = mod_doc_match.group(1).strip().split("\n")[0].strip()
        if purpose:
            parts.append(f"Purpose: {purpose}")

    # 2. Classes with their docstrings
    class_pattern = re.compile(
        r'^class\s+(\w+)[^:]*:\s*\n\s*(?:\'\'\'|""")(.+?)(?:\'\'\'|""")',
        re.MULTILINE | re.DOTALL,
    )
    classes: List[str] = []
    for m in class_pattern.finditer(text):
        name = m.group(1)
        doc = m.group(2).strip().split("\n")[0].strip()
        classes.append(f"{name} \u2014 {doc}" if doc else name)
    if classes:
        parts.append(f"Classes: {'; '.join(classes)}")

    # 3. Public function and method names (not starting with _)
    func_pattern = re.compile(r'^\s*def\s+([a-zA-Z]\w*)\s*\(', re.MULTILINE)
    funcs = sorted(set(m.group(1) for m in func_pattern.finditer(text)))
    if funcs:
        parts.append(f"Functions: {', '.join(funcs)}")

    result = "\n".join(parts)
    if len(result) > max_chars:
        result = result[:max_chars]
    return result
