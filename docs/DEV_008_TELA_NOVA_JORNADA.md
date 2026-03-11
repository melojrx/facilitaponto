# DEV-008 — Especificação da Tela `Nova Jornada de Trabalho`
**Versão:** 1.2  
**Data:** 2026-03-11  
**Contexto:** onboarding pós-cadastro de empresa (etapa `Criar jornada`)  
**Referências:** `docs/DEV_008_ONBOARDING_MODELAGEM.md`, `docs/DEV_ROADMAP.md`, mock visual aprovado

---

## Papel deste documento

- Este arquivo descreve a especificação funcional/visual da tela `Nova Jornada de Trabalho`.
- O acompanhamento de implementação e pendências fica em `docs/DEV_008_CHECKLIST.md`.
- O status macro do bloco e suas dependências ficam em `docs/DEV_008_ONBOARDING_MODELAGEM.md`.

## Status de implementação (2026-03-11)

- A tela está entregue no núcleo funcional do onboarding.
- Permanecem fora do aceite fechado do `DEV-008`:
  - aderência visual final `1:1` com o layout aprovado
  - catálogo completo de estados de interação e mensagens
- Este documento deve ser mantido como especificação-alvo, não como controle de sprint.

## 1. Objetivo da tela

Permitir o cadastro da primeira jornada da empresa durante o onboarding, no padrão visual do painel, destravando os módulos seguintes após sucesso.

Rota alvo (MVP):
- `GET /painel/jornadas/nova/`
- `POST /painel/jornadas/nova/`

---

## 2. Estrutura visual 1:1 (desktop)

### 2.1 Shell da página
- Sidebar fixa à esquerda com o menu principal.
- Topbar fixa no topo com seletor de empresa ao centro e ações no canto direito.
- Conteúdo principal com largura fluida e margens internas padrão do painel.

### 2.2 Breadcrumb (linha superior de contexto)
Formato:
- `Início > {nome_empresa_ou_conta} > Jornadas de Trabalho > Nova Jornada de Trabalho`

Comportamento:
- Itens intermediários navegáveis, último item não clicável.

### 2.3 Cabeçalho da página
- Título: `Nova Jornada de Trabalho`
- Subtítulo: `Gerencie os templates de jornada da empresa`
- Ícone à esquerda do título (relógio/calendário, conforme design system atual).

### 2.4 Card principal do formulário

Bloco superior interno:
- Título repetido: `Nova Jornada de Trabalho`
- Texto auxiliar: `Gerencie os templates de jornada da empresa`

Campo 1:
- Label: `Nome da Jornada`
- Tipo: texto simples (linha única)
- Placeholder: `Ex: Jornada Padrão 44h`

Campo 2:
- Label: `Descrição`
- Tipo: textarea (opcional)
- Placeholder: `Descrição opcional da jornada`

Campo 3:
- Label: `Tipo de Jornada` + ícone de ajuda
- Grupo de 4 cards de seleção única (radio-card):
  - `Semanal`
  - `12x36`
  - `Fracionada`
  - `Externa`

Texto descritivo de cada card:
- `Semanal`: `Horários fixos por dia da semana. Ideal para CLT padrão.`
- `12x36`: `12h trabalho, 36h descanso. Comum em saúde e segurança.`
- `Fracionada`: `Múltiplos períodos por dia. Comum em restaurantes e escolas.`
- `Externa`: `Ponto livre, sem horário fixo. Para vendedores externos.`

Bloco informativo inferior (dentro do card):
- Título: `Selecione o tipo de jornada`
- Texto: `A jornada de trabalho define os horários esperados do colaborador. Com ela, o sistema consegue automatizar diversos controles.`

### 2.5 Ações de rodapé
- Botão secundário: `Cancelar`
- Botão primário: `Salvar Jornada`
- Posição: canto inferior direito da área de conteúdo (fora do card principal, alinhado ao layout do painel).

### 2.6 Conteúdo exibido ao selecionar `Semanal`

Após selecionar o card `Semanal`, a tela expande e exibe blocos adicionais nesta ordem:

