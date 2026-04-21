"""
Atlas data models.

Contains: AtlasDocument, Segment, SegmentDocument, SegmentDescriptor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AtlasDocument:
    """A cached codebase atlas."""
    content: str
    generated_at: str
    model: str  # "structural" for no-LLM fallback, else LLM model name
    fingerprint: str  # hash for staleness detection
    file_count: int
    module_count: int
    char_count: int
    mode: str  # "llm" or "structural"
    hub_file_hashes: Dict[str, str] = field(default_factory=dict)
    segment_ids: List[str] = field(default_factory=list)  # Phase 70B: tracked for drift detection
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "generated_at": self.generated_at,
            "model": self.model,
            "fingerprint": self.fingerprint,
            "file_count": self.file_count,
            "module_count": self.module_count,
            "char_count": self.char_count,
            "mode": self.mode,
            "hub_file_hashes": self.hub_file_hashes,
            "segment_ids": self.segment_ids,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AtlasDocument":
        return cls(
            content=d.get("content", ""),
            generated_at=d.get("generated_at", ""),
            model=d.get("model", "unknown"),
            fingerprint=d.get("fingerprint", ""),
            file_count=int(d.get("file_count", 0)),
            module_count=int(d.get("module_count", 0)),
            char_count=int(d.get("char_count", 0)),
            mode=d.get("mode", "structural"),
            hub_file_hashes=d.get("hub_file_hashes") or {},
            segment_ids=d.get("segment_ids") or [],
            version=int(d.get("version", 1)),
        )


@dataclass
class Segment:
    """A directory-based grouping of files for segmented atlas generation."""
    id: str           # e.g. "src-prep-core"
    name: str         # e.g. "Core Engine"
    dir_path: str     # e.g. "src/prep/core"
    file_paths: List[str] = field(default_factory=list)
    module_ids: List[str] = field(default_factory=list)
    domain_tags: List[str] = field(default_factory=list)
    file_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "dir_path": self.dir_path,
            "file_paths": self.file_paths,
            "module_ids": self.module_ids,
            "domain_tags": self.domain_tags,
            "file_count": self.file_count,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Segment":
        return cls(
            id=d["id"],
            name=d.get("name", ""),
            dir_path=d.get("dir_path", ""),
            file_paths=d.get("file_paths", []),
            module_ids=d.get("module_ids", []),
            domain_tags=d.get("domain_tags", []),
            file_count=int(d.get("file_count", 0)),
        )


@dataclass
class SegmentDocument:
    """A cached segment atlas for one subsystem."""
    content: str
    generated_at: str
    model: str
    fingerprint: str
    segment_id: str
    segment_name: str
    dir_path: str
    file_count: int
    char_count: int
    mode: str  # "llm" or "structural"
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "generated_at": self.generated_at,
            "model": self.model,
            "fingerprint": self.fingerprint,
            "segment_id": self.segment_id,
            "segment_name": self.segment_name,
            "dir_path": self.dir_path,
            "file_count": self.file_count,
            "char_count": self.char_count,
            "mode": self.mode,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SegmentDocument":
        return cls(
            content=d.get("content", ""),
            generated_at=d.get("generated_at", ""),
            model=d.get("model", "unknown"),
            fingerprint=d.get("fingerprint", ""),
            segment_id=d.get("segment_id", ""),
            segment_name=d.get("segment_name", ""),
            dir_path=d.get("dir_path", ""),
            file_count=int(d.get("file_count", 0)),
            char_count=int(d.get("char_count", 0)),
            mode=d.get("mode", "structural"),
            version=int(d.get("version", 1)),
        )


@dataclass
class SegmentDescriptor:
    """Routing descriptor for one segment.

    The ``covers`` field contains domain vocabulary that gets embedded at
    build time. At query time, the query embedding is compared against
    pre-computed descriptor embeddings to route the query to relevant
    segments *before* the main search runs.
    """
    segment_id: str
    dir_path: str
    name: str
    covers: str          # Domain vocabulary text (this gets embedded)
    key_files: List[str] # Top hub files within segment (trace walk entry points)
    boundaries: List[str] # Cross-segment dependency descriptions
    file_paths: List[str]
    file_count: int
    fingerprint: str
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "dir_path": self.dir_path,
            "name": self.name,
            "covers": self.covers,
            "key_files": self.key_files,
            "boundaries": self.boundaries,
            "file_paths": self.file_paths,
            "file_count": self.file_count,
            "fingerprint": self.fingerprint,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SegmentDescriptor":
        return cls(
            segment_id=d["segment_id"],
            dir_path=d.get("dir_path", ""),
            name=d.get("name", ""),
            covers=d.get("covers", ""),
            key_files=d.get("key_files", []),
            boundaries=d.get("boundaries", []),
            file_paths=d.get("file_paths", []),
            file_count=int(d.get("file_count", 0)),
            fingerprint=d.get("fingerprint", ""),
            generated_at=d.get("generated_at", ""),
        )
