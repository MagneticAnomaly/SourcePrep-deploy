import pytest
from prep.core.antibodies import (
    Antibody, Trigger, TriggerType, Response, ResponseType, Severity,
    evaluate_trigger, _path_matches,
)
from prep.core.antibody_derivation import (
    suggest_antibody, _extract_import_pattern, derive_antibodies_for_project,
)


# --- Trigger evaluation tests ---

def test_import_trigger_fires_on_matching_import():
    trigger = Trigger(
        type=TriggerType.IMPORT_ADDED,
        target="src/pi_agent.py",
        pattern="llm_client|openai|anthropic",
    )
    content = "import os\nfrom prep.core.llm_client import generate\nimport json"
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
    assert _path_matches("src/prep/pi_agent/main.py", "src/prep/pi_agent/**") is True

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


# --- Status inheritance tests (closes the testing/active mismatch) ---


def test_active_concept_produces_active_antibody():
    """A concept the user has explicitly promoted to 'active' should
    derive an antibody that fires immediately. Closes the bug where
    517 derived antibodies stayed forever in 'testing' because nobody
    manually promoted them."""
    concept = {
        "id": "c-active", "title": "No openai in core",
        "content": "core must not import openai",
        "assertion": "core must not import openai",
        "category": "constraint", "status": "active",
        "anchors": ["src/core/foo.py"],
    }
    ab = suggest_antibody(concept)
    assert ab is not None
    assert ab.status == "active"


def test_seed_concept_still_produces_testing_antibody():
    """An unvetted seed concept should still derive a 'testing' antibody
    that requires manual promotion — preserves the safety valve."""
    concept = {
        "id": "c-seed", "title": "Tentative constraint",
        "content": "core must not import openai",
        "assertion": "core must not import openai",
        "category": "constraint", "status": "seed",
        "anchors": ["src/core/foo.py"],
    }
    ab = suggest_antibody(concept)
    assert ab is not None
    assert ab.status == "testing"


def test_proposed_concept_produces_testing_antibody():
    """proposed/triage_pending/shadow are also unvetted — testing only."""
    for status in ("proposed", "triage_pending", "shadow", "testing"):
        concept = {
            "id": f"c-{status}", "title": f"x ({status})",
            "content": "must not import x",
            "category": "constraint", "status": status,
            "anchors": ["src/a.py"],
        }
        ab = suggest_antibody(concept)
        assert ab is not None, f"failed to derive for status={status}"
        assert ab.status == "testing", (
            f"status={status} should produce testing antibody, got {ab.status}"
        )


def test_archived_concept_skips_derivation():
    """Archived/superseded/deprecated concepts must not derive antibodies
    at all — the upstream concept is gone, the antibody would be orphaned."""
    for status in ("archived", "superseded", "deprecated"):
        concept = {
            "id": f"c-{status}", "title": f"x ({status})",
            "content": "must not import x",
            "category": "constraint", "status": status,
            "anchors": ["src/a.py"],
        }
        assert suggest_antibody(concept) is None, (
            f"status={status} should not derive an antibody"
        )


def test_missing_status_defaults_to_testing():
    """Concepts without an explicit status (legacy rows / dict literals)
    must NOT silently auto-fire — default to testing."""
    concept = {
        "id": "c-no-status", "title": "no status",
        "content": "must not import openai",
        "category": "constraint",
        "anchors": ["src/a.py"],
    }
    ab = suggest_antibody(concept)
    assert ab is not None
    assert ab.status == "testing"


def test_derive_for_project_inherits_per_concept_status():
    """End-to-end: a mixed batch produces the right per-concept inheritance."""
    concepts = [
        {"id": "ca", "title": "active",
         "content": "must not import openai",
         "category": "constraint", "status": "active",
         "anchors": ["src/a.py"]},
        {"id": "cs", "title": "seed",
         "content": "must not import requests",
         "category": "constraint", "status": "seed",
         "anchors": ["src/b.py"]},
        {"id": "cd", "title": "deprecated",
         "content": "must not import flask",
         "category": "constraint", "status": "deprecated",
         "anchors": ["src/c.py"]},
    ]
    out = derive_antibodies_for_project(concepts)
    by_source = {ab.source_concept_id: ab for ab in out}
    assert by_source["ca"].status == "active"
    assert by_source["cs"].status == "testing"
    assert "cd" not in by_source  # archived/deprecated → skipped


