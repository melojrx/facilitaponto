"""Views web (HTML) para landing e autenticação inicial."""

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.validators import only_digits
from apps.attendance.forms import TimeClockForm
from apps.attendance.models import TimeClock
from apps.attendance.services import TimeClockService
from apps.biometrics.forms import AssistedBiometricCaptureForm
from apps.biometrics.services import AssistedBiometricCaptureService, BiometricInviteService
from apps.employees.forms import EmployeeRegistrationForm, WorkScheduleForm
from apps.employees.models import Employee, WorkSchedule
from apps.employees.services import EmployeeRegistrationService
from core.tenant_resolution import resolve_tenant_from_user

from .forms import CompanyOnboardingForm, LoginForm, ProfileForm, SignupForm
from .rate_limit import is_web_login_limited, is_web_signup_limited

PANEL_MENU = [
    {
        "key": "inicio",
        "label": "Início",
        "url_name": "web:painel",
        "min_step": 1,
        "locked_reason": "",
    },
    {
        "key": "empresa",
        "label": "Empresa",
        "url_name": "web:company",
        "min_step": 1,
        "locked_reason": "",
    },
    {
        "key": "jornadas",
        "label": "Jornadas de Trabalho",
        "url_name": "web:jornadas",
        "min_step": 2,
        "locked_reason": "Cadastre sua empresa para liberar Jornadas de Trabalho.",
    },
    {
        "key": "colaboradores",
        "label": "Colaboradores",
        "url_name": "web:colaboradores",
        "min_step": 3,
        "locked_reason": "Cadastre a primeira jornada para liberar Colaboradores.",
    },
    {
        "key": "relogio_digital",
        "label": "Relógio Digital",
        "url_name": "web:relogio_digital",
        "min_step": 3,
        "locked_reason": "Cadastre a primeira jornada para liberar Relógio Digital.",
    },
    {
        "key": "tratamento_ponto",
        "label": "Tratamento de Ponto",
        "url_name": "web:tratamento_ponto",
        "min_step": 3,
        "locked_reason": "Cadastre a primeira jornada para liberar Tratamento de Ponto.",
    },
    {
        "key": "relatorios",
        "label": "Relatórios",
        "url_name": "web:relatorios",
        "min_step": 3,
        "locked_reason": "Cadastre a primeira jornada para liberar Relatórios.",
    },
    {
        "key": "solicitacoes",
        "label": "Solicitações",
        "url_name": "web:solicitacoes",
        "min_step": 3,
        "locked_reason": "Cadastre a primeira jornada para liberar Solicitações.",
    },
    {
        "key": "configuracoes",
        "label": "Configurações",
        "url_name": "web:configuracoes",
        "min_step": 3,
        "locked_reason": "Cadastre a primeira jornada para liberar Configurações.",
        "children": [
            {"label": "Banco de Horas", "url": "#"},
            {"label": "Feriados", "url": "#"},
        ],
    },
]

PANEL_MENU_INDEX = {item["key"]: item for item in PANEL_MENU}


def _resolve_next_url(request, default_url):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return default_url


def _get_onboarding_step(user):
    tenant = _resolve_user_tenant(user)
    if not tenant:
        return 1
    # Empresa encontrada já representa step mínimo 2.
    return max(2, int(tenant.onboarding_step or 2))


def _get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or None
    return request.META.get("REMOTE_ADDR")


def _self_enroll_feedback(*, success=False, error_message=""):
    if success:
        return {
            "tone": "success",
            "title": "Cadastro facial concluído",
            "message": "Seu consentimento foi registrado e a biometria facial foi concluída com sucesso.",
            "hint": "Você já pode fechar esta página e seguir com a operação normal do ponto.",
        }

    normalized = (error_message or "").strip()
    lowered = normalized.lower()

    if "expir" in lowered:
        title = "Link expirado"
        hint = "Solicite um novo envio ao gestor da empresa para concluir o cadastro facial."
    elif "utilizado" in lowered:
        title = "Link já utilizado"
        hint = "Se precisar refazer o cadastro facial, solicite um novo envio ao gestor."
    elif "revogado" in lowered or "substitu" in lowered:
        title = "Link substituído"
        hint = "Solicite o link mais recente ao gestor para seguir com o cadastro facial."
    else:
        title = "Link indisponível"
        hint = "Se o problema persistir, solicite um novo envio ao gestor da empresa."

    return {
        "tone": "error",
        "title": title,
        "message": normalized or "Link de cadastro facial inválido ou indisponível.",
        "hint": hint,
    }


def _resolve_user_tenant(user):
    return resolve_tenant_from_user(user)


