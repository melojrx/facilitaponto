import base64
import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.test import override_settings
from PIL import Image

from apps.accounts.forms import CompanyOnboardingForm
from apps.accounts.models import User
from apps.biometrics.models import ConsentimentoBiometrico, FacialEmbedding
from apps.tenants.models import Tenant


def _build_test_image_file(name="face.jpg"):
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/jpeg")


def _build_test_image_data_url():
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buffer, format="JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="owner@acme.com",
        cpf="70379043036",
        password="Forte123!",
        role=User.Role.ADMIN,
        is_account_owner=True,
    )


@pytest.mark.django_db
class TestWebPublicPages:
    def test_landing_publica(self, client):
        response = client.get("/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Começar Agora" in content
        assert "/cadastro/" in content

    def test_painel_exige_autenticacao(self, client):
        response = client.get("/painel/")

        assert response.status_code == 302
        assert response.url == "/login/?next=/painel/"


@pytest.mark.django_db
class TestSignupFlow:
    def test_signup_com_sucesso_autentica_e_redireciona(self, client):
        response = client.post(
            "/cadastro/",
            data={
                "first_name": "Joao",
                "last_name": "Silva",
                "email": "novo@acme.com",
                "cpf": "39053344705",
                "phone": "85999998888",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
            },
            follow=False,
        )

        assert response.status_code == 302
        assert response.url == "/painel/"
        user = User.objects.get(email="novo@acme.com")
        assert user.first_name == "Joao"
        assert user.last_name == "Silva"
        assert user.cpf == "39053344705"
        assert user.phone == "85999998888"
        assert user.is_account_owner is True
        assert client.session.get("_auth_user_id") is not None

    def test_signup_rejeita_email_duplicado(self, client, user):
        response = client.post(
            "/cadastro/",
            data={
                "first_name": "Joao",
                "last_name": "Silva",
                "email": user.email,
                "cpf": "59465684002",
                "phone": "85999998888",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
            },
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Já existe uma conta com este e-mail." in content

    @override_settings(
        AUTH_RATE_LIMITS={
            "web_login": {"limit": 10, "window_seconds": 60},
            "web_signup": {"limit": 1, "window_seconds": 60},
            "api_token": {"limit": 10, "window_seconds": 60},
        }
    )
    def test_signup_aplica_rate_limit(self, client):
        cache.clear()

        first_response = client.post(
            "/cadastro/",
            data={
                "first_name": "Joao",
                "last_name": "Silva",
                "email": "primeiro@acme.com",
                "cpf": "39053344705",
                "phone": "85999998888",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
            },
            follow=False,
        )
        client.post("/logout/", follow=False)
        second_response = client.post(
            "/cadastro/",
            data={
                "first_name": "Maria",
                "last_name": "Silva",
                "email": "segundo@acme.com",
                "cpf": "59465684002",
                "phone": "85999997777",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
            },
            follow=False,
        )

        assert first_response.status_code == 302
        assert second_response.status_code == 429
        assert "Muitas tentativas de cadastro" in second_response.content.decode()


@pytest.mark.django_db
class TestLoginLogoutFlow:
    def test_login_sucesso_redireciona_para_painel(self, client, user):
        response = client.post(
            "/login/",
            data={"email": user.email, "password": "Forte123!"},
            follow=False,
        )

        assert response.status_code == 302
        assert response.url == "/painel/"
        assert client.session.get("_auth_user_id") is not None

    def test_login_invalido_exibe_erro(self, client, user):
        response = client.post(
            "/login/",
            data={"email": user.email, "password": "senha-errada"},
        )

        assert response.status_code == 200
        assert "E-mail ou senha inválidos." in response.content.decode()

    @override_settings(
        AUTH_RATE_LIMITS={
            "web_login": {"limit": 2, "window_seconds": 60},
            "web_signup": {"limit": 5, "window_seconds": 60},
            "api_token": {"limit": 10, "window_seconds": 60},
        }
    )
    def test_login_aplica_rate_limit(self, client, user):
        cache.clear()

        payload = {"email": user.email, "password": "senha-errada"}
        first_response = client.post("/login/", data=payload, follow=False)
        second_response = client.post("/login/", data=payload, follow=False)
        third_response = client.post("/login/", data=payload, follow=False)

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert third_response.status_code == 429
        assert "Muitas tentativas de login" in third_response.content.decode()

    def test_login_respeita_next(self, client, user):
        response = client.post(
            "/login/?next=/painel/",
            data={"email": user.email, "password": "Forte123!", "next": "/painel/"},
            follow=False,
        )

        assert response.status_code == 302
        assert response.url == "/painel/"

    def test_logout_invalida_sessao_e_redireciona_landing(self, client, user):
        client.force_login(user)

        response = client.post("/logout/", follow=False)
        painel_response = client.get("/painel/")

        assert response.status_code == 302
        assert response.url == "/"
        assert painel_response.status_code == 302
        assert painel_response.url == "/login/?next=/painel/"


@pytest.mark.django_db
class TestDev008EndToEndFlow:
    def test_fluxo_completo_signup_login_painel_empresa_jornada_logout(self, client):
        signup_response = client.post(
            "/cadastro/",
            data={
                "first_name": "Joao",
                "last_name": "Silva",
                "email": "owner-e2e@acme.com",
                "cpf": "39053344705",
                "phone": "85999998888",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
            },
            follow=False,
        )

        assert signup_response.status_code == 302
        assert signup_response.url == "/painel/"

        painel_inicial = client.get("/painel/")
        painel_inicial_content = painel_inicial.content.decode()
        assert painel_inicial.status_code == 200
        assert "Crie sua primeira empresa" in painel_inicial_content
        assert re.search(r'data-menu-key="empresa"[\s\S]*?data-menu-state="enabled"', painel_inicial_content)
        assert re.search(r'data-menu-key="jornadas"[\s\S]*?data-menu-state="locked"', painel_inicial_content)

        logout_signup = client.post("/logout/", follow=False)
        assert logout_signup.status_code == 302
        assert logout_signup.url == "/"

        login_response = client.post(
            "/login/",
            data={"email": "owner-e2e@acme.com", "password": "SenhaForte123!"},
            follow=False,
        )
        assert login_response.status_code == 302
        assert login_response.url == "/painel/"

        company_response = client.post(
            "/painel/empresa/nova/",
            data={
                "tipo_pessoa": "PJ",
                "documento": "50529647000183",
                "razao_social": "Acme LTDA",
                "nome_fantasia": "Acme",
                "email_contato": "contato@acme.com",
                "telefone_contato": "85999998888",
                "cep": "60711-165",
                "logradouro": "Rua das Flores",
                "numero": "100",
                "complemento": "Sala 1",
                "bairro": "Centro",
                "cidade": "Fortaleza",
                "estado": "CE",
                "responsavel_nome": "Joao Silva",
                "responsavel_cpf": "39053344705",
                "responsavel_cargo": "Diretor",
                "cno_caepf": "",
                "inscricao_estadual": "12345",
                "inscricao_municipal": "54321",
            },
            follow=False,
        )

        assert company_response.status_code == 302
        assert company_response.url == "/painel/"

        owner = User.objects.get(email="owner-e2e@acme.com")
        owner.refresh_from_db()
        assert owner.tenant_id is not None
        assert owner.tenant.documento == "50529647000183"
        assert owner.tenant.onboarding_step == 2

        painel_empresa = client.get("/painel/")
        painel_empresa_content = painel_empresa.content.decode()
        assert painel_empresa.status_code == 200
        assert "Criar horário da equipe" in painel_empresa_content
        assert "Crie a primeira jornada para liberar o painel" in painel_empresa_content
        assert 'id="journey-modal-backdrop"' in painel_empresa_content
        assert re.search(r'data-menu-key="jornadas"[\s\S]*?data-menu-state="enabled"', painel_empresa_content)
        assert re.search(r'data-menu-key="colaboradores"[\s\S]*?data-menu-state="locked"', painel_empresa_content)

        jornada_response = client.post(
            "/painel/jornadas/nova/",
            data={
                "nome": "Jornada Inicial",
                "descricao": "Fluxo E2E",
                "tipo": "SEMANAL",
                "semanal_subtipo": "COMERCIAL_40H",
                "semanal_dias_json": json.dumps(
                    [
                        {
                            "dia_semana": "SEGUNDA",
                            "dsr": False,
                            "entrada_1": "08:00",
                            "saida_1": "12:00",
                            "entrada_2": "13:00",
                            "saida_2": "17:00",
                        },
                        {"dia_semana": "DOMINGO", "dsr": True},
                    ]
                ),
            },
            follow=False,
        )

        assert jornada_response.status_code == 302
        assert jornada_response.url == "/painel/jornadas/"

        owner.refresh_from_db()
        assert owner.tenant.onboarding_step == 3

        painel_final = client.get("/painel/")
        painel_final_content = painel_final.content.decode()
        assert painel_final.status_code == 200
        assert "Criar horário da equipe" not in painel_final_content
        assert re.search(r'data-menu-key="colaboradores"[\s\S]*?data-menu-state="enabled"', painel_final_content)
        assert re.search(r'data-menu-key="relogio_digital"[\s\S]*?data-menu-state="enabled"', painel_final_content)
        assert re.search(r'data-menu-key="relatorios"[\s\S]*?data-menu-state="enabled"', painel_final_content)

        logout_response = client.post("/logout/", follow=False)
        assert logout_response.status_code == 302
        assert logout_response.url == "/"

        painel_pos_logout = client.get("/painel/", follow=False)
        assert painel_pos_logout.status_code == 302
        assert painel_pos_logout.url == "/login/?next=/painel/"


@pytest.mark.django_db
class TestCompanyOnboardingFlow:
    def test_company_create_exige_autenticacao(self, client):
        response = client.get("/painel/empresa/nova/")
        assert response.status_code == 302
        assert response.url == "/login/?next=/painel/empresa/nova/"

    def test_company_create_com_sucesso_vincula_tenant_no_owner(self, client, user):
        client.force_login(user)

        response = client.post(
            "/painel/empresa/nova/",
            data={
                "tipo_pessoa": "PJ",
                "documento": "50529647000183",
                "razao_social": "Acme LTDA",
                "nome_fantasia": "Acme",
                "email_contato": "contato@acme.com",
                "telefone_contato": "85999998888",
                "cep": "60711-165",
                "logradouro": "Rua das Flores",
                "numero": "100",
                "complemento": "Sala 1",
                "bairro": "Centro",
                "cidade": "Fortaleza",
                "estado": "CE",
                "responsavel_nome": "Joao Silva",
                "responsavel_cpf": "39053344705",
                "responsavel_cargo": "Diretor",
                "cno_caepf": "",
                "inscricao_estadual": "12345",
                "inscricao_municipal": "54321",
            },
            follow=False,
        )

        user.refresh_from_db()
        assert response.status_code == 302
        assert response.url == "/painel/"
        assert user.tenant_id is not None
        assert user.tenant.documento == "50529647000183"
        assert user.tenant.tipo_pessoa == "PJ"

    def test_company_create_bloqueia_segunda_empresa_por_owner(self, client, user):
        client.force_login(user)
        client.post(
            "/painel/empresa/nova/",
            data={
                "tipo_pessoa": "PJ",
                "documento": "50529647000183",
                "razao_social": "Acme LTDA",
                "nome_fantasia": "Acme",
                "email_contato": "contato@acme.com",
                "telefone_contato": "85999998888",
            },
            follow=False,
        )

        second_response = client.post(
            "/painel/empresa/nova/",
            data={
                "tipo_pessoa": "PF",
                "documento": "39053344705",
                "razao_social": "Empresa 2",
                "nome_fantasia": "",
                "email_contato": "contato2@acme.com",
                "telefone_contato": "85999997777",
            },
            follow=False,
        )

        assert second_response.status_code == 302
        assert second_response.url == "/painel/empresa/"

    def test_company_view_exibe_todos_dados_sem_opcao_excluir(self, client, user):
        tenant = Tenant.objects.create(
            tipo_pessoa="PJ",
            documento="50529647000183",
            cnpj="50529647000183",
            razao_social="Acme LTDA",
            nome_fantasia="Acme",
            email_contato="contato@acme.com",
            telefone_contato="85999998888",
            cep="60711165",
            logradouro="Rua das Flores",
            numero="100",
            complemento="Sala 1",
            bairro="Centro",
            cidade="Fortaleza",
            estado="CE",
            responsavel_nome="Joao Silva",
            responsavel_cpf="39053344705",
            responsavel_cargo="Diretor",
            logo_url="https://exemplo.com/logo.png",
            website="https://acme.com",
            cno_caepf="123",
            inscricao_estadual="12345",
            inscricao_municipal="54321",
            onboarding_step=2,
        )
        user.tenant = tenant
        user.save(update_fields=["tenant"])
        client.force_login(user)

        response = client.get("/painel/empresa/")
        content = response.content.decode()

        assert response.status_code == 200
        assert "Acme LTDA" in content
        assert "Rua das Flores" in content
        assert "https://exemplo.com/logo.png" in content
        assert "https://acme.com" in content
        assert "Editar empresa" in content
        assert "Excluir empresa" not in content

    def test_company_edit_atualiza_empresa(self, client, user):
        tenant = Tenant.objects.create(
            tipo_pessoa="PJ",
            documento="50529647000183",
            cnpj="50529647000183",
            razao_social="Acme LTDA",
            onboarding_step=2,
        )
        user.tenant = tenant
        user.save(update_fields=["tenant"])
        client.force_login(user)

        response = client.post(
            "/painel/empresa/editar/",
            data={
                "tipo_pessoa": "PJ",
                "documento": "50529647000183",
                "razao_social": "Acme Atualizada LTDA",
                "nome_fantasia": "Acme Nova",
                "email_contato": "novo@acme.com",
                "telefone_contato": "(85) 99999-7777",
                "cep": "60000-000",
                "logradouro": "Av Central",
                "numero": "200",
                "complemento": "Bloco B",
                "bairro": "Aldeota",
                "cidade": "Fortaleza",
                "estado": "CE",
                "responsavel_nome": "Maria Silva",
                "responsavel_cpf": "39053344705",
                "responsavel_cargo": "Outro",
                "logo_url": "https://empresa.com/logo-novo.png",
                "website": "https://empresa.com",
                "cno_caepf": "456",
                "inscricao_estadual": "67890",
                "inscricao_municipal": "09876",
            },
            follow=False,
        )

        tenant.refresh_from_db()
        assert response.status_code == 302
        assert response.url == "/painel/empresa/"
        assert tenant.razao_social == "Acme Atualizada LTDA"
        assert tenant.nome_fantasia == "Acme Nova"
        assert tenant.email_contato == "novo@acme.com"
        assert tenant.logo_url == "https://empresa.com/logo-novo.png"
        assert tenant.website == "https://empresa.com"

    def test_company_edit_redireciona_quando_sem_empresa(self, client, user):
        client.force_login(user)
        response = client.get("/painel/empresa/editar/", follow=False)
        assert response.status_code == 302
        assert response.url == "/painel/empresa/nova/"


@pytest.mark.django_db(transaction=True)
class TestCompanyOnboardingConcurrency:
    def test_mesmo_owner_concorrente_cria_apenas_uma_empresa(self, user):
        payloads = [
            {
                "tipo_pessoa": "PJ",
                "documento": "50529647000183",
                "razao_social": "Empresa A",
                "nome_fantasia": "A",
                "email_contato": "contato-a@acme.com",
                "telefone_contato": "85999998888",
            },
            {
                "tipo_pessoa": "PJ",
                "documento": "12345678000195",
                "razao_social": "Empresa B",
                "nome_fantasia": "B",
                "email_contato": "contato-b@acme.com",
                "telefone_contato": "85999997777",
            },
        ]

        def try_create_company(payload):
            close_old_connections()
            owner = User.objects.get(pk=user.pk)
            form = CompanyOnboardingForm(payload)
            assert form.is_valid(), form.errors
            try:
                tenant = form.save(owner)
                return ("ok", str(tenant.id))
            except ValidationError as exc:
                return ("blocked", str(exc))

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(try_create_company, payloads))

        user.refresh_from_db()
        documents = {payload["documento"] for payload in payloads}
        created_count = Tenant.objects.filter(documento__in=documents).count()

        assert sorted(outcome[0] for outcome in outcomes) == ["blocked", "ok"]
        assert created_count == 1
        assert user.tenant_id is not None


@pytest.mark.django_db
class TestPanelMenuRelease:
    def test_menu_bloqueia_colaboradores_sem_empresa(self, client, user):
        client.force_login(user)
        response = client.get("/painel/")

        content = response.content.decode()
        assert response.status_code == 200
        assert 'data-menu-key="inicio"' in content
        assert 'data-menu-key="empresa"' in content
        assert 'data-menu-key="colaboradores"' in content
        assert re.search(r'data-menu-key="colaboradores"[\s\S]*?data-menu-state="locked"', content)

    def test_menu_libera_jornadas_quando_empresa_existe(self, client, user):
        tenant = Tenant.objects.create(
            tipo_pessoa="PJ",
            documento="50529647000183",
            cnpj="50529647000183",
            razao_social="ACME LTDA",
            onboarding_step=2,
        )
        user.tenant = tenant
        user.save(update_fields=["tenant"])
        client.force_login(user)

        response = client.get("/painel/")
        content = response.content.decode()

        assert response.status_code == 200
        assert 'data-menu-key="jornadas"' in content
        assert re.search(r'data-menu-key="jornadas"[\s\S]*?data-menu-state="enabled"', content)
        assert re.search(r'data-menu-key="colaboradores"[\s\S]*?data-menu-state="locked"', content)

    def test_acesso_direto_modulo_bloqueado_redireciona_painel(self, client, user):
        client.force_login(user)

        response = client.get("/painel/colaboradores/", follow=False)

        assert response.status_code == 302
        assert response.url == "/painel/empresa/nova/"

    def test_painel_resolve_tenant_por_email_contato_sem_persistir_vinculo(self, client, user):
        Tenant.objects.create(
            tipo_pessoa="PJ",
            documento="71537992000152",
            cnpj="71537992000152",
            razao_social="FacilitaPonto LTDA",
            email_contato=user.email,
            onboarding_step=2,
        )
        assert user.tenant_id is None

        client.force_login(user)
        response = client.get("/painel/")
        content = response.content.decode()
        user.refresh_from_db()

        assert response.status_code == 200
        assert user.tenant_id is None
        assert user.is_account_owner is True
        assert "FacilitaPonto LTDA" in content
        assert "Crie sua primeira empresa" not in content
        assert "Crie a primeira jornada para liberar o painel" in content
        assert 'id="journey-modal-backdrop"' in content


@pytest.mark.django_db
class TestProfileFlow:
    def test_profile_exige_autenticacao(self, client):
        response = client.get("/painel/perfil/")
        assert response.status_code == 302
        assert response.url == "/login/?next=/painel/perfil/"

    def test_profile_atualiza_cpf_e_telefone(self, client, user):
        client.force_login(user)

        response = client.post(
            "/painel/perfil/",
            data={"cpf": "390.533.447-05", "phone": "(85) 99999-1111"},
            follow=False,
        )

        user.refresh_from_db()
        assert response.status_code == 302
        assert response.url == "/painel/perfil/"
        assert user.cpf == "39053344705"
        assert user.phone == "85999991111"


@pytest.mark.django_db
class TestJourneyOnboardingFlow:
    """Testa GET|POST /painel/jornadas/nova/ e o avanço de onboarding_step."""

    URL = "/painel/jornadas/nova/"
    LIST_URL = "/painel/jornadas/"

    def _make_tenant(self, step=2):
        return Tenant.objects.create(
            tipo_pessoa="PJ",
            documento="50529647000183",
            cnpj="50529647000183",
            razao_social="Acme LTDA",
            onboarding_step=step,
        )

    def _attach_tenant(self, user, tenant):
        user.tenant = tenant
        user.save(update_fields=["tenant"])

    def _semanal_json(self):
        return json.dumps(
            [
                {
                    "dia_semana": "SEGUNDA",
                    "dsr": False,
                    "entrada_1": "08:00",
                    "saida_1": "12:00",
                    "entrada_2": "13:00",
                    "saida_2": "17:00",
                },
                {"dia_semana": "DOMINGO", "dsr": True},
            ]
        )

    # --- guardas ---

    def test_exige_autenticacao(self, client):
        response = client.get(self.URL)
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_sem_empresa_redireciona_para_criar_empresa(self, client, user):
        client.force_login(user)
        response = client.get(self.URL, follow=False)
        assert response.status_code == 302
        assert response.url == "/painel/empresa/nova/"

    # --- GET ---

    def test_get_renderiza_formulario(self, client, user):
        tenant = self._make_tenant()
        self._attach_tenant(user, tenant)
        client.force_login(user)

        response = client.get(self.URL)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Nova Jornada de Trabalho" in content
        assert 'name="nome"' in content
        assert 'name="tipo"' in content
        assert "Semanal" in content
        assert "12x36" in content
        assert "Fracionada" in content
        assert "Externa" in content
        assert "Selecione o tipo de jornada para continuar" in content
        assert "Dúvidas comuns" in content
        assert 'id="btn-salvar"' in content

    def test_lista_jornadas_exibe_jornada_cadastrada(self, client, user):
        from apps.employees.models import WorkSchedule

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = WorkSchedule.all_objects.create(
            tenant=tenant,
            nome="Jornada Integral",
            tipo="SEMANAL",
            configuracao={
                "subtipo": "INTEGRAL_44H",
                "intervalo_reduzido_convencao": False,
                "norma_coletiva_ref": "",
                "dias": [
                    {
                        "dia_semana": "SEGUNDA",
                        "dsr": False,
                        "entrada_1": "07:30",
                        "saida_1": "11:30",
                        "entrada_2": "13:00",
                        "saida_2": "17:30",
                    },
                    {
                        "dia_semana": "TERCA",
                        "dsr": False,
                        "entrada_1": "07:30",
                        "saida_1": "11:30",
                        "entrada_2": "13:00",
                        "saida_2": "17:30",
                    },
                    {
                        "dia_semana": "QUARTA",
                        "dsr": False,
                        "entrada_1": "07:30",
                        "saida_1": "11:30",
                        "entrada_2": "13:00",
                        "saida_2": "17:30",
                    },
                    {
                        "dia_semana": "QUINTA",
                        "dsr": False,
                        "entrada_1": "07:30",
                        "saida_1": "11:30",
                        "entrada_2": "13:00",
                        "saida_2": "17:30",
                    },
                    {
                        "dia_semana": "SEXTA",
                        "dsr": False,
                        "entrada_1": "07:30",
                        "saida_1": "11:30",
                        "entrada_2": "13:00",
                        "saida_2": "17:30",
                    },
                    {
                        "dia_semana": "SABADO",
                        "dsr": False,
                        "entrada_1": "07:30",
                        "saida_1": "11:30",
                        "entrada_2": "13:00",
                        "saida_2": "17:30",
                    },
                    {"dia_semana": "DOMINGO", "dsr": True},
                ],
            },
        )
        client.force_login(user)

        response = client.get(self.LIST_URL)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Jornadas de Trabalho" in content
        assert "Jornada Integral" in content
        assert "51.00h" in content
        assert "/painel/jornadas/nova/" in content
        assert f"/painel/jornadas/{schedule.id}/editar/" in content
        assert f"/painel/jornadas/{schedule.id}/excluir/" in content
        assert "Confirmar exclusão de jornada" in content
        assert "Consequências: a jornada será inativada" in content

    # --- POST válido ---

    def test_post_valido_cria_jornada_e_avanca_onboarding(self, client, user):
        from apps.employees.models import WorkSchedule

        tenant = self._make_tenant(step=2)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        response = client.post(
            self.URL,
            data={
                "nome": "Jornada Padrão 44h",
                "descricao": "Segunda a sexta",
                "tipo": "SEMANAL",
                "semanal_subtipo": "COMERCIAL_40H",
                "semanal_dias_json": self._semanal_json(),
            },
            follow=False,
        )

        tenant.refresh_from_db()
        assert response.status_code == 302
        assert response.url == "/painel/jornadas/"
        assert tenant.onboarding_step == 3
        assert WorkSchedule.all_objects.filter(tenant=tenant, nome="Jornada Padrão 44h").exists()

    def test_get_editar_jornada_renderiza_formulario_preenchido(self, client, user):
        from apps.employees.models import WorkSchedule

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = WorkSchedule.all_objects.create(
            tenant=tenant,
            nome="Jornada Comercial",
            descricao="Base semanal",
            tipo="SEMANAL",
            configuracao={
                "subtipo": "COMERCIAL_40H",
                "intervalo_reduzido_convencao": False,
                "norma_coletiva_ref": "",
                "dias": [
                    {
                        "dia_semana": "SEGUNDA",
                        "dsr": False,
                        "entrada_1": "08:00",
                        "saida_1": "12:00",
                        "entrada_2": "13:00",
                        "saida_2": "17:00",
                    },
                    {"dia_semana": "DOMINGO", "dsr": True},
                ],
            },
        )
        client.force_login(user)

        response = client.get(f"/painel/jornadas/{schedule.id}/editar/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Editar Jornada de Trabalho" in content
        assert 'value="Jornada Comercial"' in content
        assert f'action="/painel/jornadas/{schedule.id}/editar/"' in content

    def test_post_editar_jornada_atualiza_registro(self, client, user):
        from apps.employees.models import WorkSchedule

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = WorkSchedule.all_objects.create(
            tenant=tenant,
            nome="Jornada Comercial",
            descricao="Base semanal",
            tipo="SEMANAL",
            configuracao={
                "subtipo": "COMERCIAL_40H",
                "intervalo_reduzido_convencao": False,
                "norma_coletiva_ref": "",
                "dias": [
                    {
                        "dia_semana": "SEGUNDA",
                        "dsr": False,
                        "entrada_1": "08:00",
                        "saida_1": "12:00",
                        "entrada_2": "13:00",
                        "saida_2": "17:00",
                    },
                    {"dia_semana": "DOMINGO", "dsr": True},
                ],
            },
        )
        client.force_login(user)

        response = client.post(
            f"/painel/jornadas/{schedule.id}/editar/",
            data={
                "nome": "Jornada Comercial Atualizada",
                "descricao": "Atualizada",
                "tipo": "SEMANAL",
                "semanal_subtipo": "INTEGRAL_44H",
                "semanal_dias_json": json.dumps(
                    [
                        {
                            "dia_semana": "SEGUNDA",
                            "dsr": False,
                            "entrada_1": "08:00",
                            "saida_1": "12:00",
                            "entrada_2": "13:00",
                            "saida_2": "17:48",
                        },
                        {"dia_semana": "DOMINGO", "dsr": True},
                    ]
                ),
            },
            follow=False,
        )

        schedule.refresh_from_db()
        assert response.status_code == 302
        assert response.url == "/painel/jornadas/"
        assert schedule.nome == "Jornada Comercial Atualizada"
        assert schedule.descricao == "Atualizada"
        assert schedule.configuracao["subtipo"] == "INTEGRAL_44H"

    def test_post_excluir_jornada_desativa_registro(self, client, user):
        from apps.employees.models import WorkSchedule

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = WorkSchedule.all_objects.create(
            tenant=tenant,
            nome="Jornada para excluir",
            tipo="EXTERNA",
            configuracao={},
        )
        client.force_login(user)

        response = client.post(f"/painel/jornadas/{schedule.id}/excluir/", follow=False)

        schedule.refresh_from_db()
        assert response.status_code == 302
        assert response.url == "/painel/jornadas/"
        assert schedule.ativo is False

    def test_post_excluir_jornada_de_outro_tenant_retorna_404(self, client, user):
        from apps.employees.models import WorkSchedule

        tenant_user = self._make_tenant(step=3)
        tenant_other = Tenant.objects.create(
            tipo_pessoa="PJ",
            documento="32324680000140",
            cnpj="32324680000140",
            razao_social="Outro Tenant LTDA",
            onboarding_step=3,
        )
        self._attach_tenant(user, tenant_user)
        schedule_other = WorkSchedule.all_objects.create(
            tenant=tenant_other,
            nome="Jornada de outro tenant",
            tipo="EXTERNA",
            configuracao={},
        )
        client.force_login(user)

        response = client.post(f"/painel/jornadas/{schedule_other.id}/excluir/", follow=False)

        assert response.status_code == 404

    def test_get_editar_jornada_de_outro_tenant_retorna_404(self, client, user):
        from apps.employees.models import WorkSchedule

        tenant_user = self._make_tenant(step=3)
        tenant_other = Tenant.objects.create(
            tipo_pessoa="PJ",
            documento="42930073000106",
            cnpj="42930073000106",
            razao_social="Tenant Externo LTDA",
            onboarding_step=3,
        )
        self._attach_tenant(user, tenant_user)
        schedule_other = WorkSchedule.all_objects.create(
            tenant=tenant_other,
            nome="Jornada externa tenant",
            tipo="EXTERNA",
            configuracao={},
        )
        client.force_login(user)

        response = client.get(f"/painel/jornadas/{schedule_other.id}/editar/", follow=False)

        assert response.status_code == 404

    def test_post_tipo_12x36_salva_corretamente(self, client, user):
        from apps.employees.models import WorkSchedule

        tenant = self._make_tenant(step=2)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        client.post(
            self.URL,
            data={
                "nome": "Plantão 12x36",
                "descricao": "",
                "tipo": "12X36",
                "x12x36_data_inicio_escala": "2026-03-09",
                "x12x36_horario_entrada": "08:00",
            },
            follow=False,
        )

        schedule = WorkSchedule.all_objects.get(tenant=tenant, nome="Plantão 12x36", tipo="12X36")
        assert schedule.configuracao["data_inicio_escala"] == "2026-03-09"
        assert schedule.configuracao["horario_entrada"] == "08:00"
        assert schedule.configuracao["horario_saida"] == "20:00"
        assert schedule.configuracao["carga_horaria_semanal_hhmm"] == "48:00"
        escala = schedule.configuracao["escala_referencia_semanal"]
        assert len(escala) == 7
        assert escala[0]["dia_semana"] == "SEGUNDA"
        assert escala[0]["tipo_dia"] == "TRABALHO"
        assert escala[0]["entrada"] == "08:00"
        assert escala[1]["dia_semana"] == "TERCA"
        assert escala[1]["tipo_dia"] == "FOLGA"

    def test_post_tipo_fracionada_com_dsr_salva_corretamente(self, client, user):
        from apps.employees.models import WorkSchedule

        tenant = self._make_tenant(step=2)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        client.post(
            self.URL,
            data={
                "nome": "Fracionada Base",
                "descricao": "",
                "tipo": "FRACIONADA",
                "fracionada_dias_json": json.dumps(
                    [
                        {
                            "dia_semana": "SEGUNDA",
                            "dsr": False,
                            "periodos": [
                                {"inicio": "08:00", "fim": "12:00"},
                                {"inicio": "14:00", "fim": "18:00"},
                            ],
                        },
                        {"dia_semana": "DOMINGO", "dsr": True, "periodos": []},
                    ]
                ),
            },
            follow=False,
        )

        schedule = WorkSchedule.all_objects.get(tenant=tenant, nome="Fracionada Base", tipo="FRACIONADA")
        assert len(schedule.configuracao["dias"]) == 2
        assert schedule.configuracao["dias"][0]["dia_semana"] == "SEGUNDA"
        assert schedule.configuracao["dias"][0]["dsr"] is False
        assert schedule.configuracao["dias"][1]["dia_semana"] == "DOMINGO"
        assert schedule.configuracao["dias"][1]["dsr"] is True
        assert schedule.configuracao["dias"][1]["periodos"] == []

    def test_post_avanca_step_apenas_para_3_nunca_regride(self, client, user):
        """Se tenant já está em step 4, não deve regredir para 3."""
        tenant = self._make_tenant(step=4)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        client.post(
            self.URL,
            data={"nome": "Jornada Extra", "descricao": "", "tipo": "EXTERNA"},
            follow=False,
        )

        tenant.refresh_from_db()
        assert tenant.onboarding_step == 4

    # --- POST inválido ---

    def test_post_sem_nome_reexibe_form_com_erro(self, client, user):
        tenant = self._make_tenant()
        self._attach_tenant(user, tenant)
        client.force_login(user)

        response = client.post(
            self.URL,
            data={"nome": "", "tipo": "SEMANAL", "semanal_dias_json": self._semanal_json()},
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Nova Jornada de Trabalho" in content

    def test_post_nome_duplicado_rejeita(self, client, user):
        from apps.employees.models import WorkSchedule

        tenant = self._make_tenant()
        self._attach_tenant(user, tenant)
        WorkSchedule.all_objects.create(tenant=tenant, nome="Jornada Padrão", tipo="SEMANAL")
        client.force_login(user)

        response = client.post(
            self.URL,
            data={
                "nome": "Jornada Padrão",
                "descricao": "",
                "tipo": "SEMANAL",
                "semanal_dias_json": self._semanal_json(),
            },
        )

        assert response.status_code == 200
        assert "Já existe uma jornada com este nome" in response.content.decode()

    def test_post_sem_tipo_rejeita(self, client, user):
        tenant = self._make_tenant()
        self._attach_tenant(user, tenant)
        client.force_login(user)

        response = client.post(
            self.URL,
            data={"nome": "Jornada X", "descricao": "", "tipo": ""},
        )

        assert response.status_code == 200

    def test_post_fracionada_com_periodos_sobrepostos_rejeita(self, client, user):
        tenant = self._make_tenant()
        self._attach_tenant(user, tenant)
        client.force_login(user)

        response = client.post(
            self.URL,
            data={
                "nome": "Jornada Fracionada Inválida",
                "descricao": "",
                "tipo": "FRACIONADA",
                "fracionada_dias_json": json.dumps(
                    [
                        {
                            "dia_semana": "SEGUNDA",
                            "periodos": [
                                {"inicio": "08:00", "fim": "12:00"},
                                {"inicio": "11:00", "fim": "15:00"},
                            ],
                        }
                    ]
                ),
            },
        )

        assert response.status_code == 200
        assert "sobreposição" in response.content.decode()

    def test_post_externa_com_horarios_rejeita(self, client, user):
        tenant = self._make_tenant()
        self._attach_tenant(user, tenant)
        client.force_login(user)

        response = client.post(
            self.URL,
            data={
                "nome": "Jornada Externa Inválida",
                "descricao": "",
                "tipo": "EXTERNA",
                "semanal_dias_json": self._semanal_json(),
            },
        )

        assert response.status_code == 200
        assert "Não é permitido definir horários para jornada externa." in response.content.decode()

    # --- liberação de menu ---

    def test_menu_libera_todos_modulos_apos_primeira_jornada(self, client, user):
        import re


        tenant = self._make_tenant(step=2)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        client.post(
            self.URL,
            data={
                "nome": "Jornada Inicial",
                "descricao": "",
                "tipo": "SEMANAL",
                "semanal_dias_json": self._semanal_json(),
            },
            follow=False,
        )

        response = client.get("/painel/")
        content = response.content.decode()

        assert re.search(r'data-menu-key="colaboradores"[\s\S]*?data-menu-state="enabled"', content)
        assert re.search(r'data-menu-key="relogio_digital"[\s\S]*?data-menu-state="enabled"', content)


@pytest.mark.django_db
class TestCollaboratorWebFlow:
    CREATE_URL = "/painel/colaboradores/novo/"
    LIST_URL = "/painel/colaboradores/"

    def _make_tenant(self, step=3):
        return Tenant.objects.create(
            tipo_pessoa="PJ",
            documento="31721174000107",
            cnpj="31721174000107",
            razao_social="Acme Colaboradores LTDA",
            onboarding_step=step,
        )

    def _attach_tenant(self, user, tenant):
        user.tenant = tenant
        user.save(update_fields=["tenant"])

    def _create_schedule(self, tenant, nome="Jornada Comercial"):
        from apps.employees.models import WorkSchedule

        return WorkSchedule.all_objects.create(
            tenant=tenant,
            nome=nome,
            tipo=WorkSchedule.TipoJornada.SEMANAL,
        )

    def test_get_exige_autenticacao(self, client):
        response = client.get(self.CREATE_URL)
        assert response.status_code == 302
        assert response.url == f"/login/?next={self.CREATE_URL}"

    def test_get_sem_empresa_redireciona_para_criar_empresa(self, client, user):
        client.force_login(user)
        response = client.get(self.CREATE_URL, follow=False)
        assert response.status_code == 302
        assert response.url == "/painel/empresa/nova/"

    def test_get_bloqueia_antes_da_primeira_jornada(self, client, user):
        tenant = self._make_tenant(step=2)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        response = client.get(self.CREATE_URL, follow=False)

        assert response.status_code == 302
        assert response.url == "/painel/"

    def test_get_renderiza_formulario_colaborador(self, client, user):
        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        self._create_schedule(tenant)
        client.force_login(user)

        response = client.get(self.CREATE_URL)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Novo Colaborador" in content
        assert 'name="nome"' in content
        assert 'name="cpf"' in content
        assert 'name="pis"' in content
        assert 'name="work_schedule"' in content
        assert "Sem dados faciais" in content

    def test_listagem_vazia_exibe_estado_inicial(self, client, user):
        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        self._create_schedule(tenant)
        client.force_login(user)

        response = client.get(self.LIST_URL)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Nenhum colaborador encontrado" in content
        assert "Criar primeiro colaborador" in content
        assert "Ativos (0)" in content
        assert "Inativos (0)" in content
        assert "Transferidos (0)" in content

    def test_post_valido_cria_colaborador_e_redireciona_para_lista(self, client, user):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        client.force_login(user)

        response = client.post(
            self.CREATE_URL,
            data={
                "nome": "Maria Clara Santos",
                "cpf": "529.982.247-25",
                "pis": "123.45678.90-0",
                "email": "maria@acme.com",
                "telefone": "(85) 99999-0000",
                "funcao": "Analista",
                "departamento": "Operacoes",
                "data_admissao": "2026-03-01",
                "matricula_interna": "COL-001",
                "work_schedule": str(schedule.id),
            },
            follow=False,
        )

        assert response.status_code == 302
        assert response.url == self.LIST_URL

        employee = Employee.all_objects.get(tenant=tenant, cpf="52998224725")
        assert employee.nome == "Maria Clara Santos"
        assert employee.work_schedule == schedule

        list_response = client.get(self.LIST_URL)
        content = list_response.content.decode()
        assert "Maria Clara Santos" in content
        assert "Pendente" in content
        assert "Jornada Comercial" in content

    def test_listagem_exibe_rastreabilidade_biometrica(self, client, user):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Clara",
            cpf="52998224725",
            pis="12345678900",
            work_schedule=schedule,
            ativo=True,
        )
        ConsentimentoBiometrico.objects.create(
            employee=employee,
            aceito=True,
            versao_termo="v1",
        )
        FacialEmbedding.objects.create(
            employee=employee,
            embedding_data=b"fake",
            ativo=True,
        )
        client.force_login(user)

        response = client.get(self.LIST_URL)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Cadastro Facial Concluido" in content
        assert "Cadastro facial concluido em" in content

    def test_listagem_filtra_por_busca_e_jornada(self, client, user):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule_a = self._create_schedule(tenant, nome="Comercial")
        schedule_b = self._create_schedule(tenant, nome="Plantao")
        Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Clara",
            cpf="52998224725",
            pis="12345678900",
            work_schedule=schedule_a,
            ativo=True,
        )
        Employee.all_objects.create(
            tenant=tenant,
            nome="Joao Pedro",
            cpf="16899535009",
            pis="98765432103",
            work_schedule=schedule_b,
            ativo=True,
        )
        client.force_login(user)

        response = client.get(
            self.LIST_URL,
            data={"q": "529.982.247-25", "work_schedule": str(schedule_a.id), "status": "ativos"},
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Maria Clara" in content
        assert "Joao Pedro" not in content
        assert "Ativos (1)" in content

    def test_listagem_aba_inativos_exibe_apenas_inativos(self, client, user):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        Employee.all_objects.create(
            tenant=tenant,
            nome="Ativo Base",
            cpf="52998224725",
            pis="12345678900",
            work_schedule=schedule,
            ativo=True,
        )
        Employee.all_objects.create(
            tenant=tenant,
            nome="Inativo Base",
            cpf="16899535009",
            pis="98765432103",
            work_schedule=schedule,
            ativo=False,
        )
        client.force_login(user)

        response = client.get(self.LIST_URL, data={"status": "inativos"})

        assert response.status_code == 200
        content = response.content.decode()
        assert "Inativo Base" in content
        assert "Ativo Base" not in content
        assert "Inativos (1)" in content

    def test_get_editar_colaborador_renderiza_formulario_preenchido(self, client, user):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Clara",
            cpf="52998224725",
            pis="12345678900",
            email="maria@acme.com",
            funcao="Analista",
            departamento="Operacoes",
            work_schedule=schedule,
            ativo=True,
        )
        client.force_login(user)

        response = client.get(f"/painel/colaboradores/{employee.id}/editar/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Editar Colaborador" in content
        assert 'value="Maria Clara"' in content
        assert 'value="52998224725"' in content
        assert "Rastreabilidade biométrica" in content
        assert "Capturar Foto Facial" in content

    def test_get_editar_colaborador_com_flag_reabre_modal_biometrico(self, client, user):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Clara",
            cpf="52998224725",
            pis="12345678900",
            work_schedule=schedule,
            ativo=True,
        )
        client.force_login(user)

        response = client.get(f"/painel/colaboradores/{employee.id}/editar/?open_biometric_modal=1")

        assert response.status_code == 200
        assert 'data-auto-open="true"' in response.content.decode()
        assert "Usar webcam" in response.content.decode()
        assert "Enviar foto" in response.content.decode()

    def test_listagem_exibe_acao_rapida_para_captura_biometrica(self, client, user):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Clara",
            cpf="52998224725",
            pis="12345678900",
            work_schedule=schedule,
            ativo=True,
        )
        client.force_login(user)

        response = client.get(self.LIST_URL)

        assert response.status_code == 200
        assert (
            f'/painel/colaboradores/{employee.id}/editar/?open_biometric_modal=1'
            in response.content.decode()
        )

    def test_post_captura_biometrica_conclui_cadastro_facial(self, client, user, monkeypatch):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Clara",
            cpf="52998224725",
            pis="12345678900",
            work_schedule=schedule,
            ativo=True,
        )
        client.force_login(user)

        captured = {}

        def fake_capture_for_panel(self, **kwargs):
            captured.update(kwargs)
            return {
                "consent": object(),
                "embedding": object(),
                "snapshot": {
                    "status": Employee.BiometricStatus.CADASTRADA,
                    "label": "Cadastro Facial Concluido",
                },
            }

        monkeypatch.setattr(
            "apps.accounts.web_views.AssistedBiometricCaptureService.capture_for_panel",
            fake_capture_for_panel,
        )

        response = client.post(
            f"/painel/colaboradores/{employee.id}/biometria/capturar/",
            data={
                "imagem": _build_test_image_file(),
                "consentimento": "on",
                "versao_termo": "painel-v1",
            },
            follow=False,
        )

        assert response.status_code == 302
        assert response.url == f"/painel/colaboradores/{employee.id}/editar/"
        assert captured["employee"].id == employee.id
        assert captured["consentimento_aceito"] is True
        assert captured["versao_termo"] == "painel-v1"
        assert captured["imagem_bytes"]

    def test_post_captura_biometrica_por_webcam_conclui_cadastro_facial(self, client, user, monkeypatch):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Clara",
            cpf="52998224725",
            pis="12345678900",
            work_schedule=schedule,
            ativo=True,
        )
        client.force_login(user)

        captured = {}

        def fake_capture_for_panel(self, **kwargs):
            captured.update(kwargs)
            return {
                "consent": object(),
                "embedding": object(),
                "snapshot": {
                    "status": Employee.BiometricStatus.CADASTRADA,
                    "label": "Cadastro Facial Concluido",
                },
            }

        monkeypatch.setattr(
            "apps.accounts.web_views.AssistedBiometricCaptureService.capture_for_panel",
            fake_capture_for_panel,
        )

        response = client.post(
            f"/painel/colaboradores/{employee.id}/biometria/capturar/",
            data={
                "imagem_capturada": _build_test_image_data_url(),
                "consentimento": "on",
                "versao_termo": "painel-v1",
            },
            follow=False,
        )

        assert response.status_code == 302
        assert response.url == f"/painel/colaboradores/{employee.id}/editar/"
        assert captured["employee"].id == employee.id
        assert captured["consentimento_aceito"] is True
        assert captured["versao_termo"] == "painel-v1"
        assert captured["imagem_bytes"]

    def test_post_captura_biometrica_bloqueia_sem_consentimento(self, client, user):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Clara",
            cpf="52998224725",
            pis="12345678900",
            work_schedule=schedule,
            ativo=True,
        )
        client.force_login(user)

        response = client.post(
            f"/painel/colaboradores/{employee.id}/biometria/capturar/",
            data={
                "imagem": _build_test_image_file(),
                "versao_termo": "painel-v1",
            },
            follow=True,
        )

        assert response.status_code == 200
        assert "Marque a autorização para confirmar o cadastro facial." in response.content.decode()
        assert 'data-auto-open="true"' in response.content.decode()

    def test_post_captura_biometrica_bloqueia_sem_upload_ou_webcam(self, client, user):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Clara",
            cpf="52998224725",
            pis="12345678900",
            work_schedule=schedule,
            ativo=True,
        )
        client.force_login(user)

        response = client.post(
            f"/painel/colaboradores/{employee.id}/biometria/capturar/",
            data={
                "consentimento": "on",
                "versao_termo": "painel-v1",
            },
            follow=True,
        )

        assert response.status_code == 200
        assert "Envie uma foto facial válida para continuar." in response.content.decode()
        assert 'data-auto-open="true"' in response.content.decode()

    def test_post_captura_biometrica_exibe_erro_de_enroll(self, client, user, monkeypatch):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Clara",
            cpf="52998224725",
            pis="12345678900",
            work_schedule=schedule,
            ativo=True,
        )
        client.force_login(user)

        def fake_capture_for_panel(self, **kwargs):
            raise ValidationError("Não foi possível concluir o cadastro facial. Tente novamente.")

        monkeypatch.setattr(
            "apps.accounts.web_views.AssistedBiometricCaptureService.capture_for_panel",
            fake_capture_for_panel,
        )

        response = client.post(
            f"/painel/colaboradores/{employee.id}/biometria/capturar/",
            data={
                "imagem": _build_test_image_file(),
                "consentimento": "on",
                "versao_termo": "painel-v1",
            },
            follow=True,
        )

        assert response.status_code == 200
        assert "Não foi possível concluir o cadastro facial. Tente novamente." in response.content.decode()
        assert 'data-auto-open="true"' in response.content.decode()

    def test_post_editar_colaborador_atualiza_registro(self, client, user):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule_a = self._create_schedule(tenant, nome="Comercial")
        schedule_b = self._create_schedule(tenant, nome="Plantao")
        employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Clara",
            cpf="52998224725",
            pis="12345678900",
            email="maria@acme.com",
            work_schedule=schedule_a,
            ativo=True,
        )
        client.force_login(user)

        response = client.post(
            f"/painel/colaboradores/{employee.id}/editar/",
            data={
                "nome": "Maria Clara Souza",
                "cpf": "529.982.247-25",
                "pis": "123.45678.90-0",
                "email": "maria.souza@acme.com",
                "telefone": "(85) 99999-0000",
                "funcao": "Coordenadora",
                "departamento": "RH",
                "data_admissao": "2026-03-02",
                "matricula_interna": "COL-090",
                "work_schedule": str(schedule_b.id),
            },
            follow=False,
        )

        employee.refresh_from_db()
        assert response.status_code == 302
        assert response.url == self.LIST_URL
        assert employee.nome == "Maria Clara Souza"
        assert employee.email == "maria.souza@acme.com"
        assert employee.work_schedule == schedule_b
        assert employee.funcao == "Coordenadora"

    def test_post_toggle_status_altera_ativo(self, client, user):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Clara",
            cpf="52998224725",
            pis="12345678900",
            work_schedule=schedule,
            ativo=True,
        )
        client.force_login(user)

        response = client.post(f"/painel/colaboradores/{employee.id}/status/", follow=False)

        employee.refresh_from_db()
        assert response.status_code == 302
        assert response.url == self.LIST_URL
        assert employee.ativo is False

    def test_post_usa_service_como_ponto_unico_de_cadastro(self, client, user, monkeypatch):
        from apps.employees.models import Employee
        from apps.employees.services import EmployeeRegistrationService

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        client.force_login(user)

        captured = {}
        employee = Employee(
            tenant=tenant,
            nome="Servico Unico",
            cpf="52998224725",
            pis="12345678900",
            work_schedule=schedule,
            ativo=True,
        )
        employee.id = 999

        def fake_create_employee(**kwargs):
            captured.update(kwargs)
            return employee

        monkeypatch.setattr(EmployeeRegistrationService, "create_employee", fake_create_employee)

        response = client.post(
            self.CREATE_URL,
            data={
                "nome": "Servico Unico",
                "cpf": "529.982.247-25",
                "pis": "123.45678.90-0",
                "work_schedule": str(schedule.id),
            },
            follow=False,
        )

        assert response.status_code == 302
        assert response.url == self.LIST_URL
        assert captured["tenant"] == tenant
        assert captured["nome"] == "Servico Unico"
        assert captured["work_schedule_id"] == schedule.id

    def test_post_cpf_duplicado_exibe_erro_amigavel(self, client, user):
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        schedule = self._create_schedule(tenant)
        Employee.all_objects.create(
            tenant=tenant,
            nome="Existente",
            cpf="52998224725",
            pis="12345678900",
            work_schedule=schedule,
            ativo=True,
        )
        client.force_login(user)

        response = client.post(
            self.CREATE_URL,
            data={
                "nome": "Duplicado",
                "cpf": "529.982.247-25",
                "pis": "987.65432.10-3",
                "work_schedule": str(schedule.id),
            },
            follow=False,
        )

        assert response.status_code == 200
        assert "Ja existe colaborador com este CPF nesta empresa." in response.content.decode()


