from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
import logging
import json
import csv

from phase9.manifest.models import ArtifactRecord
from phase9.utils.checksum import sha256_file
from phase9.exceptions import ValidationError


logger = logging.getLogger(__name__)


SEVERITY = ("INFO", "WARNING", "ERROR", "FATAL")


class ArtifactValidator:
    """Validate resolved artifacts according to Phase 9 rules.

    Produces a validation report with per-artifact findings and an overall summary.
    """

    def __init__(self, supported_extensions: List[str] | None = None):
        self.supported_extensions = supported_extensions or [".json", ".csv", ".txt", ".pdf", ".svg", ".png"]

    def validate(self, artifacts: List[ArtifactRecord], strict: bool = False) -> Dict[str, Any]:
        report: Dict[str, Any] = {"artifacts": [], "summary": {"errors": 0, "warnings": 0, "infos": 0}}

        for a in artifacts:
            findings: List[Dict[str, Any]] = []
            path = a.resolved_path
            if not path:
                findings.append({"level": "ERROR", "message": "missing file", "artifact_id": a.id})
                report["summary"]["errors"] += 1
                a.validation = {"status": "missing", "findings": findings}
                report["artifacts"].append({"id": a.id, "findings": findings})
                continue

            p = Path(path)
            # file accessibility
            try:
                if not p.exists():
                    findings.append({"level": "ERROR", "message": "file does not exist"})
                elif not p.is_file():
                    findings.append({"level": "ERROR", "message": "path is not a file"})
                else:
                    findings.append({"level": "INFO", "message": "file accessible"})
            except PermissionError:
                findings.append({"level": "ERROR", "message": "permission denied"})
                report["summary"]["errors"] += 1
                a.validation = {"status": "inaccessible", "findings": findings}
                report["artifacts"].append({"id": a.id, "findings": findings})
                continue

            # extension support
            if p.suffix.lower() not in self.supported_extensions:
                findings.append({"level": "WARNING", "message": f"unsupported extension {p.suffix}"})
                report["summary"]["warnings"] += 1

            # checksum verification
            if a.checksum:
                try:
                    actual = sha256_file(p)
                    if actual != a.checksum:
                        findings.append({"level": "ERROR", "message": "checksum mismatch", "expected": a.checksum, "actual": actual})
                        report["summary"]["errors"] += 1
                    else:
                        findings.append({"level": "INFO", "message": "checksum verified"})
                except Exception as e:
                    findings.append({"level": "ERROR", "message": f"checksum error: {e}"})
                    report["summary"]["errors"] += 1

            # basic content validation for JSON and CSV
            if p.suffix.lower() == ".json":
                try:
                    with p.open("r", encoding="utf-8") as f:
                        json.load(f)
                    findings.append({"level": "INFO", "message": "valid JSON"})
                except Exception as e:
                    findings.append({"level": "ERROR", "message": f"invalid JSON: {e}"})
                    report["summary"]["errors"] += 1

            if p.suffix.lower() == ".csv":
                try:
                    with p.open("r", encoding="utf-8") as f:
                        reader = csv.reader(f)
                        _ = next(reader, None)
                    findings.append({"level": "INFO", "message": "CSV readable"})
                except Exception as e:
                    findings.append({"level": "ERROR", "message": f"invalid CSV: {e}"})
                    report["summary"]["errors"] += 1

            # timestamp consistency (if metadata contains timestamps)
            # Skip deep timestamp checks here; record presence if found
            if a.metadata and isinstance(a.metadata, dict):
                if "timestamp" in a.metadata or "generated_timestamp" in a.metadata:
                    findings.append({"level": "INFO", "message": "artifact metadata contains timestamp"})

            # finalize status
            if any(f["level"] == "ERROR" for f in findings):
                status = "invalid"
            else:
                status = "valid"

            a.validation = {"status": status, "findings": findings}
            report["artifacts"].append({"id": a.id, "status": status, "findings": findings})

        return report


__all__ = ["ArtifactValidator"]
