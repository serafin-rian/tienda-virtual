from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from ..database import get_session
from ..models import Order, OrderItem, User, Product
from .auth_router import get_current_user
from ..permissions import PermissionChecker, require_admin, require_admin_or_vendor  # ✅ Nuevos imports

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
    
    # ✅ Usar PermissionChecker para verificar permisos
    PermissionChecker.check_order_view(current_user, order)
    
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
@require_admin  # ✅ Usar decorador
def get_all_orders(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = Query(None, description="Filtrar por estado"),
    user_id: Optional[int] = Query(None, description="Filtrar por usuario"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
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
@require_admin  # ✅ Usar decorador
def update_order_status(
    order_id: int,
    new_status: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
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
# 📈 ESTADÍSTICAS DE ÓRDENES (admin y vendedores)
# ======================================================
@router.get("/stats/summary")
@require_admin_or_vendor  # ✅ Usar decorador
def get_orders_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Estadísticas de órdenes (admin y vendedores)"""
    orders = session.exec(select(Order)).all()
    
    # Si es vendedor, filtrar solo órdenes con sus productos
    if current_user.role == "vendor":
        vendor_orders = []
        for order in orders:
            order_items = session.exec(
                select(OrderItem).where(OrderItem.order_id == order.id)
            ).all()
            
            # Verificar si la orden contiene productos del vendedor
            for item in order_items:
                product = session.get(Product, item.product_id)
                if product and product.owner_id == current_user.id:
                    vendor_orders.append(order)
                    break
        
        orders = vendor_orders
    
    if not orders:
        return {
            "user_role": current_user.role,
            "total_orders": 0,
            "total_revenue": 0,
            "orders_by_status": {},
            "recent_orders": []
        }
    
    total_orders = len(orders)
    
    # Calcular revenue basado en el rol
    if current_user.role == "admin":
        total_revenue = sum(order.total_amount for order in orders)
    else:  # vendor
        total_revenue = 0
        for order in orders:
            order_items = session.exec(
                select(OrderItem).where(OrderItem.order_id == order.id)
            ).all()
            for item in order_items:
                product = session.get(Product, item.product_id)
                if product and product.owner_id == current_user.id:
                    total_revenue += item.subtotal
    
    # Órdenes por estado
    orders_by_status = {}
    for order in orders:
        orders_by_status[order.status] = orders_by_status.get(order.status, 0) + 1
    
    # Órdenes recientes (últimas 5)
    recent_orders = sorted(orders, key=lambda x: x.created_at, reverse=True)[:5]
    
    return {
        "user_role": current_user.role,
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

# ======================================================
# 🗑️ CANCELAR ORDEN (usuario o admin)
# ======================================================
@router.put("/{order_id}/cancel")
def cancel_order(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Cancela una orden (usuario dueño o admin)"""
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    
    # Verificar que la orden se puede cancelar
    if order.status not in ["pending", "confirmed"]:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede cancelar una orden en estado '{order.status}'. Solo se pueden cancelar órdenes en estado 'pending' o 'confirmed'."
        )
    
    # Verificar permisos
    if current_user.role != "admin" and order.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para cancelar esta orden"
        )
    
    # Actualizar stock si la orden estaba confirmada
    if order.status == "confirmed":
        order_items = session.exec(
            select(OrderItem).where(OrderItem.order_id == order_id)
        ).all()
        
        for item in order_items:
            product = session.get(Product, item.product_id)
            if product:
                product.quantity += item.quantity
                session.add(product)
    
    # Cambiar estado
    old_status = order.status
    order.status = "cancelled"
    order.updated_at = datetime.utcnow()
    
    session.add(order)
    session.commit()
    
    return {
        "message": f"Orden {order.order_number} cancelada exitosamente (estado anterior: '{old_status}')",
        "order": order
    }

# ======================================================
# 🔄 REORDENAR (crear nueva orden basada en una anterior)
# ======================================================
@router.post("/{order_id}/reorder")
def reorder(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Crea una nueva orden basada en una orden anterior"""
    original_order = session.get(Order, order_id)
    if not original_order:
        raise HTTPException(status_code=404, detail="Orden original no encontrada")
    
    # ✅ Verificar permisos
    PermissionChecker.check_order_view(current_user, original_order)
    
    # Obtener items de la orden original
    original_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()
    
    if not original_items:
        raise HTTPException(status_code=400, detail="La orden original no tiene items")
    
    # Verificar stock actual
    unavailable_products = []
    total_amount = 0
    new_order_items = []
    
    for item in original_items:
        product = session.get(Product, item.product_id)
        if not product:
            unavailable_products.append(f"Producto ID {item.product_id} ya no existe")
            continue
        
        if product.quantity < item.quantity:
            unavailable_products.append(
                f"'{product.name}': Stock insuficiente. Disponible: {product.quantity}, Necesario: {item.quantity}"
            )
        else:
            subtotal = product.price * item.quantity
            total_amount += subtotal
            new_order_items.append({
                "product": product,
                "quantity": item.quantity,
                "subtotal": subtotal
            })
    
    if unavailable_products:
        return {
            "message": "Algunos productos no están disponibles",
            "unavailable_products": unavailable_products,
            "can_reorder": False
        }
    
    # Crear nueva orden
    import uuid
    new_order_number = f"RE-{uuid.uuid4().hex[:8].upper()}"
    
    new_order = Order(
        user_id=current_user.id,
        order_number=new_order_number,
        total_amount=total_amount,
        status="confirmed",
        shipping_address=original_order.shipping_address,
        payment_method=original_order.payment_method
    )
    session.add(new_order)
    session.commit()
    session.refresh(new_order)
    
    # Crear items y actualizar stock
    for item_data in new_order_items:
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=item_data["product"].id,
            product_name=item_data["product"].name,
            product_price=item_data["product"].price,
            quantity=item_data["quantity"],
            subtotal=item_data["subtotal"]
        )
        session.add(order_item)
        
        # Actualizar stock
        item_data["product"].quantity -= item_data["quantity"]
        session.add(item_data["product"])
    
    session.commit()
    
    return {
        "message": "Orden recreada exitosamente",
        "original_order": original_order.order_number,
        "new_order": new_order.order_number,
        "new_order_id": new_order.id,
        "total_amount": total_amount,
        "reordered_items": len(new_order_items)
    }