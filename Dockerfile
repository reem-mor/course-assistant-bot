# syntax=docker/dockerfile:1

# ---- Stage 1: build a populated virtualenv with uv ------------------------
FROM python:3.12-slim AS builder

# uv: fast, reproducible dependency installation.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Install dependencies first (cached layer) using only the manifest.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

# Now add the application source and install the project itself.
COPY app ./app
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# ---- Stage 2: lean runtime image ------------------------------------------
FROM python:3.12-slim AS runtime

# ffmpeg is needed by the transcription pipeline (Phase 3+); installing now keeps
# the runtime image stable across phases.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/app ./app
COPY data ./data

USER appuser

EXPOSE 8080 8081

# Default command runs the bot; compose overrides for the worker.
CMD ["python", "-m", "app.main_bot"]
