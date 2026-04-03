import json
import sys
import os
sys.path.insert(0, "src")

from codrag.server import app

from codrag.services.settings_store import settings
try:
    settings.init(".codrag.data/codrag_settings.db")
except Exception:
    pass

from fastapi.testclient import TestClient
with TestClient(app) as client:
    res = client.get("/projects/1d6f0b35-45cb-427b-ae9d-aac3c6371a4b/pipeline/status")
    stages = res.json()["data"]["stages"]
    catalogue = stages["catalogue"]
    print("KEYS:", catalogue.keys())
    
    for k, v in catalogue.items():
        if isinstance(v, str):
            print(f"Key {k} is string length {len(v)}")
        elif isinstance(v, dict):
            print(f"Key {k} is dict keys {list(v.keys())} dumped length {len(json.dumps(v))}")
        elif isinstance(v, list):
            print(f"Key {k} is list length {len(v)}")
        else:
            print(f"Key {k} is {type(v)}: {v}")
