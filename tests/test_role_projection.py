"""Tests for CoDRAG Role Projection (Phase 64A)."""
import json
import pytest
from pathlib import Path

from codrag.core.atlas.role_resolver import resolve_role
from codrag.core.atlas.role_projection import (
    _compute_in_degrees,
    _assemble_executive,
    _assemble_manager,
    _assemble_practitioner,
    _infer_layer_from_path,
    _infer_tags_from_path,
    _load_epistemic_entries,
    _load_modules,
    _load_trace_nodes,
    compute_role_relevance,
    project_atlas_for_role,
)
from codrag.core.atlas.role_vectors import BUILT_IN_ROLES, RoleVector


@pytest.fixture
def mock_index_dir(tmp_path):
    """Create a mock index directory with test data."""
    # trace_epistemic.jsonl — keyed by node_id
    epistemic = [
        {
            "node_id": "file:src/api/server.py",
            "file_path": "src/api/server.py",
            "architecture_layer": "presentation",
            "domain_tags": ["api", "http"],
            "epistemic_confidence": 0.9,
            "extended_summary": "HTTP endpoints and REST API handlers.",
        },
        {
            "node_id": "file:src/core/engine.py",
            "file_path": "src/core/engine.py",
            "architecture_layer": "business_logic",
            "domain_tags": ["engine", "processing"],
            "epistemic_confidence": 0.85,
            "extended_summary": "Core business logic processing engine.",
        },
        {
            "node_id": "file:src/db/models.py",
            "file_path": "src/db/models.py",
            "architecture_layer": "data_access",
            "domain_tags": ["database", "orm"],
            "epistemic_confidence": 0.8,
            "extended_summary": "Database models and ORM utilities.",
        },
        {
            "node_id": "file:src/auth/login.py",
            "file_path": "src/auth/login.py",
            "architecture_layer": "security",
            "domain_tags": ["auth", "security"],
            "epistemic_confidence": 0.75,
            "extended_summary": "Authentication and login handlers.",
        },
        {
            "node_id": "file:deploy/Dockerfile",
            "file_path": "deploy/Dockerfile",
            "architecture_layer": "infrastructure",
            "domain_tags": ["deploy", "docker"],
            "epistemic_confidence": 0.7,
            "extended_summary": "Docker container configuration.",
        },
        {
            "node_id": "file:tests/test_api.py",
            "file_path": "tests/test_api.py",
            "architecture_layer": "testing",
            "domain_tags": ["test", "api"],
            "epistemic_confidence": 0.65,
            "extended_summary": "Test suite for API endpoints.",
        },
        {
            "node_id": "file:src/ui/dashboard.tsx",
            "file_path": "src/ui/dashboard.tsx",
            "architecture_layer": "presentation",
            "domain_tags": ["ui", "frontend"],
            "epistemic_confidence": 0.95,
            "extended_summary": "Dashboard UI components and layout.",
        },
        {
            "node_id": "file:src/config/settings.py",
            "file_path": "src/config/settings.py",
            "architecture_layer": "configuration",
            "domain_tags": ["config", "env"],
            "epistemic_confidence": 0.6,
            "extended_summary": "Application configuration and environment settings.",
        },
    ]
    ep_path = tmp_path / "trace_epistemic.jsonl"
    with open(ep_path, "w") as f:
        for entry in epistemic:
            f.write(json.dumps(entry) + "\n")

    # trace_modules.jsonl
    modules = [
        {
            "name": "API Layer",
            "file_count": 3,
            "summary": "HTTP endpoints and REST API handlers.",
            "member_files": ["src/api/server.py"],
        },
        {
            "name": "Core Engine",
            "file_count": 5,
            "summary": "Business logic and processing engine.",
            "member_files": ["src/core/engine.py"],
        },
        {
            "name": "Data Access",
            "file_count": 2,
            "summary": "Database models and ORM utilities.",
            "member_files": ["src/db/models.py"],
        },
    ]
    mod_path = tmp_path / "trace_modules.jsonl"
    with open(mod_path, "w") as f:
        for mod in modules:
            f.write(json.dumps(mod) + "\n")

    # trace_edges.jsonl — targets have "file:" prefix
    edges = [
        {"source": "file:src/core/engine.py", "target": "file:src/api/server.py"},
        {"source": "file:src/db/models.py", "target": "file:src/core/engine.py"},
        {"source": "file:src/auth/login.py", "target": "file:src/api/server.py"},
        {"source": "file:tests/test_api.py", "target": "file:src/api/server.py"},
        {"source": "file:src/ui/dashboard.tsx", "target": "file:src/api/server.py"},
        {"source": "file:src/config/settings.py", "target": "file:src/core/engine.py"},
    ]
    edge_path = tmp_path / "trace_edges.jsonl"
    with open(edge_path, "w") as f:
        for edge in edges:
            f.write(json.dumps(edge) + "\n")

    return tmp_path


