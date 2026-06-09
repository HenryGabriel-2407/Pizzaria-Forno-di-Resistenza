from http import HTTPStatus
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import Cliente, Funcionario, MetodoPagamento
from pizzaria_system.schemas import (
    MessageResponse,
    MetodoPagamentoCreate,
    MetodoPagamentoResponse,
    MetodoPagamentoUpdate,
)
from pizzaria_system.security import get_current_user

router = APIRouter(prefix='/metodos-pagamento', tags=['metodos_pagamento'])


# ---------- UTILITÁRIOS ----------
def _verificar_metodo_existente(metodo_id: int, session: Session) -> MetodoPagamento:
    metodo = session.get(MetodoPagamento, metodo_id)
    if not metodo:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Método de pagamento com id {metodo_id} não encontrado."
        )
    return metodo


def _is_funcionario(user: Union[Cliente, Funcionario]) -> bool:
    """Verifica se o usuário é um funcionário (qualquer cargo)."""
    return isinstance(user, Funcionario)


# ---------- ENDPOINTS PÚBLICOS (leitura) ----------
@router.get('/', response_model=List[MetodoPagamentoResponse])
def listar_metodos_pagamento(
    session: Session = Depends(get_session),
    ativo: bool = None
):
    """Lista todos os métodos de pagamento. Opcionalmente filtra por 'ativo'."""
    query = select(MetodoPagamento)
    if ativo is not None:
        query = query.where(MetodoPagamento.ativo == ativo)
    metodos = session.scalars(query).all()
    return metodos


@router.get('/{metodo_id}', response_model=MetodoPagamentoResponse)
def obter_metodo_pagamento(
    metodo_id: int,
    session: Session = Depends(get_session)
):
    """Retorna um método de pagamento específico pelo ID."""
    metodo = _verificar_metodo_existente(metodo_id, session)
    return metodo


# ---------- ENDPOINTS PROTEGIDOS (apenas funcionários) ----------
@router.post('/', response_model=MetodoPagamentoResponse, status_code=HTTPStatus.CREATED)
def criar_metodo_pagamento(
    metodo_data: MetodoPagamentoCreate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Cria um novo método de pagamento. Apenas funcionários."""
    if not _is_funcionario(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas funcionários podem criar métodos de pagamento."
        )

    try:
        novo_metodo = MetodoPagamento(**metodo_data.model_dump())
        session.add(novo_metodo)
        session.commit()
        session.refresh(novo_metodo)
        return novo_metodo
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Já existe um método de pagamento com o nome '{metodo_data.nome}'."
        )


@router.put('/{metodo_id}', response_model=MetodoPagamentoResponse)
def atualizar_metodo_pagamento(
    metodo_id: int,
    dados: MetodoPagamentoUpdate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Atualiza um método de pagamento. Apenas funcionários."""
    if not _is_funcionario(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas funcionários podem alterar métodos de pagamento."
        )

    metodo = _verificar_metodo_existente(metodo_id, session)

    if dados.nome is not None and dados.nome != metodo.nome:
        try:
            for campo, valor in dados.model_dump(exclude_unset=True).items():
                setattr(metodo, campo, valor)
            session.add(metodo)
            session.commit()
            session.refresh(metodo)
        except IntegrityError:
            session.rollback()
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Já existe outro método de pagamento com o nome '{dados.nome}'."
            )
    else:
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(metodo, campo, valor)
        session.commit()
        session.refresh(metodo)
    return metodo


@router.delete('/{metodo_id}', response_model=MessageResponse)
def deletar_metodo_pagamento(
    metodo_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Remove um método de pagamento. Apenas funcionários."""
    if not _is_funcionario(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas funcionários podem remover métodos de pagamento."
        )

    metodo = _verificar_metodo_existente(metodo_id, session)

    from pizzaria_system.models import Comanda
    comanda_associada = session.scalar(
        select(Comanda).where(Comanda.id_metodo_pagamento == metodo_id).limit(1)
    )
    if comanda_associada:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Este método de pagamento está vinculado a uma ou mais comandas. Desative-o em vez de excluir."
        )

    session.delete(metodo)
    session.commit()
    return MessageResponse(
        message=f"Método de pagamento '{metodo.nome}' removido com sucesso.",
        success=True
    )
