"""ViraxLog utilities package."""

from .crypto import (
    compute_entry_hash,
    verify_log_chain,
    validate_single_entry,
    hash_payload,
    compute_hmac,
    verify_hmac,
    MerkleTree,
    create_merkle_tree_from_entries,
)

from .helpers import (
    get_caller_context,
    format_source_string,
    sanitize_data,
    safe_json_dump,
    get_process_memory_mb,
    get_process_cpu_percent,
    get_system_memory_percent,
    get_system_info,
    get_thread_info,
    format_bytes,
    format_duration,
    truncate_string,
    is_valid_log_level,
    is_valid_category,
    is_valid_session_id,
    SimpleRateLimiter,
    ExponentialMovingAverage,
)

__all__ = [
    # Crypto
    "compute_entry_hash",
    "verify_log_chain",
    "validate_single_entry",
    "hash_payload",
    "compute_hmac",
    "verify_hmac",
    "MerkleTree",
    "create_merkle_tree_from_entries",
    
    # Helpers
    "get_caller_context",
    "format_source_string",
    "sanitize_data",
    "safe_json_dump",
    "get_process_memory_mb",
    "get_process_cpu_percent",
    "get_system_memory_percent",
    "get_system_info",
    "get_thread_info",
    "format_bytes",
    "format_duration",
    "truncate_string",
    "is_valid_log_level",
    "is_valid_category",
    "is_valid_session_id",
    "SimpleRateLimiter",
    "ExponentialMovingAverage",
]
