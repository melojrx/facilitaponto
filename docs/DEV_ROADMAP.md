# Roadmap de Desenvolvimento — Sistema de Ponto Eletrônico
**Versão:** 2.1  
**Data:** 2026-03-08  
**Prazo MVP:** 8 semanas  
**Stack:** Django 5 + DRF + React Native (Expo) + PostgreSQL + Redis + Celery  

---

## Contexto para IA Desenvolvedora

Este projeto é um **SaaS multitenant de ponto eletrônico com reconhecimento facial**, enquadrado como **REP-P** conforme **Portaria 671/2021 do MTE (Brasil)**. O sistema possui três frentes:

1. **Backend Django** — API REST + painel web admin com Django Templates
2. **App Mobile React Native (Expo)** — roda em tablet Android na portaria, com suporte offline
3. **Engine Biométrica** — reconhecimento facial server-side (online) e via MLKit (offline)

O desenvolvimento é **assistido por IA**. Cada tarefa deve ser implementada seguindo os padrões definidos neste documento.

### Snapshot de execução (2026-03-08)
- Backend concluído até **DEV-007** (biometria, registro de ponto, sync offline backend, comprovante eletrônico).
- Upload de foto de batida já em **storage S3/MinIO** com `foto_hash` para auditoria.
- Ajuste prioritário aprovado: **DEV-008** para onboarding `1 conta proprietária : 1 empresa (CNPJ/CPF) : 1 tenant`.
- Próxima frente após DEV-008: **DEV-010 a DEV-013** (app mobile completo com modo offline).

---

## Convenções e Padrões

### Backend
- Python 3.12+, Django 5, DRF 3.15+
- Apps Django separados por domínio: `tenants`, `accounts`, `employees`, `attendance`, `biometrics`, `legal_files`
- Multitenancy via `tenant_id` em todas as tabelas (row-level isolation)
- Autenticação: `djangorestframework-simplejwt`
- Variáveis sensíveis via `python-decouple` + `.env`
- Testes com `pytest-django`
- Linting: `ruff`

### Mobile
- React Native com Expo SDK 51+
- TypeScript obrigatório
- Estado global: Zustand
- HTTP: Axios com interceptor de refresh token
- Banco local: WatermelonDB (SQLite)
- Biometria offline: `react-native-mlkit-face-detection` + embeddings locais
- Câmera: `expo-camera`

### Estrutura de diretórios Backend
```
backend/
├── config/               # settings, urls, wsgi, celery
├── apps/
│   ├── tenants/          # multitenancy, planos
│   ├── accounts/         # users, auth, permissões
│   ├── employees/        # funcionários, jornadas
│   ├── attendance/       # registros de ponto, NSR
│   ├── biometrics/       # embeddings, verificação facial
│   └── legal_files/      # AFD, AEJ, comprovantes
├── core/                 # mixins, base models, utils
└── tests/
```

---

## SEMANAS 1–2 — Fundação do Backend

### DEV-001 — Setup do Projeto
**Referência:** PB-001, PB-002, PB-003  
**Estimativa:** 4h

Tarefas:
- [x] Criar repositório com estrutura de diretórios definida acima
- [x] `docker-compose.yml` com serviços: `web`, `db` (PostgreSQL 16), `redis`, `celery`, `minio`
- [x] `requirements.txt` com: django, djangorestframework, djangorestframework-simplejwt, celery, redis, psycopg2-binary, python-decouple, deepface, tf-keras, Pillow, boto3, ruff, pytest-django
- [x] Settings base com `python-decouple`: DATABASE_URL, REDIS_URL, MINIO config, SECRET_KEY, BIOMETRIA_KEY (Fernet)
- [x] Settings separados: `base.py`, `development.py`, `production.py`
- [x] `.env.example` documentado
- [x] `Makefile` com comandos: `make run`, `make migrate`, `make test`, `make shell`

**Critério de aceite:** `docker-compose up` sobe todos os serviços sem erro.

---

### DEV-002 — App Tenants (Multitenancy)
**Referência:** PB-001, PB-010  
**Estimativa:** 6h

Tarefas:
- [x] Model `Tenant` com campos: `id` (UUID), `cnpj`, `razao_social`, `nome_fantasia`, `registro_inpi`, `ativo`, `plano`, `created_at`
- [x] Mixin `TenantModelMixin` com `tenant = FK(Tenant)` + `tenant_id` em todas as queries via manager customizado
- [x] Manager `TenantManager` que filtra automaticamente por `tenant` do request
- [x] Middleware `TenantMiddleware` que resolve o tenant pelo JWT ou subdomínio e injeta no request
- [x] Admin Django básico para `Tenant`
- [x] Migration inicial

**Critério de aceite:** Dados de tenants diferentes não aparecem nas queries um do outro.

---

### DEV-003 — App Accounts (Usuários e Auth)
**Referência:** PB-005  
**Estimativa:** 5h

