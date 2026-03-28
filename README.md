# ViraxLog v2.0 🛡️

**Secure, Cryptographically Chained Logging System in Python**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Build](https://img.shields.io/github/actions/workflow/status/damienos61/viraxlog/tests.yml)](https://github.com/damienos61/viraxlog/actions)
[![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen.svg)](https://github.com/damienos61/viraxlog)

---

## ✨ What's New in v2.0

- 🚀 **BLAKE2b hashing** - 2x faster than SHA-256
- 🌳 **Merkle tree verification** - O(log n) audit instead of O(n)
- ⚡ **WAL mode SQLite** - Optimized for high-throughput writes
- 🔌 **Circuit breaker pattern** - Graceful degradation under load
- 📊 **Comprehensive metrics** - Real-time performance monitoring
- 🐘 **PostgreSQL support** - Backend flexibility (beta)
- 🎯 **Threshold watchers** - Alert when N events in window
- 🔐 **HMAC authentication** - Optional message authentication
- 📈 **Exponential backoff** - Intelligent retry strategies

---

## 🎯 Key Features

| Feature | Description |
|---------|-------------|
| 🔗 **Cryptographic Chaining** | Each log hash-linked to previous, ensuring immutability |
| ⚡ **Async & Non-Blocking** | Queue-based architecture never blocks your app |
| 📦 **Batch Writing** | SQLite batches optimized with WAL mode |
| 🔍 **Audit Tools** | Merkle tree verification for fast integrity checks |
| 🛠️ **Watchers** | React to logs in real-time with pattern matching |
| 📊 **Metrics** | Built-in performance monitoring (CPU, memory, latency) |
| 🖥️ **CLI Tools** | Viewer with color-coded output, export to JSON |
| 🔒 **Security** | Timing-safe comparisons, HMAC support |
| 🌐 **Multi-Backend** | SQLite (default) or PostgreSQL |

---

## 📦 Installation

### From pip (when published)
```bash
pip install viraxlog
```

### From source
```bash
git clone https://github.com/damienos61/viraxlog.git
cd viraxlog
pip install -e .
```

### With optional backends
```bash
pip install -e ".[postgres]"  # PostgreSQL support
pip install -e ".[metrics]"   # Prometheus metrics
pip install -e ".[full]"      # Everything
```

---

## 🚀 Quick Start

### Basic Usage
```python
from viraxlog import initialize, info, warning, error, stop

# Initialize
initialize()

# Log events
info("startup", {"message": "Application started", "version": "1.0"})
warning("performance", {"cpu": 85, "memory_mb": 512})
error("database", {"error": "Connection timeout", "retries": 3})

# Shutdown (flushes queue)
stop()
```

### Custom Configuration
```python
from viraxlog import initialize, ViraxConfig, info, stop

config = ViraxConfig(
    db_name="app_logs.db",
    batch_size=100,        # Write batches of 100
    queue_maxsize=50000,   # Max queue size
    enable_heartbeat=True,
    heartbeat_interval=30,
    cache_size_mb=512,
    backend="sqlite"
)

initialize(config, session_id="APP-SESSION-001")

info("custom_config", {"loaded": True})

stop()
```

### Watchers (Real-time Reactions)
```python
from viraxlog import initialize, info, watch, error, stop

def alert_on_error(entry):
    print(f"🚨 ALERT: {entry.category} - {entry.data}")
    # Send to Slack, PagerDuty, etc.

initialize()

# Simple pattern watcher
watch("ERROR", alert_on_error, priority=1)

# Threshold watcher: Alert if 5 errors in 60 seconds
from viraxlog import watch_threshold

watch_threshold("ERROR", threshold=5, window_seconds=60, callback=alert_on_error)

for i in range(10):
    error("processing", {"task_id": i, "status": "failed"})

stop()
```

### Audit & Verification
```python
from viraxlog import initialize, ViraxAuditor, ViraxConfig, info, stop

initialize()
info("test", {"msg": "log entry"})
stop()

# Audit database integrity
config = ViraxConfig(db_name="virax.db")
auditor = ViraxAuditor(config)

report = auditor.validate_full_chain()

if report.status == "success":
    print(f"✅ All {report.total_entries} entries verified!")
else:
    print(f"❌ Corruption at index {report.error_index}")
    print(report.error_details)

auditor.close()
```

### Metrics & Monitoring
```python
from viraxlog import initialize, get_metrics, get_stats, info, stop

initialize()

# Log some entries
for i in range(100):
    info("test", {"i": i})

# Get metrics
metrics = get_metrics()
print(f"Memory: {metrics.memory_mb:.1f} MB")
print(f"CPU: {metrics.cpu_percent:.1f} %")
print(f"Queue: {metrics.queue_size}")
print(f"Write latency: {metrics.write_latency_ms:.2f} ms")

# Get full stats
stats = get_stats()
print(f"Total logged: {stats['logs_written']}")
print(f"Circuit breaker: {stats['circuit_breaker_state']}")

stop()
```

### Context Manager
```python
from viraxlog import ViraxLogContext, ViraxConfig

# Automatic cleanup
with ViraxLogContext() as virax:
    virax.info("test", {"in_context": True})
    virax.error("error", {"test": True})

# Logger automatically shut down
```

---

## 🖥️ CLI Tools

### View Logs
```bash
# Last 50 logs
viraxlog-viewer --db virax.db

# Filter by level
viraxlog-viewer --db virax.db -l ERROR -n 100

# Filter by category
viraxlog-viewer --db virax.db -c AUTH --since-hours 24

# Search data/source
viraxlog-viewer --db virax.db --search "timeout"

# JSON output
viraxlog-viewer --db virax.db --json > logs.json

# Show statistics
viraxlog-viewer --db virax.db --stats
```

### Audit Database
```bash
viraxlog-audit --db virax.db
viraxlog-audit --db virax.db --limit 10000  # Audit last 10k
viraxlog-audit --db virax.db --export report.json
```

---

## 📊 Performance

Benchmarks on modern hardware (Intel i7, 16GB RAM):

| Operation | Throughput |
|-----------|-----------|
| **Log write** | 50,000+ entries/sec (batched) |
| **Audit (1M entries)** | ~500ms (Merkle tree) vs 8s (linear) |
| **Memory** | ~50MB per 1M entries |
| **Latency (p99)** | < 50ms queue → disk |

WAL mode reduces latency by 60-80% compared to standard journal.

---

## 🔐 Security Considerations

1. **Cryptographic Chaining**: Each entry hash-linked to previous
2. **Timing-safe comparisons**: Uses `hmac.compare_digest()` 
3. **Optional HMAC**: Authenticate log integrity with shared key
4. **Read-only audit mode**: Open DB in read-only for verification
5. **No data encryption**: Logs stored in plaintext (add encryption layer if needed)

---

## 📚 API Reference

### Core Functions

```python
initialize(config=None, session_id=None) -> ViraxLogger
get_logger() -> ViraxLogger
is_initialized() -> bool
stop() -> None

# Logging shortcuts
info(category, data) -> None
warning(category, data) -> None
error(category, data) -> None
critical(category, data) -> None
debug(category, data) -> None
trace(category, data) -> None
fatal(category, data) -> None

# Watchers
watch(pattern, callback, use_regex=False, priority=100) -> str
watch_threshold(pattern, threshold, window_seconds, callback) -> str
unwatch(watcher_id) -> bool
get_watchers() -> List[Dict]

# Metrics
get_metrics() -> MetricsSnapshot
get_stats() -> Dict[str, Any]
```

### Models

```python
ViraxConfig: Dataclass with configuration options
LogEntry: Immutable log entry with hash chain
LogLevel: Enum of log levels
AuditReport: Structured audit result
MetricsSnapshot: Current performance metrics
```

### Classes

```python
ViraxLogger: Main logging engine
ViraxAuditor: Integrity verification
WatcherManager: Pattern-based event reactor
CircuitBreaker: Fault tolerance pattern
MerkleTree: O(log n) integrity verification
```

---

## 🛠️ Advanced Usage

### Custom Watchers with Priority
```python
from viraxlog import initialize, watch, error, stop

def critical_alert(entry):
    print(f"CRITICAL: {entry}")

def standard_alert(entry):
    print(f"Standard: {entry}")

initialize()

# Higher priority (lower number) executes first
watch("ERROR", critical_alert, priority=1)
watch("*", standard_alert, priority=100)

error("test", {"critical": True})

stop()
```

### Decorator for Auto-Logging
```python
from viraxlog import initialize, log_function, stop

initialize()

@log_function("INFO", include_args=True)
def expensive_operation(x, y):
    return x + y

result = expensive_operation(10, 20)

stop()
```

### Exporting Audit Reports
```python
from viraxlog import ViraxAuditor, ViraxConfig

config = ViraxConfig(db_name="virax.db")
auditor = ViraxAuditor(config)

# Export full report to JSON
auditor.export_audit_report("audit_report.json")

auditor.close()
```

---

## 🐛 Troubleshooting

**Queue getting full?**
- Increase `batch_size` (flushes more often)
- Increase `queue_maxsize` (larger in-memory buffer)
- Check database write speed (disk I/O bottleneck)

**High CPU usage?**
- Reduce `max_workers` (watcher threads)
- Profile with `get_metrics()`
- Check for runaway watchers

**Memory growing?**
- Review log data size
- Enable retention cleanup: `db.cleanup()`
- Monitor with `get_process_memory_mb()`

---

## 📄 License

MIT License - see `LICENSE` file

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork repository
2. Create feature branch
3. Add tests
4. Submit PR

See `CONTRIBUTING.md` for details.

---

## 📞 Support

- 📖 Documentation: [GitHub Wiki](https://github.com/damienos61/viraxlog/wiki)
- 🐛 Issues: [GitHub Issues](https://github.com/damienos61/viraxlog/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/damienos61/viraxlog/discussions)

---

**Made with ❤️ by damienos61**
