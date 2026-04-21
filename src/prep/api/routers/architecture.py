"""
Prep Architecture Router — Phase 71A
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

from prep.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["architecture"])


def _require_project(project_id: str):
    from prep.server import _require_project as rp
    return rp(project_id)


def _project_index_dir(proj) -> Path:
    from prep.core.project_registry import project_index_dir
    return project_index_dir(proj)


def _get_arch_state(idx_dir: Path):
    from prep.core.architecture_state import ArchitectureState
    return ArchitectureState(idx_dir)


def _get_acr_mgr(idx_dir: Path):
    from prep.core.architecture_acr import ArchitectureACRManager
    return ArchitectureACRManager(idx_dir)


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


class ACRCreate(BaseModel):
    title: str
    description: str
    source_type: str = "user"
    source_agent: str = "user"
    affected_nodes: List[str] = []


class LinkIssueBody(BaseModel):
    paperclip_issue_id: str
    title: str
    priority: str = "P2"
    status: str = "open"


class BriefingRequest(BaseModel):
    node_id: str
    scope: str = "module"


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
    show_orphans: bool = False,
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

        # Filter to only connected modules unless show_orphans is set
        if not show_orphans:
            connected_ids: set = set()
            for e in module_edges:
                connected_ids.add(e["source"])
                connected_ids.add(e["target"])
            visible_modules = [m for m in modules if m["module_id"] in connected_ids]
        else:
            visible_modules = modules

        return ok({
            "exists": True,
            "modules": [_normalize_module(m) for m in visible_modules],
            "files": [],
            "edges": module_edges,
            "external_refs": [],
            "stats": {
                "total_modules": len(visible_modules),
                "total_files": sum(m.get("file_count", 0) for m in visible_modules),
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
    acr_mgr = _get_acr_mgr(idx_dir)
    notes = arch.list_notes()
    all_acrs = acr_mgr.list_acrs()
    all_links = acr_mgr.list_issue_links()
    trace_edges = _load_trace_edges(idx_dir)
    file_to_module = _build_file_to_module_map(modules)
    module_edges = _aggregate_module_edges(trace_edges, file_to_module)

    # Build notes index by node_id
    notes_by_node: Dict[str, List[Dict[str, Any]]] = {}
    for n in notes:
        nid = n.get("node_id", "")
        notes_by_node.setdefault(nid, []).append(n)

    # Build ACR index by node_id
    acrs_by_node: Dict[str, List[Dict[str, Any]]] = {}
    for a in all_acrs:
        for nid in a.get("affected_nodes", []):
            acrs_by_node.setdefault(nid, []).append(a)

    # Build issue index by node_id
    issues_by_node: Dict[str, List[Dict[str, Any]]] = {}
    for link in all_links:
        nid = link.get("node_id", "")
        issues_by_node.setdefault(nid, []).append(link)

    # Build dependency map
    dep_map: Dict[str, List[str]] = {}
    for e in module_edges:
        dep_map.setdefault(e["source"], []).append(e["target"])

    # Phase 73.2b: Only include modules with USER ANNOTATIONS.
    # The module list in ambient context already provides structural overview.
    # This section's unique value is showing notes, ACRs, and issue links —
    # curations that the module list doesn't have.
    # Previously: showed all 239 modules with ≥5 files (18K chars, 91% noise).
    # Now: only shows modules the user has annotated (0 chars if no annotations).
    annotated = []

    for m in sorted(modules, key=lambda x: -x.get("file_count", 0)):
        mid = m["module_id"]
        has_notes = bool(notes_by_node.get(mid))
        has_acrs = bool(acrs_by_node.get(mid))
        has_issues = bool(issues_by_node.get(mid))

        if has_notes or has_acrs or has_issues:
            annotated.append(m)

    # No annotations → skip entirely (module list covers structural overview)
    if not annotated:
        return ok({"text": "", "exists": False})

    lines: List[str] = []
    lines.append(f"### Architecture Annotations ({len(annotated)} modules with notes/ACRs)")
    lines.append("")

    for m in annotated:
        mid = m["module_id"]
        name = m.get("name", mid)
        fc = m.get("file_count", 0)
        deps = dep_map.get(mid, [])
        dep_str = ", ".join(deps[:5]) if deps else "none"
        line = f"- **{name}** ({fc} files) → depends on: {dep_str}"
        if len(deps) > 5:
            line += f" (+{len(deps) - 5} more)"
        lines.append(line)

        # Add notes for this module
        for note in notes_by_node.get(mid, []):
            nt = note.get("note_type", "comment")
            prefix = "\U0001f4cc" if nt == "adr" else "\U0001f916" if nt == "agent_note" else "\U0001f4ac"
            lines.append(f"  {prefix} \"{note.get('content', '')}\"")

        # Add ACRs for this module
        for acr in acrs_by_node.get(mid, []):
            lines.append(f"  \u26a0\ufe0f ACR: \"{acr.get('title', '')}\" ({acr.get('status', '')})")

        # Add issue count
        node_issues = issues_by_node.get(mid, [])
        if node_issues:
            open_count = sum(1 for i in node_issues if i.get("status") != "closed")
            lines.append(f"  \U0001f3ab {open_count} open issue(s)")

    lines.append("")

    return ok({"text": "\n".join(lines), "exists": True})


# ── ACR CRUD (Phase B) ────────────────────────────────────────────

@router.get("/projects/{project_id}/architecture/acrs")
def list_acrs(project_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    return ok(mgr.list_acrs())


@router.post("/projects/{project_id}/architecture/acrs")
def create_acr(project_id: str, body: ACRCreate) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    acr = mgr.create_acr(
        title=body.title,
        description=body.description,
        source_type=body.source_type,
        source_agent=body.source_agent,
        affected_nodes=body.affected_nodes,
    )
    return ok(acr)


@router.put("/projects/{project_id}/architecture/acrs/{acr_id}/approve")
def approve_acr(project_id: str, acr_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    acr = mgr.approve_acr(acr_id)
    if not acr:
        raise ApiException(404, "ACR_NOT_FOUND", f"ACR '{acr_id}' not found")
    return ok(acr)


@router.put("/projects/{project_id}/architecture/acrs/{acr_id}/reject")
def reject_acr(project_id: str, acr_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    acr = mgr.reject_acr(acr_id)
    if not acr:
        raise ApiException(404, "ACR_NOT_FOUND", f"ACR '{acr_id}' not found")
    return ok(acr)


# ── Issue Linking (Phase B) ───────────────────────────────────────

@router.get("/projects/{project_id}/architecture/issue-links")
def list_issue_links_endpoint(project_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    return ok(mgr.list_issue_links())


@router.post("/projects/{project_id}/architecture/nodes/{node_id}/link-issue")
def link_issue(project_id: str, node_id: str, body: LinkIssueBody) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    mgr.link_issue(
        node_id=node_id,
        paperclip_issue_id=body.paperclip_issue_id,
        title=body.title,
        priority=body.priority,
        status=body.status,
    )
    return ok({"linked": True})


@router.delete("/projects/{project_id}/architecture/nodes/{node_id}/link-issue/{issue_id}")
def unlink_issue(project_id: str, node_id: str, issue_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    removed = mgr.unlink_issue(node_id, issue_id)
    if not removed:
        raise ApiException(404, "LINK_NOT_FOUND", f"No link for issue '{issue_id}' on node '{node_id}'")
    return ok({"unlinked": True})


# ── Agent Briefing (Phase B) ──────────────────────────────────────

@router.post("/projects/{project_id}/architecture/briefing")
def generate_briefing(project_id: str, body: BriefingRequest) -> Dict[str, Any]:
    """Generate a structured text briefing for an agent about a node."""
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)

    modules = _load_modules(idx_dir)
    arch = _get_arch_state(idx_dir)
    acr_mgr = _get_acr_mgr(idx_dir)

    # Find the target module
    target = None
    for m in modules:
        if m["module_id"] == body.node_id:
            target = m
            break

    if not target:
        raise ApiException(404, "NODE_NOT_FOUND", f"Node '{body.node_id}' not found")

    notes = arch.get_notes_for_node(body.node_id)
    acrs = acr_mgr.get_acrs_for_node(body.node_id)
    issues = acr_mgr.get_issues_for_node(body.node_id)

    # Build dependency info
    trace_edges = _load_trace_edges(idx_dir)
    file_to_module = _build_file_to_module_map(modules)
    module_edges = _aggregate_module_edges(trace_edges, file_to_module)

    deps = [e["target"] for e in module_edges if e["source"] == body.node_id]
    dependents = [e["source"] for e in module_edges if e["target"] == body.node_id]

    lines: List[str] = []
    name = target.get("name", body.node_id)
    lines.append(f"## Agent Briefing: {name}")
    lines.append("")
    lines.append(f"**Module:** {name} ({target.get('file_count', 0)} files)")
    lines.append(f"**Description:** {target.get('summary', 'No description')}")
    lines.append(f"**Dependencies:** {', '.join(deps) if deps else 'none'}")
    lines.append(f"**Depended on by:** {', '.join(dependents) if dependents else 'none'}")

    if notes:
        lines.append("")
        lines.append("**Annotations:**")
        for n in notes:
            prefix = "\U0001f4cc" if n.get("note_type") == "adr" else "\U0001f4ac"
            lines.append(f"  {prefix} {n.get('content', '')}")

    if acrs:
        lines.append("")
        lines.append("**Active ACRs:**")
        for a in acrs:
            lines.append(f"  \u26a0\ufe0f {a['id']}: {a['title']} ({a['status']})")

    if issues:
        lines.append("")
        lines.append("**Linked Issues:**")
        for i in issues:
            lines.append(f"  \U0001f3ab {i['paperclip_issue_id']}: {i['title']} [{i['priority']}] ({i['status']})")

    member_files = target.get("member_files", [])
    if member_files:
        lines.append("")
        lines.append("**Files:**")
        for f in member_files[:20]:
            lines.append(f"  - {f}")
        if len(member_files) > 20:
            lines.append(f"  ... and {len(member_files) - 20} more")

    return ok({"briefing": "\n".join(lines)})
