#!/usr/bin/env python3
"""
ViraxLog - Audit Module
Advanced tools to verify the integrity and consistency of the log database.
"""

from __future__ import annotations

import logging
import json
from typing import Dict, Any, List, Optional
from contextlib import contextmanager

from .database import DatabaseManager
from .models import ViraxConfig, LogEntry
from .utils.crypto import verify_log_chain

logger = logging.getLogger("ViraxLog.Audit")


class ViraxAuditor:
    """
    Cryptographic auditor for ViraxLog registries.
    Verifies that the hash chain is unbroken and data matches original signatures.
    """

    def __init__(self, config: ViraxConfig):
        self.config = config
        self.db = DatabaseManager(self.config)

    @contextmanager
    def open(self):
        """Context manager for safe database access and cleanup."""
        try:
            yield self
        finally:
            self.close()

    def _rows_to_entries(self, rows: List[dict]) -> List[LogEntry]:
        """
        Converts SQLite rows back into immutable LogEntry objects.
        Note: We keep 'data' as a raw string to ensure hash stability.
        """
        entries = []
        for r in rows:
            entries.append(LogEntry(
                timestamp=r["timestamp"],
                session_id=r["session_id"],
                level=r["level"],
                category=r["category"],
                source=r["source"],
                data=r["data"], # Important: keep serialized string for hashing
                hash=r["hash"],
                prev_hash=r["prev_hash"],
                schema_version=r.get("schema_version", 1)
            ))
        return entries

    def validate_full_chain(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Performs a full or partial integrity check on the log chain.
        
        Args:
            limit: Max number of recent logs to check. If None, audits everything.
        
        Returns:
            Dictionary with status, count, and error details if corruption is found.
        """
        logger.info("Starting cryptographic audit of the registry...")

        try:
            # Fetch records in ascending order to rebuild the chain
            rows = self.db.get_integrity_rows(limit)
        except Exception as e:
            logger.critical(f"Failed to retrieve logs for audit: {e}")
            return {"status": "error", "message": str(e)}

        if not rows:
            logger.info("Audit finished: Database is empty.")
            return {"status": "empty", "count": 0}

        # Convert SQL rows to LogEntry objects
        entries = self._rows_to_entries([dict(r) for r in rows])

        # Determine the starting point for validation
        # If we check the whole DB, the first log's prev_hash should be 'GENESIS'
        # If we check a partial slice, we take the prev_hash of the first entry in our slice
        starting_hash = entries[0].prev_hash

        is_valid, error_index = verify_log_chain(entries, initial_prev_hash=starting_hash)
        
        if is_valid:
            logger.info(f"Audit SUCCESS: {len(entries)} entries verified and intact.")
            return {
                "status": "success", 
                "count": len(entries), 
                "message": "The cryptographic chain is valid."
            }
        else:
            corrupted_log = entries[error_index]
            sql_id = rows[error_index]['id']
            logger.error(f"AUDIT FAILED at index {error_index} (Database ID: {sql_id})")
            
            return {
                "status": "failed",
                "count": len(entries),
                "error_index": error_index,
                "corrupted_db_id": sql_id,
                "details": {
                    "timestamp": corrupted_log.timestamp,
                    "category": corrupted_log.category,
                    "level": corrupted_log.level,
                    "expected_prev_hash": entries[error_index].prev_hash,
                    "found_hash": corrupted_log.hash
                }
            }

    def close(self):
        """Safely closes the database connection."""
        if self.db:
            self.db.close()


def run_audit(db_path: str = "virax_universal.db", limit: Optional[int] = None) -> Dict[str, Any]:
    """Utility function for quick CLI audits or scheduled checks."""
    config = ViraxConfig(db_name=db_path)
    with ViraxAuditor(config).open() as auditor:
        return auditor.validate_full_chain(limit)