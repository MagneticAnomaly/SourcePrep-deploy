"""
Regex-based Swift analyzer for extracting symbols and imports.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from codrag.core.ids import (
    stable_edge_id,
    stable_external_module_id,
    stable_file_node_id,
    stable_symbol_node_id,
)
from ..models import TraceNode, TraceEdge


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
