
import json
import os
from pathlib import Path

# Hardcoded paths based on context
PROJ_ID = "5516bc49-4911-4e2f-8394-3dae060978ae"
# The user's registry db showed the path is /Volumes/4TB-BAD/HumanAI/CoDRAG/TEST3
# The index dir usually is in ~/.local/share/codrag/indexes/{uuid} OR inside the repo if embedded?
# Wait, the previous tool output for list_dir codrag_data showed codrag_settings.db but no indexes folder.
# The indexes might be in ~/.local/share/codrag/indexes/
# Let's check typical location.

INDEX_DIR_LOCAL = Path(os.path.expanduser("~/.local/share/codrag/indexes")) / PROJ_ID

def debug_pending():
    print(f"Checking index dir: {INDEX_DIR_LOCAL}")
    if not INDEX_DIR_LOCAL.exists():
        print("Index dir does not exist.")
        return

    # 1. Trace Manifest
    trace_path = INDEX_DIR_LOCAL / "trace_manifest.json"
    traced_files = set()
    if trace_path.exists():
        try:
            with open(trace_path, "r") as f:
                data = json.load(f)
                files_map = data.get("files", {})
                traced_files = set(files_map.keys())
            print(f"Trace Manifest: {len(traced_files)} files")
        except Exception as e:
            print(f"Error reading trace manifest: {e}")
    else:
        print("trace_manifest.json not found")

    # 2. Knowledge Docs
    knowledge_path = INDEX_DIR_LOCAL / "knowledge_documents.json"
    embedded_files = set()
    if knowledge_path.exists():
        try:
            with open(knowledge_path, "r") as f:
                docs = json.load(f)
                for doc in docs:
                    src = doc.get("source_id", "")
                    # Logic to clean source_id to file path
                    # source_id can be "file:path/to/file.py" or "sym:..."
                    
                    if src.startswith("file:"):
                        embedded_files.add(src[5:])
                    elif src.startswith("sym:"):
                        # sym:Name@FilePath:Line
                        if "@" in src:
                            parts = src.split("@", 1)
                            # parts[1] is FilePath:Line
                            file_part = parts[1].rsplit(":", 1)[0]
                            embedded_files.add(file_part)
                    elif src:
                         # fallback
                         embedded_files.add(src)
            print(f"Knowledge Docs: {len(embedded_files)} unique files embedded")
        except Exception as e:
            print(f"Error reading knowledge docs: {e}")
    else:
        print("knowledge_documents.json not found")

    # 3. Compare
    pending = []
    for f in traced_files:
        if f not in embedded_files:
            pending.append(f)
            
    print(f"\nPending Files ({len(pending)}):")
    for p in pending:
        print(f" - {p}")

if __name__ == "__main__":
    debug_pending()