def _build_panel_context(request, current_menu):
    tenant = _resolve_user_tenant(request.user)
    onboarding_step = _get_onboarding_step(request.user)
    has_company = tenant is not None
    company_name = tenant.razao_social if tenant else "Sem empresa cadastrada"

    menu_items = []
    for item in PANEL_MENU:
        enabled = onboarding_step >= item["min_step"]
        menu_items.append(
            {
                "key": item["key"],
                "label": item["label"],
                "url": reverse(item["url_name"]) if enabled else "#",
                "enabled": enabled,
                "active": item["key"] == current_menu,
                "locked_reason": item["locked_reason"],
                "children": item.get("children", []),
            }
        )

    if onboarding_step <= 1:
        completed_points = 1
    elif onboarding_step == 2:
        completed_points = 2
    else:
        completed_points = 8

    current_point = min(9, completed_points + 1)
    stepper = []
    for point in range(1, 10):
        if point <= completed_points:
            state = "done"
        elif point == current_point:
            state = "current"
        else:
            state = "locked"
        stepper.append({"position": point, "state": state})

    progress = int((completed_points / 9) * 100)
    initials = f"{(request.user.first_name or 'U')[:1]}{(request.user.last_name or '')[:1]}".upper()
    user_display_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email

    return {
        "has_company": has_company,
        "company_name": company_name,
        "user_initials": initials,
        "user_display_name": user_display_name,
        "onboarding_step": onboarding_step,
        "onboarding_progress": progress,
        "menu_items": menu_items,
        "current_menu": current_menu,
        "stepper": stepper,
    }


def _render_panel(request, template_name, current_menu, extra_context=None):
    context = _build_panel_context(request, current_menu=current_menu)
    if extra_context:
        context.update(extra_context)
    return render(request, template_name, context)


def _require_step_or_redirect(request, min_step):
    current_step = _get_onboarding_step(request.user)
    if current_step >= min_step:
        return None

    prerequisite = "Cadastre sua empresa primeiro." if min_step == 2 else "Cadastre a primeira jornada primeiro."
    messages.warning(request, f"Módulo bloqueado. {prerequisite}")
    return redirect("web:painel")


def landing_view(request):
    if request.user.is_authenticated:
        return redirect("web:painel")
    return render(request, "web/landing.html")


@require_http_methods(["GET", "POST"])
def biometric_self_enroll_view(request):
    token = (request.POST.get("token") or request.GET.get("token") or "").strip()
    invite_service = BiometricInviteService()
    invite = None
    form = AssistedBiometricCaptureForm(
        initial={"versao_termo": BiometricInviteService.SELF_ENROLL_TERM_VERSION}
    )
    success = False
    error_message = ""
    feedback = None

    if request.method == "POST":
        try:
            invite = invite_service.get_invite_for_token(raw_token=token)
        except DjangoValidationError as exc:
            error_message = exc.messages[0]
            feedback = _self_enroll_feedback(error_message=error_message)
        else:
            form = AssistedBiometricCaptureForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    invite_service.complete_self_enroll(
                        raw_token=token,
                        imagem_bytes=form.cleaned_data["imagem_bytes"],
                        consentimento_aceito=form.cleaned_data["consentimento"],
                        versao_termo=form.cleaned_data["versao_termo"],
                        ip_origem=_get_client_ip(request),
                    )
                except DjangoValidationError as exc:
                    error_message = exc.messages[0]
                    feedback = _self_enroll_feedback(error_message=error_message)
                else:
                    success = True
                    feedback = _self_enroll_feedback(success=True)
            else:
                error_message = "Revise os dados e tente novamente."
    elif token:
        try:
            invite = invite_service.get_invite_for_token(raw_token=token)
        except DjangoValidationError as exc:
            error_message = exc.messages[0]
            feedback = _self_enroll_feedback(error_message=error_message)
    else:
        error_message = "Link de cadastro facial invalido ou expirado."
        feedback = _self_enroll_feedback(error_message=error_message)

    return render(
        request,
        "web/biometric_self_enroll.html",
        {
            "invite": invite,
            "form": form,
            "token": token,
            "success": success,
            "error_message": error_message,
            "feedback": feedback,
        },
    )


@require_http_methods(["GET", "POST"])
def signup_view(request):
    if request.user.is_authenticated:
        return redirect("web:painel")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if is_web_signup_limited(request):
            form.add_error(None, "Muitas tentativas de cadastro. Tente novamente em instantes.")
            return render(request, "web/signup.html", {"form": form}, status=429)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Conta criada com sucesso.")
            return redirect("web:painel")
    else:
        form = SignupForm()

    return render(request, "web/signup.html", {"form": form})


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("web:painel")

    if request.method == "POST":
        form = LoginForm(request.POST, request=request)
        if is_web_login_limited(request):
            form.add_error(None, "Muitas tentativas de login. Tente novamente em instantes.")
            return render(
                request,
                "web/login.html",
                {"form": form, "next": _resolve_next_url(request, "")},
                status=429,
            )
        if form.is_valid():
            login(request, form.cleaned_data["user"])
            messages.success(request, "Login realizado com sucesso.")
            return redirect(_resolve_next_url(request, "/painel/"))
    else:
        form = LoginForm(request=request)

    return render(
        request,
        "web/login.html",
        {"form": form, "next": _resolve_next_url(request, "")},
    )


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Sessão encerrada.")
    return redirect("web:landing")


@login_required(login_url="/login/")
def painel_view(request):
    onboarding_step = _get_onboarding_step(request.user)
    return _render_panel(
        request,
        "web/painel.html",
        current_menu="inicio",
        extra_context={
            "show_company_cta": onboarding_step == 1,
            "show_journey_cta": onboarding_step == 2,
            "show_full_access": onboarding_step >= 3,
        },
    )


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def create_company_view(request):
    if _resolve_user_tenant(request.user):
        messages.info(request, "Sua conta já possui empresa vinculada.")
        return redirect("web:company")

    if request.method == "POST":
        form = CompanyOnboardingForm(request.POST)
        if form.is_valid():
            form.save(request.user)
            messages.success(request, "Empresa cadastrada com sucesso.")
            return redirect("web:painel")
    else:
        form = CompanyOnboardingForm(initial={"tipo_pessoa": "PJ"})

    return _render_panel(
        request,
        "web/company_create.html",
        current_menu="empresa",
        extra_context={"form": form},
    )


