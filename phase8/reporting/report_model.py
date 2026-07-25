"""ReportModel dataclass for report content."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, List, Optional


@dataclass(frozen=True)
class ReportModel:
    experiment_id: str
    title: str
    generated_timestamp: str
    experiment_metadata: Mapping
    dataset_information: Mapping
    evaluation_summary: Mapping
    statistical_summary: Mapping
    visualizations: List[str]
    generated_artifacts: Mapping
    overall_conclusions: Optional[str] = None
