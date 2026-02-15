
import os
import shutil
import tempfile
from pathlib import Path
from codrag.core.trace import TraceBuilder

def test_trace_builder_includes_all_languages():
    """Verify that TraceBuilder includes all supported language extensions by default."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        index_dir = repo_root / ".codrag"
        
        # Create dummy files for various languages
        files_to_create = [
            "app.swift",
            "main.go",
            "lib.rs",
            "Service.java",
            "utils.cpp",
            "header.h",
            "script.py",
            "frontend.tsx",
            "logic.js",
            "ignored.txt", # Should be ignored
        ]
        
        for fname in files_to_create:
            (repo_root / fname).touch()
            
        # Initialize TraceBuilder with defaults (which should now include all these globs)
        builder = TraceBuilder(
            repo_root=repo_root,
            index_dir=index_dir,
            include_globs=None, # Should use new defaults
        )
        
        # Enumerate files
        found_files = builder._enumerate_files()
        found_names = {f.name for f in found_files}
        
        # Assertions
        expected_extensions = {
            "app.swift", "main.go", "lib.rs", "Service.java", 
            "utils.cpp", "header.h", "script.py", "frontend.tsx", "logic.js"
        }
        
        for name in expected_extensions:
            assert name in found_names, f"{name} should be included"
            
        assert "ignored.txt" not in found_names, "txt files should not be included by default"

def test_trace_builder_swift_analysis_smoke():
    """Smoke test for Swift analyzer integration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        index_dir = repo_root / ".codrag"
        
        swift_file = repo_root / "test.swift"
        swift_code = """
        import Foundation
        
        class MyManager {
            func doSomething() {
                print("doing")
            }
        }
        """
        swift_file.write_text(swift_code, encoding="utf-8")
        
        builder = TraceBuilder(repo_root=repo_root, index_dir=index_dir)
        
        # Build trace
        manifest = builder.build()
        
        # Verify nodes were created
        assert manifest["counts"]["nodes"] > 0
        assert manifest["counts"]["edges"] > 0
        
        # Check trace_nodes.jsonl content
        nodes_path = index_dir / "trace_nodes.jsonl"
        assert nodes_path.exists()
        
        has_class = False
        has_func = False
        
        with open(nodes_path, "r") as f:
            for line in f:
                node = import_json_line(line)
                if node["name"] == "MyManager" and node["kind"] == "symbol":
                    has_class = True
                if node["name"] == "doSomething" and node["kind"] == "symbol":
                    has_func = True
                    
        assert has_class, "Should have detected Swift class"
        assert has_func, "Should have detected Swift function"

def import_json_line(line):
    import json
    return json.loads(line)
