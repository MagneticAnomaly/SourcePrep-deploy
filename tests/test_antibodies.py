import pytest
from codrag.core.antibodies import (
    Antibody, Trigger, TriggerType, Response, ResponseType, Severity,
    evaluate_trigger, _path_matches,
)
from codrag.core.antibody_derivation import (
    suggest_antibody, _extract_import_pattern, derive_antibodies_for_project,
)


# --- Trigger evaluation tests ---

def test_import_trigger_fires_on_matching_import():
    trigger = Trigger(
        type=TriggerType.IMPORT_ADDED,
        target="src/pi_agent.py",
        pattern="llm_client|openai|anthropic",
    )
    content = "import os\nfrom codrag.core.llm_client import generate\nimport json"
    assert evaluate_trigger(trigger, "src/pi_agent.py", content) is True


def test_import_trigger_does_not_fire_on_safe_imports():
    trigger = Trigger(
        type=TriggerType.IMPORT_ADDED,
        target="src/pi_agent.py",
        pattern="llm_client|openai",
    )
    content = "import os\nimport json\nfrom pathlib import Path"
    assert evaluate_trigger(trigger, "src/pi_agent.py", content) is False


def test_import_trigger_wrong_file():
    trigger = Trigger(
        type=TriggerType.IMPORT_ADDED,
        target="src/pi_agent.py",
        pattern="llm_client",
    )
    assert evaluate_trigger(trigger, "src/other.py", "from llm_client import x") is False


def test_file_modified_trigger():
    trigger = Trigger(type=TriggerType.FILE_MODIFIED, target="src/server.py")
    assert evaluate_trigger(trigger, "src/server.py") is True
    assert evaluate_trigger(trigger, "src/other.py") is False


def test_pattern_match_trigger():
    trigger = Trigger(
        type=TriggerType.PATTERN_MATCH,
        target="src/dashboard/",
        pattern=r"fetch\(.*/api/pipeline/status",
    )
    content = 'const data = await fetch("/api/pipeline/status")'
    assert evaluate_trigger(trigger, "src/dashboard/App.tsx", content) is True


def test_pattern_match_no_match():
    trigger = Trigger(
        type=TriggerType.PATTERN_MATCH,
        target="src/dashboard/",
        pattern=r"fetch\(.*/api/pipeline/status",
    )
    assert evaluate_trigger(trigger, "src/dashboard/App.tsx", "const x = 1") is False


def test_path_matches_exact():
    assert _path_matches("src/server.py", "src/server.py") is True

def test_path_matches_directory():
    assert _path_matches("src/dashboard/App.tsx", "src/dashboard/") is True

def test_path_matches_glob():
    assert _path_matches("src/codrag/pi_agent/main.py", "src/codrag/pi_agent/**") is True

def test_path_no_match():
    assert _path_matches("src/other.py", "src/server.py") is False


# --- Antibody serialization tests ---

def test_antibody_round_trip():
    ab = Antibody(
        id="ab-1", name="Guard: Zero LLM", source_concept_id="c-1",
        trigger=Trigger(type=TriggerType.IMPORT_ADDED, target="src/pi.py", pattern="openai"),
        response=Response(type=ResponseType.AMBIENT_INJECT, message="LLM violation"),
        severity=Severity.REVIEW, status="active",
    )
    d = ab.to_dict()
    restored = Antibody.from_dict(d)
    assert restored.id == "ab-1"
    assert restored.trigger.pattern == "openai"
    assert restored.severity == Severity.REVIEW


# --- Derivation tests ---

def test_suggest_antibody_from_constraint():
    concept = {
        "id": "c-1", "title": "Zero-LLM Pi Agent",
        "content": "Pi Agent must never import llm_client, openai, or anthropic",
        "assertion": "pi_agent.py must not import llm_client, openai, or anthropic",
        "category": "constraint", "status": "active",
        "anchors": ["src/pi_agent.py"],
    }
    ab = suggest_antibody(concept)
    assert ab is not None
    assert ab.trigger.type == TriggerType.IMPORT_ADDED
    assert "llm_client" in ab.trigger.pattern
    assert ab.severity == Severity.REVIEW


def test_suggest_antibody_from_architecture():
    concept = {
        "id": "c-2", "title": "Server dispatch refactoring",
        "content": "server.py should use modular dispatch",
        "category": "architecture", "status": "active",
        "anchors": ["src/server.py"],
    }
    ab = suggest_antibody(concept)
    assert ab is not None
    assert ab.trigger.type == TriggerType.FILE_MODIFIED
    assert ab.severity == Severity.INFORM


def test_suggest_antibody_returns_none_for_pattern():
    concept = {
        "id": "c-3", "title": "Convention",
        "content": "Use snake_case", "category": "pattern",
        "anchors": ["src/"],
    }
    assert suggest_antibody(concept) is None


def test_suggest_antibody_returns_none_without_anchors():
    concept = {
        "id": "c-4", "title": "No anchors",
        "content": "General knowledge", "category": "constraint",
        "anchors": [],
    }
    assert suggest_antibody(concept) is None


def test_extract_import_pattern_never():
    pattern = _extract_import_pattern("must not import openai, anthropic")
    assert pattern is not None
    assert "openai" in pattern
    assert "anthropic" in pattern


def test_extract_import_pattern_zero():
    pattern = _extract_import_pattern("zero llm imports allowed")
    assert pattern is not None
    assert "llm" in pattern


def test_extract_import_pattern_no_match():
    assert _extract_import_pattern("the server uses dispatch pattern") is None


def test_derive_antibodies_for_project():
    concepts = [
        {"id": "c-1", "title": "A", "content": "must not import openai",
         "category": "constraint", "anchors": ["src/a.py"]},
        {"id": "c-2", "title": "B", "content": "B note",
         "category": "pattern", "anchors": ["src/"]},
        {"id": "c-3", "title": "C", "content": "C arch",
         "category": "architecture", "anchors": ["src/c.py"]},
    ]
    results = derive_antibodies_for_project(concepts)
    assert len(results) == 2  # constraint + architecture, not pattern
