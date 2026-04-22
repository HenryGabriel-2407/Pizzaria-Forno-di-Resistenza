# routes/combo.py
from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from pizzaria_system.database import get_session
from pizzaria_system.models import Combo, ComboProduto, Produto
from pizzaria_system.schemas import ComboCreate, ComboResponse, ComboUpdate, MessageResponse

router = APIRouter(prefix='/combos', tags=['combos'])


# ---------- UTILITÁRIOS ----------
def _verificar_produtos_existentes(produtos_ids: List[int], session: Session) -> List[Produto]:
    """
    Verifica se todos os produtos informados existem.
    Retorna a lista de produtos ou levanta exceção.
    """
    produtos = session.scalars(
        select(Produto).where(Produto.id.in_(produtos_ids))
    ).all()

    if len(produtos) != len(produtos_ids):
        ids_encontrados = {p.id for p in produtos}
        ids_nao_encontrados = set(produtos_ids) - ids_encontrados
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Produtos com IDs {list(ids_nao_encontrados)} não encontrados."
        )
    return produtos


def _verificar_combo_existente(combo_id: int, session: Session) -> Combo:
    """Retorna o combo ou levanta NOT FOUND."""
    combo = session.get(Combo, combo_id)
    if not combo:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Combo com id {combo_id} não encontrado."
        )
    return combo


def _atualizar_produtos_do_combo(combo_id: int, produtos_ids: List[int], session: Session) -> None:
    """
    Atualiza a associação entre o combo e seus produtos.
    Remove associações antigas e adiciona as novas.
    """
    # Remove associações existentes
    session.execute(
        select(ComboProduto).where(ComboProduto.combo_id == combo_id)
    )
    session.query(ComboProduto).filter(ComboProduto.combo_id == combo_id).delete()

    # Adiciona novas associações
    for produto_id in produtos_ids:
        combo_produto = ComboProduto(
            combo_id=combo_id,
            produto_id=produto_id
        )
        session.add(combo_produto)


# ---------- CRUD COMBO ----------

@router.post('/', response_model=ComboResponse, status_code=HTTPStatus.CREATED, summary="Criar novo combo")
def criar_combo(
    combo_data: ComboCreate,
    session: Session = Depends(get_session)
):
    """
    Cria um novo combo no cardápio.
    - Verifica se todos os produtos informados existem.
    - Os campos `popular`, `disponivel` e `tempo_preparo_medio` são opcionais.
    """
    # Verifica se todos os produtos existem
    produtos = _verificar_produtos_existentes(combo_data.produtos_ids, session)

    # Cria instância do combo (sem os produtos ainda)
    combo_dict = combo_data.model_dump(exclude={'produtos_ids'})
    novo_combo = Combo(**combo_dict)
    session.add(novo_combo)
    session.flush()  # Garante que o combo tenha um ID antes de adicionar associações

    # Adiciona associações com produtos
    for produto in produtos:
        combo_produto = ComboProduto(
            combo_id=novo_combo.id,
            produto_id=produto.id
        )
        session.add(combo_produto)

    session.commit()
    session.refresh(novo_combo)

    # Carrega o combo com os relacionamentos para a resposta
    return novo_combo


@router.get('/', response_model=List[ComboResponse], summary="Listar todos os combos")
def listar_combos(
    session: Session = Depends(get_session),
    disponivel: bool = None,          # filtro opcional
    popular: bool = None              # filtro opcional
):
    """
    Retorna a lista de combos. Permite filtrar por disponibilidade e popularidade.
    """
    query = select(Combo).options(joinedload(Combo.produtos))

    if disponivel is not None:
        query = query.where(Combo.disponivel == disponivel)
    if popular is not None:
        query = query.where(Combo.popular == popular)

    combos = session.scalars(query).unique().all()
    return combos


@router.get('/{combo_id}', response_model=ComboResponse, summary="Obter detalhes de um combo")
def obter_combo(
    combo_id: int,
    session: Session = Depends(get_session)
):
    """Retorna um combo específico pelo ID, incluindo seus produtos."""
    combo = session.scalar(
        select(Combo)
        .where(Combo.id == combo_id)
        .options(joinedload(Combo.produtos))
    )
    if not combo:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Combo não encontrado"
        )

    return combo


