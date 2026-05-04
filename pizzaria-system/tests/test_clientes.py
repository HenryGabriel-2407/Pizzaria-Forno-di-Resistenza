# tests/test_clientes.py
import uuid
from datetime import datetime
from http import HTTPStatus

import pytest
from sqlalchemy import select

from pizzaria_system.models import Cliente, EnderecoCliente
from pizzaria_system.security import get_password_hash


# ==================================================================
# Fixtures auxiliares
# ==================================================================
@pytest.fixture
def cliente_aleatorio(db_session):
    """Cria um cliente novo para testes que precisam modificar/excluir."""
    cliente = Cliente(
        nome="Cliente Temporário",
        email=f"temp_{datetime.now().timestamp()}@teste.com",
        senha_hash=get_password_hash("123456"),
        telefone=None,
        documento=None,
        ativo=True,
    )
    db_session.add(cliente)
    db_session.commit()
    db_session.refresh(cliente)
    yield cliente
    db_session.delete(cliente)
    db_session.commit()


def criar_cliente_objeto(session, nome, email, senha="123456", **kwargs):
    if email is None:
        email = f"{nome.replace(' ', '_').lower()}_{uuid.uuid4().hex}@teste.com"
    cliente = Cliente(
        nome=nome,
        email=email,
        senha_hash=get_password_hash(senha),
        telefone=kwargs.get("telefone"),
        documento=kwargs.get("documento"),
        ativo=kwargs.get("ativo", True),
    )
    session.add(cliente)
    session.commit()
    session.refresh(cliente)
    return cliente


# ==================================================================
# TESTES DE CRIAÇÃO (público)
# ==================================================================
def test_criar_cliente_sem_enderecos(client, db_session):
    payload = {
        "nome": "João Silva",
        "email": "joao@teste.com",
        "telefone": "11999999999",
        "documento": "12345678900",
        "senha": "senha123"
    }
    response = client.post("/clientes/", json=payload)
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["nome"] == "João Silva"
    assert data["email"] == "joao@teste.com"
    assert "senha" not in data
    assert data["enderecos"] == []

    # verifica persistência
    cliente = db_session.get(Cliente, data["id"])
    assert cliente is not None
    assert cliente.senha_hash != "senha123"


def test_criar_cliente_com_enderecos(client, db_session):
    payload = {
        "nome": "Maria Souza",
        "email": "maria@teste.com",
        "telefone": "11888888888",
        "documento": "98765432100",
        "senha": "senha456",
        "enderecos": [
            {
                "apelido": "casa",
                "rua": "Rua A",
                "numero": "100",
                "bairro": "Centro",
                "cidade": "São Paulo",
                "cep": "01000-000",
                "padrao": True
            }
        ]
    }
    response = client.post("/clientes/", json=payload)
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert len(data["enderecos"]) == 1
    end = data["enderecos"][0]
    assert end["apelido"] == "casa"
    assert end["padrao"] is True
    assert end["id_cliente"] == data["id"]


def test_criar_cliente_email_duplicado(client, db_session):
    # cria primeiro cliente via API
    payload = {"nome": "Teste", "email": "duplicado@teste.com", "senha": "123456"}
    client.post("/clientes/", json=payload)
    response = client.post("/clientes/", json=payload)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "E-mail já cadastrado" in response.json()["detail"]


def test_criar_cliente_documento_duplicado(client):
    payload1 = {"nome": "A", "email": "a@b.com", "documento": "111", "senha": "123456"}
    payload2 = {"nome": "B", "email": "b@c.com", "documento": "111", "senha": "123456"}
    client.post("/clientes/", json=payload1)
    response = client.post("/clientes/", json=payload2)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Documento (CPF/CNPJ) já cadastrado" in response.json()["detail"]


