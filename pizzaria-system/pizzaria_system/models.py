from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, registry

table_registry = registry()


@table_registry.mapped_as_dataclass
class User:
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    nome: Mapped[str]
    senha: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    telefone: Mapped[str]
    endereco_num_residencia: Mapped[str]
    endereco_rua: Mapped[str]
    endereco_bairro: Mapped[str]
    endereco_cidade: Mapped[str]
    endereco_complemento: Mapped[str]
    create_at: Mapped[datetime] = mapped_column(init=False, server_default=func.now())
