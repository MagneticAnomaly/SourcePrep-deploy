"""
Tests for the FIX-16-4 re-prompt loop wired into `ClusterSynthesizer.synthesize_cluster`.

When the first LLM response contains banned consulting-deck phrases, the
synthesizer issues one extra LLM call asking for a rewrite. The retry result
is preferred; if the retry fails, the original (linted) response is kept.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from prep.core.cluster import Cluster, ClusterSynthesizer, EpistemicEntry


def _epi(node_id: str) -> EpistemicEntry:
    return EpistemicEntry(
        node_id=node_id,
        extended_summary=f"summary for {node_id}",
        domain_tags=["test"],
        architecture_layer="domain",
        epistemic_confidence=0.7,
    )


def _make_synth(llm: MagicMock, tmp_path: Path) -> ClusterSynthesizer:
    return ClusterSynthesizer(llm=llm, index_dir=tmp_path)


def _llm_response(payload: dict) -> tuple[str, int]:
    return (json.dumps(payload), 100)


def test_clean_summary_does_not_trigger_reprompt(tmp_path):
    """When the first LLM response is clean, no retry call is made."""
    llm = MagicMock()
    llm.model = "test-model"
    llm.generate.return_value = _llm_response({
        "name": "Auth Service",
        "summary": (
            "Validates JSON Web Tokens against the configured issuer. "
            "Persists rotation events to audit log."
        ),
        "component_status": "complete",
        "data_flow": "request -> validator -> log",
        "dependencies": [],
        "tech_debt_summary": None,
    })
    synth = _make_synth(llm, tmp_path)
    cluster = Cluster(
        cluster_id="cluster:auth:0",
        primary_tag="auth",
        member_node_ids=["file:src/auth/jwt.py"],
        all_tags={"auth"},
    )
    epistemic = {"file:src/auth/jwt.py": _epi("file:src/auth/jwt.py")}
    mod = synth.synthesize_cluster(cluster, epistemic, edges=[])

    assert mod is not None
    assert "Validates JSON Web Tokens" in mod.summary
    # Exactly one LLM call — no re-prompt
    assert llm.generate.call_count == 1


def test_banned_phrase_triggers_one_reprompt(tmp_path):
    """A banned-phrase summary triggers exactly one retry. The retry's
    cleaner output is the one stored on the ModuleEntry."""
    llm = MagicMock()
    llm.model = "test-model"
    llm.generate.side_effect = [
        _llm_response({
            "name": "Auth Service",
            "summary": (
                "Bridges enterprise policy enforcement with consumer-grade "
                "privacy while maintaining seamless integration."
            ),
            "component_status": "complete",
            "data_flow": "x",
            "dependencies": [],
            "tech_debt_summary": None,
        }),
        _llm_response({
            "name": "Auth Service",
            "summary": "Validates JWT tokens against the issuer.",
            "component_status": "complete",
            "data_flow": "x",
            "dependencies": [],
            "tech_debt_summary": None,
        }),
    ]
    synth = _make_synth(llm, tmp_path)
    cluster = Cluster(
        cluster_id="cluster:auth:0",
        primary_tag="auth",
        member_node_ids=["file:src/auth/jwt.py"],
        all_tags={"auth"},
    )
    epistemic = {"file:src/auth/jwt.py": _epi("file:src/auth/jwt.py")}

    mod = synth.synthesize_cluster(cluster, epistemic, edges=[])

    assert mod is not None
    # The retry's clean summary won
    assert mod.summary == "Validates JWT tokens against the issuer."
    # Exactly two LLM calls
    assert llm.generate.call_count == 2
    # The retry prompt contained the banned-phrase feedback
    second_prompt = llm.generate.call_args_list[1][0][0]
    assert "ADDITIONAL CONSTRAINT" in second_prompt
    assert "while maintaining" in second_prompt or "bridges" in second_prompt


def test_reprompt_failure_keeps_original(tmp_path):
    """If the retry call raises, the synthesizer keeps the original linted
    response rather than crashing or producing a fallback."""
    llm = MagicMock()
    llm.model = "test-model"
    original_summary = "Bridges X with Y while maintaining Z."
    llm.generate.side_effect = [
        _llm_response({
            "name": "Auth",
            "summary": original_summary,
            "component_status": "complete",
            "data_flow": "x",
            "dependencies": [],
            "tech_debt_summary": None,
        }),
        RuntimeError("retry boom"),
    ]
    synth = _make_synth(llm, tmp_path)
    cluster = Cluster(
        cluster_id="cluster:auth:0",
        primary_tag="auth",
        member_node_ids=["file:src/auth/jwt.py"],
        all_tags={"auth"},
    )
    epistemic = {"file:src/auth/jwt.py": _epi("file:src/auth/jwt.py")}

    mod = synth.synthesize_cluster(cluster, epistemic, edges=[])

    assert mod is not None
    assert mod.summary == original_summary  # original kept after failed retry
    assert llm.generate.call_count == 2


def test_reprompt_caps_at_one_retry(tmp_path):
    """Even if the retry response ALSO has banned phrases, no third call is
    made — the loop is one-shot, not unbounded."""
    llm = MagicMock()
    llm.model = "test-model"
    bad_payload = {
        "name": "X",
        "summary": "Bridges A with B while maintaining C.",
        "component_status": "complete",
        "data_flow": "x",
        "dependencies": [],
        "tech_debt_summary": None,
    }
    llm.generate.side_effect = [
        _llm_response(bad_payload),
        _llm_response(bad_payload),  # retry still bad
        _llm_response(bad_payload),  # would be third — must not be called
    ]
    synth = _make_synth(llm, tmp_path)
    cluster = Cluster(
        cluster_id="cluster:x:0",
        primary_tag="x",
        member_node_ids=["file:src/x.py"],
        all_tags={"x"},
    )
    epistemic = {"file:src/x.py": _epi("file:src/x.py")}

    mod = synth.synthesize_cluster(cluster, epistemic, edges=[])
    assert mod is not None
    assert llm.generate.call_count == 2  # NOT 3
