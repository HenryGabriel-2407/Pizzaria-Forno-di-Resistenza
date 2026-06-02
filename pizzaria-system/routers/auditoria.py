from datetime import datetime
from http import HTTPStatus
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pizzaria_system.database import get_session
from pizzaria_system.models import AuditLog, Cliente, Funcionario
from pizzaria_system.schemas import AuditLogResponse
from pizzaria_system.security import get_current_user

router = APIRouter(prefix='/audit-logs', tags=['auditoria'])


# ---------- UTILITÁRIO DE PERMISSÃO ----------
def _verificar_permissao_auditoria(current_user: Union[Cliente, Funcionario]) -> None:
    """
    Verifica se o usuário autenticado é funcionário com cargo 'admin' ou 'gerente'.
    Levanta HTTPException 403 se não tiver permissão.
    """
    if not isinstance(current_user, Funcionario):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Acesso negado. Apenas funcionários podem visualizar logs de auditoria."
        )
    if current_user.cargo not in ['admin', 'gerente']:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Acesso negado. Necessário cargo de administrador ou gerente."
        )


# ---------- ENDPOINTS ----------
@router.get('/', response_model=List[AuditLogResponse])
def listar_logs(
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
    # Filtros
    usuario_tipo: Optional[str] = Query(None, description="cliente, funcionario, sistema"),
    usuario_id: Optional[int] = None,
    funcionario_id: Optional[int] = None,
    acao: Optional[str] = None,
    tabela_afetada: Optional[str] = None,
    registro_id: Optional[int] = None,
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
    # Paginação e ordenação
    limite: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    order_by: str = Query("timestamp", description="Campo para ordenar (timestamp, acao, etc.)"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="asc ou desc"),
):
    """
    Lista logs de auditoria com filtros, paginação e ordenação.
    Acesso restrito a funcionários com cargo admin ou gerente.
    """
    _verificar_permissao_auditoria(current_user)

    # Validações de ordenação segura (whitelist de colunas)
    colunas_permitidas = {"timestamp", "acao", "usuario_tipo", "tabela_afetada"}
    if order_by not in colunas_permitidas:
        order_by = "timestamp"

    query = select(AuditLog)
    if usuario_tipo:
        query = query.where(AuditLog.usuario_tipo == usuario_tipo)
    if usuario_id is not None:
        query = query.where(AuditLog.usuario_id == usuario_id)
    if funcionario_id is not None:
        query = query.where(AuditLog.funcionario_id == funcionario_id)
    if acao:
        query = query.where(AuditLog.acao == acao)
    if tabela_afetada:
        query = query.where(AuditLog.tabela_afetada == tabela_afetada)
    if registro_id is not None:
        query = query.where(AuditLog.registro_id == registro_id)
    if data_inicio:
        query = query.where(AuditLog.timestamp >= data_inicio)
    if data_fim:
        query = query.where(AuditLog.timestamp <= data_fim)

    # Ordenação dinâmica segura
    if order == "asc":
        query = query.order_by(getattr(AuditLog, order_by).asc())
    else:
        query = query.order_by(getattr(AuditLog, order_by).desc())

    query = query.offset(offset).limit(limite)
    logs = session.scalars(query).all()
    return logs


@router.get('/{log_id}', response_model=AuditLogResponse)
def obter_log(
    log_id: int,
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Retorna um log específico."""
    _verificar_permissao_auditoria(current_user)
    log = session.get(AuditLog, log_id)
    if not log:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Log não encontrado.")
    return log


@router.get('/acoes/disponiveis', response_model=List[str])
def listar_acoes_disponiveis(
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Retorna lista de ações distintas registradas nos logs (para filtro)."""
    _verificar_permissao_auditoria(current_user)
    result = session.scalars(select(AuditLog.acao).distinct()).all()
    return result


@router.get('/tabelas/disponiveis', response_model=List[str])
def listar_tabelas_afetadas(
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
):
    """Retorna lista de tabelas afetadas distintas (para filtro)."""
    _verificar_permissao_auditoria(current_user)
    result = session.scalars(select(AuditLog.tabela_afetada).distinct()).all()
    # Remove None se houver
    return [r for r in result if r is not None]


@router.get('/estatisticas/por-acao')
def estatisticas_por_acao(
    session: Session = Depends(get_session),
    current_user: Union[Cliente, Funcionario] = Depends(get_current_user),
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
):
    """
    Retorna contagem de logs agrupados por ação.
    Opcionalmente filtrando por período.
    """
    _verificar_permissao_auditoria(current_user)
    query = select(AuditLog.acao, func.count(AuditLog.id)).group_by(AuditLog.acao)
    if data_inicio:
        query = query.where(AuditLog.timestamp >= data_inicio)
    if data_fim:
        query = query.where(AuditLog.timestamp <= data_fim)
    results = session.execute(query).all()
    return {acao: count for acao, count in results}
