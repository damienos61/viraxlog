#!/usr/bin/env python3
"""
ViraxLog v2.0 - Complete Example
Demonstrates all major features and best practices.
"""

import time
import random
from viraxlog import (
    initialize,
    ViraxConfig,
    info,
    warning,
    error,
    critical,
    debug,
    watch,
    watch_threshold,
    get_metrics,
    get_stats,
    get_watchers,
    ViraxLogContext,
    ViraxAuditor,
    stop,
)


def example_1_basic_usage():
    """Simple logging with default config."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Usage")
    print("="*60)
    
    # Auto-initialize with defaults
    initialize(session_id="BASIC-DEMO")
    
    # Log at different levels
    debug("startup", {"module": "main", "stage": "init"})
    info("startup", {"message": "Application started"})
    warning("system", {"cpu": 85, "memory_mb": 512})
    error("database", {"error": "Connection timeout", "retry": 1})
    critical("security", {"threat_level": "high"})
    
    # Shutdown gracefully
    stop()
    print("✓ Logged 5 entries with different levels")


def example_2_custom_config():
    """Custom configuration for high-performance scenario."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Custom Configuration")
    print("="*60)
    
    config = ViraxConfig(
        db_name="high_perf.db",
        batch_size=200,        # Larger batches
        queue_maxsize=100000,  # Larger queue
        cache_size_mb=512,     # More cache
        max_workers=10,        # More watchers
        enable_heartbeat=True,
        heartbeat_interval=30,
    )
    
    initialize(config, session_id="HIGH-PERF")
    
    # Simulate high-throughput scenario
    print("Logging 1000 entries...")
    for i in range(1000):
        info("transaction", {
            "tx_id": i,
            "amount": random.uniform(100, 10000),
            "status": "completed"
        })
    
    print("✓ Logged 1000 entries at high speed")
    stop()


def example_3_watchers():
    """Real-time watchers and pattern matching."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Watchers & Pattern Matching")
    print("="*60)
    
    initialize(session_id="WATCHER-DEMO")
    
    # Simple watcher: alert on errors
    error_count = {"count": 0}
    
    def alert_on_error(entry):
        error_count["count"] += 1
        print(f"🚨 ERROR ALERT #{error_count['count']}: {entry.category}")
    
    watch_id = watch("ERROR", alert_on_error, priority=1)
    print(f"Registered error watcher: {watch_id}")
    
    # Threshold watcher: alert on 3 errors in 10 seconds
    def alert_threshold(entry):
        print(f"⚠️  THRESHOLD ALERT: Multiple errors detected!")
    
    threshold_id = watch_threshold(
        pattern="ERROR",
        threshold=3,
        window_seconds=10,
        callback=alert_threshold
    )
    print(f"Registered threshold watcher: {threshold_id}")
    
    # Trigger some errors
    print("\nGenerating errors...")
    for i in range(5):
        error("processing", {"task": i, "status": "failed"})
        time.sleep(0.2)
    
    # Wait for async callbacks
    time.sleep(1)
    
    # Inspect watchers
    watchers = get_watchers()
    print(f"\nActive watchers: {len(watchers)}")
    for w in watchers:
        print(f"  - {w['id']}: {w['pattern']} (hits: {w.get('hits', 0)})")
    
    stop()


def example_4_metrics_monitoring():
    """Real-time performance metrics."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Metrics & Monitoring")
    print("="*60)
    
    initialize(session_id="METRICS-DEMO")
    
    # Log some entries
    print("Generating logs...")
    for i in range(500):
        info("test", {"i": i, "data": f"entry_{i}"})
    
    time.sleep(1)  # Let writes complete
    
    # Get metrics
    metrics = get_metrics()
    if metrics:
        print("\n📊 Performance Metrics:")
        print(f"  - Memory: {metrics.memory_mb:.1f} MB")
        print(f"  - CPU: {metrics.cpu_percent:.1f} %")
        print(f"  - Queue size: {metrics.queue_size}")
        print(f"  - Write latency: {metrics.write_latency_ms:.2f} ms")
    
    # Get detailed stats
    stats = get_stats()
    print(f"\n📈 Detailed Statistics:")
    print(f"  - Total logged: {stats['logs_created']}")
    print(f"  - Actually written: {stats['logs_written']}")
    print(f"  - Dropped: {stats['logs_dropped']}")
    print(f"  - Circuit breaker: {stats['circuit_breaker_state']}")
    
    stop()


