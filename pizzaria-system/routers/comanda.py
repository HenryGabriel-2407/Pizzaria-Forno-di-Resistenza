from datetime import datetime
from http import HTTPStatus
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pizzaria_system.audit import log_audit
from pizzaria_system.database import get_session
from pizzaria_system.models import (
    Cliente,
    CodPromocional,
    Comanda,
    Combo,
    Funcionario,
    Mesa,
    MetodoPagamento,
    PedidoItem,
    Produto,
    StatusComandaLog,
)
from pizzaria_system.schemas import (
    ComandaCreate,
    ComandaResponse,
    ComandaUpdate,
    MessageResponse,
    PedidoItemCreate,
    PedidoItemCreateSemComanda,
    PedidoItemResponse,
    PedidoItemUpdate,
    StatusComandaLogResponse,
    StatusUpdateRequest,
)
from pizzaria_system.security import get_current_user

router = APIRouter(prefix='/comandas', tags=['comandas'])


# ---------- UTILITÁRIOS ----------
def _obter_comanda(comanda_id: int, session: Session) -> Comanda:
    comanda = session.get(Comanda, comanda_id)
    if not comanda:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Comanda {comanda_id} não encontrada.")
    return comanda


def _calcular_totais_comanda(comanda: Comanda) -> None:
    """Recalcula preco_total, subtotais dos itens e valor_a_pagar."""
    if not comanda.pedido_itens:
        comanda.preco_total = 0.0
    else:
        # Atualiza subtotal de cada item e soma preco_total
        total = 0.0
        for item in comanda.pedido_itens:
            item.subtotal = item.preco_unitario * item.quantidade
            total += item.subtotal
        comanda.preco_total = total
    # valor_a_pagar = preco_total - desconto + taxa_entrega
    comanda.valor_a_pagar = comanda.preco_total - comanda.desconto_aplicado + comanda.taxa_entrega
    if comanda.valor_a_pagar < 0:
        comanda.valor_a_pagar = 0.0


def _validar_itens_pedido(itens_data: List[PedidoItemCreate], session: Session) -> List[dict]:
    """Valida se produtos/combos existem e retorna lista com preco_unitario e id."""
    itens_validados = []
    for item in itens_data:
        if item.id_produto and item.id_combo:
            raise HTTPException(HTTPStatus.BAD_REQUEST,
                "Item deve ter produto OU combo, não ambos.")
        if not (item.id_produto or item.id_combo):
            raise HTTPException(HTTPStatus.BAD_REQUEST,
                "Item deve ter produto ou combo.")
        preco = None
        if item.id_produto:
            prod = session.get(Produto, item.id_produto)
            if not prod:
                raise HTTPException(HTTPStatus.NOT_FOUND,
                    f"Produto {item.id_produto} não encontrado.")
            if not prod.disponivel:
                raise HTTPException(HTTPStatus.BAD_REQUEST,
                    f"Produto '{prod.nome}' está indisponível.")
            preco = prod.preco
        else:
            combo = session.get(Combo, item.id_combo)
            if not combo:
                raise HTTPException(HTTPStatus.NOT_FOUND,
                    f"Combo {item.id_combo} não encontrado.")
            if not combo.disponivel:
                raise HTTPException(HTTPStatus.BAD_REQUEST,
                    f"Combo '{combo.nome}' está indisponível.")
            preco = combo.preco
        itens_validados.append({
            "id_produto": item.id_produto,
            "id_combo": item.id_combo,
            "quantidade": item.quantidade,
            "preco_unitario": preco,
            "subtotal": preco * item.quantidade,
            "observacao": item.observacao
        })
    return itens_validados


def _is_admin(user: Union[Cliente, Funcionario]) -> bool:
    return isinstance(user, Funcionario) and user.cargo == 'admin'


def _is_funcionario(user: Union[Cliente, Funcionario]) -> bool:
    return isinstance(user, Funcionario)


def _criar_status_log(comanda_id: int, status_anterior: str, status_novo: str, alterado_por_tipo: str, alterado_por_id: int, observacao: str, session: Session) -> None:
    log = StatusComandaLog(
        id_comanda=comanda_id,
        status_anterior=status_anterior,
        status_novo=status_novo,
        alterado_por_tipo=alterado_por_tipo,
        alterado_por_id=alterado_por_id,
        observacao=observacao,
        timestamp=datetime.now()
    )
    session.add(log)


