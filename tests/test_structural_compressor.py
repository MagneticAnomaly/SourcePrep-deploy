"""Tests for structural compression: symbol registry and compressor."""
import pytest

from codrag.core.compression.symbol_registry import SymbolRegistry
from codrag.core.compressor import StructuralCompressor


def test_registry_generates_short_codes() -> None:
    reg = SymbolRegistry()
    reg.register_paths([
        "src/codrag/core/swarm_orchestrator.py",
        "src/codrag/services/observation_store.py",
        "src/codrag/mcp/server.py",
    ])
    code = reg.get_code("src/codrag/core/swarm_orchestrator.py")
    assert code is not None
    assert 2 <= len(code) <= 5
    assert code == code.upper()


def test_registry_codes_are_unique() -> None:
    reg = SymbolRegistry()
    paths = [f"src/module{i}/file{j}.py" for i in range(10) for j in range(5)]
    reg.register_paths(paths)
    codes = [reg.get_code(p) for p in paths]
    assert len(set(codes)) == len(codes)


def test_registry_roundtrips() -> None:
    reg = SymbolRegistry()
    reg.register_paths(["src/auth/login.py"])
    code = reg.get_code("src/auth/login.py")
    resolved = reg.resolve(code)
    assert resolved == "src/auth/login.py"


def test_registry_generates_legend() -> None:
    reg = SymbolRegistry()
    reg.register_paths(["src/auth/login.py", "src/db/schema.py"])
    legend = reg.legend()
    assert "src/auth/login.py" in legend
    assert "src/db/schema.py" in legend
    assert len(legend) < 200


def test_registry_compress_text_replaces_paths() -> None:
    reg = SymbolRegistry()
    reg.register_paths(["src/auth/login.py"])
    code = reg.get_code("src/auth/login.py")
    text = "The file src/auth/login.py handles authentication."
    compressed = reg.compress_text(text)
    assert code in compressed
    assert "src/auth/login.py" not in compressed


def test_structural_compressor_compresses_paths() -> None:
    comp = StructuralCompressor(paths=["src/auth/login.py", "src/db/schema.py"])
    # Repeat paths many times so path shortening overcomes legend overhead
    text = (
        "The file src/auth/login.py imports from src/db/schema.py. "
        "Changes to src/auth/login.py will affect authentication. "
        "Verify src/auth/login.py and src/db/schema.py are in sync. "
        "src/auth/login.py reads src/db/schema.py on every request. "
        "Audit: src/auth/login.py, src/db/schema.py, src/auth/login.py. "
    ) * 3
    result = comp.compress(text)
    assert result.compression_ratio > 1.0
    assert result.output_chars < result.input_chars
    assert "LEGEND:" in result.compressed
    # Paths appear in the legend header but NOT in the body of compressed text
    body = result.compressed.split("\n\n", 1)[1] if "\n\n" in result.compressed else result.compressed
    assert "src/auth/login.py" not in body
    assert "src/db/schema.py" not in body


def test_structural_compressor_is_available() -> None:
    comp = StructuralCompressor(paths=[])
    assert comp.is_available() is True


def test_structural_compressor_passthrough_when_no_paths() -> None:
    comp = StructuralCompressor(paths=[])
    result = comp.compress("Hello world")
    assert result.compressed == "Hello world"
    assert result.compression_ratio == 1.0


def test_structural_compressor_respects_budget() -> None:
    comp = StructuralCompressor(paths=["src/auth/login.py"])
    long_text = "src/auth/login.py " * 500
    result = comp.compress(long_text, budget_chars=200)
    assert result.output_chars <= 250  # Allow some slack for legend
