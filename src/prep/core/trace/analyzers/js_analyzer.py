"""
Regex-based JavaScript/TypeScript analyzer for extracting imports and symbols.
Provides basic relationship extraction for the Python fallback engine.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from prep.core.ids import (
    stable_edge_id,
    stable_external_module_id,
    stable_file_node_id,
    stable_symbol_node_id,
)
from ..models import TraceNode, TraceEdge


class JSAnalyzer:
    """
    Regex-based JavaScript/TypeScript analyzer for extracting imports and symbols.
    Provides basic relationship extraction for the Python fallback engine.
    """

    def __init__(self, file_path: str, source: str, repo_root: Path):
        self.file_path = file_path
        self.source = source
        self.repo_root = repo_root
        self.nodes: List[TraceNode] = []
        self.edges: List[TraceEdge] = []
        self._file_node_id = stable_file_node_id(file_path)
        self._path_aliases = self._load_path_aliases()

    def analyze(self) -> Tuple[List[TraceNode], List[TraceEdge]]:
        import re

        # --- Import extraction ---
        # ES module: import ... from 'module'  /  import 'module'
        es_import = re.compile(
            r"""^\s*import\s+(?:.*?\s+from\s+)?['"]([^'"]+)['"]""",
            re.MULTILINE,
        )
        # CommonJS: require('module')
        cjs_require = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
        # Dynamic import: import('module')
        dynamic_import = re.compile(r"""import\(\s*['"]([^'"]+)['"]\s*\)""")
        # Re-export: export ... from 'module'
        re_export = re.compile(
            r"""^\s*export\s+(?:.*?\s+from\s+)['"]([^'"]+)['"]""",
            re.MULTILINE,
        )

        seen_imports: set = set()
        for pattern in (es_import, cjs_require, dynamic_import, re_export):
            for match in pattern.finditer(self.source):
                module = match.group(1).strip()
                if not module or module in seen_imports:
                    continue
                seen_imports.add(module)
                lineno = self.source.count("\n", 0, match.start()) + 1

                # Try to resolve relative imports to a file node
                if module.startswith("."):
                    resolved = self._resolve_relative(module)
                    if resolved:
                        target_id = stable_file_node_id(resolved)
                        disambiguator = f"{module}:{lineno}"
                        edge_id = stable_edge_id("imports", self._file_node_id, target_id, disambiguator)
                        self.edges.append(
                            TraceEdge(
                                id=edge_id,
                                kind="imports",
                                source=self._file_node_id,
                                target=target_id,
                                metadata={"confidence": 0.9, "import": module, "line": lineno, "relative": True},
                            )
                        )
                        continue

                # Try to resolve path aliases (e.g. @/ → src/)
                resolved = self._resolve_alias(module)
                if resolved:
                    target_id = stable_file_node_id(resolved)
                    disambiguator = f"{module}:{lineno}"
                    edge_id = stable_edge_id("imports", self._file_node_id, target_id, disambiguator)
                    self.edges.append(
                        TraceEdge(
                            id=edge_id,
                            kind="imports",
                            source=self._file_node_id,
                            target=target_id,
                            metadata={"confidence": 0.9, "import": module, "line": lineno, "alias": True},
                        )
                    )
                    continue

                # External / unresolved → external_module node
                self._add_import(module, lineno)

        # --- Symbol extraction ---
        # function declarationss: function name(  /  async function name(
        func_pattern = re.compile(
            r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)",
            re.MULTILINE,
        )
        # class declarationss: class Name
        class_pattern = re.compile(
            r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)",
            re.MULTILINE,
        )
        # interface/type/enum (TypeScript): interface Name / type Name / enum Name
        ts_pattern = re.compile(
            r"^\s*(?:export\s+)?(?:declare\s+)?(interface|type|enum)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)",
            re.MULTILINE,
        )
        # const/let/var exports: export const name =
        const_export = re.compile(
            r"^\s*export\s+(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)",
            re.MULTILINE,
        )

        for match in func_pattern.finditer(self.source):
            name = match.group(1)
            is_async = "async" in match.group(0)
            start_line = self.source.count("\n", 0, match.start()) + 1
            self._add_symbol(name, "async_function" if is_async else "function", start_line)

        for match in class_pattern.finditer(self.source):
            name = match.group(1)
            start_line = self.source.count("\n", 0, match.start()) + 1
            self._add_symbol(name, "class", start_line)

        for match in ts_pattern.finditer(self.source):
            kind = match.group(1)  # interface, type, or enum
            name = match.group(2)
            start_line = self.source.count("\n", 0, match.start()) + 1
            self._add_symbol(name, kind, start_line)

        for match in const_export.finditer(self.source):
            name = match.group(1)
            start_line = self.source.count("\n", 0, match.start()) + 1
            self._add_symbol(name, "variable", start_line)

        return self.nodes, self.edges

    def _add_symbol(self, name: str, symbol_type: str, start_line: int) -> None:
        node_id = stable_symbol_node_id(name, self.file_path, start_line)
        lang = "typescript" if self.file_path.endswith((".ts", ".tsx")) else "javascript"
        self.nodes.append(
            TraceNode(
                id=node_id,
                kind="symbol",
                name=name,
                file_path=self.file_path,
                span={"start_line": start_line, "end_line": start_line},
                language=lang,
                metadata={"symbol_type": symbol_type, "qualname": name},
            )
        )
        edge_id = stable_edge_id("contains", self._file_node_id, node_id)
        self.edges.append(
            TraceEdge(
                id=edge_id,
                kind="contains",
                source=self._file_node_id,
                target=node_id,
                metadata={"confidence": 1.0},
            )
        )

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
                metadata={"confidence": 0.7, "import": module, "line": lineno, "external": True},
            )
        )

    def _load_path_aliases(self) -> Dict[str, str]:
        """Load path aliases from tsconfig.json / jsconfig.json.

        Returns a dict mapping alias prefix (e.g. '@/') to its
        replacement directory (e.g. 'src/').
        """
        aliases: Dict[str, str] = {}
        for config_name in ("tsconfig.json", "jsconfig.json"):
            config_path = self.repo_root / config_name
            if not config_path.exists():
                continue
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                paths = data.get("compilerOptions", {}).get("paths", {})
                base_url = data.get("compilerOptions", {}).get("baseUrl", ".")
                for pattern, targets in paths.items():
                    if not targets or not pattern.endswith("/*"):
                        continue
                    prefix = pattern[:-1]  # "@/*" → "@/"
                    target = targets[0]    # "./src/*" → take first
                    if target.endswith("/*"):
                        target = target[:-1]  # "./src/*" → "./src/"
                    # Normalize: strip leading "./", ensure trailing "/"
                    target = target.lstrip("./")
                    if not target.endswith("/"):
                        target += "/"
                    if base_url != ".":
                        target = base_url.rstrip("/") + "/" + target
                    aliases[prefix] = target
                break  # Use first config found
            except Exception:
                pass
        return aliases

    def _resolve_alias(self, module: str) -> Optional[str]:
        """Resolve a path-aliased import like '@/hooks/useCopy' to a file path."""
        for prefix, replacement in self._path_aliases.items():
            if module.startswith(prefix):
                rest = module[len(prefix):]  # "hooks/useCopy"
                return self._resolve_path(replacement + rest)
        return None

    def _resolve_path(self, rel_path: str) -> Optional[str]:
        """Resolve a repo-relative path to an actual file, trying extensions."""
        extensions = [".ts", ".tsx", ".js", ".jsx", ".css", ".scss", ""]
        index_files = ["index.ts", "index.tsx", "index.js", "index.jsx"]

        for ext in extensions:
            candidate = (rel_path + ext).replace("\\", "/")
            if (self.repo_root / candidate).exists():
                return candidate

        # Try as directory with index file
        for idx in index_files:
            candidate = (rel_path.rstrip("/") + "/" + idx).replace("\\", "/")
            if (self.repo_root / candidate).exists():
                return candidate

        return None

    def _resolve_relative(self, module: str) -> Optional[str]:
        """Try to resolve a relative import like './utils' to a file path."""
        dir_path = Path(self.file_path).parent
        rel = str(dir_path / module).replace("\\", "/")
        return self._resolve_path(rel)
