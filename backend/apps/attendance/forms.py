"""Forms do domínio de relógios de ponto."""

from django import forms
from django.core.exceptions import ValidationError

from .models import TimeClock
from .services import TimeClockService


class TimeClockForm(forms.Form):
    nome = forms.CharField(
        label="Nome do Relógio",
        max_length=80,
        widget=forms.TextInput(attrs={"placeholder": "Ex: Relogio Portaria"}),
    )
    descricao = forms.CharField(
        label="Descrição",
        max_length=255,
        required=False,
        widget=forms.Textarea(
            attrs={
                "placeholder": "Descreva a localização ou função do relógio",
                "rows": 4,
            }
        ),
    )
    tipo_relogio = forms.ChoiceField(
        label="Tipo do Relógio",
        choices=TimeClock.TipoRelogio.choices,
    )
    status = forms.ChoiceField(
        label="Status",
        choices=TimeClock.Status.choices,
        initial=TimeClock.Status.ATIVO,
    )
    metodo_autenticacao = forms.ChoiceField(
        label="Método de Autenticação Suportado",
        choices=TimeClock.MetodoAutenticacao.choices,
        initial=TimeClock.MetodoAutenticacao.FACIAL,
        disabled=True,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant")
        self.user = kwargs.pop("user")
        self.instance = kwargs.pop("instance", None)
        if self.instance and not args and "initial" not in kwargs:
            kwargs["initial"] = self.initial_from_time_clock(self.instance)
        super().__init__(*args, **kwargs)
        self.fields["tipo_relogio"].choices = (
            (TimeClock.TipoRelogio.APLICATIVO, "Aplicativo"),
        )

    @staticmethod
    def initial_from_time_clock(time_clock: TimeClock) -> dict:
        return {
            "nome": time_clock.nome,
            "descricao": time_clock.descricao,
            "tipo_relogio": time_clock.tipo_relogio,
            "status": time_clock.status,
            "metodo_autenticacao": time_clock.metodo_autenticacao,
        }

    def save(self) -> TimeClock | None:
        payload = {
            "nome": self.cleaned_data["nome"],
            "descricao": self.cleaned_data.get("descricao", ""),
            "tipo_relogio": self.cleaned_data["tipo_relogio"],
            "status": self.cleaned_data["status"],
        }
        try:
            if self.instance:
                return TimeClockService().update_time_clock(
                    time_clock=self.instance,
                    **payload,
                )
            return TimeClockService().create_time_clock(
                tenant=self.tenant,
                user=self.user,
                **payload,
            )
        except ValidationError as exc:
            self._apply_service_errors(exc)
            return None

    def _apply_service_errors(self, exc: ValidationError):
        if hasattr(exc, "message_dict"):
            for field, messages in exc.message_dict.items():
                target_field = field if field in self.fields else None
                for message in messages:
                    self.add_error(target_field, message)
            return

        for message in exc.messages:
            self.add_error(None, message)
