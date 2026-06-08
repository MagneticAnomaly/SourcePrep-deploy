"""Tests for the _deep_merge utility in server.py."""

import sys
from pathlib import Path

# Ensure src/ is on the path so we can import the function directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from prep.services.config_manager import deep_merge as _deep_merge


class TestDeepMerge:
    """Unit tests for _deep_merge(base, update) -> base (mutated)."""

    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        _deep_merge(base, {"b": 3, "c": 4})
        assert base == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge_preserves_sibling_keys(self):
        """The critical bug this function was written to fix:
        a partial update to a nested dict must NOT wipe sibling keys."""
        base = {
            "llm_config": {
                "saved_endpoints": [{"id": "ep1", "url": "http://localhost"}],
                "nested": {"enabled": False},
            }
        }
        update = {
            "llm_config": {
                "nested": {"enabled": True, "url": "http://nested:8765"},
            }
        }
        _deep_merge(base, update)
        # saved_endpoints must survive
        assert base["llm_config"]["saved_endpoints"] == [{"id": "ep1", "url": "http://localhost"}]
        # nested must be updated
        assert base["llm_config"]["nested"] == {"enabled": True, "url": "http://nested:8765"}

    def test_deeply_nested(self):
        base = {"a": {"b": {"c": 1, "d": 2}}}
        _deep_merge(base, {"a": {"b": {"c": 99}}})
        assert base == {"a": {"b": {"c": 99, "d": 2}}}

    def test_new_nested_key(self):
        base = {"a": 1}
        _deep_merge(base, {"b": {"c": 3}})
        assert base == {"a": 1, "b": {"c": 3}}

    def test_overwrite_scalar_with_dict(self):
        base = {"a": 1}
        _deep_merge(base, {"a": {"nested": True}})
        assert base == {"a": {"nested": True}}

    def test_overwrite_dict_with_scalar(self):
        base = {"a": {"nested": True}}
        _deep_merge(base, {"a": 42})
        assert base == {"a": 42}

    def test_empty_update(self):
        base = {"a": 1}
        _deep_merge(base, {})
        assert base == {"a": 1}

    def test_empty_base(self):
        base = {}
        _deep_merge(base, {"a": 1, "b": {"c": 2}})
        assert base == {"a": 1, "b": {"c": 2}}

    def test_both_empty(self):
        base = {}
        result = _deep_merge(base, {})
        assert result == {}

    def test_returns_base(self):
        base = {"x": 1}
        result = _deep_merge(base, {"y": 2})
        assert result is base

    def test_list_values_replaced_not_merged(self):
        """Lists are not recursively merged — they are replaced wholesale."""
        base = {"items": [1, 2, 3]}
        _deep_merge(base, {"items": [4, 5]})
        assert base["items"] == [4, 5]

    def test_none_values(self):
        base = {"a": 1, "b": None}
        _deep_merge(base, {"a": None, "c": 3})
        assert base == {"a": None, "b": None, "c": 3}

    def test_realistic_ui_config_partial_update(self):
        """Simulate the actual dashboard config save pattern."""
        base = {
            "repo_root": "/projects/myapp",
            "core_roots": ["src", "docs"],
            "llm_config": {
                "saved_endpoints": [
                    {"id": "ep-1", "provider": "ollama", "url": "http://localhost:11434"},
                ],
                "model_slots": {
                    "embedding": {"endpoint_id": "ep-1", "model": "nomic-embed-text"},
                    "small": {"endpoint_id": "ep-1", "model": "codellama:7b"},
                },
                "nested": {"enabled": False},
            },
        }
        # Dashboard sends only the changed slot
        update = {
            "llm_config": {
                "model_slots": {
                    "small": {"endpoint_id": "ep-1", "model": "deepseek-coder:6.7b"},
                },
            },
        }
        _deep_merge(base, update)
        # Unchanged fields preserved
        assert base["repo_root"] == "/projects/myapp"
        assert base["core_roots"] == ["src", "docs"]
        assert len(base["llm_config"]["saved_endpoints"]) == 1
        assert base["llm_config"]["nested"] == {"enabled": False}
        # Embedding slot preserved
        assert base["llm_config"]["model_slots"]["embedding"]["model"] == "nomic-embed-text"
        # Small slot updated
        assert base["llm_config"]["model_slots"]["small"]["model"] == "deepseek-coder:6.7b"
