"""Views web (HTML) para landing e autenticação inicial."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from .forms import LoginForm, SignupForm


def _resolve_next_url(request, default_url):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return default_url


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
    return render(
        request,
        "web/painel.html",
        {
            "has_company": bool(request.user.tenant_id),
        },
    )
