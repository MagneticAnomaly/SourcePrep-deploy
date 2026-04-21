"""Tests for MCP response budget caps (_truncate_section)."""

from prep.mcp.server import MCPServer


class TestTruncateSection:
    """Tests for MCPServer._truncate_section."""

    def test_short_text_unchanged(self):
        text = "Short text"
        result = MCPServer._truncate_section(text, 100, "test")
        assert result == text

    def test_exact_limit_unchanged(self):
        text = "x" * 100
        result = MCPServer._truncate_section(text, 100, "test")
        assert result == text

    def test_long_text_truncated_with_notice(self):
        text = "a" * 5000
        result = MCPServer._truncate_section(text, 3000, "architecture")
        assert len(result) < 5000
        assert "[architecture: truncated to 3000 chars]" in result

    def test_truncation_at_newline_boundary(self):
        # Build text with newlines: lines of 49 chars each (+ newline = 50)
        lines = [f"line {i:03d} " + "x" * 40 for i in range(100)]
        text = "\n".join(lines)
        result = MCPServer._truncate_section(text, 500, "section")
        # Should not end mid-line (before the notice)
        body = result.split("\n\n[section:")[0]
        # The body should end with a complete line from the original
        last_line = body.rsplit("\n", 1)[-1]
        assert last_line in lines

    def test_truncation_no_good_newline_fallback(self):
        # Text with no newlines - should just cut at max_chars
        text = "a" * 5000
        result = MCPServer._truncate_section(text, 3000, "test")
        # No newline in first half, so it falls back to raw truncation at max_chars
        body = result.split("\n\n[test:")[0]
        assert len(body) == 3000

    def test_empty_text_unchanged(self):
        result = MCPServer._truncate_section("", 100, "test")
        assert result == ""

    def test_newline_in_first_half_ignored(self):
        # Newline only in first quarter - should not be used as cut point
        text = "a" * 100 + "\n" + "b" * 900
        result = MCPServer._truncate_section(text, 500, "lbl")
        # The newline at position 100 is < 250 (500//2), so it's ignored
        body = result.split("\n\n[lbl:")[0]
        assert len(body) == 500
