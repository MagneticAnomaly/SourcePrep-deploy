from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterator, List, Sequence, Set, Tuple

DEFAULT_EXCLUDE_DIR_NAMES: Set[str] = {
    ".git",
    ".codrag",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
    ".next",
    ".cache",
    ".mypy_cache",
    ".ruff_cache",
}

DOC_DIR_NAMES: Set[str] = {
    "docs",
    "doc",
    "documentation",
    "design",
    "spec",
    "specs",
    "architecture",
    "arch",
    "adr",
    "adrs",
    "decisions",
    "decision",
    "rfc",
    "rfcs",
}

TEST_DIR_NAMES: Set[str] = {
    "test",
    "tests",
    "__tests__",
    "testing",
}

CODE_DIR_NAMES: Set[str] = {
    "src",
    "lib",
    "app",
    "apps",
    "packages",
    "pkg",
    "server",
    "client",
    "ui",
    "frontend",
    "backend",
    "cmd",
}

DEFAULT_ROLE_WEIGHTS: Dict[str, float] = {
    "code": 1.0,
    "docs": 0.95,
    "tests": 0.98,
    "other": 0.9,
}

MARKER_FILES: Sequence[str] = (
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "Makefile",
)

# ── Stack Presets (Fast Scan) ────────────────────────────────────

STACK_PRESETS: Dict[str, List[str]] = {
    "Web (JS/TS)": ["**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx", "**/*.html", "**/*.css", "**/*.json"],
    "Python": ["**/*.py", "**/*.ipynb"],
    "iOS (Swift/ObjC)": ["**/*.swift", "**/*.h", "**/*.m", "**/*.mm"],
    "Rust": ["**/*.rs", "**/*.toml"],
    "Go": ["**/*.go", "**/*.mod"],
    "Java/Kotlin": ["**/*.java", "**/*.kt", "**/*.kts", "**/*.gradle"],
    "C/C++": ["**/*.c", "**/*.cpp", "**/*.h", "**/*.hpp", "**/*.cc"],
    "C#": ["**/*.cs"],
    "Ruby": ["**/*.rb"],
    "PHP": ["**/*.php"],
    "Shell": ["**/*.sh", "**/*.bash", "**/*.zsh"],
    "Configuration": ["**/*.yaml", "**/*.yml", "**/*.json", "**/*.toml", "**/*.xml", "**/*.ini", "**/*.env"],
    "Documentation": ["**/*.md", "**/*.markdown", "**/*.txt"],
}

# Map extension to preset keys
EXT_TO_PRESET: Dict[str, str] = {
    ".js": "Web (JS/TS)", ".jsx": "Web (JS/TS)", ".ts": "Web (JS/TS)", ".tsx": "Web (JS/TS)", ".html": "Web (JS/TS)", ".css": "Web (JS/TS)",
    ".py": "Python", ".ipynb": "Python",
    ".swift": "iOS (Swift/ObjC)", ".m": "iOS (Swift/ObjC)", ".mm": "iOS (Swift/ObjC)",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java/Kotlin", ".kt": "Java/Kotlin",
    ".c": "C/C++", ".cpp": "C/C++", ".h": "C/C++", ".hpp": "C/C++", ".cc": "C/C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".sh": "Shell", ".bash": "Shell",
    ".yaml": "Configuration", ".yml": "Configuration", ".json": "Configuration", ".xml": "Configuration", ".toml": "Configuration",
    ".md": "Documentation",
}

def scan_for_presets(root: Path) -> List[str]:
    """
    Quickly scan the project root for file extensions to determine active presets.
    Skips common heavy directories to be fast.
    """
    detected_presets = set()
    # Limit depth and directories to avoid slow scans in huge monorepos
    ignore_dirs = {
        ".git", "node_modules", ".venv", "venv", "env", "__pycache__", 
        "dist", "build", "target", ".next", ".idea", ".vscode", "vendor"
    }
    
    try:
        # We'll just walk up to 3 levels deep for speed, or until we find enough evidence
        for dirpath, dirnames, filenames in os.walk(str(root)):
            # Prune ignored dirs
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".")]
            
            for f in filenames:
                ext = Path(f).suffix.lower()
                if ext in EXT_TO_PRESET:
                    detected_presets.add(EXT_TO_PRESET[ext])
            
            pass
    except Exception:
        pass
        
    return list(detected_presets)


CODE_EXTS: Set[str] = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".kts",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".hpp",
    ".cs",
}

DOC_EXTS: Set[str] = {
    ".md",
    ".markdown",
    ".rst",
    ".txt",
}


def classify_rel_path(rel_path: str) -> str:
    p = rel_path.replace("\\", "/").lower()
    parts = [x for x in p.split("/") if x]

    if any(part in TEST_DIR_NAMES for part in parts):
        return "tests"

    ext = Path(p).suffix
    if ext in DOC_EXTS or any(part in DOC_DIR_NAMES for part in parts):
        return "docs"

    if ext in CODE_EXTS or any(part in CODE_DIR_NAMES for part in parts):
        return "code"

    return "other"


