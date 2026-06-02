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
def categoria_criada(client) -> dict:
    """Cria e retorna uma categoria para uso nos testes."""
    response = client.post("/categorias/", json={"nome": "Pizzas"})
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


@pytest.fixture
def categoria_id(categoria_criada) -> int:
    return categoria_criada["id"]


# ========== Testes de Criação ==========
def test_criar_categoria_sucesso(client):
    response = client.post("/categorias/", json={"nome": "Bebidas"})
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["nome"] == "Bebidas"
    assert "id" in data


def test_criar_categoria_nome_duplicado(client, categoria_criada):
    """Testa que o sistema impede criação com nome duplicado."""
    response = client.post("/categorias/", json={"nome": "Pizzas"})
    # Como o router não trata IntegrityError, esperamos 400 após adicionarmos tratamento,
    # ou 500 temporariamente. O teste falhará indicando a necessidade de tratamento.
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "já existe" in response.text.lower() or "duplicada" in response.text.lower()


def test_criar_categoria_nome_muito_longo(client):
    response = client.post("/categorias/", json={"nome": "A" * 101})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# ========== Testes de Leitura ==========
def test_listar_categorias(client, categoria_criada):
    # Cria uma segunda categoria
    client.post("/categorias/", json={"nome": "Sobremesas"})
    response = client.get("/categorias/")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data) == 2
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


# ========== Testes de Atualização ==========
def test_atualizar_categoria_completa(client, categoria_id):
    response = client.put(
        f"/categorias/{categoria_id}",
        json={"nome": "Pizzas Especiais"}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()["nome"] == "Pizzas Especiais"


def test_atualizar_categoria_parcial(client, categoria_id):
    # Como só tem nome, atualização parcial é igual
    response = client.put(f"/categorias/{categoria_id}", json={"nome": "Calzones"})
    assert response.status_code == HTTPStatus.OK
    assert response.json()["nome"] == "Calzones"


def test_atualizar_categoria_nome_duplicado(client, categoria_id):
    # Cria outra categoria
    client.post("/categorias/", json={"nome": "Massas"})
    # Tenta atualizar a primeira para "Massas"
    response = client.put(f"/categorias/{categoria_id}", json={"nome": "Massas"})
    # Deve falhar por duplicidade
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "já existe" in response.text.lower() or "duplicada" in response.text.lower()


def test_atualizar_categoria_inexistente(client):
    response = client.put("/categorias/999", json={"nome": "Nova"})
    assert response.status_code == HTTPStatus.NOT_FOUND


# ========== Testes de Exclusão ==========
def test_deletar_categoria_sem_produtos(client, categoria_id):
    response = client.delete(f"/categorias/{categoria_id}")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["success"] is True
    # Verifica que foi removida
    get_resp = client.get(f"/categorias/{categoria_id}")
    assert get_resp.status_code == HTTPStatus.NOT_FOUND


def test_deletar_categoria_com_produtos_associados(client, db_session, categoria_id):
    # Cria um produto vinculado a essa categoria
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

    response = client.delete(f"/categorias/{categoria_id}")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "produtos vinculados" in response.text.lower()
    # Verifica que a categoria ainda existe
    get_resp = client.get(f"/categorias/{categoria_id}")
    assert get_resp.status_code == HTTPStatus.OK


def test_deletar_categoria_inexistente(client):
    response = client.delete("/categorias/999")
    assert response.status_code == HTTPStatus.NOT_FOUND
