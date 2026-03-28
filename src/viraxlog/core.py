#!/usr/bin/env python3
"""
ViraxLog - Core Module v2.0
Moteur asynchrone haute performance avec circuit breaker, métriques, et backpressure.
"""

from __future__ import annotations

import queue
import threading
import time
import logging
import psutil
import os
from datetime import datetime, timezone
from typing import Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from .models import LogEntry, ViraxConfig, MetricsSnapshot
from .database import DatabaseManager
from .watchers import WatcherManager
from .utils.crypto import compute_entry_hash
from .utils.helpers import get_caller_context, format_source_string, sanitize_data

logger = logging.getLogger("ViraxLog.Core")


class CircuitState(Enum):
    """États du circuit breaker."""
    CLOSED = "CLOSED"      # Normal
    OPEN = "OPEN"          # Erreurs trop hautes
    HALF_OPEN = "HALF_OPEN"  # Test de récupération


@dataclass
class CircuitBreaker:
    """Circuit breaker pour éviter cascades d'erreurs."""
    failure_threshold: int = 10
    recovery_timeout: int = 30
    
    def __post_init__(self):
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time = None
    
    def record_success(self) -> None:
        """Enregistre succès."""
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failures = 0
        elif self.state == CircuitState.CLOSED:
            self.failures = max(0, self.failures - 1)
    
    def record_failure(self) -> None:
        """Enregistre échec."""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
    
    def can_execute(self) -> bool:
        """Vérifie si exécution est possible."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        
        return self.state == CircuitState.HALF_OPEN


class ViraxLogger:
    """Moteur de logging central avec haute performance."""

    def __init__(self, config: ViraxConfig, session_id: str = "MAIN") -> None:
        self.config = config
        self.session_id = session_id
        
        # Components
        self.db = DatabaseManager(config)
        self.watchers = WatcherManager(max_workers=config.max_watcher_threads)
        
        # Thread-safe queue
        self._queue: queue.Queue[LogEntry] = queue.Queue(maxsize=config.queue_maxsize)
        
        # Chaîne cryptographique
        self._hash_lock = threading.RLock()
        self._last_hash = self.db.get_last_hash()
        
        # Circuit breaker
        self._circuit_breaker = CircuitBreaker()
        
        # Métriques
        self._metrics_lock = threading.Lock()
        self._metrics = {
            "logs_created": 0,
            "logs_written": 0,
            "logs_dropped": 0,
            "errors": 0,
            "start_time": time.time(),
        }
        
        # Threads
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(
            target=self._process_queue,
            name="ViraxWorker",
            daemon=True
        )
        self._worker_thread.start()
        
        # Heartbeat
        self._heartbeat_thread = None
        if config.enable_heartbeat:
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                name="ViraxHeartbeat",
                daemon=True
            )
            self._heartbeat_thread.start()
        
        logger.info(f"ViraxLog v2.0 initialized | Session: {session_id}")

    # ========== LOGGING API ==========

    def log(self, level: str, category: str, data: Any) -> None:
        """Enregistre une entrée (non-blocking sauf queue pleine)."""
        try:
            # Contexte appelant
            ctx = get_caller_context(depth=2)
            source_str = format_source_string(ctx)
            clean_data = sanitize_data(data)
            
            with self._hash_lock:
                timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
                prev_hash = self._last_hash
                data_str = LogEntry.serialize_data(clean_data)
                
                # Hash
                entry_hash = compute_entry_hash(
                    timestamp, level.upper(), category, data_str, prev_hash
                )
                
                entry = LogEntry(
                    timestamp=timestamp,
                    session_id=self.session_id,
                    level=level.upper(),
                    category=category,
                    source=source_str,
                    data=data_str,
                    hash=entry_hash,
                    prev_hash=prev_hash
                )
                
                self._last_hash = entry_hash
            
            # Enqueue avec gestion backpressure
            try:
                self._queue.put(entry, block=False)
                with self._metrics_lock:
                    self._metrics["logs_created"] += 1
            except queue.Full:
                with self._metrics_lock:
                    self._metrics["logs_dropped"] += 1
                logger.warning(f"Queue full! Log dropped: {category}")
            
            # Watchers asynchrone
            self.watchers.trigger(entry)
            
        except Exception as e:
            with self._metrics_lock:
                self._metrics["errors"] += 1
            logger.error(f"Logging error: {e}", exc_info=True)

    # ========== BACKGROUND PROCESSING ==========

    def _process_queue(self) -> None:
        """Consomme queue et écrit batches DB."""
        batch: List[LogEntry] = []
        last_commit_time = time.time()

        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                entry = self._queue.get(timeout=0.5)
                batch.append(entry)
                
                now = time.time()
                is_batch_full = len(batch) >= self.config.batch_size
                is_timeout = (now - last_commit_time > 2.0) and batch
                
                if is_batch_full or is_timeout:
                    if self._write_batch(batch):
                        batch.clear()
                        last_commit_time = now
                    else:
                        # Retry logic
                        time.sleep(0.1)
            
            except queue.Empty:
                if batch:
                    self._write_batch(batch)
                    batch.clear()
            except Exception as e:
                logger.error(f"Queue processing error: {e}")

    def _write_batch(self, batch: List[LogEntry]) -> bool:
        """Écrit batch avec circuit breaker."""
        if not self._circuit_breaker.can_execute():
            logger.warning("Circuit breaker OPEN - dropping batch")
            return False
        
        try:
            success = self.db.insert_log_batch(batch)
            if success:
                self._circuit_breaker.record_success()
                with self._metrics_lock:
                    self._metrics["logs_written"] += len(batch)
            else:
                self._circuit_breaker.record_failure()
            return success
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"Write failed: {e}")
            return False

    # ========== HEARTBEAT ==========

    def _heartbeat_loop(self) -> None:
        """Envoie heartbeats périodiques."""
        while not self._stop_event.is_set():
            try:
                ts = datetime.now(timezone.utc).isoformat()
                queue_size = self._queue.qsize()
                self.db.insert_heartbeat(ts, "alive", queue_size)
                
                # Sleep avec early-exit
                for _ in range(self.config.heartbeat_interval):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    # ========== MÉTRIQUES ==========

    def get_metrics(self) -> MetricsSnapshot:
        """Snapshot des métriques actuelles."""
        process = psutil.Process(os.getpid())
        
        with self._metrics_lock:
            return MetricsSnapshot(
                timestamp=datetime.now(timezone.utc).isoformat(),
                total_logs=self._metrics["logs_created"],
                queue_size=self._queue.qsize(),
                memory_mb=process.memory_info().rss / 1024 / 1024,
                cpu_percent=process.cpu_percent(interval=None),
                write_latency_ms=self.db.get_stats().get("last_write_ms", 0.0)
            )

    def get_stats(self) -> dict:
        """Retourne stats détaillées."""
        with self._metrics_lock:
            uptime = time.time() - self._metrics["start_time"]
            return {
                "uptime_sec": round(uptime, 2),
                "logs_created": self._metrics["logs_created"],
                "logs_written": self._metrics["logs_written"],
                "logs_dropped": self._metrics["logs_dropped"],
                "errors": self._metrics["errors"],
                "queue_size": self._queue.qsize(),
                "circuit_breaker_state": self._circuit_breaker.state.value,
                "db_stats": self.db.get_stats(),
            }

    # ========== LIFECYCLE ==========

    def shutdown(self) -> None:
        """Shutdown gracieux."""
        logger.info("ViraxLog shutdown initiated...")
        self._stop_event.set()
        
        # Wait workers
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
        
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2.0)
        
        self.watchers.shutdown()
        self.db.close()
        
        logger.info(f"Shutdown complete. Stats: {self.get_stats()}")
