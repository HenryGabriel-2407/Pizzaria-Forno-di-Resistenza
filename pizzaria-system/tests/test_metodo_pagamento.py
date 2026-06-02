import uuid
from datetime import datetime
from http import HTTPStatus

import pytest

from pizzaria_system.models import Cliente, Comanda, Mesa, MetodoPagamento


# Fixture de limpeza automática
@pytest.fixture(autouse=True)
def clean_metodo_pagamento_table(db_session):
    """Remove todos os métodos de pagamento após cada teste, tratando rollback."""
    # Reseta a sessão para evitar PendingRollbackError
    try:
        db_session.rollback()
    except Exception:
        pass
    yield
    # Limpeza segura: primeiro remove dependências (comandas, itens) se houver
    from pizzaria_system.models import Comanda, PedidoItem
    db_session.query(PedidoItem).delete()
    db_session.query(Comanda).delete()
    db_session.query(MetodoPagamento).delete()
    db_session.commit()


# ---------- Fixtures auxiliares ----------
@pytest.fixture
def metodo_pagamento_criado(client) -> dict:
    """Cria e retorna um método de pagamento para uso nos testes."""
    response = client.post("/metodos-pagamento/", json={"nome": "PIX", "ativo": True})
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


@pytest.fixture
def metodo_id(metodo_pagamento_criado) -> int:
    return metodo_pagamento_criado["id"]


# ========== Testes de Criação ==========
def test_criar_metodo_pagamento_sucesso(client):
    nome_unico = f"Metodo_{uuid.uuid4().hex[:8]}"
    response = client.post("/metodos-pagamento/", json={"nome": nome_unico, "ativo": True})
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["nome"] == nome_unico
    assert data["ativo"] is True


def test_criar_metodo_pagamento_sem_ativo(client):
    """Deve criar com ativo=True por padrão."""
    response = client.post("/metodos-pagamento/", json={"nome": "Cartão"})
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["ativo"] is True


def test_criar_metodo_pagamento_nome_duplicado(client):
    client.post("/metodos-pagamento/", json={"nome": "PIX"})
    response = client.post("/metodos-pagamento/", json={"nome": "PIX"})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "duplicate" in response.text.lower() or "Já existe" in response.text


# ========== Testes de Leitura ==========
def test_listar_metodos_pagamento(client):
    # Cria um segundo método
    client.post("/metodos-pagamento/", json={"nome": "PIX"})
    client.post("/metodos-pagamento/", json={"nome": "Cartão"})
    response = client.get("/metodos-pagamento/")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data) >= 2
    nomes = [m["nome"] for m in data]
    assert "PIX" in nomes
    assert "Cartão" in nomes


def test_listar_metodos_pagamento_filtrando_por_ativo(client):
    client.post("/metodos-pagamento/", json={"nome": "Dinheiro", "ativo": True})
    client.post("/metodos-pagamento/", json={"nome": "Cheque", "ativo": False})

    response = client.get("/metodos-pagamento/?ativo=true")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert all(m["ativo"] is True for m in data)
    assert len(data) == 1
    assert data[0]["nome"] == "Dinheiro"

    response = client.get("/metodos-pagamento/?ativo=false")
    data = response.json()
    assert all(m["ativo"] is False for m in data)
    assert len(data) == 1
    assert data[0]["nome"] == "Cheque"


def test_obter_metodo_pagamento_por_id(client, metodo_id):
    response = client.get(f"/metodos-pagamento/{metodo_id}")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == metodo_id
    assert data["nome"] == "PIX"


def test_obter_metodo_pagamento_inexistente(client):
    response = client.get("/metodos-pagamento/999")
    assert response.status_code == HTTPStatus.NOT_FOUND


# ========== Testes de Atualização ==========
def test_atualizar_metodo_pagamento_completo(client, metodo_id):
    response = client.put(
        f"/metodos-pagamento/{metodo_id}",
        json={"nome": "PIX Atualizado", "ativo": False}
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["nome"] == "PIX Atualizado"
    assert data["ativo"] is False


def test_atualizar_metodo_pagamento_parcial(client, metodo_id):
    response = client.put(
        f"/metodos-pagamento/{metodo_id}",
        json={"ativo": False}
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["nome"] == "PIX"  # não alterado
    assert data["ativo"] is False


def test_atualizar_metodo_pagamento_nome_duplicado(client):
    client.post("/metodos-pagamento/", json={"nome": "Vale"})
    resp2 = client.post("/metodos-pagamento/", json={"nome": "Vale Refeição"})
    id2 = resp2.json()["id"]
    response = client.put(f"/metodos-pagamento/{id2}", json={"nome": "Vale"})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "duplicate" in response.text.lower() or "Já existe" in response.text


def test_atualizar_metodo_pagamento_inexistente(client):
    response = client.put("/metodos-pagamento/999", json={"nome": "Novo"})
    assert response.status_code == HTTPStatus.NOT_FOUND


# ========== Testes de Exclusão ==========
def test_deletar_metodo_pagamento_sem_comandas(client, metodo_id):
    response = client.delete(f"/metodos-pagamento/{metodo_id}")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["success"] is True
    # Verifica que não existe mais
    get_resp = client.get(f"/metodos-pagamento/{metodo_id}")
    assert get_resp.status_code == HTTPStatus.NOT_FOUND


def test_deletar_metodo_pagamento_com_comandas_associadas(client, db_session, metodo_id):
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

    # Tenta deletar o método de pagamento – deve falhar
    response = client.delete(f"/metodos-pagamento/{metodo_id}")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "vinculado" in response.text.lower() or "comandas" in response.text.lower()

    # Verifica que o método ainda existe
    get_resp = client.get(f"/metodos-pagamento/{metodo_id}")
    assert get_resp.status_code == HTTPStatus.OK
