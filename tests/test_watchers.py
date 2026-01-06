import time
from viraxlog.watchers import WatcherManager
from viraxlog.models import LogEntry

def test_watcher_trigger():
    manager = WatcherManager(max_workers=1)
    results = []

    def my_callback(entry):
        results.append(entry.category)

    manager.add_watcher("SECURITY", my_callback)
    
    entry = LogEntry("ts", "S1", "ERROR", "SECURITY", "src", "data", "h", "p")
    manager.trigger(entry)
    
    time.sleep(0.1) # Laisse le temps au thread de s'exécuter
    assert "SECURITY" in results
    manager.shutdown()