import pandas as pd
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

# Load parser directly from source to avoid pytest import timing issues
ROOT = Path(__file__).resolve().parents[2]
lp_path = ROOT / "src" / "log_processing" / "log_parser.py"


def _load_module_from_path(name: str, path: Path):
    loader = SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


LogParser = _load_module_from_path("log_parser_phase5", lp_path).LogParser


def test_parse_hdfs_like_line():
    line = "2020-01-01 00:00:01,123 INFO org.apache.hadoop.hdfs.server.datanode.DataNode: Block blk_1073741832_1001 received from /10.0.0.1"
    df = pd.DataFrame({"raw_line": [line]})
    parser = LogParser()
    out = parser.parse(df)

    assert out.loc[0, "timestamp"] == "2020-01-01 00:00:01,123"
    assert out.loc[0, "level"] == "INFO"
    assert "DataNode" in (out.loc[0, "component"] or "")
    assert out.loc[0, "block_id"] is not None
    assert "received from" in out.loc[0, "message"]


def test_parse_bgl_like_line_with_host_pid_thread_session():
    line = "2011-07-01 12:34:56 host1 MyService[12345] INFO Thread-1: Session session-abc started"
    df = pd.DataFrame({"raw_line": [line]})
    parser = LogParser()
    out = parser.parse(df)

    assert out.loc[0, "timestamp"] == "2011-07-01 12:34:56"
    assert out.loc[0, "hostname"] == "host1"
    assert out.loc[0, "component"] == "MyService"
    assert out.loc[0, "pid"] == "12345"
    assert out.loc[0, "level"] == "INFO"
    assert out.loc[0, "thread_id"] is not None
    assert out.loc[0, "session_id"] is not None


def test_parse_line_without_timestamp_or_structured_fields():
    line = "A random informational message without structured fields"
    df = pd.DataFrame({"raw_line": [line]})
    parser = LogParser()
    out = parser.parse(df)

    assert out.loc[0, "timestamp"] is None
    assert out.loc[0, "message"] == line
    assert out.loc[0, "component"] is None
    assert out.loc[0, "hostname"] is None
