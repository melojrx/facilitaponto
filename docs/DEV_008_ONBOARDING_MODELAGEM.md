# DEV-008 — Onboarding e Modelagem do Painel
**Versão:** 1.9  
**Data:** 2026-03-11  
**Referências:** PB-006, PB-100, `docs/PRD.md`, `docs/PRODUCT_BACKLOG.md`, `docs/DEV_ROADMAP.md`
**Anexos de UI:**
- `docs/DEV_008_TELA_NOVA_JORNADA.md` (especificação 1:1 da tela de cadastro de jornada)
- `docs/DEV_008_AREA_COLABORADORES.md` (especificação da listagem e do fluxo de novo colaborador)
- `docs/DEV_008_AREA_RELOGIOS_PONTO.md` (especificação da listagem e criação de relógios de ponto)
- `docs/DEV_008_TRATAMENTO_PONTO.md` (especificação da listagem de tratamento e espelho de ponto)
- `docs/DEV_008_AREA_RELATORIOS.md` (especificação da área de relatórios e geração de PDF)
- `docs/DEV_008_AREA_SOLICITACOES.md` (especificação da área de solicitações e decisões)

---

## Papel deste documento

- Este arquivo é o índice técnico/funcional do `DEV-008`.
- Ele descreve a arquitetura do onboarding, a liberação progressiva do painel e a dependência entre módulos.
- O acompanhamento de execução, aceite e corte de escopo fica em `docs/DEV_008_CHECKLIST.md`.
- As regras detalhadas de interface/módulo vivem nos anexos específicos (`jornada`, `colaboradores`, `relógios`, `tratamento`, `relatórios`, `solicitações`).

## Snapshot de implementação (2026-03-13)

- `DEV-008` está encerrado para aceite funcional no onboarding.
- `Colaboradores` está entregue no núcleo funcional do painel web.
- `Relógios de Ponto` está entregue no núcleo funcional do painel web/API.
- O fluxo biométrico operacional já cobre:
  - captura facial assistida no painel
  - webcam no painel como canal principal
  - upload de imagem como fallback operacional
  - envio de convite remoto por WhatsApp com link seguro, expirável e de uso único
- O próximo bloco operacional segue a ordem oficial:
  - `1. Tratamento de Ponto`
  - `2. Relatórios`
  - `3. Solicitações`
- A fonte oficial desta ordem e do status detalhado permanece em `docs/DEV_008_CHECKLIST.md`.

## 1. Objetivo do DEV-008

Formalizar o fluxo de onboarding web e a modelagem funcional/técnica para a regra de negócio:

- **1 conta proprietária (owner)**
- **1 empresa única (CNPJ ou CPF)**
- **1 tenant isolado**

Com isso, o `/painel` passa a guiar o cliente pelos primeiros cadastros obrigatórios e libera os módulos de forma progressiva.

---

## 2. Premissas obrigatórias herdadas da documentação

### Produto e negócio
- Onboarding é **self-service** via painel web.
- Público-alvo é PME com baixa maturidade técnica; UX deve ser simples e autoexplicativa.
- Decisões devem evitar over-engineering (princípio explícito no PRD).

### Arquitetura
- Stack do painel: **Django Templates + Tailwind CDN + HTMX + Alpine.js**.
- Multitenancy com isolamento por `tenant_id` (row-level).
- Contexto de tenant obrigatório para operações de domínio.

### Regras de domínio
- `email` (login) único global para conta proprietária.
- `cpf` do owner único global e obrigatório no onboarding.
- Empresa pode ser **PJ (CNPJ)** ou **PF (CPF)** com documento normalizado.
- Não pode existir segunda empresa para o mesmo owner.
- Fluxo de CNPJ no MVP:
  - provider primário: **CNPJá Open**
  - fallback manual obrigatório
  - evolução futura: **Serpro** opcional
- Busca de CEP no MVP via **ViaCEP**, com fallback manual.

---

## 3. Fluxo funcional do onboarding (painel)

### Etapa 0 — Conta criada, empresa pendente
- Usuário owner autenticado e sem empresa vinculada.
- `/painel` exibe banner de onboarding: **"Crie sua primeira empresa"**.
- CTA leva para formulário completo de empresa.

