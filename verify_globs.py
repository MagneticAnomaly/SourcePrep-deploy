
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath("src"))

from codrag.core.trace import TraceBuilder

def verify():
    # create a dummy builder
    builder = TraceBuilder(Path("."), Path(".codrag"))
    
    # Check includes
    includes = builder.include_globs
    print("Include globs:", includes)
    
    required = ["**/*.swift", "**/*.go", "**/*.rs"]
    missing = [r for r in required if r not in includes]
    
    if missing:
        print(f"FAILED: Missing required globs: {missing}")
        sys.exit(1)
    
    print("SUCCESS: All required globs present.")
    
    # Also verify that .swift file would be detected as relevant
    from codrag.core.trace import _is_relevant
    if _is_relevant("Sources/App/File.swift", includes, builder.exclude_globs):
        print("SUCCESS: .swift file is relevant")
    else:
        print("FAILED: .swift file NOT relevant")
        sys.exit(1)

if __name__ == "__main__":
    verify()
