"""Tests for Custodian archive manifest persistence."""
import json
from pathlib import Path
import pytest
from codrag.agents.custodian.manifest import ArchiveManifest, ManifestEntry

@pytest.fixture
def manifest(tmp_path: Path) -> ArchiveManifest:
    return ArchiveManifest(tmp_path)

def _sample_entry() -> ManifestEntry:
    return ManifestEntry(
        entry_id="archive-001", original_paths=["src/old/a.py", "src/old/b.py"],
        archive_path="archived/old_module/", reason="Dead code — 0 dependents",
        finding_id="ARCH-17", dependent_count=0)

class TestArchiveManifest:
    def test_add_and_get_entry(self, manifest: ArchiveManifest) -> None:
        entry = _sample_entry()
        manifest.add_entry(entry)
        loaded = manifest.get_entry("archive-001")
        assert loaded is not None
        assert loaded.original_paths == ["src/old/a.py", "src/old/b.py"]
        assert loaded.reason == "Dead code — 0 dependents"

    def test_list_entries(self, manifest: ArchiveManifest) -> None:
        manifest.add_entry(_sample_entry())
        e2 = ManifestEntry(entry_id="archive-002", original_paths=["c.py"],
            archive_path="archived/c/", reason="Orphaned", finding_id="ARCH-22", dependent_count=0)
        manifest.add_entry(e2)
        assert len(manifest.list_entries()) == 2

    def test_empty_manifest(self, manifest: ArchiveManifest) -> None:
        assert manifest.list_entries() == []
        assert manifest.get_entry("x") is None

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        m1 = ArchiveManifest(tmp_path)
        m1.add_entry(_sample_entry())
        m2 = ArchiveManifest(tmp_path)
        assert m2.get_entry("archive-001") is not None

    def test_manifest_file_is_valid_json(self, manifest: ArchiveManifest, tmp_path: Path) -> None:
        manifest.add_entry(_sample_entry())
        data = json.loads((tmp_path / ".custodian_manifest.json").read_text())
        assert "version" in data
        assert "entries" in data

    def test_entry_has_timestamp(self, manifest: ArchiveManifest) -> None:
        manifest.add_entry(_sample_entry())
        entry = manifest.get_entry("archive-001")
        assert entry is not None
        assert entry.archived_at
