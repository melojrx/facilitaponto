# DEV-008 — Especificação da Área Relatórios
**Versão:** 1.0  
**Data:** 2026-03-08  
**Contexto:** módulo `Relatórios` no painel web  
**Referências:** `docs/DEV_008_ONBOARDING_MODELAGEM.md`, `docs/PRD.md`, mocks visuais aprovados

---

## 1. Objetivo

Documentar o módulo `Relatórios` com base nas telas de referência:

- página índice com cards de relatórios
- formulário de relatório `Espelho de Ponto`
- formulário de relatório `Cartão de Ponto`
- formulário de relatório `Detalhes dos Cálculos`

Rotas alvo (MVP):
- `GET /painel/relatorios/`
- `GET /painel/relatorios/espelho-ponto/`
- `GET /painel/relatorios/cartao-ponto/`
- `GET /painel/relatorios/detalhes-calculos/`

---

## 2. Semântica negocial

### 2.1 Papel do módulo
- Centraliza geração de relatórios operacionais e de conferência.
- Deve permitir recorte por período e colaborador.
- Exportação padrão em PDF.

### 2.2 Tipos de relatório
- `Espelho de Ponto`:
  - relatório completo das marcações de ponto.
- `Cartão de Ponto`:
  - visão resumida de horas trabalhadas, extras e descontos.
- `Detalhes dos Cálculos`:
  - memória de cálculo com explicação detalhada e base legal.

---

## 3. Tela `Relatórios` (índice) — referência da imagem 1

### 3.1 Estrutura visual
- Breadcrumb: `Relatórios`
- Título: `Relatórios`
- Subtítulo: `Gere relatórios da sua empresa`
- Bloco introdutório `Gere relatórios da sua empresa`

### 3.2 Cards de entrada
Cards exibidos:
- `Espelho de Ponto` + CTA `Gerar Relatório`
- `Cartão de Ponto` + CTA `Gerar Relatório`
- `Detalhes dos Cálculos` + CTA `Gerar Relatório`

Comportamento:
- cada CTA direciona para o formulário do relatório correspondente.

---

## 4. Tela `Espelho de Ponto` (relatório) — referência da imagem 2

### 4.1 Estrutura
- Breadcrumb: `Relatórios > Espelho de Ponto`
- Título: `Espelho de Ponto`
- Subtítulo: `Relatório completo das marcações de ponto dos colaboradores`
- Botão de navegação: `Voltar para Relatórios`
- Card de filtros `Período`

### 4.2 Campos do filtro
- `Seleção Rápida por Mês` (select)
- `Data Inicial`
- `Data Final`
- `Colaborador` (select, padrão `Todos os colaboradores`)

### 4.3 Ações
- `Baixar PDF`

Estado:
- botão inicia desabilitado enquanto não houver filtro válido e relatório gerado.

---

## 5. Tela `Cartão de Ponto` (relatório) — referência da imagem 3

### 5.1 Estrutura e campos
- Mesma estrutura funcional da tela de `Espelho de Ponto`.
- Mudança principal: título/subtítulo para `Cartão de Ponto`.

### 5.2 Semântica de saída
- Documento resumido para conferência de horas, extras e descontos no período.

---

## 6. Tela `Detalhes dos Cálculos` — referência da imagem 4

### 6.1 Estrutura
- Breadcrumb: `Relatórios > Detalhes dos Cálculos`
- Título: `Detalhes dos Cálculos`
- Subtítulo: `Veja como cada valor foi calculado com embasamento legal completo`
- Botão de navegação: `Voltar para Relatórios`
- Card de filtros com período e colaborador.

### 6.2 Campos adicionais
- Segmentação do modo:
  - `Por Dia`
  - `Consolidado`

### 6.3 Ações
- `Gerar Relatório`
- `Baixar PDF`

Comportamento:
- `Gerar Relatório` cria versão calculada para o filtro selecionado.
- `Baixar PDF` habilita após geração bem-sucedida.

---

## 7. Regras de validação (MVP)

- Deve informar período por seleção rápida de mês ou por datas manuais.
- Se datas manuais forem usadas:
  - `data_inicial` obrigatória
  - `data_final` obrigatória
  - `data_final >= data_inicial`
- `colaborador` opcional (`Todos` por padrão).
- Em `Detalhes dos Cálculos`, `modo` obrigatório (`POR_DIA` ou `CONSOLIDADO`).

---

## 8. Contrato de payload/API (MVP)

### 8.1 Gerar relatório de espelho
Endpoint:
- `POST /api/relatorios/espelho-ponto/gerar/`

Request exemplo:

```json
{
  "periodo_inicio": "2026-03-01",
  "periodo_fim": "2026-03-31",
  "employee_id": null
}
```

### 8.2 Gerar relatório de cartão
Endpoint:
- `POST /api/relatorios/cartao-ponto/gerar/`

Request exemplo:

```json
{
  "periodo_inicio": "2026-03-01",
  "periodo_fim": "2026-03-31",
  "employee_id": 123
}
```

### 8.3 Gerar relatório de detalhes dos cálculos
Endpoint:
- `POST /api/relatorios/detalhes-calculos/gerar/`

Request exemplo:

```json
{
  "periodo_inicio": "2026-03-01",
  "periodo_fim": "2026-03-31",
  "employee_id": 123,
  "modo": "CONSOLIDADO"
}
```

### 8.4 Resposta de geração
Response `200` exemplo:

```json
{
  "report_id": "998dc7d6-c289-4fab-af57-b0a3f4defddd",
  "status": "READY",
  "download_url": "/api/relatorios/download/998dc7d6-c289-4fab-af57-b0a3f4defddd/"
}
```

### 8.5 Download
Endpoint:
- `GET /api/relatorios/download/{report_id}/`

Resultado:
- stream de PDF com headers de download.

### 8.6 Erros esperados
- `400` período inválido ou payload incompleto.
- `404` colaborador não encontrado no tenant.
- `409` relatório não disponível para download (não gerado/falha de processamento).

---

## 9. Catálogo de mensagens

Mensagens de validação:
- `Selecione um período para gerar o relatório.`
- `Data final deve ser maior ou igual à data inicial.`
- `Selecione o modo de visualização para detalhes dos cálculos.`

Mensagens de operação:
- `Relatório gerado com sucesso.`
- `Baixando PDF...`
- `Não foi possível gerar o relatório. Tente novamente.`
- `Não foi possível baixar o PDF.`

---

## 10. Critérios de aceite

- Tela índice de `Relatórios` renderiza os 3 cards e CTAs conforme referência.
- Cada card abre o formulário correto com breadcrumb e botão `Voltar para Relatórios`.
- Filtros de período/colaborador são respeitados na geração.
- `Detalhes dos Cálculos` suporta modos `Por Dia` e `Consolidado`.
- `Baixar PDF` só habilita após geração válida.
- Isolamento por tenant garantido na geração/download.
