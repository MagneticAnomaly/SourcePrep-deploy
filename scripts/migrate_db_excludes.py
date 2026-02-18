"""
Migration script to update all existing projects in registry.db with robust exclude patterns.
"""
import json
import sqlite3
from pathlib import Path
from codrag.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES

DB_PATH = Path.home() / ".local" / "share" / "codrag" / "registry.db"

def migrate():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return

    print(f"Migrating projects in {DB_PATH}...")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    try:
        projects = conn.execute("SELECT id, name, config FROM projects").fetchall()
        updated_count = 0
        
        default_excludes = {f"**/{d}/**" for d in DEFAULT_EXCLUDE_DIR_NAMES}
        
        for p in projects:
            pid = p["id"]
            name = p["name"]
            config_raw = p["config"]
            
            try:
                config = json.loads(config_raw) if config_raw else {}
            except Exception:
                config = {}
                
            current_excludes = set(config.get("exclude_globs") or [])
            
            # Check if missing any defaults
            if not default_excludes.issubset(current_excludes):
                new_excludes = sorted(list(current_excludes | default_excludes))
                config["exclude_globs"] = new_excludes
                
                conn.execute(
                    "UPDATE projects SET config = ? WHERE id = ?",
                    (json.dumps(config), pid)
                )
                updated_count += 1
                print(f"Updated project '{name}' ({pid}) with new excludes.")
            else:
                print(f"Project '{name}' already has up-to-date excludes.")
                
        conn.commit()
        print(f"Migration complete. Updated {updated_count} projects.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