1. Painel `O que o sistema faz com a jornada` com 6 bullets:
   - `Notifica marcações pendentes quando o colaborador esquece de bater o ponto`
   - `Controla horas extras e alerta quando ultrapassar o limite de 2h/dia (CLT)`
   - `Gera o espelho de ponto com saldo diário (horas trabalhadas vs. esperadas)`
   - `Calcula atrasos e saídas antecipadas automaticamente`
   - `Valida intervalos intrajornada obrigatórios (1h para jornadas acima de 6h)`
   - `Processa o banco de horas automaticamente com base na carga horária`
2. Bloco colapsável `Dúvidas comuns` (accordion).
3. Bloco `Selecione o tipo de jornada` com atalhos:
   - `Integral 44h`
   - `Comercial 40h`
   - `Parcial 30h`
   - `Personalizar`
4. Bloco `Jornada de Trabalho` com texto de apoio operacional.
5. Toggle global: `Intervalo reduzido por convenção coletiva`.
6. Grade semanal por dia (segunda a domingo) com campos de horário (`--:--`) e controle de DSR.

Estrutura mínima da grade semanal por linha (dia):
- coluna `Dia da semana`
- `Entrada 1`
- `Saída 1`
- `Entrada 2` (quando houver intervalo)
- `Saída 2` (quando houver intervalo)
- controle de `DSR (Descanso Semanal Remunerado)` para o dia.

### 2.7 Conteúdo exibido ao selecionar `12x36`

Após selecionar o card `12x36`, a tela expande e exibe blocos adicionais nesta ordem:

1. Painel `O que o sistema faz com a jornada` (mesmo padrão visual dos demais tipos).
2. Bloco colapsável `Dúvidas comuns`.
3. Bloco `Jornada de Trabalho` com configuração da escala:
   - `Data de Início da Escala`
   - `Horário de Entrada`
4. Ação `Gerar/Atualizar escala`.
5. Grade de prévia da escala gerada por dia com:
   - dia da semana
   - status (`Dia de Trabalho` ou `Folga`)
   - horário de entrada
   - horário de saída.

Observação visual:
- Dias de `Folga` devem aparecer sem horários definidos (`-`), conforme referência.

### 2.8 Conteúdo exibido ao selecionar `Fracionada`

Após selecionar o card `Fracionada`, a tela expande e exibe blocos adicionais nesta ordem:

1. Painel `O que o sistema faz com a jornada`.
2. Bloco colapsável `Dúvidas comuns`.
3. Bloco `Jornada de Trabalho` com texto orientativo para múltiplos períodos no dia.
4. Toggle global `Intervalo reduzido por convenção coletiva`.
5. Blocos por dia da semana contendo:
   - cabeçalho do dia com total de horas do dia
   - lista de períodos (`Período 1`, `Período 2`, ...)
   - campos `início` e `fim` por período
   - ação de remover período
   - ação `Adicionar Período`
   - ação `Copiar horários para os demais dias`.

### 2.9 Conteúdo exibido ao selecionar `Externa`

Após selecionar o card `Externa`, a tela expande e exibe blocos adicionais nesta ordem:

1. Mensagem de alerta (tom de aviso):
   - `Jornada externa não deve ter horários definidos`
2. Card informativo `Jornada Externa`:
   - descreve que o colaborador registra ponto livremente
   - informa que o sistema não valida horários fixos, apenas registra marcações.
3. Bloco colapsável `Dúvidas comuns`.

Comportamento:
- Campos de configuração de horário/escala não devem ser exibidos para esse tipo.

---

## 3. Comportamento responsivo (mobile)

- Sidebar vira drawer colapsável.
- Breadcrumb pode quebrar linha.
- Cards de tipo de jornada empilham em 1 coluna.
- Botões de ação permanecem no fim da página, em largura total quando necessário.
- Áreas clicáveis devem manter altura mínima confortável (>= 44px).

---

## 4. Estados da interface

