"""
Batch augmenter end-to-end test.

Tests that TraceAugmenter correctly batches files using PROFILE_COMPACT
and produces the expected number of augmented results in a single LLM call.
"""

import json
from pathlib import Path

import pytest

from codrag.core.augmenter import TraceAugmenter
from codrag.core import LLMClient
from codrag.core.batch_profiles import PROFILE_COMPACT


class MockLLMClient:
    def __init__(self):
        self.endpoint_url = "http://localhost:11434"
        self.model = "mock-model"
        self.provider = "mock"
        self.api_key = None
        self.timeout = 60.0
        self.calls = 0

    def generate(self, prompt, system="", num_predict=None, **kwargs):
        self.calls += 1
        items = prompt.count("=== FILE")
        
        results = []
        for i in range(1, items + 1):
            results.append({
                "summary": f"Mock summary for item {i}",
                "role": "core_logic",
                "confidence": 0.95,
                "related_files": [],
                "key_exports": []
            })
            
        return json.dumps({"results": results}), 0


def test_batch_augmenter_compact_profile(tmp_path):
    """10 files with batch size 20 should produce 1 LLM call and 10 augmented results."""
    client = MockLLMClient()
    idx_dir = tmp_path / "index"
    idx_dir.mkdir()

    # Write dummy nodes
    nodes = []
    for i in range(10):
        nodes.append({
            "id": f"file:test_{i}.py",
            "kind": "file",
            "file_path": f"test_{i}.py",
            "language": "python"
        })

    with open(idx_dir / "trace_nodes.jsonl", "w") as f:
        for n in nodes:
            f.write(json.dumps(n) + "\n")

    # Empty edges
    with open(idx_dir / "trace_edges.jsonl", "w") as f:
        pass

    # Write dummy repo files so file_hash works
    for i in range(10):
        (idx_dir / f"test_{i}.py").write_text(f"print('hello {i}')")

    # Run augmenter with compact profile (batch size 20)
    aug = TraceAugmenter(idx_dir, idx_dir, client, batch_profile=PROFILE_COMPACT)
    res = aug.run()

    assert res.augmented == 10, f"Expected 10 augmented, got {res.augmented}"
    # 1 pre-flight test call + 1 batched call = 2 total
    assert client.calls == 2, f"Expected 2 LLM calls (1 pre-flight + 1 batch), got {client.calls}"
