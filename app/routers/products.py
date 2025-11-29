from fastapi import APIRouter, Depends, HTTPException, Form, Query
from sqlmodel import Session, select, and_, or_
from typing import List, Optional
from datetime import datetime, timedelta
from ..database import get_session
from ..models import Product, User, AuditLog
from .auth_router import get_current_user

router = APIRouter(prefix="/products", tags=["products"])

# ======================================================
# 🟢 Crear producto (solo admin)
# ======================================================
@router.post("/create")
def create_product(
    name: str = Form(...),
    description: str = Form(None),
    price: float = Form(...),
    quantity: int = Form(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden crear productos")

    product = Product(
        name=name,
        description=description,
        price=price,
        quantity=quantity,
        owner_id=current_user.id
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    return {"message": "Producto creado exitosamente", "product": product}

# ======================================================
# 🔵 Listar todos los productos (clientes y admin)
# ======================================================
@router.get("/list", response_model=List[Product])
def list_products(session: Session = Depends(get_session)):
    products = session.exec(select(Product)).all()
    return products

# ======================================================
# 🟠 Actualizar producto (solo admin)
# ======================================================
@router.put("/{product_id}")
def update_product(
    product_id: int,
    name: str = Form(None),
    description: str = Form(None),
    price: float = Form(None),
    quantity: int = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden actualizar productos")

    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if name:
        product.name = name
    if description:
        product.description = description
    if price is not None:
        product.price = price
    if quantity is not None:
        product.quantity = quantity

    session.add(product)
    session.commit()
    session.refresh(product)
    return {"message": "Producto actualizado correctamente", "product": product}

# ======================================================
# 🔴 Eliminar producto (solo admin) - CON HISTORIAL
# ======================================================
@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden eliminar productos")

    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # 🔥 REGISTRAR EN HISTORIAL ANTES de eliminar
    audit_log = AuditLog(
        action="DELETE_PRODUCT",
        target_id=product_id,
        target_name=product.name,
        performed_by=current_user.username,
        details=f"Producto '{product.name}' (Precio: ${product.price}, Cantidad: {product.quantity}) eliminado por {current_user.username}"
    )
    session.add(audit_log)
    
    session.delete(product)
    session.commit()
    return {"message": f"Producto '{product.name}' eliminado exitosamente"}

# ======================================================
# 🔍 BÚSQUEDA AVANZADA CON FILTROS MÚLTIPLES
# ======================================================
@router.get("/search", response_model=List[Product])
def search_products(
    # Filtros de texto
    name: Optional[str] = Query(None, description="Buscar por nombre (búsqueda parcial)"),
    description: Optional[str] = Query(None, description="Buscar en descripción"),
    
    # Filtros numéricos
    min_price: Optional[float] = Query(None, ge=0, description="Precio mínimo"),
    max_price: Optional[float] = Query(None, ge=0, description="Precio máximo"),
    min_quantity: Optional[int] = Query(None, ge=0, description="Cantidad mínima"),
    max_quantity: Optional[int] = Query(None, ge=0, description="Cantidad máxima"),
    
    # Filtros de existencia
    in_stock: Optional[bool] = Query(None, description="Solo productos con stock"),
    has_description: Optional[bool] = Query(None, description="Solo productos con descripción"),
    
    # Filtros de dueño
    owner_id: Optional[int] = Query(None, description="Productos de un usuario específico"),
    owner_username: Optional[str] = Query(None, description="Productos por nombre de dueño"),
    
    # Filtros de fecha
    created_after: Optional[str] = Query(None, description="Creados después de (YYYY-MM-DD)"),
    created_before: Optional[str] = Query(None, description="Creados antes de (YYYY-MM-DD)"),
    
    session: Session = Depends(get_session)
):
    """
    🔍 BÚSQUEDA AVANZADA DE PRODUCTOS
    - Búsqueda por texto, precio, cantidad, dueño, fecha
    - Combinación múltiple de filtros
    - Búsqueda parcial en nombre y descripción
    """
    query = select(Product)
    
    # 🔤 Filtros de texto (búsqueda parcial)
    text_filters = []
    if name:
        text_filters.append(Product.name.ilike(f"%{name}%"))
    if description:
        text_filters.append(Product.description.ilike(f"%{description}%"))
    
    if text_filters:
        query = query.where(or_(*text_filters))
    
    # 🔢 Filtros numéricos (rangos)
    numeric_filters = []
    if min_price is not None:
        numeric_filters.append(Product.price >= min_price)
    if max_price is not None:
        numeric_filters.append(Product.price <= max_price)
    if min_quantity is not None:
        numeric_filters.append(Product.quantity >= min_quantity)
    if max_quantity is not None:
        numeric_filters.append(Product.quantity <= max_quantity)
    
    if numeric_filters:
        query = query.where(and_(*numeric_filters))
    
    # 📦 Filtros de existencia
    if in_stock is not None:
        if in_stock:
            query = query.where(Product.quantity > 0)
        else:
            query = query.where(Product.quantity == 0)
    
    if has_description is not None:
        if has_description:
            query = query.where(Product.description.isnot(None))
        else:
            query = query.where(Product.description.is_(None))
    
    # 👤 Filtros de dueño
    if owner_id:
        query = query.where(Product.owner_id == owner_id)
    
    if owner_username:
        # Subconsulta para buscar por nombre de usuario del dueño
        subquery = select(User.id).where(User.username.ilike(f"%{owner_username}%"))
        query = query.where(Product.owner_id.in_(subquery))
    
    # 📅 Filtros de fecha
    date_filters = []
    if created_after:
        try:
            after_date = datetime.fromisoformat(created_after)
            date_filters.append(Product.created_at >= after_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido para created_after")
    
    if created_before:
        try:
            before_date = datetime.fromisoformat(created_before)
            date_filters.append(Product.created_at <= before_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido para created_before")
    
    if date_filters:
        query = query.where(and_(*date_filters))
    
    products = session.exec(query).all()
    
    return {
        "filters_applied": {
            "name": name,
            "description": description,
            "price_range": f"{min_price}-{max_price}" if min_price or max_price else None,
            "quantity_range": f"{min_quantity}-{max_quantity}" if min_quantity or max_quantity else None,
            "in_stock": in_stock,
            "has_description": has_description,
            "owner_id": owner_id,
            "owner_username": owner_username,
            "date_range": f"{created_after} to {created_before}" if created_after or created_before else None
        },
        "results_count": len(products),
        "products": products
    }

# ======================================================
# 📊 LISTAR PRODUCTOS CON PAGINACIÓN Y ORDENAMIENTO
# ======================================================
@router.get("/all", response_model=List[Product])
def get_all_products(
    skip: int = 0,
    limit: int = 100,
    sort_by: str = Query("name", description="Campo para ordenar: name, price, quantity, created_at"),
    order: str = Query("asc", description="Orden: asc o desc"),
    session: Session = Depends(get_session)
):
    """Lista productos con paginación y ordenamiento"""
    valid_sort_fields = ["name", "price", "quantity", "created_at"]
    if sort_by not in valid_sort_fields:
        sort_by = "name"
    
    # Construir la consulta con ordenamiento
    order_by_field = getattr(Product, sort_by)
    if order == "desc":
        order_by_field = order_by_field.desc()
    
    query = select(Product).order_by(order_by_field).offset(skip).limit(limit)
    products = session.exec(query).all()
    return products

# ======================================================
# 🔍 VER INFORMACIÓN DEL DUEÑO DE UN PRODUCTO
# ======================================================
@router.get("/{product_id}/owner")
def get_product_owner(
    product_id: int,
    session: Session = Depends(get_session)
):
    """Obtiene información del usuario dueño de un producto"""
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    if not product.owner:
        return {"message": "Este producto no tiene dueño asignado"}
    
    return {
        "owner_id": product.owner.id,
        "owner_username": product.owner.username,
        "owner_role": product.owner.role,
        "owner_created_at": product.owner.created_at
    }

# ======================================================
# 📈 ESTADÍSTICAS DE PRODUCTOS CON FILTROS
# ======================================================
@router.get("/stats/summary")
def get_products_stats(
    owner_id: Optional[int] = Query(None, description="Filtrar por dueño"),
    min_price: Optional[float] = Query(None, description="Precio mínimo"),
    max_price: Optional[float] = Query(None, description="Precio máximo"),
    session: Session = Depends(get_session)
):
    """Estadísticas generales de productos con filtros"""
    query = select(Product)
    
    # Aplicar filtros si se proporcionan
    if owner_id:
        query = query.where(Product.owner_id == owner_id)
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)
    
    products = session.exec(query).all()
    
    if not products:
        return {
            "total_products": 0,
            "total_value": 0,
            "average_price": 0,
            "low_stock_products": 0
        }
    
    total_products = len(products)
    total_value = sum(product.price * product.quantity for product in products)
    average_price = total_value / total_products if total_products > 0 else 0
    low_stock_products = sum(1 for product in products if product.quantity < 10)
    
    # Producto más caro y más barato
    if products:
        most_expensive = max(products, key=lambda p: p.price)
        cheapest = min(products, key=lambda p: p.price)
    else:
        most_expensive = cheapest = None
    
    return {
        "total_products": total_products,
        "total_value": round(total_value, 2),
        "average_price": round(average_price, 2),
        "low_stock_products": low_stock_products,
        "products_by_owner": len(set(product.owner_id for product in products if product.owner_id)),
        "price_range": {
            "max_price": most_expensive.price if most_expensive else 0,
            "min_price": cheapest.price if cheapest else 0,
            "most_expensive_product": most_expensive.name if most_expensive else None,
            "cheapest_product": cheapest.name if cheapest else None
        }
    }

# ======================================================
# 🏪 PRODUCTOS DESTACADOS
# ======================================================
@router.get("/featured")
def get_featured_products(
    category: Optional[str] = Query(None, description="Filtrar por categoría futura"),
    limit: int = Query(10, le=50, description="Límite de productos"),
    session: Session = Depends(get_session)
):
    """Obtiene productos destacados (más stock, mejor precio, etc.)"""
    
    # Productos con mejor relación precio/cantidad
    query = select(Product).where(Product.quantity > 0).order_by(
        Product.quantity.desc(),
        Product.price.asc()
    ).limit(limit)
    
    featured_products = session.exec(query).all()
    
    return {
        "featured_criteria": "High stock & best price",
        "products": featured_products
    }