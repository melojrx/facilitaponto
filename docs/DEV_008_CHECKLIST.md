# DEV-008 Checklist (Versionado)
**Versão:** 3.0  
**Data:** 2026-03-11  
**Escopo:** onboarding conta proprietária + empresa única + liberação progressiva do painel

**Documentos base:** `docs/DEV_008_ONBOARDING_MODELAGEM.md`, `docs/DEV_008_TELA_NOVA_JORNADA.md`, `docs/DEV_008_AREA_COLABORADORES.md`, `docs/DEV_008_AREA_RELOGIOS_PONTO.md`, `docs/DEV_008_TRATAMENTO_PONTO.md`, `docs/DEV_008_AREA_RELATORIOS.md`, `docs/DEV_008_AREA_SOLICITACOES.md`

## Como manter esta documentação
- `docs/DEV_008_CHECKLIST.md` é a fonte oficial de acompanhamento de execução, aceite, cortes de escopo e ordem da próxima sprint.
- `docs/DEV_008_ONBOARDING_MODELAGEM.md` funciona como índice técnico/funcional do bloco `DEV-008`, com arquitetura, etapas e dependências entre módulos.
- `docs/DEV_008_TELA_NOVA_JORNADA.md` e os arquivos `docs/DEV_008_AREA_*.md` são especificações funcionais de tela/módulo; eles não devem virar checklist paralelo de sprint.
- `docs/DEV_ROADMAP.md` e `docs/PRODUCT_BACKLOG.md` mantêm apenas o recorte macro de prioridade; o detalhamento operacional permanece neste checklist.
- Ao concluir ou mover escopo, atualizar primeiro este arquivo e depois refletir o ajuste nos demais documentos.

## Snapshot de execução (atualizado em 2026-03-13)
- [x] Landing pública (`/`) implementada com CTAs para `Entrar` e `Começar Agora`
- [x] Login web (`/login/`) com UX atualizada no padrão visual da landing
- [x] Cadastro web (`/cadastro/`) com UX atualizada e campos `nome`, `sobrenome`, `e-mail`, `CPF`, `telefone`, `senha` e `confirmar senha`
- [x] Logout web (`POST /logout/`) com invalidação de sessão
- [x] Guarda de acesso em `/painel/` para usuário não autenticado
- [x] Testes de fluxo web inicial (signup/login/logout/guard) atualizados em `apps/accounts/test_web.py`
- [x] Cadastro completo com `CPF` do owner (premissa de negócio)
- [x] Onboarding da empresa (PJ/PF) com vínculo owner/tenant e bloqueio de segunda empresa no fluxo web
- [x] Regra 1:1 endurecida com lock transacional no owner + constraint de banco para 1 owner por tenant
- [x] CRUD web de jornadas implementado (`listar`, `criar`, `editar`, `excluir` com inativação segura)
- [x] Exclusão de jornada com modal de confirmação, explicação de impacto e bloqueio visual quando há vínculos detectados
- [x] Consulta pública de CNPJ implementada com provider `CNPJá Open`, fallback manual e testes de erro/timeout
- [x] Painel pós-empresa com modal contextual de `Criar jornada` funcionando de ponta a ponta
- [x] Teste integrado do fluxo `signup -> login -> painel -> empresa -> jornada -> logout`
- [x] Módulo `Colaboradores` entregue no núcleo funcional: cadastro operacional, listagem com filtros/abas, edição, ativação/inativação e rastreabilidade biométrica básica
- [x] Captura facial assistida no painel implementada com modal mínimo, consentimento obrigatório e enroll
- [x] Convite biométrico remoto por WhatsApp implementado com link seguro, expirável e de uso único
- [x] Runtime biométrico formalizado como pré-requisito operacional da feature (`BIOMETRIA_KEY`, dependências de ML/imagem e preload de pesos do `DeepFace`)
- [x] Sequência oficial do próximo bloco atualizada para o estado real do código: `Tratamento de Ponto -> Relatórios -> Solicitações`

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
- [x] Consulta de CNPJ (provider primário: CNPJá Open)
- [x] Fallback manual ativo em falha/timeout do provider
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
- [x] Exibir modal contextual com CTA `Criar jornada`
- [x] Navegação para tela `Nova Jornada de Trabalho` ao clicar em `Criar jornada`
- [x] Tela de nova jornada MVP implementada (nome, descrição, 4 tipos e painel explicativo por tipo)
- [ ] Tela de nova jornada 1:1 com layout aprovado (breadcrumb, card principal, 4 cards de tipo e ações)
- [ ] Ao selecionar `Semanal`, exibir blocos expandidos: painel explicativo, `Dúvidas comuns`, atalhos de jornada, toggle de intervalo reduzido e grade semanal
- [x] Atalhos `Integral 44h`, `Comercial 40h`, `Parcial 30h` e `Personalizar` aplicados corretamente na grade
- [x] Ao selecionar `12x36`, exibir configuração de data/hora base + ação `Gerar/Atualizar escala` + grade alternada trabalho/folga
- [x] Ao selecionar `Fracionada`, exibir edição por múltiplos períodos no dia + ações `Adicionar Período` e `Copiar horários para os demais dias`
- [x] Ao selecionar `Externa`, exibir aviso de não uso de horários fixos e bloquear configuração de grade horária
- [x] Tela de listagem de jornadas (`/painel/jornadas/`) com busca, filtro por status e ações de edição/exclusão
- [x] Excluir jornada com modal explicativo de consequências e confirmação explícita
- [ ] Estados de interação da tela aplicados (pristine, foco, selecionado, inválido, enviando, sucesso, erro)
- [ ] Validações e mensagens implementadas conforme catálogo do anexo da tela
- [x] Semântica negocial de cada tipo (`Semanal`, `12x36`, `Fracionada`, `Externa`) refletida nas regras de validação/cálculo

