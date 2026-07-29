import os
from pathlib import Path
import tempfile

from phase9.utils.fs import ensure_dir, safe_write_text, safe_read_text
from phase9.utils.checksum import sha256_file
from phase9.utils.timeutils import now_iso


def test_ensure_dir(tmp_path: Path):
    d = tmp_path / "a" / "b"
    p = ensure_dir(d)
    assert p.exists()
    assert p.is_dir()


def test_safe_write_and_read(tmp_path: Path):
    f = tmp_path / "test.txt"
    safe_write_text(f, "hello world")
    content = safe_read_text(f)
    assert content == "hello world"


def test_sha256(tmp_path: Path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"abc")
    digest = sha256_file(f)
    assert len(digest) == 64


def test_now_iso():
    s = now_iso()
    assert s.endswith("+00:00") or s.endswith("Z") or "+" in s
