from http import HTTPStatus

import pytest

from pizzaria_system.models import Combo, ComboProduto, Produto


# ---------- Fixtures para produtos ----------
@pytest.fixture
def produtos_base(db_session, sample_categoria):
    """Cria produtos de base para usar nos combos."""
    produtos = []
    for i, nome in enumerate(["Produto A", "Produto B", "Produto C"]):
        p = Produto(
            nome=nome,
            descricao=f"Descrição {nome}",
            imagem_link=f"http://example.com/{nome.lower()}.jpg",
            preco=10.0 + i,
            id_categoria=sample_categoria.id,
            disponivel=True,
            tempo_preparo_medio=10
        )
        db_session.add(p)
        produtos.append(p)
    db_session.commit()
    for p in produtos:
        db_session.refresh(p)
    return produtos


@pytest.fixture
def produtos_ids(produtos_base):
    return [p.id for p in produtos_base]


# ---------- Limpeza ----------
@pytest.fixture(autouse=True)
def clean_combo_table(db_session):
    """Remove combos e associações após cada teste."""
    yield
    db_session.query(ComboProduto).delete()
    db_session.query(Combo).delete()
    db_session.commit()


# ========== Testes de Criação ==========
def test_criar_combo_sucesso(admin_headers, client, produtos_ids):
    response = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Família",
            "imagem_link": "http://example.com/combo.jpg",
            "preco": 45.90,
            "popular": True,
            "disponivel": True,
            "tempo_preparo_medio": 20,
            "produtos_ids": produtos_ids,
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["nome"] == "Combo Família"
    assert data["preco"] == 45.90
    assert data["popular"] is True
    assert data["disponivel"] is True
    assert data["tempo_preparo_medio"] == 20
    assert "id" in data
    assert len(data["produtos"]) == len(produtos_ids)


def test_criar_combo_sem_produtos(admin_headers, client):
    response = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Vazio",
            "imagem_link": "http://example.com/combo.jpg",
            "preco": 10.0,
            "produtos_ids": [],
            "tempo_preparo_medio": 10
        },
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    # O schema exige min_length=1, então Pydantic já bloqueia


def test_criar_combo_com_produto_inexistente(admin_headers, client):
    response = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Inválido",
            "imagem_link": "http://example.com/combo.jpg",
            "preco": 30.0,
            "produtos_ids": [999, 1000],
            "tempo_preparo_medio": 10
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "não encontrados" in response.text


def test_criar_combo_sem_autenticacao(client, produtos_ids):
    response = client.post(
        "/combos/",
        json={
            "nome": "Sem Auth",
            "imagem_link": "http://example.com/combo.jpg",
            "preco": 20.0,
            "produtos_ids": produtos_ids,
            "tempo_preparo_medio": 10
        },
    )
    # Sem token, deve retornar 401 Unauthorized
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_criar_combo_com_cliente_comum(client, cliente_headers, produtos_ids):
    response = client.post(
        "/combos/",
        headers=cliente_headers,
        json={
            "nome": "Cliente não pode",
            "imagem_link": "http://example.com/combo.jpg",
            "preco": 20.0,
            "produtos_ids": produtos_ids,
            "tempo_preparo_medio": 10
        },
    )
    # Apenas admin pode criar
    assert response.status_code == HTTPStatus.FORBIDDEN


# ========== Testes de Leitura ==========
def test_listar_combos(client, admin_headers, produtos_ids):
    # Cria dois combos
    client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo 1",
            "imagem_link": "http://example.com/1.jpg",
            "preco": 20.0,
            "disponivel": True,
            "popular": False,
            "produtos_ids": produtos_ids[:1],
            "tempo_preparo_medio": 10
        },
    )
    client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo 2",
            "imagem_link": "http://example.com/2.jpg",
            "preco": 30.0,
            "disponivel": False,
            "popular": True,
            "produtos_ids": produtos_ids[1:],
            "tempo_preparo_medio": 10
        },
    )

    response = client.get("/combos/")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data) == 2

    # Filtro por disponível
    response = client.get("/combos/?disponivel=true")
    data = response.json()
    assert len(data) == 1
    assert data[0]["nome"] == "Combo 1"

    # Filtro por popular
    response = client.get("/combos/?popular=true")
    data = response.json()
    assert len(data) == 1
    assert data[0]["nome"] == "Combo 2"


