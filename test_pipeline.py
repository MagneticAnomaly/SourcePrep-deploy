import sys
import time
sys.path.insert(0, "src")

print("1. Importing codrag.server", flush=True)
import codrag.server

print("2. Importing helpers", flush=True)
from codrag.api.routers.trace_routes.enrichment import *
from codrag.services.build_manager import build_manager
from codrag.server import _require_project

print("3. Getting project", flush=True)
project_id = "1d6f0b35-45cb-427b-ae9d-aac3c6371a4b"
proj = _require_project(project_id)

print("4. Getting index", flush=True)
from codrag.core.project_registry import project_index_dir
idx_dir = project_index_dir(proj)

inferred_edges_count = 0
inferred_path = idx_dir / "trace_inferred_edges.jsonl"
print(f"5. Reading inferred path {inferred_path} -> {inferred_path.exists()}", flush=True)
if inferred_path.exists():
    with open(inferred_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip(): inferred_edges_count += 1
print("6. inferred edges:", inferred_edges_count, flush=True)

print("7. Getting augment status", flush=True)
try:
    augment_status = augment_status_project(project_id)
    print("augment keys:", list(augment_status["data"].keys()), flush=True)
except Exception as e:
    print("augment exception:", type(e).__name__, e)

print("8. Getting cluster status", flush=True)
try:
    cluster_status = modules_status_project(project_id)
    print("cluster keys:", list(cluster_status["data"].keys()), flush=True)
except Exception as e:
    print("cluster exception:", type(e).__name__, e)

print("9. Checking orchestrator", flush=True)
from codrag.services.pipeline.orchestrator import STAGE_BUILD_TYPE
from codrag.services.pipeline.stages import StageId
from codrag.services.pipeline_orchestrator import pipeline_orchestrator

for stage_id in list(StageId):
    bt = STAGE_BUILD_TYPE[stage_id]
    if bt:
        print(f"checking slot {stage_id}...", flush=True)
        try:
            slot = pipeline_orchestrator._orchestrator.status(project_id, bt)
            d = slot.to_dict()
            prog = d.get("progress", {})
            if prog:
                print(f"  progress message size: {len(str(prog.get('message', '')))}", flush=True)
            else:
                print(f"  no progress object", flush=True)
        except Exception as e:
            print(f"  exception: {e}", flush=True)

print("ALL DONE", flush=True)
