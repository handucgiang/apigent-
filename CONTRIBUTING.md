# Contributing

Thanks for helping! Vietnamese or English, both are fine.

## Setup

```bash
uv sync
uv run pre-commit install   # optional
```

## Before opening a PR

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
```

- Tests must not call real LLMs or the network: use `ScriptedLLM` and `httpx.ASGITransport`.
- Keep the core dependency list small (`httpx`, `pydantic`, `pyyaml`).
- New behaviour = a test + a line in `CHANGELOG.md`.

## Good first issues

Look for the `good first issue` label: new LLM provider presets, better error messages,
more example integrations (CRM, POS, accounting).
