
import json
import os
from pathlib import Path

# Hardcoded paths based on previous context
PROJ_ID = "5516bc49-4911-4e2f-8394-3dae060978ae"
INDEX_DIR = Path.home() / ".local" / "share" / "codrag" / "indexes" / PROJ_ID

def debug_trace_status():
    if not INDEX_DIR.exists():
        print(f"Index directory not found: {INDEX_DIR}")
        return

    # 1. Load Trace Manifest (files found in repo)
    trace_path = INDEX_DIR / "trace_manifest.json"
    traced_files = set()
    if trace_path.exists():
        try:
            with open(trace_path, "r") as f:
                data = json.load(f)
                # data["files"] is path -> hash
                traced_files = set(data.get("files", {}).keys())
            print(f"Trace Manifest: {len(traced_files)} files")
        except Exception as e:
            print(f"Error reading trace manifest: {e}")

    # 2. Load Knowledge Docs (files successfully embedded)
    knowledge_path = INDEX_DIR / "knowledge_documents.json"
    embedded_files = set()
    if knowledge_path.exists():
        try:
            with open(knowledge_path, "r") as f:
                docs = json.load(f)
                for doc in docs:
                    src = doc.get("source_id", "")
                    # Extract file path from source_id
                    if src.startswith("file:"):
                        embedded_files.add(src[5:])
                    elif src.startswith("sym:"):
                        # sym:Name@FilePath:Line
                        parts = src.split("@")
                        if len(parts) > 1:
                            path_part = parts[1].rsplit(":", 1)[0]
                            embedded_files.add(path_part)
                    elif src:
                        embedded_files.add(src)
            print(f"Knowledge Docs: {len(embedded_files)} unique files embedded")
        except Exception as e:
            print(f"Error reading knowledge docs: {e}")

    # 3. Find missing
    pending = []
    for f in traced_files:
        if f not in embedded_files:
            pending.append(f)

    print(f"\nPending Files ({len(pending)}):")
    for p in pending:
        print(f" - {p}")

if __name__ == "__main__":
    debug_trace_status()
