#!/usr/bin/env python3
"""
ViraxLog - Interface Module
Simple, thread-safe, and robust public API (Facade Pattern).
"""

from __future__ import annotations

import threading
import logging
import atexit
from typing import Any, Optional, Callable
from uuid import uuid4

from .models import ViraxConfig, LogEntry
from .core import ViraxLogger

# -------------------------------------------------
# GLOBAL SINGLETON STATE
# -------------------------------------------------

_GLOBAL_LOGGER: Optional[ViraxLogger] = None
_GLOBAL_LOCK = threading.Lock()

# -------------------------------------------------
# INITIALIZATION
# -------------------------------------------------

def initialize(config: Optional[ViraxConfig] = None, session_id: str = "MAIN") -> ViraxLogger:
    """
    Initializes the ViraxLog singleton in a thread-safe manner.
    
    Args:
        config: Custom configuration object.
        session_id: Unique identifier for the current logging session.
    """
    global _GLOBAL_LOGGER
    with _GLOBAL_LOCK:
        if _GLOBAL_LOGGER is not None:
            logging.warning("ViraxLog already initialized. Returning existing instance.")
            return _GLOBAL_LOGGER

        cfg = config or ViraxConfig()
        _GLOBAL_LOGGER = ViraxLogger(cfg, session_id)
        return _GLOBAL_LOGGER


def get_logger() -> ViraxLogger:
    """
    Returns the active ViraxLogger instance.
    Raises RuntimeError if initialize() has not been called.
    """
    if _GLOBAL_LOGGER is None:
        raise RuntimeError("ViraxLog not initialized. Please call initialize() first.")
    return _GLOBAL_LOGGER

# -------------------------------------------------
# PUBLIC LOGGING API
# -------------------------------------------------

def log(level: str, category: str, data: Any) -> None:
    """
    Central entry point for all logging operations.
    """
    try:
        if not isinstance(level, str) or not isinstance(category, str):
            raise TypeError("Log level and category must be strings.")

        get_logger().log(level.upper(), category, data)

    except RuntimeError:
        # Fallback to standard logging if ViraxLog is not ready
        logging.warning(
            f"ViraxLog not initialized. Dropped log [{level}] {category}: {data}"
        )
    except Exception as e:
        logging.error(f"Error during ViraxLog operation: {e}")


# Standardized Shortcuts
def info(category: str, data: Any) -> None:
    log("INFO", category, data)

def warning(category: str, data: Any) -> None:
    log("WARNING", category, data)

def error(category: str, data: Any) -> None:
    log("ERROR", category, data)

def critical(category: str, data: Any) -> None:
    log("CRITICAL", category, data)

def debug(category: str, data: Any) -> None:
    log("DEBUG", category, data)

# Extended levels
def trace(category: str, data: Any) -> None:
    log("TRACE", category, data)

def fatal(category: str, data: Any) -> None:
    log("FATAL", category, data)

# -------------------------------------------------
# WATCHERS API
# -------------------------------------------------

def watch(
    pattern: str,
    callback: Callable[[LogEntry], None],
    use_regex: bool = False
) -> str:
    """
    Registers a new watcher via the public interface.
    Returns the unique watcher ID.
    """
    logger = get_logger()
    return logger.watchers.add_watcher(pattern, callback, use_regex=use_regex)

# -------------------------------------------------
# CLEAN SHUTDOWN
# -------------------------------------------------

def stop() -> None:
    """
    Performs a graceful shutdown of the logging engine and resets the singleton.
    Ensures all remaining logs in the queue are written to the database.
    """
    global _GLOBAL_LOGGER
    with _GLOBAL_LOCK:
        if _GLOBAL_LOGGER:
            _GLOBAL_LOGGER.shutdown()
            _GLOBAL_LOGGER = None


# Automatically register the stop function to be called on program exit
atexit.register(stop)