"""
CoDRAG Architecture Router — Phase 71A
=======================================

REST endpoints for the interactive architecture diagram.

Endpoints:
  GET    /projects/{id}/architecture/graph     — Composed graph (modules + edges)
  GET    /projects/{id}/architecture/summary   — Quick stats
  GET    /projects/{id}/architecture/state     — Persisted layout + overrides
  PUT    /projects/{id}/architecture/state     — Save layout + overrides
  GET    /projects/{id}/architecture/notes     — List all notes
  POST   /projects/{id}/architecture/notes     — Create a note
  PUT    /projects/{id}/architecture/notes/{nid} — Update a note
  DELETE /projects/{id}/architecture/notes/{nid} — Delete a note
  GET    /projects/{id}/architecture/context   — Architecture as MCP-ready text
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["architecture"])


def _require_project(project_id: str):
    from codrag.server import _require_project as rp
    return rp(project_id)


def _project_index_dir(proj) -> Path:
    from codrag.core.project_registry import project_index_dir
    return project_index_dir(proj)


def _get_arch_state(idx_dir: Path):
    from codrag.core.architecture_state import ArchitectureState
    return ArchitectureState(idx_dir)


# ── Request Models ──────────────────────────────────────────────────

class NoteCreate(BaseModel):
    node_id: str
    content: str
    note_type: str = "comment"
    author: str = "user"
    color: str = "yellow"


class NoteUpdate(BaseModel):
    content: Optional[str] = None
    color: Optional[str] = None


class ArchStateBody(BaseModel):
    layouts: Dict[str, Any] = {}
    module_overrides: Dict[str, Any] = {}


# ── Helpers ─────────────────────────────────────────────────────────

def _load_modules(idx_dir: Path) -> List[Dict[str, Any]]:
    """Load module synthesis results from trace_modules.jsonl."""
    modules_path = idx_dir / "trace_modules.jsonl"
    if not modules_path.exists():
        return []
    modules: List[Dict[str, Any]] = []
    try:
        with open(modules_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        modules.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        pass
    return modules


def _load_trace_edges(idx_dir: Path) -> List[Dict[str, Any]]:
    """Load trace edges from trace_edges.jsonl."""
    edges_path = idx_dir / "trace_edges.jsonl"
    if not edges_path.exists():
        return []
    edges: List[Dict[str, Any]] = []
    try:
        with open(edges_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        edges.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        pass
    return edges


def _build_file_to_module_map(modules: List[Dict[str, Any]]) -> Dict[str, str]:
    """Map file paths to their module IDs."""
    mapping: Dict[str, str] = {}
    for m in modules:
        for f in m.get("member_files", []):
            mapping[f] = m["module_id"]
    return mapping


def _aggregate_module_edges(
    trace_edges: List[Dict[str, Any]],
    file_to_module: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Aggregate file-level trace edges into module-level edges."""
    agg: Dict[str, Dict[str, Any]] = {}
    for edge in trace_edges:
        src_path = edge.get("source", "").replace("file:", "")
        tgt_path = edge.get("target", "").replace("file:", "")
        src_mod = file_to_module.get(src_path)
        tgt_mod = file_to_module.get(tgt_path)
        if not src_mod or not tgt_mod or src_mod == tgt_mod:
            continue
        key = f"{src_mod}::{tgt_mod}"
        kind = edge.get("kind", "imports")
        if key not in agg:
            agg[key] = {
                "source": src_mod,
                "target": tgt_mod,
                "kind": kind,
                "count": 0,
            }
        agg[key]["count"] += 1
    return list(agg.values())


def _normalize_module(m: Dict[str, Any]) -> Dict[str, Any]:
    """Remap raw JSONL module fields to the frontend ArchModule contract."""
    return {
        "id": m.get("module_id", ""),
        "name": m.get("name", ""),
        "description": m.get("summary", ""),
        "file_count": m.get("file_count", len(m.get("member_files", []))),
        "member_files": m.get("member_files", []),
        "hub_files": m.get("hub_files", []),
        "domain_tags": m.get("domain_tags", []),
        "architecture_layers": m.get("architecture_layers", []),
        "component_status": m.get("component_status", "unknown"),
        "avg_confidence": m.get("avg_epistemic_confidence", 0),
        "dependencies": m.get("dependencies", []),
    }


