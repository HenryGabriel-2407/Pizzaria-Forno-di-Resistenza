from http import HTTPStatus

import pytest

from pizzaria_system.models import Cliente, Comanda, Funcionario, Mesa, MetodoPagamento


# ---------- Fixtures ----------
@pytest.fixture
def garcom_data():
    return {
        "nome": "Garçom Teste",
        "email": "garcom@teste.com",
        "senha": "123456",
        "telefone": "11999999999",
        "cargo": "garcom",
        "ativo": True,
    }


@pytest.fixture
def outro_admin_data():
    return {
        "nome": "Outro Admin",
        "email": "admin2@teste.com",
        "senha": "admin456",
        "telefone": "11888888888",
        "cargo": "admin",
        "ativo": True,
    }


@pytest.fixture
def garcom_criado(client, admin_headers, garcom_data):
    response = client.post("/funcionarios/", headers=admin_headers, json=garcom_data)
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


@pytest.fixture
def garcom_id(garcom_criado):
    return garcom_criado["id"]


@pytest.fixture
def garcom_token(client, garcom_criado):
    response = client.post("/auth/token", data={
        "username": garcom_criado["email"],
        "password": "123456"
    })
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def garcom_headers(garcom_token):
    return {"Authorization": f"Bearer {garcom_token}"}


# Limpeza automática
@pytest.fixture(autouse=True)
def clean_funcionario_table(db_session):
    yield
    # Não deletar o admin fixture (admin@teste.com) para não afetar outros testes
    db_session.query(Funcionario).filter(Funcionario.email != "admin@teste.com").delete()
    db_session.commit()


# ========== Testes de Criação ==========
def test_criar_funcionario_admin(client, admin_headers, garcom_data):
    response = client.post("/funcionarios/", headers=admin_headers, json=garcom_data)
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["nome"] == garcom_data["nome"]
    assert data["email"] == garcom_data["email"]
    assert data["cargo"] == garcom_data["cargo"]
    assert data["ativo"] is True
    assert "id" in data
    assert "senha_hash" not in data


def test_criar_funcionario_nao_admin(client, cliente_headers, garcom_data):
    response = client.post("/funcionarios/", headers=cliente_headers, json=garcom_data)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_criar_funcionario_sem_autenticacao(client, garcom_data):
    response = client.post("/funcionarios/", json=garcom_data)
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_criar_funcionario_email_duplicado(client, admin_headers, garcom_data):
    client.post("/funcionarios/", headers=admin_headers, json=garcom_data)
    response = client.post("/funcionarios/", headers=admin_headers, json=garcom_data)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "E-mail já cadastrado" in response.text


def test_criar_funcionario_cargo_invalido(client, admin_headers):
    response = client.post("/funcionarios/", headers=admin_headers, json={
        "nome": "Invalido",
        "email": "invalido@teste.com",
        "senha": "123456",
        "cargo": "chef",
    })
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY  # Pydantic valida enum?


# ========== Testes de Listagem ==========
def test_listar_funcionarios_admin(client, admin_headers, garcom_criado):
    response = client.get("/funcionarios/", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data) >= 2  # admin inicial + garcom
    emails = [f["email"] for f in data]
    assert "admin@teste.com" in emails
    assert "garcom@teste.com" in emails


