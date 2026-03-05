"""
Python AST-based analyzer for extracting symbols and imports.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from codrag.core.ids import (
    stable_edge_id,
    stable_external_module_id,
    stable_file_node_id,
    stable_symbol_node_id,
)
from ..models import TraceNode, TraceEdge
from ..utils import _to_posix


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
