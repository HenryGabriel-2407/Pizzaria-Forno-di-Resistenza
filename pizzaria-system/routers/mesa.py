from http import HTTPStatus
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import Cliente, Comanda, Funcionario, Mesa
from pizzaria_system.schemas import MesaCreate, MesaResponse, MesaUpdate, MessageResponse
from pizzaria_system.security import get_current_user
from pizzaria_system.settings import Settings

router = APIRouter(prefix='/mesas', tags=['mesas'])


# ---------- UTILITÁRIOS ----------
def _obter_mesa_por_id(mesa_id: int, session: Session) -> Mesa:
    mesa = session.get(Mesa, mesa_id)
    if not mesa:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Mesa com id {mesa_id} não encontrada."
        )
    return mesa


def _verificar_numero_existente(numero: int, session: Session, exclude_id: int = None) -> None:
    query = select(Mesa).where(Mesa.numero == numero)
    if exclude_id:
        query = query.where(Mesa.id != exclude_id)
    if session.scalar(query):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Número de mesa {numero} já está em uso."
        )


def _verificar_codigo_qr_existente(codigo_qr: str, session: Session, exclude_id: int = None) -> None:
    if not codigo_qr:
        return
    query = select(Mesa).where(Mesa.codigo_qr == codigo_qr)
    if exclude_id:
        query = query.where(Mesa.id != exclude_id)
    if session.scalar(query):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Este código QR já está associado a outra mesa."
        )


def _is_funcionario(user: Union[Cliente, Funcionario]) -> bool:
    """Verifica se o usuário é um funcionário (qualquer cargo)."""
    return isinstance(user, Funcionario)


# ---------- ENDPOINTS PÚBLICOS (leitura) ----------
@router.get('/', response_model=List[MesaResponse])
def listar_mesas(
    session: Session = Depends(get_session),
    status: str = None,
    limite: int = 100,
    offset: int = 0
):
    """
    Lista todas as mesas. Permite filtrar por status e paginar.
    """
    query = select(Mesa)
    if status:
        if status not in ['livre', 'ocupada', 'reservada']:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Status deve ser 'livre', 'ocupada' ou 'reservada'."
            )
        query = query.where(Mesa.status == status)
    query = query.offset(offset).limit(limite)
    mesas = session.scalars(query).all()
    return mesas


@router.get('/{mesa_id}', response_model=MesaResponse)
def obter_mesa(
    mesa_id: int,
    session: Session = Depends(get_session)
):
    """Retorna os detalhes de uma mesa específica."""
    mesa = _obter_mesa_por_id(mesa_id, session)
    return mesa


# ---------- ENDPOINTS PROTEGIDOS (apenas funcionários) ----------
@router.post('/', response_model=MesaResponse, status_code=HTTPStatus.CREATED)
def criar_mesa(
    mesa_data: MesaCreate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Cria uma nova mesa. Apenas funcionários podem criar."""
    if not _is_funcionario(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas funcionários podem criar mesas."
        )

    _verificar_numero_existente(mesa_data.numero, session)

    nova_mesa = Mesa(**mesa_data.model_dump())
    session.add(nova_mesa)
    session.flush()

    settings = Settings()
    qr_string = f"{settings.BASE_URL}/mesa/{nova_mesa.id}"
    nova_mesa.codigo_qr = qr_string

    session.commit()
    session.refresh(nova_mesa)
    return nova_mesa


@router.put('/{mesa_id}', response_model=MesaResponse)
def atualizar_mesa(
    mesa_id: int,
    dados: MesaUpdate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """
    Atualiza os dados de uma mesa. Apenas funcionários.
    """
    if not _is_funcionario(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas funcionários podem alterar mesas."
        )

    mesa = _obter_mesa_por_id(mesa_id, session)

    if dados.numero is not None:
        _verificar_numero_existente(dados.numero, session, mesa_id)
    if dados.codigo_qr is not None:
        _verificar_codigo_qr_existente(dados.codigo_qr, session, mesa_id)

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(mesa, campo, valor)

    session.add(mesa)
    session.commit()
    session.refresh(mesa)
    return mesa


@router.delete('/{mesa_id}', response_model=MessageResponse)
def deletar_mesa(
    mesa_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """
    Remove uma mesa do sistema. Apenas funcionários.
    """
    if not _is_funcionario(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas funcionários podem remover mesas."
        )

    mesa = _obter_mesa_por_id(mesa_id, session)

    comandas_associadas = session.scalar(
        select(Comanda).where(Comanda.id_mesa == mesa_id).limit(1)
    )
    if comandas_associadas:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Esta mesa possui comandas (pedidos) no histórico. Não é possível excluí-la."
        )

    session.delete(mesa)
    session.commit()
    return MessageResponse(
        message=f"Mesa {mesa.numero} removida com sucesso.",
        success=True
    )


# ---------- ENDPOINTS DE CONTROLE DE STATUS (apenas funcionários) ----------
@router.post('/{mesa_id}/ocupar', response_model=MesaResponse)
def ocupar_mesa(
    mesa_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Altera o status da mesa para 'ocupada'. Apenas funcionários."""
    if not _is_funcionario(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas funcionários podem alterar o status da mesa."
        )

    mesa = _obter_mesa_por_id(mesa_id, session)
    if mesa.status == 'ocupada':
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Mesa já está ocupada."
        )
    mesa.status = 'ocupada'
    session.add(mesa)
    session.commit()
    session.refresh(mesa)
    return mesa


@router.post('/{mesa_id}/liberar', response_model=MesaResponse)
def liberar_mesa(
    mesa_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Altera o status da mesa para 'livre'. Apenas funcionários."""
    if not _is_funcionario(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas funcionários podem alterar o status da mesa."
        )

    mesa = _obter_mesa_por_id(mesa_id, session)
    if mesa.status == 'livre':
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Mesa já está livre."
        )
    mesa.status = 'livre'
    session.add(mesa)
    session.commit()
    session.refresh(mesa)
    return mesa


@router.post('/{mesa_id}/reservar', response_model=MesaResponse)
def reservar_mesa(
    mesa_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Altera o status da mesa para 'reservada'. Apenas funcionários."""
    if not _is_funcionario(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas funcionários podem alterar o status da mesa."
        )

    mesa = _obter_mesa_por_id(mesa_id, session)
    if mesa.status == 'reservada':
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Mesa já está reservada."
        )
    mesa.status = 'reservada'
    session.add(mesa)
    session.commit()
    session.refresh(mesa)
    return mesa
