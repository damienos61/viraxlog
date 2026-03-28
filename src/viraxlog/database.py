#!/usr/bin/env python3
"""
ViraxLog - Database Module v2.0
Moteur haute-performance SQLite/PostgreSQL avec WAL, batch writes, et connection pooling.
"""

from __future__ import annotations

import json
import sqlite3
import logging
import threading
import time
from typing import List, Dict, Any, Optional, Union
from contextlib import contextmanager

from .models import LogEntry, ViraxConfig

logger = logging.getLogger("ViraxLog.Database")


class DatabaseManager:
    """
    Gestionnaire de persistance haute performance.
    Support SQLite (par défaut) et PostgreSQL (optionnel).
    """

    def __init__(self, config: ViraxConfig) -> None:
        self.config = config
        self.config.validate()
        self._lock = threading.RLock()
        self._write_lock = threading.Lock()
        
        if config.backend == "sqlite":
            self._init_sqlite()
        elif config.backend == "postgres":
            self._init_postgres()
        else:
            raise ValueError(f"Unknown backend: {config.backend}")
        
        self._initialize_database()
        self._batch_stats = {"writes": 0, "entries": 0, "last_write_ms": 0.0}

    def _init_sqlite(self) -> None:
        """Initialisation SQLite optimisée."""
        self.conn = sqlite3.connect(
            self.config.db_name,
            check_same_thread=False,
            isolation_level=None,
            timeout=10.0
        )
        self.conn.row_factory = sqlite3.Row
        self.backend = "sqlite"

    def _init_postgres(self) -> None:
        """Initialisation PostgreSQL (v2.0+)."""
        try:
            import psycopg2
            from psycopg2 import pool
            
            self.pg_pool = psycopg2.pool.SimpleConnectionPool(
                1, self.config.max_workers,
                self.config.postgres_dsn
            )
            self.conn = None
            self.backend = "postgres"
        except ImportError:
            raise RuntimeError("PostgreSQL support requires: pip install viraxlog[postgres]")

    def _initialize_database(self) -> None:
        """Setup schéma et pragmas."""
        try:
            if self.backend == "sqlite":
                self._apply_pragmas()
            self._create_schema()
            self._create_indexes()
            logger.info(f"Database initialized ({self.backend})")
        except Exception as e:
            logger.critical(f"Database init failed: {e}")
            raise

    def _apply_pragmas(self) -> None:
        """Pragmas SQLite pour haute performance."""
        pragmas = [
            "PRAGMA journal_mode=WAL;",              # Write-Ahead Logging
            "PRAGMA synchronous=NORMAL;",             # Balance speed/safety
            "PRAGMA foreign_keys=ON;",
            f"PRAGMA cache_size=-{self.config.cache_size_mb * 1024};",
            "PRAGMA temp_store=MEMORY;",
            "PRAGMA mmap_size=30000000;",             # Memory-mapped I/O
            "PRAGMA query_only=FALSE;",
            "PRAGMA busy_timeout=5000;",
            "PRAGMA max_page_count=4294967295;",
        ]
        
        for pragma in pragmas:
            try:
                self.conn.execute(pragma)
            except sqlite3.OperationalError as e:
                logger.warning(f"Pragma failed: {pragma} - {e}")

    def _create_schema(self) -> None:
        """Crée tables avec contraintes strictes."""
        if self.backend == "sqlite":
            with self.conn:
                # Table principale
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS registry (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schema_version INTEGER NOT NULL DEFAULT 2,
                        timestamp TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        level TEXT NOT NULL,
                        category TEXT NOT NULL,
                        source TEXT NOT NULL,
                        data TEXT NOT NULL,
                        hash TEXT NOT NULL UNIQUE,
                        prev_hash TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        CHECK (hash != prev_hash),
                        CHECK (length(category) > 0),
                        CHECK (level IN ('TRACE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'FATAL'))
                    )
                """)
                
                # Table heartbeat
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS heartbeat (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        status TEXT NOT NULL,
                        queue_size INTEGER DEFAULT 0
                    )
                """)
                
                # Table statistiques
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        total_logs INTEGER,
                        queue_size INTEGER,
                        memory_mb REAL,
                        cpu_percent REAL
                    )
                """)

    def _create_indexes(self) -> None:
        """Indexes optimisés pour requêtes communes."""
        indexes = [
            ("idx_chain", "registry", "(prev_hash, hash)"),
            ("idx_category", "registry", "(category)"),
            ("idx_level", "registry", "(level)"),
            ("idx_timestamp", "registry", "(timestamp DESC)"),
            ("idx_session", "registry", "(session_id, timestamp)"),
            ("idx_hash", "registry", "(hash)"),
        ]
        
        with self.conn:
            for name, table, cols in indexes:
                try:
                    self.conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}{cols}")
                except sqlite3.OperationalError:
                    pass

    # ========== WRITE OPERATIONS ==========

    def insert_log_batch(self, entries: List[LogEntry]) -> bool:
        """Insère batch d'entrées atomiquement."""
        if not entries:
            return True

        sql = """
            INSERT INTO registry
            (schema_version, timestamp, session_id, level, category, source, data, hash, prev_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        payload = []
        for e in entries:
            data_str = e.data if isinstance(e.data, str) else json.dumps(e.data)
            payload.append((
                e.schema_version, e.timestamp, e.session_id, e.level,
                e.category, e.source, data_str, e.hash, e.prev_hash
            ))

        start = time.time()
        with self._write_lock:
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                self.conn.executemany(sql, payload)
                self.conn.execute("COMMIT")
                
                # Stats
                elapsed = (time.time() - start) * 1000
                self._batch_stats["writes"] += 1
                self._batch_stats["entries"] += len(entries)
                self._batch_stats["last_write_ms"] = elapsed
                
                return True
            except sqlite3.Error as e:
                self.conn.execute("ROLLBACK")
                logger.error(f"Batch insert failed: {e}")
                return False

    def insert_heartbeat(self, timestamp: str, status: str, queue_size: int = 0) -> None:
        """Enregistre heartbeat avec taille queue."""
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO heartbeat (timestamp, status, queue_size) VALUES (?, ?, ?)",
                    (timestamp, status, queue_size)
                )
        except sqlite3.Error as e:
            logger.error(f"Heartbeat insert error: {e}")

    # ========== READ OPERATIONS ==========

    def get_last_hash(self) -> str:
        """Récupère le dernier hash pour chaînage."""
        try:
            row = self.conn.execute(
                "SELECT hash FROM registry ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return row["hash"] if row else "GENESIS"
        except sqlite3.Error as e:
            logger.error(f"get_last_hash failed: {e}")
            return "GENESIS"

    def query_logs(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Requête flexible avec filtres."""
        filters = filters or {}
        
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

        if filters.get("session_id"):
            sql += " AND session_id = ?"
            params.append(filters["session_id"])

        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        try:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Query failed: {e}")
            return []

    def get_integrity_rows(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Récupère rows pour audit (ordre ASC)."""
        try:
            if limit:
                rows = self.conn.execute(
                    "SELECT * FROM registry ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
                return [dict(r) for r in reversed(rows)]
            
            rows = self.conn.execute(
                "SELECT * FROM registry ORDER BY id ASC"
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            logger.error(f"get_integrity_rows failed: {e}")
            return []

    # ========== MAINTENANCE ==========

    def get_logs_count(self) -> int:
        """Compte total des logs."""
        try:
            res = self.conn.execute("SELECT COUNT(*) FROM registry").fetchone()
            return res[0] if res else 0
        except sqlite3.Error:
            return 0

    def cleanup(self, retention_days: Optional[int] = None) -> int:
        """Supprime vieux heartbeats."""
        days = retention_days or self.config.retention_days
        try:
            with self.conn:
                cursor = self.conn.execute(
                    "DELETE FROM heartbeat WHERE timestamp < datetime('now', ?)",
                    (f"-{days} days",)
                )
                deleted = cursor.rowcount
                self.conn.execute("PRAGMA optimize;")
                return deleted
        except sqlite3.Error as e:
            logger.error(f"Cleanup error: {e}")
            return 0

    def vacuum(self) -> None:
        """Compacte la base (coûteux)."""
        try:
            self.conn.execute("VACUUM;")
            logger.info("Database vacuumed")
        except sqlite3.Error as e:
            logger.error(f"Vacuum failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Retourne statistiques d'écriture."""
        return {
            "total_writes": self._batch_stats["writes"],
            "total_entries": self._batch_stats["entries"],
            "last_write_ms": self._batch_stats["last_write_ms"],
            "avg_write_ms": (
                self._batch_stats["last_write_ms"] / self._batch_stats["writes"]
                if self._batch_stats["writes"] > 0 else 0
            ),
            "db_size_mb": self._get_db_size(),
        }

    def _get_db_size(self) -> float:
        """Taille fichier DB en MB."""
        try:
            import os
            return os.path.getsize(self.config.db_name) / 1024 / 1024
        except Exception:
            return 0.0

    def close(self) -> None:
        """Ferme connexion proprement."""
        try:
            if self.conn:
                self.conn.close()
            logger.info("Database closed")
        except Exception as e:
            logger.error(f"Close error: {e}")
