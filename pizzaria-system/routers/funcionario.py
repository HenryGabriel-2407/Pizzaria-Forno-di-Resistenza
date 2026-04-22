from datetime import datetime
from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import Comanda, Funcionario
from pizzaria_system.schemas import (
    FuncionarioCreate,
    FuncionarioLogin,
    FuncionarioLoginResponse,
    FuncionarioResponse,
    FuncionarioUpdate,
    FuncionarioUpdatePassword,
    MessageResponse,
)
from pizzaria_system.security import get_password_hash, verifry_password_hash

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


# ---------- CRUD FUNCIONÁRIO ----------
@router.post('/', response_model=FuncionarioResponse, status_code=HTTPStatus.CREATED)
def criar_funcionario(
    func_data: FuncionarioCreate,
    session: Session = Depends(get_session)
):
    """
    Cria um novo funcionário (garçom, cozinha, admin, gerente).
    - A senha é armazenada com hash.
    - Verifica unicidade do e-mail.
    """
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
    ativo: bool = None,
    cargo: str = None,
    limite: int = 100,
    offset: int = 0
):
    """Lista funcionários com filtros opcionais e paginação."""
    query = select(Funcionario)
    if ativo is not None:
        query = query.where(Funcionario.ativo == ativo)
    if cargo:
        if cargo not in ['garcom', 'cozinha', 'admin', 'gerente']:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Cargo deve ser 'garcom', 'cozinha', 'admin' ou 'gerente'."
            )
        query = query.where(Funcionario.cargo == cargo)
    query = query.offset(offset).limit(limite)
    funcionarios = session.scalars(query).all()
    return funcionarios


@router.get('/{funcionario_id}', response_model=FuncionarioResponse)
def obter_funcionario(
    funcionario_id: int,
    session: Session = Depends(get_session)
):
    """Retorna detalhes de um funcionário específico."""
    func = _obter_funcionario_por_id(funcionario_id, session)
    return func


@router.put('/{funcionario_id}', response_model=FuncionarioResponse)
def atualizar_funcionario(
    funcionario_id: int,
    dados: FuncionarioUpdate,
    session: Session = Depends(get_session)
):
    """Atualiza dados de um funcionário (nome, e-mail, telefone, cargo, ativo)."""
    func = _obter_funcionario_por_id(funcionario_id, session)

    if dados.email is not None:
        _verificar_email_existente(dados.email, session, funcionario_id)

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(func, campo, valor)

    session.add(func)
    session.commit()
    session.refresh(func)
    return func


@router.delete('/{funcionario_id}', response_model=MessageResponse)
def deletar_funcionario(
    funcionario_id: int,
    session: Session = Depends(get_session)
):
    """
    Remove um funcionário permanentemente.
    - Impede exclusão se o funcionário atendeu comandas (preservar histórico).
    - Para desativar, use o endpoint /desativar.
    """
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


# ---------- CONTROLE DE SENHA ----------
@router.post('/{funcionario_id}/alterar-senha', response_model=MessageResponse)
def alterar_senha_funcionario(
    funcionario_id: int,
    dados: FuncionarioUpdatePassword,
    session: Session = Depends(get_session)
):
    """Altera a senha do funcionário, verificando a senha atual."""
    func = _obter_funcionario_por_id(funcionario_id, session)
    if not verifry_password_hash(dados.senha_atual, func.senha_hash):
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Senha atual incorreta.")

    func.senha_hash = get_password_hash(dados.nova_senha)
    session.add(func)
    session.commit()
    return MessageResponse(message="Senha alterada com sucesso.", success=True)


# ---------- ATIVAÇÃO / DESATIVAÇÃO ----------
@router.post('/{funcionario_id}/ativar', response_model=FuncionarioResponse)
def ativar_funcionario(
    funcionario_id: int,
    session: Session = Depends(get_session)
):
    """Ativa um funcionário (útil após desativação)."""
    func = _obter_funcionario_por_id(funcionario_id, session)
    func.ativo = True
    session.add(func)
    session.commit()
    session.refresh(func)
    return func


@router.post('/{funcionario_id}/desativar', response_model=FuncionarioResponse)
def desativar_funcionario(
    funcionario_id: int,
    session: Session = Depends(get_session)
):
    """Desativa um funcionário (não pode mais fazer login, mas mantém histórico)."""
    func = _obter_funcionario_por_id(funcionario_id, session)
    func.ativo = False
    session.add(func)
    session.commit()
    session.refresh(func)
    return func


# ---------- LOGIN (simples, sem JWT por enquanto) ----------
@router.post('/login', response_model=FuncionarioLoginResponse)
def login_funcionario(
    credenciais: FuncionarioLogin,
    session: Session = Depends(get_session)
):
    """
    Verifica credenciais do funcionário e retorna dados básicos.
    (Posteriormente será substituído por autenticação JWT)
    """
    funcionario = session.scalar(
        select(Funcionario).where(Funcionario.email == credenciais.email)
    )
    if not funcionario:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "E-mail ou senha inválidos.")
    if not verifry_password_hash(credenciais.senha, funcionario.senha_hash):
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "E-mail ou senha inválidos.")
    if not funcionario.ativo:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Funcionário desativado. Contate o administrador.")

    # Atualiza último login
    funcionario.ultimo_login = datetime.now()
    session.add(funcionario)
    session.commit()

    return FuncionarioLoginResponse(
        id=funcionario.id,
        nome=funcionario.nome,
        email=funcionario.email,
        cargo=funcionario.cargo,
        ativo=funcionario.ativo,
        message="Login bem-sucedido."
    )
