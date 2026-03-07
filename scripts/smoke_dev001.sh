#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[DEV-001] Validando docker compose..."
docker compose config >/dev/null

echo "[DEV-001] Subindo stack (build + up)..."
docker compose up -d --build

echo "[DEV-001] Aguardando PostgreSQL ficar pronto..."
until docker compose exec -T db pg_isready -U "${DB_USER:-postgres}" >/dev/null 2>&1; do
  sleep 1
done

echo "[DEV-001] Estado dos serviços:"
docker compose ps

echo "[DEV-001] Rodando django check..."
docker compose exec -T web python manage.py check

echo "[DEV-001] Validando drift de migrations..."
docker compose exec -T web python manage.py makemigrations --check --dry-run

echo "[DEV-001] Rodando lint..."
docker compose exec -T web ruff check .

echo "[DEV-001] Rodando testes..."
docker compose exec -T web pytest apps/ -q

echo "[DEV-001] Validando worker do Celery..."
docker compose exec -T celery celery -A config inspect ping --timeout=5 >/dev/null

echo "[DEV-001] Smoke test concluído com sucesso."
