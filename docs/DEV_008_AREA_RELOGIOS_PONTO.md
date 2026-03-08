# DEV-008 — Especificação da Área Relógios de Ponto
**Versão:** 1.5  
**Data:** 2026-03-08  
**Contexto:** módulo `Relógio Digital` no painel web (após liberação do onboarding)  
**Referências:** `docs/DEV_008_ONBOARDING_MODELAGEM.md`, `docs/PRD.md`, mocks visuais aprovados

---

## 1. Objetivo

Documentar o fluxo do módulo `Relógios de Ponto` com base nas telas de referência:

- listagem inicial (sem relógios)
- criação de relógio
- listagem após criação (card do relógio)
- detalhe do relógio (`Gerenciar`) com abas `Informações` e `Colaboradores`

Rotas alvo (MVP):
- `GET /painel/relogios/`
- `GET|POST /painel/relogios/novo/`
- `GET /painel/relogios/{id}/`

---

## 2. Semântica negocial

### 2.1 O que é um relógio de ponto no sistema
- Entidade lógica que representa um ponto de marcação (app/tablet/computador) vinculado ao tenant.
- Cada relógio possui:
  - identificação (`nome`, `descrição`)
  - tipo de REP (no MVP: `REP-P`)
  - status operacional (`Ativo`/`Inativo`/`Em Manutenção`)
  - código de ativação para pareamento do dispositivo.

### 2.2 Código de ativação
- Código curto exibido no card do relógio para ativação no app do relógio digital.
- Deve ser único por relógio e regenerável em caso de segurança/rotatividade.
- Sem código válido, o dispositivo não deve conseguir se vincular ao relógio.

### 2.3 Métodos de autenticação suportados
- No escopo atual do produto, o relógio suporta apenas:
  - `Reconhecimento Facial`
- O método é fixo no cadastro/edição e não pode ser alterado para outro fator.

### 2.4 Relação com colaboradores
- Após criar o relógio, colaboradores podem ser atribuídos a ele.
- Sem colaboradores atribuídos, relógio permanece válido, porém sem operação de batida por usuário vinculado.
- A aba `Colaboradores` do detalhe do relógio é o ponto oficial de vinculação/desvinculação em lote.

### 2.5 Regra de negócio do banner (fluxo operacional fim-a-fim)
Sequência oficial do produto:
1. Empresa acessa `app.useponto.com.br` e instala/abre o app do relógio digital em celular, tablet ou computador.
2. No painel web, cria o relógio e ativa o dispositivo usando o `código de ativação`.
3. No painel web, adiciona os colaboradores ao relógio na aba `Colaboradores`.
4. Colaborador já atribuído e elegível realiza a batida de ponto no dispositivo ativado.

Premissas obrigatórias:
- Dispositivo só opera se relógio estiver `ATIVO`.
- Colaborador só bate ponto no relógio se estiver atribuído ao relógio e `ATIVO`.
- Autenticação no relógio é exclusivamente facial (`FACIAL`).

---

## 3. Tela `Relógios de Ponto` (listagem inicial) — referência da imagem 1

### 3.1 Estrutura visual
- Breadcrumb: `Início > Relógios de Ponto`
- Cabeçalho:
  - título `Relógios de Ponto`
  - subtítulo `Listar Relógios`
  - ações no canto superior direito:
    - `Exportar AFD`
    - `+ Criar Relógio`

### 3.2 Banner informativo
Texto orientativo com passos:
1. Criar relógio e ativar com código de ativação.
2. Adicionar colaboradores ao relógio.
3. Colaboradores podem bater o ponto.

### 3.3 Filtros da listagem
- Busca: `Buscar por nome ou descrição`
- Select `Status` (padrão `Todos`)
- Select `Tipo de REP` (padrão `Todos`)

### 3.4 Estado vazio
- Mensagem central: `Nenhum resultado encontrado`
- CTA `Criar Relógio` permanece visível no cabeçalho.

---

## 4. Tela `Criar Relógio` — referência da imagem 2

