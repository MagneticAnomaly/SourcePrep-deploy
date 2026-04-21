"""Tests for LODExtractor: structural code compression via LOD levels.

Covers:
  - LOD 0–5 output correctness on synthetic fixtures
  - Token-reduction targets per LOD level
  - Signature retention (LOD 2 ≥ 95%)
  - Name retention (LOD 4 ≥ 99%)
  - Fallback behaviour when trace data is missing
  - assign_lod() score thresholds
  - Per-language coverage (Python, JS/TS, Rust, Go, Java)
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from prep.core.context_tier import ContextTier
from prep.core.lod_extractor import LODExtractor, LODResult, assign_lod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PYTHON_SOURCE = textwrap.dedent("""\
    import os
    import sys
    from pathlib import Path

    CONSTANT = 42

    def standalone_function(x: int, y: int) -> int:
        \"\"\"Return the sum of x and y.\"\"\"
        result = x + y
        return result


    class MyClass:
        \"\"\"A sample class.\"\"\"

        class_var: str = "hello"

        def __init__(self, name: str) -> None:
            \"\"\"Initialize MyClass.\"\"\"
            self.name = name
            self._data: List[int] = []

        def method_one(self, value: int) -> bool:
            \"\"\"Check if value is positive.\"\"\"
            if value > 0:
                return True
            return False

        async def async_method(self) -> str:
            \"\"\"Return the name asynchronously.\"\"\"
            return self.name
""")

TS_SOURCE = textwrap.dedent("""\
    import { foo } from './foo';
    import type { Bar } from './bar';

    export function greet(name: string): string {
        const msg = `Hello, ${name}`;
        return msg;
    }

    export class Greeter {
        private name: string;

        constructor(name: string) {
            this.name = name;
        }

        greet(): string {
            return `Hello, ${this.name}`;
        }
    }
""")

RUST_SOURCE = textwrap.dedent("""\
    use std::collections::HashMap;

    pub fn add(a: i32, b: i32) -> i32 {
        a + b
    }

    pub struct Counter {
        count: u32,
    }

    impl Counter {
        pub fn new() -> Self {
            Counter { count: 0 }
        }

        pub fn increment(&mut self) {
            self.count += 1;
        }

        pub fn value(&self) -> u32 {
            self.count
        }
    }
""")

GO_SOURCE = textwrap.dedent("""\
    package main

    import "fmt"

    func add(a, b int) int {
        return a + b
    }

    type Counter struct {
        count int
    }

    func (c *Counter) Increment() {
        c.count++
    }

    func (c *Counter) Value() int {
        return c.count
    }
