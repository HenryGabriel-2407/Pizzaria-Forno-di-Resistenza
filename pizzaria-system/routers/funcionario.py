# routes/funcionarios.py
from datetime import datetime
from http import HTTPStatus
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import Comanda, Funcionario, Cliente
from pizzaria_system.schemas import (
    FuncionarioCreate,
    FuncionarioResponse,
    FuncionarioUpdate,
    FuncionarioUpdatePassword,
    MessageResponse,
)
from pizzaria_system.security import get_current_user, get_password_hash, verify_password_hash

router = APIRouter(prefix='/funcionarios', tags=['funcionarios'])


# ---------- UTILITÁRIOS ----------
def _obter_funcionario_por_id(func_id: int, session: Session) -> Funcionario:
    func = session.get(Funcionario, func_id)
    if not func:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Funcionário com id {func_id} não encontrado."
        )
    return func


def _verificar_email_existente(email: str, session: Session, exclude_id: int = None) -> None:
    query = select(Funcionario).where(Funcionario.email == email)
    if exclude_id:
        query = query.where(Funcionario.id != exclude_id)
    if session.scalar(query):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="E-mail já cadastrado para outro funcionário."
        )


def _is_admin(current_user: Union[Cliente, Funcionario]) -> bool:
    """Verifica se o usuário atual é um funcionário com cargo 'admin'."""
    return isinstance(current_user, Funcionario) and current_user.cargo == 'admin'


# ---------- CRUD FUNCIONÁRIO (protegido) ----------
@router.post('/', response_model=FuncionarioResponse, status_code=HTTPStatus.CREATED)
def criar_funcionario(
    func_data: FuncionarioCreate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """
    Cria um novo funcionário.
    - Apenas administradores podem criar funcionários.
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas administradores podem criar novos funcionários."
        )

    _verificar_email_existente(func_data.email, session)

    func_dict = func_data.model_dump()
    func_dict['senha_hash'] = get_password_hash(func_dict.pop('senha'))
    novo_func = Funcionario(**func_dict)
    session.add(novo_func)
    session.commit()
    session.refresh(novo_func)
    return novo_func


@router.get('/', response_model=List[FuncionarioResponse])
def listar_funcionarios(
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
    ativo: bool = None,
    cargo: str = None,
    limite: int = 100,
    offset: int = 0
):
    """
    Lista funcionários com filtros opcionais.
    - Apenas administradores podem visualizar a lista.
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Acesso restrito a administradores."
        )

    query = select(Funcionario)
    if ativo is not None:
        query = query.where(Funcionario.ativo == ativo)
    if cargo:
        allowed_cargos = ['garcom', 'cozinha', 'admin', 'gerente']
        if cargo not in allowed_cargos:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Cargo deve ser um de: {', '.join(allowed_cargos)}"
            )
        query = query.where(Funcionario.cargo == cargo)
    query = query.offset(offset).limit(limite)
    funcionarios = session.scalars(query).all()
    return funcionarios


