"""
ViraxLog - Main Package
============================

ViraxLog is a secure and high-performance logging system based on SQLite,
featuring cryptographic chaining, asynchronous watchers, and a simple interface.

Quick example:

    from viraxlog import initialize, info, watch, stop

    # Initialisation
    initialize()

    # Log an event
    info("startup", {"message": "Application started"})

    # Stop
    stop()
"""

# Import from .interfaces (ensure your file is named interfaces.py)
from .interface import (
    initialize,
    stop,
    log,
    info,
    warning,
    error,
    critical,
    debug,
    trace,
    fatal,
    watch,
    get_logger
)
from .models import ViraxConfig, LogEntry
from .core import ViraxLogger

__version__ = "1.0.0"

# This defines what is available when someone does 'from viraxlog import *'
__all__ = [
    "initialize", "stop", "log", "info", "warning",
    "error", "critical", "debug", "trace", "fatal",
    "watch", "get_logger", "ViraxConfig", "ViraxLogger", "LogEntry"
]