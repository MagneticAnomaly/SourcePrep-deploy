"""
Trace data models and extension/language constants.

Contains: TraceNode, TraceEdge, FileError, TraceBuildResult,
all language extension sets, and SUPPORTED_LANGUAGES.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


TRACE_MANIFEST_VERSION = "1.0"

PYTHON_EXTENSIONS = {".py"}
TYPESCRIPT_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}
GO_EXTENSIONS = {".go"}
RUST_EXTENSIONS = {".rs"}
JAVA_EXTENSIONS = {".java"}
CPP_EXTENSIONS = {".c", ".cpp", ".cc", ".h", ".hpp"}
SWIFT_EXTENSIONS = {".swift"}
MARKDOWN_EXTENSIONS = {".md", ".markdown"}
KOTLIN_EXTENSIONS = {".kt", ".kts"}
CSHARP_EXTENSIONS = {".cs"}
RUBY_EXTENSIONS = {".rb"}
PHP_EXTENSIONS = {".php"}
DART_EXTENSIONS = {".dart"}
SCALA_EXTENSIONS = {".scala", ".sc"}
SHELL_EXTENSIONS = {".sh", ".bash", ".zsh"}
LUA_EXTENSIONS = {".lua"}
ZIG_EXTENSIONS = {".zig"}
ELIXIR_EXTENSIONS = {".ex", ".exs"}

SUPPORTED_EXTENSIONS = (
    PYTHON_EXTENSIONS | TYPESCRIPT_EXTENSIONS | GO_EXTENSIONS
    | RUST_EXTENSIONS | JAVA_EXTENSIONS | CPP_EXTENSIONS | SWIFT_EXTENSIONS
    | MARKDOWN_EXTENSIONS | KOTLIN_EXTENSIONS | CSHARP_EXTENSIONS
    | RUBY_EXTENSIONS | PHP_EXTENSIONS | DART_EXTENSIONS | SCALA_EXTENSIONS
    | SHELL_EXTENSIONS | LUA_EXTENSIONS | ZIG_EXTENSIONS | ELIXIR_EXTENSIONS
)


@dataclass
class TraceNode:
    id: str
    kind: str  # file | symbol | external_module
    name: str
    file_path: str  # repo-relative, POSIX separators
    span: Optional[Dict[str, int]]  # {start_line, end_line} or None
    language: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "file_path": self.file_path,
            "span": self.span,
            "language": self.language,
            "metadata": self.metadata,
        }


@dataclass
class TraceEdge:
    id: str
    kind: str  # contains | imports | calls | implements | documented_by
    source: str
    target: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "source": self.source,
            "target": self.target,
            "metadata": self.metadata,
        }


@dataclass
class FileError:
    file_path: str
    error_type: str
    message: str


@dataclass
class TraceBuildResult:
    nodes: List[TraceNode]
    edges: List[TraceEdge]
    files_parsed: int
    files_failed: int
    file_errors: List[FileError]


SUPPORTED_LANGUAGES = [
    "python", "typescript", "javascript", "go", "rust", "java", "c", "cpp",
    "swift", "markdown", "kotlin", "csharp", "ruby", "php", "dart", "scala",
    "shell", "lua", "zig", "elixir",
]
