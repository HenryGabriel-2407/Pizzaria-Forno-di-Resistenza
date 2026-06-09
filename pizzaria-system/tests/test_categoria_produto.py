from http import HTTPStatus

import pytest

from pizzaria_system.models import CategoriaProduto, Produto


# Fixture de limpeza automática
@pytest.fixture(autouse=True)
def clean_categoria_table(db_session):
    """Remove todas as categorias após cada teste."""
    yield
    db_session.query(CategoriaProduto).delete()
    db_session.commit()


@pytest.fixture
def categoria_criada(client, admin_headers) -> dict:
    """Cria e retorna uma categoria usando admin_headers."""
    response = client.post("/categorias/", json={"nome": "Pizzas"}, headers=admin_headers)
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


@pytest.fixture
def categoria_id(categoria_criada) -> int:
    return categoria_criada["id"]


# ========== Testes de Criação ==========
def test_criar_categoria_sucesso(client, admin_headers):
    response = client.post("/categorias/", json={"nome": "Bebidas"}, headers=admin_headers)
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["nome"] == "Bebidas"
    assert "id" in data


def test_criar_categoria_sem_autenticacao(client):
    """Sem token, deve retornar 401 Unauthorized"""
    response = client.post("/categorias/", json={"nome": "Bebidas"})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_criar_categoria_com_cliente(client, cliente_headers):
    """Cliente comum não tem permissão (deve retornar 403)"""
    response = client.post("/categorias/", json={"nome": "Bebidas"}, headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_criar_categoria_nome_duplicado(client, admin_headers, categoria_criada):
    """Testa que o sistema impede criação com nome duplicado."""
    response = client.post("/categorias/", json={"nome": "Pizzas"}, headers=admin_headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "já existe" in response.text.lower()


def test_criar_categoria_nome_muito_longo(client, admin_headers):
    response = client.post("/categorias/", json={"nome": "A" * 101}, headers=admin_headers)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# ========== Testes de Leitura (públicos) ==========
def test_listar_categorias(client, categoria_criada, admin_headers):
    # Cria uma segunda categoria usando admin_headers
    client.post("/categorias/", json={"nome": "Sobremesas"}, headers=admin_headers)
    response = client.get("/categorias/")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data) >= 2
    nomes = [c["nome"] for c in data]
    assert "Pizzas" in nomes
    assert "Sobremesas" in nomes


def test_obter_categoria_por_id(client, categoria_id):
    response = client.get(f"/categorias/{categoria_id}")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["nome"] == "Pizzas"


def test_obter_categoria_inexistente(client):
    response = client.get("/categorias/999")
    assert response.status_code == HTTPStatus.NOT_FOUND


# ========== Testes de Atualização (apenas admin) ==========
def test_atualizar_categoria_completa(client, admin_headers, categoria_id):
    response = client.put(
        f"/categorias/{categoria_id}",
        json={"nome": "Pizzas Especiais"},
        headers=admin_headers
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()["nome"] == "Pizzas Especiais"


def test_atualizar_categoria_sem_autenticacao(client, categoria_id):
    response = client.put(f"/categorias/{categoria_id}", json={"nome": "Nova"})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_atualizar_categoria_com_cliente(client, cliente_headers, categoria_id):
    response = client.put(f"/categorias/{categoria_id}", json={"nome": "Nova"}, headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_atualizar_categoria_nome_duplicado(client, admin_headers, categoria_id):
    # Cria outra categoria
    client.post("/categorias/", json={"nome": "Massas"}, headers=admin_headers)
    response = client.put(f"/categorias/{categoria_id}", json={"nome": "Massas"}, headers=admin_headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "já existe" in response.text.lower()


def test_atualizar_categoria_inexistente(client, admin_headers):
    response = client.put("/categorias/999", json={"nome": "Nova"}, headers=admin_headers)
    assert response.status_code == HTTPStatus.NOT_FOUND


# ========== Testes de Exclusão (apenas admin) ==========
def test_deletar_categoria_sem_produtos(client, admin_headers, categoria_id):
    response = client.delete(f"/categorias/{categoria_id}", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["success"] is True
    get_resp = client.get(f"/categorias/{categoria_id}")
    assert get_resp.status_code == HTTPStatus.NOT_FOUND


def test_deletar_categoria_sem_autenticacao(client, categoria_id):
    response = client.delete(f"/categorias/{categoria_id}")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_deletar_categoria_com_cliente(client, cliente_headers, categoria_id):
    response = client.delete(f"/categorias/{categoria_id}", headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_deletar_categoria_com_produtos_associados(client, admin_headers, db_session, categoria_id):
    produto = Produto(
        nome="Pizza Margherita",
        descricao="Molho, mussarela, manjericão",
        imagem_link="http://example.com/margherita.jpg",
        preco=45.90,
        id_categoria=categoria_id,
        disponivel=True,
        tempo_preparo_medio=None
    )
    db_session.add(produto)
    db_session.commit()

    response = client.delete(f"/categorias/{categoria_id}", headers=admin_headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "produtos vinculados" in response.text.lower()
    get_resp = client.get(f"/categorias/{categoria_id}")
    assert get_resp.status_code == HTTPStatus.OK


def test_deletar_categoria_inexistente(client, admin_headers):
    response = client.delete("/categorias/999", headers=admin_headers)
    assert response.status_code == HTTPStatus.NOT_FOUND
