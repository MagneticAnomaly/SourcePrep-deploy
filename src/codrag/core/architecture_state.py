"""
Architecture state persistence — Phase 71A

Manages layout positions, module overrides, and annotation notes
stored as JSON files in <index_dir>/architecture/.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ArchitectureState:
    """Read/write architecture diagram state for a project."""

    def __init__(self, index_dir: Path):
        self.base_dir = Path(index_dir)
        self._arch_dir = self.base_dir / "architecture"
        self._state_path = self._arch_dir / "graph_state.json"
        self._notes_path = self._arch_dir / "notes.json"

    def _ensure_dir(self) -> None:
        self._arch_dir.mkdir(parents=True, exist_ok=True)

    # ── State (layouts + overrides) ─────────────────────────────────

    def load_state(self) -> Dict[str, Any]:
        if not self._state_path.exists():
            return {"layouts": {}, "module_overrides": {}}
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupt architecture state at %s, returning empty", self._state_path)
            return {"layouts": {}, "module_overrides": {}}

    def save_state(self, state: Dict[str, Any]) -> None:
        self._ensure_dir()
        self._state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Notes ───────────────────────────────────────────────────────

    def _load_notes(self) -> List[Dict[str, Any]]:
        if not self._notes_path.exists():
            return []
        try:
            return json.loads(self._notes_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save_notes(self, notes: List[Dict[str, Any]]) -> None:
        self._ensure_dir()
        self._notes_path.write_text(
            json.dumps(notes, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def list_notes(self) -> List[Dict[str, Any]]:
        return self._load_notes()

    def get_notes_for_node(self, node_id: str) -> List[Dict[str, Any]]:
        return [n for n in self._load_notes() if n.get("node_id") == node_id]

    def create_note(
        self,
        node_id: str,
        content: str,
        note_type: str,
        author: str,
        color: str = "yellow",
    ) -> Dict[str, Any]:
        notes = self._load_notes()
        now = datetime.now(timezone.utc).isoformat()
        note: Dict[str, Any] = {
            "id": f"note_{uuid.uuid4().hex[:12]}",
            "node_id": node_id,
            "content": content,
            "note_type": note_type,
            "author": author,
            "color": color,
            "created_at": now,
            "updated_at": now,
        }
        notes.append(note)
        self._save_notes(notes)
        return note

    def update_note(
        self,
        note_id: str,
        content: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        notes = self._load_notes()
        for note in notes:
            if note["id"] == note_id:
                if content is not None:
                    note["content"] = content
                if color is not None:
                    note["color"] = color
                note["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save_notes(notes)
                return note
        return None

    def delete_note(self, note_id: str) -> bool:
        notes = self._load_notes()
        original_len = len(notes)
        notes = [n for n in notes if n["id"] != note_id]
        if len(notes) < original_len:
            self._save_notes(notes)
            return True
        return False
