import sys
import types
from pathlib import Path
import json

# Mock fastapi before importing codrag
fastapi = types.ModuleType("fastapi")
fastapi.FastAPI = type("FastAPI", (), {})
fastapi.HTTPException = type("HTTPException", (Exception,), {})
fastapi.Request = type("Request", (), {})
fastapi.APIRouter = type("APIRouter", (), {})
sys.modules["fastapi"] = fastapi

# Also mock pydantic since it might be missing
pydantic = types.ModuleType("pydantic")
pydantic.BaseModel = type("BaseModel", (), {})
pydantic.Field = lambda *args, **kwargs: None
sys.modules["pydantic"] = pydantic

sys.path.insert(0, str(Path("/Volumes/4TB-BAD/HumanAI/CoDRAG/src").resolve()))

from codrag.core.augmenter import TraceAugmenter
from codrag.core import LLMClient
from codrag.core.batch_profiles import PROFILE_COMPACT

class MockLLMClient:
    def __init__(self):
        self.model = "mock-model"
        self.provider = "mock"
        self.calls = 0

    def generate(self, prompt, system="", num_predict=None):
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

def test():
    print("Testing batch augmenter...")
    client = MockLLMClient()
    
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        idx_dir = Path(td)
        
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
            
        # Write a dummy repo file so file_hash works
        for i in range(10):
            with open(idx_dir / f"test_{i}.py", "w") as f:
                f.write(f"print('hello {i}')")
                
        # Run augmenter with compact profile (batch size 20)
        aug = TraceAugmenter(idx_dir, idx_dir, client, batch_profile=PROFILE_COMPACT)
        res = aug.run()
        
        print(f"Augment result: {res.augmented} augmented, {res.failed} failed, {res.synthetic} synthetic")
        print(f"LLM calls made: {client.calls} (expected 1 for 10 items since batch size is 20)")
        
        assert res.augmented == 10, f"Expected 10 augmented, got {res.augmented}"
        assert client.calls == 1, f"Expected 1 call, got {client.calls}"
        
test()
