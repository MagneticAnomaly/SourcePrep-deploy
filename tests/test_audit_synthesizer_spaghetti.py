"""Tests for Phase 124 T5b — AuditSynthesizer consumes spaghetti findings.

Covers the formatter helper and the kwarg-threading contract. The
generators themselves go through an LLM and aren't unit-testable
without a mock; we instead verify that the prompt-formatting layer
emits stable structure when fed real ``SpaghettiResult`` shapes.
"""
from __future__ import annotations

import pytest

from prep.core.audit.synthesizer import AuditSynthesizer
from prep.core.audit.spaghetti_scorer import FileScore, SpaghettiResult


# ──────────────────────────────────────────────────────────────────────
# _format_spaghetti_top
# ──────────────────────────────────────────────────────────────────────

def _make(files):
    return SpaghettiResult(files=list(files))


def test_format_returns_sentinel_when_none():
    out = AuditSynthesizer._format_spaghetti_top(None)
    assert "no spaghetti data" in out
    assert "T5" in out  # cite Phase 124 T5 so debugging is easy


def test_format_distinguishes_no_files_from_no_result():
    out = AuditSynthesizer._format_spaghetti_top(_make([]))
    assert "0 files" in out


def test_format_filters_by_severity():
    sr = _make([
        FileScore(file_path="src/critical.py", score=0.9, severity="critical"),
        FileScore(file_path="src/warn.py",     score=0.6, severity="warning"),
        FileScore(file_path="src/info.py",     score=0.3, severity="info"),
    ])
    out = AuditSynthesizer._format_spaghetti_top(sr)
    assert "src/critical.py" in out
    assert "src/warn.py" in out
    assert "src/info.py" not in out


def test_format_sorts_by_score_descending():
    sr = _make([
        FileScore(file_path="src/lo.py", score=0.55, severity="warning"),
        FileScore(file_path="src/hi.py", score=0.95, severity="critical"),
        FileScore(file_path="src/mid.py", score=0.75, severity="warning"),
    ])
    out = AuditSynthesizer._format_spaghetti_top(sr)
    lines = [l for l in out.splitlines() if l.startswith("- ")]
    assert lines[0].startswith("- src/hi.py")
    assert lines[1].startswith("- src/mid.py")
    assert lines[2].startswith("- src/lo.py")


def test_format_caps_results():
    sr = _make([
        FileScore(file_path=f"src/f{i}.py", score=0.9 - i*0.01, severity="critical")
        for i in range(15)
    ])
    out = AuditSynthesizer._format_spaghetti_top(sr, max_files=5)
    bullet_lines = [l for l in out.splitlines() if l.startswith("- ")]
    assert len(bullet_lines) == 5
    assert "10 more" in out


def test_format_includes_signal_tags():
    sr = _make([
        FileScore(
            file_path="src/foo.py", score=0.92, severity="critical",
            estimated_lines=412, fan_in=18, tech_debt_count=4, in_circular=True,
        ),
    ])
    out = AuditSynthesizer._format_spaghetti_top(sr)
    assert "circular" in out
    assert "4 debt items" in out
    assert "412L" in out
    assert "fan_in=18" in out


def test_format_no_tags_when_signals_default():
    sr = _make([FileScore(file_path="src/bare.py", score=0.6, severity="warning")])
    out = AuditSynthesizer._format_spaghetti_top(sr)
    assert "src/bare.py" in out
    assert "[" not in out  # no tag bracket emitted


def test_format_empty_filter_message():
    """Files exist but none match the severity filter."""
    sr = _make([
        FileScore(file_path="src/a.py", score=0.3, severity="info"),
        FileScore(file_path="src/b.py", score=0.2, severity="info"),
    ])
    out = AuditSynthesizer._format_spaghetti_top(sr)
    assert "no critical/warning hotspots" in out


# ──────────────────────────────────────────────────────────────────────
# Kwarg threading — _run_generator forwards spaghetti correctly
# ──────────────────────────────────────────────────────────────────────

def test_run_generator_forwards_spaghetti_when_supported():
    """Generator with spaghetti kwarg should receive it."""
    received = {}

    def gen_fn(result, ctx, *, spaghetti=None):
        received["spaghetti"] = spaghetti
        return "stub content"

    synth = AuditSynthesizer(llm_client=None, project_name="test")
    sentinel = SpaghettiResult(files=[])
    # Minimal stand-ins for the AuditResult / AuditContext args
    class _R:
        finding_count = 0
    class _C:
        pass
    doc = synth._run_generator("X", "X", gen_fn, _R(), _C(), spaghetti=sentinel)
    assert received["spaghetti"] is sentinel
    assert doc.content == "stub content"


def test_run_generator_falls_back_for_legacy_generator():
    """Generator that doesn't accept the kwarg should still run."""
    called = {"with_kwarg": 0, "without_kwarg": 0}

    def gen_fn(result, ctx):  # no spaghetti kwarg
        called["without_kwarg"] += 1
        return "legacy content"

    synth = AuditSynthesizer(llm_client=None, project_name="test")
    class _R:
        finding_count = 0
    class _C:
        pass
    doc = synth._run_generator(
        "X", "X", gen_fn, _R(), _C(),
        spaghetti=SpaghettiResult(),
    )
    assert called["without_kwarg"] == 1
    assert doc.content == "legacy content"
