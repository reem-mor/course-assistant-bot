# Architecture — course-assistant-bot

## Package map

```text
course-assistant-bot/
  app/bot/          # Telegram handlers, admin FSM, submission flow
  app/graph/        # LangGraph router + versioned prompts
  app/services/     # Drive, schedule, homework, RAG, email, LLM
  app/workers/      # Drive watcher, schedule refresh, precompute
  app/repo/         # SQLAlchemy models + repositories
  app/core/         # settings, logging, i18n, ratelimit, health
  data/             # schedule.yaml, lesson_map.yaml, resources.yaml
  migrations/       # Alembic
  tests/            # unit + integration (mocked externals)
```

## Deployment modes

| Mode | When | Config |
|------|------|--------|
| Long-polling | Dev / small VPS | Default — no public URL |
| Webhook | Production | `RUN_MODE=webhook` + `WEBHOOK_URL` |
| Single process | Small always-on box | `RUN_SCHEDULER_IN_BOT=true` (default) |
| Bot + worker | Scale jobs separately | `RUN_SCHEDULER_IN_BOT=false` + `oz-worker` |

## Data flow principles

1. **Router** returns JSON intent only — never answers the user directly.
2. **Services** own business logic; LLM calls sit behind fakeable interfaces (`app/services/llm.py`).
3. **Secrets** never logged — structlog redaction + pydantic `SecretStr`.
4. **Tests** mock Telegram, Drive, LLMs, Gmail — deterministic CI.

See root [`README.md`](README.md) for diagrams and prompts.
