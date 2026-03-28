# Contributing to ViraxLog

Thank you for interest in contributing! This document provides guidelines for participation.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/YOUR_USERNAME/viraxlog.git`
3. **Create branch**: `git checkout -b feature/your-feature-name`
4. **Install dev tools**: `pip install -e ".[dev]"`

## Development Workflow

### Code Style
- Follow **PEP 8** (enforced by `black` and `ruff`)
- Run formatter: `black src/viraxlog tests`
- Run linter: `ruff check src/viraxlog`

### Testing
```bash
# Run all tests
pytest

# With coverage
pytest --cov=src/viraxlog

# Specific test file
pytest tests/test_core.py

# Performance tests
pytest -m performance
```

**Coverage target**: 95%+

### Type Hints
- Add type hints to all new functions
- Use `mypy` for checking: `mypy src/viraxlog`

### Documentation
- Docstrings for all public functions
- Update README if adding features
- Examples in docstrings

## Commit Message Format

```
<type>: <short description>

<optional longer description>

Fixes #123
```

Types: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `chore`

## Pull Request Process

1. **Update** README/docs if needed
2. **Add tests** for new functionality
3. **Run full test suite** locally
4. **Create PR** with clear title and description
5. **Link issues**: "Fixes #123" in description
6. **Wait for review** and address feedback

## Areas for Contribution

### High Priority
- [ ] PostgreSQL backend completion
- [ ] Prometheus metrics exporter
- [ ] Performance optimizations
- [ ] Documentation improvements

### Medium Priority
- [ ] Additional compression algorithms
- [ ] Redis caching layer
- [ ] Web dashboard
- [ ] Python async support

### Low Priority
- [ ] New CLI commands
- [ ] Additional exporters
- [ ] Language bindings

## Reporting Bugs

Create issue with:
- **Title**: Clear, descriptive
- **Description**: What you expected vs what happened
- **Reproduction**: Steps to reproduce
- **Environment**: Python version, OS, etc.
- **Logs**: Any error messages

## Performance Guidelines

When adding features:
- ✅ Batch writes to DB
- ✅ Use thread pools for I/O
- ✅ Cache frequently accessed data
- ✅ Profile with `get_metrics()`
- ❌ Avoid blocking operations
- ❌ Don't spawn threads unnecessarily

## Code Review Checklist

Before submitting PR, ensure:
- [ ] Code follows style guide
- [ ] Tests pass (pytest)
- [ ] Coverage >= 95%
- [ ] Type hints added
- [ ] Docstrings present
- [ ] README updated
- [ ] No breaking changes (or documented)
- [ ] Performance acceptable

## Questions?

- 💬 Open a discussion
- 📖 Check existing issues
- 🤝 Ask in PR comments

---

**Happy contributing!** 🎉
