from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Annotated, Union
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import decode, encode
from jwt.exceptions import ExpiredSignatureError, PyJWTError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import Cliente, Funcionario
from pizzaria_system.settings import Settings

pwd_context = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='auth/token')

settings = Settings()

T_Session = Annotated[Session, Depends(get_session)]


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password_hash(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(tz=ZoneInfo('UTC')) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({'exp': expire})
    encoded_jwt = encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def get_current_user(
    session: T_Session,
    token: str = Depends(oauth2_scheme)
) -> Union[Cliente, Funcionario]:
    credentials_exception = HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except (ExpiredSignatureError, PyJWTError):
        raise credentials_exception

    # Busca primeiro em Cliente
    user = session.scalar(select(Cliente).where(Cliente.email == username))
    if user:
        return user

    # Se não for cliente, busca em Funcionario
    funcionario = session.scalar(select(Funcionario).where(Funcionario.email == username))
    if funcionario:
        return funcionario

    # Nenhum dos dois encontrado
    raise credentials_exception