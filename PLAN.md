# Oz VeRuach Course Assistant — Build Plan

The official Telegram assistant for the "Oz VeRuach" (עוז ורוח) AI-Augmented Software
Engineering course. Built phase by phase. Each phase ends with a hard stop for explicit
approval before the next begins.

## Phase Gates

| Phase | Title | Status |
|-------|-------|--------|
| 0 | Scaffold & config | Complete |
| 1 | Schedule | Complete |
| 2 | Drive read + lesson_map | Complete |
| 3 | LLM orchestrator + summaries | Complete |
| 4 | Homework submission flow | Complete |
| 5 | Notifications + admin upload | Complete |
| 6 | Recommendations + RAG | Complete |
| 7 | Hardening, optimization, deploy | Complete |

## Phase 0 — Scaffold & Config

Goal: a production-shaped skeleton that runs a `/start` + echo bot in long-polling, with
typed config, structured logging, a health endpoint, Docker delivery, empty service
interfaces, and a passing test suite. No course features yet.

### Acceptance checklist

- [x] `pyproject.toml` (uv) targets Python 3.12 with pinned-range runtime + dev deps.
- [x] Typed settings via `pydantic-settings`; all secrets come from env, never printed.
- [x] Two-tier roles: `OWNER_TELEGRAM_IDS` + `ADMIN_TELEGRAM_IDS` (owners imply admin).
- [x] `.env.example` documents every credential the full build will need (sanitized).
- [x] Structured JSON logging (`structlog`) with secret redaction.
- [x] Shared error types and user-friendly fallback message helper.
- [x] `/healthz` HTTP endpoint usable by both `bot` and `worker` processes.
- [x] Minimal async Telegram bot: `/start` onboarding + `/myid` + safe echo (long-polling).
- [x] Empty service interfaces (drive, schedule, llm, email, transcription, vectorstore,
      notifier, recommendations) with stable import paths.
- [x] `main_bot.py` and `main_worker.py` entry points.
- [x] Dockerfile (multi-stage) + docker-compose (`bot`, `worker`).
- [x] README with setup (uv + venv fallback), run, test, and required-secrets sections.
- [x] `pytest` green (33); `ruff` clean; `mypy app` clean. External services mocked in tests.

### Out of scope for Phase 0

Schedule logic, Drive integration, lesson mapping, LangGraph routing, LLM calls,
Gmail/email send, ASR/transcription, vector stores/RAG, APScheduler jobs, and any live
Telegram/Google/LLM network calls in the test suite.

## Phase 1 — Schedule (Complete)

Feature 6.1: next lesson / this week / full schedule, in he/en, all date math in
`Asia/Jerusalem`.

- [x] `data/schedule.yaml` seeded from Appendix B (35 sessions, 14 weeks).
- [x] `Session`/`Course` pydantic models with `SessionType`/`SessionStatus`.
- [x] `YamlScheduleService` with an injectable clock: next / this-week (Sun-Sat) / full
      (grouped by week) / holiday-today / course-finished / status.
- [x] Deterministic he/en keyword router (`app/bot/router.py`) as the pre-LLM fast-path.
- [x] i18n schedule strings + formatting handlers; `/schedule` command + text routing.
- [x] Tests: week boundaries, next/today, course-finished, holiday, two-same-day,
      grouped weeks, router he/en coverage, integration flow (frozen clock). 74 pass.

## Phase 2 — Drive read + lesson_map (Complete)

Read-only Drive access, the C1 mapping layer, and features 6.4 + 6.6.

- [x] Pluggable-auth `GoogleDriveService` (OAuth v1 default / service account), read-only,
      `to_thread` + retry/backoff; never downloads recordings (C4).
- [x] Recursive type-aware material classifier (C5) and tolerant recording part-sort (C2,
      handles `part1.mp4`/`part 3.mp4`, gaps, unknown indices).
