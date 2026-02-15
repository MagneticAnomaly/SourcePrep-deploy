"""
Trace Index Builder for CoDRAG.

Builds a structural graph of files, symbols, and relationships.
Deterministic output with stable IDs and ordered serialization.
"""
from __future__ import annotations

import ast
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import pathspec

from .ids import (
    stable_edge_id,
    stable_external_module_id,
    stable_file_hash,
    stable_file_node_id,
    stable_symbol_node_id,
)

logger = logging.getLogger(__name__)

# --- Rust engine availability (set in __init__.py) ---
try:
    from . import ENGINE as _ENGINE, _rust_engine
except ImportError:
    _ENGINE = "python"
    _rust_engine = None

TRACE_MANIFEST_VERSION = "1.0"

PYTHON_EXTENSIONS = {".py"}
TYPESCRIPT_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}
GO_EXTENSIONS = {".go"}
RUST_EXTENSIONS = {".rs"}
JAVA_EXTENSIONS = {".java"}
CPP_EXTENSIONS = {".c", ".cpp", ".cc", ".h", ".hpp"}
SWIFT_EXTENSIONS = {".swift"}

SUPPORTED_EXTENSIONS = (
    PYTHON_EXTENSIONS | TYPESCRIPT_EXTENSIONS | GO_EXTENSIONS
    | RUST_EXTENSIONS | JAVA_EXTENSIONS | CPP_EXTENSIONS | SWIFT_EXTENSIONS
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


SUPPORTED_LANGUAGES = ["python", "typescript", "javascript", "go", "rust", "java", "c", "cpp", "swift"]


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


class PythonAnalyzer:
    """
    Python AST-based analyzer for extracting symbols and imports.
    """

    def __init__(self, file_path: str, source: str, repo_root: Path):
        self.file_path = file_path
        self.source = source
        self.repo_root = repo_root
        self.nodes: List[TraceNode] = []
        self.edges: List[TraceEdge] = []
        self._file_node_id = stable_file_node_id(file_path)

    def analyze(self) -> Tuple[List[TraceNode], List[TraceEdge]]:
        try:
            tree = ast.parse(self.source, filename=self.file_path)
        except SyntaxError as e:
            raise ValueError(f"Syntax error: {e}")

        self._extract_symbols(tree)
        self._extract_imports(tree)

        return self.nodes, self.edges

    def _extract_symbols(self, tree: ast.Module) -> None:
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                self._add_function(node, is_async=False, parent_qualname=None)
            elif isinstance(node, ast.AsyncFunctionDef):
                self._add_function(node, is_async=True, parent_qualname=None)
            elif isinstance(node, ast.ClassDef):
                self._add_class(node)

    def _add_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool, parent_qualname: Optional[str]
    ) -> None:
        name = node.name
        qualname = f"{parent_qualname}.{name}" if parent_qualname else name
        start_line = node.lineno
        end_line = node.end_lineno or node.lineno

        symbol_type = "async_method" if is_async and parent_qualname else "method" if parent_qualname else "async_function" if is_async else "function"
        is_public = not name.startswith("_")

        decorators = [self._decorator_name(d) for d in node.decorator_list]
        docstring = ast.get_docstring(node)
        if docstring and len(docstring) > 500:
            docstring = docstring[:497] + "..."

        node_id = stable_symbol_node_id(qualname, self.file_path, start_line)
        trace_node = TraceNode(
            id=node_id,
            kind="symbol",
            name=name,
            file_path=self.file_path,
            span={"start_line": start_line, "end_line": end_line},
            language="python",
            metadata={
                "symbol_type": symbol_type,
                "qualname": qualname,
                "is_async": is_async,
                "is_public": is_public,
                "decorators": decorators if decorators else None,
                "docstring": docstring,
            },
        )
        self.nodes.append(trace_node)

        edge_id = stable_edge_id("contains", self._file_node_id, node_id)
        self.edges.append(
            TraceEdge(id=edge_id, kind="contains", source=self._file_node_id, target=node_id, metadata={"confidence": 1.0})
        )

    def _add_class(self, node: ast.ClassDef) -> None:
        name = node.name
        qualname = name
        start_line = node.lineno
        end_line = node.end_lineno or node.lineno

        is_public = not name.startswith("_")
        decorators = [self._decorator_name(d) for d in node.decorator_list]
        docstring = ast.get_docstring(node)
        if docstring and len(docstring) > 500:
            docstring = docstring[:497] + "..."

        node_id = stable_symbol_node_id(qualname, self.file_path, start_line)
        trace_node = TraceNode(
            id=node_id,
            kind="symbol",
            name=name,
            file_path=self.file_path,
            span={"start_line": start_line, "end_line": end_line},
            language="python",
            metadata={
                "symbol_type": "class",
                "qualname": qualname,
                "is_public": is_public,
                "decorators": decorators if decorators else None,
                "docstring": docstring,
            },
        )
        self.nodes.append(trace_node)

        edge_id = stable_edge_id("contains", self._file_node_id, node_id)
        self.edges.append(
            TraceEdge(id=edge_id, kind="contains", source=self._file_node_id, target=node_id, metadata={"confidence": 1.0})
        )

        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef):
                self._add_function(child, is_async=False, parent_qualname=qualname)
            elif isinstance(child, ast.AsyncFunctionDef):
                self._add_function(child, is_async=True, parent_qualname=qualname)

    def _decorator_name(self, node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{self._decorator_name(node.value)}.{node.attr}"
        if isinstance(node, ast.Call):
            return self._decorator_name(node.func)
        return "?"

    def _extract_imports(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._add_import_edge(alias.name, node.lineno)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                level = node.level
                if level > 0:
                    self._add_relative_import(module, level, node.lineno)
                else:
                    self._add_import_edge(module, node.lineno)

    def _add_import_edge(self, module: str, lineno: int) -> None:
        resolved_path = self._resolve_import(module)
        if resolved_path:
            target_id = stable_file_node_id(resolved_path)
            disambiguator = f"{module}:{lineno}"
            edge_id = stable_edge_id("imports", self._file_node_id, target_id, disambiguator)
            self.edges.append(
                TraceEdge(
                    id=edge_id,
                    kind="imports",
                    source=self._file_node_id,
                    target=target_id,
                    metadata={"confidence": 1.0, "import": module, "line": lineno},
                )
            )
        else:
            ext_id = stable_external_module_id(module)
            disambiguator = f"{module}:{lineno}"
            edge_id = stable_edge_id("imports", self._file_node_id, ext_id, disambiguator)
            self.edges.append(
                TraceEdge(
                    id=edge_id,
                    kind="imports",
                    source=self._file_node_id,
                    target=ext_id,
                    metadata={"confidence": 0.5, "import": module, "line": lineno, "external": True},
                )
            )

    def _add_relative_import(self, module: str, level: int, lineno: int) -> None:
        file_dir = Path(self.file_path).parent
        for _ in range(level - 1):
            file_dir = file_dir.parent

        if module:
            parts = module.split(".")
            target_rel = file_dir / "/".join(parts)
        else:
            target_rel = file_dir

        candidates = [
            f"{target_rel}.py",
            f"{target_rel}/__init__.py",
        ]

        resolved = None
        for c in candidates:
            c_posix = _to_posix(str(c))
            full = self.repo_root / c_posix
            if full.exists():
                resolved = c_posix
                break

        if resolved:
            target_id = stable_file_node_id(resolved)
            import_str = "." * level + (module or "")
            disambiguator = f"{import_str}:{lineno}"
            edge_id = stable_edge_id("imports", self._file_node_id, target_id, disambiguator)
            self.edges.append(
                TraceEdge(
                    id=edge_id,
                    kind="imports",
                    source=self._file_node_id,
                    target=target_id,
                    metadata={"confidence": 1.0, "import": import_str, "line": lineno, "relative": True},
                )
            )

    def _resolve_import(self, module: str) -> Optional[str]:
        parts = module.split(".")
        candidates = [
            "/".join(parts) + ".py",
            "/".join(parts) + "/__init__.py",
        ]

        for c in candidates:
            full = self.repo_root / c
            if full.exists():
                return c
        return None


class SwiftAnalyzer:
    """
    Regex-based Swift analyzer for extracting symbols and imports.
    """

    def __init__(self, file_path: str, source: str, repo_root: Path):
        self.file_path = file_path
        self.source = source
        self.repo_root = repo_root
        self.nodes: List[TraceNode] = []
        self.edges: List[TraceEdge] = []
        self._file_node_id = stable_file_node_id(file_path)

    def analyze(self) -> Tuple[List[TraceNode], List[TraceEdge]]:
        import re
        
        # Imports: import Module
        # Regex for 'import Module' or 'import class Module.Class'
        # Simplified: just grab the last part or second token
        import_pattern = re.compile(r"^\s*import\s+([a-zA-Z0-9_.]+)", re.MULTILINE)
        for match in import_pattern.finditer(self.source):
            module = match.group(1).strip()
            # If 'import class Module.Thing', module might be 'class' which is wrong.
            # Swift syntax: import [kind] Module.Submodule
            # Let's be slightly smarter.
            line_start = match.start()
            line = self.source[line_start:self.source.find('\n', line_start)].strip()
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "import":
                # Handle 'import kind module' vs 'import module'
                target = parts[-1] # The last part is usually the module/symbol
                if target and not target.startswith("@"): # Ignore attributes if any (unlikely on import line)
                     self._add_import(target, self.source.count('\n', 0, match.start()) + 1)

        # Symbols: class, struct, enum, protocol, extension, func
        # We want top-level and nested (maybe just regex scan for keywords?)
        # Regex is fragile for nesting, but good enough for basic flat list of symbols.
        # Captures: (attributes)? (visibility)? (kind) (name)
        # e.g. "public class MyClass", "struct MyStruct", "func myFunc"
        
        # Regex breakdown:
        # ^\s* -> start of line, optional whitespace
        # (?:[\w@]+\s+)* -> optional attributes/modifiers (public, @objc, etc) non-capturing
        # (class|struct|enum|protocol|extension|func)\s+ -> kind
        # ([a-zA-Z0-9_]+) -> name
        
        symbol_pattern = re.compile(
            r"^\s*(?:[\w@]+\s+)*(class|struct|enum|protocol|extension|func)\s+([a-zA-Z0-9_]+)", 
            re.MULTILINE
        )
        
        for match in symbol_pattern.finditer(self.source):
            kind = match.group(1)
            name = match.group(2)
            start_line = self.source.count('\n', 0, match.start()) + 1
            
            # Rough estimation of end line (next empty line or closing brace? Indentation?)
            # For regex analyzer, we often default end_line = start_line to avoid complex parsing.
            end_line = start_line 
            
            # Extensions don't have a name usually "extension String { ... }"
            # If regex matched "extension String", name="String". Correct.
            
            symbol_type = "method" if kind == "func" else "class" # Simplification
            if kind in ("struct", "enum", "protocol"):
                symbol_type = "class" # Map to closest trace model equivalent
            elif kind == "extension":
                symbol_type = "class"

            qualname = name # Flat namespace for regex
            
            node_id = stable_symbol_node_id(qualname, self.file_path, start_line)
            
            trace_node = TraceNode(
                id=node_id,
                kind="symbol",
                name=name,
                file_path=self.file_path,
                span={"start_line": start_line, "end_line": end_line},
                language="swift",
                metadata={
                    "symbol_type": symbol_type,
                    "qualname": qualname,
                    "swift_kind": kind,
                    "is_public": "public" in match.group(0), # Rough heuristic
                },
            )
            self.nodes.append(trace_node)
            
            edge_id = stable_edge_id("contains", self._file_node_id, node_id)
            self.edges.append(
                TraceEdge(
                    id=edge_id, 
                    kind="contains", 
                    source=self._file_node_id, 
                    target=node_id, 
                    metadata={"confidence": 0.8} # Regex is less confident
                )
            )

        return self.nodes, self.edges

    def _add_import(self, module: str, lineno: int) -> None:
        ext_id = stable_external_module_id(module)
        disambiguator = f"{module}:{lineno}"
        edge_id = stable_edge_id("imports", self._file_node_id, ext_id, disambiguator)
        self.edges.append(
            TraceEdge(
                id=edge_id,
                kind="imports",
                source=self._file_node_id,
                target=ext_id,
                metadata={"confidence": 0.8, "import": module, "line": lineno, "external": True},
            )
        )


class TraceBuilder:
    """
    Builds trace index files: trace_manifest.json, trace_nodes.jsonl, trace_edges.jsonl.
    """

    def __init__(
        self,
        repo_root: Path,
        index_dir: Path,
        include_globs: Optional[List[str]] = None,
        exclude_globs: Optional[List[str]] = None,
        max_file_bytes: int = 500_000,
        hard_limit_bytes: int = 100_000_000,
        use_gitignore: bool = False,
        max_files: int = 10_000,
        max_nodes: int = 100_000,
        max_edges: int = 500_000,
        max_failures: int = 50,
    ):
        self.repo_root = Path(repo_root).resolve()
        self.index_dir = Path(index_dir).resolve()
        self.include_globs = include_globs or [
            "**/*.py",
            "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx",
            "**/*.go",
            "**/*.rs",
            "**/*.java",
            "**/*.c", "**/*.cpp", "**/*.h", "**/*.hpp", "**/*.cc",
            "**/*.swift",
        ]
        self.exclude_globs = exclude_globs or [
            "**/node_modules/**",
            "**/.git/**",
            "**/venv/**",
            "**/__pycache__/**",
            "**/dist/**",
            "**/build/**",
        ]
        self.max_file_bytes = max_file_bytes
        self.hard_limit_bytes = hard_limit_bytes
        self.use_gitignore = use_gitignore
        self.max_files = max_files
        self.max_nodes = max_nodes
        self.max_edges = max_edges
        self.max_failures = max_failures

        self.manifest_path = self.index_dir / "trace_manifest.json"
        self.nodes_path = self.index_dir / "trace_nodes.jsonl"
        self.edges_path = self.index_dir / "trace_edges.jsonl"
        self.gitignore_spec = None

    def build(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        changed_paths: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        self.index_dir.mkdir(parents=True, exist_ok=True)

        if _ENGINE == "rust" and _rust_engine is not None:
            return self._build_rust(progress_callback)

        # Load .gitignore if requested
        if self.use_gitignore:
            gitignore_path = self.repo_root / ".gitignore"
            if gitignore_path.exists():
                try:
                    with open(gitignore_path, "r", encoding="utf-8") as f:
                        self.gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
                    logger.info("Loaded .gitignore from %s", gitignore_path)
                except Exception as e:
                    logger.warning("Failed to parse .gitignore: %s", e)

        files = self._enumerate_files()
        if len(files) > self.max_files:
            logger.warning(f"File count {len(files)} exceeds max_files {self.max_files}, truncating")
            files = files[: self.max_files]

        nodes: List[TraceNode] = []
        edges: List[TraceEdge] = []
        external_modules: Dict[str, TraceNode] = {}
        file_errors: List[FileError] = []
        file_hashes: Dict[str, str] = {}  # rel_path -> content hash
        files_parsed = 0
        files_failed = 0

        for i, file_path in enumerate(files):
            if progress_callback:
                progress_callback("trace_scan", i, len(files))

            rel_path = _to_posix(str(file_path.relative_to(self.repo_root)))

            # Read source and compute content hash for staleness detection
            try:
                # Check size for parsing decision
                file_size = file_path.stat().st_size
                is_large = file_size > self.max_file_bytes
                
                if is_large:
                     # For large files, we skip reading full content for hash/parsing
                     # Just hash the path + size + mtime as a proxy? 
                     # Or read a prefix. Let's read prefix for consistency with index.py
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        source = f.read(50_000)
                else:
                    source = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                source = ""
            
            file_hashes[rel_path] = stable_file_hash(source)

            file_node = TraceNode(
                id=stable_file_node_id(rel_path),
                kind="file",
                name=file_path.name,
                file_path=rel_path,
                span=None,
                language=_detect_language(rel_path),
                metadata={"truncated": is_large, "size": file_size} if 'file_size' in locals() else {},
            )
            nodes.append(file_node)

            if is_large:
                # Skip parsing for large files
                continue

            language = _detect_language(rel_path)
            if language == "python":
                try:
                    analyzer = PythonAnalyzer(rel_path, source, self.repo_root)
                    sym_nodes, sym_edges = analyzer.analyze()
                    nodes.extend(sym_nodes)

                    for edge in sym_edges:
                        if edge.metadata.get("external"):
                            ext_name = str(edge.metadata.get("import", ""))
                            if ext_name and ext_name not in external_modules:
                                ext_node = TraceNode(
                                    id=stable_external_module_id(ext_name),
                                    kind="external_module",
                                    name=ext_name,
                                    file_path="",
                                    span=None,
                                    language=None,
                                    metadata={"external": True},
                                )
                                external_modules[ext_name] = ext_node

                    edges.extend(sym_edges)
                    files_parsed += 1
                except Exception as e:
                    files_failed += 1
                    if len(file_errors) < self.max_failures:
                        file_errors.append(FileError(rel_path, type(e).__name__, str(e)))
            elif language == "swift":
                try:
                    analyzer = SwiftAnalyzer(rel_path, source, self.repo_root)
                    sym_nodes, sym_edges = analyzer.analyze()
                    nodes.extend(sym_nodes)

                    for edge in sym_edges:
                        if edge.metadata.get("external"):
                            ext_name = str(edge.metadata.get("import", ""))
                            if ext_name and ext_name not in external_modules:
                                ext_node = TraceNode(
                                    id=stable_external_module_id(ext_name),
                                    kind="external_module",
                                    name=ext_name,
                                    file_path="",
                                    span=None,
                                    language=None,
                                    metadata={"external": True},
                                )
                                external_modules[ext_name] = ext_node

                    edges.extend(sym_edges)
                    files_parsed += 1
                except Exception as e:
                    files_failed += 1
                    if len(file_errors) < self.max_failures:
                        file_errors.append(FileError(rel_path, type(e).__name__, str(e)))
            else:
                files_parsed += 1

            if len(nodes) > self.max_nodes:
                logger.warning(f"Node count exceeds max_nodes {self.max_nodes}, stopping")
                break
            if len(edges) > self.max_edges:
                logger.warning(f"Edge count exceeds max_edges {self.max_edges}, stopping")
                break

        nodes.extend(external_modules.values())

        valid, validation_error = self._validate(nodes, edges)
        if not valid:
            logger.error(f"Trace validation failed: {validation_error}")
            manifest = self._build_manifest(
                nodes_count=0,
                edges_count=0,
                files_parsed=files_parsed,
                files_failed=files_failed,
                file_errors=file_errors,
                last_error=validation_error,
                file_hashes=file_hashes,
            )
            self._write_manifest(manifest)
            return manifest

        self._write_atomic(nodes, edges)

        manifest = self._build_manifest(
            nodes_count=len(nodes),
            edges_count=len(edges),
            files_parsed=files_parsed,
            files_failed=files_failed,
            file_errors=file_errors,
            last_error=None,
            file_hashes=file_hashes,
        )
        self._write_manifest(manifest)

        if progress_callback:
            progress_callback("trace_write", len(files), len(files))

        return manifest

    def _build_rust(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Dict[str, Any]:
        """Delegate trace build to the Rust engine via codrag_engine."""
        import time

        logger.info("Building trace index via Rust engine")
        start = time.monotonic()

        if progress_callback:
            progress_callback("trace_scan", 0, 1)

        try:
            handle = _rust_engine.build_trace(
                str(self.repo_root),
                str(self.index_dir),
                include_globs=self.include_globs,
                exclude_globs=self.exclude_globs,
                max_file_bytes=self.max_file_bytes,
            )
        except Exception as e:
            logger.error(f"Rust engine build failed: {e}")
            manifest = self._build_manifest(
                nodes_count=0,
                edges_count=0,
                files_parsed=0,
                files_failed=0,
                file_errors=[],
                last_error=str(e),
            )
            self._write_manifest(manifest)
            return manifest

        elapsed = time.monotonic() - start
        status = handle.status()
        counts = status.get("counts", {})

        logger.info(
            "Rust engine build complete: %d nodes, %d edges in %.3fs",
            counts.get("nodes", 0),
            counts.get("edges", 0),
            elapsed,
        )

        if progress_callback:
            progress_callback("trace_write", 1, 1)

        # Read the manifest the Rust engine wrote
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {
                "version": TRACE_MANIFEST_VERSION,
                "built_at": status.get("last_build_at", ""),
                "project": {"repo_root": str(self.repo_root)},
                "counts": counts,
                "file_errors": [],
                "last_error": None,
            }

        # Rust engine doesn't write file_hashes — compute them in Python
        # so that compute_trace_coverage can determine traced/untraced/stale.
        if "file_hashes" not in manifest:
            logger.info("Computing file_hashes for Rust-built trace manifest")
            manifest["file_hashes"] = self._compute_file_hashes()
            self._write_manifest(manifest)

        return manifest

    _PRUNE_DIRS = {
        "node_modules", ".git", ".venv", "venv", "__pycache__",
        "dist", "build", ".next", ".tox", ".mypy_cache",
        ".pytest_cache", ".eggs", "egg-info", ".cargo", "target",
    }

    def _compute_file_hashes(self) -> Dict[str, str]:
        """Compute content hashes for all eligible files (used to backfill Rust manifests)."""
        files = self._enumerate_files()
        file_hashes: Dict[str, str] = {}
        for file_path in files:
            rel_path = _to_posix(str(file_path.relative_to(self.repo_root)))
            try:
                file_size = file_path.stat().st_size
                if file_size > self.max_file_bytes:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        source = f.read(50_000)
                else:
                    source = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                source = ""
            file_hashes[rel_path] = stable_file_hash(source)
        return file_hashes

    def _enumerate_files(self) -> List[Path]:
        all_files: List[Path] = []

        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in self._PRUNE_DIRS]
            root_path = Path(root)
            for fname in files:
                file_path = root_path / fname
                rel_path = _to_posix(str(file_path.relative_to(self.repo_root)))

                if file_path.is_symlink():
                    continue

                if not _is_relevant(rel_path, self.include_globs, self.exclude_globs):
                    continue

                if self.gitignore_spec and self.gitignore_spec.match_file(rel_path):
                    continue

                try:
                    if file_path.stat().st_size > self.hard_limit_bytes:
                        continue
                except OSError:
                    continue

                all_files.append(file_path)

        all_files.sort(key=lambda p: _to_posix(str(p.relative_to(self.repo_root))))
        return all_files

    def _validate(self, nodes: List[TraceNode], edges: List[TraceEdge]) -> Tuple[bool, Optional[str]]:
        node_ids: Set[str] = set()
        for n in nodes:
            if n.id in node_ids:
                return False, f"Duplicate node ID: {n.id}"
            node_ids.add(n.id)

            if n.file_path and (n.file_path.startswith("/") or "\\" in n.file_path):
                return False, f"Non-portable file_path in node {n.id}: {n.file_path}"

        edge_ids: Set[str] = set()
        for e in edges:
            if e.id in edge_ids:
                return False, f"Duplicate edge ID: {e.id}"
            edge_ids.add(e.id)

            if e.source not in node_ids:
                return False, f"Edge {e.id} references unknown source: {e.source}"
            if e.target not in node_ids:
                return False, f"Edge {e.id} references unknown target: {e.target}"

        return True, None

    def _sort_nodes(self, nodes: List[TraceNode]) -> List[TraceNode]:
        def sort_key(n: TraceNode) -> Tuple[int, str, int, str]:
            kind_order = {"file": 0, "symbol": 1, "external_module": 2}
            start_line = (n.span or {}).get("start_line", 0)
            return (kind_order.get(n.kind, 99), n.file_path, start_line, n.name)

        return sorted(nodes, key=sort_key)

    def _sort_edges(self, edges: List[TraceEdge]) -> List[TraceEdge]:
        def sort_key(e: TraceEdge) -> Tuple[str, str, str, str]:
            return (e.kind, e.source, e.target, e.id)

        return sorted(edges, key=sort_key)

    def _write_atomic(self, nodes: List[TraceNode], edges: List[TraceEdge]) -> None:
        sorted_nodes = self._sort_nodes(nodes)
        sorted_edges = self._sort_edges(edges)

        tmp_nodes = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", dir=self.index_dir, delete=False, encoding="utf-8"
        )
        try:
            for n in sorted_nodes:
                tmp_nodes.write(json.dumps(n.to_dict(), sort_keys=True) + "\n")
            tmp_nodes.flush()
            os.fsync(tmp_nodes.fileno())
            tmp_nodes.close()
            os.rename(tmp_nodes.name, self.nodes_path)
        except Exception:
            try:
                os.unlink(tmp_nodes.name)
            except OSError:
                pass
            raise

        tmp_edges = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", dir=self.index_dir, delete=False, encoding="utf-8"
        )
        try:
            for e in sorted_edges:
                tmp_edges.write(json.dumps(e.to_dict(), sort_keys=True) + "\n")
            tmp_edges.flush()
            os.fsync(tmp_edges.fileno())
            tmp_edges.close()
            os.rename(tmp_edges.name, self.edges_path)
        except Exception:
            try:
                os.unlink(tmp_edges.name)
            except OSError:
                pass
            raise

    def _build_manifest(
        self,
        nodes_count: int,
        edges_count: int,
        files_parsed: int,
        files_failed: int,
        file_errors: List[FileError],
        last_error: Optional[str],
        file_hashes: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        manifest: Dict[str, Any] = {
            "version": TRACE_MANIFEST_VERSION,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "project": {
                "repo_root": str(self.repo_root),
            },
            "config": {
                "include_globs": self.include_globs,
                "exclude_globs": self.exclude_globs,
                "max_file_bytes": self.max_file_bytes,
            },
            "counts": {
                "nodes": nodes_count,
                "edges": edges_count,
                "files_parsed": files_parsed,
                "files_failed": files_failed,
            },
            "file_errors": [{"file_path": e.file_path, "error_type": e.error_type, "message": e.message} for e in file_errors],
            "last_error": last_error,
        }
        if file_hashes is not None:
            manifest["file_hashes"] = file_hashes
        return manifest

    def _write_manifest(self, manifest: Dict[str, Any]) -> None:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", dir=self.index_dir, delete=False, encoding="utf-8"
        )
        try:
            json.dump(manifest, tmp, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, self.manifest_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise


class TraceIndex:
    """
    Query interface for a built trace index.
    Uses Rust TraceHandle when CODRAG_ENGINE=rust, else Python dicts.
    """

    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir).resolve()
        self.manifest_path = self.index_dir / "trace_manifest.json"
        self.nodes_path = self.index_dir / "trace_nodes.jsonl"
        self.edges_path = self.index_dir / "trace_edges.jsonl"

        self._manifest: Optional[Dict[str, Any]] = None
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Dict[str, Any]] = []
        self._edges_by_source: Dict[str, List[Dict[str, Any]]] = {}
        self._edges_by_target: Dict[str, List[Dict[str, Any]]] = {}
        self._loaded = False
        self._last_mtime: float = 0.0
        self._rust_handle = None  # Rust TraceHandle when using Rust engine

    def exists(self) -> bool:
        return self.manifest_path.exists() and self.nodes_path.exists() and self.edges_path.exists()

    def load(self, force: bool = False) -> bool:
        if not self.exists():
            return False
            
        # Check for staleness
        try:
            current_mtime = self.manifest_path.stat().st_mtime
            if not force and self._loaded and current_mtime <= self._last_mtime:
                return True
            self._last_mtime = current_mtime
        except OSError:
            pass

        if _ENGINE == "rust" and _rust_engine is not None:
            return self._load_rust()

        return self._load_python()

    def _load_rust(self) -> bool:
        """Load trace index via Rust engine — much faster than Python JSONL parsing."""
        try:
            self._rust_handle = _rust_engine.load_trace(str(self.index_dir))
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self._manifest = json.load(f)
            self._loaded = True
            logger.debug("Loaded trace index via Rust engine: %d nodes", self._rust_handle.node_count())
            return True
        except Exception as e:
            logger.error(f"Rust engine load failed, falling back to Python: {e}")
            self._rust_handle = None
            return self._load_python()

    def _load_python(self) -> bool:
        """Original Python JSONL loading — used as fallback."""
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self._manifest = json.load(f)

            self._nodes = {}
            with open(self.nodes_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        node = json.loads(line)
                        self._nodes[node["id"]] = node

            self._edges = []
            self._edges_by_source = {}
            self._edges_by_target = {}
            with open(self.edges_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        edge = json.loads(line)
                        self._edges.append(edge)
                        src = edge["source"]
                        tgt = edge["target"]
                        self._edges_by_source.setdefault(src, []).append(edge)
                        self._edges_by_target.setdefault(tgt, []).append(edge)

            self._loaded = True
            return True
        except Exception as e:
            logger.error(f"Failed to load trace index: {e}")
            return False

    def is_loaded(self) -> bool:
        return self._loaded

    def node_count(self) -> int:
        """Return total number of nodes in the graph."""
        if not self._loaded:
            self.load()
        if self._rust_handle is not None:
            return self._rust_handle.node_count()
        return len(self._nodes)

    def node_degree(self, node_id: str) -> Tuple[int, int]:
        """Return (in_degree, out_degree) for a node. Works with both Rust and Python backends."""
        if not self._loaded:
            self.load()
        if self._rust_handle is not None:
            result = self._rust_handle.get_neighbors(node_id, direction="both", max_nodes=10000)
            return (len(result.in_edges), len(result.out_edges))
        in_deg = len(self._edges_by_target.get(node_id, []))
        out_deg = len(self._edges_by_source.get(node_id, []))
        return (in_deg, out_deg)

    def status(self) -> Dict[str, Any]:
        engine = _ENGINE if _ENGINE else "python"
        base = {
            "engine": engine,
            "supported_languages": SUPPORTED_LANGUAGES,
        }

        if not self.exists():
            return {
                **base,
                "enabled": True,
                "exists": False,
                "building": False,
                "counts": {"nodes": 0, "edges": 0},
                "last_build_at": None,
                "last_error": None,
            }

        # Always check if we need to reload (checks mtime internally)
        self.load()

        if self._rust_handle is not None:
            rust_status = self._rust_handle.status()
            rust_status.update(base)
            return rust_status

        manifest = self._manifest or {}
        counts = manifest.get("counts", {})
        return {
            **base,
            "enabled": True,
            "exists": True,
            "building": False,
            "counts": {"nodes": counts.get("nodes", 0), "edges": counts.get("edges", 0)},
            "last_build_at": manifest.get("built_at"),
            "last_error": manifest.get("last_error"),
        }

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        if not self._loaded:
            self.load()
        if self._rust_handle is not None:
            n = self._rust_handle.get_node(node_id)
            return n.to_dict() if n else None
        return self._nodes.get(node_id)

    def search_nodes(self, query: str, kind: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if not self._loaded:
            self.load()

        if self._rust_handle is not None:
            results = self._rust_handle.search(query, kind=kind, limit=limit)
            return [r.to_dict() for r in results]

        query_lower = query.lower()
        results: List[Tuple[float, Dict[str, Any]]] = []

        for node in self._nodes.values():
            if kind and node.get("kind") != kind:
                continue

            name = str(node.get("name", "")).lower()
            qualname = str(node.get("metadata", {}).get("qualname", "")).lower()

            score = 0.0
            if name == query_lower:
                score = 1.0
            elif name.startswith(query_lower):
                score = 0.8
            elif query_lower in name:
                score = 0.6
            elif query_lower in qualname:
                score = 0.4

            if score > 0:
                results.append((score, node))

        results.sort(key=lambda x: (-x[0], x[1].get("file_path", ""), x[1].get("name", "")))
        return [r[1] for r in results[:limit]]

    def get_neighbors(
        self,
        node_id: str,
        direction: str = "both",
        edge_kinds: Optional[List[str]] = None,
        max_nodes: int = 50,
    ) -> Dict[str, Any]:
        if not self._loaded:
            self.load()

        if self._rust_handle is not None:
            result = self._rust_handle.get_neighbors(
                node_id, direction=direction, edge_kinds=edge_kinds, max_nodes=max_nodes
            )
            return {
                "in_edges": [e.to_dict() for e in result.in_edges],
                "out_edges": [e.to_dict() for e in result.out_edges],
                "in_nodes": [n.to_dict() for n in result.in_nodes],
                "out_nodes": [n.to_dict() for n in result.out_nodes],
            }

        in_edges: List[Dict[str, Any]] = []
        out_edges: List[Dict[str, Any]] = []

        if direction in ("in", "both"):
            for edge in self._edges_by_target.get(node_id, []):
                if edge_kinds and edge["kind"] not in edge_kinds:
                    continue
                in_edges.append(edge)

        if direction in ("out", "both"):
            for edge in self._edges_by_source.get(node_id, []):
                if edge_kinds and edge["kind"] not in edge_kinds:
                    continue
                out_edges.append(edge)

        in_edges = in_edges[:max_nodes]
        out_edges = out_edges[:max_nodes]

        in_nodes = [self._nodes.get(e["source"]) for e in in_edges if self._nodes.get(e["source"])]
        out_nodes = [self._nodes.get(e["target"]) for e in out_edges if self._nodes.get(e["target"])]

        return {
            "in_edges": in_edges,
            "out_edges": out_edges,
            "in_nodes": in_nodes,
            "out_nodes": out_nodes,
        }


def build_trace(
    repo_root: Path,
    index_dir: Path,
    include_globs: Optional[List[str]] = None,
    exclude_globs: Optional[List[str]] = None,
    max_file_bytes: int = 500_000,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to build trace index.
    """
    builder = TraceBuilder(
        repo_root=repo_root,
        index_dir=index_dir,
        include_globs=include_globs,
        exclude_globs=exclude_globs,
        max_file_bytes=max_file_bytes,
    )
    return builder.build(progress_callback=progress_callback)


def compute_trace_coverage(
    repo_root: Path,
    index_dir: Path,
    include_globs: Optional[List[str]] = None,
    exclude_globs: Optional[List[str]] = None,
    user_exclude_globs: Optional[List[str]] = None,
    max_file_bytes: int = 500_000,
) -> Dict[str, Any]:
    """
    Compute trace coverage by comparing current filesystem against trace manifest.

    Args:
      exclude_globs: default/system patterns — files matching these are silently skipped.
      user_exclude_globs: user-configured patterns — files matching these appear in the
                          'excluded' list so users can see what they manually excluded.

    Returns dict with:
      - traced: files that are traced and up-to-date
      - untraced: files eligible for trace but not yet traced
      - stale: files that were traced but content has changed
      - excluded: files explicitly excluded by user-configured patterns
      - summary: {total, traced, untraced, stale, excluded, coverage_pct}
    """
    repo_root = Path(repo_root).resolve()

    if include_globs is None:
        include_globs = [
            "**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx",
            "**/*.go", "**/*.rs", "**/*.java",
            "**/*.c", "**/*.cpp", "**/*.cc", "**/*.h", "**/*.hpp",
        ]
    if exclude_globs is None:
        exclude_globs = [
            "**/node_modules/**",
            "**/.git/**",
            "**/venv/**",
            "**/__pycache__/**",
            "**/dist/**",
            "**/build/**",
        ]
    if user_exclude_globs is None:
        user_exclude_globs = []

    # Load trace manifest file_hashes (if exists)
    manifest_path = Path(index_dir) / "trace_manifest.json"
    nodes_path = Path(index_dir) / "trace_nodes.jsonl"
    manifest_hashes: Dict[str, str] = {}
    manifest_built_at: Optional[str] = None
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest_hashes = manifest.get("file_hashes") or {}
            manifest_built_at = manifest.get("built_at")

            # One-time backfill: Rust engine manifests lack file_hashes.
            # Recover them from trace_nodes.jsonl so coverage isn't lost.
            if not manifest_hashes and manifest.get("counts", {}).get("nodes", 0) > 0 and nodes_path.exists():
                logger.info("Backfilling file_hashes from traced nodes (Rust manifest migration)")
                try:
                    traced_paths: List[str] = []
                    with open(nodes_path, "r", encoding="utf-8") as nf:
                        for line in nf:
                            line = line.strip()
                            if not line:
                                continue
                            node = json.loads(line)
                            if node.get("kind") == "file":
                                traced_paths.append(node["file_path"])

                    for rel_path in traced_paths:
                        full = repo_root / rel_path
                        if not full.exists():
                            continue
                        try:
                            fsize = full.stat().st_size
                            if fsize > max_file_bytes:
                                with open(full, "r", encoding="utf-8", errors="ignore") as hf:
                                    source = hf.read(50_000)
                            else:
                                source = full.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            source = ""
                        manifest_hashes[rel_path] = stable_file_hash(source)

                    # Persist so this migration only runs once
                    manifest["file_hashes"] = manifest_hashes
                    tmp_manifest = tempfile.NamedTemporaryFile(
                        mode="w", suffix=".json", dir=str(Path(index_dir)),
                        delete=False, encoding="utf-8",
                    )
                    try:
                        json.dump(manifest, tmp_manifest, indent=2, sort_keys=True)
                        tmp_manifest.flush()
                        os.fsync(tmp_manifest.fileno())
                        tmp_manifest.close()
                        os.rename(tmp_manifest.name, manifest_path)
                        logger.info("Backfilled %d file_hashes into manifest", len(manifest_hashes))
                    except Exception:
                        try:
                            os.unlink(tmp_manifest.name)
                        except OSError:
                            pass
                except Exception as e:
                    logger.warning("file_hashes backfill failed: %s", e)
        except Exception:
            pass

    # Directories to always prune from os.walk — these are never interesting
    # and can contain tens of thousands of files (e.g. node_modules).
    _PRUNE_DIRS = {
        "node_modules", ".git", ".venv", "venv", "__pycache__",
        "dist", "build", ".next", ".tox", ".mypy_cache",
        ".pytest_cache", ".eggs", "egg-info", ".cargo", "target",
    }

    traced_files: List[Dict[str, Any]] = []
    untraced_files: List[Dict[str, Any]] = []
    stale_files: List[Dict[str, Any]] = []
    excluded_files: List[Dict[str, Any]] = []

    for root_dir, dirs, filenames in os.walk(repo_root):
        # Prune noisy directories in-place so os.walk never descends into them
        dirs[:] = [d for d in dirs if d not in _PRUNE_DIRS]
        root_path = Path(root_dir)
        for fname in filenames:
            file_path = root_path / fname
            if file_path.is_symlink():
                continue

            rel_path = _to_posix(str(file_path.relative_to(repo_root)))

            # Check if file matches include globs at all (only code files)
            base = os.path.basename(rel_path)
            matches_any_include = False
            if not include_globs:
                matches_any_include = True
            else:
                for g in include_globs:
                    patterns = [g]
                    if g.startswith("**/"):
                        patterns.append(g[3:])
                    for p in patterns:
                        if fnmatch(rel_path, p) or fnmatch(base, p):
                            matches_any_include = True
                            break
                    if matches_any_include:
                        break

            if not matches_any_include:
                continue

            # Check if excluded by default/system patterns (silently skip)
            is_default_excluded = False
            for g in exclude_globs:
                patterns = [g]
                if g.startswith("**/"):
                    patterns.append(g[3:])
                for p in patterns:
                    if fnmatch(rel_path, p) or fnmatch(base, p):
                        is_default_excluded = True
                        break
                if is_default_excluded:
                    break

            if is_default_excluded:
                continue

            # Check if excluded by user-configured patterns (show in 'excluded' list)
            is_user_excluded = False
            for g in user_exclude_globs:
                patterns = [g]
                if g.startswith("**/"):
                    patterns.append(g[3:])
                for p in patterns:
                    if fnmatch(rel_path, p) or fnmatch(base, p):
                        is_user_excluded = True
                        break
                if is_user_excluded:
                    break

            # Get file stat for timestamps
            try:
                stat = file_path.stat()
                file_size = stat.st_size
                modified_ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                created_ts = datetime.fromtimestamp(stat.st_birthtime, tz=timezone.utc).isoformat() if hasattr(stat, 'st_birthtime') else modified_ts
            except OSError:
                continue

            if file_size > max_file_bytes:
                continue

            language = _detect_language(rel_path)

            file_info: Dict[str, Any] = {
                "path": rel_path,
                "language": language,
                "size": file_size,
                "modified": modified_ts,
                "created": created_ts,
            }

            if is_user_excluded:
                excluded_files.append(file_info)
                continue

            # Compare against manifest hashes
            prev_hash = manifest_hashes.get(rel_path)
            if prev_hash is None:
                # Not in trace manifest → untraced
                untraced_files.append(file_info)
            else:
                # Was traced — check if stale
                try:
                    source = file_path.read_text(encoding="utf-8", errors="ignore")
                    current_hash = stable_file_hash(source)
                except Exception:
                    current_hash = ""

                if current_hash != prev_hash:
                    stale_files.append(file_info)
                else:
                    traced_files.append(file_info)

    # Sort lists by path
    traced_files.sort(key=lambda f: f["path"])
    untraced_files.sort(key=lambda f: f["path"])
    stale_files.sort(key=lambda f: f["path"])
    excluded_files.sort(key=lambda f: f["path"])

    total = len(traced_files) + len(untraced_files) + len(stale_files)
    coverage_pct = round(len(traced_files) / total * 100, 1) if total > 0 else 0.0

    return {
        "traced": traced_files,
        "untraced": untraced_files,
        "stale": stale_files,
        "excluded": excluded_files,
        "summary": {
            "total": total,
            "traced": len(traced_files),
            "untraced": len(untraced_files),
            "stale": len(stale_files),
            "excluded": len(excluded_files),
            "coverage_pct": coverage_pct,
            "last_build_at": manifest_built_at,
        },
    }
