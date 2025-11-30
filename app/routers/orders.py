from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Optional
from ..database import get_session
from ..models import Order, OrderItem, User, Product
from .auth_router import get_current_user, get_admin_user
from datetime import datetime


router = APIRouter(prefix="/orders", tags=["orders"])

# ======================================================
# 📋 OBTENER MIS ÓRDENES
# ======================================================
@router.get("/my-orders")
def get_my_orders(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = Query(None, description="Filtrar por estado"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene las órdenes del usuario actual"""
    query = select(Order).where(Order.user_id == current_user.id)
    
    if status:
        query = query.where(Order.status == status)
    
    orders = session.exec(
        query.order_by(Order.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    
    return {
        "total_orders": len(orders),
        "orders": orders
    }

# ======================================================
# 🔍 OBTENER DETALLE DE UNA ORDEN
# ======================================================
@router.get("/{order_id}")
def get_order_details(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene los detalles de una orden específica"""
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    
    # Verificar que el usuario es el dueño o es admin
    if order.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para ver esta orden")
    
    # Obtener items de la orden
    order_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()
    
    return {
        "order": order,
        "items": order_items
    }

# ======================================================
# 📊 OBTENER TODAS LAS ÓRDENES (solo admin)
# ======================================================
@router.get("/")
def get_all_orders(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = Query(None, description="Filtrar por estado"),
    user_id: Optional[int] = Query(None, description="Filtrar por usuario"),
    session: Session = Depends(get_session),
    admin_user: User = Depends(get_admin_user)
):
    """Obtiene todas las órdenes (solo administradores)"""
    query = select(Order)
    
    if status:
        query = query.where(Order.status == status)
    if user_id:
        query = query.where(Order.user_id == user_id)
    
    orders = session.exec(
        query.order_by(Order.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    
    return {
        "total_orders": len(orders),
        "orders": orders
    }

# ======================================================
# ✏️ ACTUALIZAR ESTADO DE ORDEN (solo admin)
# ======================================================
@router.put("/{order_id}/status")
def update_order_status(
    order_id: int,
    new_status: str,
    session: Session = Depends(get_session),
    admin_user: User = Depends(get_admin_user)
):
    """Actualiza el estado de una orden (solo administradores)"""
    valid_statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Debe ser uno de: {', '.join(valid_statuses)}"
        )
    
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    
    old_status = order.status
    order.status = new_status
    order.updated_at = datetime.utcnow()
    
    session.add(order)
    session.commit()
    session.refresh(order)
    
    return {
        "message": f"Estado de orden {order.order_number} actualizado de '{old_status}' a '{new_status}'",
        "order": order
    }

# ======================================================
# 📈 ESTADÍSTICAS DE ÓRDENES
# ======================================================
@router.get("/stats/summary")
def get_orders_stats(
    session: Session = Depends(get_session),
    admin_user: User = Depends(get_admin_user)
):
    """Estadísticas de órdenes (solo administradores)"""
    orders = session.exec(select(Order)).all()
    
    if not orders:
        return {
            "total_orders": 0,
            "total_revenue": 0,
            "orders_by_status": {},
            "recent_orders": []
        }
    
    total_orders = len(orders)
    total_revenue = sum(order.total_amount for order in orders)
    
    # Órdenes por estado
    orders_by_status = {}
    for order in orders:
        orders_by_status[order.status] = orders_by_status.get(order.status, 0) + 1
    
    # Órdenes recientes (últimas 5)
    recent_orders = sorted(orders, key=lambda x: x.created_at, reverse=True)[:5]
    
    return {
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "average_order_value": round(total_revenue / total_orders, 2) if total_orders > 0 else 0,
        "orders_by_status": orders_by_status,
        "recent_orders": [
            {
                "order_number": order.order_number,
                "customer_id": order.user_id,
                "total_amount": order.total_amount,
                "status": order.status,
                "created_at": order.created_at
            }
            for order in recent_orders
        ]
    }