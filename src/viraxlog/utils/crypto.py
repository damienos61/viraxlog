#!/usr/bin/env python3
"""
ViraxLog - Crypto Module
Handles cryptographic integrity, hashing stability, and chain validation.
"""

from __future__ import annotations

import hashlib
import logging
import json
import hmac  # Used for safe digest comparison
from typing import Optional, List, Tuple, Literal, Any

logger = logging.getLogger("ViraxLog.Crypto")

# --- Constants ---
DEFAULT_HASH_ALGO: Literal["sha256"] = "sha256"


# -------------------------------------------------
# HASHING UTILITIES
# -------------------------------------------------

def compute_entry_hash(
    timestamp: str,
    level: str,
    category: str,
    data: Any,
    prev_hash: str,
    algorithm: str = DEFAULT_HASH_ALGO
) -> str:
    """
    Computes a stable cryptographic hash for a LogEntry.
    Ensures that structured data (dicts/lists) results in the same hash 
    regardless of key order or special characters.
    """
    
    # 1. Normalize data for hashing stability
    if isinstance(data, (dict, list)):
        # Force sorted keys, no extra spaces, and keep UTF-8 characters as-is
        data_str = json.dumps(
            data, 
            sort_keys=True, 
            separators=(',', ':'), 
            ensure_ascii=False
        )
    else:
        data_str = str(data)

    # 2. Build the payload for the hashing function
    # The chain integrity depends on this specific order
    payload_str = f"{timestamp}{level}{category}{data_str}{prev_hash}"
    payload = payload_str.encode("utf-8")

    try:
        algo_name = algorithm.lower()
        if algo_name == "sha256":
            return hashlib.sha256(payload).hexdigest()
        elif algo_name == "sha3_256":
            return hashlib.sha3_256(payload).hexdigest()
        elif algo_name == "blake2b":
            return hashlib.blake2b(payload, digest_size=32).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    except Exception as e:
        logger.critical(f"Hash computation failed: {e}")
        raise


# -------------------------------------------------
# CHAIN VALIDATION
# -------------------------------------------------

def verify_log_chain(
    entries: List["LogEntry"],
    initial_prev_hash: str = "GENESIS",
    algorithm: str = DEFAULT_HASH_ALGO
) -> Tuple[bool, Optional[int]]:
    """
    Verifies the full integrity of a provided log list.
    
    Returns:
        (True, None) if the entire chain is valid.
        (False, index) if corruption is detected at a specific index.
    """
    # Local import to prevent circular dependency
    from ..models import LogEntry

    current_expected_prev_hash = initial_prev_hash

    for i, entry in enumerate(entries):
        # A. Chain Verification: Does this block point to the previous one?
        # hmac.compare_digest is safer against timing attacks
        if not hmac.compare_digest(entry.prev_hash, current_expected_prev_hash):
            logger.error(
                f"[Chain Break] Index {i}: Invalid previous hash linkage "
                f"(expected={current_expected_prev_hash}, found={entry.prev_hash})"
            )
            return False, i

        # B. Data Verification: Does the content match the stored hash?
        actual_hash = compute_entry_hash(
            entry.timestamp, 
            entry.level, 
            entry.category, 
            entry.data, 
            entry.prev_hash, 
            algorithm
        )
        
        if not hmac.compare_digest(entry.hash, actual_hash):
            logger.error(
                f"[Data Corruption] Index {i}: Hash mismatch "
                f"(computed={actual_hash}, stored={entry.hash})"
            )
            return False, i

        # Update expectation for the next block
        current_expected_prev_hash = entry.hash

    return True, None


# -------------------------------------------------
# SINGLE ENTRY VALIDATION
# -------------------------------------------------

def validate_single_entry(
    entry: "LogEntry", 
    prev_hash: str, 
    algorithm: str = DEFAULT_HASH_ALGO
) -> bool:
    """Validates a single log entry against a specific previous hash."""
    try:
        computed = compute_entry_hash(
            entry.timestamp, 
            entry.level, 
            entry.category, 
            entry.data, 
            prev_hash, 
            algorithm
        )
        
        # Verify both the content hash and the link to the chain
        is_content_ok = hmac.compare_digest(entry.hash, computed)
        is_link_ok = hmac.compare_digest(entry.prev_hash, prev_hash)
        
        return is_content_ok and is_link_ok
    except Exception as e:
        logger.error(f"Single entry validation error: {e}")
        return False


def hash_payload(payload: str) -> str:
    """Simple utility to hash a raw string using SHA-256."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()