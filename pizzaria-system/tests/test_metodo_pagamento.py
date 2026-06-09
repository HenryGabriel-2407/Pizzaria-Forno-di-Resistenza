import uuid
from datetime import datetime
from http import HTTPStatus

import pytest

from pizzaria_system.models import Cliente, Comanda, Mesa, MetodoPagamento, PedidoItem


# Fixture de limpeza automática
@pytest.fixture(autouse=True)
def clean_metodo_pagamento_table(db_session):
    """Remove todos os métodos de pagamento após cada teste, tratando rollback."""
    try:
        db_session.rollback()
    except Exception:
        pass
    yield
    # Limpeza segura: primeiro remove dependências (comandas, itens)
    db_session.query(PedidoItem).delete()
    db_session.query(Comanda).delete()
    db_session.query(MetodoPagamento).delete()
    db_session.commit()


# ---------- Fixtures auxiliares ----------
@pytest.fixture
def metodo_pagamento_criado(client, admin_headers) -> dict:
    """Cria e retorna um método de pagamento para uso nos testes (requer admin)."""
    response = client.post(
        "/metodos-pagamento/",
        headers=admin_headers,
        json={"nome": "PIX", "ativo": True}
    )
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


@pytest.fixture
def metodo_id(metodo_pagamento_criado) -> int:
    return metodo_pagamento_criado["id"]


# ========== Testes de Criação (requer autenticação) ==========
def test_criar_metodo_pagamento_sucesso(client, admin_headers):
    nome_unico = f"Metodo_{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/metodos-pagamento/",
        headers=admin_headers,
        json={"nome": nome_unico, "ativo": True}
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["nome"] == nome_unico
    assert data["ativo"] is True


def test_criar_metodo_pagamento_sem_autenticacao(client):
    response = client.post("/metodos-pagamento/", json={"nome": "SemAuth"})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_criar_metodo_pagamento_com_cliente(client, cliente_headers):
    response = client.post(
        "/metodos-pagamento/",
        headers=cliente_headers,
        json={"nome": "ClienteTenta"}
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_criar_metodo_pagamento_sem_ativo(client, admin_headers):
    """Deve criar com ativo=True por padrão."""
    response = client.post(
        "/metodos-pagamento/",
        headers=admin_headers,
        json={"nome": "Cartão"}
    )
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["ativo"] is True


def test_criar_metodo_pagamento_nome_duplicado(client, admin_headers):
    client.post("/metodos-pagamento/", headers=admin_headers, json={"nome": "PIX_dup"})
    response = client.post("/metodos-pagamento/", headers=admin_headers, json={"nome": "PIX_dup"})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "já existe" in response.text.lower()


# ========== Testes de Leitura (públicos) ==========
def test_listar_metodos_pagamento(client, admin_headers):
    # Cria métodos via admin
    client.post("/metodos-pagamento/", headers=admin_headers, json={"nome": "PIX_lista"})
    client.post("/metodos-pagamento/", headers=admin_headers, json={"nome": "Cartão_lista"})
    response = client.get("/metodos-pagamento/")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data) >= 2
    nomes = [m["nome"] for m in data]
    assert "PIX_lista" in nomes
    assert "Cartão_lista" in nomes


def test_listar_metodos_pagamento_filtrando_por_ativo(client, admin_headers):
    client.post("/metodos-pagamento/", headers=admin_headers, json={"nome": "Dinheiro_filtro", "ativo": True})
    client.post("/metodos-pagamento/", headers=admin_headers, json={"nome": "Cheque_filtro", "ativo": False})

    response = client.get("/metodos-pagamento/?ativo=true")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert all(m["ativo"] is True for m in data)
    assert len(data) == 1
    assert data[0]["nome"] == "Dinheiro_filtro"

    response = client.get("/metodos-pagamento/?ativo=false")
    data = response.json()
    assert all(m["ativo"] is False for m in data)
    assert len(data) == 1
    assert data[0]["nome"] == "Cheque_filtro"


def test_obter_metodo_pagamento_por_id(client, metodo_id):
    response = client.get(f"/metodos-pagamento/{metodo_id}")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == metodo_id
    assert data["nome"] == "PIX"