def example_5_context_manager():
    """Using context manager for automatic cleanup."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Context Manager (Auto-Cleanup)")
    print("="*60)
    
    # Automatic initialization and cleanup
    with ViraxLogContext() as virax:
        virax.info("context", {"status": "entered"})
        
        for i in range(10):
            virax.debug("loop", {"iteration": i})
        
        virax.error("context", {"status": "simulated_error"})
        
        print("✓ Logged within context manager")
    
    print("✓ Context automatically shut down (no explicit stop())")


def example_6_audit_verification():
    """Verify log integrity with audits."""
    print("\n" + "="*60)
    print("EXAMPLE 6: Audit & Integrity Verification")
    print("="*60)
    
    # Create logs first
    initialize(session_id="AUDIT-DEMO")
    for i in range(100):
        info("audit_test", {"entry": i})
    stop()
    
    # Now audit the database
    from viraxlog import ViraxConfig
    
    config = ViraxConfig(db_name="virax.db")
    auditor = ViraxAuditor(config)
    
    print("Running integrity audit...")
    report = auditor.validate_full_chain()
    
    if report.status == "success":
        print(f"✅ Audit PASSED: All {report.total_entries} entries verified")
        print(f"   Chain integrity: intact")
    elif report.status == "failed":
        print(f"❌ Audit FAILED at entry {report.error_index}")
        print(f"   Error details: {report.error_details}")
    elif report.status == "empty":
        print("⚠️  Database is empty")
    else:
        print(f"⚠️  Audit error: {report.error_details}")
    
    # Get chain summary
    summary = auditor.get_chain_summary()
    print(f"\nChain Summary:")
    print(f"  - Total entries: {summary.get('total_logs', 0)}")
    print(f"  - Last hash: {summary.get('last_hash', 'N/A')}")
    print(f"  - Latest entry: {summary.get('last_timestamp', 'N/A')}")
    
    # Get statistics
    stats = auditor.get_chain_statistics()
    print(f"\nLevel Distribution:")
    for level, count in stats.get('level_distribution', {}).items():
        print(f"  - {level}: {count}")
    
    auditor.close()


def example_7_error_handling():
    """Demonstrates error handling and recovery."""
    print("\n" + "="*60)
    print("EXAMPLE 7: Error Handling & Circuit Breaker")
    print("="*60)
    
    config = ViraxConfig(
        db_name="error_test.db",
        batch_size=10,
        queue_maxsize=100,
    )
    
    initialize(config, session_id="ERROR-DEMO")
    
    # Create many error entries
    print("Simulating error conditions...")
    for i in range(50):
        error("simulated", {
            "error_id": i,
            "message": f"Error {i}",
            "traceback": "stack trace here" * 10  # Large data
        })
    
    time.sleep(1)
    
    # Check stats
    stats = get_stats()
    print(f"\nRecovery Status:")
    print(f"  - Errors logged: {stats['errors']}")
    print(f"  - Circuit breaker: {stats['circuit_breaker_state']}")
    
    stop()
    print("✓ System recovered from errors")


def example_8_best_practices():
    """Demonstrates best practices."""
    print("\n" + "="*60)
    print("EXAMPLE 8: Best Practices")
    print("="*60)
    
    # 1. Initialize early in your app
    config = ViraxConfig(
        db_name="best_practices.db",
        batch_size=100,
        enable_heartbeat=True,
    )
    initialize(config, session_id="BEST-PRACTICES")
    
    # 2. Use appropriate log levels
    debug("config", {"setting": "loaded"})        # Debug info
    info("startup", {"service": "ready"})         # Informational
    warning("performance", {"cpu": 90})           # Warnings
    error("failure", {"component": "down"})       # Errors
    critical("security", {"breach": True})        # Critical
    
    # 3. Structured data
    user_action = {
        "user_id": 12345,
        "action": "login",
        "timestamp": "2024-03-26T10:30:00Z",
        "ip_address": "192.168.1.1",
        "success": True
    }
    info("security", user_action)
    
    # 4. Use watchers for important events
    def notify_on_critical(entry):
        print(f"🔴 CRITICAL EVENT: {entry.data}")
    
    watch("CRITICAL", notify_on_critical, priority=1)
    
    # 5. Monitor with metrics
    critical("alert", {"event": "test_alert"})
    time.sleep(0.5)
    
    metrics = get_metrics()
    if metrics:
        print(f"\n✓ System Health: CPU {metrics.cpu_percent:.1f}%, Memory {metrics.memory_mb:.1f}MB")
    
    # 6. Always shutdown
    stop()
    print("\n✓ All best practices demonstrated")


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("ViraxLog v2.0 - Complete Examples")
    print("="*60)
    
    try:
        example_1_basic_usage()
        example_2_custom_config()
        example_3_watchers()
        example_4_metrics_monitoring()
        example_5_context_manager()
        example_6_audit_verification()
        example_7_error_handling()
        example_8_best_practices()
        
        print("\n" + "="*60)
        print("✅ All examples completed successfully!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