def test_obter_combo_por_id(client, admin_headers, produtos_ids):
    criar = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Detalhe",
            "imagem_link": "http://example.com/detalhe.jpg",
            "preco": 50.0,
            "produtos_ids": produtos_ids,
            "tempo_preparo_medio": 10
        },
    )
    combo_id = criar.json()["id"]

    response = client.get(f"/combos/{combo_id}")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["nome"] == "Combo Detalhe"
    assert len(data["produtos"]) == len(produtos_ids)


def test_obter_combo_inexistente(client):
    response = client.get("/combos/999")
    assert response.status_code == HTTPStatus.NOT_FOUND


# ========== Testes de Atualização ==========
def test_atualizar_combo_parcial(admin_headers, client, produtos_ids):
    criar = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Original",
            "imagem_link": "http://example.com/original.jpg",
            "preco": 40.0,
            "produtos_ids": produtos_ids[:1],
            "tempo_preparo_medio": 10
        },
    )
    combo_id = criar.json()["id"]

    response = client.put(
        f"/combos/{combo_id}",
        headers=admin_headers,
        json={"nome": "Combo Atualizado", "preco": 55.0},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["nome"] == "Combo Atualizado"
    assert data["preco"] == 55.0
    assert len(data["produtos"]) == 1  # produtos mantidos


def test_atualizar_combo_trocar_produtos(admin_headers, client, produtos_ids):
    criar = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Troca",
            "imagem_link": "http://example.com/troca.jpg",
            "preco": 30.0,
            "produtos_ids": produtos_ids[:1],
            "tempo_preparo_medio": 10
        },
    )
    combo_id = criar.json()["id"]

    # Troca para os dois últimos produtos
    novos_ids = produtos_ids[1:]
    response = client.put(
        f"/combos/{combo_id}",
        headers=admin_headers,
        json={"produtos_ids": novos_ids},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data["produtos"]) == len(novos_ids)
    # Verifica que os IDs são os novos
    novos_ids_set = set(novos_ids)
    produtos_ids_ret = {p["id"] for p in data["produtos"]}
    assert novos_ids_set == produtos_ids_ret