def _validar_cliente_mesa_garcom(comanda_data: ComandaCreate, session: Session) -> None:
    if comanda_data.id_cliente:
        cliente = session.get(Cliente, comanda_data.id_cliente)
        if not cliente:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Cliente não encontrado.")
    if comanda_data.id_mesa:
        mesa = session.get(Mesa, comanda_data.id_mesa)
        if not mesa:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Mesa não encontrada.")
    if comanda_data.id_garcom:
        garcom = session.get(Funcionario, comanda_data.id_garcom)
        if not garcom or garcom.cargo not in ['garcom', 'gerente', 'admin']:
            raise HTTPException(HTTPStatus.BAD_REQUEST, "Garçom inválido.")


def _validar_metodo_pagamento(comanda_data: ComandaCreate, session: Session) -> None:
    metodo = session.get(MetodoPagamento, comanda_data.id_metodo_pagamento)
    if not metodo:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Método de pagamento não encontrado.")


def _validar_promocao(comanda_data: ComandaCreate, session: Session) -> None:
    if comanda_data.id_cod_promocional:
        promo = session.get(CodPromocional, comanda_data.id_cod_promocional)
        if not promo or not promo.ativo or promo.data_validade < datetime.now():
            raise HTTPException(HTTPStatus.BAD_REQUEST, "Código promocional inválido ou expirado.")


