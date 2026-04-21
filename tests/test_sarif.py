"""Tests for SARIF parser, converter, and auto-detection."""
from __future__ import annotations

import copy
from typing import Dict, List

import pytest

from prep.core.sarif import (
    SarifInput,
    SarifRun,
    enriched_to_sarif,
    is_sarif,
    parse_sarif,
    sarif_to_simple,
)
from prep.core.enrichment import EnrichedFinding, EnrichmentResult


SAMPLE_SARIF: Dict = {
    "version": "2.1.0",
    "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
    "runs": [
        {
            "tool": {
                "driver": {
                    "name": "ruff",
                    "rules": [
                        {
                            "id": "C901",
                            "shortDescription": {"text": "Too complex"},
                        }
                    ],
                }
            },
            "results": [
                {
                    "ruleId": "C901",
                    "level": "warning",
                    "message": {"text": "Function too complex (C901: 23)"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "src/server.py"},
                                "region": {"startLine": 42},
                            }
                        }
                    ],
                },
                {
                    "ruleId": "E501",
                    "level": "warning",
                    "message": {"text": "Line too long (120 > 100)"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "src/utils.py"},
                                "region": {"startLine": 15},
                            }
                        }
                    ],
                },
            ],
        }
    ],
}


MULTI_RUN_SARIF: Dict = {
    "version": "2.1.0",
    "runs": [
        {
            "tool": {"driver": {"name": "ruff", "rules": []}},
            "results": [
                {
                    "ruleId": "C901",
                    "level": "warning",
                    "message": {"text": "Too complex"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "src/server.py"},
                                "region": {"startLine": 10},
                            }
                        }
                    ],
                }
            ],
        },
        {
            "tool": {"driver": {"name": "semgrep", "rules": []}},
            "results": [
                {
                    "ruleId": "python.lang.security.audit.exec-detected",
                    "level": "error",
                    "message": {"text": "Detected exec usage"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "src/eval.py"},
                                "region": {"startLine": 5, "startColumn": 1},
                            }
                        }
                    ],
                },
                {
                    "ruleId": "python.lang.security.audit.dangerous-import",
                    "level": "warning",
                    "message": {"text": "Dangerous import detected"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "src/imports.py"},
                                "region": {"startLine": 1},
                            }
                        }
                    ],
                },
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# is_sarif tests
# ---------------------------------------------------------------------------


def test_is_sarif_detects_sarif_21():
    """Dict with version+runs is detected as SARIF."""
    assert is_sarif({"version": "2.1.0", "runs": []}) is True


def test_is_sarif_detects_sarif_schema():
    """Dict with $schema containing 'sarif' is detected as SARIF."""
    data = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
    }
    assert is_sarif(data) is True


def test_is_sarif_rejects_simple_list():
    """List of findings is not SARIF."""
    assert is_sarif([{"file": "a.py", "line": 1}]) is False


def test_is_sarif_rejects_non_dict():
    """String is not SARIF."""
    assert is_sarif("not sarif") is False


# ---------------------------------------------------------------------------
# parse_sarif tests
# ---------------------------------------------------------------------------


def test_parse_sarif_extracts_findings():
    """Parse minimal SARIF and verify file/line/message/severity/tool extracted."""
    sarif_input = parse_sarif(copy.deepcopy(SAMPLE_SARIF))

    assert sarif_input.version == "2.1.0"
    assert len(sarif_input.runs) == 1

    run = sarif_input.runs[0]
    assert run.tool_name == "ruff"
    assert len(run.results) == 2

    f0 = run.results[0]
    assert f0["file"] == "src/server.py"
    assert f0["line"] == 42
    assert f0["message"] == "Function too complex (C901: 23)"
    assert f0["severity"] == "warning"
    assert f0["tool"] == "ruff"

    f1 = run.results[1]
    assert f1["file"] == "src/utils.py"
    assert f1["line"] == 15


def test_parse_sarif_normalizes_file_paths():
    """file:///src/foo.py is normalized to src/foo.py."""
    data = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "test-tool"}},
                "results": [
                    {
                        "ruleId": "R1",
                        "level": "note",
                        "message": {"text": "some note"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {
                                        "uri": "file:///src/foo.py"
                                    },
                                    "region": {"startLine": 1},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
    result = parse_sarif(data)
    assert result.runs[0].results[0]["file"] == "src/foo.py"


def test_parse_sarif_handles_missing_location():
    """Results with no locations are skipped."""
    data = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "tool"}},
                "results": [
                    {
                        "ruleId": "R1",
                        "level": "warning",
                        "message": {"text": "no location"},
                    },
                    {
                        "ruleId": "R2",
                        "level": "warning",
                        "message": {"text": "has location"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "a.py"},
                                    "region": {"startLine": 5},
                                }
                            }
                        ],
                    },
                ],
            }
        ],
    }
    result = parse_sarif(data)
    assert len(result.runs[0].results) == 1
    assert result.runs[0].results[0]["file"] == "a.py"


