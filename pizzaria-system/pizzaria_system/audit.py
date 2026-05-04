from typing import Optional, Union

from fastapi import Request
from sqlalchemy.orm import Session

from pizzaria_system.models import AuditLog, Cliente, Funcionario


def log_audit(
    session: Session,
    current_user: Optional[Union[Cliente, Funcionario]],
    acao: str,
    tabela_afetada: str,
    registro_id: Optional[int] = None,
    dados_anteriores: Optional[dict] = None,
    dados_novos: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    """
    Registra uma ação no log de auditoria.
    """
    usuario_tipo = None
    usuario_id = None
    funcionario_id = None

    if current_user:
        if isinstance(current_user, Cliente):
            usuario_tipo = 'cliente'
            usuario_id = current_user.id
        elif isinstance(current_user, Funcionario):
            usuario_tipo = 'funcionario'
            funcionario_id = current_user.id
    else:
        usuario_tipo = 'sistema'

    log = AuditLog(
        usuario_tipo=usuario_tipo,
        usuario_id=usuario_id,
        funcionario_id=funcionario_id,
        acao=acao,
        tabela_afetada=tabela_afetada,
        registro_id=registro_id,
        dados_anteriores=dados_anteriores,
        dados_novos=dados_novos,
        ip=request.client.host if request else None,
        user_agent=request.headers.get('user-agent') if request else None,
    )
    session.add(log)
