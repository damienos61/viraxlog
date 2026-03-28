#!/usr/bin/env python3
"""
ViraxLog - Watchers Module v2.0
Moteur réactif événementiel avec patterns avancés et gestion d'erreurs.
"""

from __future__ import annotations

import re
import uuid
import time
import logging
import threading
import concurrent.futures
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List, Pattern, Optional, Literal
from enum import Enum

from .models import LogEntry

logger = logging.getLogger("ViraxLog.Watchers")


class WatcherType(str, Enum):
    """Types de watchers."""
    SIMPLE = "simple"          # Regex sur category
    THRESHOLD = "threshold"    # Trigger si count > N en window
    ALERT = "alert"            # Pour alertes critiques


@dataclass(slots=True)
class Watcher:
    """Règle de surveillance réactive."""
    id: str
    pattern: Pattern[str]
    callback: Callable
    enabled: bool = True
    priority: int = 100
    created_at: float = field(default_factory=time.time)
    hits: int = 0
    last_hit_time: Optional[float] = None
    errors: int = 0
    watcher_type: WatcherType = WatcherType.SIMPLE

    def matches(self, entry: LogEntry) -> bool:
        """Vérifie si watcher doit trigger."""
        if not self.enabled:
            return False
        return bool(self.pattern.search(entry.category))

    def record_hit(self) -> None:
        """Enregistre match."""
        self.hits += 1
        self.last_hit_time = time.time()

    def record_error(self) -> None:
        """Enregistre erreur callback."""
        self.errors += 1


@dataclass(slots=True)
class ThresholdWatcher:
    """Watcher avec seuil temporel."""
    id: str
    pattern: Pattern[str]
    threshold: int           # N hits
    window_seconds: int      # dans cette fenêtre
    callback: Callable
    enabled: bool = True
    hits_in_window: List[float] = field(default_factory=list)
    triggered: bool = False

    def check_and_update(self, entry: LogEntry) -> bool:
        """Retourne True si seuil atteint."""
        if not self.enabled or not self.pattern.search(entry.category):
            return False

        now = time.time()
        # Nettoie vieux hits
        self.hits_in_window = [t for t in self.hits_in_window if now - t < self.window_seconds]
        self.hits_in_window.append(now)

        if len(self.hits_in_window) >= self.threshold:
            if not self.triggered:
                self.triggered = True
                return True
        else:
            self.triggered = False

        return False


