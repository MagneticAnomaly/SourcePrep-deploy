"""
Tests for FIX-16-4's `lint_module_summary` helper
(see docs/Phase82_MCP-Dogfooding/17_Followup_2026-05-08.md).

The helper is a pure function used to flag consulting-deck phrasing in
synthesized module summaries. Today it's advisory; a follow-up will wire it
into a re-prompt loop on detection. The unit tests cover the banned-phrase
catalog so additions/removals stay deliberate.
"""
from __future__ import annotations

import pytest

from prep.core.cluster import lint_module_summary


def test_clean_summary_passes():
    text = (
        "Renders the interactive architecture diagram with semantic zoom and "
        "annotation overlays. Built on React Flow."
    )
    assert lint_module_summary(text) == []


def test_empty_summary_passes():
    assert lint_module_summary("") == []
    assert lint_module_summary(None) == []  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "phrase, snippet",
    [
        ("central nervous system", "Serves as the central nervous system for compute."),
        ("bridges ", "Bridges enterprise policy enforcement with consumer privacy."),
        ("serves as the central", "Serves as the central coordinator for all jobs."),
        ("backbone for", "Acts as the backbone for the pipeline."),
        ("currently in active transition", "Currently in active transition with critical gaps."),
        ("currently in active development", "Currently in active development."),
        ("end-to-end", "Provides end-to-end project management."),
        ("while maintaining", "Routes traffic while maintaining session affinity."),
        ("robust ", "A robust solution for batched dispatch."),
        ("comprehensive ", "A comprehensive overview of the indexer."),
        ("seamless ", "Provides seamless integration with the dashboard."),
    ],
)
def test_individual_phrases_are_flagged(phrase: str, snippet: str):
    findings = lint_module_summary(snippet)
    assert phrase.strip() in findings


def test_multiple_findings_reported():
    text = (
        "Bridges X with Y while maintaining seamless integration. "
        "Currently in active transition."
    )
    findings = lint_module_summary(text)
    # At minimum these three should fire
    assert "bridges" in findings
    assert "while maintaining" in findings
    assert "currently in active transition" in findings


def test_case_insensitive():
    assert "central nervous system" in lint_module_summary(
        "BRIDGES the CENTRAL NERVOUS SYSTEM",
    )


def test_robust_only_matches_word_form_not_subwords():
    """`robust ` has a trailing space so it doesn't fire on 'robustness' or
    a hyphenated 'robust-mode'. Confirms the trailing-space convention."""
    # 'robustness' should NOT match because the banned phrase ends in space
    assert "robust" not in lint_module_summary("robustness as a property")
    # 'robust ' as a real adjective should match
    assert "robust" in lint_module_summary("a robust pipeline of tasks")
