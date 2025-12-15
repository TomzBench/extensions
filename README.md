# Commands

## Python

```bash
# Tests
uv run pytest

# Tests (fast)
uv run pytest -m "not slow"

# Coverage - terminal
uv run pytest --cov --cov-report=term

# Coverage - terminal with missing lines
uv run pytest --cov --cov-report=term-missing

# Coverage - HTML (outputs to htmlcov/)
uv run pytest --cov --cov-report=html

# Coverage - both terminal and HTML
uv run pytest --cov --cov-report=term-missing --cov-report=html

# Lint check
uv run ruff check

# Lint fix
uv run ruff check --fix

# Format
uv run ruff format

# Type check
uv run mypy python

# Complexity analysis (cyclomatic complexity, see radon.cfg)
uv run radon cc python/ -a -s       # B or worse only (default)
uv run radon cc python/ -a -s -na   # all functions with grades
uv run radon cc python/ --min 10    # only complexity >= 10
```

## JS/TS

```bash
# Build all
pnpm build

# Dev server
pnpm dev:summarizer

# Format
pnpm format
```
