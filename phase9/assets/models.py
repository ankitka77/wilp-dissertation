from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class AssetModel(BaseModel):
    asset_id: str
    asset_type: str  # 'table' or 'figure'
    category: str
    title: str
    caption: Optional[str] = None
    description: Optional[str] = None
    source_module: str
    source_data: List[str] = Field(default_factory=list)
    created_at: str
    relative_path: str
    filename: str
    output_format: str
    report_section: Optional[str] = None
    generation_version: Optional[str] = None


class AssetCatalog(BaseModel):
    generated_at: str
    assets: List[AssetModel] = Field(default_factory=list)


__all__ = ["AssetModel", "AssetCatalog"]
