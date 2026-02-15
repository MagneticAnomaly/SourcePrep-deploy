
import sys
import os
import shutil
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath("src"))

try:
    from codrag.api.routers.projects import _scan_for_presets
    print("Import successful")
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

def test_scan():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "main.rs").touch()
        (root / "package.json").touch()
        (root / "src").mkdir()
        (root / "src" / "index.ts").touch()
        
        presets = _scan_for_presets(root)
        print(f"Detected presets: {presets}")
        
        if "Rust" in presets and "Web (JS/TS)" in presets:
            print("SUCCESS: Detected Rust and Web")
        else:
            print("FAILURE: Did not detect expected presets")
            sys.exit(1)

if __name__ == "__main__":
    test_scan()
