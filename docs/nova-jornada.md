# Nova Jornada de Trabalho — DEV-008 Etapa 3

## Goal
Implementar o fluxo completo `GET|POST /painel/jornadas/nova/`, fechando o onboarding end-to-end:
salvar primeira jornada → `onboarding_step = 3` → liberar menu.

## Tasks

- [x] **T1** — Model `WorkSchedule` em `apps/employees/models.py` com 4 tipos + tenant-aware → Verify: `makemigrations` sem erros
- [x] **T2** — Migration `0002_workschedule.py` → Verify: `migrate` aplica sem erros
- [x] **T3** — `WorkScheduleForm` em `apps/accounts/forms.py` (validações por tipo) → Verify: instanciar o form sem erro no shell
- [x] **T4** — View `create_journey_view` em `web_views.py` + rota `nova/` em `web_urls.py` → Verify: rota existe no `url --list`
- [x] **T5** — Corrigir CTA em `painel.html` linha 75 → apontar para `web:journey_create` → Verify: HTML revisado
- [x] **T6** — Template `journey_create.html` com os 4 cards de tipo + grade por tipo → Verify: renderiza sem erro 200
- [x] **T7** — Testes em `apps/employees/tests.py` + `apps/accounts/test_web.py` → Verify: `pytest` verde

## Done When
- [ ] `pytest apps/ -k "journey or onboarding"` passa sem falhas
- [ ] Usuário em step=2 acessa `/painel/jornadas/nova/`, preenche e salva → redireciona ao painel com menu liberado
- [ ] Nenhum teste pré-existente quebrado
