"""Regression test for surrogate character handling in KnowledgeIndex.

The Click Python repo exposed a crash where surrogate codepoints (U+D800..U+DFFF)
leaked from the Rust trace engine into trace_augmented.jsonl.  The knowledge
embedding stage crashed on `content.encode('utf-8')` because surrogates are
invalid in UTF-8.

Fix: _sanitize_text() strips surrogates before hashing/embedding/serialization.
"""

from prep.core.knowledge import KnowledgeIndex


class TestSurrogateHandling:
    """Verify surrogate characters don't crash the knowledge pipeline."""

    def test_sanitize_text_strips_surrogates(self):
        """Surrogate codepoints should be replaced with U+FFFD."""
        text_with_surrogate = "hello \udcff world"
        result = KnowledgeIndex._sanitize_text(text_with_surrogate)
        assert "\udcff" not in result
        assert "hello" in result
        assert "world" in result
        # Should be valid UTF-8 now
        result.encode("utf-8")  # must not raise

    def test_sanitize_text_preserves_normal_text(self):
        """Normal text should pass through unchanged."""
        text = "def hello():\n    return 42"
        assert KnowledgeIndex._sanitize_text(text) == text

    def test_sanitize_text_preserves_unicode(self):
        """Valid non-ASCII unicode should be preserved."""
        text = "café résumé naïve 日本語"
        assert KnowledgeIndex._sanitize_text(text) == text

    def test_content_hash_with_surrogates(self):
        """_content_hash must not crash on surrogate characters."""
        text_with_surrogate = "some content \udcff here"
        # Must not raise UnicodeEncodeError
        h = KnowledgeIndex._content_hash(text_with_surrogate)
        assert isinstance(h, str)
        assert len(h) == 16  # sha256 hex[:16]

    def test_content_hash_deterministic(self):
        """Same input (after sanitization) should produce same hash."""
        text = "hello \udcff world"
        h1 = KnowledgeIndex._content_hash(text)
        h2 = KnowledgeIndex._content_hash(text)
        assert h1 == h2