def _guess_language(path: str) -> str:
    ext_map = {
        ".py": "python", ".ts": "typescript", ".tsx": "tsx", ".js": "javascript",
        ".jsx": "jsx", ".rs": "rust", ".go": "go", ".java": "java",
        ".rb": "ruby", ".css": "css", ".html": "html", ".md": "markdown",
    }
    for ext, lang in ext_map.items():
        if path.endswith(ext):
            return lang
    return "unknown"


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/projects/{project_id}/architecture/graph")
def get_architecture_graph(
    project_id: str,
    layer_path: str = "",
) -> Dict[str, Any]:
    """Compose the architecture graph from modules + trace edges."""
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)

    modules = _load_modules(idx_dir)
    if not modules:
        return ok({
            "exists": False,
            "modules": [],
            "files": [],
            "edges": [],
            "external_refs": [],
            "stats": {"total_modules": 0, "total_files": 0, "total_edges": 0, "generated_at": ""},
        })

    trace_edges = _load_trace_edges(idx_dir)
    file_to_module = _build_file_to_module_map(modules)

    if not layer_path:
        # Layer 0: System overview — modules + aggregated edges
        module_edges = _aggregate_module_edges(trace_edges, file_to_module)
        return ok({
            "exists": True,
            "modules": [_normalize_module(m) for m in modules],
            "files": [],
            "edges": module_edges,
            "external_refs": [],
            "stats": {
                "total_modules": len(modules),
                "total_files": sum(m.get("file_count", 0) for m in modules),
                "total_edges": len(module_edges),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        })

    # Layer 1+: Drill into a specific module
    target_module = None
    for m in modules:
        if m["module_id"] == layer_path:
            target_module = m
            break

    if not target_module:
        raise ApiException(404, "MODULE_NOT_FOUND", f"Module '{layer_path}' not found")

    # Build file nodes for this module
    member_files = target_module.get("member_files", [])
    files: List[Dict[str, Any]] = []
    for fp in member_files:
        files.append({
            "id": f"file:{fp}",
            "path": fp,
            "module_id": target_module["module_id"],
            "language": _guess_language(fp),
            "hub_score": 0,
            "confidence": target_module.get("avg_epistemic_confidence", 0),
            "summary": "",
            "line_count": 0,
        })

    # File-level edges within this module + external refs
    internal_paths = set(member_files)
    file_edges: List[Dict[str, Any]] = []
    ext_modules: set = set()

    for edge in trace_edges:
        src = edge.get("source", "").replace("file:", "")
        tgt = edge.get("target", "").replace("file:", "")
        if src in internal_paths or tgt in internal_paths:
            file_edges.append({
                "source": f"file:{src}",
                "target": f"file:{tgt}",
                "kind": edge.get("kind", "imports"),
                "count": 1,
            })
            # Track external modules referenced
            if src not in internal_paths:
                ext_mod = file_to_module.get(src)
                if ext_mod:
                    ext_modules.add(ext_mod)
            if tgt not in internal_paths:
                ext_mod = file_to_module.get(tgt)
                if ext_mod:
                    ext_modules.add(ext_mod)

    external_refs = []
    for ext_mod_id in ext_modules:
        for m in modules:
            if m["module_id"] == ext_mod_id:
                external_refs.append({
                    "id": ext_mod_id,
                    "path": "",
                    "module_id": ext_mod_id,
                    "language": "",
                    "hub_score": 0,
                    "confidence": 0,
                    "summary": m.get("summary", ""),
                    "line_count": 0,
                })
                break

    return ok({
        "exists": True,
        "modules": [],
        "files": files,
        "edges": file_edges,
        "external_refs": external_refs,
        "stats": {
            "total_modules": 0,
            "total_files": len(files),
            "total_edges": len(file_edges),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    })


@router.get("/projects/{project_id}/architecture/summary")
def get_architecture_summary(project_id: str) -> Dict[str, Any]:
    """Quick stats about the architecture."""
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    modules = _load_modules(idx_dir)
    arch = _get_arch_state(idx_dir)
    notes = arch.list_notes()

    return ok({
        "exists": len(modules) > 0,
        "module_count": len(modules),
        "file_count": sum(m.get("file_count", 0) for m in modules),
        "edge_count": 0,
        "note_count": len(notes),
        "last_edited": None,
    })


# ── State persistence ──────────────────────────────────────────────

@router.get("/projects/{project_id}/architecture/state")
def get_architecture_state(project_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    arch = _get_arch_state(idx_dir)
    return ok(arch.load_state())


@router.put("/projects/{project_id}/architecture/state")
def save_architecture_state(project_id: str, body: ArchStateBody) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    arch = _get_arch_state(idx_dir)
    arch.save_state(body.model_dump())
    return ok({"saved": True})


# ── Notes CRUD ─────────────────────────────────────────────────────

@router.get("/projects/{project_id}/architecture/notes")
def list_notes(project_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    arch = _get_arch_state(idx_dir)
    return ok(arch.list_notes())


@router.post("/projects/{project_id}/architecture/notes")
def create_note(project_id: str, body: NoteCreate) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    arch = _get_arch_state(idx_dir)
    note = arch.create_note(
        node_id=body.node_id,
        content=body.content,
        note_type=body.note_type,
        author=body.author,
        color=body.color,
    )
    return ok(note)


@router.put("/projects/{project_id}/architecture/notes/{note_id}")
def update_note(project_id: str, note_id: str, body: NoteUpdate) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    arch = _get_arch_state(idx_dir)
    updated = arch.update_note(note_id, content=body.content, color=body.color)
    if not updated:
        raise ApiException(404, "NOTE_NOT_FOUND", f"Note '{note_id}' not found")
    return ok(updated)


@router.delete("/projects/{project_id}/architecture/notes/{note_id}")
def delete_note(project_id: str, note_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    arch = _get_arch_state(idx_dir)
    deleted = arch.delete_note(note_id)
    if not deleted:
        raise ApiException(404, "NOTE_NOT_FOUND", f"Note '{note_id}' not found")
    return ok({"deleted": True})


# ── MCP Context ────────────────────────────────────────────────────

@router.get("/projects/{project_id}/architecture/context")
def get_architecture_context(project_id: str) -> Dict[str, Any]:
    """Return user-curated architecture as structured text for MCP consumption."""
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)

    modules = _load_modules(idx_dir)
    if not modules:
        return ok({"text": "", "exists": False})

    arch = _get_arch_state(idx_dir)
    notes = arch.list_notes()
    trace_edges = _load_trace_edges(idx_dir)
    file_to_module = _build_file_to_module_map(modules)
    module_edges = _aggregate_module_edges(trace_edges, file_to_module)

    # Build notes index by node_id
    notes_by_node: Dict[str, List[Dict[str, Any]]] = {}
    for n in notes:
        nid = n.get("node_id", "")
        notes_by_node.setdefault(nid, []).append(n)

    # Build dependency map
    dep_map: Dict[str, List[str]] = {}
    for e in module_edges:
        dep_map.setdefault(e["source"], []).append(e["target"])

    lines: List[str] = []
    lines.append(f"### Architecture ({len(modules)} modules, user-curated)")
    lines.append("")

    for m in sorted(modules, key=lambda x: -x.get("file_count", 0)):
        mid = m["module_id"]
        name = m.get("name", mid)
        fc = m.get("file_count", 0)
        deps = dep_map.get(mid, [])
        dep_str = ", ".join(deps) if deps else "none"
        line = f"- **{name}** ({fc} files) \u2192 depends on: {dep_str}"
        lines.append(line)

        # Add notes for this module
        for note in notes_by_node.get(mid, []):
            nt = note.get("note_type", "comment")
            prefix = "\U0001f4cc" if nt == "adr" else "\U0001f916" if nt == "agent_note" else "\U0001f4ac"
            lines.append(f"  {prefix} \"{note.get('content', '')}\"")

    lines.append("")

    return ok({"text": "\n".join(lines), "exists": True})
