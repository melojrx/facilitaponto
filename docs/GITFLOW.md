# Git Flow — Ponto Digital (REP-P SaaS)

## Objetivo

Definir o fluxo único de branches, PRs e deploy para o projeto **Ponto Digital**, um SaaS multitenant de ponto eletrônico com reconhecimento facial. O fluxo cobre as três frentes do projeto: **Backend Django**, **App Mobile React Native** e **Engine Biométrica**.

---

## Contexto do Projeto

| Camada          | Tecnologia                       | CI/CD                              |
|-----------------|----------------------------------|------------------------------------||
| Backend         | Django 5 + DRF + Celery          | GitHub Actions → EasyPanel (VPS)   |
| App Mobile      | React Native + Expo (EAS Build)  | EAS Build (preview/prod)           |
| Infraestrutura  | PostgreSQL + Redis + MinIO       | docker-compose.yml (DEV local)     |
| Proxy Reverso   | Traefik (gerenciado pelo EasyPanel) | Automático — sem config manual  |

### Ambientes Mapeados

| Branch    | Ambiente        | Infraestrutura                          | Ato Automático                                    |
|-----------|-----------------|-----------------------------------------|---------------------------------------------------|
| `develop` | **DEV local**   | `docker-compose.yml` na máquina do dev | N/A — sobe manualmente com `docker compose up`    |
| `main`    | **PROD (VPS)**  | EasyPanel + Traefik na VPS              | Push → GitHub Actions → EasyPanel webhook → deploy|

> **Arquitetura de PROD:** O ambiente de produção roda no EasyPanel instalado na VPS. O EasyPanel gerencia os containers (Django, Celery, PostgreSQL, Redis, MinIO) e o Traefik é o proxy reverso — **não usamos Nginx**. SSL e roteamento são gerenciados pelo próprio EasyPanel/Traefik automaticamente.

> **Sem ambiente HML:** O projeto é solo-dev com escala pequena. Não há ambiente de homologação separado. A validação ocorre localmente antes do merge em `main`.

---

## Modelo de Branches

### Permanentes
| Branch    | Propósito                                          |
|-----------|----------------------------------------------------|
| `develop` | Desenvolvimento local — integração e validação DEV |
| `main`    | Produção — push aqui = deploy automático na VPS    |

### Temporárias
| Prefixo          | Quando usar                                     | Base       |
|------------------|-------------------------------------------------|------------|
| `feature/*`      | Nova funcionalidade (DEV-XXX do roadmap)        | `develop`  |
| `fix/*`          | Bug não crítico encontrado em DEV/HML           | `develop`  |
| `hotfix/*`       | Correção urgente no que está em HML/PROD        | `main`     |
| `chore/*`        | Atualização de dependências, Makefile, Docker   | `develop`  |
| `refactor/*`     | Refatoração interna sem mudança de contrato     | `develop`  |
| `docs/*`         | Apenas documentação (ROADMAP, PRD, ADRs)        | `develop`  |
| `mobile/*`       | Funcionalidade exclusiva do app React Native    | `develop`  |
| `legal/*`        | Mudanças na engine AFD/AEJ (legalidade crítica) | `develop`  |

---

## Fluxo Padrão (feature, fix, mobile, legal, chore)

### 1. Criar branch a partir de `develop`
```bash
git checkout develop
git pull origin develop
git checkout -b feature/DEV-XXX-descricao-curta
```

> Use o código da tarefa do roadmap como prefixo (ex: `feature/DEV-005-biometrics-enroll`).

### 2. Validar localmente (Backend)
```bash
# Subir todos os serviços
docker compose up -d

# Rodar migrations
docker compose exec web python manage.py migrate

# Rodar testes
docker compose exec web pytest apps/ -v --tb=short

# Lint
docker compose exec web ruff check .
```

### 3. Validar localmente (Mobile)
```bash
# Checar tipos TypeScript
npx tsc --noEmit

# Rodar testes unitários
jest --watchAll=false

# Verificar build
npx expo export --platform android --dev
```

