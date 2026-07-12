# Phase 4 Quick Reference

## Run Phase 4

```powershell
python phase4_analysis.py
```

## Key Components

- BaseModel: abstract interface for models
- IsolationForestModel: trained on Phase 3 feature outputs
- Evaluator: computes accuracy, precision, recall, F1, and ROC-AUC
- ExperimentManager: manages experiment artifact folders
- ModelFactory: placeholder for future model extensibility

## Output Locations

- artifacts/models/
- artifacts/reports/phase4/
- artifacts/experiments/
- artifacts/plots/
