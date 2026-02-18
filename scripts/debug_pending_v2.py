
import json
import os
from pathlib import Path

# Embedded path for TEST3
REPO_ROOT = "/Volumes/4TB-BAD/HumanAI/CoDRAG/TEST3"
INDEX_DIR = Path(REPO_ROOT) / ".codrag"

def debug_pending_embedded():
    print(f"Checking index dir: {INDEX_DIR}")
    if not INDEX_DIR.exists():
        print("Index dir does not exist.")
        return

    # 1. Trace Manifest
    trace_path = INDEX_DIR / "trace_manifest.json"
    traced_files = set()
    if trace_path.exists():
        try:
            with open(trace_path, "r") as f:
                data = json.load(f)
                # FIX: use file_hashes instead of files
                traced_files = set(data.get("file_hashes", {}).keys())
            print(f"Trace Manifest: {len(traced_files)} files")
        except Exception as e:
            print(f"Error reading trace manifest: {e}")
    else:
        print("trace_manifest.json not found")

    # 2. Knowledge Docs
    knowledge_path = INDEX_DIR / "knowledge_documents.json"
    embedded_files = set()
    if knowledge_path.exists():
        try:
            with open(knowledge_path, "r") as f:
                docs = json.load(f)
                for doc in docs:
                    src = doc.get("source_id", "")
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
    else:
        print("knowledge_documents.json not found")

    # 3. Find missing
    pending = []
    for f in traced_files:
        if f not in embedded_files:
            pending.append(f)
            
    print(f"\nPending Files ({len(pending)}):")
    for p in pending:
        print(f" - {p}")

    # Check for reverse (embedded but not traced?)
    extra = []
    for f in embedded_files:
        if f not in traced_files:
            extra.append(f)
    
    if extra:
        print(f"\nExtra Embedded Files ({len(extra)}) [Not in Trace Manifest]:")
        for p in extra[:10]:
            print(f" - {p}")

if __name__ == "__main__":
    debug_pending_embedded()
