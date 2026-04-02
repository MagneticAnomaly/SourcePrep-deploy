"""Tests for Custodian prompt template rendering."""
from codrag.agents.custodian.prompts import render_safety_verification_prompt, render_archive_readme

class TestSafetyVerificationPrompt:
    def test_includes_file_path(self) -> None:
        result = render_safety_verification_prompt(
            file_path="src/legacy/old_parser.py", file_contents="def parse(): pass",
            dependent_count=0, import_list=["os", "json"], module_name="legacy", domain_tags=["deprecated"])
        assert "src/legacy/old_parser.py" in result

    def test_includes_file_contents(self) -> None:
        result = render_safety_verification_prompt(
            file_path="a.py", file_contents="class OldHandler:\n    pass",
            dependent_count=0, import_list=[], module_name="core", domain_tags=[])
        assert "class OldHandler" in result

    def test_includes_dependent_count(self) -> None:
        result = render_safety_verification_prompt(
            file_path="a.py", file_contents="x = 1", dependent_count=3,
            import_list=[], module_name="", domain_tags=[])
        assert "3" in result

    def test_asks_safety_questions(self) -> None:
        result = render_safety_verification_prompt(
            file_path="a.py", file_contents="", dependent_count=0,
            import_list=[], module_name="", domain_tags=[])
        assert "dynamic" in result.lower() or "importlib" in result.lower()
        assert "SAFE_TO_DELETE" in result
        assert "NEEDS_REVIEW" in result

class TestArchiveReadme:
    def test_includes_file_paths(self) -> None:
        result = render_archive_readme(
            original_paths=["src/old/a.py", "src/old/b.py"],
            reason="Dead code — 0 dependents", finding_id="ARCH-17", archived_at="2026-04-01T14:30:00Z")
        assert "src/old/a.py" in result
        assert "src/old/b.py" in result

    def test_includes_reason(self) -> None:
        result = render_archive_readme(
            original_paths=["a.py"], reason="Module replaced by v2",
            finding_id="QUAL-5", archived_at="2026-04-01")
        assert "Module replaced by v2" in result
        assert "QUAL-5" in result
