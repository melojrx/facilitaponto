"""Forms web para autenticação e cadastro."""

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User


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
            phone=self.cleaned_data["phone"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            role=User.Role.ADMIN,
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