### 4.1 Estado inicial (pristine)
- Campos vazios.
- Nenhum tipo selecionado.
- Exibir bloco informativo de ajuda.
- `Salvar Jornada` inicia desabilitado até os obrigatórios estarem válidos.

### 4.2 Estado de foco/edição
- Campo focado com destaque visual de borda.
- Card em hover/focus com realce sutil.
- Teclado:
  - `Tab` percorre campos e cards
  - `Space/Enter` seleciona card focado.

### 4.3 Estado selecionado (tipo de jornada)
- Apenas um card pode estar selecionado por vez.
- Card selecionado ganha:
  - borda de destaque
  - fundo sutil
  - ícone/título com cor ativa.

### 4.4 Estado inválido
- Campo com erro recebe borda de erro.
- Mensagem de erro mostrada abaixo do campo.
- Resumo de erro opcional no topo do card se houver múltiplos erros.

### 4.5 Estado enviando (submitting)
- `Salvar Jornada` entra em loading e bloqueia múltiplos cliques.
- `Cancelar` fica desabilitado enquanto submit está em andamento.

### 4.6 Estado sucesso
- Mostrar feedback: `Jornada criada com sucesso.`
- Avançar onboarding (`onboarding_step = 3`).
- Redirecionar para `/painel` com menu liberado conforme regra.

### 4.7 Estado erro de servidor
- Mensagem global no formulário sem perder dados digitados.
- Reabilitar botões após retorno de erro.

### 4.8 Estado `Semanal` ativo
- Exibir os blocos adicionais descritos na seção 2.6.
- Atalho selecionado (`Integral 44h`, `Comercial 40h`, `Parcial 30h` ou `Personalizar`) recebe destaque visual.
- Atalhos de carga horária podem autopreencher a grade semanal.
- `Personalizar` mantém/limpa grade para edição manual.
- Linha marcada como DSR desabilita campos de horário daquele dia.
- Quando intervalo não for usado no dia, `Entrada 2/Saída 2` permanecem ocultos ou desabilitados (conforme implementação final do componente).

### 4.9 Estado `12x36` ativo
- Exibir blocos adicionais descritos na seção 2.7.
- Exigir `Data de Início da Escala` e `Horário de Entrada` antes de gerar escala.
- Ao acionar `Gerar/Atualizar escala`, preencher grade alternando `Dia de Trabalho` e `Folga`.
- Em `Dia de Trabalho`, exibir janela esperada de 12 horas contínuas.
- Em `Folga`, manter horários vazios.

### 4.10 Estado `Fracionada` ativo
- Exibir blocos adicionais descritos na seção 2.8.
- Cada dia pode conter múltiplos períodos ordenados.
- Botão `Adicionar Período` cria novo par início/fim no dia.
- Ação `Copiar horários para os demais dias` replica a configuração do dia de origem.
- Total de horas por dia atualiza após qualquer alteração.

### 4.11 Estado `Externa` ativo
- Exibir somente alerta + card informativo + `Dúvidas comuns`.
- Ocultar/neutralizar campos de horário e geração de escala.
- Manter mensagem de aviso visível enquanto `Externa` estiver selecionada.

---

## 5. Validações

### 5.1 Regras de front-end
- `nome_jornada`:
  - obrigatório
  - trim antes de validar/salvar
  - mínimo de 3 caracteres úteis
  - máximo de 80 caracteres
- `descricao`:
  - opcional
  - máximo de 255 caracteres
- `tipo_jornada`:
  - obrigatório
  - valores permitidos: `SEMANAL`, `12X36`, `FRACIONADA`, `EXTERNA`

### 5.2 Regras de back-end
- Revalidar todas as regras do front.
- Garantir que a jornada pertence ao tenant do usuário autenticado.
- Bloquear duplicidade de nome por tenant (case-insensitive).
- Retornar erro semântico padronizado em conflitos de negócio.

### 5.3 Regras específicas para `Semanal`
- Deve existir pelo menos 1 dia útil com horário válido (não DSR).
- Formato de horário obrigatório: `HH:MM` (24h).
- Para dia útil:
  - `Entrada 1` e `Saída 1` obrigatórios.
  - `Entrada 1 < Saída 1`.