def test_obter_metodo_pagamento_inexistente(client):
    response = client.get("/metodos-pagamento/999")
    assert response.status_code == HTTPStatus.NOT_FOUND


# ========== Testes de Atualização (requer autenticação) ==========
def test_atualizar_metodo_pagamento_completo(client, admin_headers, metodo_id):
    response = client.put(
        f"/metodos-pagamento/{metodo_id}",
        headers=admin_headers,
        json={"nome": "PIX Atualizado", "ativo": False}
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["nome"] == "PIX Atualizado"
    assert data["ativo"] is False


def test_atualizar_metodo_pagamento_sem_autenticacao(client, metodo_id):
    response = client.put(f"/metodos-pagamento/{metodo_id}", json={"ativo": False})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_atualizar_metodo_pagamento_com_cliente(client, cliente_headers, metodo_id):
    response = client.put(
        f"/metodos-pagamento/{metodo_id}",
        headers=cliente_headers,
        json={"ativo": False}
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_atualizar_metodo_pagamento_parcial(client, admin_headers, metodo_id):
    response = client.put(
        f"/metodos-pagamento/{metodo_id}",
        headers=admin_headers,
        json={"ativo": False}
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["nome"] == "PIX"  # não alterado
    assert data["ativo"] is False


def test_atualizar_metodo_pagamento_nome_duplicado(client, admin_headers):
    client.post("/metodos-pagamento/", headers=admin_headers, json={"nome": "Vale"})
    resp2 = client.post("/metodos-pagamento/", headers=admin_headers, json={"nome": "Vale Refeição"})
    id2 = resp2.json()["id"]
    response = client.put(
        f"/metodos-pagamento/{id2}",
        headers=admin_headers,
        json={"nome": "Vale"}
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "já existe" in response.text.lower()


def test_atualizar_metodo_pagamento_inexistente(client, admin_headers):
    response = client.put("/metodos-pagamento/999", headers=admin_headers, json={"nome": "Novo"})
    assert response.status_code == HTTPStatus.NOT_FOUND


# ========== Testes de Exclusão (requer autenticação) ==========
def test_deletar_metodo_pagamento_sem_comandas(client, admin_headers, metodo_id):
    response = client.delete(f"/metodos-pagamento/{metodo_id}", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["success"] is True
    get_resp = client.get(f"/metodos-pagamento/{metodo_id}")
    assert get_resp.status_code == HTTPStatus.NOT_FOUND


def test_deletar_metodo_pagamento_sem_autenticacao(client, metodo_id):
    response = client.delete(f"/metodos-pagamento/{metodo_id}")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_deletar_metodo_pagamento_com_cliente(client, cliente_headers, metodo_id):
    response = client.delete(f"/metodos-pagamento/{metodo_id}", headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_deletar_metodo_pagamento_com_comandas_associadas(client, admin_headers, db_session, metodo_id):
    # Usa dados únicos para evitar conflitos
    email_unico = f"teste_{uuid.uuid4().hex[:8]}@email.com"
    cliente = Cliente(
        nome="Teste",
        email=email_unico,
        senha_hash="hash",
        ativo=True,
        telefone=None,
        documento=None
    )
    mesa = Mesa(numero=999, qtd_lugares=4, status="livre")
    db_session.add_all([cliente, mesa])
    db_session.commit()

    comanda = Comanda(
        id_cliente=cliente.id,
        id_mesa=mesa.id,
        id_garcom=None,
        id_metodo_pagamento=metodo_id,
        id_cod_promocional=None,
        valor_a_pagar=50.0,
        tipo_entrega="local",
        origem="web",
        data_registro=datetime.now(),
        data_finalizacao=None,
        observacao_geral=None,
        preco_total=50.0
    )
    db_session.add(comanda)
    db_session.commit()

    response = client.delete(f"/metodos-pagamento/{metodo_id}", headers=admin_headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "vinculado" in response.text.lower() or "comandas" in response.text.lower()

    get_resp = client.get(f"/metodos-pagamento/{metodo_id}")
    assert get_resp.status_code == HTTPStatus.OK