## 5) Módulo Colaboradores (`/painel/colaboradores`)
- [ ] Tela de listagem 1:1 com filtros por nome/CPF/PIS, turno, abas `Ativos`, `Inativos`, `Transferidos` e estado vazio
- [x] Após cadastro, colaborador aparece na listagem com `Ativos (N)` atualizado, `Status = Ativo`, `Face = Pendente` (quando aplicável) e paginação coerente
- [x] CTA `Novo Colaborador` abre formulário completo em seções (`Dados Básicos`, `Informações de Trabalho`, `Jornada de Trabalho`, `Reconhecimento Facial`)
- [x] Regras obrigatórias de domínio aplicadas: `CPF` único por tenant, `PIS` válido para operação legal, nome obrigatório
- [x] Vínculo de jornada no colaborador respeita semântica dos tipos de jornada
- [ ] Ao selecionar template de jornada (ex.: `Jornada Integral`), o card de tipo correspondente (ex.: `Semanal`) fica ativo e a seção expande com bloco explicativo
- [ ] Em `Personalizado (entrada manual)`, exibir estado inicial de seleção de tipo e expandir conforme card escolhido
- [x] Fluxo de biometria permite captura imediata e fluxo posterior com rastreabilidade de consentimento/enroll
- [x] Modal `Captura de Reconhecimento Facial` implementado com prévia, recaptura e consentimento obrigatório para confirmar
- [x] Pré-requisito operacional da captura formalizado:
  - `BIOMETRIA_KEY` carregada no ambiente
  - dependências biométricas instaladas no runtime
  - preload de pesos `ArcFace` + `retinaface` antes do primeiro uso real
- [x] `Webcam no painel` implementada como canal principal da captura facial assistida
- [x] `Upload no painel` mantido como fallback operacional da captura biométrica
- [x] Diretriz registrada: webcam e upload convergem para o mesmo fluxo negocial de consentimento + enroll
- [x] Fluxo de envio de link de auto-cadastro facial por WhatsApp implementado com token expirável e uso único
- [x] Antes do envio por WhatsApp, exibir modal de confirmação com telefone do colaborador e ações `Cancelar`/`Enviar`
- [ ] Coluna `Ações` da listagem com operações rápidas (reenviar link WhatsApp, editar, alterar status)

