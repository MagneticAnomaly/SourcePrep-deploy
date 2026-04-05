"""
Architecture ACR and issue-link lifecycle — Phase 71B

Manages Architecture Change Requests (ACRs) and node-to-Paperclip-issue links.
Persists to JSON files in <index_dir>/architecture/.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ArchitectureACRManager:
    """CRUD for ACRs and issue links, stored as JSON in the architecture dir."""

    def __init__(self, index_dir: Path):
        self._arch_dir = Path(index_dir) / "architecture"
        self._acrs_path = self._arch_dir / "acrs.json"
        self._links_path = self._arch_dir / "issue_links.json"

    def _ensure_dir(self) -> None:
        self._arch_dir.mkdir(parents=True, exist_ok=True)

    # ── ACR persistence ────────────────────────────────────────────

    def _load_acrs(self) -> List[Dict[str, Any]]:
        if not self._acrs_path.exists():
            return []
        try:
            return json.loads(self._acrs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save_acrs(self, acrs: List[Dict[str, Any]]) -> None:
        self._ensure_dir()
        self._acrs_path.write_text(
            json.dumps(acrs, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ── ACR CRUD ───────────────────────────────────────────────────

    def list_acrs(self) -> List[Dict[str, Any]]:
        return self._load_acrs()

    def get_acrs_for_node(self, node_id: str) -> List[Dict[str, Any]]:
        return [a for a in self._load_acrs() if node_id in a.get("affected_nodes", [])]

    def create_acr(
        self,
        title: str,
        description: str,
        source_type: str,
        source_agent: str,
        affected_nodes: List[str],
    ) -> Dict[str, Any]:
        acrs = self._load_acrs()
        now = datetime.now(timezone.utc).isoformat()
        acr: Dict[str, Any] = {
            "id": f"acr_{uuid.uuid4().hex[:12]}",
            "title": title,
            "description": description,
            "status": "proposed",
            "source_type": source_type,
            "source_agent": source_agent,
            "affected_nodes": affected_nodes,
            "paperclip_issue_id": None,
            "created_at": now,
            "approved_at": None,
            "approved_by": "",
        }
        acrs.append(acr)
        self._save_acrs(acrs)
        return acr

    def approve_acr(
        self, acr_id: str, approved_by: str = "user"
    ) -> Optional[Dict[str, Any]]:
        acrs = self._load_acrs()
        for acr in acrs:
            if acr["id"] == acr_id:
                acr["status"] = "approved"
                acr["approved_at"] = datetime.now(timezone.utc).isoformat()
                acr["approved_by"] = approved_by
                self._save_acrs(acrs)
                return acr
        return None

    def reject_acr(self, acr_id: str) -> Optional[Dict[str, Any]]:
        acrs = self._load_acrs()
        for acr in acrs:
            if acr["id"] == acr_id:
                acr["status"] = "rejected"
                self._save_acrs(acrs)
                return acr
        return None

    def set_acr_issue(self, acr_id: str, paperclip_issue_id: str) -> Optional[Dict[str, Any]]:
        acrs = self._load_acrs()
        for acr in acrs:
            if acr["id"] == acr_id:
                acr["paperclip_issue_id"] = paperclip_issue_id
                self._save_acrs(acrs)
                return acr
        return None

    # ── Issue link persistence ─────────────────────────────────────

    def _load_links(self) -> List[Dict[str, Any]]:
        if not self._links_path.exists():
            return []
        try:
            return json.loads(self._links_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save_links(self, links: List[Dict[str, Any]]) -> None:
        self._ensure_dir()
        self._links_path.write_text(
            json.dumps(links, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ── Issue link CRUD ────────────────────────────────────────────

    def list_issue_links(self) -> List[Dict[str, Any]]:
        return self._load_links()

    def get_issues_for_node(self, node_id: str) -> List[Dict[str, Any]]:
        return [link for link in self._load_links() if link.get("node_id") == node_id]

    def link_issue(
        self,
        node_id: str,
        paperclip_issue_id: str,
        title: str,
        priority: str,
        status: str,
    ) -> Dict[str, Any]:
        links = self._load_links()
        link: Dict[str, Any] = {
            "node_id": node_id,
            "paperclip_issue_id": paperclip_issue_id,
            "title": title,
            "priority": priority,
            "status": status,
        }
        links.append(link)
        self._save_links(links)
        return link

    def unlink_issue(self, node_id: str, paperclip_issue_id: str) -> bool:
        links = self._load_links()
        original_len = len(links)
        links = [
            link for link in links
            if not (link.get("node_id") == node_id and link.get("paperclip_issue_id") == paperclip_issue_id)
        ]
        if len(links) < original_len:
            self._save_links(links)
            return True
        return False
