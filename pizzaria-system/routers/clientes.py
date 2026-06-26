# routes/clientes.py
from http import HTTPStatus
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pizzaria_system.audit import log_audit
from pizzaria_system.database import get_session
from pizzaria_system.models import Cliente, EnderecoCliente, Funcionario
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


# ========== UTILITÁRIOS ==========
def _obter_cliente_por_id(cliente_id: int, session: Session) -> Cliente:
    cliente = session.get(Cliente, cliente_id)
    if not cliente:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Cliente com id {cliente_id} não encontrado."
        )
    return cliente


def _verificar_email_existente(email: str, session: Session, exclude_id: Optional[int] = None) -> None:
    query = select(Cliente).where(Cliente.email == email)
    if exclude_id:
        query = query.where(Cliente.id != exclude_id)
    if session.scalar(query):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="E-mail já cadastrado para outro cliente."
        )


def _verificar_documento_existente(documento: Optional[str], session: Session, exclude_id: Optional[int] = None) -> None:
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


def _get_cliente_with_enderecos(cliente_id: int, session: Session) -> Cliente:
    """Retorna cliente com endereços carregados via selectinload."""
    cliente = session.scalar(
        select(Cliente)
        .where(Cliente.id == cliente_id)
        .options(selectinload(Cliente.enderecos))
    )
    if not cliente:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cliente não encontrado.")
    return cliente


