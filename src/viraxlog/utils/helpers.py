#!/usr/bin/env python3
"""
ViraxLog - Helpers Module
System introspection utilities, context formatting, and secure data sanitization.
"""

from __future__ import annotations

import os
import sys
import threading
import traceback
from datetime import datetime, date
from typing import Dict, Any, Optional

# -------------------------------------------------
# CALL CONTEXT INTROSPECTION
# -------------------------------------------------

def get_caller_context(depth: int = 2, include_full_path: bool = False) -> Dict[str, Any]:
    """
    Explores the execution stack to identify the log origin.
    Uses sys._getframe for better performance than inspect.stack().

    Args:
        depth: Stack depth (2 usually points to the caller of the .log() method).
        include_full_path: If True, uses the absolute path, otherwise just the filename.

    Returns:
        Dictionary containing source info, thread, and process IDs.
    """
    try:
        # sys._getframe(depth) is faster than inspect.stack()
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
        # Fallback if the stack depth is out of range
        return {
            "source": "unknown",
            "function": "unknown",
            "module": "unknown",
            "thread_name": threading.current_thread().name,
            "thread_id": threading.get_ident(),
            "process_id": os.getpid()
        }

def format_source_string(context: Dict[str, Any], include_thread: bool = False) -> str:
    """
    Formats the context dictionary into a compact string for the 'source' field.
    Example: 'main.py:42 [start_app]'
    """
    base = f"{context.get('source')} [{context.get('function')}]"
    if include_thread:
        t_name = context.get('thread_name')
        if t_name:
            base += f" ({t_name})"
    return base

# -------------------------------------------------
# DATA SANITIZATION
# -------------------------------------------------

def sanitize_data(data: Any, max_depth: int = 5, _current_depth: int = 0) -> Any:
    """
    Cleans data before serialization to ensure hashing stability and prevent crashes.
    Handles dicts, lists, datetimes, bytes, and custom objects.
    """
    if _current_depth > max_depth:
        return "[Max Depth Reached]"

    # Primitive types
    if isinstance(data, (str, int, float, bool, type(None))):
        return data

    # Temporal types
    if isinstance(data, (datetime, date)):
        return data.isoformat()

    # Binary data
    if isinstance(data, (bytes, bytearray)):
        return data.hex()

    # Collections
    if isinstance(data, dict):
        return {str(k): sanitize_data(v, max_depth, _current_depth + 1) for k, v in data.items()}

    if isinstance(data, (list, tuple, set)):
        return [sanitize_data(item, max_depth, _current_depth + 1) for item in data]

    # Custom objects (introspection)
    if hasattr(data, "__dict__"):
        return sanitize_data(vars(data), max_depth, _current_depth + 1)

    # Fallback to string representation
    return str(data)

# -------------------------------------------------
# SYSTEM INFORMATION
# -------------------------------------------------

def get_memory_usage() -> str:
    """Returns the current process memory usage in a human-readable format."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_bytes = process.memory_info().rss
        return f"{mem_bytes / 1024 / 1024:.2f} MB"
    except ImportError:
        return "N/A (psutil missing)"

def get_system_info() -> Dict[str, Any]:
    """Retrieves system-level metrics for debugging and telemetry."""
    info = {
        "pid": os.getpid(),
        "thread": threading.current_thread().name,
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
    }
    try:
        import psutil
        process = psutil.Process(os.getpid())
        info.update({
            "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
            "cpu_percent": process.cpu_percent(interval=None) # Non-blocking
        })
    except Exception:
        info.update({"memory_mb": None, "cpu_percent": None})
    return info