## 6) Módulo Relógios de Ponto (`/painel/relogio-digital` no código atual; alvo funcional `/painel/relogios`)
- [x] Plano exato de execução das telas do `Dia 2` e `Dia 3` documentado em `docs/DEV_008_AREA_RELOGIOS_PONTO.md`
- [x] Canal oficial do app do relógio no MVP formalizado como `APK Android` distribuído internamente para instalação direta no tablet da portaria, sem dependência inicial de `Play Store`
- [x] Tela de listagem 1:1 com breadcrumb, banner orientativo, filtros e estado vazio (`Nenhum resultado encontrado`)
- [x] Ação `Criar Relógio` abre formulário com `Nome`, `Descrição`, `Tipo do Relógio`, `Status` e autenticação facial fixa
- [x] Validações aplicadas: nome obrigatório/único por tenant, tipo obrigatório e método fixo `Reconhecimento Facial`
- [x] Após criar, relógio aparece em card com badge `Ativo`, badge de tipo `REP-P`, código de ativação e ações (`Gerenciar`, `Inativar Relógio`)
- [x] Fluxo `Inativar Relógio` altera status sem remover histórico
- [x] Status do relógio suporta `Ativo`, `Inativo` e `Em Manutenção` em listagem/detalhe/edição
- [x] Ação `Gerenciar` abre a tela de detalhe do relógio (`/painel/relogios/{id}/`) com abas `Informações` e `Colaboradores`
- [x] Aba `Informações` é padrão ao abrir detalhe e exibe metadados completos (status, tipo REP, plataforma, métodos, código de ativação, sincronização, criado em)
- [x] Card `Cerca Virtual` exibe estado vazio e CTA `Configurar Cerca Virtual`
- [x] Aba `Colaboradores` implementa dupla listagem (`Disponíveis` x `No Relógio`) com busca, filtros e ações de mover/remover em lote
- [x] Contadores `(N)` e estados desabilitado/habilitado dos botões de ação refletem seleção/lista em tempo real
- [x] API `PATCH /api/relogios/{id}/` para `Editar Relógio` com validações de nome único por tenant, método fixo `FACIAL` e status (`ATIVO|INATIVO|EM_MANUTENCAO`)
- [x] Fluxo de ativação por código documentado e implementado (`POST /api/relogios/ativar/` ou extensão de `POST /api/auth/device/register/`)
- [x] Ativação bloqueada quando status do relógio for `INATIVO` ou `EM_MANUTENCAO`
- [x] API `PUT /api/relogios/{id}/cerca-virtual/` para configurar geofence com validação de latitude/longitude/raio
- [x] API de remoção/desativação de cerca virtual (`DELETE` ou `PATCH ativo=false`) implementada com retorno consistente
- [x] `GET /api/relogios/{id}/` retorna representação de `cerca_virtual` (objeto ou `null`) para renderizar aba `Informações`
- [x] APIs da aba `Colaboradores` implementadas:
  - `GET /api/relogios/{id}/colaboradores/disponiveis/`
  - `GET /api/relogios/{id}/colaboradores/no-relogio/`
  - `POST /api/relogios/{id}/colaboradores/mover-selecionados/`
  - `POST /api/relogios/{id}/colaboradores/mover-todos/`
  - `POST /api/relogios/{id}/colaboradores/remover-selecionados/`
  - `POST /api/relogios/{id}/colaboradores/remover-todos/`
- [x] Regras de elegibilidade e idempotência respeitadas nas ações em lote (sem duplicar vínculo e sem excluir colaborador do tenant)
- [x] Batida (`POST /api/attendance/register/`) valida pré-condições do relógio: dispositivo ativado, relógio ativo, colaborador atribuído e colaborador ativo

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
- [x] Testes de integração: signup -> login -> painel -> cadastro empresa -> criar jornada -> logout
- [x] Testes de autorização e isolamento tenant-aware
- [x] Testes de integrações externas (CNPJ e CEP): sucesso, falha e timeout

