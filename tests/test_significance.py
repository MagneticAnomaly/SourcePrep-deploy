"""Tests for significance classification helpers."""
import pytest

from codrag.adapters.pm_models import classify_significance


def test_security_finding_is_mandatory():
    assert classify_significance(
        category="security", consensus_score=0.0, hub_count=0,
    ) == "mandatory"


def test_high_consensus_is_mandatory():
    assert classify_significance(
        category="quality", consensus_score=0.6, hub_count=0,
    ) == "mandatory"


def test_hub_finding_is_recommended():
    assert classify_significance(
        category="quality", consensus_score=0.0, hub_count=1,
    ) == "recommended"


def test_standard_finding_is_recommended():
    assert classify_significance(
        category="quality", consensus_score=0.0, hub_count=0,
    ) == "recommended"


def test_low_confidence_is_informational():
    assert classify_significance(
        category="quality", consensus_score=0.0, hub_count=0,
        confidence="low",
    ) == "informational"


def test_low_confidence_with_hub_is_recommended():
    """Hub involvement overrides low confidence — hub findings are always at least recommended."""
    assert classify_significance(
        category="quality", consensus_score=0.0, hub_count=1,
        confidence="low",
    ) == "recommended"
