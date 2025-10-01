"""
Logging configuration for Canvas CLI
"""

import logging

from rich.logging import RichHandler


def setup_logger(name: str = "canvas_cli", level: int = logging.INFO) -> logging.Logger:
    """
    Setup application logger with rich formatting

    Args:
        name: Logger name
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding multiple handlers if logger already exists
    if not logger.handlers:
        handler = RichHandler(rich_tracebacks=True, markup=True, show_time=True, show_path=False)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    return logger


# Create default logger instance
logger = setup_logger()