@login_required(login_url="/login/")
@require_http_methods(["GET"])
def company_view(request):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        return redirect("web:company_create")

    return _render_panel(
        request,
        "web/company_detail.html",
        current_menu="empresa",
        extra_context={"tenant": tenant},
    )


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def company_edit_view(request):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        return redirect("web:company_create")

    if request.method == "POST":
        form = CompanyOnboardingForm(request.POST, existing_tenant=tenant)
        if form.is_valid():
            form.save(request.user)
            messages.success(request, "Empresa atualizada com sucesso.")
            return redirect("web:company")
    else:
        form = CompanyOnboardingForm(
            initial=CompanyOnboardingForm.initial_from_tenant(tenant),
            existing_tenant=tenant,
        )

    return _render_panel(
        request,
        "web/company_create.html",
        current_menu="empresa",
        extra_context={
            "form": form,
            "is_edit_mode": True,
        },
    )


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def profile_view(request):
    initial = {
        "first_name": request.user.first_name,
        "last_name": request.user.last_name,
        "email": request.user.email,
        "cpf": request.user.cpf or "",
        "phone": request.user.phone or "",
    }

    if request.method == "POST":
        form = ProfileForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil atualizado com sucesso.")
            return redirect("web:profile")
    else:
        form = ProfileForm(initial=initial, user=request.user)

    return _render_panel(
        request,
        "web/profile.html",
        current_menu="",
        extra_context={"form": form},
    )


@login_required(login_url="/login/")
@require_http_methods(["GET"])
def module_placeholder_view(request, module_key):
    item = PANEL_MENU_INDEX.get(module_key)
    if not item:
        return redirect("web:painel")

    guard_redirect = _require_step_or_redirect(request, min_step=item["min_step"])
    if guard_redirect:
        return guard_redirect

    return _render_panel(
        request,
        "web/panel_placeholder.html",
        current_menu=item["key"],
        extra_context={"module_title": item["label"]},
    )


@login_required(login_url="/login/")
@require_http_methods(["GET"])
def collaborator_list_view(request):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(request, "Cadastre sua empresa antes de acessar Colaboradores.")
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=3)
    if guard_redirect:
        return guard_redirect

    collaborator_query = (request.GET.get("q") or "").strip()
    collaborator_schedule_filter = (request.GET.get("work_schedule") or "").strip()
    collaborator_tab = (request.GET.get("status") or "ativos").strip().lower()
    if collaborator_tab not in {"ativos", "inativos", "transferidos"}:
        collaborator_tab = "ativos"

    filtered_qs = (
        Employee.all_objects.filter(tenant=tenant)
        .select_related("work_schedule")
        .prefetch_related("consentimentos_biometricos", "facial_embeddings", "biometric_invites")
    )
    if collaborator_query:
        query_digits = only_digits(collaborator_query)
        query_filter = Q(nome__icontains=collaborator_query)
        if query_digits:
            query_filter |= Q(cpf__icontains=query_digits) | Q(pis__icontains=query_digits)
        filtered_qs = filtered_qs.filter(query_filter)

    active_schedules = list(
        WorkSchedule.all_objects.filter(tenant=tenant, ativo=True).order_by("nome")
    )
    if collaborator_schedule_filter:
        filtered_qs = filtered_qs.filter(work_schedule_id=collaborator_schedule_filter)

    active_count = filtered_qs.filter(ativo=True).count()
    inactive_count = filtered_qs.filter(ativo=False).count()
    transferred_count = 0

    if collaborator_tab == "ativos":
        filtered_qs = filtered_qs.filter(ativo=True)
    elif collaborator_tab == "inativos":
        filtered_qs = filtered_qs.filter(ativo=False)
    else:
        filtered_qs = filtered_qs.none()

    collaborators = []
    for employee in filtered_qs.order_by("nome"):
        biometric_snapshot = employee.biometric_snapshot()
        collaborators.append(
            {
                "id": employee.id,
                "nome": employee.nome,
                "departamento": employee.departamento or "-",
                "funcao": employee.funcao or "-",
                "status_label": "Ativo" if employee.ativo else "Inativo",
                "status_class": "active" if employee.ativo else "inactive",
                "biometric_label": biometric_snapshot["label"],
                "biometric_class": biometric_snapshot["status"].lower(),
                "biometric_detail": biometric_snapshot["detail"],
                "journey_label": employee.work_schedule.nome if employee.work_schedule else "-",
                "edit_url": reverse("web:colaborador_edit", kwargs={"employee_id": employee.id}),
                "capture_biometric_url": (
                    reverse("web:colaborador_edit", kwargs={"employee_id": employee.id})
                    + "?open_biometric_modal=1"
                ),
                "whatsapp_invite_url": (
                    reverse("web:colaborador_edit", kwargs={"employee_id": employee.id})
                    + "?open_whatsapp_modal=1"
                ),
                "toggle_status_url": reverse(
                    "web:colaborador_status_toggle",
                    kwargs={"employee_id": employee.id},
                ),
                "toggle_status_label": "Inativar" if employee.ativo else "Reativar",
                "toggle_status_icon": "inactive" if employee.ativo else "active",
            }
        )

    return _render_panel(
        request,
        "web/employee_list.html",
        current_menu="colaboradores",
        extra_context={
            "collaborators": collaborators,
            "collaborator_total": len(collaborators),
            "collaborator_query": collaborator_query,
            "collaborator_schedule_filter": collaborator_schedule_filter,
            "collaborator_tab": collaborator_tab,
            "collaborator_tabs": [
                {"key": "ativos", "label": f"Ativos ({active_count})", "count": active_count},
                {"key": "inativos", "label": f"Inativos ({inactive_count})", "count": inactive_count},
                {
                    "key": "transferidos",
                    "label": f"Transferidos ({transferred_count})",
                    "count": transferred_count,
                },
            ],
            "collaborator_schedule_options": active_schedules,
            "collaborator_is_filtered": bool(collaborator_query or collaborator_schedule_filter or collaborator_tab != "ativos"),
        },
    )