- Quando houver segundo período:
  - `Entrada 2` e `Saída 2` obrigatórios em par.
  - `Saída 1 <= Entrada 2 < Saída 2`.
- Não permitir sobreposição de intervalos no mesmo dia.
- Se `DSR` ativo no dia:
  - horários do dia não devem ser persistidos como jornada ativa.
- Se `intervalo_reduzido_convencao = true`:
  - exigir indicação de base legal no payload complementar (`norma_coletiva_ref`) em implementações que ativarem essa regra.

### 5.4 Regras específicas para `12x36`
- `data_inicio_escala` obrigatória.
- `horario_entrada` obrigatório e válido (`HH:MM`).
- Duração padrão de turno de trabalho: 12 horas.
- Padrão de escala deve alternar `trabalho` e `folga` em ciclos de 48h (12h + 36h).
- Não permitir configuração manual de horário em dias marcados como `folga`.
- A grade deve ser regenerável sem duplicar linhas.

### 5.5 Regras específicas para `Fracionada`
- Cada dia deve possuir zero ou mais períodos válidos.
- Quando existir período, par `início/fim` é obrigatório.
- Todos os períodos do dia devem estar em ordem crescente.
- Períodos não podem se sobrepor.
- Não permitir período com duração zero ou negativa.
- Se `copiar horários para os demais dias` for acionado, replicar períodos mantendo consistência do total diário.

### 5.6 Regras específicas para `Externa`
- Não permitir persistência de horários fixos no template.
- Se payload chegar com horários para `EXTERNA`, rejeitar com erro semântico.
- Regras de atraso/saída antecipada baseadas em horário esperado não devem ser aplicadas.

---

## 6. Semântica negocial por tipo de jornada

### 6.1 `Semanal`
- Representa jornada fixa por dia da semana.
- Sistema compara marcações realizadas com horários esperados.
- Habilita cálculo de:
  - atrasos
  - saídas antecipadas
  - horas extras diárias
  - saldo de banco de horas por dia/período.

### 6.2 `12x36`
- Representa escala cíclica com alternância automática:
  - 12 horas de trabalho
  - 36 horas de descanso.
- A lógica de presença esperada é definida pela escala gerada a partir de data/hora base.
- Em dias `Folga`, marcações eventuais podem ser tratadas como exceção operacional para análise de horas.

### 6.3 `Fracionada`
- Representa jornada com múltiplos períodos no mesmo dia.
- A aderência é validada por período, não apenas por carga diária total.
- Intervalos intrajornada são derivados dos espaços entre períodos configurados.
- Indicado para operações com pausas longas ou mais de dois blocos diários.

### 6.4 `Externa`
- Representa atividade sem horário contratual fixo controlado pelo sistema.
- Objetivo principal: registrar marcações e manter rastreabilidade.
- O sistema não aplica validação de pontualidade por grade esperada.
- Tratamentos de conformidade e ajustes devem ocorrer por política da empresa e rotinas de tratamento de ponto.

---

## 7. Catálogo de mensagens (UI)

Mensagens de validação de campo:
- `Informe o nome da jornada.`
- `O nome da jornada deve ter pelo menos 3 caracteres.`
- `O nome da jornada deve ter no máximo 80 caracteres.`
- `A descrição deve ter no máximo 255 caracteres.`
- `Selecione um tipo de jornada.`
- `Informe pelo menos um dia de trabalho com horários válidos.`
- `Preencha Entrada 1 e Saída 1 para os dias trabalhados.`
- `Horário inválido. Use o formato HH:MM.`
- `A saída deve ser maior que a entrada no mesmo período.`
- `Os períodos do dia não podem se sobrepor.`
- `Informe a data de início da escala 12x36.`
- `Informe o horário de entrada da escala 12x36.`
- `Não é permitido definir horários para jornada externa.`

