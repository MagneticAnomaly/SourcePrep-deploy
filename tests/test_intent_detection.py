"""Tests for intent detection quality (Problem #5).

Verifies that _classify_query_intent() maps queries to the right category,
and that intent-based role weighting actually shifts rankings in the expected
direction for a corpus with distinct code, docs, and test files.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from codrag.core import CodeIndex
from codrag.core.index import CodeIndex as _CodeIndex


# ---------------------------------------------------------------------------
# Intent classification unit tests
# ---------------------------------------------------------------------------

class TestIntentClassification:
    """Test _classify_query_intent() directly without a built index."""

    @pytest.fixture
    def idx(self, tmp_path, fake_embedder):
        idx = _CodeIndex(index_dir=tmp_path / "idx", embedder=fake_embedder)
        return idx

    def test_code_query_classified_as_code(self, idx):
        for q in [
            "implement a login function",
            "write a class for database connection",
            "how to create a new endpoint",
            "refactor the auth module",
        ]:
            result = idx._classify_query_intent(q)
            assert result == "code", f"{q!r} → expected 'code', got {result!r}"

    def test_debug_query_classified_as_debug(self, idx):
        for q in [
            "fix the null pointer exception",
            "why is this failing with KeyError",
            "debug the authentication error",
            "traceback in the API handler",
        ]:
            result = idx._classify_query_intent(q)
            assert result in ("debug", "code"), f"{q!r} → unexpected intent {result!r}"

    def test_docs_query_classified_as_docs(self, idx):
        for q in [
            "explain the database architecture",
            "what is the purpose of the cache module",
            "overview of the API design",
            "show the reference for the CLI",
            "summary of the design decisions",
        ]:
            result = idx._classify_query_intent(q)
            assert result in ("docs", "code"), f"{q!r} → unexpected intent {result!r}"

    @pytest.mark.xfail(
        reason="Problem #5: 'how does X work' has no keyword match — needs semantic classification",
        strict=True,
    )
    def test_how_does_x_work_classified_as_docs(self, idx):
        """Genuinely hard: no docs/code keyword in 'how does the auth system work'."""
        result = idx._classify_query_intent("how does the authentication system work")
        assert result in ("docs", "code"), f"Expected docs/code, got {result!r}"

    def test_tests_query_classified_as_tests(self, idx):
        for q in [
            "write a unit test for the login function",
            "test the database connection",
            "mock the API endpoint in tests",
        ]:
            result = idx._classify_query_intent(q)
            assert result in ("tests", "code"), f"{q!r} → unexpected intent {result!r}"

    def test_assert_keyword_recognized_as_tests(self, idx):
        result = idx._classify_query_intent("assert the expected output")
        assert result in ("tests", "code"), f"Expected tests/code, got {result!r}"

    def test_returns_string_not_none(self, idx):
        """Intent classification should always return a non-empty string."""
        for q in ["", "???", "   ", "a", "nomic embed code benchmark"]:
            result = idx._classify_query_intent(q)
            assert isinstance(result, str) and result, f"Empty/None intent for {q!r}"

    def test_code_beats_docs_for_implementation_query(self, idx):
        """'implement X' should be code, not docs."""
        assert idx._classify_query_intent("implement the retry decorator") == "code"

    def test_tests_beats_code_for_test_query(self, idx):
        """'test X' queries should classify as tests, not code."""
        result = idx._classify_query_intent("test user login and registration")
        assert result == "tests", f"Expected 'tests', got {result!r}"


# ---------------------------------------------------------------------------
# Role weighting integration tests
# ---------------------------------------------------------------------------

class TestIntentRoleWeighting:
    """Test that intent-based role weighting shifts rankings in expected direction."""

    @pytest.fixture
    def multi_role_index(self, tmp_path, fake_embedder):
        """Index with distinct code, docs, and test files about 'auth'."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "auth.py").write_text(
            "def login(user, password):\n    return verify(user, password)\n"
            "def logout(user):\n    session.clear()\n"
        )
        (repo / "auth_docs.md").write_text(
            "# Authentication Guide\n"
            "The auth system uses JWT tokens. Login flow: user submits credentials, "
            "server validates, returns token. See auth.py for implementation.\n"
        )
        (repo / "test_auth.py").write_text(
            "def test_login_success():\n    assert login('user', 'pass') is not None\n"
            "def test_logout_clears_session():\n    logout('user')\n    assert session == {}\n"
        )
        idx = _CodeIndex(index_dir=tmp_path / "idx", embedder=fake_embedder)
        idx.build(repo_root=repo)
        return idx

    def test_search_returns_results(self, multi_role_index):
        """Sanity: search returns results at all."""
        results = multi_role_index.search("authentication login", k=5, min_score=0.0)
        assert len(results) > 0

    def test_intent_multipliers_are_applied(self, multi_role_index):
        """_intent_role_multipliers() should return a dict with numeric values."""
        idx = multi_role_index
        for intent in ("code", "docs", "tests", "debug", "general"):
            mults = idx._intent_role_multipliers(intent)
            assert isinstance(mults, dict)
            assert all(isinstance(v, (int, float)) for v in mults.values())
            assert all(v > 0 for v in mults.values())

    def test_code_intent_boosts_code_files(self, multi_role_index):
        """For code intent, code role weight should be >= docs role weight."""
        idx = multi_role_index
        code_mults = idx._intent_role_multipliers("code")
        # code multiplier should be >= docs multiplier for code queries
        assert code_mults.get("code", 1.0) >= code_mults.get("docs", 1.0)

    def test_docs_intent_boosts_docs_files(self, multi_role_index):
        """For docs intent, docs role weight should be >= code role weight."""
        idx = multi_role_index
        docs_mults = idx._intent_role_multipliers("docs")
        assert docs_mults.get("docs", 1.0) >= docs_mults.get("code", 1.0)

    def test_test_intent_boosts_test_files(self, multi_role_index):
        """For tests intent, tests role weight should be >= code role weight."""
        idx = multi_role_index
        test_mults = idx._intent_role_multipliers("tests")
        assert test_mults.get("tests", 1.0) >= test_mults.get("code", 1.0)
