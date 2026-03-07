#!/usr/bin/env sh
set -eu

wait_for_db() {
  echo "Aguardando banco de dados em ${POSTGRES_HOST}:${POSTGRES_PORT}..."

  until python -c "import psycopg; psycopg.connect(host='${POSTGRES_HOST}', port=${POSTGRES_PORT}, user='${POSTGRES_USER}', password='${POSTGRES_PASSWORD}', dbname='${POSTGRES_DB}').close()" >/dev/null 2>&1; do
    sleep 2
  done

  echo "Banco de dados disponível."
}

wait_for_db

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Executando migrations..."
  alembic upgrade head
fi

echo "Iniciando API..."
exec uvicorn internum.app:app --host 0.0.0.0 --port "${PORT:-8000}"