## 12) Critério de aceite DEV-008
- [x] Owner consegue concluir onboarding inicial sem intervenção manual do time técnico
- [x] Sistema bloqueia segunda empresa para a mesma conta
- [x] Menu libera funcionalidades progressivamente conforme onboarding
- [x] Fluxo visual pós-empresa e modal de `Criar jornada` funciona de ponta a ponta
- [x] Sem vazamento cross-tenant durante todo o processo

## 13) Comando de validação sugerido
```bash
pytest apps/ -k "onboarding or accounts or tenants or journeys"
```

## 14) Encerramento formal do bloco (2026-03-11)
- [x] `DEV-008` encerrado para aceite funcional do onboarding e da liberação progressiva do painel
- [x] Escopo efetivamente concluído neste bloco:
  - cadastro/login/logout web
  - owner com `CPF` obrigatório e vínculo `1:1` com empresa/tenant
  - onboarding de empresa `PJ/PF`
  - consultas públicas de `CEP` e `CNPJ` com fallback manual
  - painel pós-empresa com CTA/modal para `Criar jornada`
  - CRUD web de jornadas
  - testes integrados e testes de integrações externas
- [x] Itens removidos do bloco de aceite do `DEV-008` e transferidos para a próxima sprint:
  - refinamento visual final da stack/tela de jornada ainda não fechado nos itens pendentes das seções `1` e `4`
  - módulo `Relógios de Ponto` (seção `6`)
  - módulo `Tratamento de Ponto` (seção `7`)
  - módulo `Relatórios` (seção `8`)
  - módulo `Solicitações` (seção `9`)

## 15) Encerramento do bloco Colaboradores (2026-03-11)
- [x] Cadastro operacional real do colaborador implementado com vínculo explícito à jornada
- [x] Listagem web com busca por `nome/CPF/PIS`, filtro por jornada, abas de status e paginação simples
- [x] Edição e ativação/inativação de colaborador funcionando no painel
- [x] Estado biométrico do colaborador com rastreabilidade básica de consentimento e enroll
- [x] Smoke da área validado com testes web + model/service + `biometrics` + `attendance`
- [x] Itens fora desta sprint e movidos para o próximo bloco funcional:
  - envio de link de auto-cadastro facial por WhatsApp
  - jornada individual `Personalizado (entrada manual)` no cadastro
  - semântica completa da aba `Transferidos`
  - ação rápida de WhatsApp na coluna `Ações`

## 16) Sequência oficial do próximo bloco funcional
- [x] Ordem oficial de execução atualizada após fechamento de `Relógios de Ponto` e do fluxo biométrico remoto:
  - `1. Tratamento de Ponto`
  - `2. Relatórios`
  - `3. Solicitações`
- [x] Justificativa operacional registrada:
  - `Relógios de Ponto` já fecha o uso real do colaborador no contexto da batida.
  - `Captura facial no painel` e `Envio por WhatsApp` já foram incorporados ao fluxo biométrico operacional.
  - `Tratamento`, `Relatórios` e `Solicitações` continuam dependentes dos dados operacionais já produzidos pelos blocos anteriores.

## 17) Decisão técnica formal para WhatsApp
- [x] O fluxo de envio por WhatsApp deve ser implementado com arquitetura `adapter pluggable`.
- [x] O domínio do produto não deve depender diretamente de `WAHA`, `Evolution API` ou `Meta Cloud API`.
- [x] Provider inicial do MVP definido:
  - `WAHA`, por rapidez de implementação, baixo atrito operacional e aderência ao contexto do produto (`PMEs`, infra enxuta, solo dev).
- [x] Opções documentadas para evolução futura:
  - `Evolution API`
  - `Meta WhatsApp Cloud API` ou BSP oficial
- [x] Critério de implementação:
  - persistir `provider`, identificador da mensagem, status, timestamps e erro de envio;
  - permitir troca de provider sem reescrever o fluxo negocial de convite biométrico.