### 4.1 Estrutura
- Breadcrumb: `Início > Relógios de Ponto > Criar Relógio`
- Título: `Criar Relógio`
- Seção `Informações básicas` com campos:
  - `Nome do Relógio` (obrigatório)
  - `Descrição` (opcional)
  - `Tipo do Relógio` (ex.: `Aplicativo`)
  - `Status` (`Ativo`/`Inativo`/`Em Manutenção`, padrão `Ativo`)
  - `Método de Autenticação Suportado` (fixo)
    - `Reconhecimento Facial` (somente leitura/selecionado)
- Ações: `Cancelar` e `Salvar`

### 4.2 Validações da criação
- `Nome do Relógio` obrigatório (mín. 3 caracteres, máx. 80).
- Nome único por tenant (case-insensitive).
- Método de autenticação obrigatoriamente `Reconhecimento Facial`.
- Tipo de relógio obrigatório.
- `Status` deve estar no domínio permitido (`ATIVO|INATIVO|EM_MANUTENCAO`).

### 4.3 Resultado esperado ao salvar
- Criar relógio com status informado; se ausente, assumir `Ativo`.
- Gerar código de ativação.
- Redirecionar para listagem com novo card visível.

---

## 5. Tela `Relógios de Ponto` após criação — referência da imagem 3

### 5.1 Card do relógio na listagem
Cada card deve mostrar:
- nome do relógio (ex.: `Relogio Portaria`)
- badges:
  - `Ativo`
  - `REP-P (Programa/Software)`
- metadados:
  - responsável/contexto (ex.: usuário criador)
  - quantidade de colaboradores atribuídos (ex.: `Nenhum colaborador atribuído`)
  - método de autenticação suportado (`Reconhecimento Facial`)
  - `Código de Ativação`

### 5.2 Ações do card
- `Gerenciar`
- `Inativar Relógio`

Semântica:
- `Gerenciar` abre detalhamento/configuração do relógio.
- `Inativar Relógio` bloqueia novas ativações e uso operacional (preservando histórico).

---

## 6. Tela de detalhe do relógio (Gerenciar) — referência da imagem de detalhe

### 6.1 Estrutura geral da página
- Breadcrumb: `Início > Relógios de Ponto > {Nome do Relógio}`
- Título: `{Nome do Relógio}` (ex.: `Relogio Portaria`)
- Ações no topo direito:
  - `Editar Relógio`
  - `Inativar Relógio`
- Abas:
  - `Informações`
  - `Colaboradores`

Observação de mapeamento:
- A captura anterior do usuário estava com a aba `Informações` ativa.
- A captura mais recente corresponde à aba `Colaboradores`.

### 6.2 Aba `Informações` (estado ativo por padrão ao abrir Gerenciar)
Card `Informações` com os campos:
- `Nome do Relógio`
- `Tipo do Relógio` (badge ex.: `REP-P (Programa/Software)`)
- `Status` (badge ex.: `Ativo`/`Inativo`/`Em Manutenção`)
- `Plataforma` (ex.: `Web`, `Android`, `iOS`)
- `Método de Autenticação Suportado` (`Reconhecimento Facial`)
- `Código de Ativação`
- `Colaboradores` (quantidade atribuída)
- `Última Sincronização` (ex.: `Nunca sincronizado` ou data/hora)
- `Criado em` (timestamp local do tenant)

Card `Cerca Virtual`:
- Mensagem de estado quando vazia: `Nenhuma cerca virtual configurada.`
- CTA: `Configurar Cerca Virtual`

Semântica negocial:
- `Status` controla disponibilidade operacional do relógio para batidas e novas ativações.
- `Em Manutenção` representa indisponibilidade temporária planejada do relógio, sem perda de configuração.
- `Código de Ativação` identifica pareamento de dispositivo no app de relógio.
- `Última Sincronização` evidencia saúde operacional e comunicação do dispositivo.
- `Cerca Virtual` define restrição geográfica permitida para uso do relógio.

### 6.3 Aba `Colaboradores` (gestão de atribuição)
Layout em 3 colunas:

1) Painel esquerdo `Disponíveis (N)`:
- Busca `Pesquisar colaboradores`
- Ação `Filtros Avançados`
- Grid com colunas:
  - seleção (checkbox)
  - `Foto`
  - `Nome`
  - `Matrícula`

