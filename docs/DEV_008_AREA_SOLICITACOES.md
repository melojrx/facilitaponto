# DEV-008 — Especificação da Área Solicitações
**Versão:** 1.2  
**Data:** 2026-03-11  
**Contexto:** módulo `Solicitações` no painel web  
**Referências:** `docs/DEV_008_ONBOARDING_MODELAGEM.md`, `docs/PRD.md`, mocks visuais aprovados

---

## 1. Objetivo

Documentar:

- tela índice de `Solicitações`
- tela interna de `Solicitações de Ajuste` (acesso via CTA `Acessar`)
- tela interna de `Solicitações de Acesso` (acesso via CTA `Acessar`)
- fluxos de decisão (aprovar/rejeitar) com trilha auditável

Rotas alvo (MVP):
- `GET /painel/solicitacoes/`
- `GET /painel/solicitacoes/ajustes/`
- `GET /painel/solicitacoes/acessos/`

---

## Papel deste documento

- Este arquivo é a especificação funcional da área `Solicitações`.
- O status oficial de execução e a ordem da sprint ficam em `docs/DEV_008_CHECKLIST.md`.
- O enquadramento do módulo na arquitetura do `DEV-008` fica em `docs/DEV_008_ONBOARDING_MODELAGEM.md`.

## Status de implementação (2026-03-11)

- O módulo ainda não foi implementado.
- Ele entra depois de `Tratamento de Ponto` e `Relatórios`, quando já existirem eventos operacionais e decisões a governar.
- Este documento deve ser mantido como especificação de fluxo e rastreabilidade, sem duplicar controle de sprint.

---

## 2. Semântica negocial

### 2.1 Papel do módulo
- Central de governança de solicitações operacionais.
- Separa o trabalho em dois domínios:
  - `Ajuste` (marcações de ponto)
  - `Acesso` (dados e integrações)

### 2.2 Ciclo de status
- `PENDENTE`
- `APROVADA`
- `REJEITADA`
- `CANCELADA` (quando aplicável por regra interna)

### 2.3 Regras de decisão
- Aprovação/rejeição é registrada com:
  - usuário decisor
  - data/hora
  - justificativa (obrigatória para rejeição)
- Solicitação já decidida não pode ser decidida novamente.

---

## 3. Tela `Solicitações` (índice) — referência da imagem 5

### 3.1 Estrutura visual
- Breadcrumb: `Início > Solicitações`
- Título: `Solicitações`
- Subtítulo: `Gerencie solicitações de ajuste de ponto e acesso a dados`

### 3.2 Cards exibidos
Card `Solicitações de Ajuste`:
- CTA `Acessar`
- contador de pendências
- estado vazio: `Nenhuma solicitação pendente`

Card `Solicitações de Acesso`:
- CTA `Acessar`
- contador de pendências
- estado vazio: `Nenhuma solicitação pendente`

### 3.3 Comportamento
- CTA `Acessar` redireciona para lista detalhada do tipo.
- Contadores refletem dados em aberto do tenant.

---

## 4. Tela interna `Solicitações de Ajuste` (Acessar) — nível 1:1

### 4.1 Estrutura visual
- Breadcrumb: `Início > Solicitações > Solicitações de Ajuste`
- Título: `Solicitações de Ajuste`
- Subtítulo: `Gerencie pedidos de correção de marcações de ponto`
- Botão de retorno: `Voltar para Solicitações`

### 4.2 Filtros
- `Período` (mês rápido ou data inicial/final)
- `Colaborador`
- `Status` (`Todos`, `Pendentes`, `Aprovadas`, `Rejeitadas`, `Canceladas`)
- `Buscar solicitação...` (texto livre)

### 4.3 Tabela detalhada
Colunas mínimas:
- `Protocolo`
- `Colaborador`
- `Data de Referência`
- `Tipo de Ajuste`
- `Motivo`
- `Status`
- `Solicitado em`
- `Ações`

