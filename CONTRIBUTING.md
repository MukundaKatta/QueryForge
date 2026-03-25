# Contributing to QueryForge

Thanks for your interest in contributing to QueryForge! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/MukundaKatta/QueryForge.git
cd QueryForge

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in dev mode with all dev dependencies
make dev
```

## Running Tests

```bash
make test          # run all tests
make test-cov      # run tests with coverage report
```

## Code Quality

```bash
make lint          # ruff linting
make typecheck     # mypy type checking
make fmt           # auto-format with ruff
```

## Pull Request Process

1. Fork the repository and create a feature branch from `main`.
2. Write tests for any new functionality.
3. Ensure all checks pass: `make all`
4. Open a pull request with a clear description of the change.

## Adding New Query Patterns

To add support for a new SQL pattern:

1. Add keyword detection in `IntentClassifier.classify()` in `src/queryforge/core.py`.
2. Add entity extraction logic in `SchemaMapper.map()` if needed.
3. Add SQL assembly logic in `SQLBuilder.build()`.
4. Add tests in `tests/test_core.py`.

## Code Style

- Follow PEP 8, enforced by ruff.
- Use type hints for all function signatures.
- Keep functions focused and under 30 lines where possible.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
