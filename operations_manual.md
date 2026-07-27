# Operations Manual — Train and Run Models

This concise manual describes the exact steps to set up the environment, prepare data, and run the project end-to-end (Phase 2 → Phase 6). It assumes you will not modify source files. Commands are for Windows PowerShell but work in any shell with Python available.

**Prerequisites**
- Python 3.10+ (match your local TensorFlow support)
- Git (optional, for manifest/git metadata)
- ~10–20 GB free disk space for artifacts and models depending on experiments

**1. Clone / Locate Repository**
- Work from the repository root where `README.md` and the phase scripts live.
```powershell
cd <working directory>
git clone https://github.com/ankitka77/wilp-dissertation.git
cd wilp-dissertation\
git checkout phase8-performance-evaluation
```

**2. Create and activate a virtual environment**
- PowerShell (recommended):

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned (if needed)
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

**3. Install runtime dependencies**
- Install core requirements:

```powershell
python -m pip install -r requirements.txt
```

- For development/tests (optional):

```powershell
python -m pip install -r requirements-dev.txt
```

**4. Configure runtime settings (optional)**
- Primary config file: `config/settings.yaml` — edit only if you need to change paths, seeds, or experiment defaults.
- Logging config: `config/logging.yaml`.
- You can override settings via an optional `.env` placed at repo root (see `README.md` for names like `WILP_ENVIRONMENT`).

**5. Place input datasets**
- KPI pipeline expects:
  - `data/kpi/train.csv` (columns: `timestamp`, `value`, `label`, `KPI ID`)
  - `data/kpi/test.csv` (columns: `timestamp`, `value`, `KPI ID`)
- Log pipeline (Phase 5) expects raw logs under `data/logs/` or change `phase5.input_dir` in `config/settings.yaml`.

Execution order (recommended): Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6

**6. Phase 2 — KPI dataset analysis (validation + profiling + plots)**
- Purpose: validate KPI CSVs and produce profiling reports and plots.
- Run:

```powershell
python phase2_analysis.py
```

- Output (examples): `artifacts/reports/phase2/*`, `artifacts/plots/`
- If the script errors: check `data/kpi/train.csv` and `data/kpi/test.csv`, then `config/settings.yaml` and `config/logging.yaml` for paths.

**7. Phase 3 — KPI feature engineering**
- Purpose: compute feature windows/rolling stats and write processed CSVs used by modeling.
- Run:

```powershell
python phase3_feature_engineering.py
```

- Results saved to `data/processed/kpi_features_train.csv` and `data/processed/kpi_features_test.csv` and `artifacts/reports/phase3/`.

**8. Phase 4 — KPI model training (Isolation Forest) and evaluation**
- Purpose: train the KPI model, save model artifact(s), and save evaluation reports and plots.
- Precondition: outputs from Phase 3 must exist (`data/processed/kpi_features_*.csv`).
- Run:

```powershell
python phase4_analysis.py
```

- Outputs:
  - `artifacts/models/` (saved model files, e.g., `*_model.pkl`)
  - `artifacts/reports/phase4/` (metrics, predictions)
  - `artifacts/plots/`

**9. Phase 5 — Log preprocessing (template mining → sequence builder)**
- Purpose: convert raw logs into event vocabulary and sliding-window sequences for sequence models.
- Run:

```powershell
python phase5_analysis.py
```

- Outputs (key): `artifacts/reports/phase5/` containing:
  - `event_vocabulary.json` (and CSV)
  - `training_sequences.csv`, `test_sequences.csv`
  - `phase5` manifest and profiling CSVs

**10. Phase 6 — Sequence model training & inference (DeepLog design scaffold)**
- Purpose: train sequence models on Phase 5 outputs and write a canonical Phase 6 manifest.
- Precondition: Phase 5 artifacts must be present under `artifacts/reports/phase5/` with the standard filenames.
- Run (single command):

```powershell
python phase6_runner.py
```

- Notes: `phase6_runner.py` will load `config/settings.yaml` (falls back to defaults if missing) and expects these paths under `artifacts/reports/phase5`:
  - `event_vocabulary.json` or `event_vocabulary.csv`
  - `training_sequences.csv`, `test_sequences.csv`
  - `phase5_manifest.json` (optional but useful)

- On success, Phase 6 writes:
  - `artifacts/phase6/models/`
  - `artifacts/phase6/reports/predictions.csv`
  - `artifacts/phase6/reports/training_metrics.json`
  - `artifacts/phase6/plots/`
  - `artifacts/phase6/manifests/phase6_manifest.json`

**11. Phase 7 / Fusion and tests**
- Fusion code lives under `src/fusion` and higher-level Phase 7 tests under `tests/phase7`.
- Run Phase 7 unit/integration/regression tests selectively:

```powershell
pytest tests/phase7 -q
# or full test suite
pytest -q
```

**12. Common troubleshooting**
- Missing files for a phase: check previous phase outputs and re-run that phase.
- Logging is configured via `config/logging.yaml` and will print useful messages to console when running the scripts.
- If TensorFlow or other heavy libs fail to import, confirm Python version compatibility and reinstall packages inside a fresh virtualenv.
- For GPU acceleration, ensure proper CUDA/cuDNN and TensorFlow build compatible with your Python version.

**13. Quick verification commands**
- Sanity-check environment and imports:

```powershell
python -c "import sys; import pandas as pd; import numpy as np; import tensorflow as tf; print('ok', sys.version)"
```

- Run a single phase quickly (example: run Phase 2 only):

```powershell
python phase2_analysis.py
```

**14. Useful file locations**
- Project settings: `config/settings.yaml`
- Logging config: `config/logging.yaml`
- Phase runners: `phase2_analysis.py`, `phase3_feature_engineering.py`, `phase4_analysis.py`, `phase5_analysis.py`, `phase6_runner.py`
- Core source: `src/` (packages `data`, `preprocessing`, `kpi_model`, `log_processing`, `fusion`)
- Artifacts root: `artifacts/`

---
If you want, I can now: run the repository tests, generate a minimal `settings.yaml` template, or produce short runnable examples to exercise each phase locally. Which would you like next?
