#!/usr/bin/env python3
"""
ViraxLog - Database Module
Append-only SQLite persistence engine, secured and optimized for high-integrity logs.
"""

from __future__ import annotations

import json
import sqlite3
import logging
import threading
from typing import List, Dict, Any, Optional, Iterable
from .models import LogEntry, ViraxConfig


class DatabaseManager:
    """
    Low-level storage engine.
    Ensures:
    - Append-only behavior
    - Atomicity through manual transactions
    - Chain integrity support
    """

    def __init__(self, config: ViraxConfig) -> None:
        self.config = config
        self.logger = logging.getLogger("ViraxLog.Database")
        self._lock = threading.Lock() # Ensure thread-safe write access

        # Connect with WAL mode support and manual transaction control
        self.conn = sqlite3.connect(
            self.config.db_name,
            check_same_thread=False,
            isolation_level=None  
        )
        self.conn.row_factory = sqlite3.Row

        self._initialize_database()

    # -------------------------------------------------
    # INITIALIZATION & SCHEMA
    # -------------------------------------------------

    def _initialize_database(self) -> None:
        """Sets up the database structure and performance pragmas."""
        try:
            self._apply_pragmas()
            self._create_schema()
            self._create_indexes()
        except sqlite3.Error as e:
            self.logger.critical(f"Database initialization failed: {e}")
            raise

    def _apply_pragmas(self) -> None:
        """Optimizes SQLite for logging workloads (Write-Ahead Logging)."""
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        # Set cache size to 2GB (approx)
        self.conn.execute(f"PRAGMA cache_size=-{2000 * 1024};") 

    def _create_schema(self) -> None:
        """Creates the main registry and heartbeat tables."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schema_version INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    level TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source TEXT NOT NULL,
                    data TEXT NOT NULL,
                    hash TEXT NOT NULL UNIQUE,
                    prev_hash TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    CHECK (hash != prev_hash)
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS heartbeat (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL
                )
            """)

    def _create_indexes(self) -> None:
        """Generates indexes for fast auditing and querying."""
        with self.conn:
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reg_chain ON registry(prev_hash, hash)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reg_cat_lvl ON registry(category, level)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reg_ts ON registry(timestamp)"
            )

    # -------------------------------------------------
    # WRITE OPERATIONS
    # -------------------------------------------------

    def insert_log_batch(self, entries: List[LogEntry]) -> bool:
        """
        Inserts a list of LogEntry objects using a single atomic transaction.
        Returns True if successful, False otherwise.
        """
        if not entries:
            return True

        sql = """
            INSERT INTO registry
            (schema_version, timestamp, session_id, level, category, source, data, hash, prev_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        payload = []
        for e in entries:
            # Data is already serialized by LogEntry.create, but we ensure string type
            data_str = e.data if isinstance(e.data, str) else json.dumps(e.data, ensure_ascii=False)
            
            payload.append((
                e.schema_version, e.timestamp, e.session_id, e.level,
                e.category, e.source, data_str, e.hash, e.prev_hash
            ))

        with self._lock: # Thread-safe block
            try:
                self.conn.execute("BEGIN")
                self.conn.executemany(sql, payload)
                self.conn.execute("COMMIT")
                return True
            except sqlite3.Error as e:
                self.conn.execute("ROLLBACK")
                self.logger.error(f"Batch insert failed: {e}")
                return False

    def insert_heartbeat(self, timestamp: str, status: str) -> None:
        """Logs a system heartbeat to verify logger availability."""
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO heartbeat (timestamp, status) VALUES (?, ?)",
                    (timestamp, status),
                )
        except sqlite3.Error as e:
            self.logger.error(f"Heartbeat insert error: {e}")

    # -------------------------------------------------
    # READ OPERATIONS
    # -------------------------------------------------

    def get_last_hash(self) -> str:
        """Retrieves the most recent hash to chain the next entry."""
        row = self.conn.execute(
            "SELECT hash FROM registry ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row["hash"] if row else "GENESIS"

    def query_logs(self, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Queries logs based on dynamic filters (category, level, time range)."""
        sql = "SELECT * FROM registry WHERE 1=1"
        params = []

        for key in ["category", "level"]:
            if filters.get(key):
                sql += f" AND {key} = ?"
                params.append(filters[key])

        if filters.get("since"):
            sql += " AND timestamp >= ?"
            params.append(filters["since"])

        if filters.get("until"):
            sql += " AND timestamp <= ?"
            params.append(filters["until"])

        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    # -------------------------------------------------
    # INTEGRITY & MAINTENANCE
    # -------------------------------------------------

    def get_integrity_rows(self, limit: Optional[int] = None) -> List[sqlite3.Row]:
        """Fetches rows for auditing in chronological order (ASC)."""
        if limit:
            # Get last N rows then reverse for ASC audit flow
            rows = self.conn.execute(
                "SELECT * FROM registry ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return rows[::-1] 
            
        return self.conn.execute(
            "SELECT * FROM registry ORDER BY id ASC"
        ).fetchall()

    def cleanup(self) -> None:
        """Deletes old heartbeats and optimizes database file."""
        try:
            with self.conn:
                self.conn.execute(
                    "DELETE FROM heartbeat WHERE timestamp < datetime('now', ?) ",
                    (f"-{self.config.retention_days} days",),
                )
            self.conn.execute("PRAGMA optimize;")
        except sqlite3.Error as e:
            self.logger.error(f"Cleanup error: {e}")

    def vacuum(self) -> None:
        """Manually compacts the database file (resource intensive)."""
        try:
            self.conn.execute("VACUUM;")
        except sqlite3.Error as e:
            self.logger.error(f"Vacuum failed: {e}")

    def close(self) -> None:
        """Safely closes the database connection."""
        if self.conn:
            self.conn.close()

    def get_logs_count(self) -> int:
        """Retourne le nombre total de logs dans la base."""
        res = self.conn.execute("SELECT COUNT(*) FROM registry").fetchone()
        return res[0] if res else 0