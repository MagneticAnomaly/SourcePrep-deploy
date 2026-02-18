
import os
from pathlib import Path

# The exact list we put in repo_profile.py
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

REPO_ROOT = "/Volumes/4TB-BAD/HumanAI/CoDRAG/TEST3"

def count_files_with_pruning(root):
    count = 0
    skipped_dirs = []
    
    print(f"Scanning {root} with pruning...")
    for root_dir, dirs, files in os.walk(root):
        # The logic in trace.py:
        # dirs[:] = [d for d in dirs if d not in _PRUNE_DIRS]
        
        # Capture what we are skipping for debug
        to_remove = [d for d in dirs if d in DEFAULT_EXCLUDE_DIR_NAMES]
        if to_remove:
            skipped_dirs.extend([os.path.join(root_dir, d) for d in to_remove])
            
        # Apply pruning
        dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDE_DIR_NAMES]
        
        count += len(files)
        
    return count, skipped_dirs

if __name__ == "__main__":
    if not os.path.exists(REPO_ROOT):
        print(f"Path not found: {REPO_ROOT}")
        exit(1)
        
    total, skipped = count_files_with_pruning(REPO_ROOT)
    
    print(f"\nTotal files found after pruning: {total}")
    print(f"Skipped {len(skipped)} heavy directories, including:")
    for s in skipped[:10]:
        print(f"  - {s}")
    if len(skipped) > 10:
        print(f"  ... and {len(skipped)-10} more")
        
    # Check specifically for known offenders
    pods = any("Pods" in s for s in skipped)
    node_modules = any("node_modules" in s for s in skipped)
    fresh_venv = any("fresh_venv" in s for s in skipped)
    
    print(f"\nVerified blocks:")
    print(f"  - Pods: {'BLOCKED' if pods else 'NOT FOUND/NOT BLOCKED'}")
    print(f"  - node_modules: {'BLOCKED' if node_modules else 'NOT FOUND/NOT BLOCKED'}")
    print(f"  - fresh_venv: {'BLOCKED' if fresh_venv else 'NOT FOUND/NOT BLOCKED'}")
