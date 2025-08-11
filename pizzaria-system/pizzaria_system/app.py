from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import User
from pizzaria_system.schemas import Create_User, List_User, User_Public
from pizzaria_system.security import get_password_hash

app = FastAPI()

T_Session = Annotated[Session, Depends(get_session)]


@app.post("/", status_code=HTTPStatus.CREATED, response_model=User_Public)
def create_user(user: Create_User, session: T_Session):
    db_user = session.scalar(select(User).where((User.email == user.email)))
    if db_user:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Email existe no sistema")
    try:
        db_user = User(
            nome=user.nome,
            email=user.email,
            senha=get_password_hash(user.senha),
            telefone=user.telefone,
            endereco_num_residencia=user.endereco_num_residencia,
            endereco_rua=user.endereco_rua,
            endereco_bairro=user.endereco_bairro,
            endereco_cidade=user.endereco_cidade,
            endereco_complemento=user.endereco_complemento,
        )

        session.add(db_user)
        session.commit()
        session.refresh(db_user)

        return db_user

    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="Email já existe")


@app.delete("/{user_id}", status_code=HTTPStatus.OK)
def delete_user(user_id: int, session: T_Session):
    db_user = session.scalar(select(User).where((User.id == user_id)))
    if not db_user:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Não existe o usuário")
    session.delete(db_user)
    session.commit()
    return {"message": "User deleted"}


@app.put("/{user_id}", response_model=User_Public)
def update_user(user_id: int, user: Create_User, session: T_Session):
    db_user = session.scalar(select(User).where((User.id == user_id)))
    if not db_user:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Não existe o usuário")
    try:
        db_user.nome = user.nome
        db_user.email = user.email
        db_user.senha = user.senha
        db_user.telefone = user.telefone
        db_user.endereco_num_residencia = user.endereco_num_residencia
        db_user.endereco_rua = user.endereco_rua
        db_user.endereco_bairro = user.endereco_bairro
        db_user.endereco_cidade = user.endereco_cidade
        db_user.endereco_complemento = user.endereco_complemento
        session.commit()
        session.refresh(db_user)
        return db_user
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Username or Email already exists",
        )


@app.get("/", response_model=List_User, status_code=HTTPStatus.OK)
def read_users(session: T_Session, limit: int = 10, offset: int = 0):
    users = session.scalars(select(User).limit(limit).offset(offset))
    return {"list_users": users}


@app.get("/{user_id}", response_model=User_Public, status_code=HTTPStatus.OK)
def get_user(user_id: int, session: T_Session):
    db_user = session.scalar(select(User).where(User.id == user_id))
    if not db_user:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Usuário não existe")
    return db_user
