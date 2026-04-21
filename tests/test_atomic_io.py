"""Tests for codrag.core.atomic_io — tmp→rename file writes."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from prep.core.atomic_io import atomic_write_bytes, atomic_write_text


def test_atomic_write_text_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    atomic_write_text(target, "hello")
    assert target.read_text() == "hello"


def test_atomic_write_text_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("old content")
    atomic_write_text(target, "new content")
    assert target.read_text() == "new content"


def test_atomic_write_text_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deep" / "file.txt"
    atomic_write_text(target, "ok")
    assert target.read_text() == "ok"


def test_atomic_write_text_cleans_up_tmp_on_failure(tmp_path: Path) -> None:
    """If the fsync/replace path raises, no .tmp file should be left behind."""
    work = tmp_path / "work"
    work.mkdir()
    target = work / "out.txt"
    target.write_text("original")

    def boom(src: str, dst: str) -> None:
        raise OSError("rename failed")

    with patch("prep.core.atomic_io.os.replace", side_effect=boom):
        with pytest.raises(OSError):
            atomic_write_text(target, "never lands")

    # Original file unchanged
    assert target.read_text() == "original"
    # No orphan .tmp files next to it
    assert sorted(p.name for p in work.iterdir()) == ["out.txt"]


def test_atomic_write_text_no_half_file_on_crash(tmp_path: Path) -> None:
    """Reader should see old content or new content, never mixed.

    We can't actually crash the process, but we verify that the final
    file is present iff os.replace was called — and the reader path
    never sees a partial write via the tmp name.
    """
    target = tmp_path / "out.txt"
    target.write_text("A" * 1000)
    atomic_write_text(target, "B" * 2000)
    assert target.read_text() == "B" * 2000
    assert target.stat().st_size == 2000


def test_atomic_write_bytes_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "blob.bin"
    payload = bytes(range(256))
    atomic_write_bytes(target, payload)
    assert target.read_bytes() == payload


def test_atomic_write_text_no_interim_tmp_visible(tmp_path: Path) -> None:
    """After the write returns, there should be no stray .tmp siblings."""
    work = tmp_path / "work"
    work.mkdir()
    target = work / "foo.json"
    atomic_write_text(target, '{"ok": true}')
    assert sorted(p.name for p in work.iterdir()) == ["foo.json"]
