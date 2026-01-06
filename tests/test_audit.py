import sqlite3
import time
import pytest
from viraxlog.audit import ViraxAuditor
from viraxlog.models import ViraxConfig
from viraxlog.core import ViraxLogger

def test_audit_detection_of_corruption(tmp_path):
    # Utilisation d'un chemin temporaire propre pour le test
    db_path = str(tmp_path / "audit_test.db")
    config = ViraxConfig(db_name=db_path, batch_size=1)
    
    # 1. Créer une chaîne de logs valide
    logger = ViraxLogger(config)
    logger.log("INFO", "AUDIT", "Valid log 1")
    logger.log("INFO", "AUDIT", "Valid log 2")
    
    # Laisser le temps au worker de traiter la queue
    time.sleep(0.5)
    logger.shutdown()

    # 2. Corruption manuelle de la base SQL
    # On ouvre la base directement pour simuler une attaque/modification malveillante
    conn = sqlite3.connect(db_path)
    
    # On modifie la donnée du log ID=2. 
    # Note: On met du JSON valide pour que json.loads ne crash pas, 
    # mais le contenu ne correspondra plus au Hash calculé à l'origine.
    corrupted_data = '"HACKED_CONTENT"' 
    conn.execute("UPDATE registry SET data = ? WHERE id = 2", (corrupted_data,))
    conn.commit()
    conn.close()

    # 3. Lancer l'audit pour vérifier si le système détecte la fraude
    auditor = ViraxAuditor(config)
    report = auditor.validate_full_chain()
    
    # Vérifications
    assert report["status"] == "failed", "L'audit aurait dû détecter une corruption."
    assert report["corrupted_db_id"] == 2, "L'ID corrompu détecté devrait être le 2."
    
    # Nettoyage
    auditor.close()

def test_audit_empty_db(tmp_path):
    """Vérifie que l'audit gère correctement une base vide."""
    db_path = str(tmp_path / "empty.db")
    config = ViraxConfig(db_name=db_path)
    
    auditor = ViraxAuditor(config)
    report = auditor.validate_full_chain()
    
    assert report["status"] == "empty"
    auditor.close()