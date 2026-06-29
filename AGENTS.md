# AGENTS.md — course-assistant-bot

Production **Telegram course-ops bot** — async Python 3.12, uv, SQLAlchemy/Alembic, multi-LLM, strict typing.

## Conventions

- **uv** for deps (`uv sync --extra dev`); do not commit `.env`
- **Tests:** `uv run pytest` — all externals mocked; no live network in CI
- **Lint/types:** `uv run ruff check .` · `uv run mypy app`
- **Scope:** Do not refactor architecture without explicit request — shipped product

## Secrets

Telegram token, LLM keys, Gmail, Drive — via `.env` only. See `.env.example`.

## Commands

```bash
uv run oz-bot          # long-polling dev
uv run oz-worker       # optional separate worker
uv run pytest -q
```
