import pytest
from codrag.core.enrichment import enrich_findings, EnrichedFinding, EnrichmentResult


def _make_finding(file="src/server.py", line=42, message="Too complex", severity="warning", tool="ruff"):
    return {"file": file, "line": line, "message": message, "severity": severity, "tool": tool}


def _make_context():
    return {
        "src/server.py": {
            "dependents": 23,
            "hub_status": "critical",
            "module": "mcp",
            "concepts": ["Planned refactor: split handler dispatch"],
            "observations": ["2026-03-15: Growing concern"],
        },
        "src/leaf.py": {
            "dependents": 1,
            "hub_status": "low",
            "module": "helpers",
            "concepts": [],
            "observations": [],
        },
    }


def test_enrich_known_file():
    findings = [_make_finding()]
    ctx = _make_context()
    result = enrich_findings(findings, ctx)
    assert len(result.findings) == 1
    f = result.findings[0]
    assert f.codrag is not None
    assert f.codrag["dependents"] == 23
    assert f.codrag["hub_status"] == "critical"
    assert len(f.codrag["concepts"]) == 1


def test_enrich_unknown_file_shows_stale_message():
    findings = [_make_finding(file="src/unknown.py")]
    ctx = _make_context()
    result = enrich_findings(findings, ctx)
    assert result.stale_data_warning is True


def test_enrich_includes_risk_score():
    findings = [_make_finding()]
    ctx = _make_context()
    result = enrich_findings(findings, ctx)
    assert 0.0 <= result.findings[0].codrag["risk_score"] <= 1.0


def test_enrich_summary():
    findings = [_make_finding(), _make_finding(file="src/leaf.py")]
    ctx = _make_context()
    result = enrich_findings(findings, ctx)
    assert result.summary["total"] == 2
    assert result.summary["enriched"] == 2
    assert result.summary["high_risk"] >= 1


def test_enrich_respects_max_findings():
    findings = [_make_finding(file=f"src/file{i}.py") for i in range(300)]
    ctx = _make_context()
    result = enrich_findings(findings, ctx, max_findings=200)
    assert len(result.findings) <= 200


def test_enrich_to_dict_includes_stale_message():
    findings = [_make_finding(file="src/unknown.py")]
    ctx = _make_context()
    result = enrich_findings(findings, ctx)
    d = result.to_dict()
    assert "message" in d
    assert "stale data" in d["message"]


def test_enrich_to_dict_no_message_when_fresh():
    findings = [_make_finding()]
    ctx = _make_context()
    result = enrich_findings(findings, ctx)
    d = result.to_dict()
    assert "message" not in d


def test_enrich_summary_has_key_insight():
    findings = [_make_finding()]
    ctx = _make_context()
    result = enrich_findings(findings, ctx)
    assert "key_insight" in result.summary
    assert "server.py" in result.summary["key_insight"]
