from logger.app_logger import app_logger
from logger.email_logger import email_logger

# ------------------------------------------------------------------------------
# Single import point for all loggers.
#
# Usage:
#   from logger import app_logger
#   from logger import email_logger
#
# To add a new service logger:
#   1. Create logger/<service>_logger.py
#   2. Add one line: <service>_logger = create_logger("<service>")
#   3. Export it here
# ------------------------------------------------------------------------------

__all__ = [
    "app_logger",
    "email_logger",
]
