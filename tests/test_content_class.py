"""Tests for Phase 53 content classification and treatment registry.

Tests the ContentClass enum, classify_node/classify_nodes functions,
and TreatmentRegistry.
"""

import pytest

from prep.core.content_class import (
    ContentClass,
    classify_node,
    classify_nodes,
)
from prep.core.treatment_registry import TreatmentConfig, TreatmentRegistry


# ── Fixtures ─────────────────────────────────────────────────────────


def _make_node(
    file_path: str,
    language: str = "",
    section_count: int = 0,
    ref_count: int = 0,
    link_count: int = 0,
    line_count: int = 0,
) -> dict:
    """Create a minimal trace node dict for testing."""
    return {
        "id": f"file:{file_path}",
        "kind": "file",
        "name": file_path.rsplit("/", 1)[-1],
        "file_path": file_path,
        "language": language,
        "metadata": {
            "section_count": section_count,
            "ref_count": ref_count,
            "link_count": link_count,
            "line_count": line_count,
        },
    }


# ── classify_node tests ─────────────────────────────────────────────


class TestClassifyNode:
    """Tests for classify_node()."""

    def test_python_file_is_structured_code(self):
        node = _make_node("src/main.py", language="python")
        assert classify_node(node) == ContentClass.STRUCTURED_CODE

    def test_typescript_file_is_structured_code(self):
        node = _make_node("src/app.ts", language="typescript")
        assert classify_node(node) == ContentClass.STRUCTURED_CODE

    def test_rust_file_is_structured_code(self):
        node = _make_node("src/lib.rs", language="rust")
        assert classify_node(node) == ContentClass.STRUCTURED_CODE

    def test_json_config_file_is_structured_code(self):
        """Config files (.json, .yaml) get code treatment (conservative)."""
        node = _make_node("config/settings.json", language="")
        assert classify_node(node) == ContentClass.STRUCTURED_CODE

    def test_yaml_file_is_structured_code(self):
        node = _make_node("docker-compose.yaml", language="")
        assert classify_node(node) == ContentClass.STRUCTURED_CODE

    def test_api_docs_is_structured_docs(self):
        """Markdown with many refs + sections = StructuredDocs."""
        node = _make_node(
            "docs/API.md",
            language="markdown",
            section_count=12,
            ref_count=8,
            link_count=5,
            line_count=500,
        )
        assert classify_node(node) == ContentClass.STRUCTURED_DOCS

    def test_implementation_plan_is_structured_docs(self):
        """Technical spec with rich cross-references."""
        node = _make_node(
            "docs/IMPLEMENTATION.md",
            language="markdown",
            section_count=15,
            ref_count=10,
            link_count=3,
            line_count=800,
        )
        assert classify_node(node) == ContentClass.STRUCTURED_DOCS

    def test_marketing_copy_is_narrative(self):
        """Unstructured marketing doc with few sections/refs."""
        node = _make_node(
            "Marketing_Copy.md",
            language="markdown",
            section_count=2,
            ref_count=0,
            link_count=0,
            line_count=100,
        )
        assert classify_node(node) == ContentClass.UNSTRUCTURED_NARRATIVE

    def test_simple_readme_is_narrative(self):
        """Simple README without many cross-references."""
        node = _make_node(
            "README.md",
            language="markdown",
            section_count=3,
            ref_count=1,
            link_count=2,
            line_count=50,
        )
        assert classify_node(node) == ContentClass.UNSTRUCTURED_NARRATIVE

    def test_changelog_is_narrative(self):
        """Changelogs have sections but typically low ref counts."""
        node = _make_node(
            "CHANGELOG.md",
            language="markdown",
            section_count=20,
            ref_count=0,
            link_count=0,
            line_count=500,
        )
        assert classify_node(node) == ContentClass.UNSTRUCTURED_NARRATIVE

    def test_borderline_structured_docs(self):
        """Just at the threshold: ref_count=3 and section_count=5."""
        node = _make_node(
            "docs/guide.md",
            language="markdown",
            section_count=5,
            ref_count=3,
            link_count=0,
        )
        assert classify_node(node) == ContentClass.STRUCTURED_DOCS

    def test_just_below_threshold_is_narrative(self):
        """Below threshold: ref_count=2 or section_count=4."""
        node = _make_node(
            "docs/notes.md",
            language="markdown",
            section_count=4,
            ref_count=3,
        )
        assert classify_node(node) == ContentClass.UNSTRUCTURED_NARRATIVE

    def test_missing_metadata_non_markdown(self):
        """Non-markdown file with no metadata still classifies as code."""
        node = {"id": "file:app.py", "file_path": "app.py", "language": "python"}
        assert classify_node(node) == ContentClass.STRUCTURED_CODE

    def test_missing_metadata_markdown(self):
        """Markdown with missing metadata defaults to narrative."""
        node = {"id": "file:notes.md", "file_path": "notes.md", "language": "markdown"}
        assert classify_node(node) == ContentClass.UNSTRUCTURED_NARRATIVE

    def test_md_extension_without_language_field(self):
        """File with .md extension but no language field."""
        node = _make_node("README.md", language="", section_count=1, ref_count=0)
        assert classify_node(node) == ContentClass.UNSTRUCTURED_NARRATIVE


