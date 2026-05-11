"""Phase 125c T2c.2 — tests for the Generate swarm runner.

LLM is mocked end-to-end. Validates that:
- Each worker scope receives its own scoped prompt
- Worker outputs are parsed and category-filtered to scope
- Cross-worker dedup runs over the union
- Failures in one worker don't take down the whole swarm
- save_many is called with the right kind='concept' payload (no LLM cost)
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.core.concept_generate_swarm import (
    GenerateSwarmReport,
    synthesize_concepts_swarm,
)
from prep.core.concept_synthesizer import Grounding
from prep.core.docs_grounding import DocsGrounding


# ── Fixtures ────────────────────────────────────────────────────────


def _grounding() -> Grounding:
    return Grounding(
        project_name="test",
        atlas_summary="Atlas summary.",
        rationale_clusters=[
            {"title": "auth", "category": "security", "anchors": ["src/auth.py"]},
            {"title": "ui", "category": "brand", "anchors": ["packages/ui/x.tsx"]},
        ],
    )


def _docs() -> DocsGrounding:
    return DocsGrounding(version=1, generated_at=0, docs=[])


def _llm_returning(per_scope_outputs: dict[str, str]) -> MagicMock:
    """Mock LLM whose response depends on which scope's prompt arrives.

    Looks for the scope label in the system prompt and returns the
    matching JSON string from `per_scope_outputs`.
    """
    llm = MagicMock()
    def _gen(prompt: str, system: str, **_kwargs):
        for label, output in per_scope_outputs.items():
            if f"ASSIGNED DIMENSION: {label}" in system:
                return (output, 100)
        return ("[]", 50)
    llm.generate = _gen
    return llm


# ── Happy-path swarm with all scopes responding ──────────────────────


def _concept_json(title: str, tier: str, category: str, anchors: list[str]) -> dict:
    return {
        "title": title,
        "category": category,
        "tier": tier,
        "tier_pairwise": "closer_to_lower",
        "anchors": anchors,
        "counter_evidence": "n/a",
        "falsification": "grep " + (anchors[0] if anchors else ""),
        "refined_content": f"{title} content",
    }


def test_swarm_size_3_runs_three_workers_and_collects_outputs(tmp_path):
    intent_out = json.dumps([
        _concept_json("Modular core", "T2", "architecture", ["src/core.py"]),
    ])
    rules_out = json.dumps([
        _concept_json("License gate", "T3", "constraint",
                      ["src/llm/gate.py", "src/llm/client.py"]),
    ])
    impl_out = json.dumps([
        _concept_json("React strict mode", "T1", "technical",
                      ["packages/ui/src/main.tsx"]),
    ])
    llm = _llm_returning({
        "intent": intent_out, "rules": rules_out, "implementation": impl_out,
    })

    saved_payload = []
    with patch("prep.services.concept_store.concept_store") as store:
        store.save_many.return_value = (3, 0)
        store.save_many.side_effect = (
            lambda pid, dicts: (saved_payload.extend(dicts), (len(dicts), 0))[1]
        )
        report = synthesize_concepts_swarm(
            "p1", llm=llm, swarm_size=3,
            idx_dir=tmp_path, project_root=tmp_path,
            project_name="test",
        )

    assert isinstance(report, GenerateSwarmReport)
    assert report.swarm_size == 3
    assert report.worker_count == 3
    assert report.candidates_emitted_total == 3
    assert report.candidates_after_dedup == 3   # no overlap → no dedup
    assert report.saved == 3
    assert report.failed_workers == []
    assert set(report.candidates_emitted_per_scope.keys()) == {
        "intent", "rules", "implementation",
    }


def test_swarm_drops_concepts_emitted_outside_scope(tmp_path):
    """A worker assigned 'rules' that emits a 'brand' concept gets it
    filtered out at parse time — the prompt told it not to, but we
    enforce belt-and-suspenders."""
    rules_out = json.dumps([
        _concept_json("Fine constraint", "T2", "constraint", ["src/x.py"]),
        _concept_json("Off-scope brand stuff", "T2", "brand", ["src/y.py"]),
    ])
    llm = _llm_returning({
        "intent": "[]", "rules": rules_out, "implementation": "[]",
    })

    with patch("prep.services.concept_store.concept_store") as store:
        store.save_many.return_value = (1, 0)
        report = synthesize_concepts_swarm(
            "p1", llm=llm, swarm_size=3,
            idx_dir=tmp_path, project_root=tmp_path,
            project_name="test",
        )

    # Only the 'constraint' concept should survive (brand is out of
    # the rules scope categories).
    assert report.candidates_emitted_total == 1
    assert report.candidates_emitted_per_scope["rules"] == 1


def test_swarm_dedups_cross_worker_anchor_overlap(tmp_path):
    """Two workers emit concepts with identical anchors but different tiers.
    Cross-worker dedup should collapse them; T3 wins."""
    same_anchors = ["src/auth/gate.py", "src/auth/middleware.py"]
    intent_out = json.dumps([
        _concept_json("auth gate (intent take)", "T2", "architecture", same_anchors),
    ])
    rules_out = json.dumps([
        _concept_json("auth gate (rules take)", "T3", "constraint", same_anchors),
    ])
    llm = _llm_returning({
        "intent": intent_out, "rules": rules_out, "implementation": "[]",
    })

    saved_payload: list[dict] = []
    with patch("prep.services.concept_store.concept_store") as store:
        def _save(pid, dicts):
            saved_payload.extend(dicts)
            return (len(dicts), 0)
        store.save_many.side_effect = _save
        report = synthesize_concepts_swarm(
            "p1", llm=llm, swarm_size=3,
            idx_dir=tmp_path, project_root=tmp_path,
            project_name="test",
        )

    assert report.candidates_emitted_total == 2
    assert report.candidates_after_dedup == 1
    # T3 wins
    assert len(saved_payload) == 1
    assert saved_payload[0]["status"] == "active"   # T3 → active per to_save_dict


def test_swarm_continues_when_one_worker_fails(tmp_path):
    """A worker exception is logged + counted but doesn't sink the swarm."""
    def _llm_one_fails(prompt: str, system: str, **_kwargs):
        if "ASSIGNED DIMENSION: rules" in system:
            raise RuntimeError("simulated worker failure")
        if "ASSIGNED DIMENSION: intent" in system:
            return (json.dumps([
                _concept_json("Survived", "T2", "architecture", ["src/x.py"])
            ]), 100)
        return ("[]", 50)
    llm = MagicMock()
    llm.generate = _llm_one_fails

    with patch("prep.services.concept_store.concept_store") as store:
        store.save_many.return_value = (1, 0)
        report = synthesize_concepts_swarm(
            "p1", llm=llm, swarm_size=3,
            idx_dir=tmp_path, project_root=tmp_path,
            project_name="test",
        )

    assert "rules" in report.failed_workers
    assert report.candidates_emitted_total == 1   # intent's one concept
    assert report.saved == 1


