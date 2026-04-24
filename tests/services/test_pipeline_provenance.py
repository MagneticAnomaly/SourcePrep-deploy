"""Phase 117: per-stage provenance helper."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def idx_dir(tmp_path, monkeypatch):
    """Patch the helper so idx_dir resolution points at tmp_path."""
    from prep.services import pipeline_provenance

    monkeypatch.setattr(pipeline_provenance, "_resolve_idx_dir", lambda _pid: tmp_path)
    return tmp_path


def _write_manifest(idx_dir: Path, filename: str, content: dict) -> None:
    (idx_dir / filename).write_text(json.dumps(content))


def test_match_when_manifest_equals_current(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance

    _write_manifest(
        idx_dir,
        "trace_epistemic_manifest.json",
        {"model": {"provider": "ollama", "model_name": "kimi-k2.5:cloud"}},
    )
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: ("ollama", "kimi-k2.5:cloud"),
    )

    out = pipeline_provenance.compute_stage_provenance("p1", "enrichment")
    assert out["state"] == "match"
    assert out["chip_text"] is None
    assert out["rebuild_scope"] is None


def test_drift_when_manifest_differs_from_current(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance
    _write_manifest(
        idx_dir,
        "trace_epistemic_manifest.json",
        {"model": {"provider": "ollama", "model_name": "kimi-k2.5:cloud"}},
    )
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: ("ollama", "qwen3:14b"),
    )

    out = pipeline_provenance.compute_stage_provenance("p1", "enrichment")
    assert out["state"] == "drift"
    assert "kimi-k2.5:cloud" in out["chip_text"]
    assert "qwen3:14b" in out["chip_text"]
    assert out["rebuild_scope"] == "enrichment"


def test_stub_when_manifest_is_restored_selfheal(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance
    _write_manifest(
        idx_dir,
        "trace_augment_manifest.json",
        {"restored": True, "source": "selfheal"},
    )
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: ("ollama", "kimi-k2.5:cloud"),
    )
    # No golden evidence
    out = pipeline_provenance.compute_stage_provenance("p1", "augmentation")
    assert out["state"] == "recovered_stub"
    assert "provenance unknown" in out["chip_text"]
    assert out["rebuild_scope"] == "sync"


def test_stub_softened_when_golden_matches(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance
    _write_manifest(
        idx_dir,
        "trace_augment_manifest.json",
        {"restored": True, "source": "selfheal"},
    )
    # Golden _meta.json with an embedded model record
    (idx_dir / ".checkpoints").mkdir()
    (idx_dir / ".checkpoints" / "_golden").mkdir()
    (idx_dir / ".checkpoints" / "_golden" / "_meta.json").write_text(
        json.dumps({"stage_models": {"augmentation": {"provider": "ollama", "model_name": "kimi-k2.5:cloud"}}})
    )
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: ("ollama", "kimi-k2.5:cloud"),
    )

    out = pipeline_provenance.compute_stage_provenance("p1", "augmentation")
    assert out["state"] == "recovered_soft"
    assert "likely current" in out["chip_text"]


def test_missing_when_no_manifest_and_no_data(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: ("ollama", "kimi-k2.5:cloud"),
    )
    out = pipeline_provenance.compute_stage_provenance("p1", "enrichment")
    assert out["state"] == "missing"


def test_non_llm_stage_has_no_chip(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance
    _write_manifest(idx_dir, "validation_manifest.json", {"format_version": "2.0"})
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: None,  # non-LLM stage
    )
    out = pipeline_provenance.compute_stage_provenance("p1", "validation")
    assert out["state"] in ("match", "recovered_soft", "recovered_stub", "missing")
    # For non-LLM stages, match-equivalent state renders no chip
    assert out["chip_text"] is None or out["chip_text"] == ""


def test_provider_case_insensitive_match(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance
    _write_manifest(
        idx_dir,
        "trace_epistemic_manifest.json",
        {"model": {"provider": "Ollama", "model_name": "kimi-k2.5:cloud"}},
    )
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: ("ollama", "kimi-k2.5:cloud"),
    )
    out = pipeline_provenance.compute_stage_provenance("p1", "enrichment")
    assert out["state"] == "match"
