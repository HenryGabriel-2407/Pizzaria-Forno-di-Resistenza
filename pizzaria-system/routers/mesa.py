# routers/mesa.py
from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import Comanda, Mesa
from pizzaria_system.schemas import MesaCreate, MesaResponse, MesaUpdate, MessageResponse

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


# ---------- CRUD MESA ----------
@router.post('/', response_model=MesaResponse, status_code=HTTPStatus.CREATED)
def criar_mesa(
    mesa_data: MesaCreate,
    session: Session = Depends(get_session)
):
    """
    Cria uma nova mesa física no salão.
    - Verifica se o número da mesa é único.
    - O campo `codigo_qr` é opcional, mas se fornecido, deve ser único.
    """
    _verificar_numero_existente(mesa_data.numero, session)
    if mesa_data.codigo_qr:
        _verificar_codigo_qr_existente(mesa_data.codigo_qr, session)

    nova_mesa = Mesa(**mesa_data.model_dump())
    session.add(nova_mesa)
    session.commit()
    session.refresh(nova_mesa)
    return nova_mesa


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


@router.put('/{mesa_id}', response_model=MesaResponse)
def atualizar_mesa(
    mesa_id: int,
    dados: MesaUpdate,
    session: Session = Depends(get_session)
):
    """
    Atualiza os dados de uma mesa (número, lugares, status, código QR).
    - Verifica unicidade do número e do QR code, se alterados.
    """
    mesa = _obter_mesa_por_id(mesa_id, session)

    # Validações de unicidade apenas se os campos foram enviados
    if dados.numero is not None:
        _verificar_numero_existente(dados.numero, session, mesa_id)
    if dados.codigo_qr is not None:
        _verificar_codigo_qr_existente(dados.codigo_qr, session, mesa_id)

    # Aplica apenas campos enviados
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(mesa, campo, valor)

    session.add(mesa)
    session.commit()
    session.refresh(mesa)
    return mesa


@router.delete('/{mesa_id}', response_model=MessageResponse)
def deletar_mesa(
    mesa_id: int,
    session: Session = Depends(get_session)
):
    """
    Remove uma mesa do sistema.
    - Impede exclusão se houver comandas associadas (histórico de pedidos).
    """
    mesa = _obter_mesa_por_id(mesa_id, session)

    # Verifica se existem comandas associadas (mesmo que fechadas, mantém histórico)
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


# ---------- ENDPOINTS DE CONTROLE DE STATUS ----------
@router.post('/{mesa_id}/ocupar', response_model=MesaResponse)
def ocupar_mesa(
    mesa_id: int,
    session: Session = Depends(get_session)
):
    """Altera o status da mesa para 'ocupada'."""
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
    session: Session = Depends(get_session)
):
    """Altera o status da mesa para 'livre'."""
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
    session: Session = Depends(get_session)
):
    """Altera o status da mesa para 'reservada'."""
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


# ---------- ENDPOINT PARA GERAR QR CODE (simulação) ----------
@router.post('/{mesa_id}/gerar-qrcode', response_model=MessageResponse)
def gerar_qrcode_mesa(
    mesa_id: int,
    session: Session = Depends(get_session)
):
    """
    Gera um código QR para a mesa (simulação). 
    Em produção, você usaria uma biblioteca como `qrcode` e salvaria a imagem.
    """
    mesa = _obter_mesa_por_id(mesa_id, session)
    import uuid
    novo_qr = str(uuid.uuid4())
    # Verifica unicidade (embora UUID seja quase único)
    _verificar_codigo_qr_existente(novo_qr, session, mesa_id)
    mesa.codigo_qr = novo_qr
    session.add(mesa)
    session.commit()
    return MessageResponse(
        message=f"QR Code gerado para mesa {mesa.numero}: {novo_qr}",
        success=True
    )