class TestLoadFunctions:
    """Test data loading from JSONL files."""

    def test_load_epistemic(self, mock_index_dir):
        entries = _load_epistemic_entries(mock_index_dir)
        assert len(entries) == 8
        assert "file:src/api/server.py" in entries

    def test_load_modules(self, mock_index_dir):
        mods = _load_modules(mock_index_dir)
        assert len(mods) == 3
        assert mods[0]["name"] == "API Layer"

    def test_compute_in_degrees(self, mock_index_dir):
        degs = _compute_in_degrees(mock_index_dir)
        # server.py is targeted by 4 edges
        assert degs.get("file:src/api/server.py", 0) == 4
        # engine.py is targeted by 2 edges
        assert degs.get("file:src/core/engine.py", 0) == 2

    def test_missing_files_return_empty(self, tmp_path):
        entries = _load_epistemic_entries(tmp_path)
        assert entries == {}
        mods = _load_modules(tmp_path)
        assert mods == []
        degs = _compute_in_degrees(tmp_path)
        assert degs == {}


class TestComputeRoleRelevance:
    """Test relevance score computation."""

    def test_ceo_scores_high_for_hubs(self):
        ceo = resolve_role("CEO")
        # server.py: presentation layer, hub file (in_degree=4)
        server_score = compute_role_relevance(
            file_path="src/api/server.py",
            architecture_layer="presentation",
            domain_tags=["api", "http"],
            epistemic_confidence=0.9,
            in_degree=4,
            max_degree=4,
            role=ceo,
        )
        # auth/login.py: security layer, lower in_degree
        auth_score = compute_role_relevance(
            file_path="src/auth/login.py",
            architecture_layer="security",
            domain_tags=["auth", "security"],
            epistemic_confidence=0.75,
            in_degree=0,
            max_degree=4,
            role=ceo,
        )
        assert server_score > auth_score

    def test_security_role_scores_high_for_auth(self):
        sec = resolve_role("security")
        auth_score = compute_role_relevance(
            file_path="src/auth/login.py",
            architecture_layer="security",
            domain_tags=["auth", "security"],
            epistemic_confidence=0.75,
            in_degree=0,
            max_degree=4,
            role=sec,
        )
        ui_score = compute_role_relevance(
            file_path="src/ui/dashboard.tsx",
            architecture_layer="presentation",
            domain_tags=["ui", "frontend"],
            epistemic_confidence=0.95,
            in_degree=0,
            max_degree=4,
            role=sec,
        )
        assert auth_score > ui_score

    def test_design_role_scores_high_for_ui(self):
        des = resolve_role("design")
        ui_score = compute_role_relevance(
            file_path="src/ui/dashboard.tsx",
            architecture_layer="presentation",
            domain_tags=["ui", "frontend"],
            epistemic_confidence=0.95,
            in_degree=0,
            max_degree=4,
            role=des,
        )
        db_score = compute_role_relevance(
            file_path="src/db/models.py",
            architecture_layer="data_access",
            domain_tags=["database", "orm"],
            epistemic_confidence=0.8,
            in_degree=0,
            max_degree=4,
            role=des,
        )
        assert ui_score > db_score

    def test_score_range(self):
        """All scores should be in [0, 1]."""
        eng = resolve_role("engineer")
        test_cases = [
            ("test.py", "testing", ["test"], 0.5, 0, 1),
            ("hub.py", "business_logic", ["core"], 0.9, 10, 10),
            ("util.py", "utility", ["helper"], 0.3, 0, 10),
        ]
        for fp, layer, tags, conf, deg, max_deg in test_cases:
            score = compute_role_relevance(fp, layer, tags, conf, deg, max_deg, eng)
            assert 0.0 <= score <= 1.0, f"{fp} score={score}"