@router.get('/me', response_model=FuncionarioResponse)
def obter_meu_perfil_funcionario(
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Retorna o perfil do próprio funcionário autenticado."""
    if not isinstance(current_user, Funcionario):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Endpoint acessível apenas para funcionários."
        )
    return current_user


@router.get('/{funcionario_id}', response_model=FuncionarioResponse)
def obter_funcionario(
    funcionario_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """
    Retorna detalhes de um funcionário específico.
    - Permissão: apenas admin ou o próprio funcionário.
    """
    if not (_is_admin(current_user) or (isinstance(current_user, Funcionario) and current_user.id == funcionario_id)):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Você não tem permissão para acessar este perfil."
        )
    func = _obter_funcionario_por_id(funcionario_id, session)
    return func


@router.put('/{funcionario_id}', response_model=FuncionarioResponse)
def atualizar_funcionario(
    funcionario_id: int,
    dados: FuncionarioUpdate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """
    Atualiza dados de um funcionário.
    - Apenas admin pode alterar qualquer dado.
    - O próprio funcionário pode alterar apenas nome, telefone (não cargo, email, ativo).
    """
    func = _obter_funcionario_por_id(funcionario_id, session)

    if _is_admin(current_user):
        # Admin pode alterar tudo
        if dados.email is not None:
            _verificar_email_existente(dados.email, session, funcionario_id)
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(func, campo, valor)
    elif isinstance(current_user, Funcionario) and current_user.id == funcionario_id:
        # Próprio funcionário: só pode alterar nome, telefone (campos permitidos)
        allowed_fields = {'nome', 'telefone'}
        update_data = dados.model_dump(exclude_unset=True)
        for campo, valor in update_data.items():
            if campo not in allowed_fields:
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail=f"Você não pode alterar o campo '{campo}'. Apenas administradores podem."
                )
            setattr(func, campo, valor)
    else:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Você não tem permissão para editar este perfil."
        )

    session.add(func)
    session.commit()
    session.refresh(func)
    return func


@router.delete('/{funcionario_id}', response_model=MessageResponse)
def deletar_funcionario(
    funcionario_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """
    Remove um funcionário permanentemente.
    - Apenas administradores podem deletar.
    - Impede exclusão se houver comandas atendidas.
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas administradores podem remover funcionários."
        )

    func = _obter_funcionario_por_id(funcionario_id, session)

    # Verifica se existem comandas atendidas por este funcionário
    comandas_atendidas = session.scalar(
        select(Comanda).where(Comanda.id_garcom == funcionario_id).limit(1)
    )
    if comandas_atendidas:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Funcionário possui comandas atendidas. "
                   "Para manter o histórico, desative-o em vez de excluir."
        )

    session.delete(func)
    session.commit()
    return MessageResponse(
        message=f"Funcionário '{func.nome}' removido permanentemente.",
        success=True
    )


# ---------- CONTROLE DE SENHA (protegido) ----------
@router.post('/{funcionario_id}/alterar-senha', response_model=MessageResponse)
def alterar_senha_funcionario(
    funcionario_id: int,
    dados: FuncionarioUpdatePassword,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """
    Altera a senha do funcionário.
    - Permissão: apenas o próprio funcionário (admin não altera senha de outros diretamente).
    """
    if not (isinstance(current_user, Funcionario) and current_user.id == funcionario_id):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Você só pode alterar sua própria senha."
        )

    func = _obter_funcionario_por_id(funcionario_id, session)
    if not verify_password_hash(dados.senha_atual, func.senha_hash):
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Senha atual incorreta.")

    func.senha_hash = get_password_hash(dados.nova_senha)
    session.add(func)
    session.commit()
    return MessageResponse(message="Senha alterada com sucesso.", success=True)


# ---------- ATIVAÇÃO / DESATIVAÇÃO (apenas admin) ----------
@router.post('/{funcionario_id}/ativar', response_model=FuncionarioResponse)
def ativar_funcionario(
    funcionario_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Reativa um funcionário desativado. Apenas admin."""
    if not _is_admin(current_user):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Apenas administradores podem ativar funcionários.")
    func = _obter_funcionario_por_id(funcionario_id, session)
    func.ativo = True
    session.add(func)
    session.commit()
    session.refresh(func)
    return func


@router.post('/{funcionario_id}/desativar', response_model=FuncionarioResponse)
def desativar_funcionario(
    funcionario_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """
    Desativa um funcionário (não pode mais fazer login).
    - Apenas admin pode desativar.
    - (O próprio funcionário não pode se desativar)
    """
    if not _is_admin(current_user):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Apenas administradores podem desativar funcionários.")
    func = _obter_funcionario_por_id(funcionario_id, session)
    func.ativo = False
    session.add(func)
    session.commit()
    session.refresh(func)
    return func