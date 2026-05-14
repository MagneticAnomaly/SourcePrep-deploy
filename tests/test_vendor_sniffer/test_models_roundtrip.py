import json
from dataclasses import asdict

from prep.core.vendor_sniffer.models import VendorCandidate, VendorScanResult


def _sample_candidate() -> VendorCandidate:
    return VendorCandidate(
        path="/abs/path/cesium-native",
        rel_path="cesium-native",
        size_bytes=1_700_000_000,
        file_count=12_304,
        reason="Large directory, no classification signal",
        tier="propose",
        in_gitignore=False,
        is_git_repo=True,
    )


def _sample_result() -> VendorScanResult:
    return VendorScanResult(
        auto_excluded=["**/Pods/**", "**/build/**"],
        proposed=[_sample_candidate()],
        gitignore_gaps=[],
        scanned_at=1715500000.0,
        status="complete",
        error=None,
    )


def test_candidate_to_dict_keys_match_dataclass_fields():
    c = _sample_candidate()
    d = c.to_dict()
    assert d == asdict(c)


def test_candidate_from_dict_reconstructs_dataclass():
    c = _sample_candidate()
    rebuilt = VendorCandidate.from_dict(c.to_dict())
    assert rebuilt == c


def test_result_to_dict_nests_candidates_as_dicts():
    r = _sample_result()
    d = r.to_dict()
    assert isinstance(d["proposed"], list)
    assert isinstance(d["proposed"][0], dict)
    assert d["proposed"][0]["rel_path"] == "cesium-native"


def test_result_from_dict_reconstructs_dataclass_recursively():
    r = _sample_result()
    rebuilt = VendorScanResult.from_dict(r.to_dict())
    assert rebuilt == r
    assert isinstance(rebuilt.proposed[0], VendorCandidate)


def test_result_survives_json_round_trip():
    """The whole point: a result stored as JSON in Project.config must come back equal."""
    r = _sample_result()
    serialized = json.dumps(r.to_dict())
    deserialized = json.loads(serialized)
    rebuilt = VendorScanResult.from_dict(deserialized)
    assert rebuilt == r


def test_pending_result_round_trips():
    r = VendorScanResult(
        auto_excluded=[],
        proposed=[],
        gitignore_gaps=[],
        scanned_at=0.0,
        status="pending",
        error=None,
    )
    rebuilt = VendorScanResult.from_dict(json.loads(json.dumps(r.to_dict())))
    assert rebuilt == r


def test_failed_result_preserves_error_field():
    r = VendorScanResult(
        auto_excluded=[],
        proposed=[],
        gitignore_gaps=[],
        scanned_at=1715500000.0,
        status="failed",
        error="prep_engine.walk_repo: disk I/O error",
    )
    rebuilt = VendorScanResult.from_dict(json.loads(json.dumps(r.to_dict())))
    assert rebuilt == r
    assert rebuilt.error == "prep_engine.walk_repo: disk I/O error"


def test_from_dict_missing_optional_error_field_defaults_to_none():
    """For forward compatibility: tolerate missing 'error' key in older payloads."""
    payload = {
        "auto_excluded": [],
        "proposed": [],
        "gitignore_gaps": [],
        "scanned_at": 0.0,
        "status": "pending",
    }
    rebuilt = VendorScanResult.from_dict(payload)
    assert rebuilt.error is None
