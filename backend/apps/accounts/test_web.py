import pytest

from apps.accounts.models import User


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="owner@acme.com",
        password="Forte123!",
        role=User.Role.ADMIN,
    )


@pytest.mark.django_db
class TestWebPublicPages:
    def test_landing_publica(self, client):
        response = client.get("/")

        assert response.status_code == 200
        assert "Criar conta" in response.content.decode()

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
                "email": "novo@acme.com",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
            },
            follow=False,
        )

        assert response.status_code == 302
        assert response.url == "/painel/"
        assert User.objects.filter(email="novo@acme.com").exists()
        assert client.session.get("_auth_user_id") is not None

    def test_signup_rejeita_email_duplicado(self, client, user):
        response = client.post(
            "/cadastro/",
            data={
                "email": user.email,
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
