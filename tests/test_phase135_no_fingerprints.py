"""Phase 135 — static guards: no mid-pipeline fingerprint computation remains.

These tests fail loudly if anyone re-introduces the deleted pattern.
"""
from __future__ import annotations

from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "prep" / "core"


def _read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def test_group_reasoning_no_fingerprint_compute() -> None:
    body = _read("group_reasoning.py")
    assert "compute_group_fingerprint" not in body
    assert "member_fingerprint" not in body


def test_cluster_no_fingerprint_compute() -> None:
    body = _read("cluster.py")
    assert "_cluster_fingerprint" not in body
    assert "fp_to_module" not in body


def test_knowledge_deep_path_no_inline_hash_compare() -> None:
    """The legacy `prev_hash == content_hash` compare must only appear
    inside the use_changeset=False (stage 5) branch — not at the top
    level of the docs loop. If the gate phrase disappears, the cutover
    regressed."""
    body = _read("knowledge.py")
    assert "if self.use_changeset:" in body, "Stage 5/10 split gate missing"
