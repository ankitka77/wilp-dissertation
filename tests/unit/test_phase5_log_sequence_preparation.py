
from pathlib import Path
import pandas as pd
import project_bootstrap  # noqa: F401

import importlib.util
from importlib.machinery import SourceFileLoader

# Load modules directly from their file paths to avoid pytest import edge-cases
ROOT = Path(__file__).resolve().parents[2]
lp_dir = ROOT / "src" / "log_processing"

tm_path = lp_dir / "template_miner.py"
eim_path = lp_dir / "event_id_mapper.py"


def _load_module_from_path(name: str, path: Path):
    loader = SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


TemplateMiner = _load_module_from_path("template_miner_phase5", tm_path).TemplateMiner
EventIdMapper = _load_module_from_path("event_id_mapper_phase5", eim_path).EventIdMapper


def test_deterministic_vocabulary_across_runs(tmp_path: Path):
    # create synthetic messages
    messages = [
        '2020-01-01 00:00:01 Service started on 10.0.0.1 port 80',
        '2020-01-01 00:00:02 User 12345 logged in',
        '2020-01-01 00:00:03 Service started on 10.0.0.2 port 80',
    ]
    df = pd.DataFrame({"raw_line": messages})
    miner = TemplateMiner()
    mined = miner.mine_templates(df, message_col="raw_line")

    mapper1 = EventIdMapper()
    vocab1 = mapper1.build_vocabulary(mined)

    # run again to ensure deterministic ordering
    mapper2 = EventIdMapper()
    vocab2 = mapper2.build_vocabulary(mined)

    # Compare as sorted lists to ensure same mapping
    assert list(vocab1['template']) == list(vocab2['template'])
    assert list(vocab1['event_id']) == list(vocab2['event_id'])
