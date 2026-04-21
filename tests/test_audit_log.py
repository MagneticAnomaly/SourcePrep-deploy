"""
Tests for the enterprise audit log (EA-H1, EA-H2).

Covers:
- Recording events
- Querying with filters (event_type, severity, time range, project_id)
- Pagination (limit, offset)
- Count
- Purge (data retention)
- Thread safety
- Auto-initialization
"""

import tempfile
import time
from pathlib import Path

import pytest

from prep.core.audit_log import AuditLog, AuditEntry


@pytest.fixture
def log():
    """Create a fresh audit log with a temp database."""
    with tempfile.TemporaryDirectory() as tmp:
        al = AuditLog()
        al.init(Path(tmp) / "test_audit.db")
        yield al


class TestRecord:
    def test_record_returns_id(self, log):
        entry_id = log.record("llm_api_call", "Called gemini-2.5-flash", provider="google", tokens=1500)
        assert entry_id > 0

    def test_record_increments_id(self, log):
        id1 = log.record("llm_api_call", "Call 1")
        id2 = log.record("llm_api_call", "Call 2")
        assert id2 > id1

    def test_record_default_severity(self, log):
        log.record("policy_violation_blocked", "Blocked openai")
        entries = log.query(event_type="policy_violation_blocked")
        assert len(entries) == 1
        assert entries[0].severity == "WARNING"

    def test_record_override_severity(self, log):
        log.record("llm_api_call", "Test", severity="CRITICAL")
        entries = log.query()
        assert entries[0].severity == "CRITICAL"

    def test_record_with_project_id(self, log):
        log.record("index_downloaded", "Downloaded index", project_id="proj-123")
        entries = log.query(project_id="proj-123")
        assert len(entries) == 1
        assert entries[0].project_id == "proj-123"

    def test_record_with_details(self, log):
        log.record("dlp_file_blocked", "Blocked .env", file_path=".env", pattern="**/.env*")
        entries = log.query()
        assert entries[0].details["file_path"] == ".env"
        assert entries[0].details["pattern"] == "**/.env*"

    def test_record_unknown_event_type_defaults_to_info(self, log):
        log.record("custom_event", "Something happened")
        entries = log.query()
        assert entries[0].severity == "INFO"


class TestQuery:
    def test_query_empty_log(self, log):
        entries = log.query()
        assert entries == []

    def test_query_returns_newest_first(self, log):
        log.record("llm_api_call", "First")
        time.sleep(0.01)
        log.record("llm_api_call", "Second")
        entries = log.query()
        assert entries[0].message == "Second"
        assert entries[1].message == "First"

    def test_query_by_event_type(self, log):
        log.record("llm_api_call", "LLM call")
        log.record("policy_violation_blocked", "Policy block")
        log.record("llm_api_call", "Another LLM call")
        entries = log.query(event_type="llm_api_call")
        assert len(entries) == 2
        assert all(e.event_type == "llm_api_call" for e in entries)

    def test_query_by_severity(self, log):
        log.record("llm_api_call", "Info event")
        log.record("policy_violation_blocked", "Warning event")
        log.record("secrets_in_config", "Critical event")
        entries = log.query(severity="WARNING")
        assert len(entries) == 1
        assert entries[0].event_type == "policy_violation_blocked"

    def test_query_by_time_range(self, log):
        t1 = time.time()
        log.record("llm_api_call", "In range")
        time.sleep(0.02)
        t2 = time.time()
        time.sleep(0.02)
        log.record("llm_api_call", "After range")

        entries = log.query(since=t1, until=t2)
        assert len(entries) == 1
        assert entries[0].message == "In range"

    def test_query_limit(self, log):
        for i in range(10):
            log.record("llm_api_call", f"Call {i}")
        entries = log.query(limit=3)
        assert len(entries) == 3

    def test_query_offset(self, log):
        for i in range(5):
            log.record("llm_api_call", f"Call {i}")
        all_entries = log.query(limit=100)
        offset_entries = log.query(limit=100, offset=2)
        assert len(offset_entries) == 3
        assert offset_entries[0].id == all_entries[2].id


class TestCount:
    def test_count_empty(self, log):
        assert log.count() == 0

    def test_count_all(self, log):
        log.record("llm_api_call", "1")
        log.record("llm_api_call", "2")
        log.record("policy_violation_blocked", "3")
        assert log.count() == 3

    def test_count_by_event_type(self, log):
        log.record("llm_api_call", "1")
        log.record("llm_api_call", "2")
        log.record("policy_violation_blocked", "3")
        assert log.count(event_type="llm_api_call") == 2

    def test_count_by_severity(self, log):
        log.record("llm_api_call", "Info")
        log.record("secrets_in_config", "Critical")
        assert log.count(severity="CRITICAL") == 1


class TestPurge:
    def test_purge_removes_old_entries(self, log):
        log.record("llm_api_call", "Old event")
        time.sleep(0.02)
        cutoff = time.time()
        time.sleep(0.02)
        log.record("llm_api_call", "New event")

        deleted = log.purge_before(cutoff)
        assert deleted == 1
        remaining = log.query()
        assert len(remaining) == 1
        assert remaining[0].message == "New event"

    def test_purge_empty_log(self, log):
        deleted = log.purge_before(time.time())
        assert deleted == 0


class TestAuditEntry:
    def test_to_dict(self):
        entry = AuditEntry(
            id=1,
            timestamp=1000000.0,
            event_type="llm_api_call",
            severity="INFO",
            message="Test call",
            details={"provider": "google", "tokens": 100},
            project_id="proj-1",
            user="alice",
        )
        d = entry.to_dict()
        assert d["id"] == 1
        assert d["event_type"] == "llm_api_call"
        assert d["details"]["provider"] == "google"
        assert d["project_id"] == "proj-1"
        assert d["user"] == "alice"


class TestAutoInit:
    def test_record_without_explicit_init(self):
        """Audit log should auto-initialize on first record."""
        al = AuditLog()
        with tempfile.TemporaryDirectory() as tmp:
            # Manually set path to temp dir to avoid polluting home dir
            al.init(Path(tmp) / "auto_init_test.db")
            entry_id = al.record("llm_api_call", "Auto-init test")
            assert entry_id > 0
            entries = al.query()
            assert len(entries) == 1
