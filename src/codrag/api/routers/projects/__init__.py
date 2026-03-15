"""
Projects router subpackage — assembles all sub-routers into a composite router.

The composite ``router`` object is what ``server.py`` mounts, so no changes
are needed to the server's router registration logic.
"""
from fastapi import APIRouter

from . import crud, watch, files, build, search, atlas_endpoints, pipeline_history

router = APIRouter()

router.include_router(crud.router)
router.include_router(watch.router)
router.include_router(files.router)
router.include_router(build.router)
router.include_router(search.router)
router.include_router(atlas_endpoints.router)
router.include_router(pipeline_history.router)

# ── Backward-compat re-exports ────────────────────────────────────
# Tests and other modules import symbols directly from this package.
from .crud import add_project  # noqa: F401
from .models import (  # noqa: F401
    AddProjectRequest,
    BuildRequest,
    ContextRequest,
    SearchRequest,
    WatchRequest,
    UpdateProjectRequest,
    PathWeightsRequest,
    IncludedPathsRequest,
    ChunkRequest,
    PolicyRequest,
    DetectStackResponse,
)
from .search import _inject_observations  # noqa: F401
from .helpers import _srv, _get_project_globs  # noqa: F401
