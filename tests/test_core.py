import time
import sqlite3
import pytest
from viraxlog.core import ViraxLogger
from viraxlog.models import ViraxConfig

def test_logger_async_processing(tmp_path):
    db_path = str(tmp_path / "core_test.db")
    config = ViraxConfig(db_name=db_path, batch_size=2)
    logger = ViraxLogger(config)

    # On utilise des messages différents. 
    # Cela garantit des hashs uniques sans conflit de base de données.
    logger.log("INFO", "CORE", "Premier message de test")
    logger.log("INFO", "CORE", "Deuxième message de test")
    logger.log("INFO", "CORE", "Troisième message de test")

    # On laisse le temps au worker de traiter la file
    time.sleep(0.5)

    # On ferme le logger (ce qui force l'écriture du 3ème message restant)
    logger.shutdown()

    # On vérifie manuellement le résultat dans la base
    conn = sqlite3.connect(db_path)
    res = conn.execute("SELECT COUNT(*) FROM registry").fetchone()
    final_count = res[0]
    conn.close()

    assert final_count == 3, f"Attendu: 3 logs, Trouvé: {final_count}"