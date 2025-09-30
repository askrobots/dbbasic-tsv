# Contributing to dbbasic-tsv

Thank you for considering contributing to dbbasic-tsv! This document provides guidelines for contributing.

## Philosophy

dbbasic-tsv follows these core principles:

1. **Simplicity over features** - Do one thing well
2. **Human-readable always** - Text files, grep-friendly
3. **Zero dependencies** - Pure Python core
4. **Optional complexity** - Rust acceleration is optional

## Getting Started

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/askrobots/dbbasic-tsv.git
cd dbbasic-tsv

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dev dependencies
pip install pytest pytest-cov

# Run tests
python3 -m pytest tests/
```

### Running Tests

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run with coverage
python3 -m pytest tests/ --cov=dbbasic --cov-report=html

# Run specific test
python3 -m pytest tests/test_basic.py::TestBasicOperations::test_insert_single
```

## How to Contribute

### Reporting Bugs

When reporting bugs, please include:

- Your operating system and Python version
- Steps to reproduce the issue
- Expected vs actual behavior
- Minimal code example that demonstrates the bug

### Suggesting Features

We're cautious about adding features. Please:

- Explain the use case clearly
- Show how it fits the philosophy
- Consider if it can be done without adding complexity
- Provide example code showing how it would work

### Submitting Pull Requests

1. **Fork the repository** and create a branch from `main`

2. **Make your changes**:
   - Write clear, concise code
   - Follow existing code style
   - Add docstrings to public methods
   - Keep it simple - avoid cleverness

3. **Add tests**:
   - All new features need tests
   - Maintain test coverage above 80%
   - Tests should be simple and clear

4. **Update documentation**:
   - Update README.md if needed
   - Add docstrings
   - Update CHANGELOG.md

5. **Run the test suite**:
   ```bash
   python3 -m pytest tests/ -v
   ```

6. **Submit the PR**:
   - Write a clear description
   - Reference any related issues
   - Explain what changed and why

## Code Style

- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Prefer clarity over brevity
- Use meaningful variable names

### Example

```python
def query_one(self, **conditions) -> Optional[Dict[str, Any]]:
    """Query single record matching conditions

    Args:
        **conditions: Field-value pairs to match

    Returns:
        First matching record or None

    Example:
        user = db.query_one(email="alice@example.com")
    """
    results = self.query(**conditions)
    return results[0] if results else None
```

## Project Structure

```
dbbasic-tsv/
├── dbbasic/           # Main package
│   ├── tsv.py        # Core TSV implementation
│   ├── audit_log.py  # Audit logging
│   └── bigtable_tsv.py  # BigTable-style implementation
├── tests/            # Test suite
├── examples/         # Usage examples
├── benchmarks/       # Performance benchmarks
└── rust/            # Optional Rust acceleration
```

## Testing Guidelines

- **Unit tests**: Test individual methods
- **Integration tests**: Test full workflows
- **Edge cases**: Empty data, large files, concurrent access
- **Performance tests**: Benchmark critical operations

## Documentation

- Every public method needs a docstring
- Use Google-style docstrings
- Include examples for non-trivial methods
- Update README.md for new features

## Release Process

(For maintainers)

1. Update version in `setup.py`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Create git tag: `git tag v1.0.1`
5. Push tags: `git push --tags`
6. Build: `python3 -m build`
7. Upload to PyPI: `twine upload dist/*`

## Questions?

- Open an issue for questions
- Tag with `question` label
- Be respectful and patient

## Code of Conduct

- Be kind and respectful
- Focus on the code, not the person
- Assume good intentions
- Help others learn

Thank you for contributing! 🎉