from fastapi import APIRouter, Depends, HTTPException, Form, Query
from sqlmodel import Session, select, and_, or_
from typing import List, Optional
from datetime import datetime, timedelta
from ..database import get_session
from ..models import Product, User, AuditLog
from .auth_router import get_current_user
from ..permissions import PermissionChecker, require_admin_or_vendor


router = APIRouter(prefix="/products", tags=["products"])

# ======================================================
# 🔐 FUNCIONES HELPER PARA PERMISOS
# ======================================================
def can_create_product(user: User) -> bool:
    """Verifica si el usuario puede crear productos"""
    return user.role in ["admin", "vendor"]

def can_edit_product(user: User, product_owner_id: int) -> bool:
    """Verifica si el usuario puede editar un producto"""
    if user.role == "admin":
        return True
    if user.role == "vendor" and user.id == product_owner_id:
        return True
    return False

def can_delete_product(user: User, product_owner_id: int) -> bool:
    """Verifica si el usuario puede eliminar un producto"""
    return can_edit_product(user, product_owner_id)  # Mismas reglas que editar

# ======================================================
# 🟢 CREAR PRODUCTO (admin y vendedores)
# ======================================================
@router.post("/create")
def create_product(
    name: str = Form(...),
    description: str = Form(None),
    price: float = Form(...),
    quantity: int = Form(...),
    image_path: str = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Crea un nuevo producto (admin y vendedores)"""
    if not can_create_product(current_user):
        raise HTTPException(
            status_code=403, 
            detail="No tienes permisos para crear productos. Solo administradores y vendedores pueden crear productos."
        )

    product = Product(
        name=name,
        description=description,
        price=price,
        quantity=quantity,
        image_path=image_path,
        owner_id=current_user.id  # El producto pertenece al usuario que lo crea
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    
    return {
        "message": "Producto creado exitosamente",
        "product": product,
        "owner_role": current_user.role
    }

# ======================================================
# 🔵 LISTAR TODOS LOS PRODUCTOS (público)
# ======================================================
@router.get("/list", response_model=List[Product])
def list_products(session: Session = Depends(get_session)):
    products = session.exec(select(Product)).all()
    return products

# ======================================================
# 🟠 ACTUALIZAR PRODUCTO (admin y dueño vendedor)
# ======================================================
@router.put("/{product_id}")
def update_product(
    product_id: int,
    name: str = Form(None),
    description: str = Form(None),
    price: float = Form(None),
    quantity: int = Form(None),
    image_path: str = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Actualiza un producto (admin o vendedor dueño)"""
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Verificar permisos
    if not can_edit_product(current_user, product.owner_id):
        raise HTTPException(
            status_code=403, 
            detail="No tienes permisos para editar este producto. Solo administradores o el vendedor dueño pueden editarlo."
        )

    # Actualizar campos
    if name:
        product.name = name
    if description:
        product.description = description
    if price is not None:
        product.price = price
    if quantity is not None:
        product.quantity = quantity
    if image_path:
        product.image_path = image_path

    session.add(product)
    session.commit()
    session.refresh(product)
    
    return {
        "message": "Producto actualizado correctamente", 
        "product": product,
        "updated_by": current_user.username,
        "user_role": current_user.role
    }

# ======================================================
# 🔴 ELIMINAR PRODUCTO (admin y dueño vendedor) - CON HISTORIAL
# ======================================================
@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Elimina un producto (admin o vendedor dueño)"""
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Verificar permisos
    if not can_delete_product(current_user, product.owner_id):
        raise HTTPException(
            status_code=403, 
            detail="No tienes permisos para eliminar este producto. Solo administradores o el vendedor dueño pueden eliminarlo."
        )

    # 🔥 REGISTRAR EN HISTORIAL ANTES de eliminar
    audit_log = AuditLog(
        action="DELETE_PRODUCT",
        target_id=product_id,
        target_name=product.name,
        performed_by=current_user.username,
        details=f"Producto '{product.name}' (Precio: ${product.price}, Cantidad: {product.quantity}, Dueño: {product.owner_id}) eliminado por {current_user.username} (Rol: {current_user.role})"
    )
    session.add(audit_log)
    
    session.delete(product)
    session.commit()
    
    return {
        "message": f"Producto '{product.name}' eliminado exitosamente",
        "deleted_by": current_user.username,
        "user_role": current_user.role
    }

# ======================================================
# 🔍 BÚSQUEDA AVANZADA CON FILTROS MÚLTIPLES
# ======================================================
@router.get("/search", response_model=List[Product])
def search_products(
    name: Optional[str] = Query(None, description="Buscar por nombre (búsqueda parcial)"),
    description: Optional[str] = Query(None, description="Buscar en descripción"),
    min_price: Optional[float] = Query(None, ge=0, description="Precio mínimo"),
    max_price: Optional[float] = Query(None, ge=0, description="Precio máximo"),
    min_quantity: Optional[int] = Query(None, ge=0, description="Cantidad mínima"),
    max_quantity: Optional[int] = Query(None, ge=0, description="Cantidad máxima"),
    in_stock: Optional[bool] = Query(None, description="Solo productos con stock"),
    owner_id: Optional[int] = Query(None, description="Productos de un usuario específico"),
    created_after: Optional[str] = Query(None, description="Creados después de (YYYY-MM-DD)"),
    session: Session = Depends(get_session)
):
    """
    🔍 BÚSQUEDA AVANZADA DE PRODUCTOS
    - Búsqueda por texto, precio, cantidad, dueño, fecha
    - Combinación múltiple de filtros
    """
    query = select(Product)
    
    # 🔤 Filtros de texto
    text_filters = []
    if name:
        text_filters.append(Product.name.ilike(f"%{name}%"))
    if description:
        text_filters.append(Product.description.ilike(f"%{description}%"))
    
    if text_filters:
        query = query.where(or_(*text_filters))
    
    # 🔢 Filtros numéricos
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
    
    # 📦 Filtro de stock
    if in_stock is not None and in_stock:
        query = query.where(Product.quantity > 0)
    
    # 👤 Filtro de dueño
    if owner_id:
        query = query.where(Product.owner_id == owner_id)
    
    # 📅 Filtro de fecha
    if created_after:
        try:
            after_date = datetime.fromisoformat(created_after)
            query = query.where(Product.created_at >= after_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido para created_after")
    
    products = session.exec(query).all()
    
    return {
        "filters_applied": {
            "name": name,
            "description": description,
            "price_range": f"{min_price}-{max_price}" if min_price or max_price else None,
            "quantity_range": f"{min_quantity}-{max_quantity}" if min_quantity or max_quantity else None,
            "in_stock": in_stock,
            "owner_id": owner_id,
            "created_after": created_after
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
# 📈 ESTADÍSTICAS DE PRODUCTOS DEL VENDEDOR ACTUAL
# ======================================================
@router.get("/my-stats")
def get_my_products_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Estadísticas de los productos del usuario actual (vendedor o admin)"""
    if current_user.role not in ["admin", "vendor"]:
        raise HTTPException(
            status_code=403, 
            detail="Solo administradores y vendedores pueden ver estadísticas de productos"
        )
    
    # Filtrar productos por dueño (a menos que sea admin)
    if current_user.role == "admin":
        query = select(Product)
    else:
        query = select(Product).where(Product.owner_id == current_user.id)
    
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
    most_expensive = max(products, key=lambda p: p.price)
    cheapest = min(products, key=lambda p: p.price)
    
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "total_products": total_products,
        "total_inventory_value": round(total_value, 2),
        "average_price": round(average_price, 2),
        "low_stock_products": low_stock_products,
        "price_range": {
            "max_price": most_expensive.price,
            "min_price": cheapest.price,
            "most_expensive_product": most_expensive.name,
            "cheapest_product": cheapest.name
        },
        "products_by_category": "Por implementar",  # Futura feature
        "recently_added": [
            product.name for product in 
            sorted(products, key=lambda x: x.created_at, reverse=True)[:5]
        ]
    }

