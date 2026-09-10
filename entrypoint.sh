#!/bin/sh

set -e

POSTGRES_HOST="${POSTGRES_HOST:-db}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

echo "Aguardando PostgreSQL..."

while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
    sleep 1
done

echo "Banco de dados disponível."

if [ "${RUN_SETUP:-true}" = "true" ]; then
    echo "Aplicando migrations..."
    python manage.py migrate --noinput

    echo "Coletando estáticos..."
    python manage.py collectstatic --noinput
else
    echo "RUN_SETUP=false — pulando migrate/collectstatic."
fi

echo "Iniciando: $*"
exec "$@"