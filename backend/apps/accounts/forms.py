"""Forms web para autenticação e cadastro."""

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from .models import User
from apps.tenants.models import Tenant


def _only_digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _is_valid_cpf(cpf: str) -> bool:
    if len(cpf) != 11:
        return False
    if cpf == cpf[0] * 11:
        return False

    first_sum = sum(int(cpf[idx]) * (10 - idx) for idx in range(9))
    first_digit = ((first_sum * 10) % 11) % 10
    if first_digit != int(cpf[9]):
        return False

    second_sum = sum(int(cpf[idx]) * (11 - idx) for idx in range(10))
    second_digit = ((second_sum * 10) % 11) % 10
    return second_digit == int(cpf[10])


def _is_valid_cnpj(cnpj: str) -> bool:
    if len(cnpj) != 14:
        return False
    if cnpj == cnpj[0] * 14:
        return False

    first_weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    first_total = sum(int(cnpj[idx]) * first_weights[idx] for idx in range(12))
    first_remainder = first_total % 11
    first_digit = 0 if first_remainder < 2 else 11 - first_remainder
    if first_digit != int(cnpj[12]):
        return False

    second_weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    second_total = sum(int(cnpj[idx]) * second_weights[idx] for idx in range(13))
    second_remainder = second_total % 11
    second_digit = 0 if second_remainder < 2 else 11 - second_remainder
    return second_digit == int(cnpj[13])


class SignupForm(forms.Form):
    first_name = forms.CharField(
        label="Nome",
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "João"}),
    )
    last_name = forms.CharField(
        label="Sobrenome",
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Silva"}),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"placeholder": "voce@empresa.com"}),
    )
    cpf = forms.CharField(
        label="CPF",
        max_length=14,
        widget=forms.TextInput(attrs={"placeholder": "000.000.000-00"}),
    )
    phone = forms.CharField(
        label="Telefone",
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "(00) 00000-0000"}),
    )
    password1 = forms.CharField(
        label="Senha",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Mínimo de 8 caracteres"}),
    )
    password2 = forms.CharField(
        label="Confirmar senha",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Repita a senha"}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def clean_cpf(self):
        digits = _only_digits(self.cleaned_data["cpf"])
        if not _is_valid_cpf(digits):
            raise forms.ValidationError("Informe um CPF válido.")
        if User.objects.filter(cpf=digits).exists():
            raise forms.ValidationError("Já existe uma conta com este CPF.")
        return digits

    def clean_first_name(self):
        value = self.cleaned_data["first_name"].strip()
        if len(value) < 2:
            raise forms.ValidationError("Informe um nome válido.")
        return value

    def clean_last_name(self):
        value = self.cleaned_data["last_name"].strip()
        if len(value) < 2:
            raise forms.ValidationError("Informe um sobrenome válido.")
        return value

    def clean_phone(self):
        raw_value = self.cleaned_data["phone"]
        digits = "".join(ch for ch in raw_value if ch.isdigit())
        if len(digits) not in (10, 11):
            raise forms.ValidationError("Informe um telefone válido com DDD.")
        return digits

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        email = cleaned_data.get("email")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "As senhas não conferem.")

        if password1:
            try:
                validate_password(password1, user=User(email=email))
            except ValidationError as exc:
                self.add_error("password1", exc.messages)

        return cleaned_data

    def save(self):
        return User.objects.create_user(
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            cpf=self.cleaned_data["cpf"],
            phone=self.cleaned_data["phone"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            role=User.Role.ADMIN,
            is_account_owner=True,
            is_active=True,
        )


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"placeholder": "voce@empresa.com"}),
    )
    password = forms.CharField(
        label="Senha",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Sua senha"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email", "").strip().lower()
        password = cleaned_data.get("password")

        if not email or not password:
            return cleaned_data

        user = authenticate(self.request, email=email, password=password)
        if user is None:
            raise forms.ValidationError("E-mail ou senha inválidos.")

        if not user.is_active:
            raise forms.ValidationError("Usuário inativo.")

        cleaned_data["user"] = user
        cleaned_data["email"] = email
        return cleaned_data

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)


