"""Logging configuration helper for Chinese Chess Game.

Provides a centralized setup for console and file logging with:
- Structured JSON format for production
- Human-readable format for development
- Per-module log level control
- Request/Session ID tracking
"""
import logging
import logging.handlers
import json
import time
import os
from datetime import datetime
from functools import lru_cache


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter for production environments."""

    def format(self, record):
        log_obj = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_obj['user_id'] = record.user_id
        if hasattr(record, 'room_id'):
            log_obj['room_id'] = record.room_id
        if hasattr(record, 'game_mode'):
            log_obj['game_mode'] = record.game_mode
        if hasattr(record, 'move'):
            log_obj['move'] = record.move
        if hasattr(record, 'ai_depth'):
            log_obj['ai_depth'] = record.ai_depth
        if hasattr(record, 'ai_score'):
            log_obj['ai_score'] = record.ai_score
        if hasattr(record, 'duration_ms'):
            log_obj['duration_ms'] = record.duration_ms
        if hasattr(record, 'error'):
            log_obj['error'] = record.error

        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    def format(self, record):
        base = f"{self.formatTime(record)} {record.levelname:8s} [{record.name}] {record.getMessage()}"

        extras = []
        if hasattr(record, 'user_id'):
            extras.append(f"user={record.user_id}")
        if hasattr(record, 'room_id'):
            extras.append(f"room={record.room_id}")
        if hasattr(record, 'game_mode'):
            extras.append(f"mode={record.game_mode}")
        if hasattr(record, 'duration_ms'):
            extras.append(f"duration={record.duration_ms}ms")

        if extras:
            base += f" ({' '.join(extras)})"

        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"

        return base


LOG_LEVELS = {
    'auth': logging.INFO,       # Authentication events
    'game': logging.INFO,       # Game logic events
    'online': logging.INFO,     # Online/room events
    'ai': logging.INFO,         # AI engine events
    'routes': logging.INFO,     # HTTP route events
    'db': logging.WARNING,      # Database events (reduce noise)
}


def setup_logging(level: str | None = None, logfile: str | None = None, structured: bool = False):
    """Configure root logger with per-module level control.

    Args:
        level: Root log level ('DEBUG', 'INFO', 'WARNING', etc.). Defaults to INFO.
        logfile: Optional path for rotating log file.
        structured: Use JSON-structured format for production environments.
    """
    level = (level or 'INFO').upper()
    numeric_level = getattr(logging, level, logging.INFO)

    root = logging.getLogger()
    # Remove existing handlers to avoid duplicate logs when reloading
    if root.handlers:
        for h in list(root.handlers):
            root.removeHandler(h)

    # Choose formatter based on structured flag
    formatter = StructuredFormatter() if structured else HumanFormatter()

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.setLevel(numeric_level)
    root.addHandler(console)

    # File handler (optional)
    if logfile:
        try:
            # Ensure log directory exists
            log_dir = os.path.dirname(logfile)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            fh = logging.handlers.RotatingFileHandler(
                logfile,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            fh.setFormatter(formatter)
            fh.setLevel(numeric_level)
            root.addHandler(fh)
        except Exception as e:
            root.warning('Failed to create file log handler for %s: %s', logfile, e)

    # Apply per-module log levels
    # Use the configured level if it's more verbose, otherwise keep module default
    for module_name, module_level in LOG_LEVELS.items():
        effective_level = min(numeric_level, module_level)
        logging.getLogger(f'routes.{module_name}_routes').setLevel(effective_level)
        if module_name in ('game', 'ai'):
            logging.getLogger(f'game.{module_name}').setLevel(effective_level)
        if module_name == 'online':
            logging.getLogger('online').setLevel(effective_level)

    # Ensure game.core respects the root level (so DEBUG is not blocked)
    logging.getLogger('game.core').setLevel(numeric_level)

    # Reduce noise from third-party libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('engineio').setLevel(logging.WARNING)
    logging.getLogger('socketio').setLevel(logging.WARNING)


@lru_cache(maxsize=128)
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with module-specific configuration."""
    return logging.getLogger(name)


class LogContext:
    """Context manager for structured logging with extra fields."""

    def __init__(self, logger, operation: str, **extra):
        self.logger = logger
        self.operation = operation
        self.extra = extra
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(f"{self.operation} START", extra=self.extra)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self.start_time) * 1000)
        extra = {**self.extra, 'duration_ms': duration_ms}

        if exc_type:
            extra['error'] = str(exc_val)
            self.logger.error(f"{self.operation} FAILED", extra=extra, exc_info=True)
        else:
            self.logger.info(f"{self.operation} SUCCESS", extra=extra)

        return False  # Don't suppress exceptions


# Convenience functions for common log patterns
def log_auth_event(logger, event: str, user_id: int = None, username: str = None, success: bool = True, **extra):
    """Log authentication-related events."""
    extra_fields = {'user_id': user_id, **extra}
    if success:
        logger.info(f"AUTH {event}: user={username}", extra=extra_fields)
    else:
        logger.warning(f"AUTH {event} FAILED: user={username}", extra=extra_fields)


def log_game_event(logger, event: str, user_id: int = None, game_mode: str = None, **extra):
    """Log game-related events."""
    extra_fields = {'user_id': user_id, 'game_mode': game_mode, **extra}
    logger.info(f"GAME {event}", extra=extra_fields)


def log_online_event(logger, event: str, user_id: int = None, room_id: str = None, **extra):
    """Log online/room events."""
    extra_fields = {'user_id': user_id, 'room_id': room_id, **extra}
    logger.info(f"ONLINE {event}", extra=extra_fields)


def log_ai_event(logger, event: str, depth: int = None, score: int = None, **extra):
    """Log AI engine events."""
    extra_fields = {'ai_depth': depth, 'ai_score': score, **extra}
    logger.info(f"AI {event}", extra=extra_fields)