def test_criar_cliente_senha_curta(client):
    response = client.post("/clientes/", json={
        "nome": "João", "email": "joao@teste.com", "senha": "123"
    })
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# ==================================================================
# TESTES DE LISTAGEM (apenas admin)
# ==================================================================
def test_listar_clientes_sem_autenticacao(client):
    response = client.get("/clientes/")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_listar_clientes_com_cliente_comum(client, cliente_headers):
    response = client.get("/clientes/", headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "Acesso restrito a administradores" in response.json()["detail"]


def test_listar_clientes_com_admin(client, admin_headers, db_session):
    # criar clientes usando função auxiliar
    for i in range(3):
        criar_cliente_objeto(db_session, f"Cliente {i}", f"cli{i}@teste.com")

    response = client.get("/clientes/", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data) >= 3

    # filtra por ativo = false
    cli0 = db_session.execute(select(Cliente).where(Cliente.email == "cli0@teste.com")).scalar_one()
    cli0.ativo = False
    db_session.commit()
    response = client.get("/clientes/?ativo=false", headers=admin_headers)
    data = response.json()
    assert any(c["email"] == "cli0@teste.com" for c in data)
    assert all(c["ativo"] is False for c in data)


# ==================================================================
# TESTES DE PERFIL PRÓPRIO (/me)
# ==================================================================
def test_obter_meu_perfil_cliente(client, cliente_headers, cliente_comum):
    response = client.get("/clientes/me", headers=cliente_headers)
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == cliente_comum.id
    assert data["email"] == cliente_comum.email


def test_obter_meu_perfil_funcionario(client, admin_headers):
    response = client.get("/clientes/me", headers=admin_headers)
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "Usuário autenticado não é um cliente" in response.json()["detail"]


# ==================================================================
# TESTES DE OBTENÇÃO POR ID
# ==================================================================
def test_obter_cliente_por_id_sem_auth(client, cliente_comum):
    response = client.get(f"/clientes/{cliente_comum.id}")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_obter_cliente_por_id_proprio_cliente(client, cliente_headers, cliente_comum):
    response = client.get(f"/clientes/{cliente_comum.id}", headers=cliente_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["id"] == cliente_comum.id


def test_obter_cliente_por_id_admin(client, admin_headers, cliente_comum):
    response = client.get(f"/clientes/{cliente_comum.id}", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["id"] == cliente_comum.id


def test_obter_cliente_inexistente(client, admin_headers):
    response = client.get("/clientes/99999", headers=admin_headers)
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_obter_cliente_outro_sem_permissao(client, cliente_headers, db_session):
    outro = criar_cliente_objeto(db_session, "Outro", email=None)
    response = client.get(f"/clientes/{outro.id}", headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


# ==================================================================
# TESTES DE ATUALIZAÇÃO (usando cliente aleatório para não interferir)
# ==================================================================
def test_atualizar_cliente_proprio(client, cliente_headers, cliente_aleatorio):
    # Note: cliente_aleatorio não está autenticado, então precisamos de um token para ele.
    # Para simplificar, usamos o token do cliente_comum mas atualizamos o cliente_aleatorio (dá erro de permissão).
    # Melhor: criar token para o cliente_aleatorio.
    # Vamos criar um token específico para este cliente.
    # Primeiro, obter token para cliente_aleatorio via login.
    login_response = client.post("/auth/token", data={
        "username": cliente_aleatorio.email,
        "password": "123456"
    })
    assert login_response.status_code == HTTPStatus.OK
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"nome": "Cliente Atualizado", "telefone": "11999999999"}
    response = client.put(f"/clientes/{cliente_aleatorio.id}", json=payload, headers=headers)
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["nome"] == "Cliente Atualizado"
    assert data["telefone"] == "11999999999"
    assert data["email"] == cliente_aleatorio.email  # não alterado


def test_atualizar_cliente_admin(client, admin_headers, cliente_aleatorio):
    payload = {"documento": "99999999999"}
    response = client.put(f"/clientes/{cliente_aleatorio.id}", json=payload, headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["documento"] == "99999999999"


def test_atualizar_cliente_outro_sem_permissao(client, cliente_headers, db_session):
    outro = criar_cliente_objeto(db_session, "Outro", "outro@teste.com")
    response = client.put(f"/clientes/{outro.id}", json={"nome": "Hack"}, headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_atualizar_cliente_email_duplicado(client, admin_headers, db_session):
    email1 = f"cli1_{uuid.uuid4().hex}@teste.com"
    email2 = f"cli2_{uuid.uuid4().hex}@teste.com"

    client1 = criar_cliente_objeto(db_session, "Cliente1", email1)
    client2 = criar_cliente_objeto(db_session, "Cliente2", email2)

    response = client.put(f"/clientes/{client1.id}", json={"email": email2}, headers=admin_headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "E-mail já cadastrado" in response.json()["detail"]


# ==================================================================
# TESTES DE DELECÃO (hard delete apenas admin)
# ==================================================================
def test_deletar_cliente_sem_auth(client, cliente_aleatorio):
    response = client.delete(f"/clientes/{cliente_aleatorio.id}")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_deletar_cliente_nao_admin(client, cliente_headers, cliente_aleatorio):
    response = client.delete(f"/clientes/{cliente_aleatorio.id}", headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_deletar_cliente_admin_sem_comandas(client, admin_headers, db_session):
    cliente = criar_cliente_objeto(db_session, "ParaDeletar", "deletar@teste.com")
    cliente_id = cliente.id

    response = client.delete(f"/clientes/{cliente_id}", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["success"] is True

    # Força a sessão a recarregar o objeto do banco (ou perceber que ele sumiu)
    db_session.expire(cliente)   # ou db_session.expire_all()
    assert db_session.get(Cliente, cliente_id) is None


# ==================================================================
# TESTES DE ENDEREÇOS (usando cliente aleatório)
# ==================================================================
def test_adicionar_endereco_cliente_proprio(client, db_session, cliente_aleatorio):
    # obter token do cliente_aleatorio
    login_response = client.post("/auth/token", data={
        "username": cliente_aleatorio.email,
        "password": "123456"
    })
    assert login_response.status_code == HTTPStatus.OK
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "apelido": "trabalho",
        "rua": "Av. Paulista",
        "numero": "1000",
        "bairro": "Bela Vista",
        "cidade": "São Paulo",
        "cep": "01310-000",
        "padrao": False
    }
    response = client.post(f"/clientes/{cliente_aleatorio.id}/enderecos", json=payload, headers=headers)
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["apelido"] == "trabalho"
    assert data["id_cliente"] == cliente_aleatorio.id


def test_adicionar_endereco_outro_cliente_sem_permissao(client, cliente_headers, db_session):
    email_unico = f"outro_{uuid.uuid4().hex}@teste.com"
    outro = criar_cliente_objeto(db_session, "Outro", email=email_unico)
    payload = {"apelido": "casa", "rua": "R", "numero": "1", "bairro": "B", "cidade": "C"}
    response = client.post(f"/clientes/{outro.id}/enderecos", json=payload, headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_remover_endereco_proprio_cliente(client, db_session, cliente_aleatorio):
    login_response = client.post("/auth/token", data={
        "username": cliente_aleatorio.email,
        "password": "123456"
    })
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    end = EnderecoCliente(
        id_cliente=cliente_aleatorio.id,
        apelido="casa",
        rua="Rua",
        numero="1",
        bairro="Centro",
        cidade="São Paulo",
        complemento=None,
        cep=None,
        padrao=False
    )
    db_session.add(end)
    db_session.commit()

    response = client.delete(f"/clientes/enderecos/{end.id}", headers=headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["success"] is True

    db_session.expunge(end)   # Remove do cache
    assert db_session.get(EnderecoCliente, end.id) is None


# ==================================================================
# TESTES DE ALTERAÇÃO DE SENHA
# ==================================================================
def test_alterar_senha_proprio_cliente(client, cliente_headers, cliente_comum):
    payload = {"senha_atual": "123456", "nova_senha": "nova123"}
    response = client.post(f"/clientes/{cliente_comum.id}/alterar-senha", json=payload, headers=cliente_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["success"] is True


def test_alterar_senha_senha_atual_incorreta(client, cliente_headers, cliente_comum):
    payload = {"senha_atual": "errada", "nova_senha": "nova123"}
    response = client.post(f"/clientes/{cliente_comum.id}/alterar-senha", json=payload, headers=cliente_headers)
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_alterar_senha_outro_cliente(client, cliente_headers, db_session):
    outro = criar_cliente_objeto(db_session, "Outro", email=None)
    payload = {"senha_atual": "123456", "nova_senha": "nova123"}
    response = client.post(f"/clientes/{outro.id}/alterar-senha", json=payload, headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


# ==================================================================
# TESTES DE ATIVAÇÃO / DESATIVAÇÃO
# ==================================================================
def test_desativar_cliente_proprio(client, cliente_headers, cliente_comum):
    response = client.post(f"/clientes/{cliente_comum.id}/desativar", headers=cliente_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["ativo"] is False
    # reativa para não afetar outros testes
    client.post(f"/clientes/{cliente_comum.id}/ativar", headers=cliente_headers)


def test_ativar_cliente_admin(client, admin_headers, cliente_comum):
    # primeiro desativa
    client.post(f"/clientes/{cliente_comum.id}/desativar", headers=admin_headers)
    response = client.post(f"/clientes/{cliente_comum.id}/ativar", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["ativo"] is True


def test_ativar_cliente_nao_admin(client, cliente_headers, cliente_comum):
    response = client.post(f"/clientes/{cliente_comum.id}/ativar", headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN
