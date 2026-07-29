# Table and Figure Generation

This document describes the `TableGenerator` and `FigureGenerator` modules.

TableGenerator
- Module: `phase9.table_generator.generator.TableGenerator`
- Produces CSV, Markdown and JSON tables in `artifacts/phase9/latest/tables/`.
- Outputs `table_summary.json` and contributes to `asset_catalog.json`.

FigureGenerator
- Module: `phase9.figure_generator.generator.FigureGenerator`
- Produces SVG figures in `artifacts/phase9/latest/figures/` and optional PNG fallbacks when PIL is available.
- Outputs `figure_summary.json` and contributes to `asset_catalog.json`.

Asset model
- Unified asset model: `phase9.assets.models.AssetModel` and `AssetCatalog`.
- All assets are recorded in `asset_catalog.json` with metadata required by the Report Generator.
