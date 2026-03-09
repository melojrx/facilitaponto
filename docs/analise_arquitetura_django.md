# Análise Arquitetural — FacilitaPonto Django Backend (Revisada)

> Snapshot: 2026-03-09 | Base: código atual + docs DEV-008 | Sem alterações de código (somente diagnóstico)

---

## 1. Resumo executivo

A arquitetura atual está **acima da média** para o estágio do projeto: multitenancy está bem implementado, o split de settings está correto e a base de testes é ampla.  
A revisão criteriosa mostrou que a análise anterior estava **parcialmente correta**: os pontos críticos principais procedem, mas havia itens desatualizados que foram removidos nesta versão.

**Conclusão objetiva:**
- Fundação técnica: `✅ sólida`
- Riscos arquiteturais imediatos: `🔴 existem e devem ser tratados`
- Itens de melhoria contextual (MVP/roadmap): `⚠️ parciais`

---

## 2. Pontos Críticos Confirmados (P1)

| # | Ponto crítico | Evidência | Impacto |
|---|---|---|---|
| 1 | Resolução de tenant com side effect e auto-promoção de owner | `backend/apps/accounts/web_views.py:107-143` | Risco de vínculo indevido de usuário a tenant por heurística (email/CPF) e alteração automática de permissão (`is_account_owner`) |
| 2 | Dependência cruzada de domínio (`accounts -> employees`) | `backend/apps/accounts/forms.py:11` + `backend/apps/accounts/forms.py:440-480` | Acoplamento entre apps, piorando testabilidade e evolução de fronteiras de domínio |
| 3 | Duas cadeias paralelas de resolução de tenant (API vs web) | `backend/core/middleware.py:32-38` + `backend/apps/accounts/web_views.py:107-143` | Divergência futura de comportamento e manutenção mais cara |
| 4 | Falta de proteção explícita contra brute-force em autenticação | `backend/apps/accounts/web_views.py:243-260` + `backend/config/settings/base.py:139-151` (sem throttling DRF) | Maior superfície para abuso em login web/API |
| 5 | Exceções de JWT silenciosamente descartadas no middleware | `backend/core/middleware.py:46-53` | Perda de observabilidade e dificuldade de investigação operacional |

### Ação recomendada para P1 (ordem)

1. Extrair `_resolve_user_tenant` para fluxo sem side-effect e mover autocorreção para rotina explícita/administrativa.
2. Mover `WorkScheduleForm` para `apps/employees` e inverter dependência de import.
3. Definir uma única estratégia de resolução de tenant para web e API (ou serviço compartilhado com regras claras).
4. Aplicar rate limit/throttle em rotas de autenticação (web e API).
5. Logar erros de parse/claims JWT (ao menos em DEBUG; ideal com logger estruturado).

---

## 3. Pontos Parciais (P2)

