from pathlib import Path
import json

from phase9.packaging.manager import PackagingManager


def test_package_manifest_fields(tmp_path: Path):
    (tmp_path / "file1.txt").write_text("x")
    pm = PackagingManager(tmp_path)
    manifest = pm.package()
    assert "package_version" in manifest
    assert "generator_version" in manifest
    assert "files" in manifest
