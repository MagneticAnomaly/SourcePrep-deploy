from prep.core.vendor_sniffer.models import VendorCandidate, VendorScanResult


def test_vendor_candidate_required_fields():
    c = VendorCandidate(
        path="/abs/path/vcpkg",
        rel_path="vcpkg",
        size_bytes=2_700_000_000,
        file_count=8210,
        reason="Nested git repo, possibly vendored",
        tier="propose",
        in_gitignore=False,
        is_git_repo=True,
    )
    assert c.tier in ("auto", "propose")
    assert c.rel_path == "vcpkg"


def test_vendor_scan_result_default_status_complete():
    r = VendorScanResult(
        auto_excluded=["**/Pods/**", "**/build/**"],
        proposed=[],
        gitignore_gaps=[],
        scanned_at=1715500000.0,
        status="complete",
        error=None,
    )
    assert r.status == "complete"
    assert r.error is None


def test_vendor_scan_result_pending_state():
    r = VendorScanResult(
        auto_excluded=[],
        proposed=[],
        gitignore_gaps=[],
        scanned_at=0.0,
        status="pending",
        error=None,
    )
    assert r.status == "pending"


def test_vendor_scan_result_failed_state_carries_error():
    r = VendorScanResult(
        auto_excluded=[],
        proposed=[],
        gitignore_gaps=[],
        scanned_at=1715500000.0,
        status="failed",
        error="prep_engine.walk_repo: disk I/O error",
    )
    assert r.status == "failed"
    assert "disk I/O" in r.error