# ======================================================
# 🏪 MIS PRODUCTOS (para vendedores)
# ======================================================
@router.get("/my-products", response_model=List[Product])
def get_my_products(
    skip: int = 0,
    limit: int = 50,
    in_stock: Optional[bool] = Query(None, description="Filtrar por stock"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene los productos del usuario actual (vendedor)"""
    if current_user.role not in ["admin", "vendor"]:
        raise HTTPException(
            status_code=403, 
            detail="Solo administradores y vendedores pueden ver sus productos"
        )
    
    query = select(Product).where(Product.owner_id == current_user.id)
    
    if in_stock is not None:
        if in_stock:
            query = query.where(Product.quantity > 0)
        else:
            query = query.where(Product.quantity == 0)
    
    products = session.exec(
        query.order_by(Product.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    
    return products

# ======================================================
# 🏆 PRODUCTOS DESTACADOS
# ======================================================
@router.get("/featured")
def get_featured_products(
    category: Optional[str] = Query(None, description="Filtrar por categoría futura"),
    limit: int = Query(10, le=50, description="Límite de productos"),
    session: Session = Depends(get_session)
):
    """Obtiene productos destacados (más stock, mejor precio, etc.)"""
    query = select(Product).where(Product.quantity > 0).order_by(
        Product.quantity.desc(),
        Product.price.asc()
    ).limit(limit)
    
    featured_products = session.exec(query).all()
    
    return {
        "featured_criteria": "High stock & best price",
        "products": featured_products
    }