### Etapa 1 — Cadastro da empresa (obrigatório)
- Ação `Criar empresa` abre formulário completo de empresa (PJ/PF).
- Para PJ, habilitar ação **Buscar CNPJ** com autopreenchimento.
- Endereço com busca de CEP (ViaCEP) e edição manual.
- Ao salvar com sucesso:
  - cria tenant
  - vincula owner ao tenant (1:1)
  - registra progresso de onboarding

### Etapa 2 — Primeira tela após empresa cadastrada
- Dashboard segue o padrão visual acordado:
  - sidebar fixa à esquerda
  - topbar com seletor de empresa centralizado e ações à direita
  - cabeçalho de boas-vindas com stepper
  - card de pendências
- Exibir pendência principal: **"Criar horário da equipe"**.
- Abrir modal contextual no primeiro acesso com CTA **"Criar jornada"**.

### Etapa 3 — Cadastro da primeira jornada
- CTA **Criar jornada** abre `Nova Jornada de Trabalho`.
- Tela contém:
  - nome da jornada
  - descrição
  - seleção do tipo de jornada (ex.: semanal, 12x36, fracionada, externa)
- Especificação visual/funcional detalhada (cards, estados, validações e mensagens):
  - `docs/DEV_008_TELA_NOVA_JORNADA.md`
- Semântica negocial por tipo de jornada:
  - `Semanal`, `12x36`, `Fracionada`, `Externa` (com impactos de cálculo/validação)
- Ao salvar a primeira jornada, avançar onboarding e liberar próximos módulos.

### Etapa 4 — Primeiros colaboradores (módulo liberado)
- Módulo `Colaboradores` fica disponível após a primeira jornada.
- Tela de listagem e fluxo de criação de colaborador seguem especificação dedicada:
  - `docs/DEV_008_AREA_COLABORADORES.md`
- Cadastro de colaborador conecta as dimensões:
  - dados pessoais e laborais
  - vínculo de jornada
  - biometria (captura imediata via modal com consentimento ou convite posterior via link WhatsApp seguro).

### Etapa 5 — Relógios de Ponto (módulo operacional)
- Módulo `Relógio Digital` habilita criação e gestão dos relógios de ponto da empresa.
- Fluxos principais:
  - listagem inicial com filtros e estado vazio
  - criação de relógio com métodos de autenticação
  - visualização de card com status, tipo REP e código de ativação.
- Especificação dedicada:
  - `docs/DEV_008_AREA_RELOGIOS_PONTO.md`

### Etapa 6 — Tratamento de Ponto e Espelho (auditoria operacional)
- Módulo `Tratamento de Ponto` disponível após jornada inicial concluída e colaboradores operacionais.
- Fluxos principais:
  - listagem mensal por colaborador com filtros de inconsistência/pendência
  - navegação para `Ver Espelho`
  - leitura de indicadores e ocorrências por dia
  - ações de ajuste (`Editar`) e `Ajuste Automático`.
- Especificação dedicada:
  - `docs/DEV_008_TRATAMENTO_PONTO.md`

### Etapa 7 — Relatórios (consulta e exportação)
- Módulo `Relatórios` disponibiliza os três tipos:
  - `Espelho de Ponto`
  - `Cartão de Ponto`
  - `Detalhes dos Cálculos`
- Cada tipo possui filtro por período e colaborador e exportação em PDF.
- Especificação dedicada:
  - `docs/DEV_008_AREA_RELATORIOS.md`

### Etapa 8 — Solicitações (governança operacional)
- Módulo `Solicitações` inicia com visão resumida por tipo:
  - `Solicitações de Ajuste`
  - `Solicitações de Acesso`
- Cada card exibe pendências e entrada para lista detalhada (`Acessar`) com filtros, tabela e decisão.
- Especificação dedicada:
  - `docs/DEV_008_AREA_SOLICITACOES.md`

---

## 4. Estrutura visual base do `/painel`

Elementos obrigatórios para o layout inicial:

- Sidebar fixa à esquerda com estados ativo/inativo/bloqueado.
- Topbar com:
  - seletor de empresa no centro
  - ações no canto direito.
- Banner de onboarding com CTA quando aplicável.
- Cabeçalho de boas-vindas com stepper de progresso.
- Área de conteúdo limpa para cards/listagens das próximas telas.
- Comportamento responsivo para desktop e mobile (sidebar colapsável no mobile).

---

## 5. Menu e liberação progressiva de módulos

Menu alvo:

