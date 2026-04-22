# routers/audit_log.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from datetime import datetime
from http import HTTPStatus

from pizzaria_system.database import get_session
from pizzaria_system.models import AuditLog, Funcionario
from pizzaria_system.schemas import (
    AuditLogResponse,
    MessageResponse,
    AuditLogFilter
)

router = APIRouter(prefix='/audit-logs', tags=['auditoria'])

# ---------- UTILITÁRIOS ----------
def _verificar_admin(funcionario_id: int, session: Session) -> None:
    """Verifica se o funcionário é admin. Por enquanto, apenas se id existe e cargo admin.
       Em produção, use token JWT com role."""
    # Simulação: recebemos um funcionario_id via query ou header.
    # Idealmente, extrair do token JWT.
    if funcionario_id:
        func = session.get(Funcionario, funcionario_id)
        if not func or func.cargo not in ['admin', 'gerente']:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Acesso negado. Apenas administradores podem visualizar logs de auditoria."
            )
    else:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Identificação de funcionário necessária."
        )

# ---------- ENDPOINTS ----------
@router.get('/', response_model=List[AuditLogResponse])
def listar_logs(
    session: Session = Depends(get_session),
    usuario_tipo: Optional[str] = Query(None, description="cliente, funcionario, sistema"),
    usuario_id: Optional[int] = None,
    funcionario_id: Optional[int] = None,
    acao: Optional[str] = None,
    tabela_afetada: Optional[str] = None,
    registro_id: Optional[int] = None,
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
    limite: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    # Em produção, obter funcionario_id do token
    admin_funcionario_id: int = Query(..., description="ID do funcionário admin autenticado")
):
    """
    Lista logs de auditoria com filtros e paginação.
    Acesso restrito a administradores.
    """
    _verificar_admin(admin_funcionario_id, session)

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

    query = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limite)
    logs = session.scalars(query).all()
    return logs


@router.get('/{log_id}', response_model=AuditLogResponse)
def obter_log(
    log_id: int,
    session: Session = Depends(get_session),
    admin_funcionario_id: int = Query(..., description="ID do funcionário admin autenticado")
):
    """Retorna um log específico."""
    _verificar_admin(admin_funcionario_id, session)
    log = session.get(AuditLog, log_id)
    if not log:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Log não encontrado.")
    return log


@router.get('/acoes/disponiveis', response_model=List[str])
def listar_acoes_disponiveis(
    session: Session = Depends(get_session),
    admin_funcionario_id: int = Query(..., description="ID do funcionário admin autenticado")
):
    """Retorna lista de ações distintas registradas nos logs (para filtro)."""
    _verificar_admin(admin_funcionario_id, session)
    result = session.scalars(select(AuditLog.acao).distinct()).all()
    return result


@router.get('/tabelas/disponiveis', response_model=List[str])
def listar_tabelas_afetadas(
    session: Session = Depends(get_session),
    admin_funcionario_id: int = Query(..., description="ID do funcionário admin autenticado")
):
    """Retorna lista de tabelas afetadas distintas (para filtro)."""
    _verificar_admin(admin_funcionario_id, session)
    result = session.scalars(select(AuditLog.tabela_afetada).distinct()).all()
    # Remove None se houver
    return [r for r in result if r is not None]


# Opcional: endpoint para estatísticas de logs (por ação, por dia, etc.)
@router.get('/estatisticas/por-acao')
def estatisticas_por_acao(
    session: Session = Depends(get_session),
    admin_funcionario_id: int = Query(..., description="ID do funcionário admin autenticado")
):
    _verificar_admin(admin_funcionario_id, session)
    query = select(AuditLog.acao, func.count(AuditLog.id)).group_by(AuditLog.acao)
    results = session.execute(query).all()
    return {acao: count for acao, count in results}