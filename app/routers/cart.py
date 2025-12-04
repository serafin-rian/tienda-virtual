from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
import uuid

from ..database import get_session
from ..models import Cart, CartItem, Product, User, Order, OrderItem, ShippingAddress

router = APIRouter(prefix="/cart", tags=["cart"])

# Función dummy para obtener usuario actual
def get_current_user():
    """Retorna un usuario dummy para mantener compatibilidad"""
    return User(
        id=1,
        username="anonymous",
        hashed_password="",
        role="customer"
    )

# ======================================================
# 🛒 OBTENER CARRITO DEL USUARIO ACTUAL
# ======================================================
@router.get("/", response_model=Cart)
def get_cart(
    user_id: int = 1,  # Usuario por defecto
    session: Session = Depends(get_session)
):
    """Obtiene el carrito de compras (público)"""
    # Buscar o crear carrito para el usuario
    cart = session.exec(
        select(Cart).where(Cart.user_id == user_id)
    ).first()
    
    if not cart:
        # Crear nuevo carrito si no existe
        cart = Cart(user_id=user_id)
        session.add(cart)
        session.commit()
        session.refresh(cart)
    
    return cart

# ======================================================
# ➕ AGREGAR PRODUCTO AL CARRITO
# ======================================================
@router.post("/add/{product_id}")
def add_to_cart(
    product_id: int,
    quantity: int = 1,
    user_id: int = 1,  # Usuario por defecto
    session: Session = Depends(get_session)
):
    """Agrega un producto al carrito (público)"""
    # Verificar que el producto existe
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Verificar stock disponible
    if product.quantity < quantity:
        raise HTTPException(
            status_code=400, 
            detail=f"Stock insuficiente. Solo hay {product.quantity} unidades disponibles"
        )
    
    # Obtener o crear carrito
    cart = session.exec(
        select(Cart).where(Cart.user_id == user_id)
    ).first()
    
    if not cart:
        cart = Cart(user_id=user_id)
        session.add(cart)
        session.commit()
        session.refresh(cart)
    
    # Verificar si el producto ya está en el carrito
    existing_item = session.exec(
        select(CartItem)
        .where(CartItem.cart_id == cart.id)
        .where(CartItem.product_id == product_id)
    ).first()
    
    if existing_item:
        # Actualizar cantidad si ya existe
        existing_item.quantity += quantity
        session.add(existing_item)
    else:
        # Crear nuevo item en el carrito
        cart_item = CartItem(
            cart_id=cart.id,
            product_id=product_id,
            quantity=quantity
        )
        session.add(cart_item)
    
    # Actualizar timestamp del carrito
    cart.updated_at = datetime.utcnow()
    session.add(cart)
    session.commit()
    
    return {"message": f"Producto '{product.name}' agregado al carrito"}

