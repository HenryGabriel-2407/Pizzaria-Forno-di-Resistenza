from datetime import datetime, timedelta
from http import HTTPStatus

import pytest

from pizzaria_system.models import AuditLog, Funcionario
from pizzaria_system.security import get_password_hash


# ---------- Fixtures ----------
@pytest.fixture
def sample_logs(db_session):
    agora = datetime.now()
    logs = [
        AuditLog(
            usuario_tipo="funcionario",
            usuario_id=1,
            funcionario_id=1,
            acao="criar",
            tabela_afetada="produto",
            registro_id=100,
            dados_anteriores=None,
            dados_novos={"nome": "Pizza"},
            ip="127.0.0.1",
            user_agent="pytest",
        ),
        AuditLog(
            usuario_tipo="cliente",
            usuario_id=10,
            funcionario_id=None,
            acao="finalizar_pedido",
            tabela_afetada="comanda",
            registro_id=200,
            dados_anteriores=None,
            dados_novos=None,
            ip="192.168.1.1",
            user_agent="pytest",
        ),
        AuditLog(
            usuario_tipo="funcionario",
            usuario_id=2,
            funcionario_id=2,
            acao="excluir",
            tabela_afetada="funcionario",
            registro_id=300,
            dados_anteriores=None,
            dados_novos=None,
            ip=None,
            user_agent=None,
        ),
    ]
    timestamps = [agora, agora - timedelta(hours=1), agora - timedelta(days=1)]
    for log, ts in zip(logs, timestamps):
        log.timestamp = ts
        db_session.add(log)
    db_session.commit()
    for log in logs:
        db_session.refresh(log)
    return logs


@pytest.fixture
def garcom_user(db_session):
    garcom = db_session.query(Funcionario).filter_by(email="garcom_aud@teste.com").first()
    if not garcom:
        garcom = Funcionario(
            nome="Garçom Auditoria",
            email="garcom_aud@teste.com",
            senha_hash=get_password_hash("123456"),
            cargo="garcom",
            telefone="11977777777",
            ativo=True,
        )
        db_session.add(garcom)
        db_session.commit()
        db_session.refresh(garcom)
    return garcom


@pytest.fixture
def garcom_token(client, garcom_user):
    response = client.post("/auth/token", data={
        "username": garcom_user.email,
        "password": "123456",
    })
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def garcom_headers(garcom_token):
    return {"Authorization": f"Bearer {garcom_token}"}


@pytest.fixture
def gerente_user(db_session):
    gerente = db_session.query(Funcionario).filter_by(email="gerente@teste.com").first()
    if not gerente:
        gerente = Funcionario(
            nome="Gerente Teste",
            email="gerente@teste.com",
            senha_hash=get_password_hash("gerente123"),
            cargo="gerente",
            telefone="11988888888",
            ativo=True,
        )
        db_session.add(gerente)
        db_session.commit()
        db_session.refresh(gerente)
    return gerente


@pytest.fixture
def gerente_token(client, gerente_user):
    response = client.post("/auth/token", data={
        "username": gerente_user.email,
        "password": "gerente123"
    })
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def gerente_headers(gerente_token):
    return {"Authorization": f"Bearer {gerente_token}"}