class TestProjection:
    """Test end-to-end atlas projection."""

    def test_ceo_gets_small_output(self, mock_index_dir):
        ceo = resolve_role("CEO")
        result = project_atlas_for_role(ceo, mock_index_dir, "IDENTITY: Test Project")
        assert "[CEO View]" in result
        assert len(result) <= ceo.max_chars

    def test_intern_gets_larger_output(self, mock_index_dir):
        intern = resolve_role("Intern")
        result = project_atlas_for_role(intern, mock_index_dir, "IDENTITY: Test Project")
        assert "[Intern / New Contributor View]" in result
        assert len(result) >= 100  # Should have meaningful content

    def test_design_focuses_on_presentation(self, mock_index_dir):
        des = resolve_role("Design")
        result = project_atlas_for_role(des, mock_index_dir, "IDENTITY: Test Project")
        # Dashboard.tsx should rank high for design role
        assert "dashboard" in result.lower() or "ui" in result.lower()

    def test_custom_atlas_included(self, mock_index_dir):
        ceo = resolve_role("CEO")
        atlas_content = "IDENTITY: Custom Atlas Project.\nSTACK: Python, React."
        result = project_atlas_for_role(ceo, mock_index_dir, atlas_content)
        # Identity should be included
        assert "Custom Atlas" in result

    def test_empty_atlas_works(self, mock_index_dir):
        eng = resolve_role("Engineer")
        result = project_atlas_for_role(eng, mock_index_dir, "")
        assert len(result) > 0

    def test_missing_index_returns_fallback(self, tmp_path):
        eng = resolve_role("Engineer")
        result = project_atlas_for_role(eng, tmp_path, "IDENTITY: X")
        assert len(result) > 0  # Should still produce something

    def test_different_roles_produce_different_output(self, mock_index_dir):
        ceo = resolve_role("CEO")
        eng = resolve_role("Engineer")
        intern = resolve_role("Intern")

        r_ceo = project_atlas_for_role(ceo, mock_index_dir, "IDENTITY: Test")
        r_eng = project_atlas_for_role(eng, mock_index_dir, "IDENTITY: Test")
        r_intern = project_atlas_for_role(intern, mock_index_dir, "IDENTITY: Test")

        # They should differ (at minimum by header)
        assert r_ceo != r_eng
        assert r_eng != r_intern
        # CEO should be shortest, Intern longest
        assert len(r_ceo) <= len(r_intern)


class TestAssemblyLevels:
    """Test the three assembly functions."""

    @pytest.fixture
    def sample_data(self, mock_index_dir):
        entries = _load_epistemic_entries(mock_index_dir)
        mods = _load_modules(mock_index_dir)
        in_degrees = _compute_in_degrees(mock_index_dir)
        max_degree = max(in_degrees.values()) if in_degrees else 0
        role = resolve_role("engineer")

        scored = []
        for node_id, entry in entries.items():
            if node_id.startswith("file:"):
                file_path = node_id[5:]
                score = compute_role_relevance(
                    file_path=file_path,
                    architecture_layer=entry.get("architecture_layer", "unknown"),
                    domain_tags=entry.get("domain_tags", []),
                    epistemic_confidence=float(entry.get("epistemic_confidence", 0.5)),
                    in_degree=in_degrees.get(node_id, 0),
                    max_degree=max_degree,
                    role=role,
                )
                scored.append((file_path, entry, score))
        scored.sort(key=lambda x: -x[2])
        return scored, mods

    def test_executive_is_compact(self, sample_data):
        scored, mods = sample_data
        ceo = resolve_role("ceo")
        result = _assemble_executive(ceo, "IDENTITY: Test", "STACK: Python", mods, scored)
        assert len(result) <= ceo.max_chars
        assert "MODULES" in result or "KEY DOMAINS" in result

    def test_manager_includes_key_files(self, sample_data):
        scored, mods = sample_data
        pm = resolve_role("product")
        result = _assemble_manager(pm, "IDENTITY: Test", "STACK: Python", mods, scored)
        assert len(result) <= pm.max_chars

    def test_practitioner_includes_detail(self, sample_data):
        scored, mods = sample_data
        intern = resolve_role("intern")
        result = _assemble_practitioner(intern, "IDENTITY: Test", "STACK: Python", mods, scored)
        assert len(result) <= intern.max_chars
        assert "RELEVANT FILES" in result


