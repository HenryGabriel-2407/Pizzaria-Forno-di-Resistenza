# routers/auth.py
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import Cliente, Funcionario
from pizzaria_system.security import create_access_token, verify_password_hash

router = APIRouter(prefix='/auth', tags=['autenticação'])


@router.post('/token')
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """
    Endpoint para obtenção do token JWT.
    Suporta login de clientes e funcionários usando email e senha.
    """
    email = form_data.username
    password = form_data.password

    # 1. Buscar em Cliente
    user = session.scalar(select(Cliente).where(Cliente.email == email))
    is_funcionario = False

    if not user:
        # 2. Se não for cliente, buscar em Funcionario
        funcionario = session.scalar(select(Funcionario).where(Funcionario.email == email))
        if funcionario:
            user = funcionario
            is_funcionario = True

    # 3. Se não encontrou em nenhuma tabela
    if not user:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Email ou senha incorretos"
        )

    # 4. Verificar a senha
    if not verify_password_hash(password, user.senha_hash):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Email ou senha incorretos"
        )

    # 5. Preparar payload do token
    token_data = {"sub": user.email}
    
    # Opcional: adicionar claim de tipo (útil para permissões futuras)
    if is_funcionario:
        token_data["tipo"] = "funcionario"
        token_data["cargo"] = user.cargo  # se existir o campo cargo
    else:
        token_data["tipo"] = "cliente"

    # 6. Criar token
    access_token = create_access_token(data=token_data)

    return {"access_token": access_token, "token_type": "bearer"}