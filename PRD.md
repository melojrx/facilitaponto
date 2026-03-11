# PRD — Sistema de Ponto Eletrônico com Reconhecimento Facial
**Versão:** 1.1  
**Data:** 2026-02-28  
**Status:** Em desenvolvimento  

---

## 1. Visão Geral do Produto

Sistema SaaS multitenant de controle de ponto eletrônico com reconhecimento facial, enquadrado como **REP-P (Programa)** conforme **Portaria 671/2021 do Ministério do Trabalho e Emprego (MTE)**. O cliente instala um tablet ou conecta uma webcam na portaria da empresa, acessa o aplicativo mobile, e o sistema opera de forma autônoma com fallback offline.

---

## 2. Problema a Resolver

Empresas precisam de um sistema de ponto eletrônico legalmente válido, simples de operar, sem necessidade de hardware proprietário caro, com reconhecimento facial para evitar fraudes (buddy punching), e que cumpra integralmente as obrigações da Portaria 671/2021.

---

## 2.1 Contexto de Mercado (📌 LEIA ANTES DE QUALQUER DECISÃO TÉCNICA)

> Este documento orienta um produto desenvolvido especificamente para o seguinte contexto. Todas as decisões de arquitetura, tecnologia e escopo devem ser avaliadas à luz desse cenário — **simplicidade e confiabilidade são mais valiosas do que sofisticidade técnica**.

**Mercado-alvo:** Pequenas e médias empresas de **[cidade do interior do Ceará]**, principalmente do **setor têxtil** (confecções, cosúras, estamparias, lavanderia industrial). A cidade concentra um polo local de PMEs, em sua maioria sem nenhum sistema de ponto digital.

**Perfil das empresas clientes:**
- 5 a 200 funcionários por empresa (média estimada: 20-50)
- 1 a 2 pontos de entrada/saída por empresa (portaria única na maioria dos casos)
- 1 tablet na portaria como dispositivo de ponto
- Infra de TI práticamente inexistente — sem servidor local, sem T.I. interno
- Gestões familiares: o comprador é o próprio dono ou gerente administrativo
- Estratégia de vendas: indicação local (boca a boca), sem grande funil digital

**Implicações para o produto:**

| Princípio | Aplicação prática |
|-----------|---------------------|
| **Sem over-engineering** | Não precisamos de Kubernetes, micro-serviços, ML customizado ou infra dedicada por tenant |
| **Escala realista** | Pico de uso: ~20 registros em 5 minutos (virada de turno). Não precisamos de GPU |
| **Confiabilidade sobre perfeição** | O sistema deve funcionar offline e sincronizar com robustez — isso vale mais que acurácia de 99.9% |
| **UX simples** | O operador não tem treino técnico — a portaria é uma costureira. UI deve ser autoexplicativa |
| **Custo de infra baixo** | Um VPS de R$100-200/mês deve ser suficiente para suportar dezenas de tenants |
| **1 desenvolvedor** | Todas as decisões devem considerar mantenabilidade por equipe pequena (solo dev ou duo) |

### Diretriz técnica para integrações de WhatsApp

- O envio de mensagens por WhatsApp deve seguir a mesma lógica do produto: simplicidade, baixo atrito operacional e baixo custo de infraestrutura.
- A implementação deve usar um `adapter pluggable`, sem acoplamento do domínio a um vendor específico.
- Decisão inicial para o MVP web/admin:
  - usar um provider self-hosted de baixo atrito como padrão inicial
  - `WAHA` é a escolha preferencial do primeiro adapter
- Evoluções futuras devem permanecer documentadas e opcionais:
  - `Evolution API`
  - `Meta WhatsApp Cloud API` ou BSP oficial
- A troca de provider não deve exigir reescrita do fluxo de negócio; apenas novo adapter/integrador.

## 3. Público-Alvo

| Persona | Perfil Real |
|---------|-------------|
| **Comprador** | Dono ou gerente de confecção local — toma decisão por indicação de outros empresários da cidade |
| **Operador diário** | Funcionário da portaria — muitas vezes a própria costureira de prontidão. Sem treino técnico |
| **Administrador** | RH da empresa — frequentemente o próprio dono. Acessa o painel via celular ou notebook |
| **Fiscal** | Auditor trabalhista que solicita AFD/AEJ em caso de fiscalização |