Mensagens de negócio/API:
- `Já existe uma jornada com este nome na sua empresa.`
- `Não foi possível salvar a jornada. Tente novamente.`
- `Sua sessão expirou. Faça login novamente.`
- `Você não tem permissão para cadastrar jornada nesta empresa.`
- `Não foi possível aplicar o modelo de jornada selecionado. Revise os horários e tente novamente.`
- `Não foi possível gerar a escala 12x36 com os parâmetros informados.`
- `Não foi possível copiar os períodos para os demais dias. Revise os horários.`

Mensagem de sucesso:
- `Jornada criada com sucesso.`

Tooltip de bloqueio de menu (quando aplicável no onboarding):
- `Conclua o cadastro da primeira jornada para liberar este módulo.`

---

## 8. Contrato de payload (MVP)

Request (`POST /painel/jornadas/nova/`):

```json
{
  "nome_jornada": "Jornada Padrão 44h",
  "descricao": "Segunda a sexta com intervalo padrão",
  "tipo_jornada": "SEMANAL"
}
```

Request sugerido para `tipo_jornada = SEMANAL`:

```json
{
  "nome_jornada": "Jornada Comercial 40h",
  "descricao": "Segunda a sexta, com intervalo",
  "tipo_jornada": "SEMANAL",
  "subtipo_semanal": "COMERCIAL_40H",
  "intervalo_reduzido_convencao": false,
  "dias": [
    {
      "dia_semana": "SEGUNDA",
      "dsr": false,
      "entrada_1": "08:00",
      "saida_1": "12:00",
      "entrada_2": "13:00",
      "saida_2": "17:00"
    }
  ]
}
```

Request sugerido para `tipo_jornada = 12X36`:

```json
{
  "nome_jornada": "Plantão Enfermagem 12x36",
  "descricao": "Escala contínua de plantão",
  "tipo_jornada": "12X36",
  "data_inicio_escala": "2026-03-08",
  "horario_entrada": "08:00"
}
```

Request sugerido para `tipo_jornada = FRACIONADA`:

```json
{
  "nome_jornada": "Restaurante Fracionada",
  "descricao": "Almoço e jantar",
  "tipo_jornada": "FRACIONADA",
  "intervalo_reduzido_convencao": false,
  "dias": [
    {
      "dia_semana": "SEGUNDA",
      "periodos": [
        { "inicio": "08:00", "fim": "12:00" },
        { "inicio": "14:00", "fim": "18:00" }
      ]
    }
  ]
}
```

Request sugerido para `tipo_jornada = EXTERNA`:

```json
{
  "nome_jornada": "Equipe Comercial Externa",
  "descricao": "Sem horário fixo",
  "tipo_jornada": "EXTERNA"
}
```

Response de sucesso:
- HTTP `201` com id da jornada criada.

Response de erro:
- HTTP `400` para validações de campo.
- HTTP `409` para duplicidade de nome no mesmo tenant.
- HTTP `401/403` para sessão/permissão.

---

## 9. Critérios de aceite da tela

- Tela renderiza fiel ao layout aprovado (breadcrumb, cabeçalho, card principal, 4 cards de tipo e ações).
- Ao selecionar `Semanal`, a tela expande com os blocos adicionais no mesmo padrão visual da referência.
- Ao selecionar `12x36`, a tela expande com campos de início/entrada e geração de escala com dias de trabalho/folga.
- Ao selecionar `Fracionada`, a tela expande com edição de múltiplos períodos por dia e ações de copiar/adicionar.
- Ao selecionar `Externa`, a tela exibe aviso negocial e não permite horários fixos.
- `Salvar Jornada` só habilita quando campos obrigatórios estiverem válidos.
- Seleção de tipo funciona em clique e teclado, com estado visual claro.
- Atalhos (`Integral 44h`, `Comercial 40h`, `Parcial 30h`, `Personalizar`) funcionam e refletem na grade semanal.
- Regras negociais de cada tipo são respeitadas pelo cálculo e validação do ponto.
- Mensagens de validação e negócio seguem exatamente o catálogo desta especificação.
- Em sucesso, jornada é criada no tenant correto e onboarding avança para liberar os próximos módulos.
