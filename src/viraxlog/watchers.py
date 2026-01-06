#!/usr/bin/env python3
"""
ViraxLog - Watchers Module
Reactive event-driven engine for real-time log analysis.
"""

from __future__ import annotations

import re
import uuid
import time
import logging
import threading
import concurrent.futures
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List, Pattern, Optional

from .models import LogEntry

# -------------------------------------------------
# WATCHER - CONTRACT
# -------------------------------------------------

@dataclass(slots=True)
class Watcher:
    """
    Reactive event rule.
    """
    id: str
    pattern: Pattern[str]
    callback: Callable
    enabled: bool = True
    priority: int = 100  # Lower value = higher priority
    created_at: float = field(default_factory=time.time)
    hits: int = 0

    def matches(self, entry: LogEntry) -> bool:
        """Returns True if the watcher should trigger for this log entry."""
        return self.enabled and bool(self.pattern.search(entry.category))


# -------------------------------------------------
# WATCHER MANAGER
# -------------------------------------------------

class WatcherManager:
    """
    Orchestrates watchers execution.
    Features:
    - Asynchronous execution via ThreadPool
    - Priority-based ordering
    - Error isolation (one failing watcher doesn't break the system)
    """

    def __init__(self, max_workers: int = 5) -> None:
        self.logger = logging.getLogger("ViraxLog.Watchers")
        self._watchers: Dict[str, Watcher] = {}
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="ViraxWatcher"
        )
        self._shutdown_lock = threading.Lock()
        self._is_shutdown = False

    # -------------------------------------------------
    # REGISTRATION
    # -------------------------------------------------

    def add_watcher(
        self,
        pattern: str,
        callback: Callable,
        *,
        use_regex: bool = False,
        priority: int = 100,
        enabled: bool = True
    ) -> str:
        """Registers a new watcher and returns its unique ID."""
        try:
            if pattern == "*":
                compiled = re.compile(".*")
            else:
                compiled = re.compile(pattern) if use_regex else re.compile(re.escape(pattern))
        except re.error as e:
            raise ValueError(f"Invalid watcher pattern: {e}")

        wid = uuid.uuid4().hex[:8]
        self._watchers[wid] = Watcher(
            id=wid,
            pattern=compiled,
            callback=callback,
            enabled=enabled,
            priority=priority,
        )
        self.logger.debug(f"Watcher {wid} registered for pattern: {pattern}")
        return wid

    def remove_watcher(self, watcher_id: str) -> bool:
        """Removes a watcher by its ID."""
        return self._watchers.pop(watcher_id, None) is not None

    def toggle(self, watcher_id: str, state: bool) -> None:
        """Enables or disables a specific watcher."""
        if watcher_id in self._watchers:
            self._watchers[watcher_id].enabled = state

    # -------------------------------------------------
    # DISPATCH
    # -------------------------------------------------

    def trigger(self, entry: LogEntry) -> None:
        """
        Triggers all matching watchers for a given LogEntry.
        Executes callbacks asynchronously in the thread pool.
        """
        if self._is_shutdown:
            return

        # Filter and sort by priority
        active_watchers = sorted(
            (w for w in self._watchers.values() if w.matches(entry)),
            key=lambda w: w.priority
        )

        for watcher in active_watchers:
            watcher.hits += 1
            try:
                self._executor.submit(self._safe_callback, watcher.callback, entry)
            except concurrent.futures.RuntimeError:
                self.logger.warning("Executor is down, cannot trigger watcher.")

    # -------------------------------------------------
    # SAFE CALLBACK WRAPPER
    # -------------------------------------------------

    def _safe_callback(self, callback: Callable, *args) -> None:
        """Executes a callback within a try/except block to ensure stability."""
        try:
            callback(*args)
        except Exception as e:
            self.logger.error(f"Watcher callback execution failed: {e}")

    # -------------------------------------------------
    # INTROSPECTION
    # -------------------------------------------------

    def list_watchers(self) -> List[Dict[str, Any]]:
        """Returns the current state and statistics of all watchers."""
        return [
            {
                "id": w.id,
                "enabled": w.enabled,
                "priority": w.priority,
                "hits": w.hits,
                "pattern": w.pattern.pattern,
                "uptime_sec": round(time.time() - w.created_at, 2),
            }
            for w in self._watchers.values()
        ]

    # -------------------------------------------------
    # SHUTDOWN
    # -------------------------------------------------

    def shutdown(self) -> None:
        """Safely stops the executor and waits for pending callbacks."""
        self._is_shutdown = True
        self.logger.debug("Shutting down WatcherManager...")
        self._executor.shutdown(wait=True)