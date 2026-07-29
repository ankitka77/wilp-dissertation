from pathlib import Path
import json

from phase9.report_generator.generator import ReportGenerator


def test_report_generator_uses_catalog_and_writes_reports(tmp_path: Path):
    # prepare minimal asset_catalog and summaries
    catalog = {"generated_at": "now", "assets": []}
    (tmp_path / "asset_catalog.json").write_text(json.dumps(catalog))
    (tmp_path / "metadata_summary.json").write_text(json.dumps({"foo": "bar"}))
    (tmp_path / "metrics_summary.json").write_text(json.dumps({"m": 1}))
    (tmp_path / "project_statistics.json").write_text(json.dumps({"count": 0}))

    rg = ReportGenerator(tmp_path)
    outs = rg.generate()

    assert (tmp_path / "reports" / "report.md").exists()
    assert (tmp_path / "reports" / "report.html").exists()
    assert (tmp_path / "reports" / "report.json").exists()
    assert len(outs) == 3
