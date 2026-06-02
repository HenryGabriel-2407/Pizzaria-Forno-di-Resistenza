import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pizzaria_system.app import app
from pizzaria_system.database import get_session
from pizzaria_system.models import CategoriaProduto, Cliente, Funcionario, Produto, table_registry
from pizzaria_system.security import get_password_hash

# Configuração do banco de teste
_temp_db_fd, _temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(_temp_db_fd)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_temp_db_path}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_session] = override_get_session

# Cria as tabelas
table_registry.metadata.create_all(bind=engine)


# Fixtures de limpeza
@pytest.fixture(scope="session", autouse=True)
def cleanup():
    yield
    engine.dispose()
    os.unlink(_temp_db_path)


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def cliente_comum(db_session): 
    db_session.query(Cliente).filter(Cliente.email == "joao@teste.com").delete()
    cliente = Cliente(
        nome="João",
        email="joao@teste.com",
        senha_hash=get_password_hash("123456"),
        telefone=None,
        documento=None,
        ativo=True,
    )
    db_session.add(cliente)
    db_session.commit()
    db_session.refresh(cliente)
    return cliente


@pytest.fixture
def cliente_token(client, cliente_comum):
    response = client.post("/auth/token", data={
        "username": cliente_comum.email,
        "password": "123456"
    })
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def cliente_headers(cliente_token):
    return {"Authorization": f"Bearer {cliente_token}"}


# Admin similar (escopo function)
@pytest.fixture
def admin_user(db_session):
    # Remove qualquer admin existente para garantir senha correta
    db_session.query(Funcionario).filter_by(email="admin@teste.com").delete()
    admin = Funcionario(
        nome="Admin Teste",
        email="admin@teste.com",
        senha_hash=get_password_hash("admin123"),
        cargo="admin",
        telefone="11999999999",
        ativo=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def admin_token(client, admin_user):
    response = client.post("/auth/token", data={
        "username": admin_user.email,
        "password": "admin123"
    })
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def sample_categoria():
    session = TestingSessionLocal()
    cat = session.query(CategoriaProduto).filter_by(nome="Pizzas").first()
    if not cat:
        cat = CategoriaProduto(nome="Pizzas")
        session.add(cat)
        session.commit()
        session.refresh(cat)
    session.close()
    return cat


@pytest.fixture
def sample_produto(db_session, sample_categoria):
    produto = Produto(
        nome="Margherita",
        descricao="Molho, mussarela, manjericão",
        imagem_link="http://example.com/margherita.jpg",
        preco=45.90,
        id_categoria=sample_categoria.id,
        tempo_preparo_medio=15,
        disponivel=True,
        popular=True,
    )
    db_session.add(produto)
    db_session.commit()
    db_session.refresh(produto)
    return produto
