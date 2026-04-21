from __future__ import annotations

import hashlib


def stable_sha256(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[: int(length)]


def stable_file_hash(text: str) -> str:
    return stable_sha256(text, length=16)


def stable_markdown_chunk_id(source_path: str, section: str, idx: int) -> str:
    return stable_sha256(f"{source_path}:{section}:{idx}", length=16)


def stable_code_chunk_id(source_path: str, idx: int) -> str:
    return stable_sha256(f"{source_path}:{idx}", length=16)


def stable_file_node_id(file_path: str) -> str:
    return f"file:{file_path}"


def stable_symbol_node_id(qualname: str, file_path: str, start_line: int) -> str:
    return f"sym:{qualname}@{file_path}:{start_line}"


def stable_external_module_id(module_name: str) -> str:
    return f"ext:{module_name}"


def stable_edge_id(kind: str, source: str, target: str, disambiguator: str = "") -> str:
    if disambiguator:
        return f"edge:{kind}:{source}:{target}:{disambiguator}"
    return f"edge:{kind}:{source}:{target}"