# ── classify_nodes tests ─────────────────────────────────────────────


class TestClassifyNodes:
    """Tests for classify_nodes()."""

    def test_empty_list(self):
        result = classify_nodes([])
        assert result == {}

    def test_groups_mixed_input(self):
        nodes = [
            _make_node("src/main.py", language="python"),
            _make_node("docs/API.md", language="markdown", section_count=10, ref_count=5),
            _make_node("README.md", language="markdown", section_count=2, ref_count=0),
            _make_node("src/utils.ts", language="typescript"),
        ]
        result = classify_nodes(nodes)

        assert len(result[ContentClass.STRUCTURED_CODE]) == 2
        assert len(result[ContentClass.STRUCTURED_DOCS]) == 1
        assert len(result[ContentClass.UNSTRUCTURED_NARRATIVE]) == 1

    def test_all_code(self):
        nodes = [
            _make_node("a.py", language="python"),
            _make_node("b.rs", language="rust"),
        ]
        result = classify_nodes(nodes)
        assert ContentClass.STRUCTURED_CODE in result
        assert ContentClass.STRUCTURED_DOCS not in result
        assert ContentClass.UNSTRUCTURED_NARRATIVE not in result


# ── TreatmentRegistry tests ─────────────────────────────────────────


class TestTreatmentRegistry:
    """Tests for TreatmentRegistry."""

    def test_all_classes_have_treatment(self):
        for cc in ContentClass:
            treatment = TreatmentRegistry.get_treatment(cc)
            assert isinstance(treatment, TreatmentConfig)
            assert treatment.context_lines > 0
            assert treatment.system_prompt_key in ("file", "doc", "narrative")

    def test_code_treatment(self):
        t = TreatmentRegistry.get_treatment(ContentClass.STRUCTURED_CODE)
        assert t.context_lines == 30
        assert t.use_strategic_excerpt is False
        assert t.system_prompt_key == "file"

    def test_docs_treatment(self):
        t = TreatmentRegistry.get_treatment(ContentClass.STRUCTURED_DOCS)
        assert t.context_lines == 200
        assert t.use_strategic_excerpt is True
        assert t.system_prompt_key == "doc"

    def test_narrative_treatment(self):
        t = TreatmentRegistry.get_treatment(ContentClass.UNSTRUCTURED_NARRATIVE)
        assert t.context_lines == 50
        assert t.use_strategic_excerpt is False
        assert t.system_prompt_key == "narrative"

    def test_compute_batch_size_code(self):
        size = TreatmentRegistry.compute_batch_size(ContentClass.STRUCTURED_CODE, 10)
        assert size == 10  # divisor=1

    def test_compute_batch_size_docs(self):
        size = TreatmentRegistry.compute_batch_size(ContentClass.STRUCTURED_DOCS, 10)
        assert size == 2  # 10 // 5

    def test_compute_batch_size_narrative(self):
        size = TreatmentRegistry.compute_batch_size(ContentClass.UNSTRUCTURED_NARRATIVE, 10)
        assert size == 1  # forced to 1

    def test_compute_batch_size_minimum(self):
        """Even with tiny profile batch size, result is always >= 1."""
        size = TreatmentRegistry.compute_batch_size(ContentClass.STRUCTURED_DOCS, 1)
        assert size >= 1

    def test_frozen_config(self):
        """TreatmentConfig should be immutable."""
        t = TreatmentRegistry.get_treatment(ContentClass.STRUCTURED_CODE)
        with pytest.raises(AttributeError):
            t.context_lines = 999