def test_listar_funcionarios_nao_admin(client, cliente_headers):
    response = client.get("/funcionarios/", headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_listar_funcionarios_filtro_ativo(client, admin_headers, garcom_criado):
    # Desativa o garcom via admin
    client.post(f"/funcionarios/{garcom_criado['id']}/desativar", headers=admin_headers)
    response = client.get("/funcionarios/?ativo=true", headers=admin_headers)
    ativos = response.json()
    assert all(f["ativo"] for f in ativos)
    response = client.get("/funcionarios/?ativo=false", headers=admin_headers)
    inativos = response.json()
    assert any(not f["ativo"] for f in inativos)


def test_listar_funcionarios_filtro_cargo(client, admin_headers, garcom_criado):
    response = client.get("/funcionarios/?cargo=garcom", headers=admin_headers)
    data = response.json()
    assert all(f["cargo"] == "garcom" for f in data)
    assert len(data) == 1
    assert data[0]["email"] == "garcom@teste.com"


def test_listar_funcionarios_filtro_cargo_invalido(client, admin_headers):
    response = client.get("/funcionarios/?cargo=caixa", headers=admin_headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST


# ========== Testes de Obter Perfil ==========
def test_obter_meu_perfil_funcionario(client, garcom_headers, garcom_criado):
    response = client.get("/funcionarios/me", headers=garcom_headers)
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == garcom_criado["id"]
    assert data["email"] == garcom_criado["email"]


def test_obter_meu_perfil_cliente(client, cliente_headers):
    response = client.get("/funcionarios/me", headers=cliente_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_obter_funcionario_por_id_admin(client, admin_headers, garcom_criado):
    response = client.get(f"/funcionarios/{garcom_criado['id']}", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["id"] == garcom_criado["id"]


def test_obter_funcionario_por_id_proprio(client, garcom_headers, garcom_criado):
    response = client.get(f"/funcionarios/{garcom_criado['id']}", headers=garcom_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["id"] == garcom_criado["id"]


def test_obter_funcionario_por_id_outro_funcionario(client, admin_headers, garcom_headers, garcom_criado):
    # Outro funcionário (garcom) tentando ver admin? Criamos um segundo funcionário? Vamos usar admin como alvo
    response = client.get("/funcionarios/1", headers=garcom_headers)  # admin id = 1 normalmente
    # Garçom não pode ver admin (não é admin nem próprio)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_obter_funcionario_inexistente(client, admin_headers):
    response = client.get("/funcionarios/999", headers=admin_headers)
    assert response.status_code == HTTPStatus.NOT_FOUND


# ========== Testes de Atualização ==========
def test_atualizar_funcionario_admin_completo(client, admin_headers, garcom_criado):
    response = client.put(
        f"/funcionarios/{garcom_criado['id']}",
        headers=admin_headers,
        json={"nome": "Novo Nome", "email": "novoemail@teste.com", "cargo": "gerente", "ativo": False}
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["nome"] == "Novo Nome"
    assert data["email"] == "novoemail@teste.com"
    assert data["cargo"] == "gerente"
    assert data["ativo"] is False


def test_atualizar_funcionario_admin_email_duplicado(client, admin_headers, garcom_criado):
    # Cria outro funcionário
    response_outro = client.post("/funcionarios/", headers=admin_headers, json={
        "nome": "Outro",
        "email": "outro@teste.com",
        "senha": "123456", 
        "cargo": "garcom",
        "telefone": "11999999999"
    })
    assert response_outro.status_code == HTTPStatus.CREATED, response_outro.text
    outro_id = response_outro.json()["id"]
    # Tenta atualizar o primeiro com email do segundo
    response = client.put(
        f"/funcionarios/{garcom_criado['id']}",
        headers=admin_headers,
        json={"email": "outro@teste.com"}
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_atualizar_funcionario_proprio_campos_permitidos(client, garcom_headers, garcom_criado):
    response = client.put(
        f"/funcionarios/{garcom_criado['id']}",
        headers=garcom_headers,
        json={"nome": "Garçom Atualizado", "telefone": "11988887777"}
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["nome"] == "Garçom Atualizado"
    assert data["telefone"] == "11988887777"
    assert data["email"] == garcom_criado["email"]  # não alterado
    assert data["cargo"] == garcom_criado["cargo"]


def test_atualizar_funcionario_proprio_campo_proibido(client, garcom_headers, garcom_criado):
    response = client.put(
        f"/funcionarios/{garcom_criado['id']}",
        headers=garcom_headers,
        json={"cargo": "admin"}
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "não pode alterar o campo 'cargo'" in response.text


def test_atualizar_funcionario_outro_sem_permissao(client, garcom_headers, admin_headers, outro_admin_data):
    # Criar outro admin via admin
    outro = client.post("/funcionarios/", headers=admin_headers, json=outro_admin_data)
    outro_id = outro.json()["id"]
    # Garçom tenta atualizar outro admin
    response = client.put(
        f"/funcionarios/{outro_id}",
        headers=garcom_headers,
        json={"nome": "Hack"}
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


# ========== Testes de Alteração de Senha ==========
def test_alterar_senha_proprio_funcionario(client, garcom_headers, garcom_criado):
    response = client.post(
        f"/funcionarios/{garcom_criado['id']}/alterar-senha",
        headers=garcom_headers,
        json={"senha_atual": "123456", "nova_senha": "nova123"}
    )
    assert response.status_code == HTTPStatus.OK
    # Verificar se a nova senha funciona
    login_resp = client.post("/auth/token", data={
        "username": garcom_criado["email"],
        "password": "nova123"
    })
    assert login_resp.status_code == 200


def test_alterar_senha_senha_atual_incorreta(client, garcom_headers, garcom_criado):
    response = client.post(
        f"/funcionarios/{garcom_criado['id']}/alterar-senha",
        headers=garcom_headers,
        json={"senha_atual": "senha_errada", "nova_senha": "nova123"}
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_alterar_senha_outro_funcionario(client, admin_headers, garcom_criado):
    # Admin tentando alterar senha do garçom (não permitido pelo código)
    response = client.post(
        f"/funcionarios/{garcom_criado['id']}/alterar-senha",
        headers=admin_headers,
        json={"senha_atual": "qualquer", "nova_senha": "nova123"}
    )
    # O endpoint verifica se o current_user.id == funcionario_id, então admin não é o próprio
    assert response.status_code == HTTPStatus.FORBIDDEN


# ========== Testes de Ativação / Desativação ==========
def test_ativar_funcionario_admin(client, admin_headers, garcom_criado):
    # Primeiro desativar
    client.post(f"/funcionarios/{garcom_criado['id']}/desativar", headers=admin_headers)
    # Reativar
    response = client.post(f"/funcionarios/{garcom_criado['id']}/ativar", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["ativo"] is True


def test_desativar_funcionario_admin(client, admin_headers, garcom_criado):
    response = client.post(f"/funcionarios/{garcom_criado['id']}/desativar", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["ativo"] is False


def test_ativar_desativar_nao_admin(client, garcom_headers, garcom_criado):
    response = client.post(f"/funcionarios/{garcom_criado['id']}/desativar", headers=garcom_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


# ========== Testes de Exclusão ==========
def test_deletar_funcionario_sem_comandas(client, admin_headers, garcom_criado):
    response = client.delete(f"/funcionarios/{garcom_criado['id']}", headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    assert "removido permanentemente" in response.json()["message"]
    # Verificar que não existe mais
    get_resp = client.get(f"/funcionarios/{garcom_criado['id']}", headers=admin_headers)
    assert get_resp.status_code == HTTPStatus.NOT_FOUND


def test_deletar_funcionario_com_comandas(client, admin_headers, garcom_criado, db_session):
    # Criar método pagamento único
    metodo = MetodoPagamento(nome="Dinheiro_Teste", ativo=True)
    mesa = Mesa(numero=999, qtd_lugares=4)
    cliente = Cliente(
        nome="Teste",
        email="teste_delete@del.com",
        senha_hash="hash",
        telefone=None,
        documento=None
    )
    db_session.add_all([metodo, mesa, cliente])
    db_session.commit()
    comanda = Comanda(
        id_garcom=garcom_criado["id"],
        id_metodo_pagamento=metodo.id,
        id_mesa=mesa.id,
        id_cliente=cliente.id,
        valor_a_pagar=100.0,
        tipo_entrega="local",
        origem="web",
        preco_total=100.0,
        id_cod_promocional=None,
        data_registro=None,
        data_finalizacao=None,
        observacao_geral=None
    )
    db_session.add(comanda)
    db_session.commit()

    response = client.delete(f"/funcionarios/{garcom_criado['id']}", headers=admin_headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "possui comandas atendidas" in response.text


def test_deletar_funcionario_nao_admin(client, garcom_headers, garcom_criado):
    response = client.delete(f"/funcionarios/{garcom_criado['id']}", headers=garcom_headers)
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_deletar_funcionario_inexistente(client, admin_headers):
    response = client.delete("/funcionarios/999", headers=admin_headers)
    assert response.status_code == HTTPStatus.NOT_FOUND