2) Painel central `Ações`:
- `Mover Selecionados ->`
- `Mover TODOS >>`
- `<- Remover Selecionados`
- `<< Remover TODOS`

3) Painel direito `No Relógio (N)`:
- Busca `Pesquisar no relógio`
- Grid com colunas equivalentes
- Estado vazio: `Nenhum colaborador atribuído`

Comportamento:
- `Mover Selecionados` transfere apenas os itens marcados de `Disponíveis` para `No Relógio`.
- `Mover TODOS` transfere todos os itens filtrados/listados em `Disponíveis`.
- `Remover Selecionados` e `Remover TODOS` fazem o fluxo inverso.
- Contadores `(N)` atualizam imediatamente após cada operação.
- Botões dependentes de seleção/lista ficam desabilitados quando a ação não é aplicável.

Semântica negocial:
- `No Relógio` define quais colaboradores estão autorizados a utilizar aquele relógio para registro.
- Remover colaborador do relógio atual retira autorização naquele ponto específico sem excluir cadastro do colaborador.

## 7. Regras de filtragem e estado da listagem

- Filtro textual busca por `nome` e `descrição`.
- Filtro `Status` aplica em badges de status.
- Filtro `Tipo de REP` aplica em badges/tipo do relógio.
- Paginação quando houver múltiplos relógios.

---

## 8. Catálogo de mensagens

Mensagens de validação:
- `Informe o nome do relógio.`
- `O nome do relógio deve ter entre 3 e 80 caracteres.`
- `Já existe um relógio com este nome nesta empresa.`
- `O relógio suporta apenas autenticação por reconhecimento facial.`
- `Selecione o tipo do relógio.`
- `Status inválido para o relógio.`

Mensagens de operação:
- `Relógio criado com sucesso.`
- `Não foi possível criar o relógio. Tente novamente.`
- `Relógio inativado com sucesso.`
- `Relógio alterado para manutenção com sucesso.`
- `Não foi possível inativar o relógio.`
- `Colaborador(es) atribuídos ao relógio com sucesso.`
- `Colaborador(es) removidos do relógio com sucesso.`
- `Não foi possível atualizar os colaboradores do relógio.`

Mensagens de estado:
- `Nenhum resultado encontrado.`
- `Nenhum colaborador atribuído.`
- `Nenhuma cerca virtual configurada.`

---

## 9. Integração com domínio atual (MVP/evolução)

### 9.1 Mapeamento inicial
- O projeto já possui entidade de dispositivo em `accounts.Device`, útil como base técnica.
- O módulo `Relógios de Ponto` deve evoluir para entidade de domínio própria (separada de device bruto), mantendo vínculo tenant-aware.

### 9.2 Integrações esperadas
- Atribuição de colaboradores ao relógio.
- Ativação de relógio via código no app.
- Exportação AFD por período (ação de topo na listagem).

---

## 10. Critérios de aceite da área de relógios

- Tela de listagem inicial renderiza exatamente com banner, filtros e estado vazio.
- A ação `Criar Relógio` abre formulário com campos e validações descritas.
- Após salvar, relógio aparece em card com status, tipo REP, código de ativação e ações.
- `Inativar Relógio` altera status sem remover histórico.
- Status `Em Manutenção` é suportado em cadastro/edição/visualização.
- `Gerenciar` abre tela de detalhe com abas `Informações` e `Colaboradores`.
- Aba `Informações` exibe metadados do relógio e estado de cerca virtual.
- Aba `Colaboradores` permite atribuir/remover em lote com contadores coerentes.
- Fluxo respeita isolamento por tenant.

---

## 11. Contrato de payload/API (MVP) — `Editar Relógio`, `Cerca Virtual` e aba `Colaboradores`

### 11.1 Convenções gerais
- Namespace sugerido da API REST: `/api/relogios/`
- Autenticação: JWT obrigatório.
- Escopo: todas as operações são tenant-aware (`request.tenant`).
- IDs: `UUID` para relógio e cerca virtual.
- Formato de erro padronizado:

```json
{
  "code": "validation_error",
  "message": "Erro de validação.",
  "errors": {
    "campo": ["mensagem de erro"]
  }
}
```

