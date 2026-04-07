import logging
import sys

# ------------------------------------------------------------------------------
# Log format — consistent across every logger in the project.
# Output: [2026-04-06 12:00:00] [INFO] [app] — message
# ------------------------------------------------------------------------------

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] — %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def create_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Factory function — creates and returns a named, consistently configured logger.

    Every logger in this project is built through this single function so that
    formatting, handlers, and log levels are uniform across all services.

    Args:
        name:  Logger name (shows up in every log line, e.g. "app", "cab", "user").
        level: Minimum log level. Defaults to DEBUG so nothing is silently swallowed.

    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Guard: if handlers are already attached, return as-is.
    # Prevents duplicate log lines when the module is imported multiple times.
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # ── Console handler — writes to stdout ────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    logger.addHandler(console_handler)

    # Prevent log records from bubbling up to the root logger and printing twice.
    logger.propagate = False

    return logger


# ------------------------------------------------------------------------------
# App logger — default logger for core files:
# main.py, database.py, redis_client.py, middleware/jwt_middleware.py
# ------------------------------------------------------------------------------

app_logger = create_logger("app")
