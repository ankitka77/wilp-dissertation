import json
from pathlib import Path

from phase9.logging.logger import configure_logging


def test_configure_logging_creates_directory_and_file(tmp_path, simple_config):
    cfg = simple_config
    log_path = Path(cfg.logging.file_path)
    # ensure directory does not exist
    if log_path.exists():
        log_path.unlink()
    if log_path.parent.exists():
        for p in log_path.parent.iterdir():
            p.unlink()
        log_path.parent.rmdir()

    configure_logging(cfg)

    # emit a log
    import logging

    logger = logging.getLogger("phase9.test")
    logger.info("hello logging")

    assert log_path.parent.exists()
    assert log_path.exists()
    # file should contain valid JSON lines at least once
    txt = log_path.read_text()
    assert "hello logging" in txt
    # last line should be JSON
    lines = [l for l in txt.splitlines() if l.strip()]
    last = json.loads(lines[-1])
    assert last["message"].endswith("hello logging")
import logging
from pathlib import Path
from phase9.config.loader import load_config
from phase9.logging.logger import configure_logging, get_logger


def test_configure_logging(tmp_path: Path):
    cfg = load_config()
    # override file path to tmp
    cfg.logging.file_path = str(tmp_path / "phase9.log")
    configure_logging(cfg)
    lg = get_logger("phase9.test")
    lg.info("hello")
    # ensure log file created
    assert Path(cfg.logging.file_path).exists()