Tarefas:
- [x] Model `User` customizado herdando `AbstractBaseUser`: `email` como username, `tenant FK`, `role` (admin, gestor, viewer)
- [x] Endpoint `POST /api/auth/token/` — login retorna access + refresh JWT com `tenant_id` no payload
- [x] Endpoint `POST /api/auth/token/refresh/`
- [x] Endpoint `POST /api/auth/device/register/` — registra device_id do tablet, retorna JWT de dispositivo
- [x] Permissão customizada `IsTenantMember` para DRF
- [x] Permissão `IsDeviceToken` para endpoints exclusivos do app mobile

**Critério de aceite:** Token de um tenant não acessa endpoints de outro tenant.

---

### DEV-004 — App Employees (Funcionários)
**Referência:** PB-011, PB-013, PB-014  
**Estimativa:** 6h

Tarefas:
- [x] Model `Employee`: `tenant FK`, `nome`, `cpf` (único por tenant), `pis` (11 dígitos — obrigatório AFD), `email`, `ativo`, `created_at`
- [x] Model `NSRSequence`: `tenant FK`, `ultimo_nsr` (BigInt) — controla sequência por tenant
- [x] Função `get_next_nsr(tenant_id)` — atômica via `SELECT FOR UPDATE` no PostgreSQL
- [x] CRUD de funcionários via Django Admin (painel web)
- [x] API endpoint `GET /api/employees/active/` — retorna lista para o app sincronizar

**Critério de aceite:** NSR gerado é sempre único e sequencial por tenant, mesmo em requests concorrentes.

---

### DEV-005 — App Biometrics + Consentimento LGPD (Cadastro de Embedding)
**Referência:** PB-012, PB-110  
**Estimativa:** 10h

> ⚠️ **LGPD (Art. 11):** O consentimento biométrico é pré-requisito obrigatório do enroll. Nenhum embedding pode ser coletado sem consentimento registrado.

Tarefas — Consentimento (pré-requisito do enroll):
- [x] Model `ConsentimentoBiometrico`: `employee FK`, `timestamp`, `aceito` (BooleanField), `ip_origem`, `versao_termo`
- [x] Migration inicial do model
- [x] Endpoint `POST /api/employees/{id}/consent/` — registra consentimento do funcionário
- [x] Guard no enroll: bloquear `cadastrar_embedding()` se não houver `ConsentimentoBiometrico.aceito = True`

Tarefas — Engine Biométrica:
- [x] Model `FacialEmbedding`: `employee FK`, `embedding_data` (BinaryField — criptografado), `created_at`, `ativo`
- [x] `BiometriaService.cadastrar_embedding(employee, imagem_bytes)`:
  - Verifica consentimento ativo antes de prosseguir
  - Gera embedding via `DeepFace.represent(img, model_name="ArcFace", detector_backend="retinaface")`
  - Valida qualidade mínima (1 rosto detectado)
  - Criptografa vetor resultante com `Fernet(settings.BIOMETRIA_KEY)`
  - Salva no model
- [x] `BiometriaService.verificar(employee, imagem_bytes) -> dict`:
  - Descriptografa embedding armazenado
  - Executa `DeepFace.verify()` com `model_name="ArcFace"`, `detector_backend="retinaface"`, `anti_spoofing=True`
  - Retorna `{autenticado: bool, distancia: float, threshold: float}`
- [x] Endpoint `POST /api/employees/{id}/enroll/` — recebe imagem, faz enroll (exige consentimento)
- [x] Endpoint `POST /api/biometrics/verify/` — recebe imagem + employee_id, retorna resultado
- [x] Endpoint `GET /api/employees/embeddings/` — retorna embeddings criptografados para cache do app

**Critério de aceite:** Enroll sem consentimento retorna 403. Verificação retorna `autenticado: true` para foto da pessoa cadastrada e `false` para outra com confiança > 95%.

---

### DEV-006 — App Attendance (Registro de Ponto)
**Referência:** PB-030, PB-031, PB-032, PB-033, PB-034  
**Estimativa:** 8h

Tarefas:
- [x] Model `AttendanceRecord`:
  ```
  tenant FK, employee FK, tipo (E/S/II/FI),
  timestamp (DateTimeField com timezone),
  nsr (BigInt, único por tenant — imutável),
  latitude, longitude (nullable),
  foto_path (path no MinIO),
  foto_hash (SHA-256),
  confianca_biometrica (Float),
  origem (online/offline),
  sincronizado_em (nullable — para registros offline),
  justificativa (nullable — para ajustes),
  registro_original FK (self, nullable — para ajustes)
  ```
- [x] `save()` override que impede edição após criação (raise exception)
- [x] `AttendanceService.registrar(employee, tipo, imagem, timestamp, origem)`:
  - Verifica biometria
  - Gera NSR atômico
  - Salva foto no MinIO
  - Calcula hash SHA-256 da foto
  - Cria registro imutável
  - Retorna comprovante
