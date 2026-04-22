from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import MetodoPagamento
from pizzaria_system.schemas import (
    MessageResponse,
    MetodoPagamentoCreate,
    MetodoPagamentoResponse,
    MetodoPagamentoUpdate,
)

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


# ---------- CRUD ----------
@router.post('/', response_model=MetodoPagamentoResponse, status_code=HTTPStatus.CREATED)
def criar_metodo_pagamento(
    metodo_data: MetodoPagamentoCreate,
    session: Session = Depends(get_session)
):
    """Cria um novo método de pagamento (ex: PIX, Dinheiro, Cartão)."""
    novo_metodo = MetodoPagamento(**metodo_data.model_dump())
    session.add(novo_metodo)
    session.commit()
    session.refresh(novo_metodo)
    return novo_metodo


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


@router.put('/{metodo_id}', response_model=MetodoPagamentoResponse)
def atualizar_metodo_pagamento(
    metodo_id: int,
    dados: MetodoPagamentoUpdate,
    session: Session = Depends(get_session)
):
    """Atualiza um método de pagamento (apenas campos enviados)."""
    metodo = _verificar_metodo_existente(metodo_id, session)

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(metodo, campo, valor)

    session.add(metodo)
    session.commit()
    session.refresh(metodo)
    return metodo


@router.delete('/{metodo_id}', response_model=MessageResponse)
def deletar_metodo_pagamento(
    metodo_id: int,
    session: Session = Depends(get_session)
):
    """
    Remove um método de pagamento.
    ATENÇÃO: Verifique se não há comandas usando este método antes de excluir.
    """
    metodo = _verificar_metodo_existente(metodo_id, session)

    # Verificar se existe alguma comanda vinculada
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
