from http import HTTPStatus

import pytest

from pizzaria_system.models import (
    CategoriaProduto,
    Comanda,
    Combo,
    Funcionario,
    Mesa,
    MetodoPagamento,
    PedidoItem,
    Produto,
    StatusComandaLog,
)

# ---------- Fixtures de suporte ----------


@pytest.fixture
def payload_comanda_base(metodo_pagamento, produto, mesa):
    return {
        "id_cliente": None,
        "id_mesa": mesa.id,
        "id_garcom": None,
        "id_metodo_pagamento": metodo_pagamento.id,
        "tipo_entrega": "local",
        "origem": "mobile_cliente",
        "valor_a_pagar": 45.90,
        "data_registro": None,
        "data_finalizacao": None,
        "pedido_itens": [
            {
                "id_comanda": 0,
                "id_produto": produto.id,
                "quantidade": 1,
                "preco_unitario": produto.preco,
                "subtotal": produto.preco,
                "observacao": None,
            }
        ],
    }


@pytest.fixture
def metodo_pagamento(db_session):
    metodo = db_session.query(MetodoPagamento).filter_by(nome="Dinheiro").first()
    if not metodo:
        metodo = MetodoPagamento(nome="Dinheiro", ativo=True)
        db_session.add(metodo)
        db_session.commit()
        db_session.refresh(metodo)
    return metodo


@pytest.fixture
def categoria(db_session):
    cat = db_session.query(CategoriaProduto).filter_by(nome="Pizzas").first()
    if not cat:
        cat = CategoriaProduto(nome="Pizzas")
        db_session.add(cat)
        db_session.commit()
        db_session.refresh(cat)
    return cat


@pytest.fixture
def produto(db_session, categoria):
    prod = Produto(
        nome="Margherita",
        descricao="Molho, mussarela, manjericão",
        imagem_link="http://example.com/marg.jpg",
        preco=45.90,
        id_categoria=categoria.id,
        disponivel=True,
        tempo_preparo_medio=15
    )
    db_session.add(prod)
    db_session.commit()
    db_session.refresh(prod)
    return prod


@pytest.fixture
def produto_indisponivel(db_session, categoria):
    prod = Produto(
        nome="Indisponível",
        descricao="Produto fora de estoque",
        imagem_link="http://example.com/indisponivel.jpg",
        preco=30.0,
        id_categoria=categoria.id,
        disponivel=False,
        tempo_preparo_medio=10
    )
    db_session.add(prod)
    db_session.commit()
    db_session.refresh(prod)
    return prod


@pytest.fixture
def combo(db_session, produto):
    combo_obj = Combo(
        nome="Combo Família",
        imagem_link="http://example.com/combo.jpg",
        preco=89.90,
        disponivel=True,
        tempo_preparo_medio=25
    )
    db_session.add(combo_obj)
    db_session.flush()
    # Associação
    combo_obj.produtos.append(produto)
    db_session.commit()
    db_session.refresh(combo_obj)
    return combo_obj


@pytest.fixture
def mesa(db_session):
    mesa_obj = db_session.query(Mesa).filter_by(numero=10).first()
    if not mesa_obj:
        mesa_obj = Mesa(numero=10, qtd_lugares=4, status="livre")
        db_session.add(mesa_obj)
        db_session.commit()
        db_session.refresh(mesa_obj)
    return mesa_obj


@pytest.fixture
def cliente_comum_com_id(cliente_comum):
    # cliente_comum já existe na fixture, mas precisa ter id
    return cliente_comum


@pytest.fixture
def garcom(db_session):
    funcionario = Funcionario(
        nome="Garçom Teste",
        email="garcom@teste.com",
        senha_hash="hash",  # na prática viria de get_password_hash
        cargo="garcom",
        ativo=True,
    )
    db_session.add(funcionario)
    db_session.commit()
    db_session.refresh(funcionario)
    return funcionario


# Limpeza após cada teste
@pytest.fixture(autouse=True)
def clean_comanda_table(db_session):
    yield
    try:
        db_session.rollback()
    except Exception:
        pass
    db_session.query(StatusComandaLog).delete()
    db_session.query(PedidoItem).delete()
    db_session.query(Comanda).delete()
    db_session.commit()


# ========== Testes de Criação de Comanda ==========
def test_criar_comanda_como_cliente_local(
    client, cliente_headers, payload_comanda_base, cliente_comum
):
    payload = payload_comanda_base
    response = client.post("/comandas/", headers=cliente_headers, json=payload)
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["id_cliente"] == cliente_comum.id 
    assert data["id_mesa"] == payload["id_mesa"]
    assert data["tipo_entrega"] == "local"
    assert data["status_comanda"] == "aberta"
    assert data["status_pagamento"] == "pendente"
    assert len(data["pedido_itens"]) == 1
    assert data["pedido_itens"][0]["id_produto"] == payload["pedido_itens"][0]["id_produto"]


