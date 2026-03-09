import re

import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.accounts.models import User
from apps.tenants.models import Tenant


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
        assert response.url == "/painel/"

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

    # --- POST válido ---

    def test_post_valido_cria_jornada_e_avanca_onboarding(self, client, user):
        from apps.employees.models import WorkSchedule

        tenant = self._make_tenant(step=2)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        response = client.post(
            self.URL,
            data={"nome": "Jornada Padrão 44h", "descricao": "Segunda a sexta", "tipo": "SEMANAL"},
            follow=False,
        )

        tenant.refresh_from_db()
        assert response.status_code == 302
        assert response.url == "/painel/"
        assert tenant.onboarding_step == 3
        assert WorkSchedule.all_objects.filter(tenant=tenant, nome="Jornada Padrão 44h").exists()

    def test_post_tipo_12x36_salva_corretamente(self, client, user):
        from apps.employees.models import WorkSchedule

        tenant = self._make_tenant(step=2)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        client.post(
            self.URL,
            data={"nome": "Plantão 12x36", "descricao": "", "tipo": "12X36"},
            follow=False,
        )

        assert WorkSchedule.all_objects.filter(
            tenant=tenant, nome="Plantão 12x36", tipo="12X36"
        ).exists()

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
            data={"nome": "", "tipo": "SEMANAL"},
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
            data={"nome": "Jornada Padrão", "descricao": "", "tipo": "SEMANAL"},
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

    # --- liberação de menu ---

    def test_menu_libera_todos_modulos_apos_primeira_jornada(self, client, user):
        import re


        tenant = self._make_tenant(step=2)
        self._attach_tenant(user, tenant)
        client.force_login(user)

        client.post(
            self.URL,
            data={"nome": "Jornada Inicial", "descricao": "", "tipo": "SEMANAL"},
            follow=False,
        )

        response = client.get("/painel/")
        content = response.content.decode()

        assert re.search(r'data-menu-key="colaboradores"[\s\S]*?data-menu-state="enabled"', content)
        assert re.search(r'data-menu-key="relogio_digital"[\s\S]*?data-menu-state="enabled"', content)
