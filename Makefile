PYTHON = ../.venv/bin/python
DJANGO = $(PYTHON) manage.py

.DEFAULT_GOAL := help

.PHONY: help run stop migrate makemigrations shell test lint createsuperuser

help:
	@echo ""
	@echo "  Ponto Digital — Comandos disponíveis"
	@echo ""
	@echo "  make run            Sobe todos os serviços (docker compose up)"
	@echo "  make stop           Para todos os serviços"
	@echo "  make migrate        Roda as migrations pendentes"
	@echo "  make makemigrations Cria novas migrations"
	@echo "  make shell          Abre o shell Django"
	@echo "  make test           Roda a suíte de testes"
	@echo "  make lint           Roda o ruff"
	@echo "  make createsuperuser Cria superusuário"
	@echo ""

run:
	docker compose up

stop:
	docker compose down

migrate:
	docker compose exec web python manage.py migrate

makemigrations:
	docker compose exec web python manage.py makemigrations

shell:
	docker compose exec web python manage.py shell

test:
	docker compose exec web pytest apps/ -v --tb=short

lint:
	docker compose exec web ruff check .

createsuperuser:
	docker compose exec web python manage.py createsuperuser
