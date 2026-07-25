import shutil
from pathlib import Path
import tempfile
import os

import pytest

from phase8.core.artifact_store import ArtifactStore, ArtifactEntry, ArtifactStoreError


@pytest.fixture
def tmp_root(tmp_path):
    return tmp_path / "artifacts"


def test_write_and_read_artifact(tmp_root):
    store = ArtifactStore(tmp_root)
    entry = store.write_artifact("run1", "a/b.txt", b"hello")
    assert isinstance(entry, ArtifactEntry)
    data = store.read_artifact("run1", "a/b.txt")
    assert data == b"hello"


def test_list_artifacts(tmp_root):
    store = ArtifactStore(tmp_root)
    store.write_artifact("runx", "f.txt", b"1")
    store.write_artifact("runx", "g/h.txt", b"2")
    entries = store.list_artifacts("runx")
    paths = {e.path for e in entries}
    assert any(p.endswith("f.txt") for p in paths)
    assert any(p.endswith("g/h.txt") for p in paths)


def test_read_missing_raises(tmp_root):
    store = ArtifactStore(tmp_root)
    with pytest.raises(ArtifactStoreError):
        store.read_artifact("nope", "x.txt")
