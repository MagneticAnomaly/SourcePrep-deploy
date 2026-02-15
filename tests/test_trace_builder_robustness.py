
import pytest
from pathlib import Path
from codrag.core.trace import TraceBuilder, TraceNode, TraceEdge

class MockAnalyzer:
    def __init__(self, nodes, edges):
        self.nodes = nodes
        self.edges = edges

    def analyze(self):
        return self.nodes, self.edges

def test_trace_builder_robustness(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    
    # Create some dummy files so the builder finds them
    (repo_root / "valid.py").write_text("print('hello')")
    (repo_root / "invalid.py").write_text("print('world')")
    
    builder = TraceBuilder(repo_root, index_dir)
    
    # Override _enumerate_files to return our dummy files
    builder._enumerate_files = lambda: [repo_root / "valid.py", repo_root / "invalid.py"]
    
    # Mock the analyzer to return a mix of valid and invalid graph elements
    # We'll monkeypatch the internal logic or just call _validate/write directly?
    # Better to test the sanitization logic directly by injecting nodes/edges 
    # right before sanitization. Since I can't easily inject into build(), 
    # I'll reproduce the scenario by creating a subclass or just calling the internal methods 
    # if I can.
    
    # Actually, build() calls analyzers. Let's mock the analyzer for .py files.
    # But _detect_language depends on extensions.
    
    valid_node = TraceNode(id="file:valid.py", kind="file", name="valid.py", file_path="valid.py", language="python", span=None)
    # Duplicate node ID
    duplicate_node = TraceNode(id="file:valid.py", kind="file", name="valid.py", file_path="valid.py", language="python", span=None)
    # Invalid path
    invalid_path_node = TraceNode(id="file:bad_path", kind="file", name="bad", file_path="/absolute/path", language="python", span=None)
    
    # Valid edge
    valid_edge = TraceEdge(id="edge:1", kind="import", source="file:valid.py", target="file:valid.py")
    # Duplicate edge ID
    duplicate_edge = TraceEdge(id="edge:1", kind="import", source="file:valid.py", target="file:valid.py")
    # Invalid source
    invalid_source_edge = TraceEdge(id="edge:2", kind="import", source="file:missing", target="file:valid.py")
    # Invalid target
    invalid_target_edge = TraceEdge(id="edge:3", kind="import", source="file:valid.py", target="file:missing")
    
    # We need to inject these into the build process.
    # Since build() collects nodes from analyzers, we can mock PythonAnalyzer.
    
    with pytest.MonkeyPatch.context() as m:
        def mock_analyze(self):
            # Return different sets for different files to cover all cases
            if str(self.file_path).endswith("valid.py"):
                return [valid_node, duplicate_node, invalid_path_node], [valid_edge, duplicate_edge]
            else:
                return [], [invalid_source_edge, invalid_target_edge]
                
        m.setattr("codrag.core.trace.PythonAnalyzer.analyze", mock_analyze)
        
        # Run build
        manifest = builder.build()
        
        # Verify manifest success
        # Nodes: file:valid.py (1) + file:invalid.py (1) = 2. 
        # The analyzer's duplicate valid.py node and invalid path node are dropped.
        assert manifest["counts"]["nodes"] == 2 
        
        # Edges: valid_edge (1).
        # duplicate_edge dropped.
        # invalid_source_edge dropped (source missing).
        # invalid_target_edge dropped (target missing).
        assert manifest["counts"]["edges"] == 1
        
        assert manifest["last_error"] is None
        
        # Verify files exist
        assert (index_dir / "trace_nodes.jsonl").exists()
        assert (index_dir / "trace_edges.jsonl").exists()
        assert (index_dir / "trace_manifest.json").exists()