def _get_time_clock_or_404(*, tenant, time_clock_id):
    try:
        return (
            TimeClock.all_objects.filter(tenant=tenant)
            .select_related("created_by", "geofence")
            .annotate(assignments_total=Count("employee_assignments", distinct=True))
            .get(id=time_clock_id)
        )
    except TimeClock.DoesNotExist as exc:
        raise Http404 from exc


def _time_clock_status_class(status):
    return {
        TimeClock.Status.ATIVO: "active",
        TimeClock.Status.INATIVO: "inactive",
        TimeClock.Status.EM_MANUTENCAO: "maintenance",
    }[status]


def _time_clock_next_redirect(request, *, default_url):
    return _resolve_next_url(request, default_url)


def _clock_employee_initials(employee):
    parts = [part for part in (employee.nome or "").split() if part]
    if not parts:
        return "CL"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][:1]}{parts[-1][:1]}".upper()


def _serialize_clock_employee(employee):
    return {
        "id": employee.id,
        "nome": employee.nome,
        "matricula": employee.matricula_interna or "-",
        "cpf": employee.cpf,
        "initials": _clock_employee_initials(employee),
    }


def _build_time_clock_assignment_context(*, time_clock, available_search="", assigned_search=""):
    service = TimeClockService()
    available_employees = list(
        service.available_employees_queryset(
            time_clock=time_clock,
            search=available_search,
        )
    )
    assigned_employees = list(
        service.assigned_employees_queryset(
            time_clock=time_clock,
            search=assigned_search,
        )
    )
    return {
        "time_clock_available_search": available_search,
        "time_clock_assigned_search": assigned_search,
        "time_clock_available_total": len(available_employees),
        "time_clock_assigned_total": len(assigned_employees),
        "time_clock_available_employees": [
            _serialize_clock_employee(employee) for employee in available_employees
        ],
        "time_clock_assigned_employees": [
            _serialize_clock_employee(employee) for employee in assigned_employees
        ],
    }


@login_required(login_url="/login/")
@require_http_methods(["GET"])
def time_clock_list_view(request):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(request, "Cadastre sua empresa antes de acessar Relógios de Ponto.")
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=3)
    if guard_redirect:
        return guard_redirect

    time_clock_query = (request.GET.get("q") or "").strip()
    time_clock_status_filter = (request.GET.get("status") or "").strip()
    time_clock_rep_filter = (request.GET.get("tipo_rep") or "").strip()

    time_clocks_qs = (
        TimeClock.all_objects.filter(tenant=tenant)
        .select_related("created_by")
        .annotate(assignments_total=Count("employee_assignments", distinct=True))
        .order_by("nome", "created_at")
    )

    if time_clock_query:
        time_clocks_qs = time_clocks_qs.filter(
            Q(nome__icontains=time_clock_query) | Q(descricao__icontains=time_clock_query)
        )

    if time_clock_status_filter:
        time_clocks_qs = time_clocks_qs.filter(status=time_clock_status_filter)

    if time_clock_rep_filter:
        time_clocks_qs = time_clocks_qs.filter(tipo_relogio=time_clock_rep_filter)

    time_clocks = []
    for time_clock in time_clocks_qs:
        created_by_name = "-"
        if time_clock.created_by:
            created_by_name = (
                f"{time_clock.created_by.first_name} {time_clock.created_by.last_name}".strip()
                or time_clock.created_by.email
            )
        time_clocks.append(
            {
                "id": time_clock.id,
                "nome": time_clock.nome,
                "descricao": time_clock.descricao,
                "status": time_clock.status,
                "status_label": time_clock.get_status_display(),
                "status_class": {
                    TimeClock.Status.ATIVO: "active",
                    TimeClock.Status.INATIVO: "inactive",
                    TimeClock.Status.EM_MANUTENCAO: "maintenance",
                }[time_clock.status],
                "rep_badge_label": time_clock.rep_badge_label,
                "created_by_label": created_by_name,
                "assignments_total": getattr(time_clock, "assignments_total", 0),
                "activation_code": time_clock.activation_code,
                "detail_url": reverse(
                    "web:relogio_detail",
                    kwargs={"time_clock_id": time_clock.id},
                ),
                "toggle_status_url": reverse(
                    "web:relogio_status_toggle",
                    kwargs={"time_clock_id": time_clock.id},
                ),
                "toggle_status_label": (
                    "Inativar Relógio"
                    if time_clock.status != TimeClock.Status.INATIVO
                    else "Reativar Relógio"
                ),
            }
        )

    return _render_panel(
        request,
        "web/time_clock_list.html",
        current_menu="relogio_digital",
        extra_context={
            "time_clocks": time_clocks,
            "time_clock_total": len(time_clocks),
            "time_clock_query": time_clock_query,
            "time_clock_status_filter": time_clock_status_filter,
            "time_clock_rep_filter": time_clock_rep_filter,
            "time_clock_status_options": TimeClock.Status.choices,
            "time_clock_rep_options": (
                (TimeClock.TipoRelogio.APLICATIVO, "REP-P (Programa/Software)"),
            ),
            "time_clock_is_filtered": bool(
                time_clock_query or time_clock_status_filter or time_clock_rep_filter
            ),
        },
    )


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def create_time_clock_view(request):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(request, "Cadastre sua empresa antes de criar um relógio.")
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=3)
    if guard_redirect:
        return guard_redirect

    if request.method == "POST":
        form = TimeClockForm(request.POST, tenant=tenant, user=request.user)
        if form.is_valid():
            time_clock = form.save()
            if time_clock:
                messages.success(request, "Relógio criado com sucesso.")
                return redirect("web:relogio_digital")
    else:
        form = TimeClockForm(tenant=tenant, user=request.user)

    return _render_panel(
        request,
        "web/time_clock_create.html",
        current_menu="relogio_digital",
        extra_context={
            "form": form,
            "form_action_url": reverse("web:relogio_create"),
        },
    )