---

## 4. Modelo de Negócio

- SaaS multitenant com planos por número de funcionários
- Cada tenant (empresa contratante) tem seus dados completamente isolados
- Cobrança mensal recorrente
- Onboarding self-service via painel web

---

## 5. Arquitetura do Sistema

```
┌─────────────────────────────────────────────────┐
│         PAINEL WEB (Django + Templates)          │
│   Gestão de empresas, funcionários, relatórios  │
│   Geração AFD/AEJ, configurações de jornada     │
└───────────────────┬─────────────────────────────┘
                    │ DRF REST API
┌───────────────────▼─────────────────────────────┐
│              DJANGO BACKEND                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ Tenants  │ │Biometria │ │  AFD/AEJ Engine  │ │
│  │  & Auth  │ │ Engine   │ │  NSR Sequencer   │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
│  ┌──────────┐ ┌──────────┐                       │
│  │ Jornadas │ │Comprovant│                       │
│  │  Rules   │ │   es     │                       │
│  └──────────┘ └──────────┘                       │
└───────┬───────────────────────────────────────── ┘
        │
┌───────▼──────────┬────────────┬──────────────────┐
│   PostgreSQL     │   Redis    │   MinIO/S3       │
│ (dados + NSR     │  (Celery   │ (fotos de        │
│  sequence)       │   broker)  │  registro)       │
└──────────────────┴────────────┴──────────────────┘
        │
┌───────▼──────────────────────────────────────────┐
│         APP MOBILE (React Native / Expo)          │
│   Roda no tablet da portaria                     │
│   Reconhecimento facial (MLKit)                  │
│   Modo offline com SQLite + sync posterior       │
└──────────────────────────────────────────────────┘
```

---

## 6. Componentes do Sistema

### 6.1 Painel Web (Django + Templates)
Interface administrativa acessada pelo RH/gestor via browser.

**Funcionalidades:**
- Gestão de empresas (multitenancy)
- Cadastro e gestão de funcionários
- Configuração de jornadas e escalas
- Visualização do espelho de ponto
- Geração e download de AFD e AEJ
- Gestão de justificativas e ajustes de ponto
- Relatórios de frequência, horas extras e banco de horas
- Configuração do dispositivo (tablet) por empresa

### 6.2 API REST (Django REST Framework)
Serve exclusivamente o app mobile.

**Responsabilidades:**
- Autenticação do dispositivo (JWT com device_id)
- Recebimento e validação de registros de ponto
- Verificação biométrica server-side (quando online)
- Fornecimento dos embeddings para cache local no dispositivo
- Recebimento de registros offline (sincronização)
- Geração e retorno do comprovante eletrônico

### 6.3 App Mobile (React Native + Expo)
Roda em tablet Android na portaria da empresa.

**Responsabilidades:**
- Interface simples para o funcionário bater o ponto
- Captura de imagem via câmera
- Reconhecimento facial online (envia frame para API)
- Reconhecimento facial offline (MLKit embarcado + embeddings cacheados localmente)
- Armazenamento local de registros pendentes (SQLite/WatermelonDB)
- Sincronização automática quando a conexão for restaurada
- Exibição do comprovante após o registro

### 6.4 Engine Biométrica
- **Online:** Processamento server-side com `DeepFace` (modelo **ArcFace** + detector **RetinaFace**)
- **Offline:** MLKit no dispositivo com modelo TFLite embarcado
- Embeddings armazenados criptografados (AES-256) no servidor
- Cache local no dispositivo criptografado com chave derivada do device_id
- Threshold de confiança mínimo configurável (padrão ArcFace: **0.68** distância cosine)
- Anti-spoofing nativo via DeepFace (`anti_spoofing=True`) — bloqueia fraudes por foto
- Foto do momento do registro com hash SHA-256