- [x] Endpoint `POST /api/attendance/register/` — chamado pelo app (online)
- [x] Endpoint `POST /api/attendance/sync/` — recebe lote de registros offline para sincronização
- [x] Validação de ordem de batidas (não pode ter 2 entradas seguidas, etc.)

**Critério de aceite:** Registro criado nunca pode ser editado via API ou admin. NSR é gerado no servidor.

---

### DEV-007 — Comprovante Eletrônico
**Referência:** PB-033, PB-034, PB-035  
**Estimativa:** 4h

Tarefas:
- [x] Model `Comprovante`: `registro FK`, `conteudo_json`, `timestamp_carimbo`, `hash_carimbo`
- [x] `ComprovanteService.gerar(registro) -> dict`:
  - Monta JSON com dados mínimos da Portaria 671
  - Aplica carimbo de tempo MVP com `timestamp_carimbo` + `hash_carimbo` (TSA RFC 3161 fica como evolução)
  - Salva e retorna
- [x] Endpoint `GET /api/attendance/{id}/comprovante/` — retorna comprovante em JSON

**Critério de aceite:** Comprovante gerado imediatamente após registro com todos os campos obrigatórios.

---

## AJUSTE PRIORITÁRIO — ONBOARDING DE CONTA (ANTES DO MOBILE)

### DEV-008 — Conta Proprietária + Empresa Única (CNPJ/CPF) + Tenant Isolado
**Referência:** PB-006, PB-100  
**Estimativa:** 16h

**Status atual (2026-03-08):**
- ✅ Entregue bloco P0 web/auth:
  - landing pública (`/`)
  - cadastro (`/cadastro/`)
  - login (`/login/`)
  - logout (`POST /logout/`)
  - guarda de acesso de `/painel/` para autenticados
- ✅ Evolução de `accounts.User` para suportar dados básicos no signup web: `first_name`, `last_name`, `phone`
- ⏳ Pendente: completar onboarding da empresa (PJ/PF), CPF obrigatório do owner e vínculo 1:1 owner/tenant

**Cronograma sugerido (2 dias úteis):**
- **Dia 1 (Backend + Modelagem):** novas entidades/constraints, migrations e serviços transacionais de onboarding.
- **Dia 2 (Frontend Web + Integração + Testes):** telas de cadastro/login/logout/painel inicial e testes ponta a ponta do fluxo.

**Detalhamento funcional e modelagem:** `docs/DEV_008_ONBOARDING_MODELAGEM.md`
**Especificação 1:1 da tela de jornada:** `docs/DEV_008_TELA_NOVA_JORNADA.md`
**Especificação da área de colaboradores:** `docs/DEV_008_AREA_COLABORADORES.md`
**Especificação da área de relógios de ponto:** `docs/DEV_008_AREA_RELOGIOS_PONTO.md`
**Especificação da área de tratamento/espelho de ponto:** `docs/DEV_008_TRATAMENTO_PONTO.md`
**Especificação da área de relatórios:** `docs/DEV_008_AREA_RELATORIOS.md`
**Especificação da área de solicitações:** `docs/DEV_008_AREA_SOLICITACOES.md`

Objetivo:
- Garantir a regra de negócio do produto: **1 usuário dono da conta** possui **exatamente 1 empresa (CNPJ ou CPF)**; essa empresa define **1 tenant** e todo o domínio operacional (`funcionários`, `turnos`, `ponto`, `relatórios`) permanece isolado nesse tenant.

Tarefas — Modelagem:
- [ ] Evoluir model de conta proprietária (`accounts.User`) com campos de cadastro: `first_name`, `last_name`, `email` (login), `cpf`, `phone`, `is_account_owner`.
- [ ] Definir regras de unicidade global da conta proprietária:
  - `email` único em toda a aplicação (login)
  - `cpf` único em toda a aplicação para usuário dono da conta
  - `cpf` obrigatório no onboarding do dono da conta.
- [ ] Evoluir model de empresa (`tenants.Tenant`) para suportar **PJ/PF**:
  - `tipo_pessoa` (`PJ`/`PF`)
  - `documento` único (normalizado, sem máscara)
  - manter compatibilidade com campos atuais de empresa.
- [ ] Adicionar constraints de negócio:
  - `1 owner -> 1 tenant` (FK única por owner)
  - `1 tenant -> 1 owner` (unique condicional para usuário owner)
  - documento (`CNPJ`/`CPF`) único no cadastro de empresa.
- [ ] Modelar dados complementares da empresa alinhados às telas:
  - contato (`email`, `telefone`)
  - endereço (`cep`, `logradouro`, `numero`, `complemento`, `bairro`, `cidade`, `estado`)
  - responsável legal (`nome`, `cpf`, `cargo`)
  - opcionais (`logo_url`, `website`, `cno_caepf`, `inscricao_estadual`, `inscricao_municipal`).
