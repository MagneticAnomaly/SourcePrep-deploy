"""
Codebase Atlas subsystem for Prep.

Re-exports all public symbols so that ``from prep.core.atlas import X``
continues to work after the split into a subpackage.
"""
from .models import (
    AtlasDocument,
    Segment,
    SegmentDocument,
    SegmentDescriptor,
)
from .prompts import (
    ATLAS_SYSTEM,
    ATLAS_PROMPT,
    ROOT_ATLAS_SYSTEM,
    ROOT_ATLAS_PROMPT,
    SEGMENT_ATLAS_SYSTEM,
    SEGMENT_ATLAS_PROMPT,
)
from .routing import (
    MIN_FILES_FOR_ATLAS,
    MIN_ATLAS_CHARS,
    MAX_ATLAS_CHARS,
    MAX_SEGMENTS,
    MIN_SEGMENT_FILES,
    ROOT_ATLAS_MIN_CHARS,
    ROOT_ATLAS_MAX_CHARS,
    SEGMENT_ATLAS_MIN_CHARS,
    SEGMENT_ATLAS_MAX_CHARS,
    MIN_FILES_FOR_ROUTING,
    MIN_MODULES_FOR_ROUTING,
    ROUTING_MIN_SCORE,
    ROUTING_MAX_SEGMENTS,
    ROUTING_SEGMENT_BOOST,
    compute_atlas_budget,
    compute_root_atlas_budget,
    compute_segments,
    build_routing_descriptors,
    route_query,
)
from .generator import CodebaseAtlas
from .role_vectors import RoleVector, BUILT_IN_ROLES, SYNONYM_CLUSTERS
from .role_resolver import resolve_role
from .role_projection import project_atlas_for_role

__all__ = [
    "AtlasDocument",
    "Segment",
    "SegmentDocument",
    "SegmentDescriptor",
    "CodebaseAtlas",
    "compute_atlas_budget",
    "compute_root_atlas_budget",
    "compute_segments",
    "build_routing_descriptors",
    "route_query",
    "ROUTING_SEGMENT_BOOST",
    "MIN_FILES_FOR_ROUTING",
    "MIN_MODULES_FOR_ROUTING",
    "ROUTING_MIN_SCORE",
    "ROUTING_MAX_SEGMENTS",
    # Role Composition Engine (Phase 64A)
    "RoleVector",
    "BUILT_IN_ROLES",
    "SYNONYM_CLUSTERS",
    "resolve_role",
    "project_atlas_for_role",
]

