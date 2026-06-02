from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import CategoriaProduto
from pizzaria_system.schemas import (
    CategoriaProdutoCreate,
    CategoriaProdutoResponse,
    CategoriaProdutoUpdate,
    MessageResponse,
)

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


# ---------- CRUD ----------
@router.post('/', response_model=CategoriaProdutoResponse, status_code=HTTPStatus.CREATED)
def criar_categoria(
    categoria_data: CategoriaProdutoCreate,
    session: Session = Depends(get_session)
):
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


@router.get('/', response_model=List[CategoriaProdutoResponse])
def listar_categorias(
    session: Session = Depends(get_session)
):
    """Lista todas as categorias."""
    categorias = session.scalars(select(CategoriaProduto)).all()
    return categorias


@router.get('/{categoria_id}', response_model=CategoriaProdutoResponse)
def obter_categoria(
    categoria_id: int,
    session: Session = Depends(get_session)
):
    """Retorna uma categoria específica pelo ID."""
    categoria = _verificar_categoria_existente(categoria_id, session)
    return categoria


@router.put('/{categoria_id}', response_model=CategoriaProdutoResponse)
def atualizar_categoria(
    categoria_id: int,
    dados: CategoriaProdutoUpdate,
    session: Session = Depends(get_session)
):
    categoria = _verificar_categoria_existente(categoria_id, session)

    # Se o nome não está sendo alterado, não há risco de duplicidade
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
        # Atualização sem mudar o nome
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(categoria, campo, valor)
        session.commit()
        session.refresh(categoria)

    return categoria


@router.delete('/{categoria_id}', response_model=MessageResponse)
def deletar_categoria(
    categoria_id: int,
    session: Session = Depends(get_session)
):
    """
    Remove uma categoria.
    ATENÇÃO: Verifique se não há produtos vinculados antes de excluir.
    (Você pode adicionar uma checagem consultando Produto.id_categoria)
    """
    categoria = _verificar_categoria_existente(categoria_id, session)

    # Verificar se existem produtos usando esta categoria
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