### 4. Commits (Conventional Commits obrigatório)
```bash
git add .
git commit -m "feat(attendance): adicionar endpoint de sync offline"
git push -u origin feature/DEV-006-attendance-sync
```

### 5. Abrir PR para `develop`
- Título: `[DEV-006] feat(attendance): sync de registros offline`
- Usar o **Checklist de PR** abaixo antes de submeter
- Aguardar CI passar antes de mergear (ruff + pytest + build Docker)

### 7. Quando pronto para PROD → abrir PR `develop → main`
- Incluir no PR: o que foi testado localmente, quais DEV-XXX foram incluídos
- Após merge, **EasyPanel detecta o push na `main` via webhook e faz deploy automático na VPS**
- Verificar logs no painel EasyPanel após deploy
- Testar as endpoints críticas em produção (ponto, biometria, AFD)

---

## Fluxo de Hotfix (correção urgente em HML/PROD)

### 1. Criar hotfix a partir de `main`
```bash
git checkout main
git pull origin main
git checkout -b hotfix/descricao-do-bug
```

### 2. Corrigir e validar
```bash
docker compose up -d
docker compose exec web pytest apps/ -v --tb=short
docker compose exec web ruff check .
```

### 3. PR para `main`
- Título: `[HOTFIX] fix: descricao do bug`
- Revisão obrigatória antes do merge

### 4. Após merge em `main`, sincronizar `develop`
```bash
git checkout develop
git pull origin develop
git merge --no-ff main -m "chore: sync hotfix back to develop"
git push origin develop
```

> **Regra:** Hotfix em `main` SEMPRE deve voltar para `develop`. Nunca deixar divergir.

---

## Fluxo Mobile (EAS Build)

Para releases do app React Native:

```bash
# Build de preview (APK interno para testes)
eas build --platform android --profile preview

# Build de produção (APK para tablet da portaria)
eas build --platform android --profile production
```

> Builds EAS **não são automáticos via GitHub Actions**. São disparados manualmente após validação em HML.

---

## Convenções de Nomenclatura

### Branches
```
feature/DEV-005-biometrics-enroll
feature/DEV-010-mobile-setup
fix/DEV-006-attendance-nsr-gap
hotfix/csrf-auth-device
mobile/DEV-012-face-detection-ui
legal/DEV-021-afd-generator-portaria671
chore/upgrade-django-5-1
docs/update-gitflow
```

### Commits (Conventional Commits)
```
feat(biometrics): adicionar verificação de threshold configurável
fix(attendance): corrigir geração de NSR em requests concorrentes
refactor(tenants): extrair TenantManager para módulo separado
test(afd): adicionar validação de layout Portaria 671
docs(api): documentar endpoint POST /api/attendance/sync/
chore(deps): atualizar deepface para versão estável
build(docker): configurar multi-stage build para produção
ci(actions): adicionar step de ruff no workflow de PR
mobile(offline): implementar SyncService com WatermelonDB
legal(afd): corrigir encoding ISO-8859-1 no AFDGenerator
```

### Tags (SemVer) — apenas para marcar marcos históricos
```
v1.0.0       → MVP em produção (marco, não dispara deploy)
v1.1.0       → Iteração com novas funcionalidades
v1.0.1       → Patch/hotfix de produção
```
> Tags são opcionais e servem apenas para marcar versões no histórico. O deploy de PROD é disparado pelo **push na `main`**, não por tags.

---

## Checklist de PR (OBRIGATÓRIO)

Antes de abrir qualquer PR, confirmar:

- [ ] Branch criada a partir da base correta (`develop` ou `main` para hotfix)
- [ ] Referência ao DEV-XXX do roadmap no título do PR
- [ ] `ruff check .` retorna sem erros
- [ ] `pytest apps/ -v` passa sem falhas
- [ ] Migrações Django incluídas se houver mudança no model
- [ ] Sem credenciais, senhas ou chaves em diff (segredos no `.env`)
- [ ] Impacto em multitenancy revisado (queries sempre filtradas por `tenant_id`)
- [ ] Impacto em segurança/LGPD analisado (especialmente embeddings faciais)
- [ ] NSR e imutabilidade de registros não foram comprometidos
- [ ] Documentação atualizada se houve mudança de contrato de API
- [ ] TypeScript sem erros em mudanças mobile (`npx tsc --noEmit`)

