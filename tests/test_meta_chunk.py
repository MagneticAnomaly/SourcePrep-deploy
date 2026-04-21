"""Tests for meta-chunk synopsis extraction and injection."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from prep.core.chunking import extract_file_synopsis

SAMPLE_PYTHON = '''"""
Pipeline orchestrator for multi-stage builds.

This module coordinates build stages, manages dependencies,
and handles error recovery for the Prep indexing pipeline.
"""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Coordinates execution of multi-stage build pipelines.

    Manages stage ordering, dependency resolution, and
    parallel execution where possible.
    """

    def __init__(self, config: dict) -> None:
        self._config = config
        self._stages: List[str] = []

    def run_stage(self, name: str) -> bool:
        """Execute a single pipeline stage by name."""
        return True

    def process_files(self, paths: List[str]) -> int:
        """Process a batch of files through the pipeline."""
        return len(paths)

    def _internal_setup(self) -> None:
        """Private setup method."""
        pass

    def _validate(self) -> bool:
        """Private validation."""
        return True


class StageResult:
    """Container for stage execution results.

    Holds timing info, error state, and output artifacts.
    """

    def __init__(self, stage_name: str, success: bool) -> None:
        self.stage_name = stage_name
        self.success = success
        self.errors: List[str] = []

    def summary(self) -> str:
        """Return a human-readable summary of this result."""
        return f"{self.stage_name}: {'ok' if self.success else 'fail'}"


def create_orchestrator(config: dict) -> PipelineOrchestrator:
    """Factory function for creating configured orchestrators."""
    return PipelineOrchestrator(config)


def validate_config(config: dict) -> bool:
    """Check that a pipeline config is well-formed."""
    return "stages" in config


def _private_helper() -> None:
    """This should not appear in the synopsis."""
    pass
'''


class TestExtractFileSynopsis:
    """Tests for the extract_file_synopsis helper."""

    def test_includes_file_path(self) -> None:
        result = extract_file_synopsis(SAMPLE_PYTHON, "src/pipeline/orchestrator.py")
        assert "src/pipeline/orchestrator.py" in result

    def test_extracts_module_docstring(self) -> None:
        result = extract_file_synopsis(SAMPLE_PYTHON, "orchestrator.py")
        assert "Pipeline orchestrator for multi-stage builds" in result

    def test_extracts_class_names(self) -> None:
        result = extract_file_synopsis(SAMPLE_PYTHON, "orchestrator.py")
        assert "PipelineOrchestrator" in result
        assert "StageResult" in result

    def test_extracts_class_docstrings(self) -> None:
        result = extract_file_synopsis(SAMPLE_PYTHON, "orchestrator.py")
        assert "Coordinates execution" in result
        assert "Container for stage execution results" in result

    def test_extracts_public_functions(self) -> None:
        result = extract_file_synopsis(SAMPLE_PYTHON, "orchestrator.py")
        assert "run_stage" in result
        assert "process_files" in result
        assert "create_orchestrator" in result
        assert "validate_config" in result
        assert "summary" in result

    def test_excludes_private_functions(self) -> None:
        result = extract_file_synopsis(SAMPLE_PYTHON, "orchestrator.py")
        assert "_internal_setup" not in result
        assert "_validate" not in result
        assert "_private_helper" not in result

    def test_respects_max_chars(self) -> None:
        result = extract_file_synopsis(SAMPLE_PYTHON, "orchestrator.py", max_chars=100)
        assert len(result) <= 100

    def test_handles_empty_file(self) -> None:
        result = extract_file_synopsis("", "empty.py")
        assert "empty.py" in result

    def test_handles_file_with_no_classes(self) -> None:
        code = '"""A utility module."""\n\ndef helper() -> None:\n    pass\n'
        result = extract_file_synopsis(code, "utils.py")
        assert "utils.py" in result
        assert "utility module" in result
        assert "helper" in result
        assert "Classes" not in result


class TestMetaChunkInBuild:
    """Tests that meta-chunk injection works in the CodeIndex build loop."""

    def test_meta_synopsis_injected_for_multi_chunk_files(self, tmp_path: object) -> None:
        from pathlib import Path
        from prep.core.index import CodeIndex

        tmp = Path(str(tmp_path))
        project_dir = tmp / "project"
        project_dir.mkdir()

        # Generate a Python file large enough to produce multiple chunks (>2000 chars)
        lines = ['"""Big module with many functions."""\n\n']
        lines.append("class BigClass:\n")
        lines.append('    """A class with many methods."""\n\n')
        for i in range(80):
            lines.append(f"    def func_{i}(self) -> int:\n")
            lines.append(f'        """Function number {i}."""\n')
            lines.append(f"        return {i}\n\n")
        big_content = "".join(lines)
        (project_dir / "big_module.py").write_text(big_content)

        # Mock embedder
        mock_embedder = MagicMock()
        mock_result = MagicMock()
        mock_result.vector = [0.1] * 384
        mock_embedder.embed.return_value = mock_result
        mock_embedder.dimension = 384

        idx = CodeIndex(
            index_dir=tmp / "index",
            embedder=mock_embedder,
        )
        idx.build(repo_root=project_dir)

        # Find the meta-synopsis document
        meta_docs = [d for d in idx._documents if d.get("section") == "META_SYNOPSIS"]
        assert len(meta_docs) == 1, f"Expected 1 META_SYNOPSIS doc, got {len(meta_docs)}"

        meta = meta_docs[0]
        assert "big_module.py" in meta["content"]
        assert "BigClass" in meta["content"]
