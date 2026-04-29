# routes/clientes.py
from http import HTTPStatus
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pizzaria_system.database import get_session
from pizzaria_system.models import Cliente, Funcionario, EnderecoCliente
from pizzaria_system.schemas import (
    ClienteCreate,
    ClienteResponse,
    ClienteUpdate,
    ClienteUpdatePassword,
    EnderecoClienteCreate,
    EnderecoClienteResponse,
    MessageResponse,
)
from pizzaria_system.security import get_current_user, get_password_hash, verify_password_hash

router = APIRouter(prefix='/clientes', tags=['clientes'])

T_Session = Depends(get_session)

# ---------- UTILITÁRIOS ----------
def _obter_cliente_por_id(cliente_id: int, session: Session) -> Cliente:
    cliente = session.get(Cliente, cliente_id)
    if not cliente:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Cliente com id {cliente_id} não encontrado."
        )
    return cliente


def _verificar_email_existente(email: str, session: Session, exclude_id: int = None) -> None:
    query = select(Cliente).where(Cliente.email == email)
    if exclude_id:
        query = query.where(Cliente.id != exclude_id)
    if session.scalar(query):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="E-mail já cadastrado para outro cliente."
        )


def _verificar_documento_existente(documento: str, session: Session, exclude_id: int = None) -> None:
    if not documento:
        return
    query = select(Cliente).where(Cliente.documento == documento)
    if exclude_id:
        query = query.where(Cliente.id != exclude_id)
    if session.scalar(query):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Documento (CPF/CNPJ) já cadastrado para outro cliente."
        )


def _is_admin(current_user: Union[Cliente, Funcionario]) -> bool:
    """Verifica se o usuário atual é um funcionário com cargo 'admin'."""
    return isinstance(current_user, Funcionario) and current_user.cargo == 'admin'


# ---------- CRUD CLIENTE (público/autenticado) ----------
@router.post('/', response_model=ClienteResponse, status_code=HTTPStatus.CREATED)
def criar_cliente(
    cliente_data: ClienteCreate,
    session: Session = Depends(get_session)
):
    """
    Cria um novo cliente (público).
    - A senha é armazenada com hash.
    - Endereços podem ser informados na mesma requisição.
    """
    _verificar_email_existente(cliente_data.email, session)
    _verificar_documento_existente(cliente_data.documento, session)

    cliente_dict = cliente_data.model_dump(exclude={'enderecos'})
    cliente_dict['senha_hash'] = get_password_hash(cliente_dict.pop('senha'))

    novo_cliente = Cliente(**cliente_dict)
    session.add(novo_cliente)
    session.flush()

    if cliente_data.enderecos:
        for end_data in cliente_data.enderecos:
            end_dict = end_data.model_dump()
            endereco = EnderecoCliente(id_cliente=novo_cliente.id, **end_dict)
            session.add(endereco)

    session.commit()
    session.refresh(novo_cliente)

    return session.scalar(
        select(Cliente)
        .where(Cliente.id == novo_cliente.id)
        .options(selectinload(Cliente.enderecos))
    )


@router.get('/', response_model=List[ClienteResponse])
def listar_clientes(
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
    ativo: bool = None,
    limite: int = 100,
    offset: int = 0
):
    """
    Lista clientes com paginação e filtro por 'ativo'.
    - Apenas funcionários (admin) podem listar clientes.
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Acesso restrito a administradores."
        )

    query = select(Cliente).options(selectinload(Cliente.enderecos))
    if ativo is not None:
        query = query.where(Cliente.ativo == ativo)
    query = query.offset(offset).limit(limite)
    clientes = session.scalars(query).unique().all()
    return clientes


@router.get('/me', response_model=ClienteResponse)
def obter_meu_perfil(
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Retorna o perfil do próprio cliente autenticado.
    - Se for funcionário, retorna 404 (não é cliente).
    """
    if not isinstance(current_user, Cliente):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Usuário autenticado não é um cliente."
        )
    # Recarrega com endereços
    cliente = session.scalar(
        select(Cliente)
        .where(Cliente.id == current_user.id)
        .options(selectinload(Cliente.enderecos))
    )
    return cliente


@router.get('/{cliente_id}', response_model=ClienteResponse)
def obter_cliente_por_id(
    cliente_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """
    Retorna um cliente específico pelo ID.
    - Apenas o próprio cliente ou um funcionário admin pode acessar.
    """
    # Permissão: admin ou o próprio cliente
    if not (_is_admin(current_user) or (isinstance(current_user, Cliente) and current_user.id == cliente_id)):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Você não tem permissão para acessar este perfil."
        )

    cliente = session.scalar(
        select(Cliente)
        .where(Cliente.id == cliente_id)
        .options(selectinload(Cliente.enderecos))
    )
    if not cliente:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cliente não encontrado.")
    return cliente


@router.put('/{cliente_id}', response_model=ClienteResponse)
def atualizar_cliente(
    cliente_id: int,
    dados: ClienteUpdate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """
    Atualiza dados básicos do cliente (nome, telefone, documento, ativo).
    - Apenas o próprio cliente ou admin pode modificar.
    """
    if not (_is_admin(current_user) or (isinstance(current_user, Cliente) and current_user.id == cliente_id)):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Você não pode editar este perfil."
        )

    cliente = _obter_cliente_por_id(cliente_id, session)

    if dados.email is not None:
        _verificar_email_existente(dados.email, session, cliente_id)
    if dados.documento is not None:
        _verificar_documento_existente(dados.documento, session, cliente_id)

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(cliente, campo, valor)

    session.add(cliente)
    session.commit()
    session.refresh(cliente)

    return session.scalar(
        select(Cliente)
        .where(Cliente.id == cliente.id)
        .options(selectinload(Cliente.enderecos))
    )


