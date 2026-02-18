
import sys
import json
import os
from pathlib import Path

# Mock modules
sys.path.append("/Volumes/4TB-BAD/HumanAI/CoDRAG/src")
from codrag.core.project_registry import project_index_dir

# Mock Project object
class Project:
    def __init__(self, id, path, config):
        self.id = id
        self.path = path
        self.config = config

PROJ_ID = "5516bc49-4911-4e2f-8394-3dae060978ae"
PROJ_PATH = "/Volumes/4TB-BAD/HumanAI/CoDRAG/TEST3"

def find_pending_file():
    idx_dir = Path.home() / ".local" / "share" / "codrag" / "indexes" / PROJ_ID
    
    # 1. Load Trace Manifest
    trace_manifest_path = idx_dir / "trace_manifest.json"
    if not trace_manifest_path.exists():
        print("No trace manifest found.")
        return

    with open(trace_manifest_path, "r") as f:
        trace_data = json.load(f)
        # trace_data is { "files": { "path": "hash", ... }, ... }
        # traced_files keys are the paths
        traced_paths = set(trace_data.get("files", {}).keys())

    print(f"Total traced files in manifest: {len(traced_paths)}")

    # 2. Load Knowledge Docs (Embedded)
    embedded_paths = set()
    knowledge_docs_path = idx_dir / "knowledge_documents.json"
    if knowledge_docs_path.exists():
        with open(knowledge_docs_path, "r") as f:
            docs = json.load(f)
            for doc in docs:
                src = doc.get("source_id") or ""
                if not src: continue
                
                # Logic from router/trace.py
                if src.startswith("file:"):
                    embedded_paths.add(src[5:])
                elif src.startswith("sym:"):
                    at_idx = src.find("@")
                    if at_idx >= 0:
                        rest = src[at_idx + 1:]
                        colon_idx = rest.rfind(":")
                        if colon_idx > 0:
                            embedded_paths.add(rest[:colon_idx])
                        else:
                            embedded_paths.add(rest)
                else:
                    embedded_paths.add(src)
    
    print(f"Total embedded paths found: {len(embedded_paths)}")

    # 3. Find the difference
    pending = []
    for p in traced_paths:
        if p not in embedded_paths:
            pending.append(p)
            
    print(f"\nPending Files ({len(pending)}):")
    for p in pending:
        print(f" - {p}")

if __name__ == "__main__":
    find_pending_file()
