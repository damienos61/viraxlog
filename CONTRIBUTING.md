# 🛠️ Contributing to ViraxLog

Thank you for your interest in **ViraxLog**! By contributing, you help build a secure, transparent, and high-integrity logging system for everyone.

---

## 🚀 Development Workflow

| Step                       | Command / Description                                                                       |
| -------------------------- | ------------------------------------------------------------------------------------------- |
| **1. Prepare Environment** | Ensure Python 3.8+ is installed. Clone the repository and install development dependencies: |

````bash
git clone https://github.com/damienos61/viraxlog.git
cd viraxlog
pip install -e ".[dev]"
``` |
| **2. Create a Branch** | Always create a feature or bugfix branch for your changes:
```bash
git checkout -b feature/my-new-feature
# or
 git checkout -b fix/bug-name
``` |

---

## 🧪 Quality Standards

### Unit Tests
ViraxLog relies on absolute trust in data integrity. **No Pull Request will be accepted if tests do not pass 100%.**

Run the test suite:
```bash
pytest
````

If you add a new feature, **add corresponding tests** in the `tests/` folder.

### Code Style

We use **Black** for formatting and **isort** for import sorting. Before submitting:

```bash
black src tests
isort src tests
```

---

## 🛡️ Security & Cryptography

If modifying `src/viraxlog/utils/crypto.py` or `src/viraxlog/audit.py`:

* Clearly explain the impact on hash structure.
* Ensure backward compatibility with existing databases or provide a migration script.
* Any change to the SHA-256 algorithm must be justified by a major security necessity.

---

## 📝 Pull Request (PR) Process

| Step                  | Description                                                              |
| --------------------- | ------------------------------------------------------------------------ |
| **Documentation**     | Update `README.md` if any public function signature or behavior changes. |
| **Clear Description** | Explain **what** and **why** in your PR description.                     |
| **CI Validation**     | Wait for automated tests (GitHub Actions) to pass.                       |
| **Code Review**       | A maintainer will review your code before approval.                      |

---

## 🐛 Reporting Bugs

Use the **Issues** tab on GitHub:

* Provide a descriptive title.
* Include a minimal reproducible code example.
* Specify your OS (Windows/Linux/macOS).

---

## 📜 Code of Conduct

Please be respectful and constructive in all interactions. We strive to maintain a welcoming community for developers of all levels.

---

## 🔗 Badges (Optional)

![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Build](https://img.shields.io/github/actions/workflow/status/damienos61/viraxlog/python-package.yml?branch=main)
![Coverage](https://img.shields.io/codecov/c/github/damienos61/viraxlog/main)
