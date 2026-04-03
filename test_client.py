import sys
import time
sys.path.insert(0, "src")

from codrag.server import app
from codrag.services.settings_store import settings
settings.init(".codrag.data/codrag_settings.db")
from fastapi.testclient import TestClient

print("Initializing app...", flush=True)
with TestClient(app) as client:
    print("Sending request to pipeline/status...", flush=True)
    t0 = time.time()
    res = client.get("/projects/1d6f0b35-45cb-427b-ae9d-aac3c6371a4b/pipeline/status")
    t1 = time.time()
    print(f"Request complete in {t1-t0:.2f}s! Status code:", res.status_code, flush=True)
    print("Response content length:", len(res.content), flush=True)
    print(res.content[:500], flush=True)
import json
data = res.json()["data"]
stages = data.get("stages", {})
for k, v in stages.items():
    print(k, ": length", len(json.dumps(v)))
