# DEV-008 Checklist (Versionado)
**Versão:** 2.6  
**Data:** 2026-03-09  
**Escopo:** onboarding conta proprietária + empresa única + liberação progressiva do painel

**Documentos base:** `docs/DEV_008_ONBOARDING_MODELAGEM.md`, `docs/DEV_008_TELA_NOVA_JORNADA.md`, `docs/DEV_008_AREA_COLABORADORES.md`, `docs/DEV_008_AREA_RELOGIOS_PONTO.md`, `docs/DEV_008_TRATAMENTO_PONTO.md`, `docs/DEV_008_AREA_RELATORIOS.md`, `docs/DEV_008_AREA_SOLICITACOES.md`

## Snapshot de execução (atualizado em 2026-03-09)
- [x] Landing pública (`/`) implementada com CTAs para `Entrar` e `Começar Agora`
- [x] Login web (`/login/`) com UX atualizada no padrão visual da landing
- [x] Cadastro web (`/cadastro/`) com UX atualizada e campos `nome`, `sobrenome`, `e-mail`, `CPF`, `telefone`, `senha` e `confirmar senha`
- [x] Logout web (`POST /logout/`) com invalidação de sessão
- [x] Guarda de acesso em `/painel/` para usuário não autenticado
- [x] Testes de fluxo web inicial (signup/login/logout/guard) atualizados em `apps/accounts/test_web.py`
- [x] Cadastro completo com `CPF` do owner (premissa de negócio)
- [x] Onboarding da empresa (PJ/PF) com vínculo owner/tenant e bloqueio de segunda empresa no fluxo web
- [x] Regra 1:1 endurecida com lock transacional no owner + constraint de banco para 1 owner por tenant

## 1) Premissas obrigatórias
- [x] Regra 1:1 preservada: `1 owner -> 1 empresa -> 1 tenant`
- [x] `email` do owner único global
- [x] `cpf` do owner único global e obrigatório
- [x] Empresa com suporte `PJ/PF` e documento único normalizado
- [x] Isolamento por tenant mantido em todo o fluxo
- [ ] Stack web respeitada: Django Templates + Tailwind + HTMX + Alpine.js

## 2) Modelagem e backend
- [x] Evoluir `accounts.User` com campos de onboarding (`first_name`, `last_name`, `cpf`, `phone`, `is_account_owner`)
- [x] Evoluir `tenants.Tenant` para `tipo_pessoa` + `documento` mantendo compatibilidade com legado
- [x] Adicionar constraints de unicidade e vínculo 1:1 owner/tenant (owner único por tenant)
- [x] Persistir estado de onboarding no tenant (`onboarding_step`, `onboarding_completed_at`)
- [x] Implementar `AccountOnboardingService` transacional
- [x] Impedir criação de segunda empresa por owner (erro semântico claro)
- [x] Garantir contexto de tenant nas operações subsequentes

## 3) Integrações externas do onboarding
- [ ] Consulta de CNPJ (provider primário: CNPJá Open)
- [ ] Fallback manual ativo em falha/timeout do provider
- [x] Consulta de CEP via ViaCEP
- [x] Fallback manual ativo em CEP inválido/indisponibilidade

## 4) Painel e UX de onboarding (`/painel`)
- [x] Esqueleto visual implementado:
  - sidebar fixa
  - topbar com seletor de empresa central
  - cabeçalho de boas-vindas com stepper
  - área de conteúdo para cards/listagens
