import pytest
from http import HTTPStatus

from sqlalchemy.orm import Session
from pizzaria_system.database import engine

from pizzaria_system.models import Cliente, Funcionario, Produto, Combo, ComboProduto
from pizzaria_system.security import get_password_hash


@pytest.fixture
def admin_token(client, admin_user):
    response = client.post(
        "/auth/token",
        data={"username": admin_user.email, "password": "admin123"},
    )
    assert response.status_code == HTTPStatus.OK
    return response.json()["access_token"]

@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}

@pytest.fixture
def cliente_token(client, cliente_comum):
    response = client.post(
        "/auth/token",
        data={"username": cliente_comum.email, "password": "123456"},
    )
    assert response.status_code == HTTPStatus.OK
    return response.json()["access_token"]

# ------------------------------------------------------------
# Testes (mantenha todos os testes como estavam, exceto remova a segunda definição de cliente_comum)
# ------------------------------------------------------------
def test_listar_produtos_vazio(client):
    response = client.get("/produtos/")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == []

def test_listar_produtos_com_filtros(client, db_session, sample_categoria):
    p1 = Produto(
        nome="Pizza A",
        descricao="Desc A",
        imagem_link="http://example.com/a.jpg",
        preco=40.0,
        id_categoria=sample_categoria.id,
        tempo_preparo_medio=20,
        disponivel=True,
    )
    p2 = Produto(
        nome="Pizza B",
        descricao="Desc B",
        imagem_link="http://example.com/b.jpg",
        preco=50.0,
        id_categoria=sample_categoria.id,
        tempo_preparo_medio=25,
        disponivel=False,
    )
    db_session.add_all([p1, p2])
    db_session.commit()

    resp = client.get("/produtos/")
    assert len(resp.json()) == 2

    resp = client.get("/produtos/?disponivel=true")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["nome"] == "Pizza A"

    resp = client.get(f"/produtos/?categoria_id={sample_categoria.id}")
    assert len(resp.json()) == 2

    resp = client.get("/produtos/?categoria_id=999")
    assert resp.json() == []

def test_obter_produto_existente(client, sample_produto):
    response = client.get(f"/produtos/{sample_produto.id}")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == sample_produto.id
    assert data["nome"] == sample_produto.nome

def test_obter_produto_inexistente(client):
    response = client.get("/produtos/9999")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "Produto não encontrado" in response.json()["detail"]

def test_criar_produto_sem_autenticacao(client, sample_categoria):
    payload = {
        "nome": "Calabresa",
        "descricao": "Molho, calabresa, cebola",
        "imagem_link": "http://example.com/calabresa.jpg",
        "preco": 49.90,
        "id_categoria": sample_categoria.id,
        "disponivel": True,
        "popular": False,
        "tempo_preparo_medio": 20,
    }
    response = client.post("/produtos/", json=payload)
    assert response.status_code == HTTPStatus.UNAUTHORIZED

def test_criar_produto_com_admin(client, admin_headers, sample_categoria):
    payload = {
        "nome": "Calabresa",
        "descricao": "Molho, calabresa, cebola",
        "imagem_link": "http://example.com/calabresa.jpg",
        "preco": 49.90,
        "id_categoria": sample_categoria.id,
        "disponivel": True,
        "popular": False,
        "tempo_preparo_medio": 20,
    }
    response = client.post("/produtos/", json=payload, headers=admin_headers)
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["nome"] == "Calabresa"
    assert data["preco"] == 49.90
    assert data["id_categoria"] == sample_categoria.id
    assert "id" in data

def test_criar_produto_categoria_inexistente(client, admin_headers):
    payload = {
        "nome": "Quatro Queijos",
        "descricao": "Mussarela, provolone, parmesão, gorgonzola",
        "imagem_link": "http://example.com/4queijos.jpg",
        "preco": 59.90,
        "id_categoria": 9999,
        "tempo_preparo_medio": 15,
    }
    response = client.post("/produtos/", json=payload, headers=admin_headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Categoria com id 9999 não encontrada" in response.json()["detail"]

def test_criar_produto_sem_imagem_link(client, admin_headers, sample_categoria):
    payload = {
        "nome": "Sem Imagem",
        "descricao": "Teste",
        "preco": 30.0,
        "id_categoria": sample_categoria.id,
        "tempo_preparo_medio": 10,
    }
    response = client.post("/produtos/", json=payload, headers=admin_headers)
    # imagem_link é obrigatório, então deve falhar com 422
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

def test_atualizar_produto_sem_autenticacao(client, sample_produto):
    payload = {"nome": "Margherita Especial"}
    response = client.put(f"/produtos/{sample_produto.id}", json=payload)
    assert response.status_code == HTTPStatus.UNAUTHORIZED

def test_atualizar_produto_com_admin(client, admin_headers, sample_produto):
    payload = {"nome": "Margherita Especial", "preco": 55.90}
    response = client.put(f"/produtos/{sample_produto.id}", json=payload, headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["nome"] == "Margherita Especial"
    assert data["preco"] == 55.90
    assert data["descricao"] == sample_produto.descricao

def test_atualizar_produto_categoria_inexistente(client, admin_headers, sample_produto):
    payload = {"id_categoria": 8888}
    response = client.put(f"/produtos/{sample_produto.id}", json=payload, headers=admin_headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Categoria com id 8888 não encontrada" in response.json()["detail"]

def test_atualizar_produto_inexistente(client, admin_headers):
    response = client.put("/produtos/99999", json={"nome": "Nada"}, headers=admin_headers)
    assert response.status_code == HTTPStatus.NOT_FOUND

def test_deletar_produto_sem_autenticacao(client, sample_produto):
    response = client.delete(f"/produtos/{sample_produto.id}")
    assert response.status_code == HTTPStatus.UNAUTHORIZED

def test_deletar_produto_sem_combo(client, admin_headers, sample_produto):
    produto_id = sample_produto.id

    response = client.delete(f"/produtos/{produto_id}", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK

    # Criar uma nova sessão para verificar
    with Session(engine) as session:
        produto = session.get(Produto, produto_id)
        assert produto is None

def test_deletar_produto_com_combo(client, admin_headers, sample_produto, db_session):
    combo = Combo(
        nome="Combo Família",
        imagem_link="http://example.com/combo.jpg",
        preco=79.90,
        tempo_preparo_medio=30,
    )
    db_session.add(combo)
    db_session.flush()

    combo_produto = ComboProduto(combo_id=combo.id, produto_id=sample_produto.id)
    db_session.add(combo_produto)
    db_session.commit()

    response = client.delete(f"/produtos/{sample_produto.id}", headers=admin_headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    detail = response.json()["detail"]
    assert "produto está vinculado a um ou mais combos" in detail
    assert "Remova-o dos combos antes de excluí-lo" in detail

def test_criar_produto_com_cliente_nao_admin(client, cliente_token, sample_categoria):
    payload = {
        "nome": "Tentativa",
        "descricao": "Cliente tentando criar",
        "imagem_link": "http://example.com/teste.jpg",
        "preco": 100.0,
        "id_categoria": sample_categoria.id,
        "tempo_preparo_medio": 20,
    }
    headers = {"Authorization": f"Bearer {cliente_token}"}
    response = client.post("/produtos/", json=payload, headers=headers)
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "Apenas administradores podem criar produtos" in response.json()["detail"]