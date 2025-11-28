# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

This is a monorepo combining JavaScript/TypeScript browser extensions with
Python audio processing utilities. The project provides browser extension(s) for
audio/text processing with backend Python support for audio extraction,
chunking, and reactive streaming patterns.

## Working with Claude

The project is maintained by Thomas. For Thomas to maintain the codebase
long-term, he needs to deeply understand critical code paths by implementing
them himself.

**Critical code paths** (Thomas implements, Claude consults):

- Core business logic and algorithms
- System architecture decisions
- Test implementations (TDD approach)

**Wiring** (Claude can implement):

- Connecting existing components (e.g., FastAPI routes exposing business logic)
- Boilerplate, configuration, imports
- Type definitions and interfaces
- Infrastructure glue code

When unsure whether something is "critical" or "wiring", ask first.

## Architecture

```
packages/
├── agents/           # @extensions/agents - Agent framework library (Rolldown + TypeScript)
└── summarizer/       # WXT browser extension that depends on @extensions/agents

python/
├── audio/           # Audio extraction (yt-dlp) and chunking (pydub)
└── streams/         # RxPy-based reactive streaming utilities
```

Package relationships:

- `summarizer` depends on `@extensions/agents`
- `agents` exports createAgent function, language codes, OpenAI API types
- `python/streams` provides async/Observable bridges using RxPy

## Build Commands

### JavaScript/TypeScript (pnpm)

```bash
pnpm build                   # Build all packages
pnpm build:agents            # Build agents library
pnpm build:summarizer        # Build summarizer extension
pnpm dev:agents              # Watch mode for agents
pnpm dev:summarizer          # Dev server for summarizer
pnpm format                  # Format with Prettier
```

Per-package commands:

```bash
pnpm --filter @extensions/agents typecheck
pnpm --filter summarizer build:firefox
pnpm --filter summarizer zip
```

### Python (uv)

```bash
uv run pytest                           # Run all tests
uv run pytest python/audio/             # Audio tests only
uv run pytest --cov=python/             # With coverage
uv run ruff check                       # Lint
uv run ruff format                      # Format
uv run mypy python                      # Type check
```

## Code Quality Configuration

### TypeScript

- Strict mode enabled
- Target: ES2022

### Python (configured in pyproject.toml)

- **Ruff**: Line length 100, rules E/W/F/I/N/UP/B/C4/SIM/TCH/RUF, auto-fix
  enabled
- **Mypy**: Strict mode with `disallow_untyped_defs`, `warn_return_any`,
  `strict_equality`
- **Target**: Python 3.11+

### Prettier

- Print width: 100

## Key Technologies

- **JS Build**: Rolldown (Rust-based bundler)
- **Browser Extension**: WXT 0.19.0 (Chrome/Firefox)
- **Python Audio**: yt-dlp, pydub
- **Python Async**: RxPy (reactivex)
- **Package Managers**: pnpm (JS), uv (Python)

## Notes

- Many Python stream utilities in `python/streams/` are stub implementations
  (NotImplementedError)
- agents package includes 180+ ISO 639-1 language codes in `lang.ts`
- WXT handles Chrome/Firefox browser extension compatibility