@pytest.mark.django_db
class TestTimeClockWebFlow:
    CREATE_URL = "/painel/relogios/novo/"
    LIST_URL = "/painel/relogios/"

    def _make_tenant(self, step=3):
        return Tenant.objects.create(
            tipo_pessoa="PJ",
            documento="31721174000107",
            cnpj="31721174000107",
            razao_social="Acme Relogios LTDA",
            onboarding_step=step,
        )

    def _attach_tenant(self, user, tenant):
        user.tenant = tenant
        user.save(update_fields=["tenant"])

    def test_get_exige_autenticacao(self, client):
        response = client.get(self.LIST_URL)

        assert response.status_code == 302
        assert response.url == f"/login/?next={self.LIST_URL}"

    def test_get_sem_empresa_redireciona_para_criar_empresa(self, client, user):
        client.force_login(user)

        response = client.get(self.LIST_URL, follow=False)

        assert response.status_code == 302
        assert response.url == "/painel/empresa/nova/"

    def test_get_bloqueia_antes_da_primeira_jornada(self, client, user):
        tenant = self._make_tenant(step=2)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        response = client.get(self.LIST_URL, follow=False)

        assert response.status_code == 302
        assert response.url == "/painel/"

    def test_listagem_vazia_renderiza_estado_inicial(self, client, user):
        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        response = client.get(self.LIST_URL)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Relógios de Ponto" in content
        assert "Nenhum resultado encontrado" in content
        assert "Criar Relógio" in content

    def test_get_lista_aplica_busca_e_filtros(self, client, user):
        from apps.attendance.models import TimeClock

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        TimeClock.all_objects.create(
            tenant=tenant,
            created_by=user,
            nome="Relogio Portaria",
            descricao="Tablet principal da entrada",
            activation_code="AB12CD",
            tipo_relogio=TimeClock.TipoRelogio.APLICATIVO,
            status=TimeClock.Status.ATIVO,
        )
        TimeClock.all_objects.create(
            tenant=tenant,
            created_by=user,
            nome="Relogio Almoxarifado",
            descricao="Equipamento reserva",
            activation_code="EF34GH",
            tipo_relogio=TimeClock.TipoRelogio.APLICATIVO,
            status=TimeClock.Status.INATIVO,
        )
        client.force_login(user)

        response = client.get(
            self.LIST_URL,
            data={
                "q": "Portaria",
                "status": TimeClock.Status.ATIVO,
                "tipo_rep": TimeClock.TipoRelogio.APLICATIVO,
            },
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Relogio Portaria" in content
        assert "Relogio Almoxarifado" not in content
        assert 'value="Portaria"' in content
        assert (
            f'<option value="{TimeClock.Status.ATIVO}" selected>'
            in content
        )

    def test_get_renderiza_formulario_de_criacao(self, client, user):
        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        response = client.get(self.CREATE_URL)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Criar Relógio" in content
        assert 'name="nome"' in content
        assert 'name="descricao"' in content
        assert 'name="tipo_relogio"' in content
        assert 'name="status"' in content
        assert "Reconhecimento Facial" in content

    def test_post_valido_cria_relogio_e_redireciona_para_lista(self, client, user):
        from apps.attendance.models import TimeClock

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        response = client.post(
            self.CREATE_URL,
            data={
                "nome": "Relogio Portaria",
                "descricao": "Tablet principal da entrada",
                "tipo_relogio": "APLICATIVO",
                "status": "ATIVO",
            },
            follow=False,
        )

        assert response.status_code == 302
        assert response.url == self.LIST_URL

        time_clock = TimeClock.all_objects.get(tenant=tenant, nome="Relogio Portaria")
        assert time_clock.created_by == user
        assert time_clock.status == TimeClock.Status.ATIVO
        assert len(time_clock.activation_code) == 6

        list_response = client.get(self.LIST_URL)
        content = list_response.content.decode()
        assert "Relogio Portaria" in content
        assert "Código de Ativação" in content
        assert "Gerenciar" in content

    def test_post_usa_service_como_ponto_unico_de_criacao(self, client, user, monkeypatch):
        from apps.attendance.models import TimeClock
        from apps.attendance.services import TimeClockService

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        captured = {}
        time_clock = TimeClock(
            tenant=tenant,
            nome="Servico Relogio",
            activation_code="AB12CD",
        )
        time_clock.id = uuid.uuid4()

        def fake_create_time_clock(self, **kwargs):
            captured.update(kwargs)
            return time_clock

        monkeypatch.setattr(TimeClockService, "create_time_clock", fake_create_time_clock)

        response = client.post(
            self.CREATE_URL,
            data={
                "nome": "Servico Relogio",
                "descricao": "",
                "tipo_relogio": "APLICATIVO",
                "status": "ATIVO",
            },
            follow=False,
        )

        assert response.status_code == 302
        assert response.url == self.LIST_URL
        assert captured["tenant"] == tenant
        assert captured["user"] == user
        assert captured["nome"] == "Servico Relogio"

    def test_post_nome_duplicado_exibe_erro_amigavel(self, client, user):
        from apps.attendance.models import TimeClock

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        TimeClock.all_objects.create(
            tenant=tenant,
            nome="Relogio Portaria",
            activation_code="ZX12CV",
        )
        client.force_login(user)

        response = client.post(
            self.CREATE_URL,
            data={
                "nome": "relogio portaria",
                "descricao": "",
                "tipo_relogio": "APLICATIVO",
                "status": "ATIVO",
            },
            follow=False,
        )

        assert response.status_code == 200
        assert "Já existe relógio com este nome nesta empresa." in response.content.decode()

    def test_post_toggle_status_inativa_relogio(self, client, user):
        from apps.attendance.models import TimeClock

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        time_clock = TimeClock.all_objects.create(
            tenant=tenant,
            created_by=user,
            nome="Relogio Portaria",
            activation_code="MN45OP",
            status=TimeClock.Status.ATIVO,
        )
        client.force_login(user)

        response = client.post(f"/painel/relogios/{time_clock.id}/status/", follow=False)

        time_clock.refresh_from_db()
        assert response.status_code == 302
        assert response.url == self.LIST_URL
        assert time_clock.status == TimeClock.Status.INATIVO

    def test_get_detalhe_renderiza_aba_informacoes(self, client, user):
        from apps.attendance.models import TimeClock

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        time_clock = TimeClock.all_objects.create(
            tenant=tenant,
            created_by=user,
            nome="Relogio Portaria",
            descricao="Tablet principal da portaria",
            activation_code="XY12ZA",
        )
        client.force_login(user)

        response = client.get(f"/painel/relogios/{time_clock.id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Relogio Portaria" in content
        assert "Informações" in content
        assert "Código de Ativação" in content
        assert "Cerca Virtual" in content
        assert "Nenhuma cerca virtual configurada." in content

    def test_get_edicao_renderiza_valores_atuais(self, client, user):
        from apps.attendance.models import TimeClock

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        time_clock = TimeClock.all_objects.create(
            tenant=tenant,
            created_by=user,
            nome="Relogio Portaria",
            descricao="Tablet principal da portaria",
            activation_code="RT34YU",
        )
        client.force_login(user)

        response = client.get(f"/painel/relogios/{time_clock.id}/editar/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Editar Relógio" in content
        assert 'value="Relogio Portaria"' in content
        assert "Abrir aba Colaboradores" in content

    def test_post_edicao_atualiza_relogio_e_redireciona_para_detalhe(self, client, user):
        from apps.attendance.models import TimeClock

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        time_clock = TimeClock.all_objects.create(
            tenant=tenant,
            created_by=user,
            nome="Relogio Portaria",
            descricao="Tablet principal da portaria",
            activation_code="FG56HJ",
        )
        client.force_login(user)

        response = client.post(
            f"/painel/relogios/{time_clock.id}/editar/",
            data={
                "nome": "Relogio Portaria Principal",
                "descricao": "Tablet da entrada principal",
                "tipo_relogio": "APLICATIVO",
                "status": "EM_MANUTENCAO",
            },
            follow=False,
        )

        time_clock.refresh_from_db()
        assert response.status_code == 302
        assert response.url == f"/painel/relogios/{time_clock.id}/"
        assert time_clock.nome == "Relogio Portaria Principal"
        assert time_clock.status == TimeClock.Status.EM_MANUTENCAO

    def test_get_aba_colaboradores_renderiza_disponiveis_e_no_relogio(self, client, user):
        from apps.attendance.models import TimeClock, TimeClockEmployeeAssignment
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        time_clock = TimeClock.all_objects.create(
            tenant=tenant,
            created_by=user,
            nome="Relogio Portaria",
            activation_code="JK78LM",
        )
        assigned_employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Francisco Gadelha",
            cpf="11111111111",
            pis="11111111111",
            ativo=True,
        )
        available_employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Lopes",
            cpf="22222222222",
            pis="22222222222",
            ativo=True,
        )
        TimeClockEmployeeAssignment.objects.create(
            tenant=tenant,
            time_clock=time_clock,
            employee=assigned_employee,
        )
        client.force_login(user)

        response = client.get(f"/painel/relogios/{time_clock.id}/?aba=colaboradores")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Adicionar colaboradores" in content
        assert "Disponíveis (1)" in content
        assert "No Relógio (1)" in content
        assert available_employee.nome in content
        assert assigned_employee.nome in content

    def test_post_assign_selected_vincula_colaborador_ao_relogio(self, client, user):
        from apps.attendance.models import TimeClock, TimeClockEmployeeAssignment
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        time_clock = TimeClock.all_objects.create(
            tenant=tenant,
            created_by=user,
            nome="Relogio Portaria",
            activation_code="NO90PQ",
        )
        employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Maria Lopes",
            cpf="33333333333",
            pis="33333333333",
            ativo=True,
        )
        client.force_login(user)

        response = client.post(
            f"/painel/relogios/{time_clock.id}/?aba=colaboradores",
            data={
                "aba": "colaboradores",
                "action": "assign_selected",
                "available_employee_ids": [str(employee.id)],
                "available_q": "",
                "assigned_q": "",
            },
            follow=False,
        )

        time_clock.refresh_from_db()
        assert response.status_code == 302
        assert response.url == f"/painel/relogios/{time_clock.id}/?aba=colaboradores&available_q=&assigned_q="
        assert TimeClockEmployeeAssignment.all_objects.filter(
            tenant=tenant,
            time_clock=time_clock,
            employee=employee,
        ).exists()

    def test_post_remove_selected_desvincula_colaborador_do_relogio(self, client, user):
        from apps.attendance.models import TimeClock, TimeClockEmployeeAssignment
        from apps.employees.models import Employee

        tenant = self._make_tenant(step=3)
        self._attach_tenant(user, tenant)
        time_clock = TimeClock.all_objects.create(
            tenant=tenant,
            created_by=user,
            nome="Relogio Portaria",
            activation_code="RS12TU",
        )
        employee = Employee.all_objects.create(
            tenant=tenant,
            nome="Francisco Gadelha",
            cpf="44444444444",
            pis="44444444444",
            ativo=True,
        )
        TimeClockEmployeeAssignment.objects.create(
            tenant=tenant,
            time_clock=time_clock,
            employee=employee,
        )
        client.force_login(user)

        response = client.post(
            f"/painel/relogios/{time_clock.id}/?aba=colaboradores",
            data={
                "aba": "colaboradores",
                "action": "remove_selected",
                "assigned_employee_ids": [str(employee.id)],
                "available_q": "",
                "assigned_q": "",
            },
            follow=False,
        )

        assert response.status_code == 302
        assert response.url == f"/painel/relogios/{time_clock.id}/?aba=colaboradores&available_q=&assigned_q="
        assert not TimeClockEmployeeAssignment.all_objects.filter(
            tenant=tenant,
            time_clock=time_clock,
            employee=employee,
        ).exists()
