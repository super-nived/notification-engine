"""
Centralised logging configuration for the Notification Rule Engine.

Call ``configure_logging()`` once at application startup (inside
``main.py``). Every module then obtains its own logger with::

    import logging
    logger = logging.getLogger(__name__)

Never call ``print()`` — use the logger.
"""

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger with a consistent format and handler.

    Sets up a ``StreamHandler`` writing to stdout with a timestamped
    format. Should be called exactly once, during application startup.

    Args:
        level: Logging level string, e.g. ``"INFO"`` or ``"DEBUG"``.

    Returns:
        None
    """
    log_format = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
