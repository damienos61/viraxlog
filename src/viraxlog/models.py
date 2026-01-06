#!/usr/bin/env python3
"""
ViraxLog - Models Module
Defines immutable data structures and logging contracts.
"""

import json
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from .utils.crypto import compute_entry_hash

# Current database schema version for future migrations
SCHEMA_VERSION = 1 

@dataclass(frozen=True, slots=True)
class LogEntry:
    """
    Represents a unique and immutable log entry.
    The 'frozen=True' attribute ensures the object cannot be modified 
    after creation, which is vital for cryptographic integrity.
    'slots=True' optimizes memory usage for high-volume logging.
    """
    timestamp: str
    session_id: str
    level: str
    category: str
    source: str
    data: str  # Data is stored as a serialized JSON string
    hash: str
    prev_hash: str
    schema_version: int = field(default=SCHEMA_VERSION)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the entry to a dictionary for SQLite or JSON export."""
        return asdict(self)

    @staticmethod
    def serialize_data(data: Any) -> str:
        """
        Transforms any data into a deterministic JSON string.
        Uses ensure_ascii=False to support UTF-8 characters properly.
        """
        try:
            if data is None:
                data = {}
            return json.dumps(
                data, 
                default=str, 
                separators=(',', ':'), 
                sort_keys=True,
                ensure_ascii=False
            )
        except Exception as e:
            # Fallback in case of extreme serialization failure
            return json.dumps({
                "error": "serialization_failed", 
                "details": str(e),
                "raw": str(data)
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
        timestamp: Optional[str] = None
    ) -> "LogEntry":
        """
        Factory method to create a LogEntry with automatic hash computation.
        """
        # Use timezone-aware UTC datetime
        ts = timestamp or datetime.now(timezone.utc).isoformat(timespec='seconds')
        
        # Ensure data is a stable string for hashing
        data_str = cls.serialize_data(data)
        
        # Calculate cryptographic fingerprint
        entry_hash = compute_entry_hash(ts, level, category, data_str, prev_hash)
        
        return cls(
            timestamp=ts,
            session_id=session_id,
            level=level,
            category=category,
            source=source,
            data=data_str,
            hash=entry_hash,
            prev_hash=prev_hash,
            schema_version=SCHEMA_VERSION
        )

@dataclass
class ViraxConfig:
    """
    Centralized configuration for the ViraxLog instance.
    """
    db_name: str = "virax_universal.db"
    log_level: str = "INFO"
    max_workers: int = 10
    batch_size: int = 50          # Number of logs before a SQL commit
    queue_maxsize: int = 10000    # Maximum logs in memory before blocking
    enable_heartbeat: bool = True
    heartbeat_interval: int = 60  # Seconds between heartbeat logs
    retention_days: int = 30      # Default log retention period