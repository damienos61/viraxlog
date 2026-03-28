#!/usr/bin/env python3
"""
ViraxLog - Helpers Module v2.0
Utilitaires système, introspection stack, et sanitization avancée.
"""

from __future__ import annotations

import os
import sys
import threading
import traceback
import json
from datetime import datetime, date
from typing import Dict, Any, Optional, List
import psutil

# ========== STACK INTROSPECTION ==========

def get_caller_context(depth: int = 2, include_full_path: bool = False) -> Dict[str, Any]:
    """
    Introspection stack rapide avec sys._getframe (plus rapide qu'inspect.stack()).
    Récupère contexte appelant: fichier, ligne, fonction, thread.
    """
    try:
        frame = sys._getframe(depth)
        code = frame.f_code
        
        filename = code.co_filename
        if not include_full_path:
            filename = os.path.basename(filename)

        return {
            "source": f"{filename}:{frame.f_lineno}",
            "function": code.co_name or "unknown",
            "module": frame.f_globals.get("__name__", "unknown"),
            "thread_name": threading.current_thread().name,
            "thread_id": threading.get_ident(),
            "process_id": os.getpid()
        }
    except (ValueError, AttributeError):
        return {
            "source": "unknown",
            "function": "unknown",
            "module": "unknown",
            "thread_name": threading.current_thread().name,
            "thread_id": threading.get_ident(),
            "process_id": os.getpid()
        }


def format_source_string(context: Dict[str, Any], include_thread: bool = False) -> str:
    """Formate contexte en string compact: 'main.py:42 [start_app]'"""
    base = f"{context.get('source')} [{context.get('function')}]"
    if include_thread:
        t_name = context.get('thread_name')
        if t_name:
            base += f" ({t_name})"
    return base


# ========== DATA SANITIZATION ==========

def sanitize_data(data: Any, max_depth: int = 5, _current_depth: int = 0) -> Any:
    """
    Nettoie données avant sérialisation.
    Gère: dicts, listes, datetime, bytes, objets custom.
    Limite profondeur pour éviter stack overflow.
    """
    if _current_depth > max_depth:
        return "[Max Depth Exceeded]"

    # Types primitifs (passthrough)
    if isinstance(data, (str, int, float, bool, type(None))):
        return data

    # Types temporels
    if isinstance(data, (datetime, date)):
        return data.isoformat()

    # Données binaires (en hex)
    if isinstance(data, (bytes, bytearray)):
        return data.hex()

    # Dictionnaires
    if isinstance(data, dict):
        return {
            str(k): sanitize_data(v, max_depth, _current_depth + 1)
            for k, v in data.items()
        }

    # Collections
    if isinstance(data, (list, tuple, set)):
        return [sanitize_data(item, max_depth, _current_depth + 1) for item in data]

    # Objets avec __dict__
    if hasattr(data, "__dict__"):
        return sanitize_data(vars(data), max_depth, _current_depth + 1)

    # Fallback: string representation
    return str(data)


def safe_json_dump(obj: Any, max_size: int = 1_000_000) -> str:
    """
    Sérialisation JSON sûre avec limite de taille.
    Raise si trop gros.
    """
    try:
        result = json.dumps(obj, default=str, separators=(',', ':'), ensure_ascii=False)
        if len(result.encode('utf-8')) > max_size:
            raise ValueError(f"JSON exceeds {max_size} bytes")
        return result
    except Exception as e:
        return json.dumps({
            "error": "json_dump_failed",
            "reason": str(e),
            "type": type(obj).__name__
        }, ensure_ascii=False)


# ========== SYSTEM INFO ==========

def get_process_memory_mb() -> float:
    """Retourne mémoire process actuelle en MB."""
    try:
        process = psutil.Process(os.getpid())
        return round(process.memory_info().rss / 1024 / 1024, 2)
    except Exception:
        return 0.0


def get_process_cpu_percent() -> float:
    """Retourne CPU % du process (non-blocking)."""
    try:
        process = psutil.Process(os.getpid())
        return round(process.cpu_percent(interval=None), 2)
    except Exception:
        return 0.0


def get_system_memory_percent() -> float:
    """Retourne mémoire système utilisée %."""
    try:
        return round(psutil.virtual_memory().percent, 2)
    except Exception:
        return 0.0


def get_system_info() -> Dict[str, Any]:
    """Snapshot des infos système."""
    info = {
        "pid": os.getpid(),
        "thread": threading.current_thread().name,
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
    }
    try:
        process = psutil.Process(os.getpid())
        info.update({
            "memory_mb": get_process_memory_mb(),
            "cpu_percent": get_process_cpu_percent(),
            "num_threads": process.num_threads(),
            "system_memory_percent": get_system_memory_percent(),
        })
    except Exception:
        pass
    return info


def get_thread_info() -> Dict[str, Any]:
    """Info sur threads actifs."""
    return {
        "active_threads": threading.active_count(),
        "current_thread": threading.current_thread().name,
        "all_threads": [t.name for t in threading.enumerate()],
    }


# ========== FORMATTING & DISPLAY ==========

def format_bytes(size_bytes: int) -> str:
    """Formate taille en readable: '1.5 MB', '256 KB', etc."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def format_duration(seconds: float) -> str:
    """Formate durée: '1h 23m 45s'"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts)


def truncate_string(s: str, max_len: int = 100) -> str:
    """Tronque string si trop long."""
    if len(s) <= max_len:
        return s
    return s[:max_len-3] + "..."


# ========== VALIDATION ==========

def is_valid_log_level(level: str) -> bool:
    """Valide niveau de log."""
    valid = {"TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "FATAL"}
    return level.upper() in valid


def is_valid_category(category: str) -> bool:
    """Valide catégorie."""
    return isinstance(category, str) and len(category) > 0 and len(category) <= 50


def is_valid_session_id(session_id: str) -> bool:
    """Valide session ID."""
    return isinstance(session_id, str) and len(session_id) > 0 and len(session_id) <= 100


# ========== RATE LIMITING ==========

class SimpleRateLimiter:
    """Rate limiter basique pour throttling."""
    
    def __init__(self, max_count: int, window_seconds: int):
        self.max_count = max_count
        self.window_seconds = window_seconds
        self.events: List[float] = []
        self._lock = threading.Lock()
    
    def is_allowed(self) -> bool:
        """Retourne True si action est allowed."""
        now = time.time() if 'time' in dir() else 0
        
        with self._lock:
            # Nettoie vieux événements
            cutoff = now - self.window_seconds
            self.events = [t for t in self.events if t > cutoff]
            
            if len(self.events) < self.max_count:
                self.events.append(now)
                return True
            return False


# ========== STATISTICS ==========

class ExponentialMovingAverage:
    """Moyenne mobile exponentielle pour métriques lissées."""
    
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self.value: Optional[float] = None
    
    def update(self, new_value: float) -> float:
        """Met à jour et retourne nouvelle moyenne."""
        if self.value is None:
            self.value = new_value
        else:
            self.value = self.alpha * new_value + (1 - self.alpha) * self.value
        return self.value
    
    def get(self) -> Optional[float]:
        """Retourne valeur actuelle."""
        return self.value


import time  # Import manquant pour rate limiter
