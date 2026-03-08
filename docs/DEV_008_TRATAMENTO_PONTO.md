# DEV-008 — Especificação da Área Tratamento de Ponto
**Versão:** 1.0  
**Data:** 2026-03-08  
**Contexto:** módulo `Tratamento de Ponto` no painel web (após jornada e colaboradores ativos)  
**Referências:** `docs/DEV_008_ONBOARDING_MODELAGEM.md`, `docs/PRD.md`, mocks visuais aprovados

---

## 1. Objetivo

Documentar a área `Tratamento de Ponto` e a tela `Espelho de Ponto` com base nas referências visuais:

- listagem de colaboradores para auditoria de ponto
- acesso ao espelho por colaborador (`Ver Espelho`)
- leitura diária de marcações, saldo e ocorrências
- ações de ajuste (`Editar` por dia e `Ajuste Automático`)

Rotas alvo (MVP):
- `GET /painel/tratamento-ponto/`
- `GET /painel/tratamento-ponto/espelho/{colaborador_id}/`

---

## 2. Semântica negocial

### 2.1 Papel do tratamento de ponto
- Central de auditoria operacional das marcações já registradas.
- Permite identificar inconsistências, pendências e saldo por colaborador/período.
- Não substitui a origem legal (`Original AFD`); ajustes devem manter trilha auditável.

### 2.2 Conceitos de status de marcação (legenda do espelho)
- `Original (AFD)`: marcação original imutável registrada no sistema de ponto.
- `A ser adicionada`: sugestão de ajuste ainda não submetida definitivamente.
- `Adicionada (Pendente)`: ajuste submetido aguardando decisão.
- `Adicionada (Aprovada)`: ajuste aprovado e considerado no cálculo.
- `Adicionada (Rejeitada)`: ajuste recusado, não considerado no cálculo final.
- `Desconsiderada`: marcação descartada por decisão de tratamento (com rastreabilidade).
- `Fora da cerca virtual`: marcação detectada fora do perímetro configurado do relógio.

### 2.3 Inconsistência x pendência
- `Inconsistência`: divergência de jornada/marcação que impacta cálculo (ex.: dia útil sem marcações, saldo negativo).
- `Pendência`: evento que exige intervenção explícita (ex.: `Falta saída`).

### 2.4 Estado do período
- `Aberto`: período editável para tratamento.
- `Fechado` (evolução): bloqueia alterações e mantém somente consulta/auditoria.

### 2.5 Relação com jornada e relógio
- Cálculos exibidos no espelho dependem da jornada prevista do colaborador.
- Marcações herdadas do relógio consideram regras de autenticação facial e cerca virtual.

---

## 3. Tela `Tratamento de Ponto` — referência da imagem 1

### 3.1 Estrutura visual
- Breadcrumb: `Início > Tratamento de Ponto`
- Título: `Tratamento de Ponto`
- Subtítulo: `Visualize, audite e corrija marcações de ponto dos colaboradores`
- Ações no topo direito:
  - toggle `Apenas pendências`
  - botão `Ver Pendências`

### 3.2 Filtros
- `Período` (mês/ano; ex.: `março de 2026`)
- `Buscar colaborador...`
- checkbox `Apenas com inconsistências`
- checkbox `Apenas com pendências`

### 3.3 Tabela de colaboradores
Colunas:
- `Colaborador`
- `Cargo`
- `Saldo BH`
- `HE 50%`
- `HE 100%`
- `Atrasos`
- `Faltas`
- `Pendências`
- ação `Ver Espelho`

Estado com dados (conforme referência):
- linha do colaborador com métricas resumidas e link para espelho.
- paginação no rodapé (ex.: `Página 1 de 1 • 1 item no total`).

---

## 4. Tela `Espelho de Ponto` — referências das imagens 2 a 7

