"""Unit tests for `_detect_prep_command` resolution order.

Regression context: before this fix the function hardcoded ``return "prep"``,
which produced MCP configs that failed in spawn contexts (Claude Desktop,
Cursor) because GUI apps on macOS do not inherit shell PATH and venv
binaries are not on the default GUI PATH.
"""
from __future__ import annotations

import sys

import prep.mcp_config as mcp_config


def test_detect_prefers_shutil_which(monkeypatch, tmp_path):
    fake = tmp_path / "fake_prep"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)

    monkeypatch.setattr(mcp_config.shutil, "which", lambda name: str(fake) if name == "prep" else None)
    assert mcp_config._detect_prep_command() == str(fake)


def test_detect_falls_back_to_venv_sibling(monkeypatch, tmp_path):
    fake_venv = tmp_path / "venv" / "bin"
    fake_venv.mkdir(parents=True)
    fake_python = fake_venv / "python"
    fake_python.write_text("#!/bin/sh\n")
    fake_python.chmod(0o755)
    fake_prep = fake_venv / "prep"
    fake_prep.write_text("#!/bin/sh\n")
    fake_prep.chmod(0o755)

    monkeypatch.setattr(mcp_config.shutil, "which", lambda name: None)
    monkeypatch.setattr(mcp_config.sys, "executable", str(fake_python))
    assert mcp_config._detect_prep_command() == str(fake_prep)


def test_detect_falls_back_to_bare_name(monkeypatch, tmp_path):
    # Point sys.executable somewhere with no sibling 'prep' so the venv
    # detection cannot succeed either.
    empty = tmp_path / "empty" / "bin"
    empty.mkdir(parents=True)
    fake_python = empty / "python"
    fake_python.write_text("#!/bin/sh\n")
    fake_python.chmod(0o755)

    monkeypatch.setattr(mcp_config.shutil, "which", lambda name: None)
    monkeypatch.setattr(mcp_config.sys, "executable", str(fake_python))
    assert mcp_config._detect_prep_command() == "prep"