@login_required(login_url="/login/")
@require_POST
def toggle_time_clock_status_view(request, time_clock_id):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(request, "Cadastre sua empresa antes de alterar o status de um relógio.")
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=3)
    if guard_redirect:
        return guard_redirect

    time_clock = _get_time_clock_or_404(tenant=tenant, time_clock_id=time_clock_id)
    next_status = (
        TimeClock.Status.INATIVO
        if time_clock.status != TimeClock.Status.INATIVO
        else TimeClock.Status.ATIVO
    )
    TimeClockService().update_time_clock_status(time_clock=time_clock, status=next_status)
    if next_status == TimeClock.Status.INATIVO:
        messages.success(request, "Relógio inativado com sucesso.")
    else:
        messages.success(request, "Relógio reativado com sucesso.")
    return redirect(
        _time_clock_next_redirect(
            request,
            default_url=reverse("web:relogio_digital"),
        )
    )


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def time_clock_detail_view(request, time_clock_id):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(request, "Cadastre sua empresa antes de acessar Relógios de Ponto.")
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=3)
    if guard_redirect:
        return guard_redirect

    time_clock = _get_time_clock_or_404(tenant=tenant, time_clock_id=time_clock_id)
    active_tab = (request.GET.get("aba") or request.POST.get("aba") or "informacoes").strip().lower()
    if active_tab not in {"informacoes", "colaboradores"}:
        active_tab = "informacoes"

    available_search = (request.GET.get("available_q") or request.POST.get("available_q") or "").strip()
    assigned_search = (request.GET.get("assigned_q") or request.POST.get("assigned_q") or "").strip()

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        service = TimeClockService()
        try:
            if action == "assign_selected":
                moved_total = service.assign_employees(
                    time_clock=time_clock,
                    employee_ids=request.POST.getlist("available_employee_ids"),
                )
                messages.success(request, f"{moved_total} colaborador(es) atribuídos ao relógio.")
            elif action == "assign_all":
                moved_total = service.assign_all_employees(
                    time_clock=time_clock,
                    search=available_search,
                )
                messages.success(request, f"{moved_total} colaborador(es) atribuídos ao relógio.")
            elif action == "remove_selected":
                removed_total = service.remove_employees(
                    time_clock=time_clock,
                    employee_ids=request.POST.getlist("assigned_employee_ids"),
                )
                messages.success(request, f"{removed_total} colaborador(es) removidos do relógio.")
            elif action == "remove_all":
                removed_total = service.remove_all_employees(
                    time_clock=time_clock,
                    search=assigned_search,
                )
                messages.success(request, f"{removed_total} colaborador(es) removidos do relógio.")
            else:
                messages.warning(request, "Ação de colaboradores inválida para este relógio.")
        except DjangoValidationError as exc:
            messages.error(request, " ".join(exc.messages))

        query_suffix = urlencode(
            {
                "aba": "colaboradores",
                "available_q": available_search,
                "assigned_q": assigned_search,
            }
        )
        return redirect(
            f"{reverse('web:relogio_detail', kwargs={'time_clock_id': time_clock.id})}?{query_suffix}"
        )

    detail_url = reverse("web:relogio_detail", kwargs={"time_clock_id": time_clock.id})
    geofence = getattr(time_clock, "geofence", None)
    created_by_name = "-"
    if time_clock.created_by:
        created_by_name = (
            f"{time_clock.created_by.first_name} {time_clock.created_by.last_name}".strip()
            or time_clock.created_by.email
        )

    return _render_panel(
        request,
        "web/time_clock_detail.html",
        current_menu="relogio_digital",
        extra_context={
            "time_clock": time_clock,
            "time_clock_active_tab": active_tab,
            "time_clock_detail_url": detail_url,
            "time_clock_edit_url": reverse(
                "web:relogio_edit",
                kwargs={"time_clock_id": time_clock.id},
            ),
            "time_clock_status_class": _time_clock_status_class(time_clock.status),
            "time_clock_created_by_label": created_by_name,
            "time_clock_last_synced_label": (
                time_clock.last_synced_at.strftime("%d/%m/%Y %H:%M")
                if time_clock.last_synced_at
                else "Nunca sincronizado"
            ),
            "time_clock_created_at_label": time_clock.created_at.strftime("%d/%m/%Y %H:%M"),
            "time_clock_geofence": geofence,
            "time_clock_geofence_label": (
                f"{geofence.raio_metros}m • {geofence.latitude}, {geofence.longitude}"
                if geofence and geofence.ativo
                else "Nenhuma cerca virtual configurada."
            ),
            "time_clock_toggle_status_url": reverse(
                "web:relogio_status_toggle",
                kwargs={"time_clock_id": time_clock.id},
            ),
            "time_clock_tabs": [
                {
                    "key": "informacoes",
                    "label": "Informações",
                    "url": detail_url,
                },
                {
                    "key": "colaboradores",
                    "label": "Colaboradores",
                    "url": f"{detail_url}?aba=colaboradores",
                },
            ],
            **_build_time_clock_assignment_context(
                time_clock=time_clock,
                available_search=available_search,
                assigned_search=assigned_search,
            ),
        },
    )


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def edit_time_clock_view(request, time_clock_id):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(request, "Cadastre sua empresa antes de editar um relógio.")
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=3)
    if guard_redirect:
        return guard_redirect

    time_clock = _get_time_clock_or_404(tenant=tenant, time_clock_id=time_clock_id)

    if request.method == "POST":
        form = TimeClockForm(
            request.POST,
            tenant=tenant,
            user=request.user,
            instance=time_clock,
        )
        if form.is_valid():
            updated_time_clock = form.save()
            if updated_time_clock:
                messages.success(request, "Relógio atualizado com sucesso.")
                return redirect(
                    "web:relogio_detail",
                    time_clock_id=updated_time_clock.id,
                )
    else:
        form = TimeClockForm(
            tenant=tenant,
            user=request.user,
            instance=time_clock,
        )

    return _render_panel(
        request,
        "web/time_clock_create.html",
        current_menu="relogio_digital",
        extra_context={
            "form": form,
            "time_clock": time_clock,
            "is_edit_mode": True,
            "form_action_url": reverse(
                "web:relogio_edit",
                kwargs={"time_clock_id": time_clock.id},
            ),
            "time_clock_detail_url": reverse(
                "web:relogio_detail",
                kwargs={"time_clock_id": time_clock.id},
            ),
        },
    )


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def create_collaborator_view(request):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(request, "Cadastre sua empresa antes de criar um colaborador.")
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=3)
    if guard_redirect:
        return guard_redirect

    has_active_schedule = WorkSchedule.all_objects.filter(tenant=tenant, ativo=True).exists()
    if not has_active_schedule:
        messages.warning(request, "Cadastre uma jornada ativa antes de criar colaboradores.")
        return redirect("web:jornadas")

    if request.method == "POST":
        form = EmployeeRegistrationForm(request.POST, tenant=tenant)
        if form.is_valid():
            employee = form.save()
            if employee:
                messages.success(request, "Colaborador criado com sucesso. Biometria pendente de conclusão.")
                return redirect("web:colaboradores")
    else:
        form = EmployeeRegistrationForm(tenant=tenant)

    return _render_panel(
        request,
        "web/employee_create.html",
        current_menu="colaboradores",
        extra_context={
            "form": form,
            "form_action_url": reverse("web:colaborador_create"),
            "is_edit_mode": False,
        },
    )