1. Início
2. Empresa
3. Jornadas de Trabalho
4. Colaboradores
5. Relógio Digital
6. Tratamento de Ponto
7. Relatórios
8. Solicitações
9. Configurações

### Matriz de liberação (MVP DEV-008)

| Estado de onboarding | Início | Empresa | Jornadas | Colaboradores | Relógio Digital | Tratamento de Ponto | Relatórios | Solicitações | Configurações |
|---|---|---|---|---|---|---|---|---|---|
| Sem empresa cadastrada | ✅ | ✅ | 🔒 | 🔒 | 🔒 | 🔒 | 🔒 | 🔒 | 🔒 |
| Empresa cadastrada, sem jornada | ✅ | ✅ | ✅ | 🔒 | 🔒 | 🔒 | 🔒 | 🔒 | 🔒 |
| Primeira jornada cadastrada | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

Regras:
- Item bloqueado aparece no menu, mas não navega.
- Tooltip/mensagem explica pré-requisito quando item bloqueado é clicado.
- Estado de liberação é calculado por tenant e aplicado em cada request do painel.

---

## 6. Modelagem de dados para o onboarding

### 6.1 Evolução de `accounts.User` (owner)
- Campos de cadastro:
  - `first_name`
  - `last_name`
  - `email` (único global)
  - `cpf` (único global para owner)
  - `phone`
  - `is_account_owner` (bool)
- Regra: owner obrigatoriamente vinculado a no máximo 1 tenant.

### 6.2 Evolução de `tenants.Tenant` (empresa)
- Suporte PJ/PF:
  - `tipo_pessoa` (`PJ`/`PF`)
  - `documento` único (normalizado sem máscara)
- Compatibilidade:
  - manter campos atuais (`cnpj`, `razao_social`, etc.) até migração completa.
- Complementares:
  - contato, endereço, responsável legal e dados adicionais já previstos no roadmap.

### 6.3 Estado de onboarding no tenant

Para controlar stepper, pendências e bloqueio de menu, registrar estado mínimo no tenant:

- `onboarding_step` (inteiro positivo)
- `onboarding_completed_at` (datetime, nullable)

Transições:

1. `onboarding_step = 1`: empresa pendente
2. `onboarding_step = 2`: empresa cadastrada, jornada pendente
3. `onboarding_step = 3`: primeira jornada cadastrada (onboarding operacional concluído)

Observação: manter modelagem simples (sem motor de workflow); transições disparadas por serviços de domínio.

---

## 7. Contratos e serviços (DEV-008)

### Serviços
- `AccountOnboardingService`:
  - cria owner + tenant + vínculo em transação atômica
  - impede segunda empresa por owner.
- `OnboardingProgressService`:
  - calcula e atualiza progresso por tenant
  - expõe estado para templates (stepper, bloqueios, CTA).

### Endpoints públicos já previstos no roadmap
- `POST /api/public/signup/`
- `POST /api/public/login/`
- `POST /api/public/logout/`
- Endpoint para consulta CNPJ (CNPJá Open, com fallback manual)
- Endpoint para consulta CEP (ViaCEP, com fallback manual)

### Rotas web do painel (MVP)
- `GET /painel/`
- `GET|POST /painel/empresa/nova/`
- `GET /painel/jornadas/`
- `GET|POST /painel/jornadas/nova/`
- `GET|POST /painel/jornadas/{id}/editar/`
- `POST /painel/jornadas/{id}/excluir/`

### Status de implementação (snapshot real em 2026-03-13)

Entregue no núcleo funcional:
- Landing pública em `GET /` e autenticação web com sessões:
  - `GET|POST /cadastro/`
  - `GET|POST /login/`
  - `POST /logout/`
- Cadastro de conta com `first_name`, `last_name`, `email`, `cpf`, `phone`, senha e validações.
- Onboarding de empresa em `GET|POST /painel/empresa/nova/` com:
  - suporte PJ/PF e documento normalizado
  - vínculo owner -> tenant
  - bloqueio de segunda empresa no fluxo web.
- Endurecimento da regra no backend:
  - lock pessimista no owner durante criação/edição de empresa (`select_for_update`)
  - constraint de banco para garantir no máximo 1 owner por tenant.
