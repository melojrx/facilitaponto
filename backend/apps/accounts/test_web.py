import re

import pytest

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

    def test_painel_autocorrige_vinculo_tenant_por_email_contato(self, client, user):
        tenant = Tenant.objects.create(
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
        assert user.tenant_id == tenant.id
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
