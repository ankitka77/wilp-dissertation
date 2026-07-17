"""Write CSV/JSON/TXT reports and the phase5 manifest."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
from typing import Dict, Any


class ReportGenerator:
    def __init__(self, reports_dir: str | Path = "artifacts/reports/phase5") -> None:
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def save_event_table(self, table: pd.DataFrame) -> Path:
        path = self.reports_dir / "event_statistics.csv"
        table.to_csv(path, index=False)
        return path

    def save_sequence_table(self, table: pd.DataFrame) -> Path:
        path = self.reports_dir / "sequence_statistics.csv"
        table.to_csv(path, index=False)
        return path

    def save_validation_report(self, report: Dict[str, Any]) -> Path:
        path = self.reports_dir / "validation_report.txt"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(report, indent=2))
        return path

    def save_dataset_summary(self, summary: Dict[str, Any]) -> Path:
        path = self.reports_dir / "dataset_summary.json"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
        return path

    def save_manifest(self, manifest: Dict[str, Any]) -> Path:
        path = self.reports_dir / "phase5_manifest.json"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
        return path
