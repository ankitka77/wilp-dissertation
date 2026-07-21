from pathlib import Path


from phase6.config import Config
from phase6.logger import LoggerFactory, PROJECT_LOGGER_NAME


def test_get_logger_creates_files_and_handlers(tmp_path: Path):
    cfg = Config(experiment_root=str(tmp_path))
    factory = LoggerFactory(config=cfg)
    log_name = "testlogger"
    logger = factory.get_logger(log_name)

    # logger name contains project prefix
    assert logger.name.startswith(PROJECT_LOGGER_NAME)

    logs_dir = tmp_path / "logs"
    assert logs_dir.exists()

    log_file = logs_dir / f"{log_name}.log"
    # Logging something should create or write to the file
    logger.info("hello world")
    # Ensure handler flushed
    for h in logger.handlers:
        try:
            h.flush()
        except Exception:
            pass

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "hello world" in content


def test_get_logger_idempotent_handlers(tmp_path: Path):
    cfg = Config(experiment_root=str(tmp_path))
    factory = LoggerFactory(config=cfg)
    name = "idem"
    logger1 = factory.get_logger(name)
    handlers_count_1 = len(logger1.handlers)
    logger2 = factory.get_logger(name)
    handlers_count_2 = len(logger2.handlers)
    assert handlers_count_1 == handlers_count_2
