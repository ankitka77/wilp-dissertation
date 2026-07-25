import pytest

from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError


def test_write_artifact_exception_path(tmp_path):
    class BrokenArtifactStore(ArtifactStore):
        def _compute_sha256(self, path):
            raise RuntimeError("boom")

    store = BrokenArtifactStore(tmp_path / "broken")
    # calling write_artifact should raise ArtifactStoreError and not crash the test runner
    with pytest.raises(ArtifactStoreError):
        store.write_artifact("r1", "x.txt", b"data")