# ========== ENDPOINTS DE CLIENTE ==========
@router.post('/', response_model=ClienteResponse, status_code=HTTPStatus.CREATED)
def criar_cliente(
    cliente_data: ClienteCreate,
    request: Request,
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

    if request:
        log_audit(
            session=session,
            current_user=None,
            acao='cliente_create',
            tabela_afetada='cliente',
            registro_id=novo_cliente.id,
            dados_novos={'email': novo_cliente.email, 'nome': novo_cliente.nome},
            request=request
        )
        session.commit()

    # Retorna cliente com endereços carregados
    return _get_cliente_with_enderecos(novo_cliente.id, session)


@router.get('/', response_model=List[ClienteResponse])
def listar_clientes(
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
    ativo: Optional[bool] = None,
    search: Optional[str] = Query(None, description="Busca por nome ou e-mail (parcial, case-insensitive)"),
    order_by: str = Query("id", pattern="^(id|nome|email|data_cadastro)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    limite: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Lista clientes com paginação, filtros e ordenação.
    - Apenas administradores podem acessar.
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Acesso restrito a administradores."
        )

    query = select(Cliente).options(selectinload(Cliente.enderecos))

    if ativo is not None:
        query = query.where(Cliente.ativo == ativo)
    if search:
        query = query.where(
            Cliente.nome.ilike(f"%{search}%") | Cliente.email.ilike(f"%{search}%")
        )

    # Ordenação segura
    coluna = getattr(Cliente, order_by)
    if order == "desc":
        coluna = coluna.desc()
    query = query.order_by(coluna)

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
    return _get_cliente_with_enderecos(current_user.id, session)


@router.get('/busca', response_model=List[ClienteResponse])
def buscar_clientes(
    q: str = Query(..., description="Busca por nome, e-mail ou CPF (parcial, case-insensitive)"),
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Busca clientes por nome, e-mail ou CPF. Qualquer funcionário pode usar."""
    if not isinstance(current_user, Funcionario):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Apenas funcionários podem buscar clientes.")
    query = select(Cliente).where(
        Cliente.nome.ilike(f"%{q}%") |
        Cliente.email.ilike(f"%{q}%") |
        Cliente.documento.ilike(f"%{q}%")
    ).limit(20)
    clientes = session.scalars(query).all()
    return clientes


@router.get('/{cliente_id}', response_model=ClienteResponse)
def obter_cliente_por_id(
    cliente_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """
    Retorna um cliente específico pelo ID.
    - Permissão: administrador ou o próprio cliente.
    """
    if not (_is_admin(current_user) or (isinstance(current_user, Cliente) and current_user.id == cliente_id)):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Você não tem permissão para acessar este perfil."
        )
    return _get_cliente_with_enderecos(cliente_id, session)


@router.put('/{cliente_id}', response_model=ClienteResponse)
def atualizar_cliente(
    cliente_id: int,
    dados: ClienteUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """
    Atualiza dados básicos do cliente (nome, telefone, documento, ativo).
    - Permissão: administrador ou o próprio cliente.
    - Atualização parcial (apenas campos enviados).
    """
    if not (_is_admin(current_user) or (isinstance(current_user, Cliente) and current_user.id == cliente_id)):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Você não pode editar este perfil."
        )

    cliente = _obter_cliente_por_id(cliente_id, session)
    dados_anteriores = {'email': cliente.email, 'documento': cliente.documento, 'ativo': cliente.ativo}

    if dados.email is not None:
        _verificar_email_existente(dados.email, session, cliente_id)
    if dados.documento is not None:
        _verificar_documento_existente(dados.documento, session, cliente_id)

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(cliente, campo, valor)

    session.add(cliente)
    session.commit()

    # Auditoria
    if request and _is_admin(current_user):
        log_audit(
            session=session,
            current_user=current_user,
            acao='cliente_update',
            tabela_afetada='cliente',
            registro_id=cliente.id,
            dados_anteriores=dados_anteriores,
            dados_novos={'email': cliente.email, 'documento': cliente.documento, 'ativo': cliente.ativo},
            request=request
        )
        session.commit()

    return _get_cliente_with_enderecos(cliente.id, session)


@router.delete('/{cliente_id}', response_model=MessageResponse)
def deletar_cliente(
    cliente_id: int,
    request: Request,
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

    if request:
        log_audit(
            session=session,
            current_user=current_user,
            acao='cliente_delete',
            tabela_afetada='cliente',
            registro_id=cliente_id,
            dados_anteriores={'nome': cliente.nome, 'email': cliente.email},
            request=request
        )
        session.commit()

    return MessageResponse(
        message=f"Cliente '{cliente.nome}' removido permanentemente.",
        success=True
    )


# ========== ENDPOINTS DE ENDEREÇO ==========
@router.post('/{cliente_id}/enderecos', response_model=EnderecoClienteResponse, status_code=HTTPStatus.CREATED)
def adicionar_endereco(
    cliente_id: int,
    endereco_data: EnderecoClienteCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Adiciona um novo endereço a um cliente existente. Permissão: próprio cliente ou admin."""
    if not (_is_admin(current_user) or (isinstance(current_user, Cliente) and current_user.id == cliente_id)):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Você não pode adicionar endereço a este perfil.")

    _obter_cliente_por_id(cliente_id, session)

    if endereco_data.padrao:
        session.query(EnderecoCliente).filter(
            EnderecoCliente.id_cliente == cliente_id,
            EnderecoCliente.padrao == True
        ).update({EnderecoCliente.padrao: False})

    novo_endereco = EnderecoCliente(id_cliente=cliente_id, **endereco_data.model_dump())
    session.add(novo_endereco)
    session.commit()
    session.refresh(novo_endereco)

    if request:
        log_audit(
            session=session,
            current_user=current_user,
            acao='endereco_create',
            tabela_afetada='endereco_cliente',
            registro_id=novo_endereco.id,
            dados_novos={'apelido': novo_endereco.apelido, 'rua': novo_endereco.rua},
            request=request
        )
        session.commit()

    return novo_endereco


@router.put('/enderecos/{endereco_id}', response_model=EnderecoClienteResponse)
def atualizar_endereco(
    endereco_id: int,
    dados: EnderecoClienteCreate,
    request: Request,
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

    if request:
        log_audit(
            session=session,
            current_user=current_user,
            acao='endereco_update',
            tabela_afetada='endereco_cliente',
            registro_id=endereco.id,
            dados_novos={'apelido': endereco.apelido, 'padrao': endereco.padrao},
            request=request
        )
        session.commit()

    return endereco


@router.delete('/enderecos/{endereco_id}', response_model=MessageResponse)
def deletar_endereco(
    endereco_id: int,
    request: Request,
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

    if request:
        log_audit(
            session=session,
            current_user=current_user,
            acao='endereco_delete',
            tabela_afetada='endereco_cliente',
            registro_id=endereco_id,
            dados_anteriores={'apelido': endereco.apelido},
            request=request
        )
        session.commit()

    return MessageResponse(message="Endereço removido com sucesso.", success=True)


# ========== ENDPOINTS DE SEGURANÇA ==========
@router.post('/{cliente_id}/alterar-senha', response_model=MessageResponse)
def alterar_senha(
    cliente_id: int,
    dados: ClienteUpdatePassword,
    request: Request,
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

    if request:
        log_audit(
            session=session,
            current_user=current_user,
            acao='cliente_change_password',
            tabela_afetada='cliente',
            registro_id=cliente.id,
            request=request
        )
        session.commit()

    return MessageResponse(message="Senha alterada com sucesso.", success=True)


@router.post('/{cliente_id}/ativar', response_model=ClienteResponse)
def ativar_cliente(
    cliente_id: int,
    request: Request,
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

    if request:
        log_audit(
            session=session,
            current_user=current_user,
            acao='cliente_activate',
            tabela_afetada='cliente',
            registro_id=cliente.id,
            dados_novos={'ativo': True},
            request=request
        )
        session.commit()

    session.refresh(cliente)
    return cliente


@router.post('/{cliente_id}/desativar', response_model=ClienteResponse)
def desativar_cliente(
    cliente_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Desativa um cliente (não pode fazer novos pedidos). Permissão: admin ou o próprio cliente."""
    if not (_is_admin(current_user) or (isinstance(current_user, Cliente) and current_user.id == cliente_id)):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Apenas administradores ou o próprio cliente podem desativar a conta.")

    cliente = _obter_cliente_por_id(cliente_id, session)
    cliente.ativo = False
    session.add(cliente)
    session.commit()

    if request:
        log_audit(
            session=session,
            current_user=current_user,
            acao='cliente_deactivate',
            tabela_afetada='cliente',
            registro_id=cliente.id,
            dados_novos={'ativo': False},
            request=request
        )
        session.commit()

    session.refresh(cliente)
    return cliente
