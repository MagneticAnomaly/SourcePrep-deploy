
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
    """Smoke test for Swift analyzer integration (Python engine)."""
    import codrag.core as _core
    original_engine = _core.ENGINE

    try:
        # Force Python engine since Rust engine doesn't have a Swift parser yet
        _core.ENGINE = "python"
        import codrag.core.trace as _trace_mod
        _trace_mod._ENGINE = "python"

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
    finally:
        _core.ENGINE = original_engine
        _trace_mod._ENGINE = original_engine

def test_trace_builder_includes_new_languages():
    """Verify that TraceBuilder includes all newly added language extensions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        index_dir = repo_root / ".codrag"

        new_lang_files = [
            "Main.kt",
            "Program.cs",
            "app.rb",
            "index.php",
            "main.dart",
            "App.scala",
            "deploy.sh",
            "init.lua",
            "main.zig",
            "server.ex",
        ]

        for fname in new_lang_files:
            (repo_root / fname).touch()

        builder = TraceBuilder(repo_root=repo_root, index_dir=index_dir)
        found_files = builder._enumerate_files()
        found_names = {f.name for f in found_files}

        for name in new_lang_files:
            assert name in found_names, f"{name} should be included in trace"


def test_generic_regex_analyzer_kotlin():
    """Test GenericRegexAnalyzer extracts Kotlin symbols and imports."""
    import codrag.core as _core
    original_engine = _core.ENGINE
    try:
        _core.ENGINE = "python"
        import codrag.core.trace as _trace_mod
        _trace_mod._ENGINE = "python"

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            index_dir = repo_root / ".codrag"

            kt_file = repo_root / "Main.kt"
            kt_file.write_text("""
import kotlin.math.sqrt
import java.util.Collections

data class User(val name: String, val age: Int)

fun greet(user: User): String {
    return "Hello, ${user.name}"
}

object AppConfig {
    val version = "1.0"
}
""")
            builder = TraceBuilder(repo_root=repo_root, index_dir=index_dir)
            manifest = builder.build()

            assert manifest["counts"]["nodes"] > 1  # file + symbols
            assert manifest["counts"]["edges"] > 0  # contains + imports

            nodes_path = index_dir / "trace_nodes.jsonl"
            nodes = [import_json_line(l) for l in nodes_path.read_text().strip().split("\n")]

            symbol_names = {n["name"] for n in nodes if n["kind"] == "symbol"}
            assert "User" in symbol_names, "Should detect Kotlin data class"
            assert "greet" in symbol_names, "Should detect Kotlin function"
            assert "AppConfig" in symbol_names, "Should detect Kotlin object"
    finally:
        _core.ENGINE = original_engine
        _trace_mod._ENGINE = original_engine


def test_generic_regex_analyzer_csharp():
    """Test GenericRegexAnalyzer extracts C# symbols and imports."""
    import codrag.core as _core
    original_engine = _core.ENGINE
    try:
        _core.ENGINE = "python"
        import codrag.core.trace as _trace_mod
        _trace_mod._ENGINE = "python"

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            index_dir = repo_root / ".codrag"

            cs_file = repo_root / "Program.cs"
            cs_file.write_text("""
using System;
using System.Collections.Generic;

namespace MyApp
{
    public class UserService
    {
        public void CreateUser(string name)
        {
            Console.WriteLine(name);
        }
    }

    public interface IRepository
    {
        void Save();
    }
}
""")
            builder = TraceBuilder(repo_root=repo_root, index_dir=index_dir)
            manifest = builder.build()

            nodes_path = index_dir / "trace_nodes.jsonl"
            nodes = [import_json_line(l) for l in nodes_path.read_text().strip().split("\n")]

            symbol_names = {n["name"] for n in nodes if n["kind"] == "symbol"}
            assert "UserService" in symbol_names, "Should detect C# class"
            assert "IRepository" in symbol_names, "Should detect C# interface"
    finally:
        _core.ENGINE = original_engine
        _trace_mod._ENGINE = original_engine


def test_generic_regex_analyzer_ruby():
    """Test GenericRegexAnalyzer extracts Ruby symbols and imports."""
    import codrag.core as _core
    original_engine = _core.ENGINE
    try:
        _core.ENGINE = "python"
        import codrag.core.trace as _trace_mod
        _trace_mod._ENGINE = "python"

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            index_dir = repo_root / ".codrag"

            rb_file = repo_root / "app.rb"
            rb_file.write_text("""
require 'json'
require_relative 'helpers'

class UserController
  def index
    @users = User.all
  end

  def show
    @user = User.find(params[:id])
  end
end

module Authentication
  def authenticate!
    raise "Unauthorized" unless current_user
  end
end
""")
            builder = TraceBuilder(repo_root=repo_root, index_dir=index_dir)
            manifest = builder.build()

            nodes_path = index_dir / "trace_nodes.jsonl"
            nodes = [import_json_line(l) for l in nodes_path.read_text().strip().split("\n")]

            symbol_names = {n["name"] for n in nodes if n["kind"] == "symbol"}
            assert "UserController" in symbol_names, "Should detect Ruby class"
            assert "Authentication" in symbol_names, "Should detect Ruby module"
            assert "index" in symbol_names, "Should detect Ruby method"
    finally:
        _core.ENGINE = original_engine
        _trace_mod._ENGINE = original_engine


def test_detect_language_new_extensions():
    """Test _detect_language for all newly supported extensions."""
    from codrag.core.trace import _detect_language

    cases = {
        "Main.kt": "kotlin",
        "build.kts": "kotlin",
        "Program.cs": "csharp",
        "app.rb": "ruby",
        "index.php": "php",
        "main.dart": "dart",
        "App.scala": "scala",
        "util.sc": "scala",
        "deploy.sh": "shell",
        "init.bash": "shell",
        "config.zsh": "shell",
        "init.lua": "lua",
        "main.zig": "zig",
        "server.ex": "elixir",
        "test_helper.exs": "elixir",
    }

    for filename, expected_lang in cases.items():
        detected = _detect_language(filename)
        assert detected == expected_lang, f"{filename}: expected {expected_lang}, got {detected}"


def import_json_line(line):
    import json
    return json.loads(line)