# ---------- CRUD COMANDA ----------
@router.post('/', response_model=ComandaResponse, status_code=HTTPStatus.CREATED)
def criar_comanda(
    comanda_data: ComandaCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    # Se for cliente, força id_cliente
    if isinstance(current_user, Cliente):
        if comanda_data.id_cliente is not None and comanda_data.id_cliente != current_user.id:
            raise HTTPException(HTTPStatus.FORBIDDEN,
                "Cliente só pode criar comanda para si mesmo.")
        comanda_data.id_cliente = current_user.id

    if not comanda_data.id_cliente and not comanda_data.id_mesa:
        raise HTTPException(HTTPStatus.BAD_REQUEST,
            "Comanda deve ter cliente (pedido online) ou mesa (local).")

    _validar_cliente_mesa_garcom(comanda_data, session)
    _validar_metodo_pagamento(comanda_data, session)
    _validar_promocao(comanda_data, session)

    itens_validados = _validar_itens_pedido(comanda_data.pedido_itens, session)

    comanda_dict = comanda_data.model_dump(exclude={'pedido_itens'})
    comanda_dict['data_registro'] = None
    comanda_dict['data_finalizacao'] = None
    nova_comanda = Comanda(**comanda_dict)
    session.add(nova_comanda)
    session.flush()

    for item in itens_validados:
        pedido_item = PedidoItem(id_comanda=nova_comanda.id, **item)
        session.add(pedido_item)

    _calcular_totais_comanda(nova_comanda)

    if isinstance(current_user, Funcionario):
        alterado_por_tipo = "funcionario"
        alterado_por_id = current_user.id
    else:
        alterado_por_tipo = "cliente"
        alterado_por_id = current_user.id
    _criar_status_log(
        nova_comanda.id, None, nova_comanda.status_comanda,
        alterado_por_tipo, alterado_por_id, "Comanda criada", session
    )
    session.commit()
    session.refresh(nova_comanda)

    result = session.scalar(
        select(Comanda)
        .where(Comanda.id == nova_comanda.id)
        .options(
            selectinload(Comanda.cliente_rel),
            selectinload(Comanda.mesa_rel),
            selectinload(Comanda.garcom_rel),
            selectinload(Comanda.metodo_pagamento_rel),
            selectinload(Comanda.cod_promocional_rel),
            selectinload(Comanda.pedido_itens),
            selectinload(Comanda.status_logs)
        )
    )
    log_audit(
        session=session,
        current_user=current_user,
        acao='comanda_create',
        tabela_afetada='comanda',
        registro_id=nova_comanda.id,
        dados_novos={'id': nova_comanda.id, 'cliente_id': nova_comanda.id_cliente, 'mesa_id': nova_comanda.id_mesa, 'total': nova_comanda.valor_a_pagar},
        request=request
    )
    session.commit()

    return result


@router.get('/', response_model=List[ComandaResponse])
def listar_comandas(
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
    status_comanda: Optional[str] = Query(None, description="aberta, em_preparo, pronta, entregue, cancelada, paga"),
    status_pagamento: Optional[str] = Query(None, description="pendente, pago, falhou"),
    tipo_entrega: Optional[str] = Query(None, description="delivery, local"),
    id_cliente: Optional[int] = None,
    id_mesa: Optional[int] = None,
    id_garcom: Optional[int] = None,
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
    limite: int = 100,
    offset: int = 0
):
    """Lista comandas com filtros e paginação.
    - Cliente só vê suas próprias comandas.
    - Funcionário vê todas (com filtros).
    """
    query = select(Comanda).options(
        selectinload(Comanda.cliente_rel),
        selectinload(Comanda.mesa_rel),
        selectinload(Comanda.garcom_rel),
        selectinload(Comanda.metodo_pagamento_rel),
        selectinload(Comanda.cod_promocional_rel),
        selectinload(Comanda.pedido_itens),
        selectinload(Comanda.status_logs)
    )
    if isinstance(current_user, Cliente):
        # Cliente só vê suas próprias comandas
        query = query.where(Comanda.id_cliente == current_user.id)
    else:
        if id_cliente:
            query = query.where(Comanda.id_cliente == id_cliente)
        if id_mesa:
            query = query.where(Comanda.id_mesa == id_mesa)
        if id_garcom:
            query = query.where(Comanda.id_garcom == id_garcom)
    if status_comanda:
        query = query.where(Comanda.status_comanda == status_comanda)
    if status_pagamento:
        query = query.where(Comanda.status_pagamento == status_pagamento)
    if tipo_entrega:
        query = query.where(Comanda.tipo_entrega == tipo_entrega)
    if data_inicio:
        query = query.where(Comanda.data_registro >= data_inicio)
    if data_fim:
        query = query.where(Comanda.data_registro <= data_fim)
    query = query.order_by(Comanda.data_registro.desc()).offset(offset).limit(limite)
    comandas = session.scalars(query).unique().all()
    return comandas


@router.get('/{comanda_id}', response_model=ComandaResponse)
def obter_comanda(
    comanda_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """
    Retorna detalhes de uma comanda.
    - Cliente só pode ver suas próprias comandas.
    - Funcionário pode ver qualquer comanda.
    """
    comanda = session.scalar(
        select(Comanda)
        .where(Comanda.id == comanda_id)
        .options(
            selectinload(Comanda.cliente_rel),
            selectinload(Comanda.mesa_rel),
            selectinload(Comanda.garcom_rel),
            selectinload(Comanda.metodo_pagamento_rel),
            selectinload(Comanda.cod_promocional_rel),
            selectinload(Comanda.pedido_itens),
            selectinload(Comanda.status_logs)
        )
    )
    if not comanda:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Comanda não encontrada.")
    if isinstance(current_user, Cliente):
        if comanda.id_cliente != current_user.id:
            raise HTTPException(HTTPStatus.FORBIDDEN, "Acesso negado a esta comanda.")
    return comanda


@router.put('/{comanda_id}', response_model=ComandaResponse)
def atualizar_comanda(
    comanda_id: int,
    dados: ComandaUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Atualiza dados básicos da comanda (exceto itens / status). Apenas funcionários podem alterar."""
    if not _is_funcionario(current_user):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Apenas funcionários podem atualizar dados da comanda.")
    comanda = _obter_comanda(comanda_id, session)
    dados_anteriores = ComandaResponse.model_validate(comanda).model_dump(mode='json')

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(comanda, campo, valor)
    # Se alterar taxa_entrega ou desconto, recalcula valor_a_pagar
    _calcular_totais_comanda(comanda)
    session.add(comanda)
    session.commit()
    session.refresh(comanda)
    log_audit(
        session=session,
        current_user=current_user,
        acao='comanda_update',
        tabela_afetada='comanda',
        registro_id=comanda.id,
        dados_anteriores=dados_anteriores,
        dados_novos=ComandaResponse.model_validate(comanda).model_dump(mode='json'),
        request=request
    )
    session.commit()
    return comanda


@router.delete('/{comanda_id}', response_model=MessageResponse)
def deletar_comanda(
    comanda_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Remove comanda apenas se status for 'cancelada' ou 'aberta'. Apenas funcionários ou o próprio cliente? Vamos permitir só funcionários."""
    if not _is_funcionario(current_user):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Apenas funcionários podem excluir comandas.")
    comanda = _obter_comanda(comanda_id, session)
    if comanda.status_pagamento == 'pago':
        raise HTTPException(HTTPStatus.BAD_REQUEST,
            "Não é possível excluir comanda com pagamento efetuado.")
    if comanda.status_comanda not in ['aberta', 'cancelada']:
        raise HTTPException(HTTPStatus.BAD_REQUEST,
            "Comanda já em preparo ou finalizada; não pode ser excluída.")

    dados_anteriores = ComandaResponse.model_validate(comanda).model_dump(mode='json')

    session.query(PedidoItem).filter(PedidoItem.id_comanda == comanda_id).delete()
    session.delete(comanda)
    session.commit()
    log_audit(
        session=session,
        current_user=current_user,
        acao='comanda_delete',
        tabela_afetada='comanda',
        registro_id=comanda_id,
        dados_anteriores=dados_anteriores,
        request=request
    )
    session.commit()

    return MessageResponse(message="Comanda removida.", success=True)


# ---------- GERENCIAMENTO DE ITENS ----------
@router.post('/{comanda_id}/itens', response_model=PedidoItemResponse, status_code=HTTPStatus.CREATED)
def adicionar_item_comanda(
    comanda_id: int,
    item_data: PedidoItemCreateSemComanda,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """
    Adiciona item à comanda.
    - Cliente só pode adicionar item à sua própria comanda (se comanda.id_cliente == current_user.id).
    - Funcionário pode adicionar a qualquer comanda.
    """
    comanda = _obter_comanda(comanda_id, session)
    if isinstance(current_user, Cliente):
        if comanda.id_cliente != current_user.id:
            raise HTTPException(HTTPStatus.FORBIDDEN, "Você não pode modificar esta comanda.")

    if comanda.status_comanda not in ['aberta']:
        raise HTTPException(HTTPStatus.BAD_REQUEST,
            "Não é possível adicionar itens a uma comanda já em preparo ou finalizada.")
    # Valida produto/combo
    if not (item_data.id_produto or item_data.id_combo):
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Informe produto ou combo.")
    preco = None
    if item_data.id_produto:
        prod = session.get(Produto, item_data.id_produto)
        if not prod or not prod.disponivel:
            raise HTTPException(HTTPStatus.BAD_REQUEST, "Produto inválido ou indisponível.")
        preco = prod.preco
    else:
        combo = session.get(Combo, item_data.id_combo)
        if not combo or not combo.disponivel:
            raise HTTPException(HTTPStatus.BAD_REQUEST, "Combo inválido ou indisponível.")
        preco = combo.preco

    novo_item = PedidoItem(
        id_comanda=comanda_id,
        id_produto=item_data.id_produto,
        id_combo=item_data.id_combo,
        quantidade=item_data.quantidade,
        preco_unitario=preco,
        subtotal=preco * item_data.quantidade,
        observacao=item_data.observacao
    )
    session.add(novo_item)
    comanda.pedido_itens.append(novo_item)
    _calcular_totais_comanda(comanda)
    session.commit()
    session.refresh(novo_item)
    log_audit(
        session=session,
        current_user=current_user,
        acao='comanda_item_add',
        tabela_afetada='pedido_item',
        registro_id=novo_item.id,
        dados_novos={'id_produto': novo_item.id_produto, 'id_combo': novo_item.id_combo, 'quantidade': novo_item.quantidade, 'preco_unitario': novo_item.preco_unitario},
        request=request
    )
    session.commit()
    return novo_item


@router.put('/itens/{item_id}', response_model=PedidoItemResponse)
def atualizar_item_comanda(
    item_id: int,
    dados: PedidoItemUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Atualiza quantidade/observação do item. Apenas se comanda estiver aberta e usuário autorizado."""
    item = session.get(PedidoItem, item_id)
    if not item:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item não encontrado.")

    comanda = item.comanda_rel   # Obtém a comanda associada

    # Permissão: cliente só pode modificar itens de suas próprias comandas
    if isinstance(current_user, Cliente):
        if comanda.id_cliente != current_user.id:
            raise HTTPException(HTTPStatus.FORBIDDEN, "Você não pode modificar este item.")

    if comanda.status_comanda not in ['aberta']:
        raise HTTPException(HTTPStatus.BAD_REQUEST,
            "Comanda já em preparo ou finalizada, não pode alterar itens.")

    dados_anteriores = PedidoItemResponse.model_validate(item).model_dump()

    if dados.quantidade is not None:
        item.quantidade = dados.quantidade
        item.subtotal = item.preco_unitario * dados.quantidade
    if dados.observacao is not None:
        item.observacao = dados.observacao

    session.add(item)
    _calcular_totais_comanda(comanda)   # Recalcula totais da comanda
    session.commit()
    session.refresh(item)

    log_audit(
        session=session,
        current_user=current_user,
        acao='comanda_item_update',
        tabela_afetada='pedido_item',
        registro_id=item.id,
        dados_anteriores=dados_anteriores,
        dados_novos=PedidoItemResponse.model_validate(item).model_dump(mode='json'),
        request=request
    )
    session.commit()

    return item


@router.delete('/itens/{item_id}', response_model=MessageResponse)
def remover_item_comanda(
    item_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user)
):
    """Remove item da comanda. Apenas se comanda aberta e usuário autorizado."""
    item = session.get(PedidoItem, item_id)
    if not item:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item não encontrado.")

    comanda = item.comanda_rel
    if isinstance(current_user, Cliente):
        if comanda.id_cliente != current_user.id:
            raise HTTPException(HTTPStatus.FORBIDDEN, "Você não pode remover este item.")

    if comanda.status_comanda not in ['aberta']:
        raise HTTPException(HTTPStatus.BAD_REQUEST,
            "Comanda já em preparo ou finalizada, não pode remover itens.")

    dados_anteriores = PedidoItemResponse.model_validate(item).model_dump()

    session.delete(item)
    if item in comanda.pedido_itens:
        comanda.pedido_itens.remove(item)
    _calcular_totais_comanda(comanda)
    session.commit()
    log_audit(
        session=session,
        current_user=current_user,
        acao='comanda_item_remove',
        tabela_afetada='pedido_item',
        registro_id=item_id,
        dados_anteriores=dados_anteriores,
        request=request
    )
    session.commit()

    return MessageResponse(message="Item removido da comanda.", success=True)


# ---------- CONTROLE DE STATUS DA COMANDA ----------
@router.post('/{comanda_id}/status', response_model=ComandaResponse)
def atualizar_status_comanda(
    comanda_id: int,
    dados: StatusUpdateRequest,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    comanda = _obter_comanda(comanda_id, session)
    status_anterior = comanda.status_comanda
    novo_status = dados.status_novo

    transicoes_validas = {
        'aberta': ['em_preparo', 'cancelada'],
        'em_preparo': ['pronta', 'cancelada'],
        'pronta': ['entregue', 'cancelada', 'pronta'],
        'entregue': ['paga'],
        'cancelada': [],
        'paga': []
    }
    if novo_status not in transicoes_validas.get(status_anterior, []):
        raise HTTPException(HTTPStatus.BAD_REQUEST,
            f"Não é permitido mudar de '{status_anterior}' para '{novo_status}'.")

    # Verificar permissões
    if isinstance(current_user, Cliente):
        # Cliente só pode cancelar comanda aberta
        if not (status_anterior == 'aberta' and novo_status == 'cancelada'):
            raise HTTPException(HTTPStatus.FORBIDDEN,
                "Cliente só pode cancelar uma comanda em aberto.")

    comanda.status_comanda = novo_status
    if novo_status == 'paga':
        comanda.status_pagamento = 'pago'
        comanda.data_finalizacao = datetime.now()
    elif novo_status == 'cancelada':
        comanda.status_pagamento = 'falhou'

    session.add(comanda)

    if isinstance(current_user, Cliente):
        alterado_por_tipo = "cliente"
        alterado_por_id = current_user.id
    else:
        alterado_por_tipo = "funcionario"
        alterado_por_id = current_user.id

    # Log de status (histórico)
    _criar_status_log(
        comanda_id, status_anterior, novo_status,
        alterado_por_tipo, alterado_por_id, dados.observacao, session
    )

    log_audit(
        session=session,
        current_user=current_user,
        acao='comanda_status_change',
        tabela_afetada='comanda',
        registro_id=comanda.id,
        dados_anteriores={'status_comanda': status_anterior},
        dados_novos={'status_comanda': novo_status},
        request=request
    )
    session.commit()
    session.refresh(comanda)
    return comanda


@router.get('/{comanda_id}/status-logs', response_model=List[StatusComandaLogResponse])
def obter_logs_status(
    comanda_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Retorna o histórico de mudanças de status. Cliente só vê se for sua comanda."""
    comanda = _obter_comanda(comanda_id, session)
    if isinstance(current_user, Cliente):
        if comanda.id_cliente != current_user.id:
            raise HTTPException(HTTPStatus.FORBIDDEN, "Acesso negado.")
    logs = session.scalars(
        select(StatusComandaLog)
        .where(StatusComandaLog.id_comanda == comanda_id)
        .order_by(StatusComandaLog.timestamp)
    ).all()
    return logs
