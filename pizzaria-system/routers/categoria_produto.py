from http import HTTPStatus
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import CategoriaProduto, Cliente, Funcionario
from pizzaria_system.schemas import (
    CategoriaProdutoCreate,
    CategoriaProdutoResponse,
    CategoriaProdutoUpdate,
    MessageResponse,
)
from pizzaria_system.security import get_current_user

router = APIRouter(prefix='/categorias', tags=['categorias'])


# ---------- UTILITÁRIOS ----------
def _verificar_categoria_existente(categoria_id: int, session: Session) -> CategoriaProduto:
    categoria = session.get(CategoriaProduto, categoria_id)
    if not categoria:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Categoria com id {categoria_id} não encontrada."
        )
    return categoria


def _is_admin(user: Union[Cliente, Funcionario]) -> bool:
    """Verifica se o usuário é um funcionário com cargo 'admin'."""
    return isinstance(user, Funcionario) and user.cargo == 'admin'


# ---------- ENDPOINTS PÚBLICOS (apenas leitura) ----------
@router.get('/', response_model=List[CategoriaProdutoResponse])
def listar_categorias(
    session: Session = Depends(get_session)
):
    """Lista todas as categorias (público)."""
    categorias = session.scalars(select(CategoriaProduto)).all()
    return categorias


@router.get('/{categoria_id}', response_model=CategoriaProdutoResponse)
def obter_categoria(
    categoria_id: int,
    session: Session = Depends(get_session)
):
    """Retorna uma categoria específica pelo ID (público)."""
    categoria = _verificar_categoria_existente(categoria_id, session)
    return categoria


# ---------- ENDPOINTS PROTEGIDOS (apenas admin) ----------
@router.post('/', response_model=CategoriaProdutoResponse, status_code=HTTPStatus.CREATED)
def criar_categoria(
    categoria_data: CategoriaProdutoCreate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Cria uma nova categoria. Apenas administradores."""
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas administradores podem criar categorias."
        )

    try:
        nova_categoria = CategoriaProduto(**categoria_data.model_dump())
        session.add(nova_categoria)
        session.commit()
        session.refresh(nova_categoria)
        return nova_categoria
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Já existe uma categoria com o nome '{categoria_data.nome}'."
        )


@router.put('/{categoria_id}', response_model=CategoriaProdutoResponse)
def atualizar_categoria(
    categoria_id: int,
    dados: CategoriaProdutoUpdate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Atualiza uma categoria. Apenas administradores."""
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas administradores podem alterar categorias."
        )

    categoria = _verificar_categoria_existente(categoria_id, session)

    if dados.nome is not None and dados.nome != categoria.nome:
        try:
            for campo, valor in dados.model_dump(exclude_unset=True).items():
                setattr(categoria, campo, valor)
            session.commit()
            session.refresh(categoria)
        except IntegrityError:
            session.rollback()
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Já existe outra categoria com o nome '{dados.nome}'."
            )
    else:
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(categoria, campo, valor)
        session.commit()
        session.refresh(categoria)

    return categoria


@router.delete('/{categoria_id}', response_model=MessageResponse)
def deletar_categoria(
    categoria_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Remove uma categoria. Apenas administradores."""
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas administradores podem remover categorias."
        )

    categoria = _verificar_categoria_existente(categoria_id, session)

    from pizzaria_system.models import Produto
    produtos_associados = session.scalar(
        select(Produto).where(Produto.id_categoria == categoria_id).limit(1)
    )
    if produtos_associados:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Existem produtos vinculados a esta categoria. Remova ou altere os produtos antes de excluir a categoria."
        )

    session.delete(categoria)
    session.commit()
    return MessageResponse(
        message=f"Categoria '{categoria.nome}' removida com sucesso.",
        success=True
    )