### 11.2 `Editar Relógio`

Endpoint:
- `PATCH /api/relogios/{relogio_id}/`

Objetivo negocial:
- Permitir manutenção dos dados administrativos do relógio sem recriar entidade.

Campos editáveis (MVP):
- `nome` (obrigatório lógico)
- `descricao` (opcional)
- `status` (`ATIVO`/`INATIVO`/`EM_MANUTENCAO`)

Request exemplo:

```json
{
  "nome": "Relógio Portaria Principal",
  "descricao": "Tablet da entrada principal",
  "status": "ATIVO"
}
```

Response `200` exemplo:

```json
{
  "id": "8d8d8f2d-0d75-4cc7-86ac-7f4f1399f1cd",
  "nome": "Relógio Portaria Principal",
  "descricao": "Tablet da entrada principal",
  "tipo_rep": "REP-P",
  "plataforma": "WEB",
  "metodos_autenticacao": ["FACIAL"],
  "status": "ATIVO",
  "codigo_ativacao": "723B2B",
  "colaboradores_total": 1,
  "updated_at": "2026-03-08T14:40:00-03:00"
}
```

Validações:
- `nome`: obrigatório, `3..80` caracteres, trim aplicado.
- unicidade por tenant (case-insensitive).
- método de autenticação fixo em `FACIAL`; rejeitar qualquer valor fora desse escopo.
- `status`: obrigatório quando informado; valores permitidos:
  - `ATIVO`
  - `INATIVO`
  - `EM_MANUTENCAO`

Regras de negócio:
- Edição não altera histórico de batidas nem NSR já gerado.
- Método de autenticação permanece `FACIAL` para novas marcações.
- Status `INATIVO` bloqueia novas marcações e novas ativações.
- Status `EM_MANUTENCAO` bloqueia marcações durante janela operacional, preservando vínculo e configurações.

Erros esperados:
- `400` validação de campos.
- `404` relógio inexistente no tenant.
- `409` conflito de nome duplicado no tenant.

### 11.3 `Configurar Cerca Virtual`

Endpoint:
- `PUT /api/relogios/{relogio_id}/cerca-virtual/`

Objetivo negocial:
- Definir georrestrição para batidas realizadas por colaboradores vinculados ao relógio.

Request exemplo:

```json
{
  "nome": "Portaria Fábrica",
  "latitude": -3.732714,
  "longitude": -38.527004,
  "raio_metros": 120,
  "ativo": true
}
```

Response `200` exemplo:

```json
{
  "id": "4af01ea7-44b6-45e8-9ea5-4d083ca31f6a",
  "relogio_id": "8d8d8f2d-0d75-4cc7-86ac-7f4f1399f1cd",
  "nome": "Portaria Fábrica",
  "latitude": -3.732714,
  "longitude": -38.527004,
  "raio_metros": 120,
  "ativo": true,
  "updated_at": "2026-03-08T14:52:00-03:00"
}
```

Validações:
- `nome`: obrigatório, `3..60` caracteres.
- `latitude`: obrigatório, intervalo `[-90, 90]`.
- `longitude`: obrigatório, intervalo `[-180, 180]`.
- `raio_metros`: obrigatório, inteiro, faixa `20..1000`.
- deve existir no máximo 1 cerca virtual ativa por relógio (upsert).

Regras de negócio:
- Com cerca ativa, o motor de marcação deve validar coordenada da batida dentro do raio.
- Batida fora da cerca deve ser rejeitada com erro semântico e log de auditoria.
- Atualizar a cerca substitui configuração anterior (sem criar múltiplas ativas).

Erros esperados:
- `400` para latitude/longitude/raio inválidos.
- `404` relógio inexistente no tenant.
- `409` conflito de regra de negócio (quando necessário).

### 11.4 `Remover/Desativar Cerca Virtual`

Endpoints:
- `DELETE /api/relogios/{relogio_id}/cerca-virtual/`
ou
- `PATCH /api/relogios/{relogio_id}/cerca-virtual/` com `{ "ativo": false }`

Response `204` (delete físico lógico) ou `200` (toggle):
- sem payload obrigatório.

Regra:
- remover/desativar cerca virtual deve liberar batidas sem validação geográfica para o relógio.

