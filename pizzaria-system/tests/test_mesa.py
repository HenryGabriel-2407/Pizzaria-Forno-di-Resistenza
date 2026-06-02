from http import HTTPStatus

import pytest

from pizzaria_system.models import Comanda, Mesa, MetodoPagamento


# ========== Fixtures específicas para Mesa ==========
@pytest.fixture
def mesa_criada(client) -> dict:
    """Cria e retorna uma mesa (dicionário) para uso nos testes."""
    response = client.post("/mesas/", json={"numero": 100, "qtd_lugares": 4, "status": "livre"})
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


# ========== Testes de Criação ==========
def test_criar_mesa_sucesso(client):
    response = client.post("/mesas/", json={"numero": 1, "qtd_lugares": 4, "status": "livre"})
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["numero"] == 1
    assert data["qtd_lugares"] == 4
    assert data["status"] == "livre"
    assert data["codigo_qr"] is not None
    # QR code deve conter a URL base + ID
    assert data["codigo_qr"].endswith(f"/mesa/{data['id']}")


def test_criar_mesa_com_qtd_lugares_padrao(client):
    response = client.post("/mesas/", json={"numero": 2})
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["qtd_lugares"] == 4  # padrão definido no schema


def test_criar_mesa_numero_duplicado(client):
    client.post("/mesas/", json={"numero": 3})
    response = client.post("/mesas/", json={"numero": 3})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Número de mesa 3 já está em uso" in response.text


def test_criar_mesa_numero_invalido(client):
    response = client.post("/mesas/", json={"numero": -1})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    response = client.post("/mesas/", json={"numero": 0})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_criar_mesa_status_invalido(client):
    response = client.post("/mesas/", json={"numero": 4, "status": "quebrada"})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# ========== Testes de Leitura ==========
def test_listar_mesas_sem_filtro(client):
    client.post("/mesas/", json={"numero": 5})
    client.post("/mesas/", json={"numero": 6})
    response = client.get("/mesas/")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 2


def test_listar_mesas_com_filtro_status(client):
    client.post("/mesas/", json={"numero": 7, "status": "livre"})
    client.post("/mesas/", json={"numero": 8, "status": "ocupada"})
    response = client.get("/mesas/?status=livre")
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "livre"

    response = client.get("/mesas/?status=invalid")
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_listar_mesas_paginacao(client):
    for i in range(1, 6):
        client.post("/mesas/", json={"numero": i + 10})
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


# ========== Testes de Atualização ==========
def test_atualizar_mesa_completa(client, mesa_id):
    response = client.put(
        f"/mesas/{mesa_id}",
        json={"numero": 101, "qtd_lugares": 6, "status": "ocupada", "codigo_qr": "qr_manual"}
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["numero"] == 101
    assert data["qtd_lugares"] == 6
    assert data["status"] == "ocupada"
    assert data["codigo_qr"] == "qr_manual"


def test_atualizar_mesa_parcial(client, mesa_id):
    response = client.put(f"/mesas/{mesa_id}", json={"status": "reservada"})
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "reservada"
    assert data["numero"] == 100  # não alterado


def test_atualizar_numero_mesa_duplicado(client):
    client.post("/mesas/", json={"numero": 102})
    criar2 = client.post("/mesas/", json={"numero": 103})
    mesa2_id = criar2.json()["id"]
    response = client.put(f"/mesas/{mesa2_id}", json={"numero": 102})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Número de mesa 102 já está em uso" in response.text


def test_atualizar_codigo_qr_duplicado(client):
    # Cria primeira mesa
    resp1 = client.post("/mesas/", json={"numero": 105})
    mesa1_id = resp1.json()["id"]
    # Atualiza a primeira mesa com QR manual
    client.put(f"/mesas/{mesa1_id}", json={"codigo_qr": "qr_unico"})

    # Cria segunda mesa
    resp2 = client.post("/mesas/", json={"numero": 106})
    mesa2_id = resp2.json()["id"]

    # Tenta usar o mesmo QR na segunda mesa - deve falhar
    response = client.put(f"/mesas/{mesa2_id}", json={"codigo_qr": "qr_unico"})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "código QR já está associado a outra mesa" in response.text


# ========== Testes de Exclusão ==========
def test_deletar_mesa_sem_comandas(client, mesa_id):
    response = client.delete(f"/mesas/{mesa_id}")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["success"] is True
    # Verifica que foi removida
    get_resp = client.get(f"/mesas/{mesa_id}")
    assert get_resp.status_code == HTTPStatus.NOT_FOUND


def test_deletar_mesa_com_comandas_associadas(client, db_session, mesa_id):
    from datetime import datetime

    # Cria método de pagamento
    metodo = db_session.query(MetodoPagamento).filter_by(nome="Dinheiro_Teste").first()
    if not metodo:
        metodo = MetodoPagamento(nome="Dinheiro_Teste", ativo=True)
        db_session.add(metodo)
        db_session.commit()
        db_session.refresh(metodo)

    # Cria comanda vinculada à mesa (fornecendo todos os argumentos obrigatórios)
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

    # Tenta deletar a mesa - deve falhar devido à comanda associada
    response = client.delete(f"/mesas/{mesa_id}")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "possui comandas" in response.text


# ========== Testes de Controle de Status ==========
def test_ocupar_mesa(client, mesa_id):
    response = client.post(f"/mesas/{mesa_id}/ocupar")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["status"] == "ocupada"

    # Segunda tentativa deve falhar
    response2 = client.post(f"/mesas/{mesa_id}/ocupar")
    assert response2.status_code == HTTPStatus.BAD_REQUEST
    assert "Mesa já está ocupada" in response2.text


def test_liberar_mesa(client, mesa_id):
    # Primeiro ocupa para depois liberar
    client.post(f"/mesas/{mesa_id}/ocupar")
    response = client.post(f"/mesas/{mesa_id}/liberar")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["status"] == "livre"

    response2 = client.post(f"/mesas/{mesa_id}/liberar")
    assert response2.status_code == HTTPStatus.BAD_REQUEST
    assert "Mesa já está livre" in response2.text


def test_reservar_mesa(client, mesa_id):
    response = client.post(f"/mesas/{mesa_id}/reservar")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["status"] == "reservada"

    response2 = client.post(f"/mesas/{mesa_id}/reservar")
    assert response2.status_code == HTTPStatus.BAD_REQUEST
    assert "Mesa já está reservada" in response2.text


def test_transicoes_entre_status(client, mesa_id):
    # Livre -> Reservada
    client.post(f"/mesas/{mesa_id}/reservar")
    # Reservada -> Ocupada
    client.post(f"/mesas/{mesa_id}/ocupar")
    assert client.get(f"/mesas/{mesa_id}").json()["status"] == "ocupada"
    # Ocupada -> Livre
    client.post(f"/mesas/{mesa_id}/liberar")
    assert client.get(f"/mesas/{mesa_id}").json()["status"] == "livre"


def test_status_endpoint_mesa_inexistente(client):
    for action in ["ocupar", "liberar", "reservar"]:
        response = client.post(f"/mesas/999/{action}")
        assert response.status_code == HTTPStatus.NOT_FOUND
