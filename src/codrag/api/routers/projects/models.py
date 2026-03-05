"""
Pydantic request/response models for the projects router.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class BuildRequest(BaseModel):
    project_root: Optional[str] = None
    repo_root: Optional[str] = None
    roots: Optional[List[str]] = None
    include_globs: Optional[List[str]] = None
    exclude_globs: Optional[List[str]] = None
    max_file_bytes: Optional[int] = None
    hard_limit_bytes: Optional[int] = None
    use_gitignore: bool = False
    included_paths: Optional[List[str]] = None


class PolicyRequest(BaseModel):
    repo_root: Optional[str] = None
    force: bool = False


class WatchRequest(BaseModel):
    repo_root: Optional[str] = None
    debounce_ms: Optional[int] = None
    min_rebuild_gap_ms: Optional[int] = None


class SearchRequest(BaseModel):
    query: str
    k: int = 8
    min_score: float = 0.15
    score_drop_ratio: float = 0.4
    mmr_lambda: float = 0.7
    exclude_paths: List[str] = []


class ContextRequest(BaseModel):
    query: str = ""  # Phase 34 C4: optional — empty triggers ambient context mode
    k: int = 5
    max_chars: int = 12000  # Phase 34c E2: increased from 6000 — LOD compression means more files fit
    include_sources: bool = True
    include_scores: bool = False
    min_score: float = 0.15
    score_drop_ratio: float = 0.4
    mmr_lambda: float = 0.7
    exclude_paths: List[str] = []
    structured: bool = False
    trace_expand: bool = True  # Follow trace edges to include structurally related code (Phase 34: on by default)
    trace_max_chars: int = 4000  # Phase 34c B2: increased from 2000 — trace neighbors are LOD-compressed
    compression: str = "none"  # "none" | "lingua" | "lod"
    compression_level: str = "standard"  # "light" | "standard" | "aggressive"
    compression_target_chars: Optional[int] = None
    compression_timeout_s: float = 30.0
    include_atlas: bool = False  # Explicit opt-in: prepend atlas text to context. Routing (Phase 29B) handles segment selection automatically; atlas text is primarily accessed via the codrag_atlas tool.


class ChunkRequest(BaseModel):
    chunk_id: str


class AddProjectRequest(BaseModel):
    path: str
    name: Optional[str] = None
    mode: str = "standalone"
    index_path: Optional[str] = None


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    path_weights: Optional[Dict[str, float]] = None
    touch: bool = True


class PathWeightsRequest(BaseModel):
    path_weights: Dict[str, float]


class IncludedPathsRequest(BaseModel):
    included_paths: List[str]


class DetectStackResponse(BaseModel):
    recommended_globs: List[str]
    detected_presets: List[str]
    all_presets: Dict[str, List[str]]
