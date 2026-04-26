"""Schema + integrity tests for the per-provider plan-tier limits.

Each tier entry must declare:
  - tier_label: human-readable name (e.g. "Max")
  - concurrent: integer, the documented concurrent-request limit
  - source_url: where this number came from (so future maintainers can verify)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

LIMITS_PATH = Path(__file__).parent.parent / "src/prep/data/concurrency_limits.json"


def _load() -> dict:
    return json.loads(LIMITS_PATH.read_text())


def test_file_exists() -> None:
    assert LIMITS_PATH.exists(), f"Expected limits file at {LIMITS_PATH}"


def test_required_providers_present() -> None:
    """All providers we research in 05_Cross_Provider_Concurrency_Design.md
    have entries (even if Auto-detect-only)."""
    data = _load()
    expected = {"ollama_cloud", "openai", "anthropic", "google_gemini", "moonshot_kimi", "ollama_local"}
    assert set(data["providers"].keys()) >= expected


def test_ollama_cloud_published_numbers() -> None:
    """Verify the Ollama Cloud numbers match the pricing page (Free/Pro/Max = 1/3/10)."""
    data = _load()
    tiers = {t["tier_key"]: t for t in data["providers"]["ollama_cloud"]["tiers"]}
    assert tiers["free"]["concurrent"] == 1
    assert tiers["pro"]["concurrent"] == 3
    assert tiers["max"]["concurrent"] == 10


def test_every_tier_has_required_fields() -> None:
    """Schema integrity: each tier entry has tier_key/tier_label/concurrent/source_url."""
    data = _load()
    required = {"tier_key", "tier_label", "concurrent", "source_url"}
    for provider_key, provider in data["providers"].items():
        for tier in provider["tiers"]:
            missing = required - tier.keys()
            assert not missing, f"{provider_key} tier {tier} missing keys: {missing}"


def test_provider_records_auto_detect_capability() -> None:
    """Each provider declares whether 'Auto' (header-driven) is offered.
    UI uses this to decide whether to allow save without picking."""
    data = _load()
    for provider_key, provider in data["providers"].items():
        assert "auto_detect" in provider, f"{provider_key} missing auto_detect"
        assert isinstance(provider["auto_detect"], bool)


def test_auto_detect_only_for_header_rich_providers() -> None:
    """OpenAI, Anthropic have headers -> auto_detect=True. Ollama Cloud and
    Gemini do not -> auto_detect=False. (Per 05_design.md table.)"""
    data = _load()
    assert data["providers"]["openai"]["auto_detect"] is True
    assert data["providers"]["anthropic"]["auto_detect"] is True
    assert data["providers"]["ollama_cloud"]["auto_detect"] is False
    assert data["providers"]["google_gemini"]["auto_detect"] is False


def test_concurrent_values_are_positive_ints() -> None:
    """No zero or negative; the special 'Auto' case is at provider level, not tier level."""
    data = _load()
    for provider_key, provider in data["providers"].items():
        for tier in provider["tiers"]:
            assert isinstance(tier["concurrent"], int)
            assert tier["concurrent"] >= 1, f"{provider_key}/{tier['tier_key']}: bad concurrent={tier['concurrent']}"


def test_no_unexpected_tier_keys() -> None:
    """Strict schema: catch typo'd field names like 'concurency' (missing 'r')
    or 'tier_label_v2' (drift) that the missing-keys test would silently pass."""
    data = _load()
    allowed = {"tier_key", "tier_label", "concurrent", "source_url"}
    for provider_key, provider in data["providers"].items():
        for tier in provider["tiers"]:
            extra = tier.keys() - allowed
            assert not extra, f"{provider_key}/{tier.get('tier_key')}: unexpected keys {extra}"


def test_provider_auto_detect_reason_present_and_nonempty() -> None:
    """The reason string is maintainer-facing documentation — defend it
    against accidental drop during a copy/paste edit."""
    data = _load()
    for provider_key, provider in data["providers"].items():
        reason = provider.get("auto_detect_reason", "")
        assert isinstance(reason, str) and reason.strip(), (
            f"{provider_key} missing auto_detect_reason"
        )


def test_source_urls_are_http_urls() -> None:
    """Catch placeholder strings like 'TODO' or accidental file paths."""
    data = _load()
    for provider_key, provider in data["providers"].items():
        for tier in provider["tiers"]:
            url = tier.get("source_url", "")
            assert isinstance(url, str) and url.startswith(("http://", "https://")), (
                f"{provider_key}/{tier.get('tier_key')}: bad source_url {url!r}"
            )


def test_tier_keys_and_labels_are_strings() -> None:
    """Defend the Python ↔ TypeScript contract. A bare number tier_key (e.g.
    forgot quotes around 1) would pass JSON parse but break the TS interface."""
    data = _load()
    for provider_key, provider in data["providers"].items():
        for tier in provider["tiers"]:
            assert isinstance(tier["tier_key"], str), (
                f"{provider_key}/{tier['tier_key']}: tier_key must be string"
            )
            assert isinstance(tier["tier_label"], str), (
                f"{provider_key}/{tier['tier_key']}: tier_label must be string"
            )
