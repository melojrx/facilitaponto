# DEV-008 — Especificação da Área de Colaboradores
**Versão:** 1.4  
**Data:** 2026-03-08  
**Contexto:** módulo liberado após conclusão da primeira jornada (`onboarding_step >= 3`)  
**Referências:** `docs/DEV_008_ONBOARDING_MODELAGEM.md`, `docs/DEV_008_TELA_NOVA_JORNADA.md`, mocks visuais aprovados

---

## 1. Objetivo

Documentar a área `Colaboradores` no painel web com:

- Tela de listagem de colaboradores.
- Fluxo de `Novo Colaborador`.
- Semântica negocial de cadastro, status, vínculo de jornada e biometria.

Rotas alvo (MVP):
- `GET /painel/colaboradores/`
- `GET|POST /painel/colaboradores/novo/`

---

## 2. Semântica negocial da área

### 2.1 Papel do colaborador no domínio
- Colaborador representa o funcionário vinculado ao tenant da empresa.
- O cadastro de colaborador habilita operações de:
  - marcação de ponto
  - cálculo de jornada/espelho
  - emissão de comprovante/arquivos legais.

### 2.2 Status operacionais
- `Ativo`:
  - pode registrar ponto
  - participa de cálculos e relatórios correntes.
- `Inativo`:
  - não pode registrar ponto novo
  - histórico permanece para auditoria e relatórios passados.
- `Transferido` (nível de painel):
  - indica mudança de vínculo interno (setor/jornada/matrícula) com rastreabilidade.
  - não representa transferência entre tenants.

### 2.3 Relação com jornada
- Todo colaborador operacional deve possuir uma jornada associada (template ou personalizada).
- Regras de atraso, extra, banco e tratamento de ponto dependem dessa associação.

### 2.4 Relação com biometria
- Reconhecimento facial exige:
  - consentimento LGPD ativo
  - embedding facial ativo.
- Sem cadastro facial, colaborador pode ficar `pendente de biometria` até captura/envio de convite.

---

## 3. Tela `Colaboradores` (listagem) — referência da imagem 1

### 3.1 Estrutura visual
- Breadcrumb: `Início > Colaboradores`
- Cabeçalho:
  - título `Colaboradores`
  - subtítulo `Gerencie os colaboradores cadastrados na empresa`
  - CTA primário `+ Novo Colaborador` (canto superior direito)

### 3.2 Barra de filtros
- Busca textual: `Buscar por nome, CPF ou PIS`
- Filtro de turno/jornada: select `Todos os Turnos`

### 3.3 Abas de estado
- `Ativos (N)`
- `Inativos`
- `Transferidos`

### 3.4 Grade/tabela
Colunas mínimas:
- seleção (checkbox)
- `Nome`
- `Face`
- `Departamento`
- `Função`
- `Status`
- `Jornada`
- `Ações`

### 3.5 Estado vazio
- Ícone central + texto:
  - `Nenhum colaborador encontrado`
  - `Nenhum colaborador encontrado com os filtros aplicados`
- CTA `Novo Colaborador` deve permanecer visível no cabeçalho.

### 3.6 Estado pós-cadastro (referência da imagem enviada)

Após criar 1 colaborador com sucesso, a listagem deve refletir:
- Aba `Ativos` com contador atualizado (ex.: `Ativos (1)`).
- Uma linha na tabela com:
  - `Nome` do colaborador cadastrado
  - `Face` com badge `Pendente` quando biometria ainda não concluída
  - `Departamento` (ou `-` quando não preenchido)
  - `Função` conforme cadastro
  - `Status` com badge `Ativo`
  - `Jornada` vinculada (ex.: `Semanal`)
  - `Ações` rápidas na linha.
- Rodapé de paginação com total de itens (ex.: `Página 1 de 1 • 1 item no total`).

---

## 4. Comportamento e filtros da listagem

### 4.1 Busca
- Deve buscar por:
  - nome parcial (case-insensitive)
  - CPF (com ou sem máscara)
  - PIS/PASEP (com ou sem máscara)

### 4.2 Filtro de turno/jornada
- Filtra colaboradores pela jornada vinculada.
- `Todos os Turnos` remove restrição do filtro.

### 4.3 Abas
- Aba ativa determina subconjunto principal.
- Contador da aba `Ativos` reflete quantidade já filtrada por tenant.

### 4.4 Ordenação
- Padrão por nome (A-Z), com paginação quando necessário.

### 4.5 Ações por linha na listagem

Ações visuais da coluna `Ações` (conforme referência):
- ícone WhatsApp (verde):
  - enviar/reenviar link de cadastro facial ao colaborador.
- ícone edição:
  - abrir edição do colaborador.
- ícone vermelho (status):
  - alterar situação do colaborador (ex.: inativar/transferir, conforme regra final do domínio).

---

