from viraxlog.utils.helpers import get_caller_context, sanitize_data
from datetime import datetime

def test_caller_context():
    # On appelle la fonction et on vérifie si elle nous "voit"
    ctx = get_caller_context(depth=1)
    assert "test_helpers.py" in ctx["source"]
    assert ctx["function"] == "test_caller_context"

def test_sanitize_complex_data():
    now = datetime.now()
    complex_input = {
        "date": now,
        "bytes": b"\xff\x00",
        "nested": {"list": [1, 2, {3}]}
    }
    clean = sanitize_data(complex_input)
    
    assert isinstance(clean["date"], str) # Converti en ISO string
    assert clean["bytes"] == "ff00"       # Converti en hex
    assert isinstance(clean["nested"]["list"][2], list) # Set converti en list