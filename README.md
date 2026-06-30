> **Portfolio project** — bilingual Telegram course ops bot. Course archive: [amdocs-ai-course](https://github.com/reem-mor/amdocs-ai-course).

# course-assistant-bot

[![CI](https://github.com/reem-mor/course-assistant-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/reem-mor/course-assistant-bot/actions/workflows/ci.yml)

The official Telegram assistant for the **Oz VeRuach** (עוז ורוח) AI-Augmented Software
Engineering course (Amdocs Learning Center / Fursa).

Production-grade, fully async Python 3.12 bot. Two long-running processes:

- `bot` — the Telegram update handler (long-polling in dev, webhook in prod).
- `worker` — scheduled jobs (Drive watcher, schedule refresh, nightly precompute). Idle
  in Phase 0; jobs land in Phase 5.

> **Status: feature-complete (Phases 0-7).** Schedule, recordings, homework + submission
> emails, lesson summaries, recommendations/RAG, Drive watcher + broadcasts, admin
> upload/announce/schedule-overrides, and a single-process deployment with scheduled jobs.
> See [PLAN.md](PLAN.md) for the per-phase breakdown.

## Single process by default

For a small always-on box, the bot and its scheduled jobs (Drive watcher, weekly schedule
re-scrape, nightly precompute) run in **one process / one event loop** — less to run and
monitor. `RUN_SCHEDULER_IN_BOT=true` (default) enables this; set it to `false` and run
`oz-worker` separately only if you later want to scale the two apart.

## Commands

- Everyone: `/start`, `/stop`, `/menu`, `/help`, `/myid`, plus free-text (he/en) for
  schedule, recordings, summaries, homework, and recommended materials.
- Admins (Alex, Sagy): `/announce`, `/schedule_update`, and uploading a file to broadcast.
- Owner (Re'em): `/map`, `/reindex`, `/refresh_schedule`, `/admin add|remove|list`.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/) (recommended) — manages the env and dependencies.
- `ffmpeg` — only needed from Phase 3 (transcription); not required to run Phase 0.
- A Telegram bot token from [@BotFather](https://t.me/BotFather).

## Quick start (uv)

```bash
cd course-assistant-bot
cp .env.example .env          # then edit .env and set TELEGRAM_BOT_TOKEN
uv sync --extra dev           # create venv + install runtime and dev deps
uv run oz-bot                 # start the bot in long-polling mode
```

In a second terminal you can run the worker:

```bash
uv run oz-worker
```

Health checks:

```bash
curl http://localhost:8080/healthz   # bot
curl http://localhost:8081/healthz   # worker (HEALTH_PORT + 1)
```

## Quick start (venv fallback, no uv)

```bash
cd course-assistant-bot
python3.12 -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp .env.example .env          # edit and set TELEGRAM_BOT_TOKEN
python -m app.main_bot
```

## Tests, lint, types

```bash
uv run pytest                 # unit + mocked integration; no live network calls
uv run pytest --cov=app       # with coverage
uv run ruff check .
uv run mypy app
```

All external services (Telegram, Drive, LLMs, Gmail, ASR) are mocked in tests — the
suite never makes live calls.

## Docker

```bash
cp .env.example .env          # configure first
docker compose up --build     # starts bot + worker
```

The image is multi-stage (uv build → slim runtime, non-root user, `ffmpeg` preinstalled).
Postgres/Supabase is external and not provisioned by compose.

## Configuration

All configuration — including every secret — comes from environment variables, loaded
from `.env` in development. Nothing is hardcoded; secrets are held as `SecretStr` and are
redacted from logs. See [.env.example](.env.example) for the full contract.

Phase 0 only requires `TELEGRAM_BOT_TOKEN`. Remaining variables are placeholders for
later phases and can stay blank for now.

### Required credentials (full build) and who provides them

| Variable | Phase | Notes |
|----------|-------|-------|
| `TELEGRAM_BOT_TOKEN` | 0 | From @BotFather. |
| `OWNER_TELEGRAM_IDS` | 0 | Re'em's numeric ID (operator / superadmin). Owners are implicitly admins. |
| `ADMIN_TELEGRAM_IDS` | 5 | Alex's and Sagy's numeric IDs (comma-separated). |
| `GOOGLE_OAUTH_*` *(default)* / `GOOGLE_SA_JSON` *(upgrade)* | 2 | Drive auth. **Decision: OAuth with Re'em's own Google account for v1** — Re'em already has full view access, so this needs nothing from Alex or Sagy. Set the OAuth app to **Internal / In-production** so the refresh token does not expire. Optional later upgrade: a Service Account, after which the root-folder owner (Sagy) shares the course folder with the SA email as Viewer. |
| `HW_TO_EMAIL`, `HW_CC_EMAIL` | 4 | Recipients via env, never hardcoded. To = Alex; CC = Sagy (comma-separated supports his two addresses). |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` | 3 | At least one required then; OpenAI also powers ASR + embeddings. |
| `SUPABASE_DB_URL` / `DATABASE_URL` | 2+ | Postgres+pgvector for prod; SQLite for dev. |
| `WEBHOOK_URL` | 7 | Public HTTPS URL for production webhook mode. |

### Roles

| Role | Who | Capabilities |
|------|-----|--------------|
| Owner / superadmin | Re'em (`OWNER_TELEGRAM_IDS`) | Everything admins can do, plus manage the admin list, edit `lesson_map`, force schedule refresh, rebuild the RAG index. |
| Admin | Alex, Sagy (`ADMIN_TELEGRAM_IDS`) | Upload to broadcast, post announcements, override schedule entries. |
| Student | Everyone else | On-demand features and opt-in broadcasts. |

Use `/myid` to collect numeric Telegram IDs: each person messages the bot once and sends
back the number it reports. Add owners to `OWNER_TELEGRAM_IDS` and Alex/Sagy to
`ADMIN_TELEGRAM_IDS`. (Most role-gated commands land in later phases; `/myid` works now.)

### Generating a Google OAuth refresh token

Drive reads, Gmail send, and the optional admin Drive-write all use one OAuth refresh
token. Create a **Desktop** OAuth client in Google Cloud Console (set the app to
**Internal / In-production** so the refresh token doesn't expire), download its
`client_secret.json`, then run the one-time helper:

```bash
uv sync --extra auth
uv run python scripts/get_google_token.py --client-secrets /path/to/client_secret.json
```

It opens a browser for consent (Drive read + `drive.file` + `gmail.send` scopes) and prints
`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and `GOOGLE_OAUTH_REFRESH_TOKEN` for
you to paste into `.env`. Nothing is written to disk by the helper.

## Project layout

```
course-assistant-bot/
  app/
    bot/          # PTB handlers + application factory
    graph/        # LangGraph orchestrator (Phase 3)
    services/     # service interfaces (drive, schedule, llm, email, ...)
    domain/       # pydantic domain types + lesson_map (Phase 2)
    repo/         # SQLAlchemy models + repositories (Phase 2+)
    workers/      # APScheduler jobs (Phase 5)
    core/         # settings, logging, errors, health, i18n
    main_bot.py   # bot entry point
    main_worker.py# worker entry point
  data/           # schedule.yaml / lesson_map.yaml / resources.yaml, local DB
  migrations/     # Alembic (prod schema migrations)
  scripts/        # get_google_token.py (one-time OAuth helper)
  tests/          # unit + integration (mocked)
  .env.example  Dockerfile  docker-compose.yml  pyproject.toml  README.md  PLAN.md
```

## Database schema

- Dev: `init_db()` runs `create_all` on startup (zero-config SQLite).
- Prod (Supabase Postgres): apply migrations once with `uv run alembic upgrade head`
  (the URL is resolved from `SUPABASE_DB_URL`/`DATABASE_URL`).

## Deploy on EC2 (single process)

```bash
# On the box (Ubuntu): install uv + ffmpeg, clone, configure
sudo apt-get update && sudo apt-get install -y ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
cd course-assistant-bot && cp .env.example .env   # fill in secrets
uv sync --extra auth                         # + --extra scrape for schedule re-scrape
uv run alembic upgrade head                  # if using Supabase Postgres
```

Run it as a systemd service (long-polling; no public URL needed):

```ini
# /etc/systemd/system/oz-bot.service
[Unit]
Description=Oz VeRuach Course Assistant
After=network-online.target

[Service]
WorkingDirectory=/home/ubuntu/course-assistant-bot
ExecStart=/home/ubuntu/.local/bin/uv run oz-bot
Restart=always
RestartSec=5
EnvironmentFile=/home/ubuntu/course-assistant-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now oz-bot
sudo systemctl status oz-bot      # health: curl http://localhost:8080/healthz
```

For production webhook mode instead of polling, set `RUN_MODE=webhook` + `WEBHOOK_URL`
(a public HTTPS endpoint) and open the port. Docker: `docker compose up --build -d`.

## Runbook

- **Add an admin:** owner sends `/admin add <telegram_id>` (get IDs via `/myid`). Remove
  with `/admin remove <id>`; persistent admins live in the DB, owners in `.env`.
- **Re-map a lesson:** owner `/map suggest` then `/map link <YYYY-MM-DD> rec=<n> pres=<n>`.
- **Force a schedule refresh:** owner `/refresh_schedule` (re-scrapes the site, reports a
  diff; apply changes with `/schedule_update <date> title=... time=... type=...`).
- **Rebuild the RAG index:** owner `/reindex`.
- **Rotate keys:** edit `.env`, then `sudo systemctl restart oz-bot`. For Google, re-run
  `scripts/get_google_token.py` to mint a fresh refresh token.
- **Observability:** structured JSON logs (`journalctl -u oz-bot`), `/healthz`, `/metrics`.