- [x] Estado sem empresa: exibir banner/CTA `Criar sua primeira empresa`
- [x] Estado após empresa: exibir pendência `Criar horário da equipe`
- [ ] Exibir modal contextual com CTA `Criar jornada`
- [x] Navegação para tela `Nova Jornada de Trabalho` ao clicar em `Criar jornada`
- [x] Tela de nova jornada MVP implementada (nome, descrição, 4 tipos e painel explicativo por tipo)
- [ ] Tela de nova jornada 1:1 com layout aprovado (breadcrumb, card principal, 4 cards de tipo e ações)
- [ ] Ao selecionar `Semanal`, exibir blocos expandidos: painel explicativo, `Dúvidas comuns`, atalhos de jornada, toggle de intervalo reduzido e grade semanal
- [ ] Atalhos `Integral 44h`, `Comercial 40h`, `Parcial 30h` e `Personalizar` aplicados corretamente na grade
- [ ] Ao selecionar `12x36`, exibir configuração de data/hora base + ação `Gerar/Atualizar escala` + grade alternada trabalho/folga
- [ ] Ao selecionar `Fracionada`, exibir edição por múltiplos períodos no dia + ações `Adicionar Período` e `Copiar horários para os demais dias`
- [ ] Ao selecionar `Externa`, exibir aviso de não uso de horários fixos e bloquear configuração de grade horária
- [ ] Estados de interação da tela aplicados (pristine, foco, selecionado, inválido, enviando, sucesso, erro)
- [ ] Validações e mensagens implementadas conforme catálogo do anexo da tela
- [x] Semântica negocial de cada tipo (`Semanal`, `12x36`, `Fracionada`, `Externa`) refletida nas regras de validação/cálculo

## 5) Módulo Colaboradores (`/painel/colaboradores`)
- [ ] Tela de listagem 1:1 com filtros por nome/CPF/PIS, turno, abas `Ativos`, `Inativos`, `Transferidos` e estado vazio
- [ ] Após cadastro, colaborador aparece na listagem com `Ativos (N)` atualizado, `Status = Ativo`, `Face = Pendente` (quando aplicável) e paginação coerente
- [ ] CTA `Novo Colaborador` abre formulário completo em seções (`Dados Básicos`, `Informações de Trabalho`, `Jornada de Trabalho`, `Reconhecimento Facial`)
- [ ] Regras obrigatórias de domínio aplicadas: `CPF` único por tenant, `PIS` válido para operação legal, nome obrigatório
- [ ] Vínculo de jornada no colaborador respeita semântica dos tipos de jornada
- [ ] Ao selecionar template de jornada (ex.: `Jornada Integral`), o card de tipo correspondente (ex.: `Semanal`) fica ativo e a seção expande com bloco explicativo
- [ ] Em `Personalizado (entrada manual)`, exibir estado inicial de seleção de tipo e expandir conforme card escolhido
- [ ] Fluxo de biometria permite captura imediata e fluxo posterior com rastreabilidade de consentimento/enroll
- [ ] Modal `Captura de Reconhecimento Facial` implementado com prévia, recaptura e consentimento obrigatório para confirmar
- [ ] Fluxo de envio de link de auto-cadastro facial por WhatsApp implementado com token expirável e uso único
- [ ] Antes do envio por WhatsApp, exibir modal de confirmação com telefone do colaborador e ações `Cancelar`/`Enviar`
- [ ] Coluna `Ações` da listagem com operações rápidas (reenviar link WhatsApp, editar, alterar status)

