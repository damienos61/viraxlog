import os
import pytest
from viraxlog import interface as vlog
from viraxlog.models import ViraxConfig

def test_full_integration(tmp_path):
    # On crée une DB temporaire
    db_file = tmp_path / "test.db"
    config = ViraxConfig(db_name=str(db_file), batch_size=1)
    
    vlog.initialize(config=config)
    vlog.info("TEST", "Message intégré")
    
    # On force l'arrêt pour flusher les logs
    vlog.stop()
    
    assert os.path.exists(db_file)