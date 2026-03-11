# Product Backlog — Sistema de Ponto Eletrônico
**Versão:** 1.5  
**Data:** 2026-03-11  

---

## Status de Execução (2026-03-11)

- ✅ Entregue no backend/web: PB-001 a PB-006, PB-010 a PB-014, PB-030 a PB-034 e PB-100 no núcleo funcional self-service.
- 🟡 Parcial: PB-035 com carimbo MVP (`timestamp_carimbo` + `hash_carimbo`); integração TSA RFC 3161 externa permanece como evolução.
- 🆕 Regra de negócio formalizada: conta proprietária com vínculo **1:1** com empresa (CNPJ/CPF) e isolamento total por tenant.
- ✅ Bloco `Colaboradores` entregue no núcleo funcional do painel web.
- 🚧 Próxima sprint: executar na ordem `Relógios de Ponto -> Captura facial no painel -> Envio por WhatsApp -> Tratamento de Ponto -> Relatórios -> Solicitações`.
- 📌 A fonte oficial do acompanhamento detalhado desse bloco é `docs/DEV_008_CHECKLIST.md`.
- 📌 Direção técnica do WhatsApp no MVP: `adapter pluggable` com provider inicial `WAHA`; alternativas futuras documentadas para escala/compliance.
- ⏭️ Bloco seguinte após estabilização web/admin: PB-020 a PB-028 (app mobile).

---

## FASE 1 — MVP (Semanas 1 a 4) 🎯
*Objetivo: Sistema rodando na primeira empresa de testes*

### Épico 1.1 — Infraestrutura e Multitenancy

| ID | User Story | Prioridade |
|---|---|---|
| PB-001 | Como sistema, preciso ter multitenancy com isolamento de dados por empresa via tenant_id | CRÍTICO |
| PB-002 | Como sistema, preciso de configuração Docker Compose com Django, PostgreSQL, Redis, MinIO | CRÍTICO |
| PB-003 | Como sistema, preciso de variáveis de ambiente e settings separados por ambiente (dev/prod) | CRÍTICO |
| PB-004 | Como sistema, preciso de migrations iniciais com todas as tabelas core | CRÍTICO |
| PB-005 | Como sistema, preciso de autenticação JWT para o app mobile com device_id | CRÍTICO |
| PB-006 | Como dono da conta, quero cadastrar meu usuário (nome, sobrenome, e-mail/login único global, CPF único global e telefone) e vincular exatamente uma empresa (CNPJ ou CPF), para que funcionários, turnos, relatórios e batidas fiquem isolados no tenant da minha conta | CRÍTICO |

### Épico 1.2 — Cadastro de Empresa e Funcionários

| ID | User Story | Prioridade |
|---|---|---|
| PB-010 | Como admin, quero cadastrar minha empresa com CNPJ, razão social e dados do responsável | CRÍTICO |
| PB-011 | Como admin, quero cadastrar funcionários com nome, CPF, PIS e foto para enroll biométrico | CRÍTICO |
| PB-012 | Como sistema, preciso armazenar o embedding facial do funcionário criptografado (AES-256) | CRÍTICO |
| PB-013 | Como admin, quero ativar e desativar funcionários | ALTA |
| PB-014 | Como sistema, preciso gerar e gerenciar o NSR sequencial por empresa via PostgreSQL sequence | CRÍTICO |

### Épico 1.3 — App Mobile (Tablet da Portaria)

| ID | User Story | Prioridade |
|---|---|---|
| PB-020 | Como dispositivo, preciso me autenticar na API com device_id e JWT | CRÍTICO |
| PB-021 | Como funcionário, quero ver a interface do tablet e acionar o reconhecimento facial | CRÍTICO |
| PB-022 | Como sistema, o app deve capturar o frame da câmera e enviar para a API verificar | CRÍTICO |
| PB-023 | Como sistema, o app deve exibir o resultado do reconhecimento (aprovado/negado) | CRÍTICO |
| PB-024 | Como sistema, o app deve exibir o comprovante na tela após registro aprovado | CRÍTICO |
| PB-025 | Como sistema, o app deve funcionar offline salvando registros no SQLite local | CRÍTICO |
| PB-026 | Como sistema, o app deve sincronizar registros offline ao restaurar conexão | CRÍTICO |
| PB-027 | Como sistema, o app deve cachear embeddings dos funcionários localmente (criptografado) | CRÍTICO |
| PB-028 | Como sistema, o app deve usar MLKit para reconhecimento facial offline | CRÍTICO |

### Épico 1.4 — Registro de Ponto e Comprovante

| ID | User Story | Prioridade |
|---|---|---|
| PB-030 | Como sistema, preciso registrar Entrada, Saída, Início e Fim de Intervalo | CRÍTICO |
| PB-031 | Como sistema, cada registro deve ter NSR único, timestamp com fuso, foto hash e confiança biométrica | CRÍTICO |
| PB-032 | Como sistema, registros nunca podem ser alterados, apenas justificados com novo NSR | CRÍTICO |
| PB-033 | Como sistema, devo emitir comprovante eletrônico imediatamente após cada registro | CRÍTICO |
| PB-034 | Como sistema, o comprovante deve conter nome, PIS, data, hora, NSR e tipo de marcação | CRÍTICO |
| PB-035 | Como sistema, o comprovante deve ter carimbo de tempo RFC 3161 | ALTA |

