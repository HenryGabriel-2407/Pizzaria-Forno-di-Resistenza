from http import HTTPStatus
from unittest.mock import patch

from pizzaria_system.models import PasswordResetToken
from pizzaria_system.security import verify_password_hash

# Caminho correto da função usada no router
SEND_EMAIL_PATH = "routers.auth.send_reset_password_email"


# ---------- Testes de Forgot Password ----------
class TestForgotPassword:
    def test_email_inexistente_retorna_sucesso(self, client):
        response = client.post("/auth/forgot-password", json={
            "email": "naoexiste@teste.com",
        })
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["token_ttl_minutes"] == 30

    def test_cliente_recebe_token(self, client, cliente_comum):
        with patch(SEND_EMAIL_PATH, return_value=True) as mock:
            response = client.post("/auth/forgot-password", json={
                "email": cliente_comum.email,
            })
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["token_ttl_minutes"] == 30
        mock.assert_called_once()
        # A função é chamada com argumentos nomeados
        kwargs = mock.call_args[1]
        assert kwargs["to_email"] == cliente_comum.email
        assert "code" in kwargs
        assert isinstance(kwargs["code"], str)
        assert len(kwargs["code"]) == 6
        assert kwargs["ttl_minutes"] == 30

    def test_funcionario_recebe_token(self, client, admin_user):
        with patch(SEND_EMAIL_PATH, return_value=True) as mock:
            response = client.post("/auth/forgot-password", json={
                "email": admin_user.email,
            })
        assert response.status_code == HTTPStatus.OK
        assert response.json()["token_ttl_minutes"] == 30
        mock.assert_called_once()
        kwargs = mock.call_args[1]
        assert kwargs["to_email"] == admin_user.email

    def test_token_salvo_no_banco(self, client, cliente_comum, db_session):
        with patch(SEND_EMAIL_PATH, return_value=True):
            client.post("/auth/forgot-password", json={
                "email": cliente_comum.email,
            })
        tokens = db_session.query(PasswordResetToken).filter_by(
            email=cliente_comum.email, used=False
        ).all()
        assert len(tokens) >= 1
        token = tokens[-1]
        assert token.email == cliente_comum.email
        assert token.expires_at is not None
        assert token.used is False

    def test_token_hash_valido(self, client, cliente_comum, db_session):
        with patch(SEND_EMAIL_PATH, return_value=True) as mock:
            client.post("/auth/forgot-password", json={
                "email": cliente_comum.email,
            })
        kwargs = mock.call_args[1]
        raw_code = kwargs["code"]
        assert raw_code is not None
        token = db_session.query(PasswordResetToken).filter_by(
            email=cliente_comum.email, used=False
        ).order_by(PasswordResetToken.id.desc()).first()
        assert token is not None
        assert verify_password_hash(raw_code, token.token_hash)


# ---------- Testes de Reset Password ----------
class TestResetPassword:
    def _get_valid_code(self, client, email):
        with patch(SEND_EMAIL_PATH, return_value=True) as mock:
            client.post("/auth/forgot-password", json={"email": email})
        kwargs = mock.call_args[1]
        return kwargs["code"]

    def test_reset_com_token_valido_cliente(self, client, cliente_comum, db_session):
        code = self._get_valid_code(client, cliente_comum.email)
        assert code is not None

        new_password = "nova_senha_123"
        response = client.post("/auth/reset-password", json={
            "email": cliente_comum.email,
            "token": code,
            "new_password": new_password,
        })
        assert response.status_code == HTTPStatus.OK
        assert response.json()["message"] == "Senha redefinida com sucesso."

        login_resp = client.post("/auth/token", data={
            "username": cliente_comum.email,
            "password": new_password,
        })
        assert login_resp.status_code == HTTPStatus.OK

    def test_reset_com_token_valido_funcionario(self, client, admin_user, db_session):
        code = self._get_valid_code(client, admin_user.email)
        assert code is not None

        new_password = "nova_admin_senha"
        response = client.post("/auth/reset-password", json={
            "email": admin_user.email,
            "token": code,
            "new_password": new_password,
        })
        assert response.status_code == HTTPStatus.OK

        login_resp = client.post("/auth/token", data={
            "username": admin_user.email,
            "password": new_password,
        })
        assert login_resp.status_code == HTTPStatus.OK

    def test_token_marcado_como_usado(self, client, cliente_comum, db_session):
        email = cliente_comum.email
        code = self._get_valid_code(client, email)
        assert code is not None

        client.post("/auth/reset-password", json={
            "email": email,
            "token": code,
            "new_password": "outra_senha",
        })

        tokens_usados = db_session.query(PasswordResetToken).filter_by(
            email=email, used=True
        ).all()
        assert len(tokens_usados) >= 1

    def test_token_reutilizado_retorna_erro(self, client, cliente_comum, db_session):
        email = cliente_comum.email
        code = self._get_valid_code(client, email)
        assert code is not None

        client.post("/auth/reset-password", json={
            "email": email,
            "token": code,
            "new_password": "senha_primeiro_uso",
        })

        response = client.post("/auth/reset-password", json={
            "email": email,
            "token": code,
            "new_password": "tentativa_reuso",
        })
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_token_invalido(self, client):
        response = client.post("/auth/reset-password", json={
            "email": "qualquer@teste.com",
            "token": "000000",
            "new_password": "qualquer_senha",
        })
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_email_inexistente_reset(self, client):
        response = client.post("/auth/reset-password", json={
            "email": "naoexiste@teste.com",
            "token": "123456",
            "new_password": "qualquer_senha",
        })
        assert response.status_code == HTTPStatus.BAD_REQUEST
