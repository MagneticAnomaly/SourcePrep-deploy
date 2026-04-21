"""Tests for the structural-only audit scanner."""
import pytest
from prep.core.audit.structural import run_structural_audit, StructuralFinding


def _make_mock_context():
    return {
        "hub_files": [
            ("src/server.py", 40),    # clear outlier — z-score >> 2.0
            ("src/utils.py", 5),
            ("src/middleware.py", 4),
            ("src/config.py", 4),
            ("src/helpers.py", 3),
            ("src/models.py", 3),
            ("src/schemas.py", 2),
            ("src/leaf.py", 1),
        ],
        "cycles": [["src/a.py", "src/b.py", "src/c.py"]],
        "modules": [
            {"name": "core", "member_files": ["src/server.py", "src/utils.py"]},
            {"name": "helpers", "member_files": ["src/leaf.py"]},
        ],
        "concepts": [],
        "observations": [],
        "total_files": 50,
    }


def test_structural_returns_findings():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx)
    assert isinstance(findings, list)
    assert len(findings) > 0
    assert all(isinstance(f, StructuralFinding) for f in findings)


def test_structural_detects_hub_hotspots():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx)
    hub_findings = [f for f in findings if f.finding_type == "coupling_hotspot"]
    assert len(hub_findings) >= 1
    assert "server.py" in hub_findings[0].file_path


def test_structural_detects_cycles():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx)
    cycle_findings = [f for f in findings if f.finding_type == "import_cycle"]
    assert len(cycle_findings) >= 1


def test_structural_no_duplicates():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx)
    seen = set()
    for f in findings:
        key = (f.finding_type, f.file_path)
        assert key not in seen, f"Duplicate finding: {key}"
        seen.add(key)


def test_structural_excludes_generated_files():
    ctx = _make_mock_context()
    ctx["hub_files"].append(("package-lock.json", 30))
    findings = run_structural_audit(ctx)
    paths = [f.file_path for f in findings]
    assert "package-lock.json" not in paths


def test_structural_under_20_findings():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx)
    assert len(findings) <= 20


def test_structural_sorted_by_risk_score():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx)
    scores = [f.risk_score for f in findings]
    assert scores == sorted(scores, reverse=True)


def test_structural_finding_fields():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx)
    for f in findings:
        assert f.finding_type in ("coupling_hotspot", "import_cycle")
        assert f.severity in ("critical", "high", "moderate", "low", "info")
        assert isinstance(f.title, str) and f.title
        assert isinstance(f.description, str) and f.description
        assert 0.0 <= f.risk_score <= 1.0
        assert isinstance(f.recommendation, str)
        assert isinstance(f.evidence, dict)
        assert isinstance(f.related_concepts, list)
        assert isinstance(f.related_observations, list)


def test_structural_max_findings_param():
    ctx = _make_mock_context()
    # Add lots of cycles to generate more findings
    for i in range(30):
        ctx["cycles"].append([f"src/mod{i}.py", f"src/mod{i+1}.py"])
    findings = run_structural_audit(ctx, max_findings=5)
    assert len(findings) <= 5


def test_structural_scope_filters_to_prefix():
    ctx = _make_mock_context()
    ctx["hub_files"].append(("lib/external.py", 40))
    ctx["cycles"].append(["lib/x.py", "lib/y.py"])
    findings = run_structural_audit(ctx, scope="src/")
    paths = [f.file_path for f in findings]
    for p in paths:
        assert p.startswith("src/"), f"Finding {p} should be under src/"


def test_structural_category_coupling_only():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx, category="coupling")
    for f in findings:
        assert f.finding_type == "coupling_hotspot"


def test_structural_category_cycles_only():
    ctx = _make_mock_context()
    findings = run_structural_audit(ctx, category="cycles")
    for f in findings:
        assert f.finding_type == "import_cycle"


def test_structural_detects_concept_conflicts():
    ctx = _make_mock_context()
    ctx["concepts"] = [
        {"id": "c1", "title": "Use dispatch pattern", "anchors": ["src/server.py"],
         "category": "architecture", "status": "active", "created_at": 1000},
        {"id": "c2", "title": "Use inline handlers", "anchors": ["src/server.py"],
         "category": "architecture", "status": "active", "created_at": 2000},
    ]
    findings = run_structural_audit(ctx)
    conflict_findings = [f for f in findings if f.finding_type == "concept_conflict"]
    assert len(conflict_findings) == 1
    assert "dispatch" in conflict_findings[0].title.lower() or "inline" in conflict_findings[0].title.lower()


def test_structural_category_concept_violation():
    ctx = _make_mock_context()
    ctx["concepts"] = [
        {"id": "c1", "title": "A", "anchors": ["src/server.py"],
         "category": "constraint", "status": "active", "created_at": 1000},
        {"id": "c2", "title": "B", "anchors": ["src/server.py"],
         "category": "constraint", "status": "active", "created_at": 2000},
    ]
    findings = run_structural_audit(ctx, category="concept_violation")
    for f in findings:
        assert f.finding_type == "concept_conflict"