### 11.5 `GET` de detalhe com representação de cerca

Endpoint:
- `GET /api/relogios/{relogio_id}/`

Trecho de response esperado:

```json
{
  "id": "8d8d8f2d-0d75-4cc7-86ac-7f4f1399f1cd",
  "nome": "Relógio Portaria Principal",
  "tipo_rep": "REP-P",
  "status": "ATIVO",
  "cerca_virtual": {
    "id": "4af01ea7-44b6-45e8-9ea5-4d083ca31f6a",
    "nome": "Portaria Fábrica",
    "latitude": -3.732714,
    "longitude": -38.527004,
    "raio_metros": 120,
    "ativo": true
  }
}
```

Quando não houver cerca:

```json
{
  "id": "8d8d8f2d-0d75-4cc7-86ac-7f4f1399f1cd",
  "nome": "Relógio Portaria Principal",
  "tipo_rep": "REP-P",
  "status": "ATIVO",
  "cerca_virtual": null
}
```

### 11.6 Mensagens de negócio para UI (edição e cerca)
- `Relógio atualizado com sucesso.`
- `Não foi possível atualizar o relógio. Revise os dados e tente novamente.`
- `Cerca virtual configurada com sucesso.`
- `Cerca virtual atualizada com sucesso.`
- `Cerca virtual removida com sucesso.`
- `A localização informada é inválida.`
- `O raio da cerca deve estar entre 20m e 1000m.`
- `Batida fora da cerca virtual não permitida para este relógio.`

### 11.7 Ativação do relógio no app (código de ativação)

#### 11.7.1 Objetivo
- Formalizar o passo `Criar seu relógio e fazer a ativação utilizando o código de ativação` para o app.

#### 11.7.2 Endpoint de ativação
- `POST /api/relogios/ativar/`

Request exemplo:

```json
{
  "activation_code": "723B2B",
  "device_id": "android-tablet-portaria-01",
  "nome_dispositivo": "Tablet Portaria",
  "plataforma": "ANDROID",
  "app_version": "1.0.0"
}
```

Response `200` exemplo:

```json
{
  "access": "<jwt-device-access>",
  "refresh": "<jwt-device-refresh>",
  "relogio": {
    "id": "8d8d8f2d-0d75-4cc7-86ac-7f4f1399f1cd",
    "nome": "Relógio Portaria Principal",
    "status": "ATIVO",
    "tipo_rep": "REP-P",
    "metodos_autenticacao": ["FACIAL"]
  },
  "device": {
    "id": "c9a61162-247f-4fd8-8a2d-0bdb6c4f7b22",
    "device_id": "android-tablet-portaria-01",
    "ativo": true
  }
}
```

Validações:
- `activation_code` obrigatório e válido.
- `device_id` obrigatório e não vazio.
- Relógio deve pertencer ao tenant correto.
- Relógio deve estar em `ATIVO` para ativação.

Erros esperados:
- `400` código malformado ou campos obrigatórios ausentes.
- `404` código inexistente.
- `409` relógio `INATIVO` ou `EM_MANUTENCAO` (ativação bloqueada).

Mensagens sugeridas:
- `Relógio ativado com sucesso no dispositivo.`
- `Código de ativação inválido ou expirado.`
- `Relógio indisponível para ativação no momento.`

#### 11.7.3 Relação com endpoint de device auth existente
- Pode ser implementado como endpoint dedicado (`/api/relogios/ativar/`) ou como extensão de `POST /api/auth/device/register/` aceitando `activation_code`.
- Em ambos os casos, a regra de negócio deve ser idêntica.

### 11.8 Pré-condições para colaborador bater ponto após ativação

Para `POST /api/attendance/register/` ser aceito no dispositivo do relógio:
- relógio do dispositivo em `ATIVO`
- colaborador atribuído ao relógio (`No Relógio`)
- colaborador com status `ATIVO`
- autenticação facial válida (conforme serviço biométrico)

Erros semânticos esperados:
- `Colaborador não está atribuído a este relógio.`
- `Relógio em manutenção. Tente novamente após liberação.`
- `Relógio inativo.`
- `Autenticação facial não concluída para o colaborador.`

