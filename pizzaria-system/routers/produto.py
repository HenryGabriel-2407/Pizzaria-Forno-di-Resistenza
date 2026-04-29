# routes/produto.py
from http import HTTPStatus
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from pizzaria_system.database import get_session
from pizzaria_system.models import CategoriaProduto, Cliente, ComboProduto, Funcionario, Produto
from pizzaria_system.schemas import MessageResponse, ProdutoCreate, ProdutoResponse, ProdutoUpdate
from pizzaria_system.security import get_current_user

router = APIRouter(prefix='/produtos', tags=['produtos'])


# ---------- UTILITÁRIOS ----------
def _verificar_categoria_existente(categoria_id: int, session: Session) -> None:
    """Levanta HTTPException se a categoria informada não existir."""
    categoria = session.get(CategoriaProduto, categoria_id)
    if not categoria:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Categoria com id {categoria_id} não encontrada."
        )


def _verificar_produto_existente(produto_id: int, session: Session) -> Produto:
    """Retorna o produto ou levanta NOT FOUND."""
    produto = session.get(Produto, produto_id)
    if not produto:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Produto com id {produto_id} não encontrado."
        )
    return produto


def _is_admin(user: Union[Cliente, Funcionario]) -> bool:
    """Verifica se o usuário atual é um funcionário com cargo 'admin'."""
    return isinstance(user, Funcionario) and user.cargo == 'admin'


# ---------- CRUD PRODUTO ----------
@router.post('/', response_model=ProdutoResponse, status_code=HTTPStatus.CREATED, summary="Criar novo produto")
def criar_produto(
    produto_data: ProdutoCreate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """
    Cria um novo produto no cardápio.
    - Apenas administradores podem criar produtos.
    - Verifica se a categoria informada existe.
    - Os campos `popular`, `disponivel` e `tempo_preparo_medio` são opcionais.
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas administradores podem criar produtos."
        )

    _verificar_categoria_existente(produto_data.id_categoria, session)

    novo_produto = Produto(**produto_data.model_dump())
    session.add(novo_produto)
    session.commit()
    session.refresh(novo_produto)

    return novo_produto


@router.get('/', response_model=List[ProdutoResponse], summary="Listar todos os produtos")
def listar_produtos(
    session: Session = Depends(get_session),
    disponivel: bool = None,
    categoria_id: int = None,
):
    """
    Retorna a lista de produtos (público).
    Permite filtrar por disponibilidade e categoria.
    """
    query = select(Produto).options(joinedload(Produto.categoria_rel))

    if disponivel is not None:
        query = query.where(Produto.disponivel == disponivel)
    if categoria_id is not None:
        query = query.where(Produto.id_categoria == categoria_id)

    produtos = session.scalars(query).unique().all()
    return produtos


@router.get('/{produto_id}', response_model=ProdutoResponse, summary="Obter detalhes de um produto")
def obter_produto(
    produto_id: int,
    session: Session = Depends(get_session),
):
    """Retorna um produto específico pelo ID (público)."""
    produto = session.scalar(
        select(Produto)
        .where(Produto.id == produto_id)
        .options(joinedload(Produto.categoria_rel))
    )
    if not produto:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Produto não encontrado"
        )
    return produto


@router.put('/{produto_id}', response_model=ProdutoResponse, summary="Atualizar produto existente")
def atualizar_produto(
    produto_id: int,
    dados: ProdutoUpdate,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """
    Atualiza os campos informados do produto.
    - Apenas administradores podem atualizar produtos.
    - Se `id_categoria` for enviado, verifica se a nova categoria existe.
    - Atualização parcial (apenas campos enviados).
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas administradores podem atualizar produtos."
        )

    produto = _verificar_produto_existente(produto_id, session)

    if dados.id_categoria is not None:
        _verificar_categoria_existente(dados.id_categoria, session)

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(produto, campo, valor)

    session.add(produto)
    session.commit()
    session.refresh(produto)

    return produto


@router.delete('/{produto_id}', response_model=MessageResponse, summary="Remover produto")
def deletar_produto(
    produto_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """
    Remove um produto do cardápio.
    - Apenas administradores podem excluir produtos.
    - Impede a exclusão se o produto estiver vinculado a algum combo.
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Apenas administradores podem remover produtos."
        )

    produto = _verificar_produto_existente(produto_id, session)

    combo_associado = session.scalar(
        select(ComboProduto).where(ComboProduto.produto_id == produto_id)
    )
    if combo_associado:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Este produto está vinculado a um ou mais combos. "
                   "Remova-o dos combos antes de excluí-lo."
        )

    session.delete(produto)
    session.commit()
    return MessageResponse(
        message=f"Produto '{produto.nome}' removido com sucesso.",
        success=True
    )