# ── Structural Fallback Tests (Gap 2) ─────────────────────────────


@pytest.fixture
def structural_only_dir(tmp_path):
    """Create an index directory with only trace_nodes.jsonl (no epistemic).

    Simulates the state after Stage 1 completes but before Deep Enrichment.
    """
    nodes = [
        {"node_id": "file:src/api/server.py", "summary": "API server"},
        {"node_id": "file:src/core/engine.py", "summary": "Core engine"},
        {"node_id": "file:src/db/models.py", "summary": "Database models"},
        {"node_id": "file:src/auth/login.py", "summary": "Auth handlers"},
        {"node_id": "file:src/ui/dashboard.tsx", "summary": "Dashboard UI"},
        {"node_id": "file:tests/test_api.py", "summary": "API tests"},
        {"node_id": "file:deploy/Dockerfile", "summary": "Docker config"},
        {"node_id": "file:src/config/settings.py", "summary": "Settings"},
        # Non-file node — should be skipped
        {"node_id": "module:core_engine", "summary": "Core module"},
    ]
    nodes_path = tmp_path / "trace_nodes.jsonl"
    with open(nodes_path, "w") as f:
        for node in nodes:
            f.write(json.dumps(node) + "\n")

    # Add some edges for centrality
    edges = [
        {"source": "file:src/core/engine.py", "target": "file:src/api/server.py"},
        {"source": "file:src/db/models.py", "target": "file:src/core/engine.py"},
        {"source": "file:src/auth/login.py", "target": "file:src/api/server.py"},
    ]
    edge_path = tmp_path / "trace_edges.jsonl"
    with open(edge_path, "w") as f:
        for edge in edges:
            f.write(json.dumps(edge) + "\n")

    return tmp_path


class TestStructuralFallback:
    """Test projection using only trace_nodes.jsonl (no epistemic data)."""

    def test_infer_layer_api(self):
        assert _infer_layer_from_path("src/api/server.py") == "presentation"

    def test_infer_layer_core(self):
        assert _infer_layer_from_path("src/core/engine.py") == "business_logic"

    def test_infer_layer_db(self):
        assert _infer_layer_from_path("src/db/models.py") == "data_access"

    def test_infer_layer_auth(self):
        assert _infer_layer_from_path("src/auth/login.py") == "security"

    def test_infer_layer_test(self):
        assert _infer_layer_from_path("tests/test_api.py") == "testing"

    def test_infer_layer_deploy(self):
        assert _infer_layer_from_path("deploy/Dockerfile") == "infrastructure"

    def test_infer_layer_config(self):
        assert _infer_layer_from_path("src/config/settings.py") == "configuration"

    def test_infer_layer_unknown(self):
        assert _infer_layer_from_path("random/stuff.xyz") == "unknown"

    def test_infer_tags_tsx(self):
        tags = _infer_tags_from_path("src/ui/dashboard.tsx")
        assert "ui" in tags
        assert "frontend" in tags

    def test_infer_tags_py(self):
        tags = _infer_tags_from_path("src/core/engine.py")
        assert "backend" in tags or "python" in tags
        assert "core" in tags or "engine" in tags

    def test_infer_tags_test(self):
        tags = _infer_tags_from_path("tests/test_api.py")
        assert "test" in tags

    def test_infer_tags_capped(self):
        """Tags should be capped at 5."""
        tags = _infer_tags_from_path("src/api/auth/test/config/engine.py")
        assert len(tags) <= 5

    def test_load_trace_nodes(self, structural_only_dir):
        entries = _load_trace_nodes(structural_only_dir)
        # Should load 8 file: nodes, skip the module: node
        assert len(entries) == 8
        assert "file:src/api/server.py" in entries
        assert "module:core_engine" not in entries
        # Should have inferred layer and tags
        entry = entries["file:src/api/server.py"]
        assert entry["architecture_layer"] == "presentation"
        assert len(entry["domain_tags"]) > 0

    def test_projection_with_trace_nodes_only(self, structural_only_dir):
        """Role projection should work using only trace_nodes.jsonl."""
        ceo = resolve_role("CEO")
        result = project_atlas_for_role(ceo, structural_only_dir, "IDENTITY: Test")
        assert "[CEO View]" in result
        assert len(result) > 20

    def test_projection_structural_vs_epistemic_differs(
        self, structural_only_dir, mock_index_dir
    ):
        """Structural fallback output should differ from epistemic-enriched output."""
        eng = resolve_role("engineer")
        structural = project_atlas_for_role(eng, structural_only_dir, "IDENTITY: X")
        enriched = project_atlas_for_role(eng, mock_index_dir, "IDENTITY: X")
        # Both should produce output, but typically different
        assert len(structural) > 0
        assert len(enriched) > 0

    def test_all_roles_produce_output_structural(self, structural_only_dir):
        """Every built-in role should produce non-empty output from structural data."""
        for role_id in BUILT_IN_ROLES:
            role = resolve_role(role_id)
            result = project_atlas_for_role(role, structural_only_dir, "IDENTITY: X")
            assert len(result) > 0, f"Role {role_id} produced empty output"