def test_parse_sarif_multi_run():
    """SARIF with 2 runs from different tools extracts all findings with correct tool names."""
    result = parse_sarif(copy.deepcopy(MULTI_RUN_SARIF))

    assert len(result.runs) == 2
    assert result.runs[0].tool_name == "ruff"
    assert result.runs[1].tool_name == "semgrep"

    assert len(result.runs[0].results) == 1
    assert len(result.runs[1].results) == 2

    # Verify tool name propagated to each finding
    assert result.runs[0].results[0]["tool"] == "ruff"
    assert result.runs[1].results[0]["tool"] == "semgrep"
    assert result.runs[1].results[1]["tool"] == "semgrep"

    # Verify severity mapping: error level
    assert result.runs[1].results[0]["severity"] == "error"


def test_parse_sarif_v20():
    """SARIF version 2.0.0 is accepted."""
    data = {
        "version": "2.0.0",
        "runs": [
            {
                "tool": {"driver": {"name": "old-tool"}},
                "results": [
                    {
                        "ruleId": "X1",
                        "level": "error",
                        "message": {"text": "old finding"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "legacy.py"},
                                    "region": {"startLine": 99},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
    result = parse_sarif(data)
    assert result.version == "2.0.0"
    assert result.runs[0].results[0]["file"] == "legacy.py"


# ---------------------------------------------------------------------------
# sarif_to_simple tests
# ---------------------------------------------------------------------------


def test_sarif_to_simple():
    """SarifInput is flattened into a list of simple finding dicts."""
    sarif_input = parse_sarif(copy.deepcopy(MULTI_RUN_SARIF))
    simple = sarif_to_simple(sarif_input)

    assert isinstance(simple, list)
    assert len(simple) == 3  # 1 from ruff + 2 from semgrep

    # All have required keys
    for f in simple:
        assert "file" in f
        assert "line" in f
        assert "message" in f
        assert "severity" in f
        assert "tool" in f


# ---------------------------------------------------------------------------
# enriched_to_sarif tests
# ---------------------------------------------------------------------------


def _make_enrichment_result(sarif_input: SarifInput) -> EnrichmentResult:
    """Build an EnrichmentResult matching the sarif_input's findings."""
    simple = sarif_to_simple(sarif_input)
    enriched: List[EnrichedFinding] = []
    for f in simple:
        enriched.append(
            EnrichedFinding(
                file=f["file"],
                line=f["line"],
                message=f["message"],
                severity=f["severity"],
                tool=f["tool"],
                codrag={
                    "dependents": 12,
                    "hub_status": "high",
                    "module": "core",
                    "concepts": ["security"],
                    "observations": ["needs review"],
                    "risk_score": 0.75,
                    "recommendation": "Review carefully",
                },
            )
        )
    return EnrichmentResult(
        findings=enriched,
        summary={
            "total": len(enriched),
            "enriched": len(enriched),
            "unenriched": 0,
            "high_risk": len(enriched),
            "key_insight": "All findings are high risk.",
        },
        stale_data_warning=False,
    )


def test_enriched_to_sarif_injects_property_bags():
    """Enriched results get properties.codrag with dependents, hub_status, etc."""
    sarif_input = parse_sarif(copy.deepcopy(SAMPLE_SARIF))
    enrichment = _make_enrichment_result(sarif_input)
    output = enriched_to_sarif(sarif_input, enrichment)

    # Check that codrag properties are injected
    result0 = output["runs"][0]["results"][0]
    assert "properties" in result0
    assert "codrag" in result0["properties"]
    codrag = result0["properties"]["codrag"]
    assert codrag["dependents"] == 12
    assert codrag["hub_status"] == "high"
    assert codrag["risk_score"] == 0.75
    assert codrag["recommendation"] == "Review carefully"


def test_enriched_to_sarif_preserves_original_fields():
    """Original ruleId, message, locations are untouched."""
    sarif_input = parse_sarif(copy.deepcopy(SAMPLE_SARIF))
    enrichment = _make_enrichment_result(sarif_input)
    output = enriched_to_sarif(sarif_input, enrichment)

    result0 = output["runs"][0]["results"][0]
    assert result0["ruleId"] == "C901"
    assert result0["message"]["text"] == "Function too complex (C901: 23)"
    assert result0["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "src/server.py"
    assert result0["level"] == "warning"


def test_enriched_to_sarif_adds_run_summary():
    """runs[0].properties.codrag.summary is present."""
    sarif_input = parse_sarif(copy.deepcopy(SAMPLE_SARIF))
    enrichment = _make_enrichment_result(sarif_input)
    output = enriched_to_sarif(sarif_input, enrichment)

    run_props = output["runs"][0]["properties"]["codrag"]
    assert "summary" in run_props
    assert run_props["summary"]["total"] == 2
    assert run_props["summary"]["enriched"] == 2


# ---------------------------------------------------------------------------
# Size limit tests
# ---------------------------------------------------------------------------


def test_size_limit_rejects_large_input():
    """>1000 results raises ValueError."""
    data = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "bulk-tool"}},
                "results": [
                    {
                        "ruleId": f"R{i}",
                        "level": "warning",
                        "message": {"text": f"Finding {i}"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": f"file{i}.py"},
                                    "region": {"startLine": i},
                                }
                            }
                        ],
                    }
                    for i in range(1001)
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="1000"):
        parse_sarif(data)