- `AccountOnboardingService` implementado para encapsular transação de criação de owner e vínculo/atualização de empresa no onboarding.
- Painel com liberação progressiva por `onboarding_step` e CTA para jornada.
- Tela de jornada em `GET|POST /painel/jornadas/nova/` com tipos (`Semanal`, `12x36`, `Fracionada`, `Externa`) e avanço para `onboarding_step >= 3`.
- Listagem de jornadas em `GET /painel/jornadas/` com busca, filtro por status e ações de CRUD.
- Edição de jornada em `GET|POST /painel/jornadas/{id}/editar/`, reaproveitando as mesmas validações semânticas por tipo.
- Exclusão segura de jornada em `POST /painel/jornadas/{id}/excluir/` com proteção de tenant, checagem de vínculos relacionais e inativação lógica (`ativo=False`).
- Fluxo de exclusão com modal explicativo de consequências, confirmação explícita e desabilitação preventiva da ação quando há vínculos detectados na listagem.
- Persistência completa de `WorkSchedule.configuracao` com validação forte por tipo (ordem/sobreposição de períodos, regras de `12x36`, bloqueio de horários em `EXTERNA`).
- Endpoint público de CEP via ViaCEP com fallback manual (`GET /api/public/cep/`).
- Endpoint público de CNPJ com provider `CNPJá Open` e fallback manual (`GET /api/public/cnpj/`).
- Resolução de tenant unificada entre web/API e rate limit nas rotas públicas de autenticação.
- Fluxo visual pós-empresa com modal contextual para `Criar jornada`.
- Teste integrado `signup -> login -> painel -> empresa -> jornada -> logout`.
- Módulo `Colaboradores` entregue no núcleo funcional:
  - modelagem operacional com vínculo explícito à jornada
  - listagem com filtros/abas
  - cadastro e edição
  - ativação/inativação
  - rastreabilidade biométrica básica
  - captura facial assistida no painel
  - webcam como canal principal com upload como fallback operacional
  - envio de convite biométrico remoto por WhatsApp com autoatendimento via link seguro
- Módulo `Relógios de Ponto` entregue no núcleo funcional:
  - listagem, criação, edição e alteração de status no painel
  - detalhe operacional com abas `Informações` e `Colaboradores`
  - geofence/cerca virtual
  - ativação por código
  - APIs de gestão e atribuição de colaboradores

Itens pendentes após o encerramento do `DEV-008`:
- refinamento visual final da tela de jornada e catálogo completo de estados/mensagens
- acabamentos remanescentes de `Colaboradores`:
  - jornada individual `Personalizado (entrada manual)`
  - semântica completa de `Transferidos`
  - ações rápidas adicionais na listagem
- módulos pós-onboarding ainda não implementados:
  - `Tratamento de Ponto`
  - `Relatórios`
  - `Solicitações`

Observação de governança:
- o detalhamento de aceite e a movimentação desse escopo são mantidos em `docs/DEV_008_CHECKLIST.md`;
- este documento deve permanecer estável como mapa técnico do bloco, sem duplicar controle fino de sprint.

---

## 8. Critérios de aceite específicos do onboarding visual

- Após login sem empresa, `/painel` destaca CTA para criar primeira empresa.
- Após cadastro da empresa, painel exibe estado de pendência para próxima etapa:
  - boas-vindas
  - stepper
  - card de pendências
  - CTA para **Criar jornada**.
- Clique em **Criar jornada** abre tela de nova jornada no padrão definido.
- Menu lateral respeita matriz de liberação por estado de onboarding.
- Liberação é tenant-aware; não há vazamento de estado entre empresas.

---

## 9. Escopo fora do DEV-008

- Cálculo completo de banco de horas.
- Engine legal AFD/AEJ completa.
- Fluxos avançados de solicitações e relatórios.
- Integrações externas além de CNPJá Open e ViaCEP no onboarding.

---

## 10. Entregáveis de documentação

- Este documento como referência funcional/técnica do onboarding.
- Anexo de especificação 1:1 da tela `Nova Jornada de Trabalho`.
- Anexo de especificação da área `Colaboradores`.
- Anexo de especificação da área `Relógios de Ponto`.
- Anexo de especificação da área `Tratamento de Ponto`.
- Anexo de especificação da área `Relatórios`.
- Anexo de especificação da área `Solicitações`.
- Atualização da seção DEV-008 do roadmap com vínculo para este detalhamento.
- Checklist operacional versionado para execução e validação da DEV-008.
