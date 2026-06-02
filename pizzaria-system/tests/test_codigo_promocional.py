from datetime import datetime, timedelta
from http import HTTPStatus

import pytest

from pizzaria_system.models import Cliente, CodPromocional, Comanda, Mesa, MetodoPagamento


# Fixture de limpeza automática
@pytest.fixture(autouse=True)
def clean_cod_promocional_table(db_session):
    """Remove todos os códigos promocionais após cada teste."""
    yield
    db_session.query(CodPromocional).delete()
    db_session.commit()


# Fixtures auxiliares
@pytest.fixture
def data_validade_futura():
    """Retorna uma data 30 dias no futuro."""
    return datetime.now() + timedelta(days=30)


@pytest.fixture
def data_validade_passada():
    """Retorna uma data 30 dias no passado."""
    return datetime.now() - timedelta(days=30)


@pytest.fixture
def promo_criado(client, data_validade_futura):
    """Cria e retorna um código promocional válido."""
    response = client.post(
        "/promocoes/",
        json={
            "codigo": "DESCONTO10",
            "desconto_percentual": 10.0,
            "data_validade": data_validade_futura.isoformat(),
            "ativo": True,
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


@pytest.fixture
def promo_id(promo_criado) -> int:
    return promo_criado["id"]


# ========== Testes de Criação ==========
def test_criar_promocao_sucesso(client, data_validade_futura):
    response = client.post(
        "/promocoes/",
        json={
            "codigo": "BLACKFRIDAY",
            "desconto_percentual": 20.5,
            "data_validade": data_validade_futura.isoformat(),
            "ativo": True,
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["codigo"] == "BLACKFRIDAY"
    assert data["desconto_percentual"] == 20.5
    assert data["ativo"] is True
    assert "id" in data


def test_criar_promocao_sem_ativo(client, data_validade_futura):
    """Deve criar com ativo=True por padrão."""
    response = client.post(
        "/promocoes/",
        json={
            "codigo": "PADRAO",
            "desconto_percentual": 15,
            "data_validade": data_validade_futura.isoformat(),
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["ativo"] is True


def test_criar_promocao_codigo_duplicado(client, data_validade_futura, promo_criado):
    response = client.post(
        "/promocoes/",
        json={
            "codigo": "DESCONTO10",
            "desconto_percentual": 5,
            "data_validade": data_validade_futura.isoformat(),
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "já está em uso" in response.text


def test_criar_promocao_data_passada(client, data_validade_passada):
    response = client.post(
        "/promocoes/",
        json={
            "codigo": "EXPIRADO",
            "desconto_percentual": 10,
            "data_validade": data_validade_passada.isoformat(),
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "data de validade deve ser futura" in response.text


def test_criar_promocao_desconto_invalido(client, data_validade_futura):
    response = client.post(
        "/promocoes/",
        json={
            "codigo": "INVALIDO",
            "desconto_percentual": 150,
            "data_validade": data_validade_futura.isoformat(),
        },
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# ========== Testes de Leitura ==========
def test_listar_promocoes(client, promo_criado):
    # Cria um segundo código
    client.post(
        "/promocoes/",
        json={
            "codigo": "DESCONTO20",
            "desconto_percentual": 20,
            "data_validade": (datetime.now() + timedelta(days=10)).isoformat(),
            "ativo": False,
        },
    )
    response = client.get("/promocoes/")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data) == 2
    codigos = [p["codigo"] for p in data]
    assert "DESCONTO10" in codigos
    assert "DESCONTO20" in codigos


def test_listar_promocoes_filtrando_por_ativo(client):
    client.post(
        "/promocoes/",
        json={
            "codigo": "ATIVO1",
            "desconto_percentual": 10,
            "data_validade": (datetime.now() + timedelta(days=1)).isoformat(),
            "ativo": True,
        },
    )
    client.post(
        "/promocoes/",
        json={
            "codigo": "INATIVO1",
            "desconto_percentual": 15,
            "data_validade": (datetime.now() + timedelta(days=1)).isoformat(),
            "ativo": False,
        },
    )
    response = client.get("/promocoes/?ativo=true")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert all(p["ativo"] is True for p in data)
    assert len(data) == 1
    assert data[0]["codigo"] == "ATIVO1"

    response = client.get("/promocoes/?ativo=false")
    data = response.json()
    assert all(p["ativo"] is False for p in data)
    assert len(data) == 1
    assert data[0]["codigo"] == "INATIVO1"


def test_listar_promocoes_paginacao(client):
    for i in range(1, 6):
        client.post(
            "/promocoes/",
            json={
                "codigo": f"PROMO{i}",
                "desconto_percentual": 5,
                "data_validade": (datetime.now() + timedelta(days=30)).isoformat(),
            },
        )
    response = client.get("/promocoes/?limite=2&offset=0")
    assert len(response.json()) == 2
    response = client.get("/promocoes/?limite=2&offset=2")
    assert len(response.json()) == 2
    response = client.get("/promocoes/?limite=10&offset=0")
    assert len(response.json()) == 5


def test_obter_promocao_por_id(client, promo_id):
    response = client.get(f"/promocoes/{promo_id}")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["codigo"] == "DESCONTO10"


def test_obter_promocao_inexistente(client):
    response = client.get("/promocoes/999")
    assert response.status_code == HTTPStatus.NOT_FOUND


# ========== Testes de Atualização ==========
def test_atualizar_promocao_completa(client, promo_id, data_validade_futura):
    nova_data = data_validade_futura + timedelta(days=10)
    response = client.put(
        f"/promocoes/{promo_id}",
        json={
            "codigo": "NOVOCODIGO",
            "desconto_percentual": 25.0,
            "data_validade": nova_data.isoformat(),
            "ativo": False,
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["codigo"] == "NOVOCODIGO"
    assert data["desconto_percentual"] == 25.0
    assert data["ativo"] is False
    # Comparar datas ignorando milissegundos/segundos
    assert data["data_validade"].startswith(nova_data.strftime("%Y-%m-%dT%H:%M"))


def test_atualizar_promocao_parcial(client, promo_id, data_validade_futura):
    response = client.put(f"/promocoes/{promo_id}", json={"ativo": False})
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["ativo"] is False
    assert data["codigo"] == "DESCONTO10"  # Não alterado


def test_atualizar_promocao_codigo_duplicado(client, promo_id):
    # Cria outro código
    client.post(
        "/promocoes/",
        json={
            "codigo": "OUTRO",
            "desconto_percentual": 5,
            "data_validade": (datetime.now() + timedelta(days=30)).isoformat(),
        },
    )
    response = client.put(f"/promocoes/{promo_id}", json={"codigo": "OUTRO"})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "já está em uso" in response.text


def test_atualizar_promocao_data_passada(client, promo_id, data_validade_passada):
    response = client.put(
        f"/promocoes/{promo_id}", json={"data_validade": data_validade_passada.isoformat()}
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "data de validade deve ser futura" in response.text


def test_atualizar_promocao_inexistente(client):
    response = client.put("/promocoes/999", json={"ativo": False})
    assert response.status_code == HTTPStatus.NOT_FOUND


# ========== Testes de Exclusão ==========
def test_deletar_promocao_sem_comandas(client, promo_id):
    response = client.delete(f"/promocoes/{promo_id}")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["success"] is True
    # Verifica que não existe mais
    get_resp = client.get(f"/promocoes/{promo_id}")
    assert get_resp.status_code == HTTPStatus.NOT_FOUND


def test_deletar_promocao_com_comandas_associadas(client, db_session, promo_id):
    # Cria um método de pagamento
    metodo = MetodoPagamento(nome="Dinheiro", ativo=True)
    db_session.add(metodo)
    # Cria cliente e mesa para a comanda
    cliente = Cliente(
        nome="Teste",
        email="teste@email.com",
        senha_hash="hash",
        ativo=True,
        telefone=None,
        documento=None
    )
    mesa = Mesa(numero=123, qtd_lugares=4, status="livre")
    db_session.add_all([cliente, mesa])
    db_session.commit()

    # Cria comanda vinculada ao código promocional
    comanda = Comanda(
        id_cliente=cliente.id,
        id_mesa=mesa.id,
        id_garcom=None,
        id_metodo_pagamento=metodo.id,
        id_cod_promocional=promo_id,
        valor_a_pagar=90.0,
        tipo_entrega="local",
        origem="web",
        data_registro=datetime.now(),
        preco_total=100.0,
        desconto_aplicado=10.0,
        data_finalizacao=None,
        observacao_geral=None
    )
    db_session.add(comanda)
    db_session.commit()

    # Tenta deletar - deve falhar
    response = client.delete(f"/promocoes/{promo_id}")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "já foi utilizado" in response.text or "comanda" in response.text

    # Verifica que o código ainda existe
    get_resp = client.get(f"/promocoes/{promo_id}")
    assert get_resp.status_code == HTTPStatus.OK


# ========== Testes de Validação ==========
def test_validar_promocao_valido(client, promo_criado):
    response = client.post(
        "/promocoes/validar",
        json={"codigo": "DESCONTO10", "valor_pedido": 200.0},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["valido"] is True
    assert data["desconto_percentual"] == 10.0
    assert data["valor_desconto"] == 20.0
    assert data["valor_final"] == 180.0
    assert "válido" in data["mensagem"].lower()


def test_validar_promocao_nao_encontrado(client):
    response = client.post(
        "/promocoes/validar",
        json={"codigo": "INEXISTENTE", "valor_pedido": 100.0},
    )
    assert response.status_code == HTTPStatus.OK  # Retorna 200 com valido=False
    data = response.json()
    assert data["valido"] is False
    assert "não encontrado" in data["mensagem"].lower()


def test_validar_promocao_inativo(client, data_validade_futura):
    # Cria código inativo
    client.post(
        "/promocoes/",
        json={
            "codigo": "INATIVO",
            "desconto_percentual": 10,
            "data_validade": data_validade_futura.isoformat(),
            "ativo": False,
        },
    )
    response = client.post(
        "/promocoes/validar",
        json={"codigo": "INATIVO", "valor_pedido": 100.0},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["valido"] is False
    assert "desativado" in data["mensagem"].lower()


def test_validar_promocao_expirado(client, data_validade_passada, db_session):
    # Cria código com data passada
    codigo_expirado = CodPromocional(
        codigo="EXPIRADO",
        desconto_percentual=10.0,
        data_validade=data_validade_passada,
        ativo=True,
    )
    db_session.add(codigo_expirado)
    db_session.commit()

    response = client.post(
        "/promocoes/validar",
        json={"codigo": "EXPIRADO", "valor_pedido": 100.0},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["valido"] is False
    assert "expirado" in data["mensagem"].lower()