- [x] `lesson_map` seeded from Appendix C; `LessonMap` model + YAML-backed
      `YamlLessonMapStore` (atomic writes) behind a repository interface (DB swap = Phase 5).
- [x] `RecordingsService` (6.6): last / specific / all as Drive links; empty folders ->
      "not uploaded yet" (C3); missing links -> "not linked yet" (C1).
- [x] `HomeworkService` (6.4): newest lesson's HW docs (lists multiple). LLM 3-5 line
      requirements summary deferred to Phase 3.
- [x] Owner-gated `/map` (view / suggest / link) + auto-suggester (never auto-applies).
- [x] Router extended with recording + homework intents (he/en) and lesson-ref capture.
- [x] Tests against Appendix D fixtures + FakeDriveService (C1-C5 quirks, admin gating).
      111 pass; ruff + mypy clean.

## Phase 3 — LLM orchestrator + summaries (Complete)

Model layer + feature 6.2. Deviation (approved by silence): a thin provider-adapter
registry behind the existing `ChatModel`/`ModelRegistry` interfaces instead of full
LangGraph/LangChain - same seams, lighter deps, swappable later.

- [x] Multi-provider `DefaultModelRegistry` (anthropic/openai/google), role->model from
      Section 7 defaults + env overrides; graceful cross-provider fallback; never crashes
      when a provider key is missing.
- [x] Versioned Section 12 prompts; LLM router fallback node with defensive JSON parsing,
      invoked only when the keyword router misses.
- [x] Content extraction (Google export + pdf/docx/pptx) with size cap; summary cache
      (content hash + TTL).
- [x] `SummaryService` (6.2): slides/HW default, transcript for deep/no-slides; caches
      `(lesson_key, source_hash)`; no-materials and llm-unavailable handled.
- [x] `WhisperTranscriptionService` (ffmpeg + ASR + cache), worker-safe; mocked in tests.
- [x] Router extended with `summarize` (+deep) intent; dispatch + i18n wired.
- [x] Tests: registry fallback, router JSON parsing, summaries + cache + deep, extraction
      dispatch, transcription cache - all external calls mocked. 141 pass; ruff + mypy clean.

## Phase 4 — Homework submission flow (Complete)

Feature 6.5 + 4.3 + C8.

- [x] `SubmissionDraft` state machine (drafting->preview->confirmed->sent/cancelled) with
      validation and `missing_fields`.
- [x] Deterministic email composition: subject byte-for-byte per 4.3 (en dash), body per
      the prescribed structure; recipients only from `HW_TO_EMAIL`/`HW_CC_EMAIL`
      (comma-separated CC supported).
- [x] `EmailService` backends: `GmailEmailService` (gmail.send, lazy client) +
      `SmtpEmailService`; `build_email_service` selection; graceful "not configured".
- [x] `ConversationHandler` draft->preview->send with attachments (size cap), GitHub link,
      inline Send/Edit/Cancel, no-attachment warn, send-failure retry, double-send guard.
- [x] C8 guardrail: `looks_like_solve_request` + labeled starter-scaffold disclaimer; wired
      into the text handler; `homework_submit` intent + `/submit` entry.
- [x] Tests: subject/body byte-for-byte, state machine, finalize/send (To/Cc/attachments,
      double-send, failure), backend selection, C8, conversation step handlers. 172 pass;
      ruff + mypy clean.

## Phase 5 — Notifications + admin upload (Complete)

Features 6.7, 6.8, 6.9 + the datastore.

- [x] SQLAlchemy 2.x async datastore (subscribers, drive_state, broadcast_log, audit_log)
      via `create_all`; Supabase Postgres prod / SQLite dev; repositories per table.
      (Alembic migrations deferred to Phase 7.)
- [x] `TelegramNotifier`: token-bucket throttling, `RetryAfter`/429 backoff, single retry,
      partial-failure counts, `broadcast_log` idempotency (no double-send).