### 4.1 Cabeçalho do espelho
- Breadcrumb: `Início > Tratamento de Ponto > Espelho de Ponto`
- Título: `Espelho de Ponto`
- Nome do colaborador e cargo
- Período (ex.: `01/03/2026 - 31/03/2026`) + badge de estado (`Aberto`)
- Ações:
  - `Voltar`
  - `Ajuste Automático`

### 4.2 Cards de indicadores
Indicadores exibidos:
- `Saldo BH`
- `HE 50%`
- `HE 100%`
- `Atrasos`
- `S. Antec` (saídas antecipadas)
- `Faltas`
- `Ad. Noturno`
- `Total Trabalhado`
- `Total Previsto`

### 4.3 Legenda operacional de marcações
Exibir visualmente os chips da seção 2.2:
- `Original (AFD)`
- `A ser adicionada`
- `Adicionada (Pendente)`
- `Adicionada (Aprovada)`
- `Adicionada (Rejeitada)`
- `Desconsiderada`
- `Fora da cerca virtual`

### 4.4 Grade diária (tabela principal)
Colunas:
- `Data/Dia`
- `Jornada Prevista`
- `Marcações`
- `Total/Saldo`
- `Saldo`
- `Ocorrências`
- `Ações` (`Editar`)

Estados observados nas referências:
- dia sem jornada prevista (ex.: domingo) com saldo neutro (`+0min`).
- dia útil com jornada prevista e `Sem marcações`, gerando saldo negativo (ex.: `-8h30`).
- dia com marcação única e ocorrência `Falta saída` (linha destacada em tom de alerta).
- ação `Editar` disponível em cada linha para tratamento manual.

### 4.5 Semântica visual das linhas
- Fundo neutro/cinza: dia sem jornada aplicável ou sem impacto relevante.
- Fundo amarelo/claro: inconsistência de jornada (ex.: ausência de marcações em dia útil).
- Fundo avermelhado/claro: pendência crítica que exige ação (ex.: `Falta saída`).
- Indicador lateral colorido reforça o tipo de estado da linha.

---

## 5. Fluxos operacionais

### 5.1 Da listagem para o espelho
- Usuário clica em `Ver Espelho` na linha do colaborador.
- Sistema abre espelho no período/filtros ativos.

### 5.2 Editar dia
- Clique em `Editar` abre interface de ajuste do dia.
- Ajustes devem registrar status (`pendente`, `aprovada`, `rejeitada`, `desconsiderada`) conforme política de aprovação.

### 5.3 Ajuste automático
- `Ajuste Automático` aplica regras automáticas configuradas para reduzir inconsistências recorrentes.
- Deve retornar resumo de dias afetados e manter trilha de auditoria.

### 5.4 Ver pendências
- `Ver Pendências` filtra visão para eventos com necessidade de ação imediata.

---

## 6. Regras de cálculo e validação (MVP)

### 6.1 Cálculo diário
- `saldo_dia = horas_trabalhadas - horas_previstas`.
- Dia útil sem marcações:
  - `horas_trabalhadas = 0`
  - saldo tende a negativo (conforme carga diária prevista, ex.: `-8h30`).

### 6.2 Falta de saída
- Quando a sequência de marcações do dia estiver incompleta (quantidade ímpar), gerar ocorrência `Falta saída`.
- Dia permanece pendente até ajuste/manual ou política automática.

### 6.3 Horas e acumuladores
- `HE 50%` e `HE 100%` dependem da política de jornada da empresa.
- `Saldo BH` é acumulado no período considerando aprovações/rejeições de ajustes.

### 6.4 Fora da cerca virtual
- Marcação fora da cerca virtual recebe tag específica.
- Tratamento pode exigir justificativa/decisão conforme política do tenant.

---

## 7. Catálogo de mensagens

Mensagens de estado:
- `Sem marcações`
- `Falta saída`
- `Nenhuma pendência encontrada para os filtros aplicados.`
- `Espelho de ponto carregado com sucesso.`

