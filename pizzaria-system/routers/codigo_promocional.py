from datetime import date, datetime, time
from http import HTTPStatus
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import Cliente, CodPromocional, Funcionario
from pizzaria_system.schemas import (
    CodPromocionalCreate,
    CodPromocionalResponse,
    CodPromocionalUpdate,
    CodPromocionalValidate,
    CodPromocionalValidateResponse,
    MessageResponse,
)
from pizzaria_system.security import get_current_user

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


def _validar_data_validade(data_validade: date) -> None:
    if data_validade <= date.today():
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="A data de validade deve ser futura."
        )


def _is_funcionario(user: Union[Cliente, Funcionario]) -> bool:
    """Verifica se o usuário é um funcionário (qualquer cargo)."""
    return isinstance(user, Funcionario)


# ---------- ENDPOINTS PÚBLICOS (leitura) ----------
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

    valor_desconto = dados.valor_pedido * (promo.desconto_percentual / 100)
    valor_final = dados.valor_pedido - valor_desconto

    return CodPromocionalValidateResponse(
        valido=True,
        desconto_percentual=promo.desconto_percentual,
        valor_desconto=round(valor_desconto, 2),
        valor_final=round(valor_final, 2),
        mensagem="Código válido! Desconto aplicado."
    )


# ---------- ENDPOINTS PROTEGIDOS (apenas funcionários) ----------
@router.post('/', response_model=CodPromocionalResponse, status_code=HTTPStatus.CREATED)
def criar_promocao(
    promo_data: CodPromocionalCreate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Cria um novo código promocional. Apenas funcionários."""
    if not _is_funcionario(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas funcionários podem criar códigos promocionais."
        )

    _verificar_codigo_existente(promo_data.codigo, session)
    _validar_data_validade(promo_data.data_validade)

    dados = promo_data.model_dump()
    dados['data_validade'] = datetime.combine(dados['data_validade'], time.min)

    nova_promo = CodPromocional(**dados)
    session.add(nova_promo)
    session.commit()
    session.refresh(nova_promo)
    return nova_promo


@router.put('/{promo_id}', response_model=CodPromocionalResponse)
def atualizar_promocao(
    promo_id: int,
    dados: CodPromocionalUpdate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Atualiza um código promocional. Apenas funcionários."""
    if not _is_funcionario(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas funcionários podem alterar códigos promocionais."
        )

    promo = _obter_promocao_por_id(promo_id, session)

    if dados.codigo is not None:
        _verificar_codigo_existente(dados.codigo, session, promo_id)
    if dados.data_validade is not None:
        _validar_data_validade(dados.data_validade)

    update_data = dados.model_dump(exclude_unset=True)
    if 'data_validade' in update_data:
        update_data['data_validade'] = datetime.combine(update_data['data_validade'], time.min)

    for campo, valor in update_data.items():
        setattr(promo, campo, valor)

    session.add(promo)
    session.commit()
    session.refresh(promo)
    return promo


@router.delete('/{promo_id}', response_model=MessageResponse)
def deletar_promocao(
    promo_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Remove um código promocional. Apenas funcionários."""
    if not _is_funcionario(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas funcionários podem remover códigos promocionais."
        )

    promo = _obter_promocao_por_id(promo_id, session)

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