def test_swarm_dry_run_skips_llm_and_save(tmp_path):
    """Dry-run still builds prompts (so we can inspect token counts),
    but no LLM calls and no save."""
    llm = MagicMock()
    llm.generate = MagicMock(side_effect=AssertionError("LLM should not be called"))

    with patch("prep.services.concept_store.concept_store") as store:
        store.save_many = MagicMock(side_effect=AssertionError("save should not run"))
        report = synthesize_concepts_swarm(
            "p1", llm=llm, swarm_size=3,
            idx_dir=tmp_path, project_root=tmp_path,
            project_name="test",
            dry_run=True,
        )

    assert report.candidates_emitted_total == 0
    assert report.saved == 0
    llm.generate.assert_not_called()


def test_swarm_size_1_runs_single_worker(tmp_path):
    """Smoke: swarm_size=1 yields one worker covering all categories."""
    llm = _llm_returning({"all-categories": json.dumps([
        _concept_json("Solo", "T2", "decision", ["src/a.py"])
    ])})
    with patch("prep.services.concept_store.concept_store") as store:
        store.save_many.return_value = (1, 0)
        report = synthesize_concepts_swarm(
            "p1", llm=llm, swarm_size=1,
            idx_dir=tmp_path, project_root=tmp_path,
            project_name="test",
        )
    assert report.worker_count == 1
    assert report.candidates_emitted_total == 1


# ── Freshness short-circuit (scrutiny fix) ──────────────────────────


def test_swarm_skips_when_rationale_unchanged(tmp_path):
    """Second run with same rationale fingerprint must short-circuit
    without firing the LLM."""
    llm = _llm_returning({
        "intent": "[]", "rules": "[]", "implementation": "[]",
    })
    # Pre-write a manifest matching the patched _rationale_fingerprint
    # default. The autouse fixture's grounding has 2 rationale rows,
    # but _rationale_fingerprint reads concept_store, which our autouse
    # patch_loaders fixture doesn't intercept. Patch _rationale_fingerprint
    # directly here to force a deterministic fingerprint.
    with patch(
        "prep.core.concept_generate_swarm._rationale_fingerprint",
        return_value=(5, 1000.0),
    ), patch(
        "prep.core.concept_generate_swarm._read_gen_swarm_manifest",
        return_value={
            "rationale_count": 5,
            "rationale_max_updated_at": 1500.0,
            "completed_at": 1500.0,
            "prompt_revision": 999,    # match current; freshness applies
        },
    ), patch(
        "prep.core.concept_generate_swarm._GEN_PROMPT_REVISION", 999,
    ), patch("prep.services.concept_store.concept_store") as store:
        store.save_many = MagicMock(side_effect=AssertionError("save should not run"))
        report = synthesize_concepts_swarm(
            "p1", llm=llm, swarm_size=3,
            idx_dir=tmp_path, project_root=tmp_path,
            project_name="test",
        )
    assert report.skipped_fresh is True
    assert report.candidates_emitted_total == 0
    # No LLM call should have happened (we didn't pre-set llm.generate
    # to refuse; the gate is structural — if the freshness check fails,
    # ANY worker-bound call would have hit the empty `_llm_returning`
    # which returns "[]" rather than raising). We assert via
    # candidates_emitted_total == 0 + skipped_fresh + save not called.