### 4.4 Ações por linha
- `Visualizar`
- `Aprovar` (quando pendente)
- `Rejeitar` (quando pendente)

### 4.5 Detalhe da solicitação (drawer/modal)
Blocos mínimos:
- dados do solicitante
- marcações originais do dia
- marcações propostas para ajuste
- justificativa/anexos
- histórico de decisões

### 4.6 Estados da tela
- estado vazio:
  - `Nenhuma solicitação encontrada para os filtros aplicados`
- estado carregando:
  - skeletons na tabela
- estado erro:
  - mensagem global + ação de tentar novamente

---

## 5. Tela interna `Solicitações de Acesso` (Acessar) — nível 1:1

### 5.1 Estrutura visual
- Breadcrumb: `Início > Solicitações > Solicitações de Acesso`
- Título: `Solicitações de Acesso`
- Subtítulo: `Gerencie pedidos de acesso a dados e integrações`
- Botão de retorno: `Voltar para Solicitações`

### 5.2 Filtros
- `Período`
- `Status`
- `Tipo de Acesso` (integração/exportação/leitura avançada)
- `Buscar solicitação...`

### 5.3 Tabela detalhada
Colunas mínimas:
- `Protocolo`
- `Solicitante`
- `Recurso/Integração`
- `Escopo`
- `Finalidade`
- `Status`
- `Solicitado em`
- `Ações`

### 5.4 Ações por linha
- `Visualizar`
- `Aprovar` (quando pendente)
- `Rejeitar` (quando pendente)

### 5.5 Detalhe da solicitação (drawer/modal)
Blocos mínimos:
- identificação do solicitante
- escopo e nível de acesso solicitado
- finalidade informada
- período/validade do acesso (quando aplicável)
- histórico de decisões

### 5.6 Estados da tela
- estado vazio:
  - `Nenhuma solicitação encontrada para os filtros aplicados`
- carregando e erro seguem padrão da tela de ajustes.

---

## 6. Fluxos operacionais

### 6.1 Fluxo índice -> lista interna
- Usuário entra em `/painel/solicitacoes/`.
- Clica `Acessar` em um card.
- Sistema navega para a lista interna do tipo com filtros padrão.

### 6.2 Fluxo de decisão
- Usuário abre `Visualizar`.
- Decide `Aprovar` ou `Rejeitar`.
- Rejeição exige justificativa.
- Sistema atualiza status e contadores de pendência.

### 6.3 Pós-decisão
- Registro da decisão fica visível no histórico.
- Solicitação sai da contagem de pendentes.

---

## 7. Regras de validação e autorização

- Usuário deve pertencer ao tenant da solicitação.
- Somente perfis com permissão podem decidir.
- `REJEITAR` exige justificativa com mínimo de 10 caracteres.
- Não permitir decisão em solicitação já finalizada (`APROVADA/REJEITADA/CANCELADA`).

---

## 8. Contrato de payload/API (MVP)

### 8.1 Resumo da tela índice
Endpoint:
- `GET /api/solicitacoes/resumo/`

Response `200` exemplo:

```json
{
  "ajustes": { "pendentes": 0, "total_abertas": 0 },
  "acessos": { "pendentes": 0, "total_abertas": 0 }
}
```

### 8.2 Lista de solicitações de ajuste
Endpoint:
- `GET /api/solicitacoes/ajustes/`

Query params:
- `status`
- `periodo_inicio`
- `periodo_fim`
- `employee_id`
- `q`
- `page`
- `page_size`

Response `200` exemplo:

```json
{
  "count": 1,
  "results": [
    {
      "id": "8cda4a7e-f42f-4f5d-a3eb-84ea15316d95",
      "protocolo": "AJ-20260308-0001",
      "employee_id": 123,
      "colaborador_nome": "FRANCISCO MARCIO GADELHA PAES",
      "data_referencia": "2026-03-08",
      "tipo_ajuste": "FALTA_SAIDA",
      "motivo": "Esqueceu de registrar saída",
      "status": "PENDENTE",
      "solicitado_em": "2026-03-08T14:00:00-03:00"
    }
  ]
}
```

