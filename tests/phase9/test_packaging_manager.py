from pathlib import Path
import json

from phase9.packaging.manager import PackagingManager


def test_packaging_manager_creates_manifest(tmp_path: Path):
    # create some sample files
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("world")

    pm = PackagingManager(tmp_path)
    manifest = pm.package()

    pkg_root = tmp_path / "package"
    assert (pkg_root / "package_manifest.json").exists()
    assert (pkg_root / "package_summary.json").exists()
    assert isinstance(manifest.get("files"), list)
    assert len(manifest.get("files")) >= 2
