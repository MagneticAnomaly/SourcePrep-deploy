"""
Tests for atlas LLM-output validators.

See docs/Phase124_FinalizeChainEpistemicAudit/MCP_DOGFOOD_FEEDBACK_2026-05-05_SCRUTINY.md
item #4 for the bug that motivated these.
"""
from __future__ import annotations

import pytest

from prep.core.atlas.validators import (
    detect_missing_sections,
    detect_prompt_leak,
    detect_repeat_attack,
    validate_atlas_content,
)


# ── detect_repeat_attack ─────────────────────────────────────────────


def test_repeat_attack_catches_single_char_loop():
    # Observed in the wild: "maximally dense,ooooooooo short" — sampler stuck on 'o'
    text = "IDENTITY: foo. STACK: bar. " + "o" * 60 + " short."
    reason = detect_repeat_attack(text)
    assert reason is not None
    assert "'o'" in reason


def test_repeat_attack_catches_2char_ngram_loop():
    # The actual bug — 加油 repeated 200+ times. The detector may align on
    # either '加油' or '油加' depending on where it starts scanning; we just
    # care that *some* 2-char loop is reported.
    text = "IDENTITY: foo. " + "加油" * 50
    reason = detect_repeat_attack(text)
    assert reason is not None
    assert "2-char ngram" in reason


def test_repeat_attack_catches_3char_ngram_loop():
    text = "IDENTITY: foo. " + "abc" * 20
    reason = detect_repeat_attack(text)
    assert reason is not None


def test_repeat_attack_allows_natural_prose():
    text = (
        "IDENTITY: This is a local-first AI codebase intelligence platform "
        "with a FastAPI backend. STACK: Python, Rust, TypeScript. "
        "ARCHITECTURE: Three-language monorepo. The engine parses files via "
        "tree-sitter and stores results in SQLite."
    )
    assert detect_repeat_attack(text) is None


def test_repeat_attack_allows_whitespace_runs():
    # Long whitespace shouldn't trigger (e.g. a generated table)
    text = "IDENTITY: foo." + " " * 100 + "STACK: bar."
    assert detect_repeat_attack(text) is None


def test_repeat_attack_allows_short_repeats():
    # "===" or "---" dividers below threshold
    text = "IDENTITY: foo\n" + "=" * 20 + "\nSTACK: bar"
    assert detect_repeat_attack(text) is None


def test_repeat_attack_handles_empty():
    assert detect_repeat_attack("") is None


# ── detect_prompt_leak ───────────────────────────────────────────────


def test_prompt_leak_catches_actual_observed_opening():
    # Verbatim from the cached bad atlas.json on this repo (2026-05-06)
    text = (
        "I need to write a concise project orientation header based on the "
        "provided data, following strict rules: plain text only..."
    )
    reason = detect_prompt_leak(text)
    assert reason is not None
    assert "prompt-leak" in reason


def test_prompt_leak_catches_let_me_parse():
    text = "Let me parse the provided data carefully:\n\nProject Root..."
    assert detect_prompt_leak(text) is not None


def test_prompt_leak_catches_first_person_planning():
    cases = [
        "I'll write a header that...",
        "I will write the orientation...",
        "Let me start by analyzing the modules.",
        "Okay, let me think about this.",
        "Sure, here is the orientation:",
        "Here's the project header.",
    ]
    for text in cases:
        assert detect_prompt_leak(text) is not None, f"failed to catch: {text!r}"


def test_prompt_leak_passes_valid_identity_opener():
    text = "IDENTITY: A local-first codebase intelligence platform.\nSTACK: Python."
    assert detect_prompt_leak(text) is None


def test_prompt_leak_passes_valid_segment_opener():
    text = "SEGMENT: ui (packages/ui, 357 files)\nROLE: React component library."
    assert detect_prompt_leak(text) is None


def test_prompt_leak_handles_leading_whitespace():
    text = "\n\n  I need to write the header...\n"
    assert detect_prompt_leak(text) is not None


def test_prompt_leak_handles_empty():
    assert detect_prompt_leak("") is None


# ── detect_missing_sections ──────────────────────────────────────────


def test_missing_sections_rejects_pure_prose():
    text = (
        "This is a Python project that does codebase analysis. "
        "It has many subsystems and a daemon."
    )
    assert detect_missing_sections(text) is not None


def test_missing_sections_passes_with_identity():
    text = "IDENTITY: A codebase platform. The rest is free prose without other markers."
    assert detect_missing_sections(text) is None


def test_missing_sections_passes_with_segment_marker():
    text = "SEGMENT: ui (packages/ui, 357 files)"
    assert detect_missing_sections(text) is None


def test_missing_sections_passes_with_modules_keyword():
    text = "MODULES (10 subsystems, 500 files):\n• core: backend engine"
    assert detect_missing_sections(text) is None


# ── validate_atlas_content (composite) ───────────────────────────────


def test_validate_rejects_actual_cached_bad_content():
    """Reproduces the exact failure mode observed in atlas.json on 2026-05-06.

    The cached content this repo was serving combines BOTH a prompt-leak
    opening and a long Chinese-character n-gram loop. The validator should
    flag it on the first failing check (prompt-leak runs first).
    """
    bad = (
        "I need to write a concise project orientation header based on the "
        "provided data, following strict rules: plain text only, no markdown, "
        "no bold, no headers, no bullet characters, no asterisks. every claim "
        "from provided data, exact names, maximally dense,ooooooooo short, "
        "under 2570 characters, no invented info.\n\n"
        "Let me parse the provided data carefully:\n\n"
        "Project Root (1228 files): marketing, mcp, local-first\n"
        + "加油" * 200
    )
    reason = validate_atlas_content(bad)
    assert reason is not None
    # First-running detector should win — it's the prompt leak.
    assert "prompt-leak" in reason


def test_validate_passes_realistic_good_atlas():
    good = (
        "IDENTITY: SourcePrep is a local-first codebase intelligence platform "
        "that prep's context before AI calls.\n"
        "STACK: Python (FastAPI, Pydantic), Rust (tree-sitter), TypeScript (React, Next.js).\n"
        "ARCHITECTURE: Three-language monorepo. The Python daemon at "
        "src/prep/server.py exposes /search and /context. The Rust engine "
        "at engine/crates/prep-engine builds the trace graph.\n"
        "FLOW: Indexer -> embedder -> augmenter -> atlas generator.\n"
        "CROSS-CUTTING: Atomic I/O, immune watcher, MCP protocol bridge."
    )
    assert validate_atlas_content(good) is None


def test_validate_passes_valid_segment_doc():
    seg = (
        "SEGMENT: dashboard (src/prep/dashboard, 63 files)\n"
        "ROLE: React/Vite dashboard wired to the Prep daemon.\n"
        "KEY FILES:\n"
        "  App.tsx: top-level layout\n"
        "  hooks/useProjects.ts: project state\n"
        "DEPENDENCIES: depends on prep-daemon-api segment via HTTP.\n"
        "STATUS: active development."
    )
    assert validate_atlas_content(seg) is None


def test_validate_handles_empty_string():
    assert validate_atlas_content("") is None  # length gate handles empties separately
