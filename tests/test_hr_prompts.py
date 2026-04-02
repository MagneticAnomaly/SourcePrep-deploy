"""Tests for HR prompt template rendering."""
from codrag.agents.hr.prompts import (
    render_agents_md_prompt,
    render_soul_md_prompt,
    render_knowledge_md,
    render_auto_roles_prompt,
)


class TestAgentsMdPrompt:
    def test_includes_role_name(self) -> None:
        result = render_agents_md_prompt(
            role_name="Backend Developer",
            role_slug="backend_dev",
            atlas_excerpt="# Project\nPython backend",
            modules_summary="core (15 files), api (10 files)",
            recommended_files=["src/core/main.py", "src/api/routes.py"],
        )
        assert "Backend Developer" in result
        assert "backend_dev" in result

    def test_includes_atlas_excerpt(self) -> None:
        result = render_agents_md_prompt(
            role_name="Dev",
            role_slug="dev",
            atlas_excerpt="Python + FastAPI monolith",
            modules_summary="",
            recommended_files=[],
        )
        assert "Python + FastAPI monolith" in result

    def test_includes_recommended_files(self) -> None:
        result = render_agents_md_prompt(
            role_name="Dev",
            role_slug="dev",
            atlas_excerpt="",
            modules_summary="",
            recommended_files=["src/main.py", "src/config.py"],
        )
        assert "src/main.py" in result


class TestSoulMdPrompt:
    def test_includes_role_name(self) -> None:
        result = render_soul_md_prompt(
            role_name="CTO",
            role_slug="cto",
            atlas_excerpt="Large enterprise platform",
        )
        assert "CTO" in result

    def test_includes_context(self) -> None:
        result = render_soul_md_prompt(
            role_name="Dev",
            role_slug="dev",
            atlas_excerpt="React dashboard with charts",
        )
        assert "React dashboard" in result


class TestKnowledgeMd:
    def test_renders_template_with_tools(self) -> None:
        result = render_knowledge_md(
            role_name="Backend Developer",
            role_slug="backend_dev",
            atlas_snapshot="# Atlas\nPython backend",
            recommended_files=[("src/main.py", 0.95), ("src/config.py", 0.82)],
            domain_focus=["backend", "database"],
            project_id="proj_123",
        )
        assert "codrag" in result
        assert "backend_dev" in result
        assert "src/main.py" in result
        assert "0.95" in result or "95" in result
        assert "proj_123" in result

    def test_no_llm_needed(self) -> None:
        """KNOWLEDGE.md is template-based, not LLM-generated."""
        result = render_knowledge_md(
            role_name="Dev",
            role_slug="dev",
            atlas_snapshot="atlas",
            recommended_files=[],
            domain_focus=[],
            project_id="p",
        )
        assert isinstance(result, str)
        assert len(result) > 50


class TestAutoRolesPrompt:
    def test_includes_codebase_stats(self) -> None:
        result = render_auto_roles_prompt(
            file_count=150,
            module_count=8,
            modules_summary="core (30 files), api (20 files), ui (25 files)",
            atlas_excerpt="Full-stack Python + React app",
            domain_tags=["backend", "frontend", "api", "database", "auth"],
            layer_distribution={"core": 30, "api": 20, "presentation": 25},
        )
        assert "150" in result
        assert "8" in result
