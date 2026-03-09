"""Forms do domínio de funcionários."""

from django import forms

from .models import WorkSchedule


class WorkScheduleForm(forms.Form):
    nome = forms.CharField(
        label="Nome da Jornada",
        max_length=80,
        widget=forms.TextInput(attrs={"placeholder": "Ex: Jornada Padrão 44h"}),
    )
    descricao = forms.CharField(
        label="Descrição",
        max_length=255,
        required=False,
        widget=forms.Textarea(attrs={"placeholder": "Descrição opcional da jornada", "rows": 3}),
    )
    tipo = forms.ChoiceField(
        label="Tipo de Jornada",
        choices=WorkSchedule.TipoJornada.choices,
    )

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant")
        super().__init__(*args, **kwargs)

    def clean_nome(self):
        nome = self.cleaned_data["nome"].strip()
        if len(nome) < 3:
            raise forms.ValidationError("O nome da jornada deve ter pelo menos 3 caracteres.")
        duplicado = WorkSchedule.all_objects.filter(
            tenant=self.tenant,
            nome__iexact=nome,
            ativo=True,
        ).exists()
        if duplicado:
            raise forms.ValidationError("Já existe uma jornada com este nome na sua empresa.")
        return nome

    def save(self) -> WorkSchedule:
        return WorkSchedule.all_objects.create(
            tenant=self.tenant,
            nome=self.cleaned_data["nome"],
            descricao=self.cleaned_data["descricao"],
            tipo=self.cleaned_data["tipo"],
        )