def test_atualizar_combo_produto_inexistente(admin_headers, client, produtos_ids):
    criar = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Inválido",
            "imagem_link": "http://example.com/inv.jpg",
            "preco": 10.0,
            "produtos_ids": produtos_ids[:1],
            "tempo_preparo_medio": 10
        },
    )
    combo_id = criar.json()["id"]

    response = client.put(
        f"/combos/{combo_id}",
        headers=admin_headers,
        json={"produtos_ids": [999]},
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "não encontrados" in response.text


# Teste real com cliente_headers
def test_atualizar_combo_cliente_comum(client, cliente_headers, admin_headers, produtos_ids):
    criar = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Cliente",
            "imagem_link": "http://example.com/cliente.jpg",
            "preco": 25.0,
            "produtos_ids": produtos_ids[:1],
            "tempo_preparo_medio": 10
        },
    )
    combo_id = criar.json()["id"]

    response = client.put(
        f"/combos/{combo_id}",
        headers=cliente_headers,
        json={"nome": "Tentativa"},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


# ========== Testes de Exclusão ==========
def test_deletar_combo_sem_associacoes(admin_headers, client, produtos_ids):
    criar = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo a Remover",
            "imagem_link": "http://example.com/remover.jpg",
            "preco": 18.0,
            "produtos_ids": produtos_ids[:1],
            "tempo_preparo_medio": 10
        },
    )
    combo_id = criar.json()["id"]

    response = client.delete(f"/combos/{combo_id}", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["success"] is True

    # Verifica que não existe mais
    get_resp = client.get(f"/combos/{combo_id}")
    assert get_resp.status_code == HTTPStatus.NOT_FOUND


def test_deletar_combo_inexistente(admin_headers, client):
    response = client.delete("/combos/999", headers=admin_headers)
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_deletar_combo_cliente_comum(client, cliente_headers, admin_headers, produtos_ids):
    criar = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Protegido",
            "imagem_link": "http://example.com/protegido.jpg",
            "preco": 22.0,
            "produtos_ids": produtos_ids[:1],
            "tempo_preparo_medio": 10
        },
    )
    combo_id = criar.json()["id"]

    response = client.delete(f"/combos/{combo_id}", headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


# ========== Testes de Adicionar/Remover Produtos ==========
def test_adicionar_produto_ao_combo(admin_headers, client, produtos_ids):
    # Cria combo com apenas um produto
    criar = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Inicial",
            "imagem_link": "http://example.com/inicial.jpg",
            "preco": 20.0,
            "produtos_ids": produtos_ids[:1],
            "tempo_preparo_medio": 10
        },
    )
    combo_id = criar.json()["id"]

    # Adiciona segundo produto
    novo_produto_id = produtos_ids[1]
    response = client.post(
        f"/combos/{combo_id}/produtos/{novo_produto_id}",
        headers=admin_headers,
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()["success"] is True
    assert "adicionado" in response.json()["message"]

    # Verifica que o combo agora tem dois produtos
    get_resp = client.get(f"/combos/{combo_id}")
    assert len(get_resp.json()["produtos"]) == 2


def test_adicionar_produto_duplicado(admin_headers, client, produtos_ids):
    criar = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Duplicado",
            "imagem_link": "http://example.com/duplicado.jpg",
            "preco": 20.0,
            "produtos_ids": produtos_ids[:1],
            "tempo_preparo_medio": 10
        },
    )
    combo_id = criar.json()["id"]
    produto_id = produtos_ids[0]

    # Tenta adicionar o mesmo produto novamente
    response = client.post(
        f"/combos/{combo_id}/produtos/{produto_id}",
        headers=admin_headers,
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "já está associado" in response.text


def test_adicionar_produto_inexistente(admin_headers, client, produtos_ids):
    criar = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Teste",
            "imagem_link": "http://example.com/teste.jpg",
            "preco": 10.0,
            "produtos_ids": produtos_ids[:1],
            "tempo_preparo_medio": 10
        },
    )
    combo_id = criar.json()["id"]

    response = client.post(
        f"/combos/{combo_id}/produtos/999",
        headers=admin_headers,
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_remover_produto_do_combo(admin_headers, client, produtos_ids):
    # Cria combo com dois produtos
    criar = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Completo",
            "imagem_link": "http://example.com/completo.jpg",
            "preco": 30.0,
            "produtos_ids": produtos_ids[:2],
            "tempo_preparo_medio": 10
        },
    )
    combo_id = criar.json()["id"]
    produto_remover = produtos_ids[0]

    response = client.delete(
        f"/combos/{combo_id}/produtos/{produto_remover}",
        headers=admin_headers,
    )
    assert response.status_code == HTTPStatus.OK
    assert "removido" in response.json()["message"]

    # Verifica que restou apenas um produto
    get_resp = client.get(f"/combos/{combo_id}")
    produtos = get_resp.json()["produtos"]
    assert len(produtos) == 1
    assert produtos[0]["id"] == produtos_ids[1]


def test_remover_produto_nao_associado(admin_headers, client, produtos_ids):
    criar = client.post(
        "/combos/",
        headers=admin_headers,
        json={
            "nome": "Combo Vazio",
            "imagem_link": "http://example.com/vazio.jpg",
            "preco": 10.0,
            "produtos_ids": produtos_ids[:1],
            "tempo_preparo_medio": 10
        },
    )
    combo_id = criar.json()["id"]
    produto_nao_associado = produtos_ids[2]  # produto não incluso

    response = client.delete(
        f"/combos/{combo_id}/produtos/{produto_nao_associado}",
        headers=admin_headers,
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
