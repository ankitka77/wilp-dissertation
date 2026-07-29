# Configuration Module

Purpose: Load and validate Phase 9 runtime configuration.

Public APIs:
- `load_config(path: Optional[Path], overrides: Optional[Dict]) -> Phase9Settings`

Usage example:

```python
from phase9.config.loader import load_config

cfg = load_config(Path("phase9/config/default.yaml"))
```
