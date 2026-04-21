from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


MANIFEST_VERSION = "1.0"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_manifest(path: Path) -> Dict[str, Any]:
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return data


def write_manifest(path: Path, manifest: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)


@dataclass(frozen=True)
class ManifestBuildStats:
    mode: str
    files_total: int
    files_reused: int
    files_embedded: int
    files_deleted: int = 0
    chunks_total: int = 0
    chunks_reused: int = 0
    chunks_embedded: int = 0
    chunks_code: int = 0
    chunks_docs: int = 0
    # New stats
    lines_scanned: int = 0
    lines_indexed: int = 0
    files_docs: int = 0
    files_code: int = 0
    lines_docs: int = 0
    lines_code: int = 0


def build_manifest(
    *,
    model: str,
    embedding_dim: int,
    roots: list[str],
    count: int,
    build: ManifestBuildStats,
    config: Dict[str, Any],
    file_hashes: Optional[Dict[str, str]] = None,
    version: str = MANIFEST_VERSION,
    built_at: Optional[str] = None,
) -> Dict[str, Any]:
    m: Dict[str, Any] = {
        "version": version,
        "built_at": built_at or utc_now_iso(),
        "model": model,
        "roots": list(roots),
        "count": int(count),
        "embedding_dim": int(embedding_dim),
        "build": {
            "mode": build.mode,
            "files_total": int(build.files_total),
            "files_reused": int(build.files_reused),
            "files_embedded": int(build.files_embedded),
            "files_deleted": int(build.files_deleted),
            "chunks_total": int(build.chunks_total),
            "chunks_reused": int(build.chunks_reused),
            "chunks_embedded": int(build.chunks_embedded),
            "lines_scanned": int(build.lines_scanned),
            "lines_indexed": int(build.lines_indexed),
            "files_docs": int(build.files_docs),
            "files_code": int(build.files_code),
            "chunks_code": int(build.chunks_code),
            "chunks_docs": int(build.chunks_docs),
            "lines_docs": int(build.lines_docs),
            "lines_code": int(build.lines_code),
        },
        "config": dict(config),
    }
    if file_hashes is not None:
        m["file_hashes"] = dict(file_hashes)
    return m