class WatcherManager:
    """
    Orchestrateur de watchers avec:
    - Exécution asynchrone thread pool
    - Ordering par priorité
    - Isolation erreurs
    - Statistiques
    """

    def __init__(self, max_workers: int = 5) -> None:
        self.logger = logging.getLogger("ViraxLog.Watchers")
        self._watchers: Dict[str, Watcher] = {}
        self._threshold_watchers: Dict[str, ThresholdWatcher] = {}
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="ViraxWatcher"
        )
        self._shutdown_lock = threading.Lock()
        self._is_shutdown = False
        self._stats = {
            "total_triggers": 0,
            "total_errors": 0,
        }

    # ========== REGISTRATION ==========

    def add_watcher(
        self,
        pattern: str,
        callback: Callable,
        *,
        use_regex: bool = False,
        priority: int = 100,
        enabled: bool = True,
        watcher_type: WatcherType = WatcherType.SIMPLE
    ) -> str:
        """Enregistre watcher et retourne son ID."""
        try:
            if pattern == "*":
                compiled = re.compile(".*")
            else:
                compiled = re.compile(pattern) if use_regex else re.compile(re.escape(pattern))
        except re.error as e:
            raise ValueError(f"Invalid pattern: {e}")

        wid = uuid.uuid4().hex[:8]
        self._watchers[wid] = Watcher(
            id=wid,
            pattern=compiled,
            callback=callback,
            enabled=enabled,
            priority=priority,
            watcher_type=watcher_type
        )
        self.logger.debug(f"Watcher {wid} registered | pattern={pattern} | priority={priority}")
        return wid

    def add_threshold_watcher(
        self,
        pattern: str,
        threshold: int,
        window_seconds: int,
        callback: Callable,
        *,
        use_regex: bool = False,
        enabled: bool = True
    ) -> str:
        """Enregistre watcher de seuil (N hits en W secondes)."""
        try:
            compiled = re.compile(pattern) if use_regex else re.compile(re.escape(pattern))
        except re.error as e:
            raise ValueError(f"Invalid pattern: {e}")

        wid = uuid.uuid4().hex[:8]
        self._threshold_watchers[wid] = ThresholdWatcher(
            id=wid,
            pattern=compiled,
            threshold=threshold,
            window_seconds=window_seconds,
            callback=callback,
            enabled=enabled
        )
        self.logger.debug(
            f"Threshold watcher {wid} registered | {threshold} hits / {window_seconds}s"
        )
        return wid

    def remove_watcher(self, watcher_id: str) -> bool:
        """Supprime watcher par ID."""
        removed = False
        if watcher_id in self._watchers:
            del self._watchers[watcher_id]
            removed = True
        if watcher_id in self._threshold_watchers:
            del self._threshold_watchers[watcher_id]
            removed = True
        return removed

    def toggle(self, watcher_id: str, state: bool) -> None:
        """Active/désactive watcher."""
        if watcher_id in self._watchers:
            self._watchers[watcher_id].enabled = state
        if watcher_id in self._threshold_watchers:
            self._threshold_watchers[watcher_id].enabled = state

    # ========== DISPATCH ==========

    def trigger(self, entry: LogEntry) -> None:
        """Déclenche watchers actifs pour une entry."""
        if self._is_shutdown:
            return

        # Watchers simples (ordered by priority)
        active_watchers = sorted(
            (w for w in self._watchers.values() if w.matches(entry)),
            key=lambda w: w.priority
        )

        for watcher in active_watchers:
            watcher.record_hit()
            try:
                self._executor.submit(self._safe_callback, watcher.callback, entry, watcher)
                self._stats["total_triggers"] += 1
            except concurrent.futures.RuntimeError:
                self.logger.warning("Executor unavailable")

        # Threshold watchers
        for tw in self._threshold_watchers.values():
            if tw.check_and_update(entry):
                try:
                    self._executor.submit(self._safe_callback, tw.callback, entry, tw)
                    self._stats["total_triggers"] += 1
                except concurrent.futures.RuntimeError:
                    pass

    def _safe_callback(self, callback: Callable, *args) -> None:
        """Exécute callback avec gestion erreurs."""
        try:
            callback(*args)
        except Exception as e:
            self._stats["total_errors"] += 1
            # Enregistre erreur dans watcher si possible
            if len(args) > 1 and hasattr(args[1], "record_error"):
                args[1].record_error()
            self.logger.error(f"Watcher callback failed: {e}", exc_info=False)

    # ========== INTROSPECTION ==========

    def list_watchers(self) -> List[Dict[str, Any]]:
        """Retourne état de tous watchers."""
        result = []
        
        for w in self._watchers.values():
            result.append({
                "id": w.id,
                "type": w.watcher_type.value,
                "enabled": w.enabled,
                "priority": w.priority,
                "hits": w.hits,
                "errors": w.errors,
                "pattern": w.pattern.pattern,
                "uptime_sec": round(time.time() - w.created_at, 2),
                "last_hit": w.last_hit_time,
            })
        
        for tw in self._threshold_watchers.values():
            result.append({
                "id": tw.id,
                "type": "threshold",
                "enabled": tw.enabled,
                "threshold": tw.threshold,
                "window_seconds": tw.window_seconds,
                "pattern": tw.pattern.pattern,
                "current_hits": len(tw.hits_in_window),
                "triggered": tw.triggered,
            })
        
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Retourne statistiques globales."""
        return {
            "total_watchers": len(self._watchers) + len(self._threshold_watchers),
            "simple_watchers": len(self._watchers),
            "threshold_watchers": len(self._threshold_watchers),
            "total_triggers": self._stats["total_triggers"],
            "total_errors": self._stats["total_errors"],
        }

    # ========== SHUTDOWN ==========

    def shutdown(self) -> None:
        """Arrête executor et attend callbacks."""
        self._is_shutdown = True
        self.logger.debug("Shutting down WatcherManager...")
        self._executor.shutdown(wait=True)
        self.logger.info(f"Watchers shutdown complete | Stats: {self.get_stats()}")