def _get_collaborator_or_404(*, tenant, employee_id):
    try:
        return (
            Employee.all_objects.filter(tenant=tenant)
            .select_related("work_schedule")
            .prefetch_related("consentimentos_biometricos", "facial_embeddings", "biometric_invites")
            .get(id=employee_id)
        )
    except Employee.DoesNotExist as exc:
        raise Http404 from exc


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def edit_collaborator_view(request, employee_id):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(request, "Cadastre sua empresa antes de editar um colaborador.")
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=3)
    if guard_redirect:
        return guard_redirect

    employee = _get_collaborator_or_404(tenant=tenant, employee_id=employee_id)

    if request.method == "POST":
        form = EmployeeRegistrationForm(request.POST, tenant=tenant, instance=employee)
        if form.is_valid():
            updated_employee = form.save()
            if updated_employee:
                messages.success(request, "Colaborador atualizado com sucesso.")
                return redirect("web:colaboradores")
    else:
        form = EmployeeRegistrationForm(tenant=tenant, instance=employee)

    return _render_panel(
        request,
        "web/employee_create.html",
        current_menu="colaboradores",
        extra_context={
            "form": form,
            "form_action_url": reverse("web:colaborador_edit", kwargs={"employee_id": employee.id}),
            "is_edit_mode": True,
            "employee": employee,
            "employee_biometric": employee.biometric_snapshot(),
            "biometric_capture_form": AssistedBiometricCaptureForm(),
            "biometric_capture_action_url": reverse(
                "web:colaborador_biometria_capture",
                kwargs={"employee_id": employee.id},
            ),
            "biometric_whatsapp_action_url": reverse(
                "web:colaborador_biometria_whatsapp",
                kwargs={"employee_id": employee.id},
            ),
            "open_biometric_modal": request.GET.get("open_biometric_modal") == "1",
            "open_whatsapp_modal": request.GET.get("open_whatsapp_modal") == "1",
            "employee_phone_for_whatsapp": employee.telefone or "",
        },
    )


