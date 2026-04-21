"""Tests for Phase 34e F: Query preprocessing."""

import pytest

from prep.core.query import preprocess_query as _preprocess_query, _MAX_QUERY_CHARS


class TestPreprocessQuery:
    """Test _preprocess_query F1/F2/F3."""

    # ── F2: Filler removal ───────────────────────────────────────

    def test_strips_please(self):
        assert _preprocess_query("please find the main function") == "find the main function"

    def test_strips_can_you(self):
        assert _preprocess_query("can you show the database models") == "show the database models"

    def test_strips_could_you(self):
        assert _preprocess_query("could you find the auth handler") == "find the auth handler"

    def test_strips_i_want_to(self):
        assert _preprocess_query("I want to find the login route") == "find the login route"

    def test_strips_i_need_to(self):
        assert _preprocess_query("I need to understand the config module") == "understand the config module"

    def test_strips_help_me(self):
        assert _preprocess_query("help me find the error handler") == "find the error handler"

    def test_strips_im_trying_to(self):
        assert _preprocess_query("I'm trying to fix the parser") == "fix the parser"

    def test_strips_show_me(self):
        assert _preprocess_query("show me the test fixtures") == "the test fixtures"

    def test_strips_lets(self):
        assert _preprocess_query("let's look at the router") == "look at the router"

    def test_strips_chained_filler(self):
        assert _preprocess_query("please can you find the main function") == "find the main function"

    def test_case_insensitive(self):
        assert _preprocess_query("PLEASE find the main") == "find the main"
        assert _preprocess_query("Can You show models") == "show models"

    def test_preserves_non_filler(self):
        assert _preprocess_query("find the authentication handler") == "find the authentication handler"

    # ── F1: Truncation ───────────────────────────────────────────

    def test_short_query_unchanged(self):
        q = "find the main function"
        assert _preprocess_query(q) == q

    def test_truncates_long_query_at_word_boundary(self):
        long_q = "word " * 100  # 500 chars
        result = _preprocess_query(long_q)
        assert len(result) <= _MAX_QUERY_CHARS
        assert not result.endswith(" ")  # Clean word boundary

    def test_truncates_at_limit(self):
        # Exactly at limit — no truncation needed
        q = "a" * _MAX_QUERY_CHARS
        result = _preprocess_query(q)
        assert len(result) == _MAX_QUERY_CHARS

    def test_truncates_above_limit(self):
        q = "a" * (_MAX_QUERY_CHARS + 50)
        result = _preprocess_query(q)
        assert len(result) <= _MAX_QUERY_CHARS

    # ── F3: Code entity preservation ─────────────────────────────

    def test_preserves_camel_case(self):
        assert _preprocess_query("getUserName implementation") == "getUserName implementation"

    def test_preserves_snake_case(self):
        assert _preprocess_query("get_user_name function") == "get_user_name function"

    def test_preserves_dotted_names(self):
        assert _preprocess_query("os.path.join usage") == "os.path.join usage"

    def test_preserves_file_paths(self):
        assert _preprocess_query("src/utils.py error handler") == "src/utils.py error handler"

    def test_filler_before_code_entity(self):
        assert _preprocess_query("please find getUserName") == "find getUserName"
        assert _preprocess_query("can you show src/utils.py") == "show src/utils.py"

    # ── Edge cases ───────────────────────────────────────────────

    def test_empty_query(self):
        assert _preprocess_query("") == ""

    def test_whitespace_only(self):
        assert _preprocess_query("   ") == ""

    def test_filler_only_no_match(self):
        # "please" alone doesn't match (filler regex requires trailing \s+)
        assert _preprocess_query("please") == "please"

    def test_filler_with_content_after(self):
        # "please " + content → filler stripped, content remains
        assert _preprocess_query("please do something") == "do something"

    def test_none_like_empty(self):
        assert _preprocess_query("  \t\n  ") == ""
