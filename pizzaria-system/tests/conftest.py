import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pizzaria_system.app import app 
from pizzaria_system.database import get_session
from pizzaria_system.models import table_registry, CategoriaProduto, Produto, Funcionario, Cliente
from pizzaria_system.security import get_password_hash
from datetime import datetime

# Cria um arquivo de banco de dados temporário
@pytest.fixture(scope="session")
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)

@pytest.fixture(scope="session")
def engine(temp_db):
    db_url = f"sqlite:///{temp_db}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    # Cria as tabelas uma única vez
    table_registry.metadata.create_all(bind=engine)
    yield engine
    table_registry.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture(scope="session")
def TestingSessionLocal(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_session(TestingSessionLocal):
    def _override():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    return _override

# ============================================
# Configuração global (executada uma vez no carregamento do conftest)
# ============================================
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

# Cria as tabelas imediatamente (fora das fixtures)
table_registry.metadata.create_all(bind=engine)

# ------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def cleanup():
    """Remove o arquivo de banco de dados após todos os testes."""
    yield
    engine.dispose()
    os.unlink(_temp_db_path)

@pytest.fixture
def db_session():
    """Sessão isolada para cada teste – com rollback automático."""
    session = TestingSessionLocal()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def client():
    return TestClient(app)

# Categoria única (escopo session) – usa a sessão global
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

# Admin único (escopo session)
@pytest.fixture(scope="session")
def admin_user():
    session = TestingSessionLocal()
    admin = session.query(Funcionario).filter_by(email="admin@teste.com").first()
    if not admin:
        admin = Funcionario(
            nome="Admin Teste",
            email="admin@teste.com",
            senha_hash=get_password_hash("admin123"),
            cargo="admin",
            telefone="11999999999",
            data_contratacao=datetime.now(),
            ultimo_login=None,
            ativo=True,
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
    session.close()
    return admin

# Cliente comum único (escopo session)
@pytest.fixture(scope="session")
def cliente_comum():
    session = TestingSessionLocal()
    cliente = session.query(Cliente).filter_by(email="joao@teste.com").first()
    if not cliente:
        cliente = Cliente(
            nome="João",
            email="joao@teste.com",
            senha_hash=get_password_hash("123456"),
            telefone=None,
            documento=None,
            data_cadastro=datetime.now(),
            ultimo_login=None,
            ativo=True,
        )
        session.add(cliente)
        session.commit()
        session.refresh(cliente)
    session.close()
    return cliente

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