- [ ] Modelar estado mínimo de onboarding por tenant para controlar stepper e liberação de menu:
  - `onboarding_step`
  - `onboarding_completed_at`.

Tarefas — Backend:
- [ ] Criar serviço transacional `AccountOnboardingService` para criar `User owner + Tenant + vínculo` em uma única operação atômica.
- [ ] Criar endpoints públicos do fluxo web:
  - `POST /api/public/signup/` (cadastro conta + empresa PJ/PF)
  - `POST /api/public/login/`
  - `POST /api/public/logout/`
- [ ] Criar endpoint de consulta automática de CNPJ para o botão **Buscar CNPJ** (com validação de formato, timeout e tratamento de indisponibilidade do provedor externo), com decisão de integração:
  - provider primário: **CNPJá Open**
  - fallback: preenchimento manual no formulário
  - evolução planejada (Fase 2): provider oficial **Serpro** opcional.
- [ ] Criar endpoint de consulta automática de endereço por CEP via **API ViaCEP** (normalização de CEP, validação de retorno e fallback para preenchimento manual).
- [ ] Impedir criação de segunda empresa para a mesma conta proprietária (retornar 409/400 com mensagem clara).
- [ ] Garantir tenant context para todas as operações subsequentes da conta criada.
- [ ] Ajustar serializers/validators para CPF/CNPJ, telefone e campos obrigatórios por tipo de pessoa.
- [ ] Validar conflito de unicidade de `email` e `cpf` no signup com erro semântico (HTTP 409 ou 400 padronizado).

Tarefas — Frontend Web (Django Templates):
- [ ] Landing page pública com CTA para cadastro/login.
- [ ] Tela de cadastro de conta com os campos:
  - `nome`
  - `sobrenome`
  - `e-mail` (login)
  - `cpf` (obrigatório)
  - `telefone`
  - `senha`
  - `confirmar senha`.
- [ ] Wizard de cadastro da empresa (PJ/PF) com os blocos:
  - dados da empresa/empregador
  - endereço
  - representante
  - dados adicionais.
- [ ] Implementar ação **Buscar CNPJ** no formulário da empresa para autopreenchimento dos campos compatíveis (ex.: razão social e nome fantasia), mantendo edição manual disponível.
- [ ] Implementar busca automática de endereço por CEP no formulário (ViaCEP), preenchendo logradouro/bairro/cidade/estado, com possibilidade de ajuste manual.
- [ ] Tela de login e ação de logout.
- [ ] Página inicial do painel (`/painel`) após autenticação com resumo básico do tenant.
- [ ] Implementar layout base do painel no padrão definido para onboarding:
  - sidebar fixa à esquerda com estados ativo/inativo/bloqueado
  - topbar com seletor de empresa no centro e ações no canto direito
  - cabeçalho de boas-vindas com stepper de progresso
  - área de conteúdo limpa para cards/listagens.
- [ ] Implementar banner/CTA de onboarding para **Criar primeira empresa** quando tenant ainda não existir.
- [ ] Após cadastro da empresa, exibir card de pendências no `/painel` com etapa **Criar horário da equipe**.
- [ ] Exibir modal contextual com CTA **Criar jornada** e navegar para formulário de `Nova Jornada de Trabalho`.
- [ ] Implementar tela `Nova Jornada de Trabalho` conforme especificação 1:1:
  - estrutura visual do layout aprovado
  - estados de cards e botões
  - estado expandido por tipo (`Semanal`, `12x36`, `Fracionada`, `Externa`) conforme referência visual
  - validações de formulário
  - semântica negocial por tipo de jornada (efeito no cálculo/validação de ponto)
  - catálogo de mensagens de erro/sucesso.
- [ ] Implementar liberação progressiva do menu lateral por estado de onboarding:
  - sem empresa: somente `Início` e `Empresa` ativos
  - com empresa e sem jornada: liberar `Jornadas de Trabalho`
  - após primeira jornada: liberar demais módulos do menu.
- [ ] Implementar módulo `Colaboradores` conforme especificação dedicada:
  - listagem com filtros, abas de status e estado vazio
  - estado pós-cadastro com linha em `Ativos`, badge de face pendente e paginação atualizada
  - ação `Novo Colaborador`
  - formulário em seções (`Dados Básicos`, `Informações de Trabalho`, `Jornada de Trabalho`, `Reconhecimento Facial`)
  - estado de jornada no cadastro: template selecionado ativa card/tipo correspondente e expande bloco explicativo
  - modal de captura facial com consentimento explícito antes de confirmar
  - alternativa de envio de link de auto-cadastro facial por WhatsApp com modal de confirmação de envio
  - ações rápidas na linha da listagem (reenviar link, editar, alterar status)
  - regras de domínio de CPF/PIS, vínculo de jornada e fluxo de biometria.