### Épico 1.5 — Painel Web Admin (MVP)

| ID | User Story | Prioridade |
|---|---|---|
| PB-040 | Como admin, quero visualizar os registros de ponto do dia | CRÍTICO |
| PB-041 | Como admin, quero ver o espelho de ponto do funcionário por período | ALTA |
| PB-042 | Como admin, quero gerar e baixar o arquivo AFD por período | CRÍTICO |
| PB-043 | Como admin, quero cadastrar jornada padrão da empresa (horário, tolerâncias) | ALTA |

---

## FASE 2 — Conformidade Legal Completa (Semanas 5 a 7)
*Objetivo: Sistema 100% conforme Portaria 671/2021*

### Épico 2.1 — Arquivos Legais

| ID | User Story | Prioridade |
|---|---|---|
| PB-050 | Como sistema, devo gerar o AFD completo conforme layout do Anexo I da Portaria 671 | CRÍTICO |
| PB-051 | Como sistema, devo gerar o AEJ completo conforme layout do Anexo II da Portaria 671 | CRÍTICO |
| PB-052 | Como sistema, devo validar internamente os arquivos AFD e AEJ antes de exportar | CRÍTICO |
| PB-053 | Como admin, quero gerar AFD/AEJ filtrando por período e empresa | ALTA |
| PB-054 | Como sistema, registros offline devem receber NSR no momento da sincronização | CRÍTICO |

### Épico 2.2 — Auditoria e Inviolabilidade

| ID | User Story | Prioridade |
|---|---|---|
| PB-060 | Como sistema, devo manter log imutável de todas as ações (quem acessou, exportou, configurou) | CRÍTICO |
| PB-061 | Como sistema, nenhum registro de ponto pode ser deletado ou editado | CRÍTICO |
| PB-062 | Como admin, quero registrar justificativas de ajuste que geram novo NSR sem alterar o original | ALTA |

---

## FASE 3 — Gestão Operacional (Semanas 8 a 10)

### Épico 3.1 — Jornadas e Escalas

| ID | User Story | Prioridade |
|---|---|---|
| PB-070 | Como admin, quero configurar múltiplos tipos de jornada (fixo, 12x36, turnos) | ALTA |
| PB-071 | Como admin, quero vincular funcionários a jornadas específicas | ALTA |
| PB-072 | Como sistema, devo calcular horas trabalhadas, extras e banco de horas | ALTA |
| PB-073 | Como admin, quero visualizar o banco de horas por funcionário | MÉDIA |

### Épico 3.2 — Relatórios e Dashboard

| ID | User Story | Prioridade |
|---|---|---|
| PB-080 | Como admin, quero um dashboard com frequência em tempo real | ALTA |
| PB-081 | Como admin, quero relatório de faltas e atrasos por período | ALTA |
| PB-082 | Como admin, quero relatório de horas extras por funcionário | ALTA |
| PB-083 | Como admin, quero exportar relatórios em PDF e XLSX | MÉDIA |

### Épico 3.3 — Gestão de Afastamentos

| ID | User Story | Prioridade |
|---|---|---|
| PB-090 | Como admin, quero registrar férias, atestados e outros afastamentos | ALTA |
| PB-091 | Como sistema, afastamentos devem ser considerados no cálculo de jornada | ALTA |

---

## FASE 4 — Hardening, SaaS e INPI (Semanas 11 a 13)

### Épico 4.1 — SaaS e Onboarding

| ID | User Story | Prioridade |
|---|---|---|
| PB-100 | Como empresa, quero me cadastrar no sistema de forma self-service | ALTA |
| PB-101 | Como sistema, devo ter planos com limites de funcionários | ALTA |
| PB-102 | Como admin master, quero gerenciar todos os tenants | ALTA |

### Épico 4.2 — Segurança e LGPD

| ID | User Story | Prioridade |
|---|---|---|
| PB-110 | Como sistema, devo exibir e registrar o consentimento do funcionário para uso de biometria | CRÍTICO |
| PB-111 | Como sistema, devo ter política de retenção de dados biométricos configurável | ALTA |
| PB-112 | Como admin, quero solicitar exclusão dos dados biométricos de um funcionário | ALTA |
| PB-113 | Como sistema, devo ter backup criptografado com verificação de integridade | ALTA |

### Épico 4.3 — Documentação INPI

| ID | User Story | Prioridade |
|---|---|---|
| PB-120 | Como produto, devo ter documentação técnica completa para depósito no INPI | CRÍTICO |
| PB-121 | Como produto, devo ter declaração de conformidade técnica com a Portaria 671/2021 | CRÍTICO |
| PB-122 | Como produto, devo ter manual do usuário nos moldes exigidos pelo INPI | ALTA |

### Épico 4.4 — Evoluções de Integração WhatsApp

| ID | User Story | Prioridade |
|---|---|---|
| PB-130 | Como sistema, quero usar um adapter pluggable de WhatsApp para trocar o provider sem alterar o fluxo negocial | ALTA |
| PB-131 | Como produto, quero manter suporte futuro a `Evolution API` como alternativa ao provider inicial | MÉDIA |
| PB-132 | Como produto, quero evoluir para `Meta WhatsApp Cloud API` ou BSP oficial caso haja ganho de escala, compliance ou estabilidade operacional | MÉDIA |
