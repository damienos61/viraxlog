import pytest
import os
from viraxlog.models import ViraxConfig
from viraxlog.core import ViraxLogger

@pytest.fixture
def temp_config(tmp_path):
    """
    Fournit une configuration pointant vers une base de données temporaire.
    """
    db_path = str(tmp_path / "virax_test.db")
    return ViraxConfig(
        db_name=db_path,
        batch_size=1,           # On réduit le batch pour que les tests soient instantanés
        enable_heartbeat=False  # On désactive le heartbeat pour éviter les threads parasites
    )

@pytest.fixture
def temp_logger(temp_config):
    """
    Fournit une instance de ViraxLogger prête à l'emploi.
    S'assure que le moteur est éteint proprement après chaque test.
    """
    logger = ViraxLogger(temp_config, session_id="TEST-SESSION")
    yield logger
    
    # Nettoyage après le test
    logger.shutdown()
    
    # Optionnel : On s'assure que le fichier DB est supprimé pour le test suivant
    if os.path.exists(temp_config.db_name):
        try:
            os.remove(temp_config.db_name)
        except PermissionError:
            pass # Parfois Windows bloque le fichier un court instant