# 🛡️ ViraxLog

[![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org/)
[![Build Status](https://img.shields.io/github/actions/workflow/status/damienos61/viraxlog/python-package.yml)](https://github.com/damienos61/viraxlog/actions)
[![Coverage Status](https://img.shields.io/badge/coverage-73%25-yellowgreen)](https://github.com/damienos61/viraxlog)

ViraxLog is a **high-security logging system** designed to guarantee full integrity of your event logs. Using **cryptographic chaining** (Blockchain-style), each entry is linked to the previous one, making any modification or deletion detectable.

---

## ✨ Key Features

| Feature                           | Description                                                                        |
| --------------------------------- | ---------------------------------------------------------------------------------- |
| 🔗 Cryptographic Chaining         | Each log contains the SHA-256 hash of the previous entry, ensuring full integrity. |
| ⚡ Asynchronous & High Performance | Uses a queue and worker thread to never block your main application.               |
| 📦 Batch Writing                  | Optimized SQLite writes in configurable batches to reduce disk I/O.                |
| 🔍 Built-in Audit                 | Native tools to verify database integrity and detect chain breaks.                 |
| 🖥️ CLI Interface                 | Ready-to-use commands to initialize, view, and monitor logs.                       |
| 🛠️ Watchers                      | System monitoring (CPU, RAM, Heartbeat) integrated directly into the log stream.   |
| 🔒 Security                       | Designed to resist tampering and ensure authenticity of log data.                  |

---

## 🚀 Installation

### Development Mode (Editable)

Clone the repository and install the project with dependencies:

```bash
git clone https://github.com/damienos61/viraxlog.git
cd viraxlog
pip install -e .
```

### Installing Development Tools

```bash
pip install -e ".[dev]"
```

---

## 📖 Quick Usage

```python
from viraxlog.core import ViraxLogger
from viraxlog.models import ViraxConfig

# 1. Custom Configuration
config = ViraxConfig(
    db_name="secure_logs.db",
    batch_size=10  # Writes to DB every 10 messages
)

# 2. Initialize Logger
logger = ViraxLogger(config)

# 3. Log Events
logger.log("INFO", "AUTH", "Admin user logged in")
logger.log("WARNING", "SYSTEM", "High CPU temperature", data={"temp": 75})

# 4. Graceful Shutdown (flush remaining logs)
logger.shutdown()
```

---

## 🛡️ Integrity Verification

Check that no one has tampered with your SQLite logs:

```python
from viraxlog.audit import AuditManager

auditor = AuditManager("secure_logs.db")
is_valid, error_report = auditor.verify_chain()

if is_valid:
    print("✅ Integrity confirmed: No log entries were altered.")
else:
    print(f"❌ Corruption alert: Issue detected at index {error_report}")
```

---

## 🧪 Tests

The project comes with a complete unit test suite covering cryptography, database, and async engine.

```bash
pytest
```

Expected result: `12 passed`

---

## 📂 Project Structure

| File                            | Description                                           |
| ------------------------------- | ----------------------------------------------------- |
| `src/viraxlog/core.py`          | Main engine, async thread handling.                   |
| `src/viraxlog/database.py`      | SQLite persistence manager.                           |
| `src/viraxlog/audit.py`         | Verification and security audit logic.                |
| `src/viraxlog/utils/crypto.py`  | SHA-256 hashing functions.                            |
| `src/viraxlog/utils/helpers.py` | Utility functions (sanitization, formatting).         |
| `src/viraxlog/watchers.py`      | System monitoring sensors.                            |
| `src/viraxlog/interface.py`     | Simplified facade, global singleton, logging helpers. |
| `src/viraxlog/viewer.py`        | CLI to view logs in real-time.                        |

---

## 👤 Author

damienos61
GitHub: [@damienos61](https://github.com/damienos61)

---

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.
