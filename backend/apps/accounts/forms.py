"""Forms web para autenticação e cadastro."""

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User


class SignupForm(forms.Form):
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"placeholder": "voce@empresa.com"}),
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