@login_required(login_url="/login/")
@require_POST
def capture_collaborator_biometric_view(request, employee_id):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(
            request,
            "Cadastre sua empresa antes de realizar a captura biométrica.",
        )
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=3)
    if guard_redirect:
        return guard_redirect

    employee = _get_collaborator_or_404(tenant=tenant, employee_id=employee_id)
    form = AssistedBiometricCaptureForm(request.POST, request.FILES)
    redirect_url = reverse("web:colaborador_edit", kwargs={"employee_id": employee.id})
    retry_url = f"{redirect_url}?open_biometric_modal=1"

    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect(retry_url)

    try:
        AssistedBiometricCaptureService().capture_for_panel(
            employee=employee,
            imagem_bytes=form.cleaned_data["imagem_bytes"],
            consentimento_aceito=form.cleaned_data["consentimento"],
            versao_termo=form.cleaned_data["versao_termo"],
            ip_origem=_get_client_ip(request),
        )
    except DjangoValidationError as exc:
        for error in exc.messages:
            messages.error(request, error)
        return redirect(retry_url)

    messages.success(request, "Cadastro facial concluído com sucesso.")
    return redirect(redirect_url)


@login_required(login_url="/login/")
@require_POST
def send_collaborator_biometric_invite_view(request, employee_id):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(
            request,
            "Cadastre sua empresa antes de enviar convite biométrico.",
        )
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=3)
    if guard_redirect:
        return guard_redirect

    employee = _get_collaborator_or_404(tenant=tenant, employee_id=employee_id)
    redirect_url = reverse("web:colaborador_edit", kwargs={"employee_id": employee.id})
    retry_url = f"{redirect_url}?open_whatsapp_modal=1"

    try:
        BiometricInviteService().send_whatsapp_invite(
            employee=employee,
            requested_by=request.user,
        )
    except (DjangoValidationError, PermissionDenied) as exc:
        errors = exc.messages if hasattr(exc, "messages") else [str(exc)]
        for error in errors:
            messages.error(request, error)
        return redirect(retry_url)

    messages.success(request, "Link de cadastro facial enviado para o WhatsApp do colaborador.")
    return redirect(redirect_url)


@login_required(login_url="/login/")
@require_POST
def toggle_collaborator_status_view(request, employee_id):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(request, "Cadastre sua empresa antes de alterar o status de um colaborador.")
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=3)
    if guard_redirect:
        return guard_redirect

    employee = _get_collaborator_or_404(tenant=tenant, employee_id=employee_id)
    was_active = employee.ativo
    EmployeeRegistrationService.update_employee_status(employee=employee, ativo=not was_active)
    if was_active:
        messages.success(request, "Colaborador inativado com sucesso.")
    else:
        messages.success(request, "Colaborador reativado com sucesso.")
    return redirect("web:colaboradores")


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def create_journey_view(request):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(request, "Cadastre sua empresa antes de criar uma jornada.")
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=2)
    if guard_redirect:
        return guard_redirect

    if request.method == "POST":
        form = WorkScheduleForm(request.POST, tenant=tenant)
        if form.is_valid():
            form.save()
            tenant.onboarding_step = max(3, int(tenant.onboarding_step or 2))
            tenant.save(update_fields=["onboarding_step"])
            messages.success(request, "Jornada criada com sucesso.")
            return redirect("web:jornadas")
    else:
        form = WorkScheduleForm(tenant=tenant)

    return _render_panel(
        request,
        "web/journey_create.html",
        current_menu="jornadas",
        extra_context={
            "form": form,
            "is_edit_mode": False,
            "form_action_url": reverse("web:journey_create"),
        },
    )


def _schedule_usage_warnings(schedule):
    warnings = []
    for relation in schedule._meta.related_objects:
        accessor = relation.get_accessor_name()
        if not accessor:
            continue

        try:
            if relation.one_to_one:
                related_object = getattr(schedule, accessor)
                count = 1 if related_object else 0
            else:
                related_manager = getattr(schedule, accessor, None)
                if not related_manager:
                    continue
                count = related_manager.all().count()
        except Exception:
            continue
        if count > 0:
            warnings.append(
                {
                    "label": relation.related_model._meta.verbose_name_plural,
                    "count": count,
                }
            )
    return warnings


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def edit_journey_view(request, journey_id):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(request, "Cadastre sua empresa antes de editar uma jornada.")
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=2)
    if guard_redirect:
        return guard_redirect

    schedule = get_object_or_404(WorkSchedule.all_objects, tenant=tenant, id=journey_id)

    if request.method == "POST":
        form = WorkScheduleForm(request.POST, tenant=tenant, instance=schedule)
        if form.is_valid():
            form.save()
            messages.success(request, "Jornada atualizada com sucesso.")
            return redirect("web:jornadas")
    else:
        form = WorkScheduleForm(tenant=tenant, instance=schedule)

    return _render_panel(
        request,
        "web/journey_create.html",
        current_menu="jornadas",
        extra_context={
            "form": form,
            "is_edit_mode": True,
            "journey": schedule,
            "form_action_url": reverse("web:journey_edit", kwargs={"journey_id": schedule.id}),
        },
    )


