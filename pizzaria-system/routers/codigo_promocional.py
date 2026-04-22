from datetime import datetime
from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import CodPromocional
from pizzaria_system.schemas import (
    CodPromocionalCreate,
    CodPromocionalResponse,
    CodPromocionalUpdate,
    CodPromocionalValidate,
    CodPromocionalValidateResponse,
    MessageResponse,
)

router = APIRouter(prefix='/promocoes', tags=['codigos_promocionais'])


# ---------- UTILITÁRIOS ----------
def _obter_promocao_por_id(promo_id: int, session: Session) -> CodPromocional:
    promo = session.get(CodPromocional, promo_id)
    if not promo:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Código promocional com id {promo_id} não encontrado."
        )
    return promo


def _obter_promocao_por_codigo(codigo: str, session: Session) -> CodPromocional | None:
    return session.scalar(select(CodPromocional).where(CodPromocional.codigo == codigo))


def _verificar_codigo_existente(codigo: str, session: Session, exclude_id: int = None) -> None:
    query = select(CodPromocional).where(CodPromocional.codigo == codigo)
    if exclude_id:
        query = query.where(CodPromocional.id != exclude_id)
    if session.scalar(query):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Código promocional '{codigo}' já está em uso."
        )


def _validar_data_validade(data_validade: datetime) -> None:
    if data_validade <= datetime.now():
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="A data de validade deve ser futura."
        )


# ---------- CRUD ----------
@router.post('/', response_model=CodPromocionalResponse, status_code=HTTPStatus.CREATED)
def criar_promocao(
    promo_data: CodPromocionalCreate,
    session: Session = Depends(get_session)
):
    """
    Cria um novo código promocional.
    - Verifica unicidade do código.
    - Valida se a data de validade é futura.
    """
    _verificar_codigo_existente(promo_data.codigo, session)
    _validar_data_validade(promo_data.data_validade)

    nova_promo = CodPromocional(**promo_data.model_dump())
    session.add(nova_promo)
    session.commit()
    session.refresh(nova_promo)
    return nova_promo


@router.get('/', response_model=List[CodPromocionalResponse])
def listar_promocoes(
    session: Session = Depends(get_session),
    ativo: bool = None,
    limite: int = 100,
    offset: int = 0
):
    """Lista códigos promocionais. Permite filtrar por 'ativo' e paginar."""
    query = select(CodPromocional)
    if ativo is not None:
        query = query.where(CodPromocional.ativo == ativo)
    query = query.offset(offset).limit(limite)
    promos = session.scalars(query).all()
    return promos


@router.get('/{promo_id}', response_model=CodPromocionalResponse)
def obter_promocao(
    promo_id: int,
    session: Session = Depends(get_session)
):
    """Retorna um código promocional específico pelo ID."""
    promo = _obter_promocao_por_id(promo_id, session)
    return promo


@router.put('/{promo_id}', response_model=CodPromocionalResponse)
def atualizar_promocao(
    promo_id: int,
    dados: CodPromocionalUpdate,
    session: Session = Depends(get_session)
):
    """Atualiza os campos informados do código promocional."""
    promo = _obter_promocao_por_id(promo_id, session)

    # Validações condicionais
    if dados.codigo is not None:
        _verificar_codigo_existente(dados.codigo, session, promo_id)
    if dados.data_validade is not None:
        _validar_data_validade(dados.data_validade)

    # Aplica atualização parcial
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(promo, campo, valor)

    session.add(promo)
    session.commit()
    session.refresh(promo)
    return promo


@router.delete('/{promo_id}', response_model=MessageResponse)
def deletar_promocao(
    promo_id: int,
    session: Session = Depends(get_session)
):
    """
    Remove um código promocional permanentemente.
    (Recomenda-se apenas desativar, mas implementamos a exclusão física)
    """
    promo = _obter_promocao_por_id(promo_id, session)

    # Opcional: verificar se há comandas associadas usando este código
    # (caso exista relacionamento com Comanda.id_cod_promocional)
    from pizzaria_system.models import Comanda
    comanda_associada = session.scalar(
        select(Comanda).where(Comanda.id_cod_promocional == promo_id).limit(1)
    )
    if comanda_associada:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Este código promocional já foi utilizado em uma comanda. "
                   "Para manter a integridade do histórico, desative-o em vez de excluí-lo."
        )

    session.delete(promo)
    session.commit()
    return MessageResponse(
        message=f"Código promocional '{promo.codigo}' removido com sucesso.",
        success=True
    )


@router.post('/validar', response_model=CodPromocionalValidateResponse)
def validar_promocao(
    dados: CodPromocionalValidate,
    session: Session = Depends(get_session)
):
    """
    Valida um código promocional para um determinado valor de pedido.
    - Verifica se o código existe, está ativo e não está expirado.
    - Calcula o desconto aplicável.
    """
    promo = _obter_promocao_por_codigo(dados.codigo, session)
    if not promo:
        return CodPromocionalValidateResponse(
            valido=False,
            mensagem="Código promocional não encontrado."
        )

    if not promo.ativo:
        return CodPromocionalValidateResponse(
            valido=False,
            mensagem="Este código promocional está desativado."
        )

    if promo.data_validade < datetime.now():
        return CodPromocionalValidateResponse(
            valido=False,
            mensagem="Este código promocional está expirado."
        )

    # Cálculo do desconto
    valor_desconto = dados.valor_pedido * (promo.desconto_percentual / 100)
    valor_final = dados.valor_pedido - valor_desconto

    return CodPromocionalValidateResponse(
        valido=True,
        desconto_percentual=promo.desconto_percentual,
        valor_desconto=round(valor_desconto, 2),
        valor_final=round(valor_final, 2),
        mensagem="Código válido! Desconto aplicado."
    )
