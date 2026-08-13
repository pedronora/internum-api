FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.1.4 \
    POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    PATH="/opt/poetry/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY . .

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

COPY --chown=app:app --from=builder /app/.venv /app/.venv
COPY --chown=app:app --from=builder /app/internum /app/internum
COPY --chown=app:app --from=builder /app/migrations /app/migrations
COPY --chown=app:app --from=builder /app/alembic.ini /app/alembic.ini
COPY --chown=app:app --from=builder /app/pyproject.toml /app/pyproject.toml

RUN chmod +x /app/internum/infra/entrypoint.sh

USER app

EXPOSE 8000

ENTRYPOINT ["./internum/infra/entrypoint.sh"]
