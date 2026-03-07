#!/bin/sh
set -e

echo "Aguardando banco de dados..."
until python -c "import psycopg2; psycopg2.connect(
    dbname='$DB_NAME', user='$DB_USER',
    password='$DB_PASSWORD', host='$DB_HOST', port='$DB_PORT'
)" 2>/dev/null; do
  sleep 1
done

echo "Rodando migrations..."
python manage.py migrate --noinput

echo "Iniciando servidor..."
exec "$@"
