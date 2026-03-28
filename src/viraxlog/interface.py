#!/usr/bin/env python3
"""
ViraxLog - Interface Module v2.0
Facade publique thread-safe avec context managers et async support.
"""

from __future__ import annotations

import threading
import logging
import atexit
import contextvars
from typing import Any, Optional, Callable
from uuid import uuid4

from .models import ViraxConfig, LogEntry
from .core import ViraxLogger

logger = logging.getLogger("ViraxLog.Interface")

# ========== GLOBAL STATE (thread-safe) ==========

_GLOBAL_LOGGER: Optional[ViraxLogger] = None
_GLOBAL_LOCK = threading.RLock()
_LOGGER_CONTEXT: contextvars.ContextVar[Optional[ViraxLogger]] = contextvars.ContextVar(
    'viraxlog_context', default=None
)

# ========== INITIALIZATION ==========

def initialize(
    config: Optional[ViraxConfig] = None,
    session_id: Optional[str] = None
) -> ViraxLogger:
    """
    Initialise singleton ViraxLog thread-safe.
    
    Args:
        config: Configuration personnalisée (optionnel)
        session_id: ID session unique (auto-généré si None)
    
    Returns:
        Instance ViraxLogger
    """
    global _GLOBAL_LOGGER
    
    with _GLOBAL_LOCK:
        if _GLOBAL_LOGGER is not None:
            logger.warning("ViraxLog already initialized. Returning existing instance.")
            return _GLOBAL_LOGGER

        cfg = config or ViraxConfig()
        cfg.validate()
        
        sid = session_id or f"SESS-{uuid4().hex[:8]}"
        _GLOBAL_LOGGER = ViraxLogger(cfg, sid)
        
        # Set context
        _LOGGER_CONTEXT.set(_GLOBAL_LOGGER)
        
        return _GLOBAL_LOGGER


def get_logger() -> ViraxLogger:
    """
    Retourne instance ViraxLog active.
    Raise RuntimeError si non initialisé.
    """
    logger_inst = _LOGGER_CONTEXT.get()
    if logger_inst is not None:
        return logger_inst
    
    if _GLOBAL_LOGGER is None:
        raise RuntimeError("ViraxLog not initialized. Call initialize() first.")
    
    return _GLOBAL_LOGGER


def is_initialized() -> bool:
    """Vérifie si ViraxLog est initialisé."""
    return _GLOBAL_LOGGER is not None or _LOGGER_CONTEXT.get() is not None


# ========== LOGGING API ==========

def log(level: str, category: str, data: Any) -> None:
    """
    Point d'entrée central pour tous logs.
    Non-blocking sauf queue pleine.
    """
    try:
        if not isinstance(level, str) or not isinstance(category, str):
            raise TypeError("level and category must be strings")

        get_logger().log(level.upper(), category, data)

    except RuntimeError:
        logging.warning(f"ViraxLog not initialized. Dropped: [{level}] {category}")
    except Exception as e:
        logging.error(f"ViraxLog error: {e}", exc_info=False)


# ========== CONVENIENCE SHORTCUTS ==========

def trace(category: str, data: Any) -> None:
    """Log TRACE level."""
    log("TRACE", category, data)


def debug(category: str, data: Any) -> None:
    """Log DEBUG level."""
    log("DEBUG", category, data)


def info(category: str, data: Any) -> None:
    """Log INFO level."""
    log("INFO", category, data)


def warning(category: str, data: Any) -> None:
    """Log WARNING level."""
    log("WARNING", category, data)


def error(category: str, data: Any) -> None:
    """Log ERROR level."""
    log("ERROR", category, data)


def critical(category: str, data: Any) -> None:
    """Log CRITICAL level."""
    log("CRITICAL", category, data)


def fatal(category: str, data: Any) -> None:
    """Log FATAL level."""
    log("FATAL", category, data)


# ========== WATCHERS API ==========

def watch(
    pattern: str,
    callback: Callable[[LogEntry], None],
    *,
    use_regex: bool = False,
    priority: int = 100
) -> str:
    """
    Enregistre watcher global.
    Retourne ID unique du watcher.
    """
    logger_inst = get_logger()
    return logger_inst.watchers.add_watcher(
        pattern, callback, use_regex=use_regex, priority=priority
    )


