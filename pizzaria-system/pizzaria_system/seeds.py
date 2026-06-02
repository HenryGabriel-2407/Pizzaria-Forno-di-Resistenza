from sqlalchemy.orm import Session

from pizzaria_system.models import Funcionario
from pizzaria_system.security import get_password_hash
from pizzaria_system.settings import Settings


def criar_primeiro_admin(session: Session):
    """Cria um administrador inicial se não existir nenhum funcionário."""
    settings = Settings()

    # Verifica se já existe algum funcionário
    if session.query(Funcionario).first() is not None:
        print("ℹ️ Já existe pelo menos um funcionário. Seed de admin ignorado.")
        return

    admin_email = settings.ADMIN_EMAIL
    admin_password = settings.ADMIN_PASSWORD
    admin_name = settings.ADMIN_NAME

    admin = Funcionario(
        nome=admin_name,
        email=admin_email,
        senha_hash=get_password_hash(admin_password),
        cargo="admin",
        ativo=True,
        telefone=None 
    )
    session.add(admin)
    session.commit()
    print(f"✅ Admin criado: {admin_email}")
