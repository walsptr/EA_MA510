import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional


class _AutoCloseRotatingFileHandler(RotatingFileHandler):
    def emit(self, record):
        if self.stream is None:
            self.stream = self._open()
        try:
            super().emit(record)
        finally:
            if self.stream is not None:
                try:
                    self.stream.flush()
                except Exception:
                    pass
                try:
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None


def setup_logger(log_dir: str, log_level: str = "INFO") -> logging.Logger:
    """
    Setup logger "ea_ma510" dengan console + file handler.
    - Nama logger tetap: "ea_ma510"
    - Jika logger sudah punya handlers (setup sudah dipanggil sebelumnya), JANGAN duplikat handler.
    - Console handler: stream ke stderr/stdout dengan format yang rapi.
    - File handler: RotatingFileHandler (maxBytes 10MB, backupCount 5).
    - Format log: `%(asctime)s | %(levelname)-7s | %(message)s` (ISO timestamp).
    - Pastikan log_dir dibuat jika belum ada.
    - Return logger instance.
    """
    # 1. Pastikan direktori log
    os.makedirs(log_dir, exist_ok=True)

    # 2. Dapatkan / buat logger
    logger_name = "ea_ma510"
    logger = logging.getLogger(logger_name)

    # 3. Jangan duplikat handler jika setup berulang
    if logger.handlers:
        # Update level saja jika ada handler
        level = getattr(logging, log_level.upper(), logging.INFO)
        logger.setLevel(level)
        return logger

    # 4. Set level
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    # Jangan propagasi ke root logger (hindari double log ke parent)
    logger.propagate = False

    # 5. Format
    log_format = "%(asctime)s | %(levelname)-7s | %(message)s"
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    # 6. Console Handler (Stream ke stderr)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 7. File Rotating Handler
    log_file = os.path.join(log_dir, "ea_ma510.log")
    file_handler = _AutoCloseRotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
        delay=True,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