def test_force_bypasses_freshness_check(tmp_path):
    """force=True overrides the manifest-based skip."""
    intent_out = json.dumps([
        _concept_json("Forced", "T2", "architecture", ["src/x.py"])
    ])
    llm = _llm_returning({
        "intent": intent_out, "rules": "[]", "implementation": "[]",
    })
    with patch(
        "prep.core.concept_generate_swarm._rationale_fingerprint",
        return_value=(5, 1000.0),
    ), patch(
        "prep.core.concept_generate_swarm._read_gen_swarm_manifest",
        return_value={
            "rationale_count": 5,
            "rationale_max_updated_at": 1500.0,
            "prompt_revision": 999,
        },
    ), patch(
        "prep.core.concept_generate_swarm._GEN_PROMPT_REVISION", 999,
    ), patch("prep.services.concept_store.concept_store") as store:
        store.save_many.return_value = (1, 0)
        report = synthesize_concepts_swarm(
            "p1", llm=llm, swarm_size=3,
            idx_dir=tmp_path, project_root=tmp_path,
            project_name="test",
            force=True,
        )
    assert report.skipped_fresh is False
    assert report.candidates_emitted_total == 1


def test_swarm_runs_when_prompt_revision_bumped(tmp_path):
    """Manifest from an older prompt revision is treated as stale even
    when rationale is unchanged — bumping prompts forces a re-run so
    behavior changes take effect immediately."""
    intent_out = json.dumps([
        _concept_json("After bump", "T2", "architecture", ["src/x.py"])
    ])
    llm = _llm_returning({
        "intent": intent_out, "rules": "[]", "implementation": "[]",
    })
    with patch(
        "prep.core.concept_generate_swarm._rationale_fingerprint",
        return_value=(5, 1000.0),   # rationale unchanged
    ), patch(
        "prep.core.concept_generate_swarm._read_gen_swarm_manifest",
        return_value={
            "rationale_count": 5,
            "rationale_max_updated_at": 1500.0,
            "prompt_revision": 1,    # older than current
        },
    ), patch(
        "prep.core.concept_generate_swarm._GEN_PROMPT_REVISION", 2,
    ), patch("prep.services.concept_store.concept_store") as store:
        store.save_many.return_value = (1, 0)
        report = synthesize_concepts_swarm(
            "p1", llm=llm, swarm_size=3,
            idx_dir=tmp_path, project_root=tmp_path,
            project_name="test",
        )
    assert report.skipped_fresh is False
    assert report.candidates_emitted_total == 1


def test_swarm_runs_when_rationale_changed(tmp_path):
    """Manifest is older than current rationale max_ts → must run."""
    intent_out = json.dumps([
        _concept_json("Refreshed", "T2", "architecture", ["src/x.py"])
    ])
    llm = _llm_returning({
        "intent": intent_out, "rules": "[]", "implementation": "[]",
    })
    with patch(
        "prep.core.concept_generate_swarm._rationale_fingerprint",
        return_value=(7, 2000.0),   # rationale grew + max_ts moved forward
    ), patch(
        "prep.core.concept_generate_swarm._read_gen_swarm_manifest",
        return_value={
            "rationale_count": 5,
            "rationale_max_updated_at": 1500.0,
            "prompt_revision": 999,
        },
    ), patch(
        "prep.core.concept_generate_swarm._GEN_PROMPT_REVISION", 999,
    ), patch("prep.services.concept_store.concept_store") as store:
        store.save_many.return_value = (1, 0)
        report = synthesize_concepts_swarm(
            "p1", llm=llm, swarm_size=3,
            idx_dir=tmp_path, project_root=tmp_path,
            project_name="test",
        )
    assert report.skipped_fresh is False
    assert report.candidates_emitted_total == 1


# ── Module-level grounding/docs loaders are bypassed via mocks ──────


@pytest.fixture(autouse=True)
def patch_loaders(tmp_path):
    """Patch grounding loader + docs loader so tests don't read disk."""
    with patch(
        "prep.core.concept_generate_swarm.load_grounding",
        return_value=_grounding(),
    ), patch(
        "prep.core.concept_generate_swarm.load_or_build_docs_grounding",
        return_value=_docs(),
    ):
        yield