- [ ] Implementar módulo `Relógios de Ponto` conforme especificação dedicada:
  - listagem inicial com banner, filtros e estado vazio
  - formulário `Criar Relógio` com método de autenticação fixo (`Reconhecimento Facial`)
  - validações de nome único por tenant e método fixo `FACIAL`
  - card pós-criação com status, tipo REP e código de ativação
  - suporte aos status operacionais do relógio: `Ativo`, `Inativo`, `Em Manutenção`
  - ações `Gerenciar` e `Inativar Relógio`
  - tela de detalhe (`/painel/relogios/{id}/`) com aba `Informações` padrão e card de `Cerca Virtual`
  - aba `Colaboradores` com dupla listagem (`Disponíveis` x `No Relógio`) e ações em lote para mover/remover colaboradores.
  - contrato API para `Editar Relógio` (`PATCH /api/relogios/{id}/`) com validações semânticas
  - contrato API de ativação do relógio por código (`POST /api/relogios/ativar/`), com bloqueio para status `Inativo` e `Em Manutenção`
  - contrato API de cerca virtual (`PUT|PATCH|DELETE /api/relogios/{id}/cerca-virtual/`) com regra geográfica de validação de batida
  - contrato API da aba `Colaboradores` para mover/remover selecionados e mover/remover todos com contadores sincronizados no retorno
  - pré-condições de batida no dispositivo: relógio ativo + colaborador atribuído + colaborador ativo + biometria facial válida
- [ ] Implementar módulo `Tratamento de Ponto` conforme especificação dedicada:
  - listagem mensal por colaborador com filtros (`período`, busca, inconsistências, pendências)
  - ação `Ver Espelho` para abrir espelho individual por período
  - tela `Espelho de Ponto` com cards de indicadores, legenda de status de marcações e tabela diária
  - ação `Editar` por dia e `Ajuste Automático` com trilha auditável
  - contrato API para listagem/resumo e ajustes por dia no período aberto
- [ ] Implementar módulo `Relatórios` conforme especificação dedicada:
  - tela índice com cards (`Espelho de Ponto`, `Cartão de Ponto`, `Detalhes dos Cálculos`)
  - formulários com período, colaborador e geração/exportação de PDF
  - `Detalhes dos Cálculos` com modos `Por Dia` e `Consolidado`
  - contrato API de geração e download de relatórios
- [ ] Implementar módulo `Solicitações` conforme especificação dedicada:
  - tela índice com cards `Solicitações de Ajuste` e `Solicitações de Acesso`
  - contadores de pendências e navegação `Acessar`
  - telas internas de `Acessar` (ajustes e acessos) com filtros, tabela detalhada e ação `Visualizar`
  - fluxo de decisão (aprovar/rejeitar) com trilha auditável
  - contrato API de resumo, listagem, detalhe e decisão por tipo

Tarefas — Qualidade, Segurança e Documentação:
- [ ] Testes unitários de validação de CPF/CNPJ e regras 1:1 owner/tenant.
- [ ] Testes de integração do fluxo completo: cadastro -> login -> painel -> logout.
- [ ] Testes de autorização garantindo isolamento por tenant.
- [ ] Testes de integração dos conectores externos:
  - consulta de CNPJ com sucesso/erro/timeout
  - consulta de CEP via ViaCEP com sucesso/CEP inválido/serviço indisponível.
- [ ] Atualizar documentação de API e README com o novo fluxo de onboarding, incluindo:
  - decisão de provider de CNPJ (CNPJá Open no MVP)
  - fallback manual
  - roadmap para Serpro opcional na Fase 2.

**Entregáveis:**
- Migrations versionadas de `accounts` e `tenants`.
- Endpoints públicos de onboarding/login/logout.
- Templates web de landing, cadastro, login e painel inicial.
- Suíte de testes do fluxo de onboarding 1:1.
- Documentação funcional e técnica atualizada.

**Critério de aceite:**
- Conta proprietária consegue se cadastrar com empresa **PJ ou PF** em fluxo único.
- `email` (login) e `cpf` do dono da conta são únicos em toda a aplicação.
- Botão **Buscar CNPJ** preenche automaticamente os dados disponíveis da empresa e permite edição manual antes de salvar.
- Campo CEP realiza consulta automática no **ViaCEP** e preenche endereço com fallback manual em caso de erro.
- Fluxo de CNPJ no MVP usa **CNPJá Open** como provider primário; indisponibilidade não bloqueia cadastro (fallback manual ativo).
- Sistema bloqueia segunda empresa para a mesma conta proprietária.
- Cada conta proprietária acessa somente dados do próprio tenant.
- Após login, usuário entra no painel inicial; logout encerra sessão/token.
- Funcionários, turnos, ponto e relatórios permanecem associados ao tenant da conta criada.
- `/painel` renderiza o esqueleto visual de onboarding no padrão acordado (sidebar + topbar + boas-vindas + stepper + pendências).
- Menu lateral respeita a liberação progressiva por tenant, sem vazamento de estado entre empresas.
- Fluxo `Criar jornada` abre a tela de nova jornada a partir do modal de pendência pós-cadastro da empresa.

