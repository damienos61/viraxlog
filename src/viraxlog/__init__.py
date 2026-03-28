#!/usr/bin/env python3
"""
ViraxLog v2.0 - Secure, Cryptographically Chained Logging System
=========================================================================

High-performance immutable logging with:
- Cryptographic chaining (SHA256/BLAKE2b)
- Merkle tree verification (O(log n))
- WAL-mode SQLite optimizations
- Circuit breaker pattern
- Watchers & event reactors
- Multi-backend support (SQLite/PostgreSQL)
- Full async support

Quick Start:
    from viraxlog import initialize, info, stop
    
    initialize()
    info("startup", {"message": "App started"})
    stop()

Documentation: https://github.com/damienos61/viraxlog
"""

from .interface import (
    initialize,
    stop,
    get_logger,
    is_initialized,
    log,
    trace,
    debug,
    info,
    warning,
    error,
    critical,
    fatal,
    watch,
    watch_threshold,
    unwatch,
    get_watchers,
    get_metrics,
    get_stats,
    ViraxLogContext,
    log_function,
)

from .models import (
    ViraxConfig,
    LogEntry,
    LogLevel,
    AuditReport,
    MetricsSnapshot,
)

from .core import ViraxLogger, CircuitBreaker

from .audit import ViraxAuditor, run_audit

from .watchers import Watcher, WatcherManager, WatcherType

__version__ = "2.0.0"
__author__ = "damienos61"
__license__ = "MIT"

__all__ = [
    # Initialization & lifecycle
    "initialize",
    "stop",
    "get_logger",
    "is_initialized",
    "ViraxLogContext",
    
    # Logging API
    "log",
    "trace",
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "fatal",
    
    # Watchers
    "watch",
    "watch_threshold",
    "unwatch",
    "get_watchers",
    
    # Metrics
    "get_metrics",
    "get_stats",
    
    # Models
    "ViraxConfig",
    "LogEntry",
    "LogLevel",
    "AuditReport",
    "MetricsSnapshot",
    
    # Core classes
    "ViraxLogger",
    "CircuitBreaker",
    "ViraxAuditor",
    
    # Utilities
    "run_audit",
    "log_function",
    "Watcher",
    "WatcherManager",
    "WatcherType",
]
