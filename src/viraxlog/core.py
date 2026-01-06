#!/usr/bin/env python3
"""
ViraxLog - Core Module
The brain of the system: handles asynchronicity, integrity chaining, watchers, and heartbeats.
"""

from __future__ import annotations

import queue
import threading
import time
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from .models import LogEntry, ViraxConfig
from .database import DatabaseManager
from .watchers import WatcherManager
from .utils.crypto import compute_entry_hash
from .utils.helpers import get_caller_context, format_source_string, sanitize_data

class ViraxLogger:
    """Main entry point for log capture and persistence."""

    def __init__(self, config: ViraxConfig, session_id: str = "SESS-DEFAULT") -> None:
        self.config = config
        self.session_id = session_id
        self.logger = logging.getLogger("ViraxLog.Core")

        # Initialize core components
        self.db = DatabaseManager(self.config)
        self.watchers = WatcherManager(max_workers=self.config.max_workers)
        
        # Thread-safe queue for incoming logs
        self._queue: queue.Queue[LogEntry] = queue.Queue(maxsize=self.config.queue_maxsize)
        
        # Cryptographic chain management
        self._hash_lock = threading.Lock()
        self._last_hash = self.db.get_last_hash()

        # Background processing threads
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._process_queue, name="ViraxWorker", daemon=True)
        self._worker_thread.start()

        # Optional system heartbeat
        self._heartbeat_thread = None
        if self.config.enable_heartbeat:
            self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, name="ViraxHeartbeat", daemon=True)
            self._heartbeat_thread.start()

        self.logger.info(f"ViraxLog started. Session: {self.session_id} | Last Hash: {self._last_hash[:16]}...")

    # -------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------

    def log(self, level: str, category: str, data: Any) -> None:
        """
        Captures a log entry, computes its hash, and puts it into the background queue.
        This method is non-blocking unless the queue is full.
        """
        try:
            # Gather execution context (caller info)
            ctx = get_caller_context(depth=2)
            source_str = format_source_string(ctx)
            clean_data = sanitize_data(data)
            
            with self._hash_lock:
                # Prepare entry with ISO timestamp and cryptographic link
                timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
                prev_hash = self._last_hash
                
                # Serialize data once to ensure consistency between hash and storage
                data_str = LogEntry.serialize_data(clean_data)
                
                # Compute unique fingerprint
                hash_val = compute_entry_hash(
                    timestamp, level.upper(), category, data_str, prev_hash
                )

                entry = LogEntry(
                    timestamp=timestamp,
                    session_id=self.session_id,
                    level=level.upper(),
                    category=category,
                    source=source_str,
                    data=data_str,
                    hash=hash_val,
                    prev_hash=prev_hash
                )

                # Update the chain head
                self._last_hash = hash_val

            # Enqueue for database writing
            self._queue.put(entry, block=False)
            
            # Trigger real-time watchers (async)
            self.watchers.trigger(entry)

        except queue.Full:
            self.logger.warning("ViraxLog queue is full! Log entry dropped.")
        except Exception as e:
            self.logger.error(f"Critical error during logging: {e}")

    # -------------------------------------------------
    # BACKGROUND PROCESSING
    # -------------------------------------------------

    def _process_queue(self) -> None:
        """Consumes the queue and writes batches to the database."""
        batch: List[LogEntry] = []
        last_commit_time = time.time()

        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                # Wait for an entry, but don't block forever to allow checking stop_event
                entry = self._queue.get(timeout=0.5)
                batch.append(entry)

                # Check if we should commit the current batch
                now = time.time()
                is_batch_full = len(batch) >= self.config.batch_size
                is_timeout = (now - last_commit_time > 2.0) and batch
                
                if is_batch_full or is_timeout:
                    if self._write_batch(batch):
                        batch.clear()
                        last_commit_time = now

            except queue.Empty:
                # Flush remaining logs even if batch size isn't reached
                if batch:
                    self._write_batch(batch)
                    batch.clear()
                continue
            except Exception as e:
                self.logger.error(f"Internal worker error: {e}")

    def _write_batch(self, batch: List[LogEntry]) -> bool:
        """Persists a batch of logs to the database with error handling."""
        try:
            return self.db.insert_log_batch(batch)
        except Exception as e:
            self.logger.error(f"Database batch write failed: {e}")
            return False

    # -------------------------------------------------
    # MONITORING & MAINTENANCE
    # -------------------------------------------------

    def _heartbeat_loop(self) -> None:
        """Background thread that writes a periodic 'alive' signal."""
        while not self._stop_event.is_set():
            try:
                ts = datetime.now(timezone.utc).isoformat()
                self.db.insert_heartbeat(ts, "alive")
                # Sleep in small increments to allow faster shutdown
                for _ in range(self.config.heartbeat_interval):
                    if self._stop_event.is_set(): break
                    time.sleep(1)
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")

    # -------------------------------------------------
    # LIFECYCLE MANAGEMENT
    # -------------------------------------------------

    def shutdown(self) -> None:
        """Graceful shutdown: flushes queue, stops threads, and closes database."""
        self.logger.info("ViraxLog shutdown initiated...")
        self._stop_event.set()

        # Wait for worker to finish processing the remaining queue
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
        
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2.0)

        self.watchers.shutdown()
        self.db.close()
        self.logger.info("ViraxLog shutdown complete.")