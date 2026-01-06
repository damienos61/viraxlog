import pytest
import sqlite3
from viraxlog.database import DatabaseManager
from viraxlog.models import ViraxConfig, LogEntry

@pytest.fixture
def db_manager():
    config = ViraxConfig(db_name=":memory:")
    db = DatabaseManager(config)
    yield db
    db.close()

def test_db_init(db_manager):
    # Vérifie que la table existe
    res = db_manager.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='registry'").fetchone()
    assert res is not None

def test_insert_batch(db_manager):
    entry = LogEntry("ts", "S1", "INFO", "CAT", "src", "data", "h1", "h0")
    db_manager.insert_log_batch([entry])
    
    row = db_manager.conn.execute("SELECT hash FROM registry").fetchone()
    assert row['hash'] == "h1"