@login_required(login_url="/login/")
@require_POST
def delete_journey_view(request, journey_id):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(request, "Cadastre sua empresa antes de excluir uma jornada.")
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=2)
    if guard_redirect:
        return guard_redirect

    with transaction.atomic():
        schedule = get_object_or_404(
            WorkSchedule.all_objects.select_for_update(),
            tenant=tenant,
            id=journey_id,
        )
        if not schedule.ativo:
            messages.info(request, "A jornada selecionada já está inativa.")
            return redirect("web:jornadas")

        usages = _schedule_usage_warnings(schedule)
        if usages:
            usage_text = ", ".join([f"{item['label']} ({item['count']})" for item in usages])
            messages.error(
                request,
                f"Não foi possível excluir a jornada porque ela possui vínculos ativos: {usage_text}.",
            )
            return redirect("web:jornadas")

        schedule.ativo = False
        schedule.save(update_fields=["ativo"])

    messages.success(request, "Jornada excluída com sucesso.")
    return redirect("web:jornadas")


def _to_minutes(value):
    if not isinstance(value, str):
        return None
    try:
        hour, minute = value.strip().split(":")
        parsed = int(hour) * 60 + int(minute)
    except (TypeError, ValueError):
        return None
    return parsed if 0 <= parsed < (24 * 60) else None


def _format_weekly_hours(minutes):
    if minutes is None:
        return "-"
    return f"{(minutes / 60):.2f}h"


def _schedule_weekly_minutes(schedule):
    config = schedule.configuracao or {}

    if schedule.tipo == WorkSchedule.TipoJornada.SEMANAL:
        total = 0
        for day in config.get("dias", []):
            if not isinstance(day, dict) or day.get("dsr"):
                continue
            for start_key, end_key in (("entrada_1", "saida_1"), ("entrada_2", "saida_2")):
                start = _to_minutes(day.get(start_key))
                end = _to_minutes(day.get(end_key))
                if start is None or end is None or end <= start:
                    continue
                total += end - start
        return total

    if schedule.tipo == WorkSchedule.TipoJornada.X12X36:
        explicit_minutes = config.get("carga_horaria_semanal_minutos")
        if isinstance(explicit_minutes, int) and explicit_minutes >= 0:
            return explicit_minutes
        return None

    if schedule.tipo == WorkSchedule.TipoJornada.FRACIONADA:
        total = 0
        for day in config.get("dias", []):
            if not isinstance(day, dict) or day.get("dsr"):
                continue
            for period in day.get("periodos", []):
                if not isinstance(period, dict):
                    continue
                start = _to_minutes(period.get("inicio"))
                end = _to_minutes(period.get("fim"))
                if start is None or end is None or end <= start:
                    continue
                total += end - start
        return total

    if schedule.tipo == WorkSchedule.TipoJornada.EXTERNA:
        return None

    return None


@login_required(login_url="/login/")
@require_http_methods(["GET"])
def journey_list_view(request):
    tenant = _resolve_user_tenant(request.user)
    if not tenant:
        messages.warning(request, "Cadastre sua empresa antes de acessar Jornadas de Trabalho.")
        return redirect("web:company_create")

    guard_redirect = _require_step_or_redirect(request, min_step=2)
    if guard_redirect:
        return guard_redirect

    query = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "ativo").strip().lower()
    if status_filter not in {"ativo", "inativo", "todos"}:
        status_filter = "ativo"

    schedules_qs = WorkSchedule.all_objects.filter(tenant=tenant)
    if query:
        schedules_qs = schedules_qs.filter(nome__icontains=query)
    if status_filter == "ativo":
        schedules_qs = schedules_qs.filter(ativo=True)
    elif status_filter == "inativo":
        schedules_qs = schedules_qs.filter(ativo=False)

    schedules = []
    for schedule in schedules_qs.order_by("nome"):
        usage_warnings = _schedule_usage_warnings(schedule)
        schedules.append(
            {
                "id": schedule.id,
                "nome": schedule.nome,
                "tipo_label": schedule.get_tipo_display(),
                "weekly_hours_label": _format_weekly_hours(_schedule_weekly_minutes(schedule)),
                "status_label": "Ativo" if schedule.ativo else "Inativo",
                "status_class": "active" if schedule.ativo else "inactive",
                "edit_url": reverse("web:journey_edit", kwargs={"journey_id": schedule.id}),
                "delete_url": reverse("web:journey_delete", kwargs={"journey_id": schedule.id}),
                "usage_warnings": usage_warnings,
                "usage_summary": ", ".join(
                    [f"{item['label']} ({item['count']})" for item in usage_warnings]
                ),
            }
        )

    return _render_panel(
        request,
        "web/journey_list.html",
        current_menu="jornadas",
        extra_context={
            "journeys": schedules,
            "journey_query": query,
            "journey_status_filter": status_filter,
        },
    )
