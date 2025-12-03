# CLAUDE.md

## Project Overview

Monorepo: JS/TS browser extensions + Python audio processing with RxPy streaming.

```
packages/
├── agents/           # @extensions/agents library
└── summarizer/       # WXT browser extension

python/
├── audio/            # Audio processing, VAD, Whisper STT
└── streams/          # RxPy utilities
```

## Code Style

- **Functional first**: No classes with methods unless wrapping FFI or managing
  external resources (e.g., `Transcriber` wrapping Whisper bindings)
- **Dataclasses for data**: Use `@dataclass(frozen=True)` for structured data
- **Test coverage**: Maintain 90%+ on entire code base
- **Small files**: If you need section dividers, split the file

## On Every Code Change

Run these before committing:

```bash
# Python
uv run ruff check --fix && uv run ruff format
uv run mypy python
uv run pytest python/ --cov=python

# JS/TS
pnpm format
pnpm build
```

## Working with Claude

The project is maintained by Thomas. For long-term maintainability, Thomas needs
to deeply understand and scrutinize critical code paths.

**Critical code paths** (expect heavy scrutiny, multiple revision passes):

- Core business logic and algorithms
- System architecture decisions
- Test implementations (TDD approach)

**Wiring** (typically accepted first or second pass):

- Connecting existing components (e.g., FastAPI routes exposing business logic)
- Boilerplate, configuration, imports
- Type definitions and interfaces
- Infrastructure glue code

When unsure whether something is "critical" or "wiring", ask first.

## Commands

```bash
# Python
uv run pytest                    # Tests
uv run pytest --cov=python       # With coverage
uv run ruff check && uv run ruff format
uv run mypy python

# JS/TS
pnpm build                       # Build all
pnpm dev:summarizer              # Dev server
pnpm format
```
