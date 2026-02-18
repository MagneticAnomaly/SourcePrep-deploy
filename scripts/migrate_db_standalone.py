
import json
import sqlite3
import os
from pathlib import Path

# Expanded list matching the recent code updates
DEFAULT_EXCLUDE_DIR_NAMES = {
    ".git", ".svn", ".hg", "CVS", ".DS_Store", ".codrag",
    "node_modules", "bower_components", "jspm_packages", ".npm", ".yarn",
    "__pycache__", ".venv", "venv", "fresh_venv", "env", ".env", ".tox", ".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov", ".coverage",
    ".gradle", ".idea",
    "obj", ".vs",
    "cmake-build-debug", "cmake-build-release",
    "Pods", "Carthage", "DerivedData", ".xcworkspace",
    "vendor",
    ".next", "_next", ".nuxt", ".output", ".vercel", ".netlify", ".turbo", ".cache", ".parcel-cache", "dist", "build", "target", "out", "coverage"
}

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
        # Add common file excludes too
        default_excludes.update({
            "**/*.lock", "**/*.log", "**/.DS_Store"
        })
        
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
                print(f"Updated project '{name}' ({pid})")
                print(f"  Added {len(new_excludes) - len(current_excludes)} new patterns.")
            else:
                print(f"Project '{name}' is already up-to-date.")
                
        conn.commit()
        print(f"\nMigration complete. Updated {updated_count} projects.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