## 6) Módulo Relógios de Ponto (`/painel/relogio-digital` no código atual; alvo funcional `/painel/relogios`)
- [ ] Tela de listagem 1:1 com breadcrumb, banner orientativo, filtros e estado vazio (`Nenhum resultado encontrado`)
- [ ] Ação `Criar Relógio` abre formulário com `Nome`, `Descrição`, `Tipo do Relógio`, `Status` e autenticação facial fixa
- [ ] Validações aplicadas: nome obrigatório/único por tenant, tipo obrigatório e método fixo `Reconhecimento Facial`
- [ ] Após criar, relógio aparece em card com badge `Ativo`, badge de tipo `REP-P`, código de ativação e ações (`Gerenciar`, `Inativar Relógio`)
- [ ] Fluxo `Inativar Relógio` altera status sem remover histórico
- [ ] Status do relógio suporta `Ativo`, `Inativo` e `Em Manutenção` em listagem/detalhe/edição
- [ ] Ação `Gerenciar` abre a tela de detalhe do relógio (`/painel/relogios/{id}/`) com abas `Informações` e `Colaboradores`
- [ ] Aba `Informações` é padrão ao abrir detalhe e exibe metadados completos (status, tipo REP, plataforma, métodos, código de ativação, sincronização, criado em)
- [ ] Card `Cerca Virtual` exibe estado vazio e CTA `Configurar Cerca Virtual`
- [ ] Aba `Colaboradores` implementa dupla listagem (`Disponíveis` x `No Relógio`) com busca, filtros e ações de mover/remover em lote
- [ ] Contadores `(N)` e estados desabilitado/habilitado dos botões de ação refletem seleção/lista em tempo real
- [ ] API `PATCH /api/relogios/{id}/` para `Editar Relógio` com validações de nome único por tenant, método fixo `FACIAL` e status (`ATIVO|INATIVO|EM_MANUTENCAO`)
- [ ] Fluxo de ativação por código documentado e implementado (`POST /api/relogios/ativar/` ou extensão de `POST /api/auth/device/register/`)
- [ ] Ativação bloqueada quando status do relógio for `INATIVO` ou `EM_MANUTENCAO`
- [ ] API `PUT /api/relogios/{id}/cerca-virtual/` para configurar geofence com validação de latitude/longitude/raio
- [ ] API de remoção/desativação de cerca virtual (`DELETE` ou `PATCH ativo=false`) implementada com retorno consistente
- [ ] `GET /api/relogios/{id}/` retorna representação de `cerca_virtual` (objeto ou `null`) para renderizar aba `Informações`
- [ ] APIs da aba `Colaboradores` implementadas:
  - `GET /api/relogios/{id}/colaboradores/disponiveis/`
  - `GET /api/relogios/{id}/colaboradores/no-relogio/`
  - `POST /api/relogios/{id}/colaboradores/mover-selecionados/`
  - `POST /api/relogios/{id}/colaboradores/mover-todos/`
  - `POST /api/relogios/{id}/colaboradores/remover-selecionados/`
  - `POST /api/relogios/{id}/colaboradores/remover-todos/`
- [ ] Regras de elegibilidade e idempotência respeitadas nas ações em lote (sem duplicar vínculo e sem excluir colaborador do tenant)
- [ ] Batida (`POST /api/attendance/register/`) valida pré-condições do relógio: dispositivo ativado, relógio ativo, colaborador atribuído e colaborador ativo

## 7) Módulo Tratamento de Ponto (`/painel/tratamento-ponto`)
- [ ] Tela de listagem 1:1 com breadcrumb, período mensal, busca de colaborador, filtros de inconsistência/pendência e ação `Ver Pendências`
- [ ] Tabela de colaboradores com colunas de indicadores (`Saldo BH`, `HE 50%`, `HE 100%`, `Atrasos`, `Faltas`, `Pendências`) e ação `Ver Espelho`
- [ ] Navegação `Ver Espelho` abre espelho por colaborador e período selecionado
- [ ] Tela `Espelho de Ponto` 1:1 com cards de indicadores, badge de período (`Aberto`) e ação `Ajuste Automático`
- [ ] Legenda de marcações implementada: `Original (AFD)`, `A ser adicionada`, `Adicionada (Pendente/Aprovada/Rejeitada)`, `Desconsiderada`, `Fora da cerca virtual`
- [ ] Grade diária com estados visuais (normal, inconsistência, pendência crítica) e ação `Editar` por dia
- [ ] Ocorrências críticas (ex.: `Falta saída`) aparecem na coluna `Ocorrências` com destaque visual
- [ ] APIs do módulo implementadas:
  - `GET /api/tratamento-ponto/colaboradores/`
  - `GET /api/tratamento-ponto/espelho/{employee_id}/`
  - `POST /api/tratamento-ponto/espelho/{employee_id}/dias/{date}/ajustes/`
  - `POST /api/tratamento-ponto/espelho/{employee_id}/ajuste-automatico/`
