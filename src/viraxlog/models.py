#!/usr/bin/env python3
"""
ViraxLog - Models Module v2.0
Structures de données immutables améliorées avec validation stricte et optimisations mémoire.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, Optional, Literal
from datetime import datetime, timezone
from enum import Enum

from .utils.crypto import compute_entry_hash

SCHEMA_VERSION = 2
MAX_DATA_SIZE = 1_000_000  # 1MB max per log


class LogLevel(str, Enum):
    """Niveaux de log standardisés."""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


@dataclass(frozen=True, slots=True)
class LogEntry:
    """
    Entrée de log immuable avec intégrité garantie.
    Slots réduit la mémoire pour millions d'entrées.
    """
    timestamp: str
    session_id: str
    level: str
    category: str
    source: str
    data: str
    hash: str
    prev_hash: str
    schema_version: int = field(default=SCHEMA_VERSION)

    def to_dict(self) -> Dict[str, Any]:
        """Conversion dict avec gestion stricte du type."""
        return asdict(self)

    def to_json(self) -> str:
        """Export JSON optimisé."""
        return json.dumps(self.to_dict(), separators=(',', ':'), ensure_ascii=False)

    @staticmethod
    def serialize_data(data: Any, max_size: int = MAX_DATA_SIZE) -> str:
        """
        Sérialisation déterministe avec vérification de taille.
        Utilise un ordre fixe pour garantir la stabilité du hash.
        """
        try:
            if data is None:
                return "{}"
            
            # Validation taille préalable
            temp_json = json.dumps(
                data,
                default=str,
                separators=(',', ':'),
                sort_keys=True,
                ensure_ascii=False
            )
            
            if len(temp_json.encode('utf-8')) > max_size:
                raise ValueError(f"Data exceeds maximum size of {max_size} bytes")
            
            return temp_json
            
        except Exception as e:
            # Fallback sécurisé
            return json.dumps({
                "error": "serialization_failed",
                "details": str(e)[:200],
                "type": type(data).__name__
            }, ensure_ascii=False)

    @classmethod
    def create(
        cls,
        session_id: str,
        level: str,
        category: str,
        source: str,
        data: Any,
        prev_hash: str,
        timestamp: Optional[str] = None,
        schema_version: int = SCHEMA_VERSION
    ) -> LogEntry:
        """Factory avec validation complète."""
        # Validation basique
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id must be non-empty string")
        if not isinstance(level, str):
            raise ValueError("level must be string")
        if not isinstance(category, str) or not category:
            raise ValueError("category must be non-empty string")
        
        # Timestamp
        ts = timestamp or datetime.now(timezone.utc).isoformat(timespec='seconds')
        
        # Sérialisation données
        data_str = cls.serialize_data(data)
        
        # Hash cryptographique
        entry_hash = compute_entry_hash(
            ts, level.upper(), category, data_str, prev_hash
        )
        
        return cls(
            timestamp=ts,
            session_id=session_id,
            level=level.upper(),
            category=category,
            source=source,
            data=data_str,
            hash=entry_hash,
            prev_hash=prev_hash,
            schema_version=schema_version
        )


@dataclass
class ViraxConfig:
    """Configuration centralisée avec valeurs optimales par défaut."""
    db_name: str = "virax.db"
    log_level: str = "INFO"
    
    # Tuning performance
    max_workers: int = 8
    batch_size: int = 100  # Augmenté pour WAL
    queue_maxsize: int = 50000  # Augmenté
    
    # Heartbeat
    enable_heartbeat: bool = True
    heartbeat_interval: int = 60
    
    # Retention & maintenance
    retention_days: int = 90
    auto_vacuum_enabled: bool = True
    auto_vacuum_interval: int = 3600
    
    # Cache & optimization
    cache_size_mb: int = 256
    enable_compression: bool = False
    
    # Sécurité
    enable_hmac: bool = True
    encryption_key: Optional[str] = None
    
    # Watchers
    max_watcher_threads: int = 10
    
    # Backends alternatifs (v2.0+)
    backend: Literal["sqlite", "postgres"] = "sqlite"
    postgres_dsn: Optional[str] = None
    
    def validate(self) -> None:
        """Validation de configuration stricte."""
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.queue_maxsize < self.batch_size:
            raise ValueError("queue_maxsize must be >= batch_size")
        if self.max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if self.heartbeat_interval < 10:
            raise ValueError("heartbeat_interval must be >= 10 seconds")
        if self.backend == "postgres" and not self.postgres_dsn:
            raise ValueError("postgres_dsn required when backend='postgres'")


@dataclass(frozen=True, slots=True)
class AuditReport:
    """Rapport d'audit structuré."""
    status: Literal["success", "failed", "error", "empty"]
    total_entries: int
    verified_entries: int
    error_index: Optional[int] = None
    error_details: Optional[Dict[str, Any]] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """Snapshot de métriques système."""
    timestamp: str
    total_logs: int
    queue_size: int
    memory_mb: float
    cpu_percent: float
    write_latency_ms: float
    audit_latency_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
