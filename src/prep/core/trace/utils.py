"""
Trace utility functions shared across the trace subsystem.

Contains: _detect_language, _to_posix, _is_relevant.
"""
from __future__ import annotations

import os
from fnmatch import fnmatch
from pathlib import Path
from typing import List, Optional

from .models import (
    PYTHON_EXTENSIONS,
    TYPESCRIPT_EXTENSIONS,
    GO_EXTENSIONS,
    RUST_EXTENSIONS,
    JAVA_EXTENSIONS,
    CPP_EXTENSIONS,
    SWIFT_EXTENSIONS,
    MARKDOWN_EXTENSIONS,
    KOTLIN_EXTENSIONS,
    CSHARP_EXTENSIONS,
    RUBY_EXTENSIONS,
    PHP_EXTENSIONS,
    DART_EXTENSIONS,
    SCALA_EXTENSIONS,
    SHELL_EXTENSIONS,
    LUA_EXTENSIONS,
    ZIG_EXTENSIONS,
    ELIXIR_EXTENSIONS,
)


def _detect_language(file_path: str) -> Optional[str]:
    ext = Path(file_path).suffix.lower()
    if ext in PYTHON_EXTENSIONS:
        return "python"
    if ext in TYPESCRIPT_EXTENSIONS:
        return "typescript" if ext in {".ts", ".tsx"} else "javascript"
    if ext in GO_EXTENSIONS:
        return "go"
    if ext in RUST_EXTENSIONS:
        return "rust"
    if ext in JAVA_EXTENSIONS:
        return "java"
    if ext in CPP_EXTENSIONS:
        return "cpp" if ext in {".cpp", ".cc", ".hpp"} else "c"
    if ext in SWIFT_EXTENSIONS:
        return "swift"
    if ext in MARKDOWN_EXTENSIONS:
        return "markdown"
    if ext in KOTLIN_EXTENSIONS:
        return "kotlin"
    if ext in CSHARP_EXTENSIONS:
        return "csharp"
    if ext in RUBY_EXTENSIONS:
        return "ruby"
    if ext in PHP_EXTENSIONS:
        return "php"
    if ext in DART_EXTENSIONS:
        return "dart"
    if ext in SCALA_EXTENSIONS:
        return "scala"
    if ext in SHELL_EXTENSIONS:
        return "shell"
    if ext in LUA_EXTENSIONS:
        return "lua"
    if ext in ZIG_EXTENSIONS:
        return "zig"
    if ext in ELIXIR_EXTENSIONS:
        return "elixir"
    return None


def _to_posix(path: str) -> str:
    return path.replace("\\", "/")


def _is_relevant(rel_posix: str, include_globs: List[str], exclude_globs: List[str]) -> bool:
    base = os.path.basename(rel_posix)

    def _matches(pattern: str) -> bool:
        patterns = [pattern]
        if pattern.startswith("**/"):
            patterns.append(pattern[3:])
        for p in patterns:
            if fnmatch(rel_posix, p) or fnmatch(base, p):
                return True
        return False

    included = False
    if not include_globs:
        included = True
    else:
        for g in include_globs:
            if _matches(g):
                included = True
                break
    if not included:
        return False

    for g in exclude_globs:
        if _matches(g):
            return False
    return True