## 5. Tela `Novo Colaborador` — referência das imagens 2 e 3

### 5.1 Estrutura geral
- Breadcrumb: `Início > Colaboradores > Novo Colaborador`
- Formulário em cards/seções:
  1. `Dados Básicos`
  2. `Informações de Trabalho`
  3. `Jornada de Trabalho`
  4. `Reconhecimento Facial`
- Ações finais: `Cancelar` e `Criar`.

### 5.2 Seção `Dados Básicos`
Campos exibidos:
- `CPF*`
- `PIS/PASEP`
- `Nome Completo*`
- `Data de Nascimento`
- `E-mail`
- `Telefone`

Observação de UX:
- Mensagem contextual sobre envio de convite/cadastro facial via WhatsApp.

### 5.3 Seção `Informações de Trabalho`
Campos exibidos:
- `Função/Cargo`
- `Departamento/Setor`
- `Data de Admissão`
- `Matrícula Interna`

### 5.4 Seção `Jornada de Trabalho`
Contém:
- Select `Selecionar Jornada` (template existente ou personalizado)
- Cards de tipo de jornada (`Semanal`, `12x36`, `Fracionada`, `Externa`)
- Bloco informativo do tipo selecionado (mesma semântica da tela de jornadas)

#### 5.4.1 Estado com template selecionado (referência da imagem enviada)

Exemplo:
- `Selecionar Jornada = Jornada Integral`
- Card `Semanal` ativo.

Comportamento esperado:
- O tipo da jornada é inferido pelo template selecionado e o card correspondente fica destacado.
- A seção expande e exibe o painel:
  - `O que o sistema faz com a jornada`
  - bullets de efeitos operacionais (atraso, saída antecipada, extras, banco, etc.).
- Exibir bloco `Dúvidas comuns`.
- Nessa etapa do cadastro de colaborador, os dados estruturais da jornada do template são tratados como referência operacional do colaborador (não como edição do template global).

#### 5.4.2 Estado `Personalizado (entrada manual)`

Comportamento esperado:
- Sem card selecionado inicialmente, exibir bloco:
  - `Selecione o tipo de jornada`
- Ao escolher um card (`Semanal`, `12x36`, `Fracionada`, `Externa`), expandir conteúdo correspondente à semântica já definida na especificação de jornadas.
- Configuração manual vinculada ao colaborador (escopo individual), sem alterar templates globais da empresa.

### 5.5 Seção `Reconhecimento Facial`
Contém:
- Estado atual (ex.: `Sem dados faciais`)
- Botão `Capturar Foto Facial`
- Texto orientativo para captura imediata ou envio posterior por WhatsApp.

#### 5.5.1 Fluxo `Capturar Foto Facial` (modal da imagem enviada)

Ao clicar em `Capturar Foto Facial`, abrir modal com:
- título: `Captura de Reconhecimento Facial`
- texto de instrução para captura
- área de prévia da foto
- mini-card com foto capturada (`Frente`)
- checkbox de autorização/consentimento:
  - `Declaro que autorizo a captura de dados biométricos faciais para uso no sistema de ponto eletrônico.`
- ações:
  - `Cancelar`
  - `Recapturar Foto`
  - `Confirmar e Salvar`

Regras de estado do modal:
- `Confirmar e Salvar` inicia desabilitado até existir foto válida + consentimento marcado.
- `Recapturar Foto` substitui a imagem atual e mantém consentimento desmarcado.
- Fechar modal sem confirmar não altera status biométrico do colaborador.

#### 5.5.2 Fluxo alternativo `Enviar link por WhatsApp`

Objetivo:
- Permitir auto-cadastro facial pelo próprio funcionário fora do painel administrativo.

Comportamento esperado:
- A partir do cadastro do colaborador, o sistema disponibiliza ação para envio de link seguro ao WhatsApp informado.
- Antes do disparo, abrir modal de confirmação (como na referência) com:
  - título: `Enviar link de cadastro facial?`
  - mensagem dinâmica: `Uma mensagem será enviada para {telefone} via WhatsApp com instruções para o cadastro facial do colaborador.`
  - botões: `Cancelar` e `Enviar`.
- `Enviar` deve ficar habilitado apenas com telefone válido no cadastro do colaborador.
- `Cancelar` fecha o modal sem qualquer envio.
- O link leva para página de auto-captura facial com:
  - identificação do colaborador
  - termo de consentimento LGPD
  - captura da foto
  - confirmação final.
- Após conclusão pelo colaborador:
  - registrar consentimento
  - executar enroll
  - atualizar status no painel para `Cadastro facial concluído`.

Regras de segurança do link:
- token único, assinado e com expiração
- uso único (invalidar após conclusão)
- bloquear reuso e exibir mensagem de link expirado/inválido.

---

## 6. Regras de validação do `Novo Colaborador`