### 6.5 Engine AFD/AEJ
- Geração do **AFD** (Arquivo Fonte de Dados) conforme Anexo I da Portaria 671/2021
- Geração do **AEJ** (Arquivo Eletrônico de Jornada) conforme Anexo II
- **NSR (Número Sequencial de Registro):** gerado por `sequence` PostgreSQL, único por empresa, estritamente sequencial, imutável
- Validação interna do arquivo antes da exportação
- Registros offline sincronizados recebem NSR no momento da sincronização (não retroativo)

### 6.6 Comprovante Eletrônico
- Emitido imediatamente após cada registro (exigência da Portaria 671)
- Conteúdo mínimo: nome, PIS, data, hora, NSR, tipo de marcação
- Carimbo de tempo RFC 3161 para garantir inviolabilidade
- Exibido na tela do tablet e disponível no portal do funcionário

---

## 7. Requisitos Legais (Portaria 671/2021 — REP-P)

| Requisito | Implementação |
|---|---|
| Registro do programa no INPI | Documentação técnica gerada ao fim do projeto |
| NSR sequencial e inviolável | PostgreSQL sequence por empresa |
| Comprovante eletrônico imediato | Gerado via API após cada registro |
| Arquivo AFD | Engine conforme Anexo I |
| Arquivo AEJ | Engine conforme Anexo II |
| Inviolabilidade dos dados | Registros imutáveis, apenas justificativas |
| Carimbo de tempo | RFC 3161 |

---

## 8. Requisitos de Multitenancy

- Isolamento completo de dados por empresa (schema ou row-level com tenant_id)
- NSR sequencial independente por empresa
- Configurações de jornada independentes por empresa
- Plano de acesso e limites por tenant
- Onboarding self-service

---

## 9. Requisitos de Segurança e LGPD

- Dados biométricos são **dados sensíveis** (Art. 11 LGPD) — exigem consentimento explícito
- Embeddings faciais armazenados criptografados (AES-256)
- Fotos de registro armazenadas com hash para auditoria, com política de retenção
- Logs de acesso imutáveis (quem acessou, exportou, alterou configurações)
- HTTPS obrigatório em todas as comunicações
- Autenticação do dispositivo via JWT com device_id vinculado ao tenant

---

## 10. Requisitos de Disponibilidade e Offline

- O app mobile deve funcionar sem internet
- Modo offline: reconhecimento facial via MLKit + embeddings cacheados
- Registros offline armazenados localmente em SQLite
- Sincronização automática e ordenada ao restaurar conexão
- NSR gerado apenas no servidor (no momento da sincronização para registros offline)
- Flag `origem: offline` nos registros sincronizados (rastreabilidade)

---

## 11. Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Backend | Django 5 + Django REST Framework |
| Frontend Admin | Django Templates + Tailwind CSS (CDN Play) + HTMX + Alpine.js |
| App Mobile | React Native + Expo |
| Biometria Server | DeepFace (ArcFace + RetinaFace) |
| Biometria Mobile | MLKit (Google) via Expo Camera |
| Banco de Dados | PostgreSQL 16 |
| Cache / Broker | Redis |
| Tarefas Assíncronas | Celery + Celery Beat |
| Storage | MinIO (self-hosted) ou AWS S3 |
| Banco Local Mobile | WatermelonDB (SQLite) |
| Containerização | Docker + Docker Compose (DEV local) |
| Proxy Reverso / SSL | Traefik (gerenciado pelo EasyPanel) |
| Hospedagem PROD | EasyPanel na VPS |
| CI/CD | GitHub Actions → EasyPanel webhook |

---

## 12. Fora do Escopo

- Integração com eSocial (obrigação da empresa, não do sistema de ponto)
- Integração com folha de pagamento
- Hardware proprietário (REP-C)
- Módulo financeiro
- App para funcionário consultar ponto (fase futura)

---

## 13. Critérios de Sucesso do MVP

- Funcionário consegue bater o ponto com reconhecimento facial em menos de 5 segundos
- Sistema funciona offline e sincroniza corretamente ao voltar online
- AFD gerado passa na validação do layout da Portaria 671
- Comprovante eletrônico emitido imediatamente após cada registro
- Multitenancy funcionando com pelo menos 2 empresas isoladas
- Rodando na primeira empresa de testes em 1 mês
