# routes/produto.py
from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from pizzaria_system.database import get_session
from pizzaria_system.models import CategoriaProduto, ComboProduto, Produto
from pizzaria_system.schemas import MessageResponse, ProdutoCreate, ProdutoResponse, ProdutoUpdate

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


# ---------- CRUD PRODUTO ----------

@router.post('/', response_model=ProdutoResponse, status_code=HTTPStatus.CREATED, summary="Criar novo produto")
def criar_produto(
    produto_data: ProdutoCreate,
    session: Session = Depends(get_session)
):
    """
    Cria um novo produto no cardápio.
    - Verifica se a categoria informada existe.
    - Os campos `popular`, `disponivel` e `tempo_preparo_medio` são opcionais.
    """
    # Valida categoria
    _verificar_categoria_existente(produto_data.id_categoria, session)

    # Cria instância do modelo
    novo_produto = Produto(**produto_data.model_dump())  # Transforma em dict
    session.add(novo_produto)
    session.commit()
    session.refresh(novo_produto)

    return novo_produto


@router.get('/', response_model=List[ProdutoResponse], summary="Listar todos os produtos")
def listar_produtos(
    session: Session = Depends(get_session),
    disponivel: bool = None,          # filtro opcional
    categoria_id: int = None          # filtro opcional
):
    """
    Retorna a lista de produtos. Permite filtrar por disponibilidade e categoria.
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
    session: Session = Depends(get_session)
):
    """Retorna um produto específico pelo ID, incluindo sua categoria."""
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
    session: Session = Depends(get_session)
):
    """
    Atualiza os campos informados do produto.
    - Se `id_categoria` for enviado, verifica se a nova categoria existe.
    - Atualização parcial (apenas campos enviados).
    """
    produto = _verificar_produto_existente(produto_id, session)

    # Se a categoria está sendo alterada, valida a nova
    if dados.id_categoria is not None:
        _verificar_categoria_existente(dados.id_categoria, session)

    # Aplica apenas os campos que vieram na requisição, sem sobrescrever os outros campos com valores vazios ou None
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(produto, campo, valor)

    session.add(produto)
    session.commit()
    session.refresh(produto)

    return produto


@router.delete('/{produto_id}', response_model=MessageResponse, summary="Remover produto")
def deletar_produto(
    produto_id: int,
    session: Session = Depends(get_session)
):
    """
    Remove um produto do cardápio.
    - Impede a exclusão se o produto estiver vinculado a algum combo.
    - Caso esteja, sugere remover do combo primeiro.
    """
    produto = _verificar_produto_existente(produto_id, session)

    # Verifica se o produto pertence a algum combo
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
