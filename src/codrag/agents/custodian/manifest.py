"""Archive manifest persistence for Digital Custodian.
Stores the master index of all archived items to ``<index_dir>/.custodian_manifest.json``."""
from __future__ import annotations
import json, logging, os, tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
_MANIFEST_FILENAME = ".custodian_manifest.json"

@dataclass
class ManifestEntry:
    entry_id: str
    original_paths: List[str]
    archive_path: str
    reason: str
    finding_id: str
    dependent_count: int
    archived_at: str = ""
    cleanup_branch: str = ""
    cleanup_commit: str = ""

    def __post_init__(self) -> None:
        if not self.archived_at:
            self.archived_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> ManifestEntry:
        return cls(
            entry_id=d["entry_id"],
            original_paths=list(d.get("original_paths", [])),
            archive_path=d.get("archive_path", ""),
            reason=d.get("reason", ""),
            finding_id=d.get("finding_id", ""),
            dependent_count=d.get("dependent_count", 0),
            archived_at=d.get("archived_at", ""),
            cleanup_branch=d.get("cleanup_branch", ""),
            cleanup_commit=d.get("cleanup_commit", ""),
        )

class ArchiveManifest:
    def __init__(self, index_dir: Path) -> None:
        self._path = Path(index_dir) / _MANIFEST_FILENAME
        self._entries: Dict[str, ManifestEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._entries = {}
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._entries = {e["entry_id"]: ManifestEntry.from_dict(e) for e in data.get("entries", [])}
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to load manifest: %s", exc)
            self._entries = {}

    def _save(self) -> None:
        data = {"version": 1, "entries": [e.to_dict() for e in self._entries.values()]}
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp", prefix=".manifest_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            Path(tmp).replace(self._path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

    def add_entry(self, entry: ManifestEntry) -> None:
        self._entries[entry.entry_id] = entry
        self._save()

    def get_entry(self, entry_id: str) -> Optional[ManifestEntry]:
        return self._entries.get(entry_id)

    def list_entries(self) -> List[ManifestEntry]:
        return list(self._entries.values())
