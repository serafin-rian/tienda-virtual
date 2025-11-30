from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List
import uuid
from datetime import datetime
from ..database import get_session
from ..models import Cart, CartItem, Product, User, Order, OrderItem
from .auth_router import get_current_user

router = APIRouter(prefix="/cart", tags=["cart"])

# ======================================================
# 🛒 OBTENER CARRITO DEL USUARIO ACTUAL
# ======================================================
@router.get("/", response_model=Cart)
def get_cart(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene el carrito de compras del usuario actual"""
    # Buscar o crear carrito para el usuario
    cart = session.exec(
        select(Cart).where(Cart.user_id == current_user.id)
    ).first()
    
    if not cart:
        # Crear nuevo carrito si no existe
        cart = Cart(user_id=current_user.id)
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
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Agrega un producto al carrito del usuario"""
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
        select(Cart).where(Cart.user_id == current_user.id)
    ).first()
    
    if not cart:
        cart = Cart(user_id=current_user.id)
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
# ➖ ACTUALIZAR CANTIDAD EN CARRITO
# ======================================================
@router.put("/update/{product_id}")
def update_cart_item(
    product_id: int,
    quantity: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Actualiza la cantidad de un producto en el carrito"""
    if quantity < 1:
        raise HTTPException(status_code=400, detail="La cantidad debe ser al menos 1")
    
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
        select(Cart).where(Cart.user_id == current_user.id)
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
    
    return {"message": f"Cantidad de '{product.name}' actualizada a {quantity}"}

# ======================================================
# 🗑️ REMOVER PRODUCTO DEL CARRITO
# ======================================================
@router.delete("/remove/{product_id}")
def remove_from_cart(
    product_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Remueve un producto del carrito"""
    # Buscar carrito del usuario
    cart = session.exec(
        select(Cart).where(Cart.user_id == current_user.id)
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
    
    # Eliminar item
    session.delete(cart_item)
    cart.updated_at = datetime.utcnow()
    session.add(cart)
    session.commit()
    
    return {"message": "Producto removido del carrito"}

# ======================================================
# 🧹 VACIAR CARRITO
# ======================================================
@router.delete("/clear")
def clear_cart(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Vacía todo el carrito del usuario"""
    # Buscar carrito del usuario
    cart = session.exec(
        select(Cart).where(Cart.user_id == current_user.id)
    ).first()
    
    if not cart:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    
    # Eliminar todos los items del carrito
    cart_items = session.exec(
        select(CartItem).where(CartItem.cart_id == cart.id)
    ).all()
    
    for item in cart_items:
        session.delete(item)
    
    cart.updated_at = datetime.utcnow()
    session.add(cart)
    session.commit()
    
    return {"message": "Carrito vaciado correctamente"}

# ======================================================
# 📊 RESUMEN DEL CARRITO
# ======================================================
@router.get("/summary")
def get_cart_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene un resumen detallado del carrito"""
    # Buscar carrito del usuario
    cart = session.exec(
        select(Cart).where(Cart.user_id == current_user.id)
    ).first()
    
    if not cart:
        return {
            "total_items": 0,
            "total_amount": 0,
            "items": []
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
                "product_id": product.id,
                "product_name": product.name,
                "price": product.price,
                "quantity": item.quantity,
                "subtotal": item_total,
                "image_url": product.image_path
            })
            total_amount += item_total
            total_items += item.quantity
    
    return {
        "total_items": total_items,
        "total_amount": round(total_amount, 2),
        "items": items_summary,
        "cart_id": cart.id,
        "last_updated": cart.updated_at
    }
# ======================================================
# 🛍️ PROCESAR CHECKOUT
# ======================================================
@router.post("/checkout")
def checkout(
    shipping_address: str = None,
    payment_method: str = "credit_card",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Procesa el checkout y crea una orden desde el carrito"""
    # Buscar carrito del usuario
    cart = session.exec(
        select(Cart).where(Cart.user_id == current_user.id)
    ).first()
    
    if not cart:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    
    # Obtener items del carrito
    cart_items = session.exec(
        select(CartItem).where(CartItem.cart_id == cart.id)
    ).all()
    
    if not cart_items:
        raise HTTPException(status_code=400, detail="El carrito está vacío")
    
    # Verificar stock y calcular total
    total_amount = 0
    order_items_data = []
    
    for cart_item in cart_items:
        product = session.get(Product, cart_item.product_id)
        if not product:
            raise HTTPException(
                status_code=404, 
                detail=f"Producto con ID {cart_item.product_id} no encontrado"
            )
        
        # Verificar stock
        if product.quantity < cart_item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente para '{product.name}'. Disponible: {product.quantity}, Solicitado: {cart_item.quantity}"
            )
        
        # Calcular subtotal
        subtotal = product.price * cart_item.quantity
        total_amount += subtotal
        
        # Preparar datos para OrderItem
        order_items_data.append({
            "product_id": product.id,
            "product_name": product.name,
            "product_price": product.price,
            "quantity": cart_item.quantity,
            "subtotal": subtotal
        })
    
    # Generar número de orden único
    order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    # Crear la orden
    order = Order(
        user_id=current_user.id,
        order_number=order_number,
        total_amount=total_amount,
        status="confirmed",
        shipping_address=shipping_address,
        payment_method=payment_method
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    
    # Crear items de la orden y actualizar stock
    for item_data in order_items_data:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item_data["product_id"],
            product_name=item_data["product_name"],
            product_price=item_data["product_price"],
            quantity=item_data["quantity"],
            subtotal=item_data["subtotal"]
        )
        session.add(order_item)
        
        # Actualizar stock del producto
        product = session.get(Product, item_data["product_id"])
        product.quantity -= item_data["quantity"]
        session.add(product)
    
    # Vaciar el carrito después del checkout
    for cart_item in cart_items:
        session.delete(cart_item)
    
    cart.updated_at = datetime.utcnow()
    session.add(cart)
    session.commit()
    
    return {
        "message": "Orden creada exitosamente",
        "order_number": order_number,
        "order_id": order.id,
        "total_amount": total_amount,
        "status": "confirmed"
    }