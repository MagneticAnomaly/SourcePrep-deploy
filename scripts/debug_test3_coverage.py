
import sys
import os
import json
from pathlib import Path

# Add src to sys.path
sys.path.append("/Volumes/4TB-BAD/HumanAI/CoDRAG/src")

from codrag.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES
from codrag.core.trace import compute_trace_coverage

TEST3_PATH = "/Volumes/4TB-BAD/HumanAI/CoDRAG/TEST3"
INDEX_DIR = "/tmp/codrag_debug_test3" # Fake index dir

os.makedirs(INDEX_DIR, exist_ok=True)

print(f"DEFAULT_EXCLUDE_DIR_NAMES contains 'Pods': {'Pods' in DEFAULT_EXCLUDE_DIR_NAMES}")
print(f"DEFAULT_EXCLUDE_DIR_NAMES contains 'node_modules': {'node_modules' in DEFAULT_EXCLUDE_DIR_NAMES}")

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
        print("\nTop 20 found files:")
        for f in coverage['untraced'][:20]:
            print(f['path'])
            
except Exception as e:
    print(f"Error: {e}")
