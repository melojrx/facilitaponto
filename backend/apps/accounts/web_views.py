"""Views web (HTML) para landing e autenticação inicial."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from .forms import CompanyOnboardingForm, LoginForm, ProfileForm, SignupForm
from apps.tenants.models import Tenant


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


def _resolve_user_tenant(user):
    if user.tenant_id:
        return user.tenant

    candidate_filters = []
    if user.email:
        candidate_filters.append({"email_contato__iexact": user.email})
    if user.cpf:
        candidate_filters.extend(
            [
                {"documento": user.cpf},
                {"cnpj": user.cpf},
                {"responsavel_cpf": user.cpf},
            ]
        )

    if not candidate_filters:
        return None

    qs = Tenant.objects.none()
    for filter_kwargs in candidate_filters:
        qs = qs | Tenant.objects.filter(**filter_kwargs)

    candidates = qs.distinct()
    if candidates.count() != 1:
        return None

    tenant = candidates.first()
    # Auto-correção para manter painel coerente com dados já existentes no banco.
    update_fields = []
    user.tenant = tenant
    update_fields.append("tenant")
    if not user.is_account_owner:
        user.is_account_owner = True
        update_fields.append("is_account_owner")
    user.save(update_fields=update_fields)
    return tenant


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
def signup_view(request):
    if request.user.is_authenticated:
        return redirect("web:painel")

    if request.method == "POST":
        form = SignupForm(request.POST)
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
