"""Tests for IO operations: fingerprint, backup, atomic write."""

from pathlib import Path

from xl.io.fileops import atomic_write, backup, fingerprint


def test_fingerprint(simple_workbook: Path):
    fp = fingerprint(simple_workbook)
    assert fp.startswith("sha256:")
    assert len(fp) == 71  # sha256: + 64 hex chars

    # Same file -> same fingerprint
    fp2 = fingerprint(simple_workbook)
    assert fp == fp2


def test_backup(simple_workbook: Path):
    bak_path = backup(simple_workbook)
    assert Path(bak_path).exists()
    assert ".bak" in bak_path
    # Backup should have same content
    assert Path(bak_path).stat().st_size == simple_workbook.stat().st_size


def test_atomic_write(tmp_path: Path):
    target = tmp_path / "output.xlsx"
    data = b"test data content"
    atomic_write(target, data)
    assert target.exists()
    assert target.read_bytes() == data


def test_atomic_write_overwrites(tmp_path: Path):
    target = tmp_path / "output.xlsx"
    target.write_bytes(b"old content")
    atomic_write(target, b"new content")
    assert target.read_bytes() == b"new content"
