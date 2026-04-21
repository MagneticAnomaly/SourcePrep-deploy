"""Tests for the regex-based JSAnalyzer (Python fallback for JS/TS trace graph)."""
import tempfile
from pathlib import Path

import pytest

from prep.core.trace import JSAnalyzer


@pytest.fixture
def repo_root(tmp_path):
    """Create a minimal repo structure for relative import resolution."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils.ts").write_text("export function helper() {}")
    (tmp_path / "src" / "index.ts").write_text("export * from './utils'")
    (tmp_path / "src" / "components").mkdir()
    (tmp_path / "src" / "components" / "index.tsx").write_text("export {}")
    return tmp_path


class TestJSAnalyzerImports:
    """Test import extraction from JS/TS source."""

    def test_es_import_from(self, repo_root):
        source = "import { useState } from 'react';\nimport React from 'react';\n"
        analyzer = JSAnalyzer("src/app.tsx", source, repo_root)
        nodes, edges = analyzer.analyze()
        import_edges = [e for e in edges if e.kind == "imports"]
        assert len(import_edges) >= 1
        assert any(e.metadata.get("import") == "react" for e in import_edges)

    def test_es_import_side_effect(self, repo_root):
        source = "import './styles.css';\n"
        analyzer = JSAnalyzer("src/app.tsx", source, repo_root)
        nodes, edges = analyzer.analyze()
        import_edges = [e for e in edges if e.kind == "imports"]
        assert len(import_edges) >= 1

    def test_commonjs_require(self, repo_root):
        source = "const path = require('path');\nconst fs = require('fs');\n"
        analyzer = JSAnalyzer("src/server.js", source, repo_root)
        nodes, edges = analyzer.analyze()
        import_edges = [e for e in edges if e.kind == "imports"]
        modules = {e.metadata.get("import") for e in import_edges}
        assert "path" in modules
        assert "fs" in modules

    def test_dynamic_import(self, repo_root):
        source = "const mod = await import('lodash');\n"
        analyzer = JSAnalyzer("src/app.ts", source, repo_root)
        nodes, edges = analyzer.analyze()
        import_edges = [e for e in edges if e.kind == "imports"]
        assert any(e.metadata.get("import") == "lodash" for e in import_edges)

    def test_re_export(self, repo_root):
        source = "export { default } from 'react-dom';\n"
        analyzer = JSAnalyzer("src/index.ts", source, repo_root)
        nodes, edges = analyzer.analyze()
        import_edges = [e for e in edges if e.kind == "imports"]
        assert any(e.metadata.get("import") == "react-dom" for e in import_edges)

    def test_relative_import_resolves(self, repo_root):
        source = "import { helper } from './utils';\n"
        analyzer = JSAnalyzer("src/app.ts", source, repo_root)
        nodes, edges = analyzer.analyze()
        import_edges = [e for e in edges if e.kind == "imports"]
        # Should resolve to src/utils.ts (file node), not external_module
        assert len(import_edges) >= 1
        resolved = [e for e in import_edges if e.metadata.get("relative")]
        assert len(resolved) >= 1

    def test_relative_import_directory_index(self, repo_root):
        source = "import { Foo } from './components';\n"
        analyzer = JSAnalyzer("src/app.ts", source, repo_root)
        nodes, edges = analyzer.analyze()
        import_edges = [e for e in edges if e.kind == "imports"]
        resolved = [e for e in import_edges if e.metadata.get("relative")]
        assert len(resolved) >= 1

    def test_deduplicates_imports(self, repo_root):
        source = (
            "import React from 'react';\n"
            "import { useState } from 'react';\n"
        )
        analyzer = JSAnalyzer("src/app.tsx", source, repo_root)
        nodes, edges = analyzer.analyze()
        import_edges = [e for e in edges if e.kind == "imports"]
        react_imports = [e for e in import_edges if e.metadata.get("import") == "react"]
        assert len(react_imports) == 1


class TestJSAnalyzerSymbols:
    """Test symbol extraction from JS/TS source."""

    def test_function_declaration(self, repo_root):
        source = "function handleClick() {\n  console.log('click');\n}\n"
        analyzer = JSAnalyzer("src/utils.ts", source, repo_root)
        nodes, edges = analyzer.analyze()
        sym_nodes = [n for n in nodes if n.kind == "symbol"]
        assert any(n.name == "handleClick" for n in sym_nodes)
        # Should have a contains edge
        contains = [e for e in edges if e.kind == "contains"]
        assert len(contains) >= 1

    def test_async_function(self, repo_root):
        source = "export async function fetchData() {}\n"
        analyzer = JSAnalyzer("src/api.ts", source, repo_root)
        nodes, edges = analyzer.analyze()
        sym_nodes = [n for n in nodes if n.kind == "symbol"]
        fn = next((n for n in sym_nodes if n.name == "fetchData"), None)
        assert fn is not None
        assert fn.metadata.get("symbol_type") == "async_function"

    def test_class_declaration(self, repo_root):
        source = "export class ApiClient {\n  fetch() {}\n}\n"
        analyzer = JSAnalyzer("src/client.ts", source, repo_root)
        nodes, edges = analyzer.analyze()
        sym_nodes = [n for n in nodes if n.kind == "symbol"]
        assert any(n.name == "ApiClient" for n in sym_nodes)

    def test_typescript_interface(self, repo_root):
        source = "export interface UserProps {\n  name: string;\n}\n"
        analyzer = JSAnalyzer("src/types.ts", source, repo_root)
        nodes, edges = analyzer.analyze()
        sym_nodes = [n for n in nodes if n.kind == "symbol"]
        iface = next((n for n in sym_nodes if n.name == "UserProps"), None)
        assert iface is not None
        assert iface.metadata.get("symbol_type") == "interface"

    def test_typescript_type_alias(self, repo_root):
        source = "export type ID = string;\n"
        analyzer = JSAnalyzer("src/types.ts", source, repo_root)
        nodes, edges = analyzer.analyze()
        sym_nodes = [n for n in nodes if n.kind == "symbol"]
        assert any(n.name == "ID" for n in sym_nodes)

    def test_typescript_enum(self, repo_root):
        source = "export enum Status {\n  Active,\n  Inactive,\n}\n"
        analyzer = JSAnalyzer("src/types.ts", source, repo_root)
        nodes, edges = analyzer.analyze()
        sym_nodes = [n for n in nodes if n.kind == "symbol"]
        e = next((n for n in sym_nodes if n.name == "Status"), None)
        assert e is not None
        assert e.metadata.get("symbol_type") == "enum"

    def test_exported_const(self, repo_root):
        source = "export const MAX_RETRIES = 3;\n"
        analyzer = JSAnalyzer("src/config.ts", source, repo_root)
        nodes, edges = analyzer.analyze()
        sym_nodes = [n for n in nodes if n.kind == "symbol"]
        assert any(n.name == "MAX_RETRIES" for n in sym_nodes)

    def test_language_detection(self, repo_root):
        source = "export function foo() {}\n"
        ts_analyzer = JSAnalyzer("src/foo.ts", source, repo_root)
        ts_nodes, _ = ts_analyzer.analyze()
        ts_sym = next(n for n in ts_nodes if n.kind == "symbol")
        assert ts_sym.language == "typescript"

        js_analyzer = JSAnalyzer("src/foo.js", source, repo_root)
        js_nodes, _ = js_analyzer.analyze()
        js_sym = next(n for n in js_nodes if n.kind == "symbol")
        assert js_sym.language == "javascript"


class TestJSAnalyzerCombined:
    """Test a realistic file with both imports and symbols."""

    def test_realistic_ts_file(self, repo_root):
        source = """\
import React, { useState, useCallback } from 'react';
import { cn } from '../lib/utils';
import type { ButtonProps } from './types';

export interface ExtendedButtonProps extends ButtonProps {
  loading?: boolean;
}

export function Button({ loading, ...props }: ExtendedButtonProps) {
  const [clicked, setClicked] = useState(false);
  return <button {...props} />;
}

export default Button;
"""
        analyzer = JSAnalyzer("src/components/Button.tsx", source, repo_root)
        nodes, edges = analyzer.analyze()

        sym_nodes = [n for n in nodes if n.kind == "symbol"]
        import_edges = [e for e in edges if e.kind == "imports"]
        contains_edges = [e for e in edges if e.kind == "contains"]

        # Should find imports
        assert len(import_edges) >= 2  # react + at least one relative

        # Should find symbols
        names = {n.name for n in sym_nodes}
        assert "ExtendedButtonProps" in names
        assert "Button" in names

        # Each symbol should have a contains edge
        assert len(contains_edges) >= 2