---

## Regras de Ouro

1. **Nunca commitar direto em `main` ou `develop`.**
2. **Toda mudança passa por PR** — sem exceções.
3. **Teste local obrigatório** antes de abrir PR.
4. **O CI deve estar verde** antes do merge.
5. **Hotfix em `main` SEMPRE volta para `develop`** — sem divergência.
6. **Branches temporárias são deletadas após merge.**
7. **NSR e registros de ponto são imutáveis** — qualquer mudança que toque nessa lógica exige revisão especializada.
8. **Dados biométricos são sensíveis (LGPD)** — qualquer mudança no modelo `FacialEmbedding` exige discussão antes do PR.

---

## Deploy PROD — EasyPanel + Traefik

### Fluxo automático
```
Push na `main`
  → GitHub Actions: ruff + pytest
  → EasyPanel webhook detecta push
  → EasyPanel faz pull do repo GitHub e builda o Dockerfile
  → Restará os services com a nova imagem
  → Traefik roteia tráfego (SSL automático)
```

> **Como o EasyPanel funciona:** Cada serviço (`web`, `celery`) é configurado no EasyPanel apontando para o repositório GitHub + caminho do `Dockerfile`. Não existe `docker-compose.prod.yml` — o EasyPanel gerencia os containers individualmente via UI.

### Serviços gerenciados pelo EasyPanel
| Service       | Tecnologia           | Notas |
|---------------|----------------------|-------|
| `web`         | Django + Gunicorn    | Imagem buildada pelo GitHub Actions |
| `celery`      | Celery Worker        | Mesmo Dockerfile, entrypoint diferente |
| `db`          | PostgreSQL 16        | Volume persistente no EasyPanel |
| `redis`       | Redis                | Cache + broker Celery |
| `minio`       | MinIO                | Storage de fotos + AFD/AEJ |
| `traefik`     | Traefik (built-in)   | Proxy reverso + SSL — gerenciado pelo EasyPanel |

> **Sem Nginx.** O Traefik já é o proxy reverso gerenciado pelo EasyPanel. Não adicionar Nginx ao compose de produção.

---

## Rollback

### PROD (EasyPanel)
Interástico preferido: no painel do EasyPanel, selectão'anterior deploy para redeploy instantâneo.

Via git se necessário:
```bash
# Reverter o commit que causou o problema e fazer push na main
git checkout main
git pull origin main
git revert <commit_hash>
git push origin main
# EasyPanel detecta o push e redeploy automático
```

### DEV (`develop`)
```bash
git checkout develop
git pull origin develop
git revert <commit_hash>
git push origin develop
```

---

## Referência Rápida de Comandos

| Ação                          | Comando                                      |
|-------------------------------|----------------------------------------------|
| Nova feature                  | `git checkout -b feature/DEV-XXX-nome`       |
| Sync branch com develop       | `git pull origin develop --rebase`           |
| Rodar testes backend          | `docker compose exec web pytest apps/ -v`    |
| Lint backend                  | `docker compose exec web ruff check .`       |
| Checar tipos mobile           | `npx tsc --noEmit`                           |
| Build APK preview             | `eas build --platform android --profile preview` |
| Criar tag de release          | `git tag v1.0.0 && git push origin v1.0.0`   |
| Deletar branch local          | `git branch -d feature/nome`                 |
| Deletar branch remoto         | `git push origin --delete feature/nome`      |

---

*Este documento é a base oficial do fluxo Git para o projeto Ponto Digital. Substituiu o `GITFLOW_CHATCOTIN_SIMPLES.md` adaptado do ChatCOTIN.*
