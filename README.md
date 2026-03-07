<div align="center">

# 🕒 FacilitaPonto.com

**O ponto digital simples e moderno para a sua empresa**

<br>

<!-- Stack badges -->
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-REST%20Framework-A30000?logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5.3-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev/)

<!-- Infra badges -->
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![MinIO](https://img.shields.io/badge/MinIO-S3%20Compatible-C72E49?logo=minio&logoColor=white)](https://min.io/)
[![JWT](https://img.shields.io/badge/Auth-JWT-000000?logo=jsonwebtokens&logoColor=white)](https://jwt.io/)

<!-- Quality badges -->
[![Pytest](https://img.shields.io/badge/Pytest-Tests-0A9EDC?logo=pytest&logoColor=white)](https://pytest.org/)
[![Ruff](https://img.shields.io/badge/Ruff-Lint-D7FF64?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)
[![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-orange)](#status-do-projeto)
[![Privado](https://img.shields.io/badge/Repositório-Privado-red)](https://github.com/melojrx/facilitaponto)

<br>

[📖 Sobre](#sobre-o-projeto) · [📊 Status](#status-do-projeto) · [🏗️ Arquitetura](#arquitetura-resumida) · [🚀 Como rodar](#como-rodar-localmente) · [🔌 Endpoints](#endpoints-principais-já-disponíveis) · [👤 Autor](#autor)

</div>

---

## Sobre o projeto

O **FacilitaPonto.com** é um sistema SaaS multitenant de controle de ponto eletrônico com reconhecimento facial, voltado para empresas que precisam de uma operação simples, moderna e aderente ao contexto legal brasileiro (REP-P / Portaria 671/2021).

O projeto está organizado para evoluir em três frentes:

- 🔧 **Backend Django** — API REST + base para painel administrativo
- 📱 **App mobile** — tablet na portaria, com operação online/offline
- ⚖️ **Engine legal** — AFD/AEJ, comprovantes e trilha de auditoria

---

## Status do projeto

### ✅ Entregas concluídas

- Fundação do backend e ambiente Docker
- Multitenancy com isolamento por tenant
- Autenticação JWT (usuário e dispositivo)
- Cadastro de funcionários + sequência NSR atômica por tenant
- Módulo de biometria DEV-005 concluído (consentimento, enroll, verify e cache mobile):
  - Consentimento LGPD
  - Enroll de embedding facial criptografado
  - Verificação biométrica online (`/api/biometrics/verify/`)
  - Endpoint de embeddings para cache mobile (`/api/employees/embeddings/`)
- Núcleo de ponto DEV-006 concluído:
  - Registro imutável com NSR atômico por tenant
  - Registro online (`/api/attendance/register/`)
  - Sincronização offline com idempotência (`/api/attendance/sync/`)
  - Regras de ordenação de batidas (E/S/II/FI)
  - Upload real da foto em storage S3/MinIO + hash SHA-256 para auditoria
- Comprovante eletrônico DEV-007 concluído:
  - Geração automática ao registrar ponto
  - Endpoint de consulta (`/api/attendance/{id}/comprovante/`)

### 🔍 Qualidade atual

| Verificação | Status |
|---|---|
| Lint (`ruff check .`) | ✅ Passando |
| Migrações (`--check --dry-run`) | ✅ Sem drift |
| Testes backend (`apps/`) | ✅ Passando |

---

## Arquitetura resumida

| Camada | Tecnologia |
|---|---|
| **Backend** | Django + DRF |
| **Banco de dados** | PostgreSQL 16 |
| **Fila e assíncrono** | Redis + Celery |
| **Storage de objetos** | MinIO (S3 compatível) |
| **Autenticação** | JWT com claims de tenant e tipo de token |
| **Multitenancy** | `tenant_id` + middleware + manager tenant-aware |

---

## Estrutura do repositório

```text
facilitaponto/
├── backend/          # Django, API REST, apps de domínio
├── docs/             # PRD, backlog, roadmap e layouts legais
├── mobile/           # App mobile (em evolução)
├── scripts/          # Scripts utilitários/smoke
├── docker-compose.yml
└── Makefile
```

### Apps backend

| App | Responsabilidade |
|---|---|
| `tenants` | Modelo de empresa e isolamento multitenant |
| `accounts` | Usuários, dispositivos e autenticação |
| `employees` | Funcionários e sequência NSR |
| `biometrics` | Consentimento, enroll, verify e embeddings |
| `attendance` | Registro de ponto, sync offline, NSR e comprovante |
| `legal_files` | Comprovante eletrônico e base para AFD/AEJ |

---

## Pré-requisitos

- Docker + Docker Compose
- *(Opcional)* Ambiente virtual Python local para comandos fora do container

---

## Como rodar localmente

**1. Clonar o repositório**

```bash
git clone https://github.com/melojrx/facilitaponto.git
cd facilitaponto
```

**2. Configurar variáveis de ambiente**

```bash
cp backend/.env.example backend/.env
```

**3. Subir os serviços**

```bash
docker compose up -d --build
```

**4. Aplicar migrações**

```bash
docker compose exec web python manage.py migrate
```

**5. Acessar**

| Serviço | URL |
|---|---|
| API / Admin | <http://localhost:8000> |
| MinIO Console | <http://localhost:9001> |

---

## Comandos úteis

```bash
# Stack
make run          # Subir serviços
make stop         # Parar serviços

# Banco e shell
make migrate      # Aplicar migrações
make shell        # Shell interativo Django

# Qualidade
make lint         # Ruff lint
make test         # Pytest

# Smoke tests
make smoke-dev001  # Validação técnica DEV-001
```

---

## Endpoints principais já disponíveis

### 🔐 Autenticação

| Método | Endpoint |
|---|---|
| `POST` | `/api/auth/token/` |
| `POST` | `/api/auth/token/refresh/` |
| `POST` | `/api/auth/device/register/` |

### 👷 Funcionários

| Método | Endpoint |
|---|---|
| `GET` | `/api/employees/active/` |

### 🧬 Biometria

| Método | Endpoint |
|---|---|
| `POST` | `/api/employees/{id}/consent/` |
| `POST` | `/api/employees/{id}/enroll/` |
| `POST` | `/api/biometrics/verify/` |
| `GET` | `/api/employees/embeddings/` |

### 🕒 Ponto e comprovante

| Método | Endpoint |
|---|---|
| `POST` | `/api/attendance/register/` |
| `POST` | `/api/attendance/sync/` |
| `GET` | `/api/attendance/{id}/comprovante/` |

---

## Documentação do produto

| Documento | Descrição |
|---|---|
| [`docs/PRD.md`](docs/PRD.md) | Product Requirements Document |
| [`docs/PRODUCT_BACKLOG.md`](docs/PRODUCT_BACKLOG.md) | Backlog priorizado |
| [`docs/DEV_ROADMAP.md`](docs/DEV_ROADMAP.md) | Roadmap de desenvolvimento |
| [`docs/LAYOUT_AFD.md`](docs/LAYOUT_AFD.md) | Layout do Arquivo de Fonte de Dados |
| [`docs/LAYOUT_AEJ.md`](docs/LAYOUT_AEJ.md) | Layout do Arquivo Eletrônico de Jornada |

---

## Segurança e conformidade

- 🔒 Dados biométricos tratados como **sensíveis** (LGPD)
- 🔑 Embeddings faciais armazenados de forma **criptografada**
- 🗂️ Fotos de registro armazenadas em **storage S3/MinIO** com hash SHA-256 de integridade
- 🏢 **Separação de dados por tenant** sem vazamento cross-tenant
- 📋 Evolução planejada para trilhas de auditoria e engine legal completa (AFD/AEJ)

---

## Autor

<div align="left">
<img src="https://github.com/melojrx.png" alt="Avatar de Junior Melo" width="72" style="border-radius:50%;vertical-align:middle;margin-right:12px">
<strong>Junior Melo</strong> — Desenvolvedor do projeto
</div>

<br>

[![GitHub](https://img.shields.io/badge/@melojrx-181717?logo=github&logoColor=white)](https://github.com/melojrx) · [![Email](https://img.shields.io/badge/jrmeloafrf@gmail.com-EA4335?logo=gmail&logoColor=white)](mailto:jrmeloafrf@gmail.com)

---

<div align="center">

Desenvolvido com ❤️ e ☕ para melhorar a gestão das pequenas empresas brasileiras

</div>
