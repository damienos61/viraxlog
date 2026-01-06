from viraxlog.utils.crypto import compute_entry_hash, verify_log_chain
from viraxlog.models import LogEntry

def test_chain_break():
    # 1. On définit la donnée une seule fois pour être sûr
    test_data = '"data"' 
    
    # 2. On calcule le hash correct
    h1 = compute_entry_hash("ts", "INFO", "CAT", test_data, "GENESIS")
    
    # 3. On crée l'entrée avec cette EXACTE donnée
    e1 = LogEntry(
        timestamp="ts",
        session_id="S1",
        level="INFO",
        category="CAT",
        source="src",
        data=test_data, # <--- Doit être identique à test_data au-dessus
        prev_hash="GENESIS",
        hash=h1
    )
    
    # 4. Le deuxième log est volontairement corrompu (mauvais prev_hash)
    e2 = LogEntry("ts", "S1", "INFO", "CAT", "src", test_data, "hash2", "WRONG_HASH")
    
    is_valid, error_idx = verify_log_chain([e1, e2], initial_prev_hash="GENESIS")
    assert is_valid is False
    assert error_idx == 1 # L'erreur sera bien détectée au 2ème élément