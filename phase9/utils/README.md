# Utilities Module

Purpose: Generic helpers (filesystem, checksum, JSON/YAML, CSV, time) used by Phase 9 modules.

Public APIs (selected):
- `safe_write_text(path, text)`
- `safe_read_text(path)`
- `ensure_dir(path)`
- `sha256_file(path)`
- `now_iso()`