def watch_threshold(
    pattern: str,
    threshold: int,
    window_seconds: int,
    callback: Callable,
    *,
    use_regex: bool = False
) -> str:
    """
    Enregistre watcher de seuil (N hits en W secondes).
    """
    logger_inst = get_logger()
    return logger_inst.watchers.add_threshold_watcher(
        pattern, threshold, window_seconds, callback, use_regex=use_regex
    )


def unwatch(watcher_id: str) -> bool:
    """Supprime watcher par ID."""
    try:
        return get_logger().watchers.remove_watcher(watcher_id)
    except RuntimeError:
        return False


def get_watchers() -> list:
    """Retourne liste de tous watchers actifs."""
    try:
        return get_logger().watchers.list_watchers()
    except RuntimeError:
        return []


# ========== METRICS & STATS ==========

def get_metrics():
    """Retourne snapshot métrique actualisé."""
    try:
        return get_logger().get_metrics()
    except RuntimeError:
        return None


def get_stats() -> dict:
    """Retourne stats détaillées du logger."""
    try:
        return get_logger().get_stats()
    except RuntimeError:
        return {}


# ========== SHUTDOWN ==========

def stop() -> None:
    """
    Arrêt gracieux: flush queue, ferme DB, reset singleton.
    """
    global _GLOBAL_LOGGER
    
    with _GLOBAL_LOCK:
        if _GLOBAL_LOGGER:
            _GLOBAL_LOGGER.shutdown()
            _GLOBAL_LOGGER = None
            _LOGGER_CONTEXT.set(None)
            logger.info("ViraxLog stopped")


# Auto-register shutdown
atexit.register(stop)


# ========== CONTEXT MANAGER ==========

class ViraxLogContext:
    """
    Context manager pour usage local.
    
    Usage:
        with ViraxLogContext() as virax:
            virax.info("test", {"msg": "hello"})
    """
    
    def __init__(self, config: Optional[ViraxConfig] = None):
        self.config = config
        self.logger: Optional[ViraxLogger] = None
        self.is_global = False
    
    def __enter__(self) -> ViraxLogContext:
        """Entre context."""
        try:
            self.logger = get_logger()
            self.is_global = True
        except RuntimeError:
            # Crée instance locale
            cfg = self.config or ViraxConfig()
            self.logger = ViraxLogger(cfg)
            self.is_global = False
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sort context."""
        if not self.is_global and self.logger:
            self.logger.shutdown()
        return False
    
    # Delegates
    def log(self, level: str, category: str, data: Any) -> None:
        if self.logger:
            self.logger.log(level, category, data)
    
    def info(self, category: str, data: Any) -> None:
        self.log("INFO", category, data)
    
    def error(self, category: str, data: Any) -> None:
        self.log("ERROR", category, data)
    
    def warning(self, category: str, data: Any) -> None:
        self.log("WARNING", category, data)
    
    def debug(self, category: str, data: Any) -> None:
        self.log("DEBUG", category, data)


# ========== DECORATORS ==========

def log_function(level: str = "DEBUG", include_args: bool = False):
    """
    Decorator pour auto-log function calls.
    
    Usage:
        @log_function("INFO")
        def my_function(x, y):
            return x + y
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            category = f"function.{func.__module__}.{func.__name__}"
            
            data = {}
            if include_args:
                data["args"] = str(args)[:200]
                data["kwargs"] = str(kwargs)[:200]
            
            try:
                result = func(*args, **kwargs)
                data["status"] = "success"
                log(level, category, data)
                return result
            except Exception as e:
                data["status"] = "error"
                data["error"] = str(e)
                log("ERROR", category, data)
                raise
        
        return wrapper
    return decorator


# ========== MAIN ENTRY POINT ==========

def main():
    """CLI entry point (placeholder)."""
    print("ViraxLog v2.0 - Secure Logging System")
    print("Initialize with: viraxlog.initialize()")
