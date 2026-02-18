
import sys
import os
import json
from pathlib import Path
from types import ModuleType

# Mock numpy to bypass dependency check
sys.modules['numpy'] = ModuleType('numpy')

# Add src to sys.path
sys.path.append("/Volumes/4TB-BAD/HumanAI/CoDRAG/src")

try:
    from codrag.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES
    from codrag.core.trace import compute_trace_coverage, TraceBuilder
except ImportError as e:
    print(f"ImportError: {e}")
    # Try to verify what's in repo_profile if import fails
    import codrag.core.repo_profile
    print(f"repo_profile has DEFAULT_EXCLUDE_DIR_NAMES: {hasattr(codrag.core.repo_profile, 'DEFAULT_EXCLUDE_DIR_NAMES')}")
    sys.exit(1)

TEST3_PATH = "/Volumes/4TB-BAD/HumanAI/CoDRAG/TEST3"
INDEX_DIR = "/tmp/codrag_debug_test3" 

os.makedirs(INDEX_DIR, exist_ok=True)

print(f"DEFAULT_EXCLUDE_DIR_NAMES len: {len(DEFAULT_EXCLUDE_DIR_NAMES)}")
print(f"Contains 'Pods': {'Pods' in DEFAULT_EXCLUDE_DIR_NAMES}")
print(f"Contains 'node_modules': {'node_modules' in DEFAULT_EXCLUDE_DIR_NAMES}")

# Verify TraceBuilder._PRUNE_DIRS
print(f"TraceBuilder._PRUNE_DIRS len: {len(TraceBuilder._PRUNE_DIRS)}")
print(f"TraceBuilder._PRUNE_DIRS contains 'Pods': {'Pods' in TraceBuilder._PRUNE_DIRS}")

print(f"Scanning {TEST3_PATH}...")

try:
    coverage = compute_trace_coverage(
        repo_root=Path(TEST3_PATH),
        index_dir=Path(INDEX_DIR),
        # simulating the enforced defaults from the router
        exclude_globs=[f"**/{d}/**" for d in DEFAULT_EXCLUDE_DIR_NAMES],
        max_file_bytes=500000
    )
    
    summary = coverage["summary"]
    print("\nCoverage Summary:")
    print(json.dumps(summary, indent=2))
    
    print(f"\nTotal files found: {summary['total']}")
    
    if summary['total'] > 1000:
        print("\nTop 20 found files (that should have been excluded):")
        for f in coverage['untraced'][:20]:
            print(f['path'])
            
except Exception as e:
    print(f"Error during scan: {e}")