## SEMANAS 3–4 — App Mobile

### DEV-010 — Setup do App Mobile
**Referência:** PB-020  
**Estimativa:** 6h

> ⚠️ **Atenção:** Este projeto usa bibliotecas nativas (MLKit) que **não funcionam no Expo Go**.
> O ambiente de desenvolvimento usa **Expo Dev Client** com **Prebuild** para gerar o projeto nativo Android.
> O build de produção (APK para o tablet) é gerado via **EAS Build**.

Tarefas:
- [ ] Criar projeto Expo com TypeScript: `npx create-expo-app ponto-app --template expo-template-typescript`
- [ ] Configurar `app.json` com `expo.android.package`, permissões de câmera e `plugins`
- [ ] Instalar dependências nativas: `expo-camera`, `react-native-mlkit-face-detection`, `expo-dev-client`
- [ ] Instalar dependências JS: `zustand`, `axios`, `@nozbe/watermelondb`, `@react-native-community/netinfo`
- [ ] Rodar `npx expo prebuild --platform android` para gerar a pasta `android/`
- [ ] Configurar `eas.json` com perfis: `development` (Dev Client), `preview` (APK interno), `production`
- [ ] Configurar Axios com interceptor de JWT refresh automático
- [ ] Tela de configuração inicial: inserir URL da API + código de ativação do dispositivo
- [ ] `AuthService.registerDevice(url, code)` — autentica o tablet e armazena JWT local
- [ ] Zustand store: `authStore`, `attendanceStore`, `employeeStore`

**Critério de aceite:** App compila com `npx expo run:android`, abre no tablet via Dev Client, configura a URL da API e autentica o dispositivo.

---

### DEV-011 — Sincronização de Funcionários e Embeddings
**Referência:** PB-027  
**Estimativa:** 6h

Tarefas:
- [ ] WatermelonDB schema: tabela `employees` (id, nome, pis, embedding_encrypted, updated_at)
- [ ] `SyncService.syncEmployees()`:
  - Busca lista de funcionários ativos da API
  - Busca embeddings criptografados da API
  - Persiste localmente no WatermelonDB
  - Roda na abertura do app e a cada 30 minutos
- [ ] Indicador de status de sincronização na UI

**Critério de aceite:** App exibe funcionários mesmo sem internet após primeira sincronização.

---

### DEV-012 — Tela de Ponto e Reconhecimento Facial
**Referência:** PB-021, PB-022, PB-023, PB-024  
**Estimativa:** 10h

Tarefas:
- [ ] Tela principal: câmera em fullscreen com overlay de detecção de rosto
- [ ] `FaceDetectionService.detectar(frame)`:
  - **Online:** envia frame para `POST /api/biometrics/verify/` e aguarda resultado
  - **Offline:** usa MLKit para extrair embedding local e compara com embeddings cacheados
- [ ] Lógica de fallback: detectar conexão com `NetInfo`, escolher modo automaticamente
- [ ] Componente `ResultadoModal`: exibe aprovado/negado com nome e foto por 3 segundos
- [ ] Componente `ComprovanteModal`: exibe comprovante após registro aprovado
- [ ] Botão de registro manual com justificativa (fallback biométrico)
- [ ] Animações de feedback visual (verde = aprovado, vermelho = negado)

**Critério de aceite:** Funcionário aponta rosto para câmera e em até 5 segundos o ponto é registrado.

---

### DEV-013 — Modo Offline e Sincronização
**Referência:** PB-025, PB-026  
**Estimativa:** 8h

Tarefas:
- [ ] WatermelonDB schema: tabela `pending_records` (employee_id, tipo, timestamp, foto_base64, confiança, sincronizado)
- [ ] `OfflineAttendanceService.salvar(registro)` — persiste registro pendente localmente
- [ ] `SyncService.syncPendingRecords()`:
  - Detecta conexão restaurada via NetInfo listener
  - Busca registros não sincronizados ordenados por timestamp
  - Envia para `POST /api/attendance/sync/` em lotes de 10
  - Marca como sincronizado ao receber confirmação com NSR
  - Exibe notificação de registros sincronizados
- [ ] Indicador visual no app: modo offline (ícone vermelho) / online (ícone verde)

**Critério de aceite:** Registros feitos offline aparecem corretamente no painel web após sincronização com NSR sequencial correto.

---

## SEMANAS 5–6 — Painel Web e Engine Legal

### DEV-020 — Painel Web Admin (Django Templates)
**Referência:** PB-040, PB-041, PB-042, PB-043  
**Estimativa:** 12h

**Stack do painel:**
- **Tailwind CSS** via CDN Play — zero build step, classes utilitárias diretamente nos templates
- **HTMX** via CDN — requisições assíncronas sem escrever JS (filtros, paginação, dashboard refresh)
- **Alpine.js** via CDN — estado local de componentes (modais, webcam, toggles)

