import pytest
from viraxlog.models import ViraxConfig, LogEntry

def test_config_defaults():
    """Vérifie que les valeurs par défaut de la configuration sont correctes."""
    config = ViraxConfig()
    # On vérifie 50 car c'est la valeur actuelle dans ton code source
    assert config.batch_size == 50
    assert config.db_name == "virax_universal.db"

def test_log_entry_serialization():
    """Vérifie qu'une LogEntry accepte et stocke correctement les données sérialisées."""
    entry = LogEntry(
        timestamp="2024-01-01", 
        session_id="S1", 
        level="INFO",
        category="CAT", 
        source="src", 
        data='{"key": "val"}',  # On passe une string JSON directe
        hash="h1", 
        prev_hash="h0"
    )
    
    # Vérifie que la donnée est bien traitée comme une chaîne (string)
    assert isinstance(entry.data, str)
    # Vérifie que le contenu JSON est cohérent
    assert '"key"' in entry.data
    assert '"val"' in entry.data