@router.delete('/{cliente_id}', response_model=MessageResponse)
def deletar_cliente(
    cliente_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """
    Remove um cliente (hard delete) apenas se não houver comandas vinculadas.
    - Apenas administradores podem deletar.
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas administradores podem remover clientes."
        )

    cliente = _obter_cliente_por_id(cliente_id, session)

    if cliente.comandas:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Cliente possui pedidos. Para preservar histórico, apenas desative-o."
        )

    session.delete(cliente)
    session.commit()
    return MessageResponse(
        message=f"Cliente '{cliente.nome}' removido permanentemente.",
        success=True
    )


# ---------- ENDPOINTS DE ENDEREÇO (protegidos) ----------
@router.post('/{cliente_id}/enderecos', response_model=EnderecoClienteResponse, status_code=HTTPStatus.CREATED)
def adicionar_endereco(
    cliente_id: int,
    endereco_data: EnderecoClienteCreate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Adiciona um novo endereço a um cliente existente. Permissão: próprio cliente ou admin."""
    if not (_is_admin(current_user) or (isinstance(current_user, Cliente) and current_user.id == cliente_id)):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Você não pode adicionar endereço a este perfil.")

    cliente = _obter_cliente_por_id(cliente_id, session)

    if endereco_data.padrao:
        session.query(EnderecoCliente).filter(
            EnderecoCliente.id_cliente == cliente_id,
            EnderecoCliente.padrao == True
        ).update({EnderecoCliente.padrao: False})

    novo_endereco = EnderecoCliente(id_cliente=cliente_id, **endereco_data.model_dump())
    session.add(novo_endereco)
    session.commit()
    session.refresh(novo_endereco)
    return novo_endereco


@router.put('/enderecos/{endereco_id}', response_model=EnderecoClienteResponse)
def atualizar_endereco(
    endereco_id: int,
    dados: EnderecoClienteCreate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Atualiza um endereço existente. Permissão: dono do endereço ou admin."""
    endereco = session.get(EnderecoCliente, endereco_id)
    if not endereco:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Endereço não encontrado.")

    cliente = session.get(Cliente, endereco.id_cliente)
    if not (_is_admin(current_user) or (isinstance(current_user, Cliente) and current_user.id == cliente.id)):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Você não pode editar este endereço.")

    if dados.padrao and not endereco.padrao:
        session.query(EnderecoCliente).filter(
            EnderecoCliente.id_cliente == endereco.id_cliente,
            EnderecoCliente.padrao == True
        ).update({EnderecoCliente.padrao: False})

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(endereco, campo, valor)

    session.add(endereco)
    session.commit()
    session.refresh(endereco)
    return endereco


@router.delete('/enderecos/{endereco_id}', response_model=MessageResponse)
def deletar_endereco(
    endereco_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Remove um endereço. Permissão: dono do endereço ou admin."""
    endereco = session.get(EnderecoCliente, endereco_id)
    if not endereco:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Endereço não encontrado.")

    cliente = session.get(Cliente, endereco.id_cliente)
    if not (_is_admin(current_user) or (isinstance(current_user, Cliente) and current_user.id == cliente.id)):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Você não pode remover este endereço.")

    if endereco.padrao:
        qtd_enderecos = session.query(EnderecoCliente).filter(
            EnderecoCliente.id_cliente == endereco.id_cliente
        ).count()
        if qtd_enderecos == 1:
            raise HTTPException(
                HTTPStatus.BAD_REQUEST,
                "Não é possível remover o único endereço do cliente. Adicione outro antes."
            )

    session.delete(endereco)
    session.commit()
    return MessageResponse(message="Endereço removido com sucesso.", success=True)


# ---------- ENDPOINTS DE SEGURANÇA (senha) ----------
@router.post('/{cliente_id}/alterar-senha', response_model=MessageResponse)
def alterar_senha(
    cliente_id: int,
    dados: ClienteUpdatePassword,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Altera a senha do cliente. Permissão: apenas o próprio cliente."""
    if not (isinstance(current_user, Cliente) and current_user.id == cliente_id):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Você só pode alterar sua própria senha.")

    cliente = _obter_cliente_por_id(cliente_id, session)
    if not verify_password_hash(dados.senha_atual, cliente.senha_hash):
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Senha atual incorreta.")

    cliente.senha_hash = get_password_hash(dados.nova_senha)
    session.add(cliente)
    session.commit()
    return MessageResponse(message="Senha alterada com sucesso.", success=True)


@router.post('/{cliente_id}/ativar', response_model=ClienteResponse)
def ativar_cliente(
    cliente_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Ativa um cliente (desativado anteriormente). Apenas admin."""
    if not _is_admin(current_user):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Apenas administradores podem ativar clientes.")

    cliente = _obter_cliente_por_id(cliente_id, session)
    cliente.ativo = True
    session.add(cliente)
    session.commit()
    session.refresh(cliente)
    return cliente


@router.post('/{cliente_id}/desativar', response_model=ClienteResponse)
def desativar_cliente(
    cliente_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Desativa um cliente (não pode fazer novos pedidos). Apenas admin ou o próprio cliente."""
    if not (_is_admin(current_user) or (isinstance(current_user, Cliente) and current_user.id == cliente_id)):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Apenas administradores ou o próprio cliente podem desativar a conta.")

    cliente = _obter_cliente_por_id(cliente_id, session)
    cliente.ativo = False
    session.add(cliente)
    session.commit()
    session.refresh(cliente)
    return cliente