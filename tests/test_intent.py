import pytest
from prep.core.intent import classify_intent, rewrite_query, SearchIntent


# --- Classification tests ---

def test_locate_where_is():
    intent, conf = classify_intent("where is the auth middleware")
    assert intent == SearchIntent.LOCATE

def test_locate_find():
    intent, conf = classify_intent("find PersonaMemoryStore")
    assert intent == SearchIntent.LOCATE

def test_locate_definition():
    intent, conf = classify_intent("definition of _score_memory_with_relevance")
    assert intent == SearchIntent.LOCATE

def test_explain_how_does():
    intent, conf = classify_intent("how does the pipeline work")
    assert intent == SearchIntent.EXPLAIN

def test_explain_what_does():
    intent, conf = classify_intent("what does tool_audit_structural do")
    assert intent == SearchIntent.EXPLAIN

def test_rationale_why():
    intent, conf = classify_intent("why does the server use dispatch pattern")
    assert intent == SearchIntent.RATIONALE

def test_rationale_instead_of():
    intent, conf = classify_intent("the auth module uses JWT instead of sessions")
    assert intent == SearchIntent.RATIONALE

def test_trace_who_imports():
    intent, conf = classify_intent("who imports server.py")
    assert intent == SearchIntent.TRACE

def test_trace_dependents():
    intent, conf = classify_intent("dependents of app.py")
    assert intent == SearchIntent.TRACE

def test_example_how_to_use():
    intent, conf = classify_intent("how to use enrich_findings")
    assert intent == SearchIntent.EXAMPLE

def test_example_call_sites():
    intent, conf = classify_intent("call sites for compute_risk_score")
    assert intent == SearchIntent.EXAMPLE

def test_compare():
    intent, conf = classify_intent("difference between Flask and FastAPI routes")
    assert intent == SearchIntent.COMPARE

def test_compare_vs():
    intent, conf = classify_intent("concept_store vs observation_store")
    assert intent == SearchIntent.COMPARE

def test_discover_whats_in():
    intent, conf = classify_intent("what's in the core/audit directory")
    assert intent == SearchIntent.DISCOVER

def test_discover_overview():
    intent, conf = classify_intent("overview of the MCP module")
    assert intent == SearchIntent.DISCOVER

def test_default_is_explain():
    intent, conf = classify_intent("PersonaMemoryStore")
    assert intent == SearchIntent.EXPLAIN
    assert conf == "low"

def test_high_confidence():
    _, conf = classify_intent("where is the auth middleware")
    assert conf == "high"

def test_bare_symbol_is_explain():
    intent, _ = classify_intent("enrich_findings")
    assert intent == SearchIntent.EXPLAIN


# --- Query rewriting tests ---

def test_rewrite_locate():
    result = rewrite_query("where is the auth middleware", SearchIntent.LOCATE)
    assert result == "the auth middleware"

def test_rewrite_explain():
    result = rewrite_query("how does the pipeline work", SearchIntent.EXPLAIN)
    assert result == "the pipeline work"

def test_rewrite_rationale():
    result = rewrite_query("why does server.py use dispatch", SearchIntent.RATIONALE)
    assert result == "server.py use dispatch"

def test_rewrite_preserves_bare_query():
    result = rewrite_query("PersonaMemoryStore", SearchIntent.EXPLAIN)
    assert result == "PersonaMemoryStore"

def test_rewrite_trace():
    result = rewrite_query("who imports server.py", SearchIntent.TRACE)
    assert result == "server.py"