@router.put('/{combo_id}', response_model=ComboResponse, summary="Atualizar combo existente")
def atualizar_combo(
    combo_id: int,
    dados: ComboUpdate,
    session: Session = Depends(get_session)
):
    """
    Atualiza os campos informados do combo.
    - Se `produtos_ids` for enviado, verifica se todos os produtos existem.
    - Atualização parcial (apenas campos enviados).
    """
    combo = _verificar_combo_existente(combo_id, session)

    # Se a lista de produtos está sendo alterada, valida e atualiza
    if dados.produtos_ids is not None:
        produtos = _verificar_produtos_existentes(dados.produtos_ids, session)
        _atualizar_produtos_do_combo(combo_id, dados.produtos_ids, session)

    # Aplica apenas os campos que vieram na requisição (excluindo produtos_ids)
    dados_dict = dados.model_dump(exclude_unset=True, exclude={'produtos_ids'})
    for campo, valor in dados_dict.items():
        setattr(combo, campo, valor)

    session.add(combo)
    session.commit()
    session.refresh(combo)

    return combo


@router.delete('/{combo_id}', response_model=MessageResponse, summary="Remover combo")
def deletar_combo(
    combo_id: int,
    session: Session = Depends(get_session)
):
    """
    Remove um combo do cardápio.
    - Remove também as associações na tabela combo_produto (cascade).
    """
    combo = _verificar_combo_existente(combo_id, session)

    # Remove associações primeiro (opcional, se não tiver cascade)
    session.query(ComboProduto).filter(ComboProduto.combo_id == combo_id).delete()

    # Remove o combo
    session.delete(combo)
    session.commit()

    return MessageResponse(
        message=f"Combo '{combo.nome}' removido com sucesso.",
        success=True
    )


@router.post('/{combo_id}/produtos/{produto_id}', response_model=MessageResponse, summary="Adicionar produto a um combo existente")
def adicionar_produto_ao_combo(
    combo_id: int,
    produto_id: int,
    session: Session = Depends(get_session)
):
    """
    Adiciona um produto existente a um combo existente.
    Útil para adicionar produtos sem precisar enviar toda a lista.
    """
    combo = _verificar_combo_existente(combo_id, session)
    produto = session.get(Produto, produto_id)

    if not produto:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Produto com id {produto_id} não encontrado."
        )

    # Verifica se o produto já está no combo
    assoc_existente = session.scalar(
        select(ComboProduto).where(
            ComboProduto.combo_id == combo_id,
            ComboProduto.produto_id == produto_id
        )
    )

    if assoc_existente:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Este produto já está associado a este combo."
        )

    # Cria nova associação
    combo_produto = ComboProduto(
        combo_id=combo_id,
        produto_id=produto_id
    )
    session.add(combo_produto)
    session.commit()

    return MessageResponse(
        message=f"Produto '{produto.nome}' adicionado ao combo '{combo.nome}' com sucesso.",
        success=True
    )


@router.delete(
    '/{combo_id}/produtos/{produto_id}',
    response_model=MessageResponse,
    summary="Remover produto de um combo"
)
def remover_produto_do_combo(
    combo_id: int,
    produto_id: int,
    session: Session = Depends(get_session)
):
    """
    Remove um produto de um combo existente.
    Não remove o produto nem o combo, apenas a associação.
    """
    combo = _verificar_combo_existente(combo_id, session)
    produto = session.get(Produto, produto_id)

    if not produto:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Produto com id {produto_id} não encontrado."
        )

    # Remove a associação
    resultado = session.query(ComboProduto).filter(
        ComboProduto.combo_id == combo_id,
        ComboProduto.produto_id == produto_id
    ).delete()

    if resultado == 0:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Esta associação entre produto e combo não existe."
        )

    session.commit()

    return MessageResponse(
        message=f"Produto '{produto.nome}' removido do combo '{combo.nome}' com sucesso.",
        success=True
    )