# ======================================================
# 🔄 ACTUALIZAR CANTIDAD DE PRODUCTO EN CARRITO
# ======================================================
@router.put("/update/{product_id}")
def update_cart_item(
    product_id: int,
    quantity: int = Query(..., ge=1, description="Nueva cantidad"),
    user_id: int = 1,  # Usuario por defecto
    session: Session = Depends(get_session)
):
    """Actualiza la cantidad de un producto en el carrito"""
    # Verificar que el producto existe
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Verificar stock disponible
    if product.quantity < quantity:
        raise HTTPException(
            status_code=400, 
            detail=f"Stock insuficiente. Solo hay {product.quantity} unidades disponibles"
        )
    
    # Buscar carrito del usuario
    cart = session.exec(
        select(Cart).where(Cart.user_id == user_id)
    ).first()
    
    if not cart:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    
    # Buscar item en el carrito
    cart_item = session.exec(
        select(CartItem)
        .where(CartItem.cart_id == cart.id)
        .where(CartItem.product_id == product_id)
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Producto no encontrado en el carrito")
    
    # Actualizar cantidad
    cart_item.quantity = quantity
    cart.updated_at = datetime.utcnow()
    
    session.add(cart_item)
    session.add(cart)
    session.commit()
    
    return {
        "message": f"Cantidad de '{product.name}' actualizada a {quantity}",
        "product_id": product_id,
        "new_quantity": quantity
    }

# ======================================================
# 🗑️ ELIMINAR PRODUCTO DEL CARRITO
# ======================================================
@router.delete("/remove/{product_id}")
def remove_from_cart(
    product_id: int,
    user_id: int = 1,  # Usuario por defecto
    session: Session = Depends(get_session)
):
    """Elimina un producto del carrito"""
    # Buscar carrito del usuario
    cart = session.exec(
        select(Cart).where(Cart.user_id == user_id)
    ).first()
    
    if not cart:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    
    # Buscar y eliminar item del carrito
    cart_item = session.exec(
        select(CartItem)
        .where(CartItem.cart_id == cart.id)
        .where(CartItem.product_id == product_id)
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Producto no encontrado en el carrito")
    
    product_name = session.get(Product, product_id).name if session.get(Product, product_id) else "Producto"
    
    session.delete(cart_item)
    cart.updated_at = datetime.utcnow()
    session.add(cart)
    session.commit()
    
    return {"message": f"'{product_name}' eliminado del carrito"}

# ======================================================
# 🗑️ VACIAR CARRITO COMPLETO
# ======================================================
@router.delete("/clear")
def clear_cart(
    user_id: int = 1,  # Usuario por defecto
    session: Session = Depends(get_session)
):
    """Elimina todos los productos del carrito"""
    # Buscar carrito del usuario
    cart = session.exec(
        select(Cart).where(Cart.user_id == user_id)
    ).first()
    
    if not cart:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    
    # Eliminar todos los items del carrito
    cart_items = session.exec(
        select(CartItem).where(CartItem.cart_id == cart.id)
    ).all()
    
    deleted_count = len(cart_items)
    
    for item in cart_items:
        session.delete(item)
    
    cart.updated_at = datetime.utcnow()
    session.add(cart)
    session.commit()
    
    return {
        "message": f"Carrito vaciado. Se eliminaron {deleted_count} productos",
        "deleted_count": deleted_count
    }

# ======================================================
# 📊 RESUMEN DEL CARRITO (MEJORADO)
# ======================================================
@router.get("/summary")
def get_cart_summary(
    user_id: int = 1,  # Usuario por defecto
    session: Session = Depends(get_session)
):
    """Obtiene un resumen detallado del carrito (público)"""
    # Buscar carrito del usuario
    cart = session.exec(
        select(Cart).where(Cart.user_id == user_id)
    ).first()
    
    if not cart:
        return {
            "total_items": 0,
            "total_amount": 0,
            "items": [],
            "cart_exists": False
        }
    
    # Obtener items del carrito con información del producto
    cart_items = session.exec(
        select(CartItem).where(CartItem.cart_id == cart.id)
    ).all()
    
    items_summary = []
    total_amount = 0
    total_items = 0
    
    for item in cart_items:
        product = session.get(Product, item.product_id)
        if product:
            item_total = product.price * item.quantity
            items_summary.append({
                "cart_item_id": item.id,
                "product_id": product.id,
                "product_name": product.name,
                "description": product.description,
                "price": product.price,
                "quantity": item.quantity,
                "subtotal": item_total,
                "image_url": product.image_url or product.image_path or "/static/no-image.png",
                "stock_available": product.quantity,
                "max_allowed": product.quantity
            })
            total_amount += item_total
            total_items += item.quantity
    
    # Obtener direcciones del usuario (para checkout)
    shipping_addresses = session.exec(
        select(ShippingAddress).where(ShippingAddress.user_id == user_id)
    ).all()
    
    # Calcular envío
    shipping_cost = 0.0
    if total_amount > 0 and total_amount < 100:
        shipping_cost = 5.0  # Envío estándar
    
    return {
        "cart_id": cart.id,
        "total_items": total_items,
        "total_amount": round(total_amount, 2),
        "subtotal": round(total_amount, 2),
        "shipping_cost": shipping_cost,
        "grand_total": round(total_amount + shipping_cost, 2),
        "items": items_summary,
        "item_count": len(items_summary),
        "shipping_addresses": [
            {
                "id": addr.id,
                "full_name": addr.full_name,
                "address_line1": addr.address_line1,
                "city": addr.city,
                "country": addr.country,
                "is_default": addr.is_default
            }
            for addr in shipping_addresses
        ],
        "last_updated": cart.updated_at,
        "cart_exists": True,
        "free_shipping_threshold": 100,
        "eligible_for_free_shipping": total_amount >= 100
    }

# ======================================================
# 💳 CHECKOUT - CREAR PEDIDO DESDE CARRITO
# ======================================================
@router.post("/checkout")
def checkout_cart(
    shipping_address_id: Optional[int] = None,
    payment_method: str = "credit_card",
    notes: Optional[str] = None,
    user_id: int = 1,  # Usuario por defecto
    session: Session = Depends(get_session)
):
    """Crea un pedido a partir del carrito actual"""
    # Obtener resumen del carrito
    cart_summary = get_cart_summary(user_id, session)
    
    if not cart_summary["cart_exists"] or len(cart_summary["items"]) == 0:
        raise HTTPException(status_code=400, detail="El carrito está vacío")
    
    # Verificar stock disponible
    out_of_stock_items = []
    for item in cart_summary["items"]:
        product = session.get(Product, item["product_id"])
        if product and product.quantity < item["quantity"]:
            out_of_stock_items.append({
                "product_name": item["product_name"],
                "requested": item["quantity"],
                "available": product.quantity
            })
    
    if out_of_stock_items:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Algunos productos no tienen stock suficiente",
                "out_of_stock_items": out_of_stock_items
            }
        )
    
    # Obtener dirección de envío
    shipping_address = None
    if shipping_address_id:
        shipping_address = session.get(ShippingAddress, shipping_address_id)
        if not shipping_address or shipping_address.user_id != user_id:
            raise HTTPException(status_code=400, detail="Dirección de envío inválida")
    
    # Si no se especifica dirección, usar la predeterminada
    if not shipping_address:
        default_address = session.exec(
            select(ShippingAddress)
            .where(ShippingAddress.user_id == user_id)
            .where(ShippingAddress.is_default == True)
            .limit(1)
        ).first()
        
        if default_address:
            shipping_address = default_address
    
    # Crear número de pedido único
    order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    # Crear la orden
    order = Order(
        user_id=user_id,
        order_number=order_number,
        total_amount=cart_summary["grand_total"],
        status="pending",
        shipping_cost=cart_summary["shipping_cost"],
        payment_method=payment_method,
        notes=notes
    )
    
    if shipping_address:
        order.shipping_address_text = f"{shipping_address.full_name}, {shipping_address.address_line1}, {shipping_address.city}, {shipping_address.country}"
    
    session.add(order)
    session.commit()
    session.refresh(order)
    
    # Crear items de la orden y actualizar stock
    for item in cart_summary["items"]:
        product = session.get(Product, item["product_id"])
        if product:
            # Crear order item
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                product_price=product.price,
                quantity=item["quantity"],
                subtotal=item["subtotal"]
            )
            session.add(order_item)
            
            # Actualizar stock del producto
            product.quantity -= item["quantity"]
            session.add(product)
    
    # Vaciar carrito después del checkout
    clear_cart(user_id, session)
    
    # Crear envío automático si requiere envío
    shipment_info = None
    if cart_summary["shipping_cost"] > 0 and shipping_address:
        from ..models import Shipment, ShippingStatus
        from datetime import datetime, timedelta
        
        # Crear envío simple
        tracking_number = f"TRK-{uuid.uuid4().hex[:10].upper()}"
        shipment = Shipment(
            order_id=order.id,
            shipping_address_id=shipping_address.id,
            tracking_number=tracking_number,
            carrier="local",
            status=ShippingStatus.PENDING,
            shipping_cost=cart_summary["shipping_cost"],
            total_cost=cart_summary["shipping_cost"],
            estimated_delivery_start=datetime.utcnow() + timedelta(days=2),
            estimated_delivery_end=datetime.utcnow() + timedelta(days=5)
        )
        session.add(shipment)
        session.commit()
        
        shipment_info = {
            "tracking_number": tracking_number,
            "estimated_delivery": shipment.estimated_delivery_start.strftime("%Y-%m-%d")
        }
    
    session.commit()
    
    return {
        "message": "¡Pedido creado exitosamente!",
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "total_amount": order.total_amount,
            "status": order.status,
            "created_at": order.created_at
        },
        "shipment": shipment_info,
        "items_count": len(cart_summary["items"]),
        "next_steps": [
            "El pedido está siendo procesado",
            "Recibirás actualizaciones por email",
            "Puedes rastrear tu envío en la sección de seguimiento"
        ]
    }

# ======================================================
# 📦 VERIFICAR DISPONIBILIDAD DE STOCK
# ======================================================
@router.get("/check-stock")
def check_stock_availability(
    user_id: int = 1,  # Usuario por defecto
    session: Session = Depends(get_session)
):
    """Verifica si todos los productos en el carrito tienen stock suficiente"""
    cart_summary = get_cart_summary(user_id, session)
    
    if not cart_summary["cart_exists"]:
        return {
            "all_in_stock": True,
            "message": "Carrito vacío",
            "details": []
        }
    
    stock_issues = []
    all_in_stock = True
    
    for item in cart_summary["items"]:
        product = session.get(Product, item["product_id"])
        if product:
            if product.quantity < item["quantity"]:
                all_in_stock = False
                stock_issues.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "requested": item["quantity"],
                    "available": product.quantity,
                    "shortage": item["quantity"] - product.quantity
                })
    
    return {
        "all_in_stock": all_in_stock,
        "message": "Todo en stock" if all_in_stock else "Hay problemas de stock",
        "details": stock_issues,
        "total_items": len(cart_summary["items"]),
        "items_with_issues": len(stock_issues)
    }