- [ ] Regras de cálculo diário/mensal e auditoria de ajustes respeitadas no período aberto

## 8) Módulo Relatórios (`/painel/relatorios`)
- [ ] Tela índice 1:1 com cards `Espelho de Ponto`, `Cartão de Ponto` e `Detalhes dos Cálculos`
- [ ] Cada card abre formulário específico com breadcrumb e ação `Voltar para Relatórios`
- [ ] Filtros de período (mês rápido ou data inicial/final) e colaborador aplicados na geração
- [ ] Tela `Detalhes dos Cálculos` suporta modo `Por Dia` e `Consolidado`
- [ ] Botão `Baixar PDF` habilita somente após geração válida do relatório
- [ ] APIs do módulo implementadas:
  - `POST /api/relatorios/espelho-ponto/gerar/`
  - `POST /api/relatorios/cartao-ponto/gerar/`
  - `POST /api/relatorios/detalhes-calculos/gerar/`
  - `GET /api/relatorios/download/{report_id}/`

## 9) Módulo Solicitações (`/painel/solicitacoes`)
- [ ] Tela índice 1:1 com cards `Solicitações de Ajuste` e `Solicitações de Acesso`
- [ ] Cada card exibe contagem de pendências e estado vazio quando aplicável
- [ ] Ação `Acessar` navega para listagem detalhada do tipo correspondente
- [ ] Tela interna `Solicitações de Ajuste` (Acessar) 1:1 com breadcrumb, filtros, tabela detalhada e ações por linha (`Visualizar`, `Aprovar`, `Rejeitar`)
- [ ] Tela interna `Solicitações de Acesso` (Acessar) 1:1 com breadcrumb, filtros, tabela detalhada e ações por linha (`Visualizar`, `Aprovar`, `Rejeitar`)
- [ ] Drawer/modal `Visualizar` exibe contexto completo da solicitação e histórico de decisões
- [ ] Fluxo de decisão (aprovar/rejeitar) com rastreabilidade e validação de permissão
- [ ] APIs do módulo implementadas:
  - `GET /api/solicitacoes/resumo/`
  - `GET /api/solicitacoes/ajustes/`
  - `GET /api/solicitacoes/ajustes/{id}/`
  - `GET /api/solicitacoes/acessos/`
  - `GET /api/solicitacoes/acessos/{id}/`
  - `POST /api/solicitacoes/ajustes/{id}/decidir/`
  - `POST /api/solicitacoes/acessos/{id}/decidir/`

## 10) Liberação de menu por estado
- [x] Sem empresa: apenas `Início` e `Empresa` ativos
- [x] Com empresa e sem jornada: liberar `Jornadas de Trabalho`
- [x] Após primeira jornada: liberar `Colaboradores`, `Relógio Digital`, `Tratamento de Ponto`, `Relatórios`, `Solicitações`, `Configurações`
- [x] Itens bloqueados exibem mensagem de pré-requisito

## 11) Qualidade e testes
- [x] Testes unitários de validação CPF/CNPJ e regras 1:1
- [ ] Testes de integração: signup -> login -> painel -> cadastro empresa -> criar jornada -> logout
- [x] Testes de autorização e isolamento tenant-aware
- [ ] Testes de integrações externas (CNPJ e CEP): sucesso, falha e timeout

## 12) Critério de aceite DEV-008
- [x] Owner consegue concluir onboarding inicial sem intervenção manual do time técnico
- [x] Sistema bloqueia segunda empresa para a mesma conta
- [x] Menu libera funcionalidades progressivamente conforme onboarding
- [ ] Fluxo visual pós-empresa e modal de `Criar jornada` funciona de ponta a ponta
- [x] Sem vazamento cross-tenant durante todo o processo

## 13) Comando de validação sugerido
```bash
pytest apps/ -k "onboarding or accounts or tenants or journeys"
```