# ---------- Testes de Permissão ----------
class TestPermissao:
    def test_sem_autenticacao(self, client):
        response = client.get("/audit-logs/")
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_cliente_sem_permissao(self, client, cliente_headers):
        response = client.get("/audit-logs/", headers=cliente_headers)
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_garcom_sem_permissao(self, client, garcom_headers):
        response = client.get("/audit-logs/", headers=garcom_headers)
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_admin_com_permissao(self, client, admin_headers):
        response = client.get("/audit-logs/", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK

    def test_gerente_com_permissao(self, client, gerente_headers):
        response = client.get("/audit-logs/", headers=gerente_headers)
        assert response.status_code == HTTPStatus.OK


# ---------- Testes de Listagem ----------
class TestListarLogs:
    def test_listar_todos(self, client, admin_headers, sample_logs):
        response = client.get("/audit-logs/", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) >= 3
        acoes = [log["acao"] for log in data]
        assert "criar" in acoes
        assert "finalizar_pedido" in acoes
        assert "excluir" in acoes

    def test_filtro_usuario_tipo(self, client, admin_headers, sample_logs):
        response = client.get("/audit-logs/?usuario_tipo=cliente", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK
        assert all(log["usuario_tipo"] == "cliente" for log in response.json())

    def test_filtro_acao(self, client, admin_headers, sample_logs):
        response = client.get("/audit-logs/?acao=criar", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK
        assert all(log["acao"] == "criar" for log in response.json())

    def test_filtro_tabela_afetada(self, client, admin_headers, sample_logs):
        response = client.get("/audit-logs/?tabela_afetada=comanda", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK
        assert all(log["tabela_afetada"] == "comanda" for log in response.json())

    def test_filtro_funcionario_id(self, client, admin_headers, sample_logs):
        response = client.get("/audit-logs/?funcionario_id=1", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK
        assert all(log["funcionario_id"] == 1 for log in response.json())

    def test_filtro_registro_id(self, client, admin_headers, sample_logs):
        response = client.get("/audit-logs/?registro_id=200", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK
        assert all(log["registro_id"] == 200 for log in response.json())

    def test_filtro_periodo_data(self, client, admin_headers, sample_logs):
        data_inicio = (datetime.now() - timedelta(hours=2)).isoformat()
        response = client.get(
            f"/audit-logs/?data_inicio={data_inicio}",
            headers=admin_headers,
        )
        assert response.status_code == HTTPStatus.OK
        acoes = [log["acao"] for log in response.json()]
        assert "criar" in acoes

    def test_paginacao_limite(self, client, admin_headers, sample_logs):
        response = client.get("/audit-logs/?limite=1", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK
        assert len(response.json()) == 1

    def test_paginacao_offset(self, client, admin_headers, sample_logs):
        response_all = client.get("/audit-logs/", headers=admin_headers)
        total = len(response_all.json())
        if total > 1:
            response_offset = client.get(
                f"/audit-logs/?limite=1&offset={total - 1}",
                headers=admin_headers,
            )
            assert response_offset.status_code == HTTPStatus.OK
            assert len(response_offset.json()) == 1

    def test_ordenacao_asc(self, client, admin_headers, sample_logs):
        response = client.get("/audit-logs/?order_by=acao&order=asc", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        acoes = [log["acao"] for log in data]
        assert acoes == sorted(acoes)

    def test_ordenacao_desc(self, client, admin_headers, sample_logs):
        response = client.get("/audit-logs/?order_by=acao&order=desc", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        acoes = [log["acao"] for log in data]
        assert acoes == sorted(acoes, reverse=True)


# ---------- Testes de Obter Log Específico ----------
class TestObterLog:
    def test_log_existente(self, client, admin_headers, sample_logs):
        log_id = sample_logs[0].id
        response = client.get(f"/audit-logs/{log_id}", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["id"] == log_id
        assert data["acao"] == "criar"

    def test_log_inexistente(self, client, admin_headers):
        response = client.get("/audit-logs/99999", headers=admin_headers)
        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_log_sem_permissao(self, client, cliente_headers, sample_logs):
        log_id = sample_logs[0].id
        response = client.get(f"/audit-logs/{log_id}", headers=cliente_headers)
        assert response.status_code == HTTPStatus.FORBIDDEN


# ---------- Testes de Ações Disponíveis ----------
class TestAcoesDisponiveis:
    def test_listar_acoes(self, client, admin_headers, sample_logs):
        response = client.get("/audit-logs/acoes/disponiveis", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "criar" in data
        assert "finalizar_pedido" in data
        assert "excluir" in data

    def test_acoes_sem_permissao(self, client, cliente_headers):
        response = client.get("/audit-logs/acoes/disponiveis", headers=cliente_headers)
        assert response.status_code == HTTPStatus.FORBIDDEN


# ---------- Testes de Tabelas Afetadas Disponíveis ----------
class TestTabelasDisponiveis:
    def test_listar_tabelas(self, client, admin_headers, sample_logs):
        response = client.get("/audit-logs/tabelas/disponiveis", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "produto" in data
        assert "comanda" in data
        assert "funcionario" in data

    def test_tabelas_sem_permissao(self, client, cliente_headers):
        response = client.get("/audit-logs/tabelas/disponiveis", headers=cliente_headers)
        assert response.status_code == HTTPStatus.FORBIDDEN


# ---------- Testes de Estatísticas ----------
class TestEstatisticas:
    def test_estatisticas_por_acao(self, client, admin_headers, sample_logs):
        response = client.get("/audit-logs/estatisticas/por-acao", headers=admin_headers)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data.get("criar", 0) >= 1
        assert data.get("finalizar_pedido", 0) >= 1
        assert data.get("excluir", 0) >= 1

    def test_estatisticas_filtro_periodo(self, client, admin_headers, sample_logs):
        data_inicio = (datetime.now() - timedelta(hours=2)).isoformat()
        response = client.get(
            f"/audit-logs/estatisticas/por-acao?data_inicio={data_inicio}",
            headers=admin_headers,
        )
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "excluir" not in data

    def test_estatisticas_sem_permissao(self, client, cliente_headers):
        response = client.get("/audit-logs/estatisticas/por-acao", headers=cliente_headers)
        assert response.status_code == HTTPStatus.FORBIDDEN
