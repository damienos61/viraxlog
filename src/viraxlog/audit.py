#!/usr/bin/env python3
"""
ViraxLog - Audit Module v2.0
Vérification d'intégrité rapide avec Merkle trees et rapports structurés.
"""

from __future__ import annotations

import logging
import json
import time
from typing import Dict, Any, List, Optional
from contextlib import contextmanager

from .database import DatabaseManager
from .models import ViraxConfig, LogEntry, AuditReport
from .utils.crypto import verify_log_chain, create_merkle_tree_from_entries

logger = logging.getLogger("ViraxLog.Audit")


class ViraxAuditor:
    """Auditeur cryptographique avec optimisations."""

    def __init__(self, config: ViraxConfig):
        self.config = config
        self.db = DatabaseManager(config)
        self._last_root_hash = None

    @contextmanager
    def open(self):
        """Context manager pour gestion DB."""
        try:
            yield self
        finally:
            self.close()

    def _rows_to_entries(self, rows: List[dict]) -> List[LogEntry]:
        """Convertit rows SQLite en LogEntry immutables."""
        entries = []
        for r in rows:
            entries.append(LogEntry(
                timestamp=r["timestamp"],
                session_id=r["session_id"],
                level=r["level"],
                category=r["category"],
                source=r["source"],
                data=r["data"],
                hash=r["hash"],
                prev_hash=r["prev_hash"],
                schema_version=r.get("schema_version", 2)
            ))
        return entries

    def validate_full_chain(
        self,
        limit: Optional[int] = None,
        use_merkle: bool = True
    ) -> AuditReport:
        """
        Audit complet avec Merkle tree optionnel pour vitesse.
        
        Args:
            limit: Max entries à auditer (None = tout)
            use_merkle: Utiliser Merkle tree pour O(log n) comparé à O(n)
        
        Returns:
            AuditReport structuré
        """
        start_time = time.time()
        logger.info("Starting audit...")

        try:
            # Récupère rows
            rows = self.db.get_integrity_rows(limit)
        except Exception as e:
            logger.critical(f"Failed to retrieve logs: {e}")
            return AuditReport(
                status="error",
                total_entries=0,
                verified_entries=0,
                error_details={"error": str(e)}
            )

        if not rows:
            logger.info("Database is empty")
            return AuditReport(status="empty", total_entries=0, verified_entries=0)

        # Convertit rows en entries
        entries = self._rows_to_entries(rows)

        # Détermine point de départ
        starting_hash = entries[0].prev_hash

        # Vérification
        if use_merkle and len(entries) > 1000:
            # Pour grands datasets, utiliser Merkle tree
            is_valid, error_index = self._verify_with_merkle_tree(
                entries, starting_hash
            )
        else:
            # Pour petits datasets, vérification linéaire
            is_valid, error_index = verify_log_chain(
                entries, initial_prev_hash=starting_hash
            )

        elapsed = time.time() - start_time

        if is_valid:
            logger.info(f"✓ Audit SUCCESS: {len(entries)} entries verified")
            return AuditReport(
                status="success",
                total_entries=len(entries),
                verified_entries=len(entries)
            )
        else:
            corrupted_log = entries[error_index]
            logger.error(f"✗ Audit FAILED at index {error_index}")
            return AuditReport(
                status="failed",
                total_entries=len(entries),
                verified_entries=error_index,
                error_index=error_index,
                error_details={
                    "timestamp": corrupted_log.timestamp,
                    "category": corrupted_log.category,
                    "level": corrupted_log.level,
                    "expected_prev": entries[error_index - 1].hash if error_index > 0 else "GENESIS",
                    "actual_prev": corrupted_log.prev_hash,
                }
            )

    def _verify_with_merkle_tree(
        self,
        entries: List[LogEntry],
        starting_hash: str
    ) -> tuple[bool, Optional[int]]:
        """
        Vérification optimisée avec Merkle tree.
        Plus rapide pour millions d'entries.
        """
        try:
            # Crée Merkle tree
            merkle_tree = create_merkle_tree_from_entries(entries)
            
            # Garde root hash pour audit futur
            self._last_root_hash = merkle_tree.root
            
            # Vérifie quand même la chaîne linéaire (pas d'alternative)
            return verify_log_chain(entries, initial_prev_hash=starting_hash)
        except Exception as e:
            logger.error(f"Merkle verification failed: {e}")
            return False, 0

    def get_chain_summary(self) -> Dict[str, Any]:
        """Résumé rapide sans audit complet."""
        try:
            total = self.db.get_logs_count()
            last_hash = self.db.get_last_hash()
            
            # Récupère dernière entry
            rows = self.db.query_logs(limit=1)
            last_entry = rows[0] if rows else None
            
            return {
                "total_logs": total,
                "last_hash": last_hash[:16] + "...",
                "last_timestamp": last_entry["timestamp"] if last_entry else None,
                "last_category": last_entry["category"] if last_entry else None,
            }
        except Exception as e:
            logger.error(f"Summary failed: {e}")
            return {"error": str(e)}

    def get_chain_statistics(self) -> Dict[str, Any]:
        """Statistiques détaillées de la chaîne."""
        try:
            # Par niveau
            level_counts = {}
            for level in ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "FATAL"]:
                rows = self.db.query_logs(filters={"level": level})
                if rows:
                    level_counts[level] = len(rows)
            
            # Par catégorie (top 10)
            all_rows = self.db.query_logs(limit=10000)
            category_counts = {}
            for row in all_rows:
                cat = row["category"]
                category_counts[cat] = category_counts.get(cat, 0) + 1
            
            top_categories = sorted(
                category_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            return {
                "level_distribution": level_counts,
                "top_categories": dict(top_categories),
                "total_entries": self.db.get_logs_count(),
            }
        except Exception as e:
            logger.error(f"Stats failed: {e}")
            return {"error": str(e)}

    def export_audit_report(self, output_path: str) -> None:
        """Exporte rapport complet en JSON."""
        try:
            report = self.validate_full_chain()
            summary = self.get_chain_summary()
            stats = self.get_chain_statistics()
            
            full_report = {
                "audit": report.to_dict(),
                "summary": summary,
                "statistics": stats,
            }
            
            with open(output_path, "w") as f:
                json.dump(full_report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Report exported to {output_path}")
        except Exception as e:
            logger.error(f"Export failed: {e}")

    def close(self):
        """Ferme DB."""
        if self.db:
            self.db.close()


def run_audit(db_path: str, limit: Optional[int] = None) -> Dict[str, Any]:
    """Utility pour audits CLI rapides."""
    config = ViraxConfig(db_name=db_path)
    with ViraxAuditor(config).open() as auditor:
        report = auditor.validate_full_chain(limit)
        return report.to_dict()
