"""
Configurable regex-based analyzer for languages without dedicated parsers.
Handles Kotlin, C#, Ruby, PHP, Dart, Scala, Lua, Zig, Elixir, Shell,
Go, Rust, Java, C, and C++.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from prep.core.ids import (
    stable_edge_id,
    stable_external_module_id,
    stable_file_node_id,
    stable_symbol_node_id,
)
from ..models import TraceNode, TraceEdge


class GenericRegexAnalyzer:
    """
    Configurable regex-based analyzer for languages without dedicated parsers.
    Handles Kotlin, C#, Ruby, PHP, Dart, Scala, Lua, Zig, Elixir, and Shell.
    Extracts symbols (classes/functions) and imports using language-specific patterns.
    """

    # Per-language regex configs: (symbol_patterns, import_patterns)
    # symbol_patterns: list of (regex, kind_extractor) tuples
    # import_patterns: list of (regex, module_group_index) tuples
    LANGUAGE_CONFIGS: Dict[str, Dict[str, Any]] = {
        "kotlin": {
            "symbol_patterns": [
                (r"^\s*(?:[\w@]+\s+)*(class|object|interface|enum\s+class|data\s+class|sealed\s+class|fun)\s+([a-zA-Z_][a-zA-Z0-9_]*)", 2),
            ],
            "import_pattern": r"^\s*import\s+([\w.]+)",
        },
        "csharp": {
            "symbol_patterns": [
                (r"^\s*(?:[\w\[\]]+\s+)*(class|struct|interface|enum|record)\s+([a-zA-Z_][a-zA-Z0-9_]*)", 2),
                (r"^\s*(?:[\w\[\]]+\s+)*(?:static\s+)?(?:async\s+)?[\w<>\[\]]+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", 1),
            ],
            "import_pattern": r"^\s*using\s+(?:static\s+)?([a-zA-Z][\w.]*)",
        },
        "ruby": {
            "symbol_patterns": [
                (r"^\s*(class|module)\s+([A-Z][a-zA-Z0-9_:]*)", 2),
                (r"^\s*def\s+(?:self\.)?([a-zA-Z_][a-zA-Z0-9_!?]*)", 1),
            ],
            "import_pattern": r"^\s*require(?:_relative)?\s+['\"]([^'\"]+)['\"]",
        },
        "php": {
            "symbol_patterns": [
                (r"^\s*(?:abstract\s+|final\s+)?(?:class|interface|trait|enum)\s+([a-zA-Z_][a-zA-Z0-9_]*)", 1),
                (r"^\s*(?:public|protected|private|static|\s)*\s*function\s+([a-zA-Z_][a-zA-Z0-9_]*)", 1),
            ],
            "import_pattern": r"^\s*(?:use|require|require_once|include|include_once)\s+([^\s;]+)",
        },
        "dart": {
            "symbol_patterns": [
                (r"^\s*(?:abstract\s+)?class\s+([a-zA-Z_][a-zA-Z0-9_]*)", 1),
                (r"^\s*(?:[\w<>]+\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*(?:async\s*)?{", 1),
            ],
            "import_pattern": r"^\s*import\s+['\"]([^'\"]+)['\"]",
        },
        "scala": {
            "symbol_patterns": [
                (r"^\s*(?:case\s+)?(?:class|object|trait)\s+([a-zA-Z_][a-zA-Z0-9_]*)", 1),
                (r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)", 1),
            ],
            "import_pattern": r"^\s*import\s+([\w.{},\s]+)",
        },
        "lua": {
            "symbol_patterns": [
                (r"^\s*(?:local\s+)?function\s+([a-zA-Z_][a-zA-Z0-9_.]*)", 1),
            ],
            "import_pattern": r"""require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)""",
        },
        "zig": {
            "symbol_patterns": [
                (r"^\s*(?:pub\s+)?(?:fn|const)\s+([a-zA-Z_][a-zA-Z0-9_]*)", 1),
                (r"^\s*(?:pub\s+)?const\s+([A-Z][a-zA-Z0-9_]*)\s*=\s*(?:struct|enum|union)", 1),
            ],
            "import_pattern": r"""@import\s*\(\s*\"([^\"]+)\"\s*\)""",
        },
        "elixir": {
            "symbol_patterns": [
                (r"^\s*defmodule\s+([A-Z][a-zA-Z0-9_.]*)", 1),
                (r"^\s*(?:def|defp|defmacro)\s+([a-zA-Z_][a-zA-Z0-9_!?]*)", 1),
            ],
            "import_pattern": r"^\s*(?:import|alias|use)\s+([A-Z][\w.]*)",
        },
        "shell": {
            "symbol_patterns": [
                (r"^\s*(?:function\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*\)", 1),
            ],
            "import_pattern": r"^\s*(?:source|\.)\s+([^\s;#]+)",
        },
        "go": {
            "symbol_patterns": [
                # func Name(...)
                (r"^\s*func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", 1),
                # func (receiver) Name(...)
                (r"^\s*func\s+\([^)]*\)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", 1),
                # type Name struct/interface/...
                (r"^\s*type\s+([A-Z][A-Za-z0-9_]*)\s+(?:struct|interface)\b", 1),
            ],
            "import_pattern": r'^\s*(?:import\s+)?"([^"]+)"',
        },
        "rust": {
            "symbol_patterns": [
                # pub fn / fn name
                (r"^\s*(?:pub(?:\([^)]*\))?\s+)?fn\s+([a-zA-Z_][a-zA-Z0-9_]*)", 1),
                # pub struct / struct Name
                (r"^\s*(?:pub(?:\([^)]*\))?\s+)?struct\s+([A-Z][a-zA-Z0-9_]*)", 1),
                # pub enum / enum Name
                (r"^\s*(?:pub(?:\([^)]*\))?\s+)?enum\s+([A-Z][a-zA-Z0-9_]*)", 1),
                # pub trait / trait Name
                (r"^\s*(?:pub(?:\([^)]*\))?\s+)?trait\s+([A-Z][a-zA-Z0-9_]*)", 1),
                # impl Name (but not impl Trait for ...)
                (r"^\s*impl(?:<[^>]*>)?\s+([A-Z][a-zA-Z0-9_]*)\s*(?:\{|<)", 1, "class"),
            ],
            "import_pattern": r"^\s*use\s+((?:crate|super|self|std|[a-z][a-z0-9_]*)(?:::[a-zA-Z0-9_*{}]+)*)",
        },
        "java": {
            "symbol_patterns": [
                # class / interface / enum declarations
                (r"^\s*(?:[\w@]+\s+)*(class|interface|enum)\s+([A-Z][a-zA-Z0-9_]*)", 2),
                # method declarations (return_type name(...))
                (r"^\s*(?:[\w@\[\]<>,\s]+\s+)([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*(?:\{|throws)", 1, "method"),
            ],
            "import_pattern": r"^\s*import\s+(?:static\s+)?([\w.]+(?:\.\*)?)",
        },
        "c": {
            "symbol_patterns": [
                # function definitions: type name(...)  {  (heuristic)
                (r"^(?:[\w*\s]+\s+)([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{", 1, "function"),
                # struct/enum/union Name {
                (r"^\s*(?:typedef\s+)?(?:struct|enum|union)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\{", 1),
            ],
            "import_pattern": r'^\s*#include\s+[<"]([^>"]+)[>"]',
        },
        "cpp": {
            "symbol_patterns": [
                # class/struct Name
                (r"^\s*(?:template\s*<[^>]*>\s*)?(?:class|struct)\s+([A-Z][a-zA-Z0-9_]*)", 1),
                # function definitions
                (r"^(?:[\w*&:<>\s]+\s+)([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*(?:const\s*)?(?:override\s*)?(?:noexcept\s*)?\{", 1, "function"),
                # namespace Name
                (r"^\s*namespace\s+([a-zA-Z_][a-zA-Z0-9_]*)", 1),
            ],
            "import_pattern": r'^\s*#include\s+[<"]([^>"]+)[>"]',
        },
    }

    def __init__(self, file_path: str, source: str, repo_root: Path, language: str):
        self.file_path = file_path
        self.source = source
        self.repo_root = repo_root
        self.language = language
        self.nodes: List[TraceNode] = []
        self.edges: List[TraceEdge] = []
        self._file_node_id = stable_file_node_id(file_path)
        self._config = self.LANGUAGE_CONFIGS.get(language, {})

    def analyze(self) -> Tuple[List[TraceNode], List[TraceEdge]]:
        import re

        if not self._config:
            return self.nodes, self.edges

        # Symbol extraction
        for pattern_info in self._config.get("symbol_patterns", []):
            # Tuple: (regex, name_group) or (regex, name_group, forced_type)
            if len(pattern_info) == 3:
                pattern_str, name_group, forced_type = pattern_info
            else:
                pattern_str, name_group = pattern_info
                forced_type = None
            pattern = re.compile(pattern_str, re.MULTILINE)
            for match in pattern.finditer(self.source):
                name = match.group(name_group)
                if not name or name in ("if", "for", "while", "return", "else", "switch", "case"):
                    continue
                start_line = self.source.count("\n", 0, match.start()) + 1

                # Use forced type if specified, otherwise infer from the match
                if forced_type:
                    symbol_type = forced_type
                else:
                    full = match.group(0).lower()
                    if any(k in full for k in ("class", "struct", "interface", "trait", "module", "object", "enum", "record")):
                        symbol_type = "class"
                    elif any(k in full for k in ("fun", "func", "def", "function", "fn")):
                        symbol_type = "function"
                    else:
                        symbol_type = "variable"

                node_id = stable_symbol_node_id(name, self.file_path, start_line)
                self.nodes.append(
                    TraceNode(
                        id=node_id,
                        kind="symbol",
                        name=name,
                        file_path=self.file_path,
                        span={"start_line": start_line, "end_line": start_line},
                        language=self.language,
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
                        metadata={"confidence": 0.8},
                    )
                )

        # Import extraction
        import_pattern_str = self._config.get("import_pattern")
        if import_pattern_str:
            import_re = re.compile(import_pattern_str, re.MULTILINE)
            seen: set = set()
            for match in import_re.finditer(self.source):
                module = match.group(1).strip().rstrip(";")
                if not module or module in seen:
                    continue
                seen.add(module)
                lineno = self.source.count("\n", 0, match.start()) + 1
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

        return self.nodes, self.edges