def classify_dir_name(name: str) -> Tuple[str, float]:
    n = name.lower().strip("/")
    if n in DOC_DIR_NAMES:
        return "docs", 0.9
    if n in TEST_DIR_NAMES:
        return "tests", 0.9
    if n in CODE_DIR_NAMES:
        return "code", 0.9
    return "other", 0.5


def _iter_repo_files(repo_root: Path, max_depth: int, max_files: int) -> Iterator[Path]:
    seen = 0
    for root, dirs, files in os.walk(repo_root, topdown=True):
        rel_dir = Path(root).resolve().relative_to(repo_root)
        depth = len(rel_dir.parts)

        dirs[:] = [
            d
            for d in dirs
            if d not in DEFAULT_EXCLUDE_DIR_NAMES and not d.startswith(".")
        ]

        if depth >= max_depth:
            dirs[:] = []

        for fn in files:
            if fn.startswith("."):
                continue
            yield Path(root) / fn
            seen += 1
            if seen >= max_files:
                return


def profile_repo(repo_root: Path, max_depth: int = 4, max_files: int = 5000) -> Dict[str, Any]:
    repo_root = Path(repo_root).resolve()

    top_level_dirs: List[str] = []
    if repo_root.exists():
        for child in repo_root.iterdir():
            if child.is_dir() and not child.name.startswith(".") and child.name not in DEFAULT_EXCLUDE_DIR_NAMES:
                top_level_dirs.append(child.name)
    top_level_dirs = sorted(top_level_dirs)

    marker_files = [name for name in MARKER_FILES if (repo_root / name).exists()]

    ext_counts: Counter[str] = Counter()
    for p in _iter_repo_files(repo_root, max_depth=max_depth, max_files=max_files):
        ext = p.suffix.lower()
        if ext:
            ext_counts[ext] += 1

    detected_languages: Set[str] = set()

    if "pyproject.toml" in marker_files or "requirements.txt" in marker_files or ext_counts.get(".py", 0) > 0:
        detected_languages.add("python")

    if "package.json" in marker_files or ext_counts.get(".ts", 0) > 0 or ext_counts.get(".tsx", 0) > 0:
        detected_languages.add("typescript")
    elif ext_counts.get(".js", 0) > 0 or ext_counts.get(".jsx", 0) > 0:
        detected_languages.add("javascript")

    if "go.mod" in marker_files or ext_counts.get(".go", 0) > 0:
        detected_languages.add("go")

    if "Cargo.toml" in marker_files or ext_counts.get(".rs", 0) > 0:
        detected_languages.add("rust")

    if "pom.xml" in marker_files or "build.gradle" in marker_files or ext_counts.get(".java", 0) > 0:
        detected_languages.add("java")

    include_globs: List[str] = []

    if ext_counts.get(".md", 0) > 0 or (repo_root / "README.md").exists() or (repo_root / "docs").exists():
        include_globs.extend(["**/*.md", "**/*.markdown"])

    if ext_counts.get(".rst", 0) > 0:
        include_globs.append("**/*.rst")

    if "python" in detected_languages:
        include_globs.append("**/*.py")

    if "typescript" in detected_languages:
        include_globs.extend(["**/*.ts", "**/*.tsx"])

    if "javascript" in detected_languages:
        include_globs.extend(["**/*.js", "**/*.jsx"])

    if "go" in detected_languages:
        include_globs.append("**/*.go")

    if "rust" in detected_languages:
        include_globs.append("**/*.rs")

    if "java" in detected_languages:
        include_globs.extend(["**/*.java", "**/*.kt", "**/*.kts"])

    include_globs = sorted(set(include_globs))

    exclude_globs: List[str] = [
        "**/.git/**",
        "**/.codrag/**",
        "**/node_modules/**",
        "**/__pycache__/**",
        "**/.venv/**",
        "**/venv/**",
        "**/dist/**",
        "**/build/**",
        "**/target/**",
        "**/.next/**",
        "**/.cache/**",
    ]

    path_roles: List[Dict[str, Any]] = []
    for d in top_level_dirs:
        role, confidence = classify_dir_name(d)
        path_roles.append({"path": d + "/**", "role": role, "confidence": confidence})

    return {
        "repo_root": str(repo_root),
        "top_level_dirs": top_level_dirs,
        "marker_files": marker_files,
        "extension_counts": dict(ext_counts.most_common(30)),
        "detected_languages": sorted(detected_languages),
        "path_roles": path_roles,
        "recommended": {
            "include_globs": include_globs,
            "exclude_globs": exclude_globs,
            "role_weights": dict(DEFAULT_ROLE_WEIGHTS),
        },
    }