Tarefas:
- [ ] Instalar bibliotecas via CDN no `base.html` (Tailwind Play CDN, HTMX, Alpine.js)
- [ ] Base template com sidebar de navegação (Tailwind + Alpine.js para mobile toggle)
- [ ] Dashboard: cards com totais do dia (presentes, ausentes, em intervalo) com `hx-trigger="every 30s"` (HTMX)
- [ ] Listagem de registros do dia com filtros sem reload (`hx-get` no form de filtros)
- [ ] Espelho de ponto: tabela por funcionário com todos os registros do período
- [ ] Página de cadastro de funcionários com enroll biométrico (webcam via Alpine.js + captura + POST para API)
- [ ] Página de configuração de jornada padrão da empresa
- [ ] Página de gestão de dispositivos (tablets cadastrados)
- [ ] Página de geração de AFD/AEJ com seletor de período + botão de download

**Critério de aceite:** Admin consegue visualizar ponto do dia e gerar AFD sem tocar no terminal. Dashboard atualiza sem reload de página.

---

### DEV-021 — Engine AFD (Arquivo Fonte de Dados)
**Referência:** PB-050, PB-052, PB-053, PB-054  
**Estimativa:** 8h

Tarefas:
- [ ] `AFDGenerator.gerar(tenant, data_inicio, data_fim) -> str`:
  - **Tipo 2 (Header):** CNPJ, razão social, CNPJ do software (INPI), período — 294 chars
  - **Tipo 3 (Registro):** NSR, data, hora, PIS, tipo de marcação — 94 chars por linha
  - **Tipo 9 (Trailer):** quantidade de registros, NSR inicial e final — 94 chars
  - CRLF obrigatório entre linhas
  - Encoding: ISO-8859-1 conforme portaria
- [ ] `AFDValidator.validar(conteudo) -> list[str]`:
  - Valida tamanho de cada linha
  - Valida sequência de NSR
  - Valida formato de datas e PIS
  - Retorna lista de erros (vazia = válido)
- [ ] Celery task `gerar_afd_task(tenant_id, data_inicio, data_fim)` — assíncrona para arquivos grandes
- [ ] Endpoint `POST /api/legal/afd/generate/` — dispara task e retorna task_id
- [ ] Endpoint `GET /api/legal/afd/status/{task_id}/` — retorna status + URL de download

**Critério de aceite:** AFD gerado passa no validador interno sem erros e tem o layout correto da Portaria 671.

---

### DEV-022 — Engine AEJ (Arquivo Eletrônico de Jornada)
**Referência:** PB-051  
**Estimativa:** 6h

Tarefas:
- [ ] `AEJGenerator.gerar(tenant, data_inicio, data_fim) -> str`:
  - **Tipo 1 (Header):** dados do empregador e período
  - **Tipo 2 (Empregado):** PIS, nome, cargo, CBO — por funcionário
  - **Tipo 3 (Marcações):** data, pares de entrada/saída calculados
  - **Tipo 9 (Trailer):** totais
- [ ] `AEJValidator.validar(conteudo) -> list[str]`
- [ ] Integração com endpoint de download no painel web

**Critério de aceite:** AEJ gerado tem layout conforme Anexo II da Portaria 671.

---

### DEV-023 — Celery Tasks e Agendamentos
**Referência:** Suporte geral  
**Estimativa:** 4h

Tarefas:
- [ ] Configuração do Celery com Redis como broker
- [ ] Celery Beat schedule:
  - `fechar_jornada_diaria` — roda às 23:59 todos os dias
  - `limpar_fotos_expiradas` — roda semanalmente (política de retenção LGPD)
  - `sincronizar_status_dispositivos` — roda a cada hora
- [ ] Task `enviar_comprovantes_pendentes` — reenvio de comprovantes com falha
- [ ] Flower para monitoramento de tasks (ambiente de desenvolvimento)

---

## SEMANAS 7–8 — Integração, Testes e Deploy MVP

### DEV-030 — Testes Automatizados
**Estimativa:** 8h

Tarefas:
- [ ] Testes unitários: `BiometriaService`, `AFDGenerator`, `AEJGenerator`, `NSR sequence`
- [ ] Testes de integração: fluxo completo de registro de ponto (online e offline)
- [ ] Teste de multitenancy: garantir isolamento de dados entre tenants
- [ ] Teste de inviolabilidade: tentar editar registro via API deve retornar 403
- [ ] Teste de concorrência: geração de NSR com 10 requests simultâneos deve ser sequencial
- [ ] Coverage mínimo: 70% no core

**Critério de aceite:** `pytest` passa sem falhas, coverage ≥ 70%.

---

### DEV-031 — Segurança Complementar
**Referência:** PB-110  
**Estimativa:** 2h