### 11.9 Atribuição de colaboradores ao relógio (aba `Colaboradores`)

#### 11.9.1 Endpoints de listagem (base da tela dual-list)
- `GET /api/relogios/{relogio_id}/colaboradores/disponiveis/`
- `GET /api/relogios/{relogio_id}/colaboradores/no-relogio/`

Query params suportados:
- `q` (busca por `nome`, `cpf`, `matricula`)
- `page`
- `page_size`
- `status` (quando filtros avançados estiverem ativos)
- `departamento` (opcional)

Response `200` exemplo (paginado):

```json
{
  "count": 1,
  "page": 1,
  "page_size": 10,
  "results": [
    {
      "id": 123,
      "nome": "FRANCISCO MARCIO GADELHA PAES",
      "matricula": "MAT-12345",
      "foto_url": null,
      "status": "ATIVO"
    }
  ]
}
```

#### 11.9.2 Mover selecionados (`Disponíveis -> No Relógio`)

Endpoint:
- `POST /api/relogios/{relogio_id}/colaboradores/mover-selecionados/`

Request exemplo:

```json
{
  "employee_ids": [123, 456]
}
```

Response `200` exemplo:

```json
{
  "moved_count": 2,
  "ignored_count": 0,
  "disponiveis_count": 8,
  "no_relogio_count": 2
}
```

Validações:
- `employee_ids` obrigatório, lista não vazia, máximo 500 itens por requisição.
- todos os IDs devem pertencer ao tenant autenticado.
- não permitir vincular colaborador `INATIVO` ao relógio (regra MVP).

Semântica:
- operação idempotente: colaboradores já vinculados entram em `ignored_count`.
- atualização deve refletir os contadores `(N)` da tela após a resposta.

#### 11.9.3 Mover TODOS (`Disponíveis -> No Relógio`)

Endpoint:
- `POST /api/relogios/{relogio_id}/colaboradores/mover-todos/`

Request exemplo (com contexto de filtro):

```json
{
  "filter": {
    "q": "francisco",
    "status": "ATIVO",
    "departamento": null
  }
}
```

Response `200` exemplo:

```json
{
  "moved_count": 1,
  "ignored_count": 0,
  "disponiveis_count": 0,
  "no_relogio_count": 1
}
```

Semântica:
- aplica ao conjunto filtrado atual de `Disponíveis`.
- garante comportamento previsível com os filtros ativos no frontend.

#### 11.9.4 Remover selecionados (`No Relógio -> Disponíveis`)

Endpoint:
- `POST /api/relogios/{relogio_id}/colaboradores/remover-selecionados/`

Request exemplo:

```json
{
  "employee_ids": [123]
}
```

Response `200` exemplo:

```json
{
  "removed_count": 1,
  "ignored_count": 0,
  "disponiveis_count": 1,
  "no_relogio_count": 0
}
```

Semântica:
- remove apenas vínculo relógio-colaborador, sem excluir colaborador do tenant.
- histórico de ponto permanece íntegro.

#### 11.9.5 Remover TODOS (`No Relógio -> Disponíveis`)

Endpoint:
- `POST /api/relogios/{relogio_id}/colaboradores/remover-todos/`

Request exemplo:

```json
{
  "filter": {
    "q": "",
    "status": "ATIVO"
  }
}
```

Response `200` exemplo:

```json
{
  "removed_count": 12,
  "ignored_count": 0,
  "disponiveis_count": 12,
  "no_relogio_count": 0
}
```

#### 11.9.6 Erros e validações comuns das quatro ações
- `400` payload inválido (`employee_ids` vazio, filtro malformado, limite excedido).
- `404` relógio inexistente no tenant.
- `409` conflito de negócio (ex.: tentativa de vincular colaborador não elegível).

Mensagens sugeridas:
- `Colaboradores atribuídos ao relógio com sucesso.`
- `Nenhum colaborador foi movimentado.`
- `Colaboradores removidos do relógio com sucesso.`
- `Não foi possível atualizar os colaboradores do relógio.`
- `Selecione ao menos um colaborador para continuar.`
- `Não é permitido vincular colaborador inativo ao relógio.`