def test_criar_comanda_como_cliente_delivery(
    client, cliente_headers, payload_comanda_base
):
    payload = payload_comanda_base
    payload["tipo_entrega"] = "delivery"
    response = client.post("/comandas/", headers=cliente_headers, json=payload)
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["id_cliente"] is not None
    assert data["tipo_entrega"] == "delivery"


def test_criar_comanda_como_funcionario(client, admin_headers, payload_comanda_base):
    response = client.post(
        "/comandas/",
        headers=admin_headers,
        json=payload_comanda_base
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["id_cliente"] == payload_comanda_base["id_cliente"]
    assert data["id_mesa"] == payload_comanda_base["id_mesa"]


def test_criar_comanda_sem_cliente_ou_mesa(client, admin_headers, metodo_pagamento):
    response = client.post(
        "/comandas/",
        headers=admin_headers,
        json={
            "id_cliente": None,
            "id_mesa": None,
            "id_garcom": None,
            "id_metodo_pagamento": metodo_pagamento.id,
            "tipo_entrega": "local",
            "origem": "web",
            "valor_a_pagar": 0,
            "pedido_itens": [],
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "cliente (pedido online) ou mesa" in response.text


def test_criar_comanda_com_produto_indisponivel(
    client, cliente_headers, payload_comanda_base, produto_indisponivel
):
    payload = payload_comanda_base
    payload["pedido_itens"][0]["id_produto"] = produto_indisponivel.id
    payload["pedido_itens"][0]["preco_unitario"] = produto_indisponivel.preco
    payload["pedido_itens"][0]["subtotal"] = produto_indisponivel.preco
    response = client.post("/comandas/", headers=cliente_headers, json=payload)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "indisponível" in response.text


# ========== Testes de Listagem ==========
def test_listar_comandas_como_cliente(client, cliente_headers, payload_comanda_base):
    # Cria uma comanda para o cliente
    resp_criar = client.post(
        "/comandas/",
        headers=cliente_headers,
        json=payload_comanda_base
    )
    assert resp_criar.status_code == HTTPStatus.CREATED
    comanda_id = resp_criar.json()["id"]

    # Cliente vê apenas suas comandas
    response = client.get("/comandas/", headers=cliente_headers)
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == comanda_id


def test_listar_comandas_como_admin(client, admin_headers, payload_comanda_base):
    # Cria comanda para cliente comum
    resp_cliente = client.post(
        "/comandas/",
        headers=admin_headers,
        json=payload_comanda_base
    )
    assert resp_cliente.status_code == HTTPStatus.CREATED

    # Admin vê todas
    response = client.get("/comandas/", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data) >= 1
    # Testar filtro por status
    response_filtro = client.get("/comandas/?status_comanda=aberta", headers=admin_headers)
    assert response_filtro.status_code == HTTPStatus.OK
    assert all(c["status_comanda"] == "aberta" for c in response_filtro.json())


# ========== Testes de Recuperação de Uma Comanda ==========
def test_obter_comanda_cliente_propria(client, cliente_headers, payload_comanda_base):
    # Criar comanda
    criar = client.post(
        "/comandas/",
        headers=cliente_headers,
        json=payload_comanda_base
    )
    comanda_id = criar.json()["id"]

    resp_get = client.get(f"/comandas/{comanda_id}", headers=cliente_headers)
    assert resp_get.status_code == HTTPStatus.OK
    assert resp_get.json()["id"] == comanda_id


def test_obter_comanda_cliente_nao_autorizado(client, cliente_headers, admin_headers, payload_comanda_base):
    # Admin cria comanda para outro cliente
    criar = client.post(
        "/comandas/",
        headers=admin_headers,
        json=payload_comanda_base
    )
    comanda_id = criar.json()["id"]

    # Cliente comum tenta acessar comanda de outro
    resp_get = client.get(f"/comandas/{comanda_id}", headers=cliente_headers)
    assert resp_get.status_code == HTTPStatus.FORBIDDEN


# ========== Testes de Atualização de Comanda (apenas funcionário) ==========
def test_atualizar_comanda_funcionario(client, admin_headers, payload_comanda_base):
    # Criar comanda como admin
    criar = client.post(
        "/comandas/",
        headers=admin_headers,
        json=payload_comanda_base
    )
    comanda_id = criar.json()["id"]

    # Atualizar taxa_entrega
    resp_put = client.put(
        f"/comandas/{comanda_id}",
        headers=admin_headers,
        json={"taxa_entrega": 5.0},
    )
    assert resp_put.status_code == HTTPStatus.OK
    assert resp_put.json()["taxa_entrega"] == 5.0
    # O valor_a_pagar deve ter sido recalculado
    assert resp_put.json()["valor_a_pagar"] == 45.90 - 0 + 5.0


def test_atualizar_comanda_cliente_nao_permitido(client, cliente_headers, admin_headers, payload_comanda_base):
    # Admin cria comanda
    criar = client.post(
        "/comandas/",
        headers=admin_headers,
        json=payload_comanda_base
    )
    comanda_id = criar.json()["id"]

    # Cliente tenta atualizar
    resp_put = client.put(
        f"/comandas/{comanda_id}",
        headers=cliente_headers,
        json={"taxa_entrega": 10.0},
    )
    assert resp_put.status_code == HTTPStatus.FORBIDDEN


# ========== Testes de Exclusão de Comanda ==========
def test_deletar_comanda_funcionario(client, admin_headers, payload_comanda_base):
    criar = client.post(
        "/comandas/",
        headers=admin_headers,
        json=payload_comanda_base
    )
    comanda_id = criar.json()["id"]

    resp_del = client.delete(f"/comandas/{comanda_id}", headers=admin_headers)
    assert resp_del.status_code == HTTPStatus.OK
    assert resp_del.json()["success"] is True

    # Verificar que não existe mais
    resp_get = client.get(f"/comandas/{comanda_id}", headers=admin_headers)
    assert resp_get.status_code == HTTPStatus.NOT_FOUND


def test_deletar_comanda_cliente_nao_permitido(client, cliente_headers, admin_headers, payload_comanda_base):
    criar = client.post(
        "/comandas/",
        headers=admin_headers,
        json=payload_comanda_base
    )
    comanda_id = criar.json()["id"]

    resp_del = client.delete(f"/comandas/{comanda_id}", headers=cliente_headers)
    assert resp_del.status_code == HTTPStatus.FORBIDDEN


# ========== Testes de Gerenciamento de Itens ==========
def test_adicionar_item_na_comanda_como_cliente(client, cliente_headers, payload_comanda_base, produto):
    criar = client.post(
        "/comandas/",
        headers=cliente_headers,
        json=payload_comanda_base
    )
    comanda_id = criar.json()["id"]

    # Adicionar segundo item
    resp_add = client.post(
        f"/comandas/{comanda_id}/itens",
        headers=cliente_headers,
        json={
            "id_produto": produto.id,
            "quantidade": 2,
            "observacao": "Extra queijo",
        },
    )
    assert resp_add.status_code == HTTPStatus.CREATED
    item_data = resp_add.json()
    assert item_data["quantidade"] == 2
    assert item_data["observacao"] == "Extra queijo"

    # Verificar que a comanda foi atualizada (opcional, se desejar)
    comanda_resp = client.get(f"/comandas/{comanda_id}", headers=cliente_headers)
    assert comanda_resp.status_code == HTTPStatus.OK
    # O total deve ser a soma do item original (45.90) + 2 * 45.90 = 137.70
    assert comanda_resp.json()["preco_total"] == 45.90 * 3


def test_atualizar_item_comanda(client, cliente_headers, produto, payload_comanda_base):
    criar = client.post(
        "/comandas/",
        headers=cliente_headers,
        json=payload_comanda_base
    )
    comanda_id = criar.json()["id"]
    item_id = criar.json()["pedido_itens"][0]["id"]

    resp_put = client.put(
        f"/comandas/itens/{item_id}",
        headers=cliente_headers,
        json={"quantidade": 3, "observacao": "Bem passado"},
    )
    assert resp_put.status_code == HTTPStatus.OK
    assert resp_put.json()["quantidade"] == 3
    assert resp_put.json()["observacao"] == "Bem passado"
    assert resp_put.json()["subtotal"] == produto.preco * 3

    # Verificar total da comanda
    comanda_resp = client.get(f"/comandas/{comanda_id}", headers=cliente_headers)
    assert comanda_resp.json()["preco_total"] == produto.preco * 3


def test_remover_item_comanda(client, cliente_headers, payload_comanda_base):
    criar = client.post(
        "/comandas/",
        headers=cliente_headers,
        json=payload_comanda_base
    )
    item_id = criar.json()["pedido_itens"][0]["id"]
    comanda_id = criar.json()["id"]

    resp_del = client.delete(f"/comandas/itens/{item_id}", headers=cliente_headers)
    assert resp_del.status_code == HTTPStatus.OK

    comanda_resp = client.get(f"/comandas/{comanda_id}", headers=cliente_headers)
    assert len(comanda_resp.json()["pedido_itens"]) == 0
    assert comanda_resp.json()["preco_total"] == 0


# ========== Testes de Controle de Status ==========
def test_cliente_cancelar_comanda_aberta(client, cliente_headers, payload_comanda_base):
    criar = client.post("/comandas/", headers=cliente_headers, json=payload_comanda_base)
    comanda_id = criar.json()["id"]

    resp_status = client.post(
        f"/comandas/{comanda_id}/status",
        headers=cliente_headers,
        json={"status_novo": "cancelada", "observacao": "Desistiu"},
    )
    assert resp_status.status_code == HTTPStatus.OK
    assert resp_status.json()["status_comanda"] == "cancelada"
    assert resp_status.json()["status_pagamento"] == "falhou"

    # Verifica os logs
    logs_resp = client.get(f"/comandas/{comanda_id}/status-logs", headers=cliente_headers)
    assert logs_resp.status_code == HTTPStatus.OK
    logs = logs_resp.json()
    # O último log deve ser o cancelamento
    ultimo_log = logs[-1]
    assert ultimo_log["status_novo"] == "cancelada"
    assert ultimo_log["alterado_por_tipo"] == "cliente"
    assert ultimo_log["observacao"] == "Desistiu"


def test_cliente_nao_pode_mudar_para_em_preparo(client, cliente_headers, payload_comanda_base):
    criar = client.post(
        "/comandas/",
        headers=cliente_headers,
        json=payload_comanda_base
    )
    comanda_id = criar.json()["id"]

    resp_status = client.post(
        f"/comandas/{comanda_id}/status",
        headers=cliente_headers,
        json={"status_novo": "em_preparo"},
    )
    assert resp_status.status_code == HTTPStatus.FORBIDDEN


def test_funcionario_pode_avancar_status(client, admin_headers, payload_comanda_base):
    criar = client.post(
        "/comandas/",
        headers=admin_headers,
        json=payload_comanda_base
    )
    comanda_id = criar.json()["id"]

    # Mudar para em_preparo
    resp1 = client.post(
        f"/comandas/{comanda_id}/status",
        headers=admin_headers,
        json={"status_novo": "em_preparo"},
    )
    assert resp1.status_code == HTTPStatus.OK
    assert resp1.json()["status_comanda"] == "em_preparo"

    # Mudar para pronta
    resp2 = client.post(
        f"/comandas/{comanda_id}/status",
        headers=admin_headers,
        json={"status_novo": "pronta"},
    )
    assert resp2.json()["status_comanda"] == "pronta"

    # Mudar para entregue
    resp3 = client.post(
        f"/comandas/{comanda_id}/status",
        headers=admin_headers,
        json={"status_novo": "entregue"},
    )
    assert resp3.json()["status_comanda"] == "entregue"

    # Mudar para paga
    resp4 = client.post(
        f"/comandas/{comanda_id}/status",
        headers=admin_headers,
        json={"status_novo": "paga"},
    )
    assert resp4.json()["status_comanda"] == "paga"
    assert resp4.json()["status_pagamento"] == "pago"
    assert resp4.json()["data_finalizacao"] is not None


def test_transicao_invalida(client, admin_headers, payload_comanda_base):
    criar = client.post(
        "/comandas/",
        headers=admin_headers,
        json=payload_comanda_base
    )
    comanda_id = criar.json()["id"]

    # Tentar pular de aberta para entregue
    resp = client.post(
        f"/comandas/{comanda_id}/status",
        headers=admin_headers,
        json={"status_novo": "entregue"},
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST


# ========== Testes de Histórico de Status ==========
def test_obter_logs_status_como_cliente(client, cliente_headers, payload_comanda_base):
    criar = client.post("/comandas/", headers=cliente_headers, json=payload_comanda_base)
    comanda_id = criar.json()["id"]

    # Cancelar para gerar outro log
    client.post(
        f"/comandas/{comanda_id}/status",
        headers=cliente_headers,
        json={"status_novo": "cancelada"},
    )

    resp_logs = client.get(f"/comandas/{comanda_id}/status-logs", headers=cliente_headers)
    assert resp_logs.status_code == HTTPStatus.OK
    logs = resp_logs.json()
    # Deve haver pelo menos 2 logs: criação + cancelamento
    assert len(logs) >= 2
    # O último log deve ser cancelamento
    ultimo_log = logs[-1]
    assert ultimo_log["status_novo"] == "cancelada"
    assert ultimo_log["alterado_por_tipo"] == "cliente"
    # O primeiro log deve ser criação (status_novo = "aberta")
    primeiro_log = logs[0]
    assert primeiro_log["status_novo"] == "aberta"


def test_obter_logs_status_cliente_nao_autorizado(client, cliente_headers, admin_headers, payload_comanda_base):
    # Admin cria comanda para outro cliente
    criar = client.post(
        "/comandas/",
        headers=admin_headers,
        json=payload_comanda_base
    )
    comanda_id = criar.json()["id"]

    resp_logs = client.get(f"/comandas/{comanda_id}/status-logs", headers=cliente_headers)
    assert resp_logs.status_code == HTTPStatus.FORBIDDEN