# --- Layer filter: only kind="concept" derives ---


def test_module_rationale_concepts_do_not_derive_antibodies():
    """``kind='module_rationale'`` rows (per-module observations,
    ~thousands per project) must NOT auto-derive antibodies — they're
    too noisy a substrate for runtime alerts. Closes a gap caught
    during the 2026-05-07 scrutiny pass: ``concept_store.list_concepts``
    returns both kinds by default, so a project with thousands of
    rationale entries would otherwise produce noisy auto-derived
    antibodies on every pipeline run."""
    rationale = {
        "id": "r-1", "title": "Module rationale",
        "content": "must not import openai",
        "category": "constraint", "status": "active",
        "anchors": ["src/a.py"],
        "kind": "module_rationale",
    }
    assert suggest_antibody(rationale) is None


def test_concept_kind_default_still_derives():
    """Legacy concept dicts that omit the ``kind`` field (e.g. older
    rows or hand-built dicts) must still derive — default to the
    derivable kind."""
    concept_no_kind = {
        "id": "c-no-kind", "title": "no kind",
        "content": "must not import openai",
        "category": "constraint", "status": "active",
        "anchors": ["src/a.py"],
    }
    ab = suggest_antibody(concept_no_kind)
    assert ab is not None


def test_explicit_concept_kind_derives():
    """Explicit ``kind='concept'`` rows derive (the small curated layer)."""
    concept = {
        "id": "c-1", "title": "explicit concept",
        "content": "must not import openai",
        "category": "constraint", "status": "active",
        "anchors": ["src/a.py"],
        "kind": "concept",
    }
    ab = suggest_antibody(concept)
    assert ab is not None


# --- Stable IDs: re-derivation upserts in place ---


def test_re_derivation_produces_stable_id():
    """Calling suggest_antibody twice on the same concept must yield
    the same antibody.id so the underlying INSERT OR REPLACE upserts
    in place rather than accumulating duplicates across pipeline runs.
    Closes a gap caught during scrutiny: the previous uuid4 ID meant
    every run grew the antibodies table by N rows."""
    concept = {
        "id": "c-stable", "title": "stable",
        "content": "must not import openai",
        "category": "constraint", "status": "active",
        "anchors": ["src/a.py"],
    }
    ab1 = suggest_antibody(concept)
    ab2 = suggest_antibody(concept)
    assert ab1 is not None and ab2 is not None
    assert ab1.id == ab2.id


def test_distinct_concepts_produce_distinct_ids():
    """Different source concepts must still produce different IDs."""
    a = {
        "id": "ca", "title": "A",
        "content": "must not import openai",
        "category": "constraint", "status": "active",
        "anchors": ["src/a.py"],
    }
    b = {
        "id": "cb", "title": "B",
        "content": "must not import openai",
        "category": "constraint", "status": "active",
        "anchors": ["src/b.py"],  # different anchor → different trigger target
    }
    ab1 = suggest_antibody(a)
    ab2 = suggest_antibody(b)
    assert ab1 is not None and ab2 is not None
    assert ab1.id != ab2.id


def test_distinct_trigger_types_produce_distinct_ids():
    """Same source concept producing both an import-trigger and a
    file-modified trigger (hypothetically, via different content
    derivations) must produce distinct IDs so they don't collide."""
    # concept that yields import-trigger (matches _extract_import_pattern)
    import_concept = {
        "id": "c-shared", "title": "import",
        "content": "must not import openai",
        "category": "constraint", "status": "active",
        "anchors": ["src/a.py"],
    }
    # concept with same id but content that DOESN'T match import pattern,
    # so it falls through to FILE_MODIFIED
    file_concept = {
        "id": "c-shared", "title": "file",
        "content": "anchored architecture invariant",
        "category": "architecture", "status": "active",
        "anchors": ["src/a.py"],
    }
    ab1 = suggest_antibody(import_concept)
    ab2 = suggest_antibody(file_concept)
    assert ab1 is not None and ab2 is not None
    assert ab1.id != ab2.id, "trigger type should be part of the ID hash"