### 6.1 Regras obrigatórias de domínio
- `nome` obrigatório.
- `cpf` obrigatório, 11 dígitos numéricos.
- `cpf` único por tenant.
- `pis` obrigatório no salvamento operacional do MVP (11 dígitos), por exigência legal de relatórios/AFD.

### 6.2 Regras de consistência
- `email` opcional, mas deve ser válido quando informado.
- `telefone` opcional, mas obrigatório para envio de convite por WhatsApp.
- `data_nascimento` não pode ser futura.
- `data_admissao` não pode ser futura.
- `matricula_interna` deve ser única por tenant quando utilizada (regra recomendada para evolução).

### 6.3 Regras de jornada
- Deve haver jornada selecionada para colaborador ativo.
- Se jornada personalizada for escolhida, aplicar mesmas validações de tipos (`Semanal`, `12x36`, `Fracionada`, `Externa`).
- Se template existente for selecionado:
  - bloquear alteração estrutural do template a partir desta tela
  - permitir somente vínculo do colaborador ao template.

### 6.4 Regras de biometria
- Cadastro facial imediato:
  - registrar consentimento LGPD
  - executar enroll do embedding.
- Sem biometria imediata:
  - colaborador fica em estado `sem dados faciais`/`pendente`
  - sistema permite concluir cadastro administrativo.
- No modal de captura:
  - consentimento explícito obrigatório para `Confirmar e Salvar`.
- No fluxo via WhatsApp:
  - telefone válido obrigatório
  - link deve respeitar expiração e uso único.

---

## 7. Catálogo de mensagens

Mensagens de validação:
- `Informe o nome completo do colaborador.`
- `Informe um CPF válido com 11 dígitos.`
- `Já existe colaborador com este CPF nesta empresa.`
- `Informe um PIS/PASEP válido com 11 dígitos.`
- `Informe uma jornada de trabalho para o colaborador.`
- `Data inválida.`

Mensagens de biometria:
- `Sem dados faciais.`
- `Consentimento biométrico pendente.`
- `Cadastro facial concluído com sucesso.`
- `Não foi possível concluir o cadastro facial. Tente novamente.`
- `Marque a autorização para confirmar o cadastro facial.`
- `Foto capturada com sucesso. Revise antes de confirmar.`
- `Link de cadastro facial enviado para o WhatsApp do colaborador.`
- `Não foi possível enviar o link por WhatsApp. Verifique o número informado.`
- `Confirme o envio do link para continuar.`
- `Telefone inválido para envio por WhatsApp.`
- `Este link de cadastro facial expirou. Solicite um novo link.`
- `Este link já foi utilizado.`
- `Cadastro criado. Biometria pendente de conclusão.`

Mensagens de operação:
- `Colaborador criado com sucesso.`
- `Não foi possível criar o colaborador. Revise os dados e tente novamente.`

---

## 8. Semântica de integração com backend atual

### 8.1 Campos já suportados no modelo atual (`employees.Employee`)
- `nome`
- `cpf` (único por tenant)
- `pis`
- `email`
- `ativo`

### 8.2 Campos de trabalho e vínculo de jornada
- `função`, `departamento`, `data_admissao`, `matricula_interna`, `jornada`:
  - devem ser tratados como evolução de modelagem/API para refletir o formulário completo do painel.
  - até a evolução completa, UI pode operar com salvamento parcial controlado por feature flag.

### 8.3 Fluxo biométrico
- Consentimento: `POST /api/employees/{id}/consent/`
- Enroll: `POST /api/employees/{id}/enroll/`
- Sem consentimento ativo, enroll deve ser bloqueado.

### 8.4 Fluxo de auto-cadastro facial por WhatsApp (evolução do painel)
- Geração de link seguro para auto-enroll do colaborador.
- Envio via provedor WhatsApp com template de mensagem.
- Callback/retorno do fluxo atualiza status biométrico do colaborador no painel.
- Auditoria mínima:
  - data/hora de envio
  - status de entrega
  - data/hora de conclusão do auto-cadastro.

---

## 9. Critérios de aceite da área de colaboradores

- Tela de listagem renderiza fiel ao layout (filtros, abas, tabela e estado vazio).
- Após cadastro, colaborador aparece na listagem com `Status = Ativo` e `Face = Pendente` quando biometria não concluída.
- Botão `Novo Colaborador` abre formulário completo com as 4 seções previstas.
- Validações de CPF/PIS e unicidade por tenant são respeitadas.
- Seção de jornada no colaborador mantém a mesma semântica negocial dos tipos de jornada do sistema.
- Seção de reconhecimento facial permite captura imediata ou fluxo posterior sem perder rastreabilidade.
- Modal de captura facial exige consentimento antes de confirmar.
- Fluxo de envio de link por WhatsApp funciona com segurança (token expirável e uso único).
- Colaborador criado aparece na listagem da empresa correta, sem vazamento cross-tenant.
