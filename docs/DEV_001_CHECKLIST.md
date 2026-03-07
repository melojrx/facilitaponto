# DEV-001 Checklist (Versionado)
**Versão:** 1.0  
**Data:** 2026-03-07  
**Escopo:** fechamento profissional da DEV-001 sem overengineering

## 1) Itens obrigatórios
- [x] Estrutura de repositório criada e organizada (`backend/`, `docs/`, `mobile/`)
- [x] `docker-compose.yml` com `web`, `db`, `redis`, `celery`, `minio`
- [x] `requirements.txt` com stack base e ferramentas de qualidade
- [x] Settings separados (`base.py`, `development.py`, `production.py`)
- [x] Suporte a `DATABASE_URL` com fallback para `DB_*`
- [x] `.env.example` documentado e atualizado
- [x] `Makefile` com comandos operacionais principais
- [x] Script de smoke test versionado (`scripts/smoke_dev001.sh`)

## 2) Hardening mínimo aplicado
- [x] Build não depende mais de `collectstatic` em tempo de imagem
- [x] `entrypoint` valida conexão com DB via configuração ativa (inclui `DATABASE_URL`)
- [x] `celery` configurado para execução sem root via flags `--uid/--gid`

## 3) Critério de aceite DEV-001
- [x] `docker compose up -d --build` sobe os serviços sem erro
- [x] `docker compose ps` mostra stack ativa
- [x] `python manage.py check` passa
- [x] `python manage.py makemigrations --check --dry-run` sem drift
- [x] `ruff check .` sem erros
- [x] `pytest apps/` passando

## 4) Comando único de validação
```bash
make smoke-dev001
```

## 5) Resultado esperado
Execução completa sem falhas e mensagem final:  
`[DEV-001] Smoke test concluído com sucesso.`
