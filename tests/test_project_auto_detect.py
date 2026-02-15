
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# We need to mock codrag.server imports before importing projects router
sys_modules_mock = MagicMock()
with patch.dict("sys.modules", {"codrag.server": sys_modules_mock}):
    from codrag.api.routers.projects import _scan_for_presets, _STACK_PRESETS, add_project, AddProjectRequest

def test_scan_for_presets():
    """Verify that _scan_for_presets detects the correct stacks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Create some files
        (root / "main.go").touch()
        (root / "App.swift").touch()
        (root / "script.py").touch()
        (root / "README.md").touch()
        
        # Create a deep file that should also be found (depth check)
        (root / "src").mkdir()
        (root / "src" / "utils.rs").touch()
        
        # Create an ignored dir
        (root / "node_modules").mkdir()
        (root / "node_modules" / "ignore.js").touch() # Should NOT trigger Web preset
        
        presets = _scan_for_presets(root)
        
        assert "Go" in presets
        assert "iOS (Swift/ObjC)" in presets
        assert "Python" in presets
        assert "Documentation" in presets
        assert "Rust" in presets
        assert "Web (JS/TS)" not in presets

def test_add_project_populates_globs():
    """Verify that add_project populates include_globs based on detected stack."""
    
    # Mock dependencies
    mock_registry = MagicMock()
    mock_registry.list_projects.return_value = [] # No existing projects
    
    mock_server = MagicMock()
    mock_server._get_registry.return_value = mock_registry
    mock_server._DEFAULT_UI_CONFIG = {"include_globs": [], "exclude_globs": []}
    mock_server._project_to_dict.side_effect = lambda p: {"id": p.id, "config": p.config}
    
    # Patch the lazy import in projects.py
    with patch("codrag.api.routers.projects._srv", return_value=mock_server), \
         patch("codrag.core.feature_gate.get_license") as mock_license, \
         patch("codrag.core.feature_gate.get_feature_limit", return_value=10):
        
        mock_license.return_value.tier = 1 # Starter
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "main.swift").touch()
            
            req = AddProjectRequest(path=str(root), name="TestProj", mode="standalone")
            
            # The add_project function will call registry.add_project
            # We want to capture the config passed to it
            def capture_add_project(path, name, mode, config):
                # Create a dummy project object to return
                p = MagicMock()
                p.id = "test-id"
                p.path = path
                p.name = name
                p.mode = mode
                p.config = config
                return p
            
            mock_registry.add_project.side_effect = capture_add_project
            
            result = add_project(req)
            
            # Check the config in the result
            config = result["project"]["config"]
            include_globs = config["include_globs"]
            
            # Check that Swift globs were added
            assert "**/*.swift" in include_globs
            # Check defaults
            assert config["trace"]["enabled"] is True
