from http import HTTPStatus

import pytest

from pizzaria_system.models import Comanda, Mesa, MetodoPagamento


# ========== Fixtures específicas para Mesa ==========
@pytest.fixture
def mesa_criada(client, admin_headers) -> dict:
    """Cria e retorna uma mesa (dicionário) para uso nos testes (requer admin)."""
    response = client.post(
        "/mesas/",
        headers=admin_headers,
        json={"numero": 100, "qtd_lugares": 4, "status": "livre"}
    )
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


@pytest.fixture
def mesa_id(mesa_criada) -> int:
    return mesa_criada["id"]


@pytest.fixture(autouse=True)
def clean_mesa_table(db_session):
    """Limpa as mesas após cada teste (evita interferência entre testes)."""
    db_session.rollback()
    yield
    db_session.query(Mesa).delete()
    db_session.commit()


# ========== Testes de Criação (requer autenticação) ==========
def test_criar_mesa_sucesso(client, admin_headers):
    response = client.post(
        "/mesas/",
        headers=admin_headers,
        json={"numero": 1, "qtd_lugares": 4, "status": "livre"}
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["numero"] == 1
    assert data["qtd_lugares"] == 4
    assert data["status"] == "livre"
    assert data["codigo_qr"] is not None
    assert data["codigo_qr"].endswith(f"/mesa/{data['id']}")


def test_criar_mesa_sem_autenticacao(client):
    response = client.post("/mesas/", json={"numero": 1})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_criar_mesa_com_cliente(client, cliente_headers):
    response = client.post("/mesas/", headers=cliente_headers, json={"numero": 1})
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_criar_mesa_com_qtd_lugares_padrao(client, admin_headers):
    response = client.post("/mesas/", headers=admin_headers, json={"numero": 2})
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["qtd_lugares"] == 4


def test_criar_mesa_numero_duplicado(client, admin_headers):
    client.post("/mesas/", headers=admin_headers, json={"numero": 3})
    response = client.post("/mesas/", headers=admin_headers, json={"numero": 3})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Número de mesa 3 já está em uso" in response.text


def test_criar_mesa_numero_invalido(client, admin_headers):
    response = client.post("/mesas/", headers=admin_headers, json={"numero": -1})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    response = client.post("/mesas/", headers=admin_headers, json={"numero": 0})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_criar_mesa_status_invalido(client, admin_headers):
    response = client.post("/mesas/", headers=admin_headers, json={"numero": 4, "status": "quebrada"})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# ========== Testes de Leitura (públicos, sem autenticação) ==========
def test_listar_mesas_sem_filtro(client, admin_headers):
    # Cria mesas usando admin
    client.post("/mesas/", headers=admin_headers, json={"numero": 5})
    client.post("/mesas/", headers=admin_headers, json={"numero": 6})
    response = client.get("/mesas/")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 2


def test_listar_mesas_com_filtro_status(client, admin_headers):
    client.post("/mesas/", headers=admin_headers, json={"numero": 7, "status": "livre"})
    client.post("/mesas/", headers=admin_headers, json={"numero": 8, "status": "ocupada"})
    response = client.get("/mesas/?status=livre")
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "livre"

    response = client.get("/mesas/?status=invalid")
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_listar_mesas_paginacao(client, admin_headers):
    for i in range(1, 6):
        client.post("/mesas/", headers=admin_headers, json={"numero": i + 10})
    response = client.get("/mesas/?limite=2&offset=0")
    assert len(response.json()) == 2
    response = client.get("/mesas/?limite=2&offset=2")
    assert len(response.json()) == 2


def test_obter_mesa_por_id(client, mesa_id):
    response = client.get(f"/mesas/{mesa_id}")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["numero"] == 100


def test_obter_mesa_inexistente(client):
    response = client.get("/mesas/999")
    assert response.status_code == HTTPStatus.NOT_FOUND


# ========== Testes de Atualização (requer autenticação) ==========
def test_atualizar_mesa_completa(client, admin_headers, mesa_id):
    response = client.put(
        f"/mesas/{mesa_id}",
        headers=admin_headers,
        json={"numero": 101, "qtd_lugares": 6, "status": "ocupada", "codigo_qr": "qr_manual"}
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["numero"] == 101
    assert data["qtd_lugares"] == 6
    assert data["status"] == "ocupada"
    assert data["codigo_qr"] == "qr_manual"


def test_atualizar_mesa_sem_autenticacao(client, mesa_id):
    response = client.put(f"/mesas/{mesa_id}", json={"status": "reservada"})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_atualizar_mesa_com_cliente(client, cliente_headers, mesa_id):
    response = client.put(f"/mesas/{mesa_id}", headers=cliente_headers, json={"status": "reservada"})
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_atualizar_mesa_parcial(client, admin_headers, mesa_id):
    response = client.put(f"/mesas/{mesa_id}", headers=admin_headers, json={"status": "reservada"})
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "reservada"
    assert data["numero"] == 100


def test_atualizar_numero_mesa_duplicado(client, admin_headers):
    client.post("/mesas/", headers=admin_headers, json={"numero": 102})
    criar2 = client.post("/mesas/", headers=admin_headers, json={"numero": 103})
    mesa2_id = criar2.json()["id"]
    response = client.put(f"/mesas/{mesa2_id}", headers=admin_headers, json={"numero": 102})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Número de mesa 102 já está em uso" in response.text


def test_atualizar_codigo_qr_duplicado(client, admin_headers):
    resp1 = client.post("/mesas/", headers=admin_headers, json={"numero": 105})
    mesa1_id = resp1.json()["id"]
    client.put(f"/mesas/{mesa1_id}", headers=admin_headers, json={"codigo_qr": "qr_unico"})

    resp2 = client.post("/mesas/", headers=admin_headers, json={"numero": 106})
    mesa2_id = resp2.json()["id"]

    response = client.put(f"/mesas/{mesa2_id}", headers=admin_headers, json={"codigo_qr": "qr_unico"})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "código QR já está associado a outra mesa" in response.text


# ========== Testes de Exclusão (requer autenticação) ==========
def test_deletar_mesa_sem_comandas(client, admin_headers, mesa_id):
    response = client.delete(f"/mesas/{mesa_id}", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["success"] is True
    get_resp = client.get(f"/mesas/{mesa_id}")
    assert get_resp.status_code == HTTPStatus.NOT_FOUND


def test_deletar_mesa_sem_autenticacao(client, mesa_id):
    response = client.delete(f"/mesas/{mesa_id}")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_deletar_mesa_com_cliente(client, cliente_headers, mesa_id):
    response = client.delete(f"/mesas/{mesa_id}", headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_deletar_mesa_com_comandas_associadas(client, admin_headers, db_session, mesa_id):
    from datetime import datetime

    metodo = db_session.query(MetodoPagamento).filter_by(nome="Dinheiro_Teste").first()
    if not metodo:
        metodo = MetodoPagamento(nome="Dinheiro_Teste", ativo=True)
        db_session.add(metodo)
        db_session.commit()
        db_session.refresh(metodo)

    comanda = Comanda(
        id_cliente=None,
        id_mesa=mesa_id,
        id_garcom=None,
        id_metodo_pagamento=metodo.id,
        id_cod_promocional=None,
        valor_a_pagar=100.0,
        tipo_entrega="local",
        origem="web",
        data_registro=datetime.now(),
        data_finalizacao=None,
        observacao_geral=None,
        preco_total=100.0
    )
    db_session.add(comanda)
    db_session.commit()

    response = client.delete(f"/mesas/{mesa_id}", headers=admin_headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "possui comandas" in response.text


# ========== Testes de Controle de Status (requer autenticação) ==========
def test_ocupar_mesa(client, admin_headers, mesa_id):
    response = client.post(f"/mesas/{mesa_id}/ocupar", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["status"] == "ocupada"

    response2 = client.post(f"/mesas/{mesa_id}/ocupar", headers=admin_headers)
    assert response2.status_code == HTTPStatus.BAD_REQUEST
    assert "Mesa já está ocupada" in response2.text


def test_ocupar_mesa_sem_autenticacao(client, mesa_id):
    response = client.post(f"/mesas/{mesa_id}/ocupar")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_ocupar_mesa_com_cliente(client, cliente_headers, mesa_id):
    response = client.post(f"/mesas/{mesa_id}/ocupar", headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_liberar_mesa(client, admin_headers, mesa_id):
    client.post(f"/mesas/{mesa_id}/ocupar", headers=admin_headers)
    response = client.post(f"/mesas/{mesa_id}/liberar", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["status"] == "livre"

    response2 = client.post(f"/mesas/{mesa_id}/liberar", headers=admin_headers)
    assert response2.status_code == HTTPStatus.BAD_REQUEST
    assert "Mesa já está livre" in response2.text


def test_reservar_mesa(client, admin_headers, mesa_id):
    response = client.post(f"/mesas/{mesa_id}/reservar", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["status"] == "reservada"

    response2 = client.post(f"/mesas/{mesa_id}/reservar", headers=admin_headers)
    assert response2.status_code == HTTPStatus.BAD_REQUEST
    assert "Mesa já está reservada" in response2.text


def test_transicoes_entre_status(client, admin_headers, mesa_id):
    client.post(f"/mesas/{mesa_id}/reservar", headers=admin_headers)
    client.post(f"/mesas/{mesa_id}/ocupar", headers=admin_headers)
    assert client.get(f"/mesas/{mesa_id}").json()["status"] == "ocupada"
    client.post(f"/mesas/{mesa_id}/liberar", headers=admin_headers)
    assert client.get(f"/mesas/{mesa_id}").json()["status"] == "livre"


def test_status_endpoint_mesa_inexistente(client, admin_headers):
    for action in ["ocupar", "liberar", "reservar"]:
        response = client.post(f"/mesas/999/{action}", headers=admin_headers)
        assert response.status_code == HTTPStatus.NOT_FOUND