Mensagens de operação:
- `Ajuste aplicado com sucesso.`
- `Ajuste enviado para aprovação.`
- `Ajuste aprovado com sucesso.`
- `Ajuste rejeitado.`
- `Ajuste desconsiderado com sucesso.`
- `Ajuste automático concluído.`
- `Não foi possível concluir o ajuste automático.`

Mensagens de validação:
- `Informe um período válido.`
- `Colaborador não encontrado para este tenant.`
- `Não é possível editar período fechado.`
- `Dados de marcação inválidos para este dia.`

---

## 8. Contrato de payload/API (MVP)

### 8.1 Listagem de tratamento (resumo por colaborador)
Endpoint:
- `GET /api/tratamento-ponto/colaboradores/`

Query params:
- `period=YYYY-MM`
- `q`
- `only_inconsistencies=true|false`
- `only_pendencias=true|false`
- `page`
- `page_size`

Response `200` exemplo:

```json
{
  "count": 1,
  "results": [
    {
      "employee_id": 123,
      "nome": "FRANCISCO MARCIO GADELHA PAES",
      "cargo": "Supervisor de Grupo de Costura",
      "saldo_bh_min": 0,
      "he_50_min": 0,
      "he_100_min": 0,
      "atrasos_min": 0,
      "faltas_dias": 0,
      "pendencias_count": 1
    }
  ]
}
```

### 8.2 Espelho por colaborador/período
Endpoint:
- `GET /api/tratamento-ponto/espelho/{employee_id}/?period=2026-03`

Response `200` exemplo (resumo):

```json
{
  "employee": {
    "id": 123,
    "nome": "FRANCISCO MARCIO GADELHA PAES",
    "cargo": "Supervisor de Grupo de Costura"
  },
  "periodo": {
    "inicio": "2026-03-01",
    "fim": "2026-03-31",
    "status": "ABERTO"
  },
  "indicadores": {
    "saldo_bh_min": 0,
    "he_50_min": 0,
    "he_100_min": 0,
    "atrasos_min": 0,
    "saidas_antecipadas_min": 0,
    "faltas_dias": 0,
    "adicional_noturno_min": 0,
    "total_trabalhado_min": 0,
    "total_previsto_min": 10200
  },
  "dias": []
}
```

### 8.3 Editar marcações do dia
Endpoint:
- `POST /api/tratamento-ponto/espelho/{employee_id}/dias/{date}/ajustes/`

Request exemplo:

```json
{
  "acao": "ADICIONAR_MARCACAO",
  "hora": "13:33",
  "motivo": "Correção operacional"
}
```

Response `201` exemplo:

```json
{
  "ajuste_id": "f89f329d-8cd4-4ff6-a95f-9f67fbbce0f9",
  "status": "PENDENTE",
  "date": "2026-03-08"
}
```

### 8.4 Ajuste automático do espelho
Endpoint:
- `POST /api/tratamento-ponto/espelho/{employee_id}/ajuste-automatico/`

Request exemplo:

```json
{
  "periodo_inicio": "2026-03-01",
  "periodo_fim": "2026-03-31"
}
```

Response `200` exemplo:

```json
{
  "processed_days": 31,
  "updated_days": 3,
  "pendencias_restantes": 1
}
```

### 8.5 Erros esperados
- `400` parâmetros inválidos (período, data, payload de ajuste).
- `404` colaborador não encontrado no tenant.
- `409` tentativa de ajuste em período fechado.
- `422` ajuste inconsistente com regra do dia/jornada.

---

## 9. Critérios de aceite da área

- Tela `Tratamento de Ponto` renderiza conforme referência (filtros, tabela e ações).
- `Ver Espelho` abre o espelho do colaborador no período selecionado.
- Espelho exibe cards de indicadores, legenda e tabela diária com estados visuais.
- Dias com `Sem marcações` em jornada prevista refletem saldo negativo diário.
- Ocorrência `Falta saída` é exibida e tratável via `Editar`.
- `Ajuste Automático` processa período aberto com retorno de resultado.
- Fluxo mantém isolamento por tenant e trilha auditável dos ajustes.
