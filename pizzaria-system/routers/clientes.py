from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pizzaria_system.database import get_session
from pizzaria_system.models import Cliente, EnderecoCliente
from pizzaria_system.schemas import (
    ClienteCreate,
    ClienteResponse,
    ClienteUpdate,
    ClienteUpdatePassword,
    EnderecoClienteCreate,
    EnderecoClienteResponse,
    MessageResponse,
)
from pizzaria_system.security import get_password_hash, verifry_password_hash

router = APIRouter(prefix='/clientes', tags=['clientes'])


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


# ---------- CRUD CLIENTE ----------
@router.post('/', response_model=ClienteResponse, status_code=HTTPStatus.CREATED)
def criar_cliente(
    cliente_data: ClienteCreate,
    session: Session = Depends(get_session)
):
    """
    Cria um novo cliente.
    - A senha é armazenada com hash.
    - Endereços podem ser informados na mesma requisição.
    """
    # Validações de unicidade
    _verificar_email_existente(cliente_data.email, session)
    _verificar_documento_existente(cliente_data.documento, session)

    # Prepara dados do cliente (sem endereços)
    cliente_dict = cliente_data.model_dump(exclude={'enderecos'})
    cliente_dict['senha_hash'] = get_password_hash(cliente_dict.pop('senha'))

    novo_cliente = Cliente(**cliente_dict)
    session.add(novo_cliente)
    session.flush()  # gera o id do cliente

    # Cria endereços se informados
    if cliente_data.enderecos:
        for end_data in cliente_data.enderecos:
            end_dict = end_data.model_dump()
            endereco = EnderecoCliente(id_cliente=novo_cliente.id, **end_dict)
            session.add(endereco)

    session.commit()
    session.refresh(novo_cliente)

    # Carrega endereços para resposta (se houver)
    return session.scalar(
        select(Cliente)
        .where(Cliente.id == novo_cliente.id)
        .options(selectinload(Cliente.enderecos))
    )


@router.get('/', response_model=List[ClienteResponse])
def listar_clientes(
    session: Session = Depends(get_session),
    ativo: bool = None,
    limite: int = 100,
    offset: int = 0
):
    """Lista clientes com paginação e filtro opcional por 'ativo'."""
    query = select(Cliente).options(selectinload(Cliente.enderecos))
    if ativo is not None:
        query = query.where(Cliente.ativo == ativo)
    query = query.offset(offset).limit(limite)
    clientes = session.scalars(query).unique().all()
    return clientes


@router.get('/{cliente_id}', response_model=ClienteResponse)
def obter_cliente(
    cliente_id: int,
    session: Session = Depends(get_session)
):
    """Retorna um cliente específico pelo ID, incluindo seus endereços."""
    cliente = session.scalar(
        select(Cliente)
        .where(Cliente.id == cliente_id)
        .options(selectinload(Cliente.enderecos))
    )
    if not cliente:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Cliente não encontrado"
        )
    return cliente


@router.put('/{cliente_id}', response_model=ClienteResponse)
def atualizar_cliente(
    cliente_id: int,
    dados: ClienteUpdate,
    session: Session = Depends(get_session)
):
    """Atualiza dados básicos do cliente (nome, telefone, documento, ativo)."""
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

    # Recarrega com endereços
    return session.scalar(
        select(Cliente)
        .where(Cliente.id == cliente.id)
        .options(selectinload(Cliente.enderecos))
    )


@router.delete('/{cliente_id}', response_model=MessageResponse)
def deletar_cliente(
    cliente_id: int,
    session: Session = Depends(get_session)
):
    """
    Remove um cliente (soft delete definindo ativo=False) ou hard delete.
    Optamos por hard delete apenas se não houver comandas vinculadas.
    """
    cliente = _obter_cliente_por_id(cliente_id, session)

    # Verifica se existem comandas associadas (pedidos)
    if cliente.comandas:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Cliente possui pedidos (comandas). Para preservar histórico, apenas desative-o."
        )

    session.delete(cliente)
    session.commit()
    return MessageResponse(
        message=f"Cliente '{cliente.nome}' removido permanentemente.",
        success=True
    )


# ---------- ENDPOINTS DE ENDEREÇO ----------
@router.post('/{cliente_id}/enderecos', response_model=EnderecoClienteResponse, status_code=HTTPStatus.CREATED)
def adicionar_endereco(
    cliente_id: int,
    endereco_data: EnderecoClienteCreate,
    session: Session = Depends(get_session)
):
    """Adiciona um novo endereço a um cliente existente."""
    cliente = _obter_cliente_por_id(cliente_id, session)

    # Se este endereço for marcado como padrão, remove padrão dos outros
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
    session: Session = Depends(get_session)
):
    """Atualiza um endereço existente."""
    endereco = session.get(EnderecoCliente, endereco_id)
    if not endereco:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Endereço não encontrado")

    # Se tornando padrão, remove padrão dos outros endereços do mesmo cliente
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
    session: Session = Depends(get_session)
):
    """Remove um endereço do cliente."""
    endereco = session.get(EnderecoCliente, endereco_id)
    if not endereco:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Endereço não encontrado")

    # Impede remoção do único endereço padrão (opcional)
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
    session: Session = Depends(get_session)
):
    """Altera a senha do cliente, verificando a senha atual."""
    cliente = _obter_cliente_por_id(cliente_id, session)
    if not verifry_password_hash(dados.senha_atual, cliente.senha_hash):
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Senha atual incorreta.")

    cliente.senha_hash = get_password_hash(dados.nova_senha)
    session.add(cliente)
    session.commit()
    return MessageResponse(message="Senha alterada com sucesso.", success=True)


@router.post('/{cliente_id}/ativar', response_model=ClienteResponse)
def ativar_cliente(
    cliente_id: int,
    session: Session = Depends(get_session)
):
    """Ativa um cliente (desativado anteriormente)."""
    cliente = _obter_cliente_por_id(cliente_id, session)
    cliente.ativo = True
    session.add(cliente)
    session.commit()
    session.refresh(cliente)
    return cliente


@router.post('/{cliente_id}/desativar', response_model=ClienteResponse)
def desativar_cliente(
    cliente_id: int,
    session: Session = Depends(get_session)
):
    """Desativa um cliente (não pode fazer novos pedidos, mas mantém histórico)."""
    cliente = _obter_cliente_por_id(cliente_id, session)
    cliente.ativo = False
    session.add(cliente)
    session.commit()
    session.refresh(cliente)
    return cliente
