#!/bin/sh
set -e

echo "Aguardando banco de dados..."
until python - <<'PY' >/dev/null 2>&1
import django
from django.db import connections

django.setup()
connections["default"].cursor()
PY
do
  sleep 1
done

echo "Rodando migrations..."
python manage.py migrate --noinput

if [ "${RUN_COLLECTSTATIC:-1}" = "1" ]; then
  echo "Rodando collectstatic..."
  python manage.py collectstatic --noinput
fi

echo "Iniciando servidor..."
exec "$@"