- [x] APScheduler worker hosting the `DriveWatcher`: recursive enumerate -> diff vs
      `drive_state` -> classify -> resolve lesson -> broadcast; first run seeds silently;
      `(file_id, modifiedTime)` keys prevent re-notify.
- [x] `GoogleDriveUploader` (create-only, scoped, `DRIVE_WRITE_ENABLED`-gated) + admin
      upload->broadcast handler (caption parse, optional Drive filing, non-admin refuse).
- [x] Subscriptions: `/start` registers + language, `/stop`, `/menu` inline keyboard.
- [x] Tests with in-memory SQLite + mocked Telegram/Drive: repos, notifier
      idempotency/partial-failure/RetryAfter, watcher first-run/no-double-notify/re-change,
      admin gating, subscriptions. 189 pass; ruff + mypy clean.

## Phase 6 — Recommendations + RAG (Complete)

Feature 6.3 + the RAG index, plus a Google OAuth token helper.

- [x] `scripts/get_google_token.py` (one-time refresh-token helper, `--extra auth`) +
      README setup section.
- [x] `materials_index` table; DB-backed `DbVectorStore` (JSON embeddings + cosine, runs on
      SQLite + Supabase; pgvector accel noted for Phase 7) + `OpenAIEmbedder` behind the
      `Embedder`/`VectorStore` interfaces.
- [x] `data/resources.yaml` curated topic->links + `ResourcesCatalog` (key/alias match).
- [x] `MaterialsIndexer` (walk -> extract -> chunk -> embed -> upsert) + owner `/reindex`.
- [x] `CourseRecommendationService` (curated + RAG internal + optional web search behind a
      disabled-by-default interface) + `materials` intent + handler grouped "From our
      course" / "Recommended reading".
- [x] `init_db()` now also runs on bot startup (subscribers + RAG tables).
- [x] Tests: catalog lookup, vector store ranking/clear, indexer+chunking, recommendation
      combine/format, router materials/submit intents, materials flow. 208 pass; ruff +
      mypy clean.

## Phase 7 — Hardening, optimization, deploy (Complete)

Finishes the spec and runs as one process.

- [x] Single-process default: scheduler runs in the bot's event loop
      (`RUN_SCHEDULER_IN_BOT`); split mode still available via `oz-worker`.
- [x] Scheduler hosts Drive watcher + weekly schedule re-scrape + nightly precompute.
- [x] Playwright schedule scraper (lazy/optional) + diff + `/refresh_schedule`; parser
      tested offline against a captured fixture (DOM captured via Playwright MCP).
- [x] Nightly precompute warms the shared summary cache.
- [x] Admin commands: `/announce` (preview->send), `/schedule_update` (manual override),
      `/refresh_schedule`, `/admin add|remove|list` (DB-backed), `/help`.
- [x] Per-user cooldown on heavy ops + "working on it" UX; in-process metrics + `/metrics`.
- [x] Alembic async migrations + baseline (verified `upgrade head`); `create_all` for dev.
- [x] Full README + EC2 single-process deploy (systemd/compose) + runbook.
- [x] Tests: scraper/diff, admin commands, rate-limit/metrics, scheduler wiring. 224 pass;
      ruff + mypy clean; coverage ~74%.
- [x] Bug fixed: dotenv inline-comment-as-value on blank vars (cleaned `.env`/`.env.example`
      + a DB-URL guard) which had been silently misconfiguring Drive/LLM/email/DB.

## Operating Rules (all phases)

1. Phased execution with a hard stop after each phase.
2. Stop and ask on ambiguity; never invent course facts, Drive IDs, or schedule entries.
3. Drive access for the course folder is read-only; the only write path is the scoped
   admin-upload feature, which creates (never overwrites) files.
4. No secrets in code; typed settings from env; never commit `.env`.
5. Production hygiene: async I/O, type hints, structured logs, retries/backoff,
   idempotency on notify/send, health checks.
6. Test as you go; mock all external services.
7. Explain decisions in one line, then act.
