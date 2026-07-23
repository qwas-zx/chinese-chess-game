"""Logging configuration helper for Chinese Chess Game.

Provides a simple centralized setup for console and optional file
logging with hardcoded log level.
"""
import logging
from logging.handlers import RotatingFileHandler


def setup_logging(level: str | None = None, logfile: str | None = None):
    """Configure root logger.

    - level: string like 'DEBUG', 'INFO'. Defaults to INFO.
    - logfile: optional path to write rolling logs. If provided, a RotatingFileHandler is added.
    """
    level = (level or 'INFO').upper()
    numeric_level = getattr(logging, level, logging.INFO)

    root = logging.getLogger()
    # Remove existing handlers to avoid duplicate logs when reloading
    if root.handlers:
        for h in list(root.handlers):
            root.removeHandler(h)

    fmt = '%(asctime)s %(levelname)-8s [%(name)s] %(message)s'
    formatter = logging.Formatter(fmt)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.setLevel(numeric_level)
    root.addHandler(console)

    if logfile:
        try:
            fh = RotatingFileHandler(logfile, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
            fh.setFormatter(formatter)
            fh.setLevel(numeric_level)
            root.addHandler(fh)
        except Exception:
            # If file handler cannot be created, keep console logging but warn.
            root.warning('Failed to create file log handler for %s', logfile)


def get_logger(name: str):
    return logging.getLogger(name)
