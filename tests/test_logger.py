import pytest
import tempfile
import os
import logging
from src.logger import setup_logger


@pytest.fixture(autouse=True)
def reset_logger():
    logger = logging.getLogger("ea_ma510")
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    logger.handlers = []
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    yield
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def test_setup_logger_returns_logger_instance():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = setup_logger(tmpdir, "INFO")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "ea_ma510"
        assert logger.level == logging.INFO


def test_log_file_created_after_info_write():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "ea_ma510.log")
        logger = setup_logger(tmpdir, "DEBUG")
        # Tulis pesan
        logger.info("Test pesan info")
        logger.debug("Test pesan debug")
        # Pastikan file ada
        assert os.path.exists(log_file), f"Log file tidak ada: {log_file}"
        # Baca isi
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Test pesan info" in content
        assert "Test pesan debug" in content


def test_log_dir_created_automatically():
    import shutil
    with tempfile.TemporaryDirectory() as tmpdir:
        subdir = os.path.join(tmpdir, "nested", "logs", "deep")
        assert not os.path.exists(subdir)
        logger = setup_logger(subdir, "INFO")
        assert os.path.exists(subdir), "Log dir harus otomatis dibuat"


def test_no_duplicate_handlers_on_repeated_setup():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger1 = setup_logger(tmpdir, "INFO")
        count1 = len(logger1.handlers)
        # Setup lagi dengan dir sama
        logger2 = setup_logger(tmpdir, "WARNING")
        count2 = len(logger2.handlers)
        assert count1 == count2, f"Handler duplikat: {count1} → {count2}"
        assert logger1 is logger2  # harus instance yang sama
