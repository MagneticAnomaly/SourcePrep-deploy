import pytest
from prep.core.audit.recommendations import generate_recommendation, compute_risk_score


def test_critical_hub_with_concept():
    rec = generate_recommendation(
        hub_status="critical",
        dependents=23,
        concepts=["Planned refactor: split handler dispatch"],
        observations=[],
    )
    assert "Critical hub file" in rec
    assert "23 dependents" in rec
    assert "Planned refactor" in rec


def test_moderate_hub_no_concept():
    rec = generate_recommendation(
        hub_status="moderate",
        dependents=8,
        concepts=[],
        observations=[],
    )
    assert "Moderate coupling" in rec


def test_hub_with_observations():
    rec = generate_recommendation(
        hub_status="high",
        dependents=15,
        concepts=[],
        observations=["2026-03-15: Growing concern", "2026-04-01: Still growing"],
    )
    assert "Flagged 2 times" in rec


def test_low_risk_file():
    rec = generate_recommendation(
        hub_status="low",
        dependents=2,
        concepts=[],
        observations=[],
    )
    assert "Low coupling" in rec


def test_risk_score_critical_hub_with_concept():
    score = compute_risk_score(
        hub_percentile=0.95,
        has_constraint_concept=True,
        has_architecture_concept=False,
        observation_score=0.5,
        churn_score=0.3,
    )
    # 0.40*0.95 + 0.30*1.0 + 0.20*0.5 + 0.10*0.3 = 0.81
    assert abs(score - 0.81) < 0.01


def test_risk_score_leaf_file():
    score = compute_risk_score(
        hub_percentile=0.1,
        has_constraint_concept=False,
        has_architecture_concept=False,
        observation_score=0.0,
        churn_score=0.1,
    )
    # 0.40*0.1 + 0.30*0.0 + 0.20*0.0 + 0.10*0.1 = 0.05
    assert abs(score - 0.05) < 0.01


def test_risk_score_clamped_0_to_1():
    score = compute_risk_score(
        hub_percentile=1.0,
        has_constraint_concept=True,
        observation_score=1.0,
        churn_score=1.0,
    )
    assert 0.0 <= score <= 1.0