class CompanyOnboardingForm(forms.Form):
    CARGO_EMPRESA_CHOICES = [
        ("Dono", "Dono"),
        ("Diretor", "Diretor"),
        ("Socio", "Socio"),
        ("Gerente", "Gerente"),
        ("Coordenador", "Coordenador"),
        ("Colaborador", "Colaborador"),
        ("Outro", "Outro"),
    ]

    tipo_pessoa = forms.ChoiceField(
        label="Tipo de Pessoa",
        choices=Tenant.TipoPessoa.choices,
    )
    documento = forms.CharField(
        label="CNPJ/CPF",
        max_length=18,
        widget=forms.TextInput(attrs={"placeholder": "Digite somente números ou com máscara"}),
    )
    razao_social = forms.CharField(
        label="Razão social / Nome",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Nome da empresa ou do empregador"}),
    )
    nome_fantasia = forms.CharField(
        label="Nome fantasia",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Opcional"}),
    )
    email_contato = forms.EmailField(
        label="E-mail de contato",
        widget=forms.EmailInput(attrs={"placeholder": "contato@empresa.com"}),
    )
    telefone_contato = forms.CharField(
        label="Telefone de contato",
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "(00) 00000-0000"}),
    )
    cep = forms.CharField(
        label="CEP",
        max_length=9,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "00000-000"}),
    )
    logradouro = forms.CharField(label="Logradouro", max_length=255, required=False)
    numero = forms.CharField(label="Número", max_length=20, required=False)
    complemento = forms.CharField(label="Complemento", max_length=255, required=False)
    bairro = forms.CharField(label="Bairro", max_length=120, required=False)
    cidade = forms.CharField(label="Cidade", max_length=120, required=False)
    estado = forms.CharField(label="UF", max_length=2, required=False)
    responsavel_nome = forms.CharField(label="Responsável legal", max_length=255, required=False)
    responsavel_cpf = forms.CharField(label="CPF do responsável", max_length=14, required=False)
    responsavel_cargo = forms.ChoiceField(
        label="Cargo na empresa",
        choices=[("", "Selecione")] + CARGO_EMPRESA_CHOICES,
        required=False,
    )
    logo_url = forms.URLField(
        label="URL do logo",
        required=False,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"placeholder": "https://exemplo.com/logo.png"}),
    )
    website = forms.URLField(
        label="Website",
        required=False,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"placeholder": "https://empresa.com"}),
    )
    cno_caepf = forms.CharField(label="CNO/CAEPF", max_length=20, required=False)
    inscricao_estadual = forms.CharField(label="Inscrição estadual", max_length=30, required=False)
    inscricao_municipal = forms.CharField(label="Inscrição municipal", max_length=30, required=False)

    def __init__(self, *args, **kwargs):
        self.existing_tenant = kwargs.pop("existing_tenant", None)
        super().__init__(*args, **kwargs)

    def clean_razao_social(self):
        value = self.cleaned_data["razao_social"].strip()
        if len(value) < 3:
            raise forms.ValidationError("Informe um nome válido para a empresa.")
        return value

    def clean_telefone_contato(self):
        digits = _only_digits(self.cleaned_data["telefone_contato"])
        if len(digits) not in (10, 11):
            raise forms.ValidationError("Informe um telefone válido com DDD.")
        return digits

    def clean_cep(self):
        digits = _only_digits(self.cleaned_data.get("cep"))
        if digits and len(digits) != 8:
            raise forms.ValidationError("Informe um CEP válido.")
        return digits

    def clean_estado(self):
        value = self.cleaned_data.get("estado", "").strip().upper()
        if value and len(value) != 2:
            raise forms.ValidationError("Informe uma UF válida com 2 caracteres.")
        return value

    def clean_responsavel_cpf(self):
        digits = _only_digits(self.cleaned_data.get("responsavel_cpf"))
        if digits and not _is_valid_cpf(digits):
            raise forms.ValidationError("Informe um CPF válido para o responsável.")
        return digits

    def clean(self):
        cleaned_data = super().clean()
        tipo_pessoa = cleaned_data.get("tipo_pessoa")
        documento = _only_digits(cleaned_data.get("documento"))

        if not documento:
            self.add_error("documento", "Informe o documento da empresa.")
            return cleaned_data

        if tipo_pessoa == Tenant.TipoPessoa.PJ:
            if not _is_valid_cnpj(documento):
                self.add_error("documento", "Informe um CNPJ válido.")
        elif tipo_pessoa == Tenant.TipoPessoa.PF:
            if not _is_valid_cpf(documento):
                self.add_error("documento", "Informe um CPF válido.")

        existing_tenant_qs = Tenant.objects.filter(Q(documento=documento) | Q(cnpj=documento))
        if self.existing_tenant:
            existing_tenant_qs = existing_tenant_qs.exclude(pk=self.existing_tenant.pk)
        if existing_tenant_qs.exists():
            self.add_error("documento", "Já existe uma empresa cadastrada com este documento.")

        cleaned_data["documento"] = documento
        cleaned_data["responsavel_nome"] = cleaned_data.get("responsavel_nome", "").strip()
        cleaned_data["responsavel_cargo"] = cleaned_data.get("responsavel_cargo", "").strip()
        cleaned_data["logradouro"] = cleaned_data.get("logradouro", "").strip()
        cleaned_data["numero"] = cleaned_data.get("numero", "").strip()
        cleaned_data["complemento"] = cleaned_data.get("complemento", "").strip()
        cleaned_data["bairro"] = cleaned_data.get("bairro", "").strip()
        cleaned_data["cidade"] = cleaned_data.get("cidade", "").strip()
        cleaned_data["inscricao_estadual"] = cleaned_data.get("inscricao_estadual", "").strip()
        cleaned_data["inscricao_municipal"] = cleaned_data.get("inscricao_municipal", "").strip()
        cleaned_data["cno_caepf"] = cleaned_data.get("cno_caepf", "").strip()
        cleaned_data["logo_url"] = cleaned_data.get("logo_url", "").strip()
        cleaned_data["website"] = cleaned_data.get("website", "").strip()
        return cleaned_data

    @transaction.atomic
    def save(self, user: User) -> Tenant:
        if user.tenant_id and (not self.existing_tenant or user.tenant_id != self.existing_tenant.pk):
            raise ValidationError("Esta conta já possui empresa vinculada.")

        tipo_pessoa = self.cleaned_data["tipo_pessoa"]
        documento = self.cleaned_data["documento"]

        tenant = self.existing_tenant or Tenant()
        tenant.tipo_pessoa = tipo_pessoa
        tenant.documento = documento
        tenant.cnpj = documento if tipo_pessoa == Tenant.TipoPessoa.PJ else None
        tenant.razao_social = self.cleaned_data["razao_social"]
        tenant.nome_fantasia = self.cleaned_data["nome_fantasia"].strip()
        tenant.email_contato = self.cleaned_data["email_contato"]
        tenant.telefone_contato = self.cleaned_data["telefone_contato"]
        tenant.cep = self.cleaned_data["cep"]
        tenant.logradouro = self.cleaned_data["logradouro"]
        tenant.numero = self.cleaned_data["numero"]
        tenant.complemento = self.cleaned_data["complemento"]
        tenant.bairro = self.cleaned_data["bairro"]
        tenant.cidade = self.cleaned_data["cidade"]
        tenant.estado = self.cleaned_data["estado"]
        tenant.responsavel_nome = self.cleaned_data["responsavel_nome"]
        tenant.responsavel_cpf = self.cleaned_data["responsavel_cpf"]
        tenant.responsavel_cargo = self.cleaned_data["responsavel_cargo"]
        tenant.logo_url = self.cleaned_data["logo_url"]
        tenant.website = self.cleaned_data["website"]
        tenant.cno_caepf = self.cleaned_data["cno_caepf"]
        tenant.inscricao_estadual = self.cleaned_data["inscricao_estadual"]
        tenant.inscricao_municipal = self.cleaned_data["inscricao_municipal"]
        tenant.onboarding_step = max(2, int(tenant.onboarding_step or 2))
        tenant.save()

        user.tenant = tenant
        user.is_account_owner = True
        user.save(update_fields=["tenant", "is_account_owner"])
        return tenant

    @classmethod
    def initial_from_tenant(cls, tenant: Tenant):
        cargo_choices = {choice[0] for choice in cls.CARGO_EMPRESA_CHOICES}
        cargo_atual = tenant.responsavel_cargo if tenant.responsavel_cargo in cargo_choices else ""
        return {
            "tipo_pessoa": tenant.tipo_pessoa,
            "documento": tenant.documento or tenant.cnpj or "",
            "razao_social": tenant.razao_social,
            "nome_fantasia": tenant.nome_fantasia,
            "email_contato": tenant.email_contato,
            "telefone_contato": tenant.telefone_contato,
            "cep": tenant.cep,
            "logradouro": tenant.logradouro,
            "numero": tenant.numero,
            "complemento": tenant.complemento,
            "bairro": tenant.bairro,
            "cidade": tenant.cidade,
            "estado": tenant.estado,
            "responsavel_nome": tenant.responsavel_nome,
            "responsavel_cpf": tenant.responsavel_cpf,
            "responsavel_cargo": cargo_atual,
            "logo_url": tenant.logo_url,
            "website": tenant.website,
            "cno_caepf": tenant.cno_caepf,
            "inscricao_estadual": tenant.inscricao_estadual,
            "inscricao_municipal": tenant.inscricao_municipal,
        }


class ProfileForm(forms.Form):
    first_name = forms.CharField(label="Nome", max_length=120, required=False)
    last_name = forms.CharField(label="Sobrenome", max_length=120, required=False)
    email = forms.EmailField(label="E-mail", required=False)
    cpf = forms.CharField(label="CPF", max_length=14, required=True)
    phone = forms.CharField(label="Telefone", max_length=20, required=False)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

    def clean_cpf(self):
        digits = _only_digits(self.cleaned_data["cpf"])
        if not _is_valid_cpf(digits):
            raise forms.ValidationError("Informe um CPF válido.")

        exists = User.objects.exclude(pk=self.user.pk).filter(cpf=digits).exists()
        if exists:
            raise forms.ValidationError("Este CPF já está em uso por outra conta.")
        return digits

    def clean_phone(self):
        raw_value = self.cleaned_data.get("phone", "")
        digits = _only_digits(raw_value)
        if digits and len(digits) not in (10, 11):
            raise forms.ValidationError("Informe um telefone válido com DDD.")
        return digits

    def save(self):
        self.user.cpf = self.cleaned_data["cpf"]
        self.user.phone = self.cleaned_data["phone"]
        self.user.save(update_fields=["cpf", "phone"])
        return self.user