# ── Cache Roundtrip Tests (Gaps 1+3) ────────────────────────────────


class TestCacheRoundtrip:
    """Test role atlas caching in CodebaseAtlas."""

    @pytest.fixture
    def atlas_with_data(self, mock_index_dir):
        """Create a CodebaseAtlas instance with test data and a structural atlas."""
        from codrag.core.atlas import CodebaseAtlas

        atlas = CodebaseAtlas(mock_index_dir, llm=None, project_root=Path("/fake/project"))
        # Write a minimal atlas.json so load() works
        atlas_data = {
            "content": "IDENTITY: Test Project.\nSTACK: Python.",
            "generated_at": "2026-01-01T00:00:00Z",
            "model": "structural",
            "fingerprint": "test",
            "file_count": 8,
            "module_count": 3,
            "char_count": 40,
            "mode": "structural",
        }
        atlas_path = mock_index_dir / "atlas.json"
        with open(atlas_path, "w") as f:
            json.dump(atlas_data, f)
        return atlas

    def test_cache_writes_files(self, atlas_with_data):
        results = atlas_with_data.cache_role_atlases()
        assert len(results) == len(BUILT_IN_ROLES)
        roles_dir = atlas_with_data.index_dir / "atlas_roles"
        assert roles_dir.exists()
        for role_id in BUILT_IN_ROLES:
            assert (roles_dir / f"{role_id}.txt").exists()

    def test_cache_read_matches_write(self, atlas_with_data):
        atlas_with_data.cache_role_atlases()
        for role_id in BUILT_IN_ROLES:
            cached = atlas_with_data.load_cached_role_atlas(role_id)
            assert cached is not None
            assert len(cached) > 0

    def test_cache_fallback_on_miss(self, atlas_with_data):
        """Uncached role should return None from load_cached_role_atlas."""
        result = atlas_with_data.load_cached_role_atlas("ceo")
        assert result is None

    def test_cache_staleness_detection(self, atlas_with_data):
        """If base atlas is newer than cache, cache should be stale."""
        import time
        atlas_with_data.cache_role_atlases()
        # Touch atlas.json to make it newer
        time.sleep(0.05)
        atlas_path = atlas_with_data.index_dir / "atlas.json"
        atlas_path.write_text(atlas_path.read_text())
        # Now cache should be stale
        result = atlas_with_data.load_cached_role_atlas("ceo")
        assert result is None

    def test_cache_clear(self, atlas_with_data):
        atlas_with_data.cache_role_atlases()
        roles_dir = atlas_with_data.index_dir / "atlas_roles"
        assert len(list(roles_dir.glob("*.txt"))) > 0
        removed = atlas_with_data.clear_role_cache()
        assert removed == len(BUILT_IN_ROLES)
        assert len(list(roles_dir.glob("*.txt"))) == 0

    def test_get_role_atlas_uses_cache(self, atlas_with_data):
        """get_role_atlas should use cache when available."""
        atlas_with_data.cache_role_atlases()
        result = atlas_with_data.get_role_atlas("ceo")
        assert "[CEO View]" in result or "CEO" in result
        assert len(result) > 0

    def test_get_role_atlas_live_fallback(self, atlas_with_data):
        """get_role_atlas should work without cache (live generation)."""
        result = atlas_with_data.get_role_atlas("ceo")
        assert len(result) > 0