### 8.3 Detalhe de solicitação de ajuste
Endpoint:
- `GET /api/solicitacoes/ajustes/{id}/`

Response `200` exemplo:

```json
{
  "id": "8cda4a7e-f42f-4f5d-a3eb-84ea15316d95",
  "protocolo": "AJ-20260308-0001",
  "status": "PENDENTE",
  "marcacoes_originais": ["13:33"],
  "marcacoes_propostas": ["13:33", "17:30"],
  "historico": []
}
```

### 8.4 Lista de solicitações de acesso
Endpoint:
- `GET /api/solicitacoes/acessos/`

Query params:
- `status`
- `periodo_inicio`
- `periodo_fim`
- `tipo_acesso`
- `q`
- `page`
- `page_size`

Response `200` exemplo:

```json
{
  "count": 1,
  "results": [
    {
      "id": "95aa4f4a-b4a4-447d-a49a-53ccf2f54f31",
      "protocolo": "AC-20260308-0001",
      "solicitante_nome": "Integração RH",
      "recurso": "API de Espelho de Ponto",
      "escopo": "LEITURA",
      "finalidade": "Conciliação mensal",
      "status": "PENDENTE",
      "solicitado_em": "2026-03-08T15:00:00-03:00"
    }
  ]
}
```

### 8.5 Detalhe de solicitação de acesso
Endpoint:
- `GET /api/solicitacoes/acessos/{id}/`

Response `200` exemplo:

```json
{
  "id": "95aa4f4a-b4a4-447d-a49a-53ccf2f54f31",
  "protocolo": "AC-20260308-0001",
  "status": "PENDENTE",
  "recurso": "API de Espelho de Ponto",
  "escopo": "LEITURA",
  "finalidade": "Conciliação mensal",
  "historico": []
}
```

### 8.6 Decisão de solicitação (aprovar/rejeitar)
Endpoints:
- `POST /api/solicitacoes/ajustes/{id}/decidir/`
- `POST /api/solicitacoes/acessos/{id}/decidir/`

Request exemplo:

```json
{
  "decisao": "APROVAR",
  "justificativa": "Conferido e validado.",
  "observacoes": "Aplicar imediatamente."
}
```

Request de rejeição:

```json
{
  "decisao": "REJEITAR",
  "justificativa": "Informações insuficientes para aprovação."
}
```

Response `200` exemplo:

```json
{
  "id": "8cda4a7e-f42f-4f5d-a3eb-84ea15316d95",
  "status": "APROVADA",
  "decidido_por": "gestor@empresa.com",
  "decidido_em": "2026-03-08T16:30:00-03:00"
}
```

### 8.7 Erros esperados
- `400` decisão inválida/justificativa ausente.
- `403` usuário sem permissão.
- `404` solicitação inexistente no tenant.
- `409` solicitação já decidida.

---

## 9. Catálogo de mensagens

Mensagens de estado:
- `Nenhuma solicitação pendente`
- `Nenhuma solicitação encontrada para os filtros aplicados`

Mensagens de operação:
- `Solicitação aprovada com sucesso.`
- `Solicitação rejeitada com sucesso.`
- `Não foi possível concluir a decisão da solicitação.`

Mensagens de validação:
- `Informe a justificativa para rejeitar a solicitação.`
- `Você não tem permissão para decidir esta solicitação.`
- `Esta solicitação já foi decidida.`

---

## 10. Critérios de aceite

- Tela índice renderiza os dois cards com contadores e estado vazio conforme referência.
- Cada `Acessar` abre lista interna 1:1 do tipo correspondente.
- Listas internas exibem filtros, tabela, status e ações por linha.
- `Visualizar` mostra detalhe com contexto suficiente para decisão.
- Aprovação/rejeição respeita permissão, validações e rastreabilidade.
- Isolamento por tenant é mantido em resumo, listagens, detalhes e decisões.
