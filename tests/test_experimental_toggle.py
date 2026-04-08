import pytest
from codrag.services.settings_store import SettingsStore
from pathlib import Path


@pytest.fixture
def store(tmp_path):
    s = SettingsStore()
    s.init(tmp_path / "test_settings.db")
    yield s
    s.close()


def test_experimental_defaults_to_false(store):
    assert store.get_experimental() is False


def test_experimental_can_be_enabled(store):
    store.set("global/experimental", True)
    assert store.get_experimental() is True


def test_experimental_can_be_disabled(store):
    store.set("global/experimental", True)
    store.set("global/experimental", False)
    assert store.get_experimental() is False
