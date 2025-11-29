from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime, timedelta
from ..database import get_session
from ..models import AuditLog, User
from .auth_router import get_current_user, get_admin_user

router = APIRouter(prefix="/audit", tags=["audit"])

# ======================================================
# 📜 OBTENER TODO EL HISTORIAL (solo admin)
# ======================================================
@router.get("/history", response_model=List[AuditLog])
def get_audit_history(
    skip: int = 0,
    limit: int = 100,
    action: Optional[str] = None,
    performed_by: Optional[str] = None,
    days: Optional[int] = Query(None, description="Filtrar por últimos X días"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_admin_user)  # Solo admin
):
    """Obtiene el historial completo de eliminaciones (solo administradores)"""
    query = select(AuditLog)
    
    # Aplicar filtros
    if action:
        query = query.where(AuditLog.action == action)
    if performed_by:
        query = query.where(AuditLog.performed_by.ilike(f"%{performed_by}%"))
    if days:
        start_date = datetime.utcnow() - timedelta(days=days)
        query = query.where(AuditLog.performed_at >= start_date)
    
    # Ordenar por fecha más reciente primero y aplicar paginación
    query = query.order_by(AuditLog.performed_at.desc()).offset(skip).limit(limit)
    
    logs = session.exec(query).all()
    return logs

# ======================================================
# 🔍 BUSCAR EN EL HISTORIAL (solo admin)
# ======================================================
@router.get("/search")
def search_audit_logs(
    target_name: Optional[str] = None,
    action: Optional[str] = None,
    performed_by: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_admin_user)  # Solo admin
):
    """Búsqueda avanzada en el historial de auditoría"""
    query = select(AuditLog)
    
    # Aplicar filtros de búsqueda
    if target_name:
        query = query.where(AuditLog.target_name.ilike(f"%{target_name}%"))
    if action:
        query = query.where(AuditLog.action == action)
    if performed_by:
        query = query.where(AuditLog.performed_by.ilike(f"%{performed_by}%"))
    if start_date:
        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.where(AuditLog.performed_at >= start)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inicial inválido")
    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.where(AuditLog.performed_at <= end)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha final inválido")
    
    logs = session.exec(query.order_by(AuditLog.performed_at.desc())).all()
    return logs

# ======================================================
# 📊 ESTADÍSTICAS DEL HISTORIAL (solo admin)
# ======================================================
@router.get("/stats")
def get_audit_stats(
    days: Optional[int] = Query(30, description="Estadísticas de últimos X días"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_admin_user)  # Solo admin
):
    """Estadísticas del historial de eliminaciones"""
    # Calcular fecha de inicio
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Consulta base
    query = select(AuditLog).where(AuditLog.performed_at >= start_date)
    logs = session.exec(query).all()
    
    # Calcular estadísticas
    total_actions = len(logs)
    actions_by_type = {}
    actions_by_user = {}
    
    for log in logs:
        # Conteo por tipo de acción
        actions_by_type[log.action] = actions_by_type.get(log.action, 0) + 1
        # Conteo por usuario
        actions_by_user[log.performed_by] = actions_by_user.get(log.performed_by, 0) + 1
    
    # Usuarios más activos (top 5)
    top_users = sorted(actions_by_user.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Acciones recientes (últimas 10)
    recent_actions = [
        {
            "action": log.action,
            "target_name": log.target_name,
            "performed_by": log.performed_by,
            "performed_at": log.performed_at,
            "details": log.details
        }
        for log in sorted(logs, key=lambda x: x.performed_at, reverse=True)[:10]
    ]
    
    return {
        "period": f"Últimos {days} días",
        "total_actions": total_actions,
        "actions_by_type": actions_by_type,
        "top_users": top_users,
        "recent_actions": recent_actions
    }

# ======================================================
# 📋 OBTENER ACCIONES POR USUARIO (solo admin)
# ======================================================
@router.get("/user/{username}")
def get_user_actions(
    username: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_admin_user)  # Solo admin
):
    """Obtiene todas las acciones realizadas por un usuario específico"""
    # Verificar que el usuario existe
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    logs = session.exec(
        select(AuditLog)
        .where(AuditLog.performed_by == username)
        .order_by(AuditLog.performed_at.desc())
    ).all()
    
    return {
        "username": username,
        "total_actions": len(logs),
        "actions": logs
    }

# ======================================================
# 🗑️ ELIMINAR REGISTROS ANTIGUOS (solo super admin)
# ======================================================
@router.delete("/cleanup")
def cleanup_old_logs(
    days: int = Query(365, description="Eliminar registros más antiguos que X días"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_admin_user)  # Solo admin
):
    """Elimina registros de auditoría antiguos (solo super administradores)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, 
            detail="Se requieren permisos de super administrador"
        )
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Encontrar y eliminar registros antiguos
    old_logs = session.exec(
        select(AuditLog).where(AuditLog.performed_at < cutoff_date)
    ).all()
    
    deleted_count = len(old_logs)
    
    for log in old_logs:
        session.delete(log)
    
    session.commit()
    
    return {
        "message": f"Se eliminaron {deleted_count} registros de auditoría antiguos",
        "cutoff_date": cutoff_date,
        "deleted_count": deleted_count
    }

# ======================================================
# 📄 OBTENER DETALLES DE UN REGISTRO ESPECÍFICO
# ======================================================
@router.get("/{log_id}")
def get_audit_log_details(
    log_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_admin_user)  # Solo admin
):
    """Obtiene los detalles completos de un registro de auditoría específico"""
    log = session.get(AuditLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Registro de auditoría no encontrado")
    
    return log