> ℹ️ O Model `ConsentimentoBiometrico` e o fluxo de consentimento LGPD foram movidos para o **DEV-005** como pré-requisito obrigatório do enroll. Este item cobre apenas as configurações de segurança de infraestrutura.

Tarefas:
- [ ] Rate limiting na API de verificação biométrica (max 10 req/min por device)
- [ ] CORS configurado apenas para origens permitidas
- [ ] Verificar que todos os endpoints com dados biométricos retornam 403 sem consentimento ativo

---

### DEV-032 — CI/CD e Deploy (EasyPanel + Traefik)
**Estimativa:** 6h

**Arquitetura de ambientes:**
- **DEV local:** `docker-compose.yml` na máquina do desenvolvedor espelhando o ambiente PROD
- **PROD (VPS):** EasyPanel conecta ao repositório GitHub e usa o `Dockerfile` diretamente — **sem `docker-compose.prod.yml`**
- **Push na `main` = deploy automático em PROD** via webhook do EasyPanel

Tarefas:
- [ ] `Dockerfile` multi-stage para o backend Django (dev + prod em uma imagem)
- [ ] `Dockerfile` separado (ou mesmo com `CMD` diferente) para o Celery worker
- [ ] `docker-compose.yml` local (DEV): serviços `web`, `db`, `redis`, `celery`, `minio` + volumes
- [ ] Configurar cada serviço no EasyPanel apontando para o repositório GitHub + `Dockerfile`
- [ ] Configurar variáveis de ambiente no EasyPanel por serviço (`.env` de PROD — **não commitar**)
- [ ] GitHub Actions workflow `on push main`:
  - Roda `ruff check .` + `pytest`
  - Notifica EasyPanel via webhook para redeploy
- [ ] Garantir que migrations rodam automáticas no `entrypoint.sh` antes do Gunicorn
- [ ] `collectstatic` no build da imagem (não em runtime)
- [ ] Build do app Expo para APK de desenvolvimento (EAS Build preview)

> **EasyPanel usa o Dockerfile diretamente do GitHub.** Não usar `docker-compose.prod.yml` em PROD. Cada serviço (web, celery) é configurado individualmente no EasyPanel apontando para o mesmo repositório. O Traefik gerencia SSL e roteamento automaticamente — sem Nginx.

**Critério de aceite:** Push na `main` dispara CI verde, EasyPanel faz redeploy automático. APK instalado no tablet conecta na API de produção via HTTPS.

---

### DEV-033 — Validação com Empresa de Testes
**Estimativa:** 4h (operacional)

Tarefas:
- [ ] Cadastrar empresa de teste como tenant
- [ ] Cadastrar 5 funcionários com enroll biométrico
- [ ] Instalar APK no tablet e configurar
- [ ] Testar ciclo completo: entrada, saída, intervalo
- [ ] Testar modo offline: desligar WiFi, bater ponto, religar, verificar sync
- [ ] Gerar AFD do período e validar
- [ ] Documentar bugs encontrados e abrir issues

---

## Dependências Críticas entre Tarefas

```
DEV-001 → DEV-002 → DEV-003 → DEV-004 → DEV-005 → DEV-006 → DEV-007
                      ↓
                   DEV-008 → DEV-020

DEV-003 → DEV-010 → DEV-011 → DEV-012 → DEV-013
                         ↑
                    DEV-005 (embeddings)

DEV-006 → DEV-021 (AFD precisa dos registros)
DEV-006 → DEV-022 (AEJ precisa dos registros)
DEV-020 precisa de DEV-006 e DEV-021
```

---

## Glossário Técnico para a IA

| Termo | Definição |
|---|---|
| REP-P | Registrador Eletrônico de Ponto — Programa. Sistema 100% digital sem hardware proprietário |
| AFD | Arquivo Fonte de Dados. Arquivo texto com todos os registros brutos de ponto. Layout na Portaria 671 Anexo I |
| AEJ | Arquivo Eletrônico de Jornada. Arquivo com a jornada calculada por funcionário. Layout na Portaria 671 Anexo II |
| NSR | Número Sequencial de Registro. Identificador único e sequencial de cada batida de ponto. Nunca pode ser reutilizado ou ter gap |
| PIS | Programa de Integração Social. Número de 11 dígitos do trabalhador brasileiro. Obrigatório no AFD |
| Tenant | Empresa contratante do SaaS. Cada tenant tem dados completamente isolados |
| Embedding | Vetor numérico que representa um rosto humano. Gerado por **DeepFace** (modelo ArcFace). Armazenado criptografado. |
| Enroll | Processo de cadastro biométrico: capturar foto, gerar embedding via ArcFace e armazenar criptografado |
| Threshold | Distância cosine máxima entre embeddings para reconhecimento válido. Padrão ArcFace: **0.68** |
| Comprovante | Documento eletrônico emitido ao trabalhador após cada batida. Exigido pela Portaria 671 |
| RFC 3161 | Protocolo de carimbo de tempo criptográfico que garante quando um documento foi criado |