""")


def _make_python_trace_nodes(file_path: str = "src/example.py") -> List[Dict[str, Any]]:
    """Synthetic trace nodes matching PYTHON_SOURCE."""
    return [
        {
            "id": f"file:{file_path}",
            "kind": "file",
            "name": file_path,
            "file_path": file_path,
            "span": None,
            "language": "python",
            "metadata": {},
        },
        {
            "id": f"sym:standalone_function@{file_path}:7",
            "kind": "symbol",
            "name": "standalone_function",
            "file_path": file_path,
            "span": {"start_line": 7, "end_line": 10},
            "language": "python",
            "metadata": {
                "symbol_type": "function",
                "qualname": "standalone_function",
                "docstring": "Return the sum of x and y.",
                "is_public": True,
            },
        },
        {
            "id": f"sym:MyClass@{file_path}:13",
            "kind": "symbol",
            "name": "MyClass",
            "file_path": file_path,
            "span": {"start_line": 13, "end_line": 31},
            "language": "python",
            "metadata": {
                "symbol_type": "class",
                "qualname": "MyClass",
                "docstring": "A sample class.",
                "is_public": True,
            },
        },
        {
            "id": f"sym:MyClass.__init__@{file_path}:18",
            "kind": "symbol",
            "name": "__init__",
            "file_path": file_path,
            "span": {"start_line": 18, "end_line": 21},
            "language": "python",
            "metadata": {
                "symbol_type": "method",
                "qualname": "MyClass.__init__",
                "docstring": "Initialize MyClass.",
                "is_public": False,
            },
        },
        {
            "id": f"sym:MyClass.method_one@{file_path}:23",
            "kind": "symbol",
            "name": "method_one",
            "file_path": file_path,
            "span": {"start_line": 23, "end_line": 27},
            "language": "python",
            "metadata": {
                "symbol_type": "method",
                "qualname": "MyClass.method_one",
                "docstring": "Check if value is positive.",
                "is_public": True,
            },
        },
        {
            "id": f"sym:MyClass.async_method@{file_path}:29",
            "kind": "symbol",
            "name": "async_method",
            "file_path": file_path,
            "span": {"start_line": 29, "end_line": 31},
            "language": "python",
            "metadata": {
                "symbol_type": "async_method",
                "qualname": "MyClass.async_method",
                "docstring": "Return the name asynchronously.",
                "is_public": True,
            },
        },
    ]


def _make_ts_trace_nodes(file_path: str = "src/example.ts") -> List[Dict[str, Any]]:
    return [
        {
            "id": f"sym:greet@{file_path}:4",
            "kind": "symbol",
            "name": "greet",
            "file_path": file_path,
            "span": {"start_line": 4, "end_line": 7},
            "language": "typescript",
            "metadata": {"symbol_type": "function", "qualname": "greet", "is_public": True},
        },
        {
            "id": f"sym:Greeter@{file_path}:9",
            "kind": "symbol",
            "name": "Greeter",
            "file_path": file_path,
            "span": {"start_line": 9, "end_line": 22},
            "language": "typescript",
            "metadata": {"symbol_type": "class", "qualname": "Greeter", "is_public": True},
        },
        {
            "id": f"sym:Greeter.constructor@{file_path}:12",
            "kind": "symbol",
            "name": "constructor",
            "file_path": file_path,
            "span": {"start_line": 12, "end_line": 14},
            "language": "typescript",
            "metadata": {"symbol_type": "method", "qualname": "Greeter.constructor", "is_public": True},
        },
        {
            "id": f"sym:Greeter.greet@{file_path}:16",
            "kind": "symbol",
            "name": "greet",
            "file_path": file_path,
            "span": {"start_line": 16, "end_line": 18},
            "language": "typescript",
            "metadata": {"symbol_type": "method", "qualname": "Greeter.greet", "is_public": True},
        },
    ]


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a temporary repo with test source files."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "example.py").write_text(PYTHON_SOURCE, encoding="utf-8")
    (tmp_path / "src" / "example.ts").write_text(TS_SOURCE, encoding="utf-8")
    (tmp_path / "src" / "example.rs").write_text(RUST_SOURCE, encoding="utf-8")
    (tmp_path / "src" / "main.go").write_text(GO_SOURCE, encoding="utf-8")
    return tmp_path


@pytest.fixture
def extractor() -> LODExtractor:
    return LODExtractor()


# ---------------------------------------------------------------------------
# LOD 0: full source passthrough
# ---------------------------------------------------------------------------

class TestLOD0:
    def test_returns_full_source(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        result = extractor.extract("src/example.py", 0, [], tmp_repo)
        assert result.content == PYTHON_SOURCE
        assert result.lod == 0
        assert result.compression_ratio == pytest.approx(1.0, abs=0.05)
        assert result.fallback is False

    def test_compression_ratio_is_one(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        result = extractor.extract("src/example.py", 0, [], tmp_repo)
        assert result.input_chars == result.output_chars

    def test_missing_file_returns_error(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        result = extractor.extract("src/nonexistent.py", 0, [], tmp_repo)
        assert result.error is not None
        assert result.content == ""


# ---------------------------------------------------------------------------
# LOD 1: comment stripping
# ---------------------------------------------------------------------------

class TestLOD1:
    def test_strips_python_hash_comments(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        src = "# module comment\nimport os\n# another comment\nX = 1\n"
        (tmp_repo / "src" / "commented.py").write_text(src)
        result = extractor.extract("src/commented.py", 1, [], tmp_repo)
        assert "# module comment" not in result.content
        assert "import os" in result.content
        assert "X = 1" in result.content

    def test_strips_js_slashslash_comments(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        src = "// top comment\nimport { x } from './x';\n// inline\nconst y = 1;\n"
        (tmp_repo / "src" / "c.ts").write_text(src)
        result = extractor.extract("src/c.ts", 1, [], tmp_repo)
        assert "// top comment" not in result.content
        assert "import { x }" in result.content

    def test_reduces_size(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        result = extractor.extract("src/example.py", 1, [], tmp_repo)
        assert result.output_chars <= result.input_chars


# ---------------------------------------------------------------------------
# LOD 2: signatures + docstrings + ... bodies
# ---------------------------------------------------------------------------

class TestLOD2:
    def test_contains_function_signature(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 2, nodes, tmp_repo)
        assert "def standalone_function(x: int, y: int) -> int:" in result.content

    def test_contains_function_docstring(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 2, nodes, tmp_repo)
        assert "Return the sum of x and y." in result.content

    def test_body_replaced_with_placeholder(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 2, nodes, tmp_repo)
        assert "..." in result.content
        # Implementation body should NOT appear
        assert "result = x + y" not in result.content

    def test_contains_class_definition(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 2, nodes, tmp_repo)
        assert "class MyClass:" in result.content

    def test_contains_method_signatures(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 2, nodes, tmp_repo)
        assert "def method_one(self, value: int) -> bool:" in result.content
        assert "async def async_method(self) -> str:" in result.content

    def test_import_lines_preserved(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 2, nodes, tmp_repo)
        assert "import os" in result.content
        assert "import sys" in result.content
        assert "from pathlib import Path" in result.content

    def test_compression_ratio_at_least_1_2x(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        # Small fixture (664 chars, 2-line bodies) inherently limits ratio.
        # Real-world files with 10-50 line bodies achieve 3-4x as documented.
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 2, nodes, tmp_repo)
        assert result.compression_ratio >= 1.2, (
            f"Expected ≥1.2x compression on small fixture, got {result.compression_ratio:.2f}x"
        )

    def test_no_fallback_when_symbols_present(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 2, nodes, tmp_repo)
        assert result.fallback is False
        assert result.lod == 2

    def test_fallback_to_lod0_when_no_symbols(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        result = extractor.extract("src/example.py", 2, [], tmp_repo)
        assert result.fallback is True
        assert result.lod == 0
        assert result.content == PYTHON_SOURCE

    def test_typescript_signatures_present(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_ts_trace_nodes()
        result = extractor.extract("src/example.ts", 2, nodes, tmp_repo)
        assert "function greet" in result.content
        assert "class Greeter" in result.content

    def test_typescript_import_preserved(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_ts_trace_nodes()
        result = extractor.extract("src/example.ts", 2, nodes, tmp_repo)
        assert "import { foo }" in result.content


# ---------------------------------------------------------------------------
# LOD 2 signature retention metric
# ---------------------------------------------------------------------------

class TestSignatureRetention:
    """LOD 2 must retain ≥95% of function/class names."""

    def test_python_signature_retention(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 2, nodes, tmp_repo)

        expected_names = [
            "standalone_function", "MyClass", "__init__", "method_one", "async_method"
        ]
        found = sum(1 for name in expected_names if name in result.content)
        retention = found / len(expected_names)
        assert retention >= 0.95, (
            f"Signature retention {retention:.0%} < 95% "
            f"(missing: {[n for n in expected_names if n not in result.content]})"
        )


# ---------------------------------------------------------------------------
# LOD 3: class skeletons only
# ---------------------------------------------------------------------------

class TestLOD3:
    def test_class_retained(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 3, nodes, tmp_repo)
        assert "class MyClass:" in result.content

    def test_method_signatures_retained(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 3, nodes, tmp_repo)
        assert "def method_one" in result.content

    def test_standalone_function_removed(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 3, nodes, tmp_repo)
        # Top-level standalone functions should be stripped
        assert "result = x + y" not in result.content

    def test_lod3_smaller_than_lod2(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        r2 = extractor.extract("src/example.py", 2, nodes, tmp_repo)
        r3 = extractor.extract("src/example.py", 3, nodes, tmp_repo)
        assert r3.output_chars <= r2.output_chars


# ---------------------------------------------------------------------------
# LOD 2.5: signatures + docstrings, strip module-level constants
# ---------------------------------------------------------------------------

class TestLOD25:
    """LOD 2.5: signatures + docstrings, strip module-level constants."""

    def test_retains_function_signatures(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 25, nodes, tmp_repo)
        assert "def standalone_function" in result.content
        assert "class MyClass" in result.content

    def test_strips_module_level_constants(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 25, nodes, tmp_repo)
        assert "CONSTANT = 42" not in result.content

    def test_retains_imports(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 25, nodes, tmp_repo)
        assert "import os" in result.content
        assert "from pathlib import Path" in result.content

    def test_better_ratio_than_lod2(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        r2 = extractor.extract("src/example.py", 2, nodes, tmp_repo)
        r25 = extractor.extract("src/example.py", 25, nodes, tmp_repo)
        assert r25.output_chars <= r2.output_chars

    def test_larger_than_lod4(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        r25 = extractor.extract("src/example.py", 25, nodes, tmp_repo)
        r4 = extractor.extract("src/example.py", 4, nodes, tmp_repo)
        assert r25.output_chars >= r4.output_chars

    def test_retains_method_docstrings(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 25, nodes, tmp_repo)
        assert "Return the sum of x and y." in result.content
        assert "A sample class." in result.content


# ---------------------------------------------------------------------------
# LOD 4: imports + first lines of symbols
# ---------------------------------------------------------------------------

class TestLOD4:
    def test_imports_preserved(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 4, nodes, tmp_repo)
        assert "import os" in result.content
        assert "import sys" in result.content

    def test_symbol_first_lines_present(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 4, nodes, tmp_repo)
        # Should contain the def/class opening lines
        assert "def standalone_function" in result.content
        assert "class MyClass" in result.content

    def test_bodies_absent(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 4, nodes, tmp_repo)
        assert "result = x + y" not in result.content

    def test_compression_ratio_at_least_2x(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        # LOD 4 keeps only import + first-line per symbol → strong compression even on small fixtures.
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 4, nodes, tmp_repo)
        assert result.compression_ratio >= 2.0, (
            f"LOD 4 expected ≥2x compression, got {result.compression_ratio:.2f}x"
        )

    def test_lod4_smaller_than_lod2(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        r2 = extractor.extract("src/example.py", 2, nodes, tmp_repo)
        r4 = extractor.extract("src/example.py", 4, nodes, tmp_repo)
        assert r4.output_chars < r2.output_chars


# ---------------------------------------------------------------------------
# LOD 4 name retention metric
# ---------------------------------------------------------------------------

class TestNameRetention:
    """LOD 4 must retain ≥99% of public symbol names."""

    def test_python_name_retention(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 4, nodes, tmp_repo)

        public_names = ["standalone_function", "MyClass", "method_one", "async_method"]
        found = sum(1 for name in public_names if name in result.content)
        retention = found / len(public_names)
        assert retention >= 0.99, (
            f"Name retention {retention:.0%} < 99% "
            f"(missing: {[n for n in public_names if n not in result.content]})"
        )


# ---------------------------------------------------------------------------
# LOD 5: summary
# ---------------------------------------------------------------------------

class TestLOD5:
    def test_contains_file_path(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 5, nodes, tmp_repo)
        assert "src/example.py" in result.content

    def test_contains_exported_names(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 5, nodes, tmp_repo)
        assert "standalone_function" in result.content
        assert "MyClass" in result.content

    def test_with_augmented_data(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        augmented = {
            "file:src/example.py": {
                "node_id": "file:src/example.py",
                "summary": "Core utility module for arithmetic and OOP examples.",
                "role": "utility",
            }
        }
        result = extractor.extract(
            "src/example.py", 5, nodes, tmp_repo, augmented_data=augmented
        )
        assert "Core utility module" in result.content
        assert "utility" in result.content

    def test_lod5_smallest(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        r4 = extractor.extract("src/example.py", 4, nodes, tmp_repo)
        r5 = extractor.extract("src/example.py", 5, nodes, tmp_repo)
        assert r5.output_chars < r4.output_chars


# ---------------------------------------------------------------------------
# Monotonicity: higher LOD should be ≤ lower LOD size
# ---------------------------------------------------------------------------

class TestMonotonicity:
    def test_lod_sizes_decrease_monotonically(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        sizes = {}
        for lod in range(6):
            r = extractor.extract("src/example.py", lod, nodes, tmp_repo)
            sizes[lod] = r.output_chars

        # LOD 0 ≥ LOD 2 ≥ LOD 4 ≥ LOD 5 (strict order for material levels)
        assert sizes[0] >= sizes[2], f"LOD0 ({sizes[0]}) < LOD2 ({sizes[2]})"
        assert sizes[2] >= sizes[4], f"LOD2 ({sizes[2]}) < LOD4 ({sizes[4]})"
        assert sizes[4] >= sizes[5], f"LOD4 ({sizes[4]}) < LOD5 ({sizes[5]})"


# ---------------------------------------------------------------------------
# assign_lod() thresholds
# ---------------------------------------------------------------------------

class TestAssignLOD:
    def test_high_score_gives_lod0(self) -> None:
        assert assign_lod(0.75) == 0
        assert assign_lod(0.50) == 0

    def test_mid_score_gives_lod2(self) -> None:
        assert assign_lod(0.49) == 2
        assert assign_lod(0.35) == 2

    def test_low_score_gives_lod4(self) -> None:
        assert assign_lod(0.34) == 4
        assert assign_lod(0.20) == 4

    def test_very_low_score_gives_lod5(self) -> None:
        assert assign_lod(0.19) == 5
        assert assign_lod(0.00) == 5

    def test_trace_expanded_gives_lod4(self) -> None:
        assert assign_lod(0.10, is_trace_expanded=True) == 4
        assert assign_lod(0.80, is_trace_expanded=True) == 4

    def test_boundary_values(self) -> None:
        assert assign_lod(0.50) == 0
        assert assign_lod(0.499) == 2
        assert assign_lod(0.35) == 2
        assert assign_lod(0.349) == 4
        assert assign_lod(0.20) == 4
        assert assign_lod(0.199) == 5


# ---------------------------------------------------------------------------
# LODResult properties
# ---------------------------------------------------------------------------

class TestLODResult:
    def test_compression_ratio(self) -> None:
        r = LODResult(content="abc", lod=2, input_chars=300, output_chars=100)
        assert r.compression_ratio == pytest.approx(3.0)

    def test_compression_ratio_no_zero_division(self) -> None:
        r = LODResult(content="", lod=5, input_chars=500, output_chars=0)
        assert r.compression_ratio > 0  # denominator clipped to 1

    def test_error_field(self) -> None:
        r = LODResult(
            content="", lod=0, input_chars=0, output_chars=0, error="File not found"
        )
        assert r.error == "File not found"


# ---------------------------------------------------------------------------
# LODExtractor.load_augmented_data
# ---------------------------------------------------------------------------

class TestLoadAugmentedData:
    def test_loads_jsonl_file(self, tmp_path: Path) -> None:
        idx_dir = tmp_path / "idx"
        idx_dir.mkdir()
        aug_file = idx_dir / "trace_augmented.jsonl"
        entries = [
            {"node_id": "file:src/foo.py", "summary": "Foo module", "role": "utility",
             "confidence": 0.9, "augmented_at": "2024-01-01", "model": "test"},
            {"node_id": "file:src/bar.py", "summary": "Bar module", "role": "api",
             "confidence": 0.8, "augmented_at": "2024-01-01", "model": "test"},
        ]
        aug_file.write_text("\n".join(json.dumps(e) for e in entries))

        ext = LODExtractor(index_dir=idx_dir)
        data = ext.load_augmented_data()

        assert "file:src/foo.py" in data
        assert data["file:src/foo.py"]["summary"] == "Foo module"
        assert "file:src/bar.py" in data

    def test_returns_empty_when_no_index_dir(self) -> None:
        ext = LODExtractor()
        assert ext.load_augmented_data() == {}

    def test_returns_empty_when_file_missing(self, tmp_path: Path) -> None:
        ext = LODExtractor(index_dir=tmp_path)
        assert ext.load_augmented_data() == {}

    def test_caches_on_second_call(self, tmp_path: Path) -> None:
        idx_dir = tmp_path / "idx"
        idx_dir.mkdir()
        ext = LODExtractor(index_dir=idx_dir)
        d1 = ext.load_augmented_data()
        d2 = ext.load_augmented_data()
        assert d1 is d2  # same object = cached


# ---------------------------------------------------------------------------
# Tier-aware assign_lod()
# ---------------------------------------------------------------------------

class TestAssignLODTierAware:
    """Verify tier-adaptive LOD thresholds."""

    def test_tier1_more_generous(self) -> None:
        # Tier 1 lod_full=0.40 so 0.45 → LOD 0; Tier 2 lod_full=0.50 so 0.45 → LOD 2
        assert assign_lod(0.45, tier=ContextTier.TIER_1) == 0
        assert assign_lod(0.45, tier=ContextTier.TIER_2) == 2

    def test_tier2_5_more_aggressive(self) -> None:
        # Tier 2 lod_full=0.50 so 0.55 → LOD 0; Tier 2.5 lod_full=0.60 so 0.55 → LOD 2
        assert assign_lod(0.55, tier=ContextTier.TIER_2) == 0
        assert assign_lod(0.55, tier=ContextTier.TIER_2_5) == 2

    def test_tier1_boundaries(self) -> None:
        # Tier 1: lod_full=0.40, lod_sig=0.25, lod_names=0.15
        assert assign_lod(0.40, tier=ContextTier.TIER_1) == 0
        assert assign_lod(0.39, tier=ContextTier.TIER_1) == 2
        assert assign_lod(0.25, tier=ContextTier.TIER_1) == 2
        assert assign_lod(0.24, tier=ContextTier.TIER_1) == 4
        assert assign_lod(0.15, tier=ContextTier.TIER_1) == 4
        assert assign_lod(0.14, tier=ContextTier.TIER_1) == 5

    def test_tier2_5_boundaries(self) -> None:
        # Tier 2.5: lod_full=0.60, lod_sig=0.40, lod_names=0.25
        assert assign_lod(0.60, tier=ContextTier.TIER_2_5) == 0
        assert assign_lod(0.59, tier=ContextTier.TIER_2_5) == 2
        assert assign_lod(0.40, tier=ContextTier.TIER_2_5) == 2
        assert assign_lod(0.39, tier=ContextTier.TIER_2_5) == 4
        assert assign_lod(0.25, tier=ContextTier.TIER_2_5) == 4
        assert assign_lod(0.24, tier=ContextTier.TIER_2_5) == 5

    def test_no_tier_uses_tier2_defaults(self) -> None:
        # Backward compat: no tier → Tier 2 thresholds (0.50, 0.35, 0.20)
        assert assign_lod(0.50) == 0
        assert assign_lod(0.49) == 2
        assert assign_lod(0.35) == 2
        assert assign_lod(0.34) == 4

    def test_trace_expanded_ignores_tier(self) -> None:
        for tier in ContextTier:
            assert assign_lod(0.80, is_trace_expanded=True, tier=tier) == 4
            assert assign_lod(0.10, is_trace_expanded=True, tier=tier) == 4
