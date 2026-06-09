from datetime import datetime, timedelta
from http import HTTPStatus
from random import SystemRandom
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.email_utils import send_reset_password_email
from pizzaria_system.models import Cliente, Funcionario, PasswordResetToken
from pizzaria_system.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from pizzaria_system.security import create_access_token, get_password_hash, verify_password_hash
from pizzaria_system.settings import Settings

settings = Settings()
TOKEN_TTL_MINUTES = 30

router = APIRouter(prefix='/auth', tags=['autenticação'])


@router.post('/token')
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    email = form_data.username
    password = form_data.password

    user = session.scalar(select(Cliente).where(Cliente.email == email))
    is_funcionario = False

    if not user:
        funcionario = session.scalar(select(Funcionario).where(Funcionario.email == email))
        if funcionario:
            user = funcionario
            is_funcionario = True

    if not user:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Email ou senha incorretos"
        )

    if not verify_password_hash(password, user.senha_hash):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Email ou senha incorretos"
        )

    token_data = {"sub": user.email}

    if is_funcionario:
        token_data["tipo"] = "funcionario"
        token_data["cargo"] = user.cargo
    else:
        token_data["tipo"] = "cliente"

    access_token = create_access_token(data=token_data)

    return {"access_token": access_token, "token_type": "bearer"}


@router.post('/forgot-password', response_model=ForgotPasswordResponse)
def forgot_password(
    body: ForgotPasswordRequest,
    session: Session = Depends(get_session),
):
    email = body.email

    user = session.scalar(select(Cliente).where(Cliente.email == email))
    if not user:
        user = session.scalar(select(Funcionario).where(Funcionario.email == email))

    if not user:
        return ForgotPasswordResponse(
            message="Se o e-mail estiver cadastrado, você receberá um código de redefinição.",
            token_ttl_minutes=TOKEN_TTL_MINUTES,
        )

    code = f"{SystemRandom().randint(100000, 999999)}"
    token_hash = get_password_hash(code)
    expires_at = datetime.now(tz=ZoneInfo('UTC')).replace(tzinfo=None) + timedelta(minutes=TOKEN_TTL_MINUTES)

    token = PasswordResetToken(
        email=email,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(token)
    session.commit()

    send_reset_password_email(
        to_email=email,
        code=code,
        ttl_minutes=TOKEN_TTL_MINUTES,
    )

    return ForgotPasswordResponse(
        message="Se o e-mail estiver cadastrado, você receberá um código de redefinição.",
        token_ttl_minutes=TOKEN_TTL_MINUTES,
    )


@router.post('/reset-password', response_model=ResetPasswordResponse)
def reset_password(
    body: ResetPasswordRequest,
    session: Session = Depends(get_session),
):
    now = datetime.now(tz=ZoneInfo('UTC')).replace(tzinfo=None)

    tokens = session.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.email == body.email,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > now,
        )
    ).all()

    valid_token = None
    for t in tokens:
        if verify_password_hash(body.token, t.token_hash):
            valid_token = t
            break

    if not valid_token:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Código inválido ou expirado.",
        )

    user = session.scalar(select(Cliente).where(Cliente.email == body.email))
    if not user:
        user = session.scalar(select(Funcionario).where(Funcionario.email == body.email))

    if not user:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Código inválido ou expirado.",
        )

    user.senha_hash = get_password_hash(body.new_password)
    valid_token.used = True
    session.commit()

    return ResetPasswordResponse(message="Senha redefinida com sucesso.")