| # | Ponto | Status | Contexto atual | Direção recomendada |
|---|---|---|---|---|
| 6 | `cnpj` + `documento` no `Tenant` | ⚠️ Parcial | Há redundância técnica, mas a documentação DEV-008 prevê compatibilidade temporária durante migração | Planejar migração para fonte única (`documento`) com janela de compatibilidade e limpeza |
| 7 | `onboarding_step` no model `Tenant` | ⚠️ Parcial | Mistura estado de UX com domínio, porém está aderente ao DEV-008 | Manter no curto prazo; evoluir para serviço de progresso com regras centralizadas |
| 8 | `is_account_owner` persistido em campo | ⚠️ Parcial | Funciona no onboarding atual, mas pode conflitar com regra derivada por papel e vínculo | Evoluir para regra derivada de vínculo/role e manter campo apenas se houver necessidade de legado |
| 9 | `web_urls` concentrado em `accounts` | ⚠️ Parcial | Aceitável em MVP, mas já há rotas de jornada de outro domínio | Criar `employees/web_urls.py` quando iniciar expansão do módulo |
| 10 | Lógica de stepper simplificada (`completed_points = 8` para step>=3) | ⚠️ Parcial | Coerente com liberação rápida do MVP, mas sem granularidade real de progresso | Extrair cálculo de progresso para serviço e alinhar com estados funcionais reais |
| 11 | `User.tenant` com `on_delete=CASCADE` | ⚠️ Parcial | Pode ser decisão de negócio válida para encerramento total do tenant | Confirmar política de retenção/auditoria; considerar soft-delete/PROTECT conforme compliance |
| 12 | `WorkSchedule.configuracao` sem schema | ⚠️ Parcial | Não quebra MVP, mas cria risco de payload inconsistente por tipo de jornada | Validar por tipo (serializer/schema/versionamento) |
| 13 | `Tenant` sem `updated_at` | ⚠️ Parcial | Não impede operação, mas reduz rastreabilidade | Adicionar `updated_at` para auditoria básica |
| 14 | `CONN_MAX_AGE` ausente | ⚠️ Parcial | Sem pool persistente via Django | Definir valor por ambiente e validar impacto no banco |
| 15 | Dependências de ML no requirements principal (`deepface`, `tf-keras`) | ⚠️ Parcial | Funciona, porém aumenta custo de build/deploy em cenários sem biometria | Separar em extra/arquivo dedicado (`requirements/ml.txt`) |
| 16 | `psycopg2-binary` no runtime geral | ⚠️ Parcial | Aceitável em dev/CI; menos indicado para produção robusta | Planejar troca para `psycopg2` compilado no ambiente de produção |
| 17 | Segurança de transporte incompleta (`SECURE_SSL_REDIRECT` ausente) | ⚠️ Parcial | `HSTS` e cookies secure já existem em produção, mas sem redirect explícito no Django | Adicionar `SECURE_SSL_REDIRECT=True` (ou garantir equivalência no proxy, documentado) |

---

## 4. Pontos Fortes Confirmados

1. Multitenancy com `TenantModelMixin` + `TenantManager` tenant-aware e `contextvars` (`core/tenant_context.py`, `core/managers.py`, `core/middleware.py`).
2. Split de settings (`base/development/production`) com leitura de segredos por ambiente.
3. Custom User consistente (`AbstractBaseUser`, UUID, email como `USERNAME_FIELD`).
4. Boas práticas de segurança já aplicadas no web auth: logout via POST + validação de `next` com `url_has_allowed_host_and_scheme`.
5. Constraints importantes de unicidade por tenant (ex.: NSR e nome de jornada ativa).
6. Cobertura de testes ampla para o estágio atual: **99 testes coletados** em `pytest --collect-only`.

---

## 5. Aderência às melhores práticas Django

### 5.1 O que está aderente
- Organização por apps de domínio.
- Uso correto de managers customizados para isolamento de dados.
- Uso de `transaction.atomic` em pontos sensíveis de gravação.
- Segurança base de sessão/CSRF e hardening relevante em produção (`HSTS`, cookies secure).

### 5.2 O que ainda precisa evoluir
- Fronteiras entre apps (evitar dependências invertidas).
- Camada de serviços para regras de onboarding/progressão (reduzir lógica de negócio em view).
- Controles de abuso (rate limit/throttling).
- Observabilidade em middleware de autenticação/tenant.

---

## 6. Plano objetivo para próxima execução (foco em críticos)

### Etapa 1 (P1 imediato)
1. Corrigir `_resolve_user_tenant` para remover persistência implícita e promoção automática de owner.
2. Mover `WorkScheduleForm` para `employees/forms.py` e ajustar imports/views/tests.

### Etapa 2 (P1 complementar)
3. Unificar resolução de tenant para web/API em serviço reutilizável.
4. Adicionar rate limiting/throttling em autenticação.
5. Incluir logging de exceções de JWT no middleware.

### Etapa 3 (P2 de curto prazo)
6. Ajustar segurança de transporte (`SECURE_SSL_REDIRECT` ou documentação equivalente de proxy).
7. Preparar plano de simplificação de `Tenant` (`documento` como fonte única).

---

## 7. Fechamento

A análise revisada confirma que **não há necessidade de reescrita estrutural**. O projeto tem base técnica boa e evolutiva.  
O ganho mais relevante agora vem de atacar os **P1 arquiteturais** (fronteiras de domínio, consistência de tenant e segurança operacional), que são correções localizadas e de alto retorno.
