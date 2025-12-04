from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
from ..database import get_session
from ..models import User, AuditLog, Product
from ..auth import hash_password

router = APIRouter(prefix="/users", tags=["users"])

# ======================================================
# 👤 CREAR USUARIO (público)
# ======================================================
@router.post("/", response_model=User)
def create_user(user: User, session: Session = Depends(get_session)):
    # Verificar si el usuario ya existe
    db_user = session.exec(select(User).where(User.username == user.username)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe.")

    # Validar rol
    valid_roles = ["admin", "vendor", "customer"]
    if user.role not in valid_roles:
        raise HTTPException(
            status_code=400, 
            detail=f"Rol inválido. Debe ser uno de: {', '.join(valid_roles)}"
        )

    # Hashear la contraseña antes de guardar
    user.hashed_password = hash_password(user.hashed_password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

# ======================================================
# 📋 LISTAR TODOS LOS USUARIOS (público)
# ======================================================
@router.get("/", response_model=List[User])
def list_users(session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()
    return users

# ======================================================
# ✏️ ACTUALIZAR USUARIO (público)
# ======================================================
@router.put("/{user_id}", response_model=User)
def update_user(
    user_id: int,
    updated_user: User,
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Validar rol si se está actualizando
    if updated_user.role:
        valid_roles = ["admin", "vendor", "customer"]
        if updated_user.role not in valid_roles:
            raise HTTPException(
                status_code=400, 
                detail=f"Rol inválido. Debe ser uno de: {', '.join(valid_roles)}"
            )

    # Actualizamos los campos básicos
    user.username = updated_user.username
    user.role = updated_user.role

    # Solo actualiza contraseña si se pasa una nueva
    if updated_user.hashed_password:
        user.hashed_password = hash_password(updated_user.hashed_password)

    session.add(user)
    session.commit()
    session.refresh(user)
    return user

# ======================================================
# 🗑️ ELIMINAR USUARIO (público)
# ======================================================
@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Registrar en historial
    audit_log = AuditLog(
        action="DELETE_USER",
        target_id=user_id,
        target_name=user.username,
        performed_by="system",
        details=f"Usuario '{user.username}' eliminado sin autenticación"
    )
    session.add(audit_log)
    
    session.delete(user)
    session.commit()
    return {"message": f"Usuario '{user.username}' eliminado correctamente"}

# ======================================================
# 🔍 BUSCAR USUARIOS (público)
# ======================================================
@router.get("/search", response_model=List[User])
def search_users(
    username: Optional[str] = None,
    role: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Busca usuarios por nombre o rol (público)"""
    query = select(User)
    
    if username:
        query = query.where(User.username.ilike(f"%{username}%"))
    if role:
        valid_roles = ["admin", "vendor", "customer"]
        if role not in valid_roles:
            raise HTTPException(
                status_code=400, 
                detail=f"Rol inválido. Debe ser uno de: {', '.join(valid_roles)}"
            )
        query = query.where(User.role == role)
    
    users = session.exec(query).all()
    return users

# ======================================================
# 📊 ESTADÍSTICAS DE USUARIOS (público)
# ======================================================
@router.get("/stats")
def get_users_stats(session: Session = Depends(get_session)):
    """Estadísticas de usuarios (público)"""
    users = session.exec(select(User)).all()
    
    total_users = len(users)
    admin_count = sum(1 for user in users if user.role == "admin")
    vendor_count = sum(1 for user in users if user.role == "vendor")
    customer_count = sum(1 for user in users if user.role == "customer")
    
    # Usuarios con productos
    users_with_products = sum(1 for user in users if len(user.products) > 0)
    total_products = sum(len(user.products) for user in users)
    
    # Usuario más reciente
    latest_user = max(users, key=lambda u: u.created_at) if users else None
    
    return {
        "total_users": total_users,
        "admin_users": admin_count,
        "vendor_users": vendor_count,
        "customer_users": customer_count,
        "users_with_products": users_with_products,
        "total_products": total_products,
        "average_products_per_user": round(total_products / total_users, 2) if total_users > 0 else 0,
        "latest_user": {
            "username": latest_user.username if latest_user else None,
            "created_at": latest_user.created_at if latest_user else None,
            "role": latest_user.role if latest_user else None
        },
        "roles_distribution": {
            "admin": f"{(admin_count/total_users)*100:.1f}%" if total_users > 0 else "0%",
            "vendor": f"{(vendor_count/total_users)*100:.1f}%" if total_users > 0 else "0%",
            "customer": f"{(customer_count/total_users)*100:.1f}%" if total_users > 0 else "0%"
        }
    }

# ======================================================
# 🛍️ VER PRODUCTOS DE UN USUARIO ESPECÍFICO (público)
# ======================================================
@router.get("/{user_id}/products", response_model=List[Product])
def get_user_products(
    user_id: int,
    session: Session = Depends(get_session)
):
    """Obtiene todos los productos de un usuario específico (público)"""
    # Verificar que el usuario existe
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return user.products

# ======================================================
# 👤 INFORMACIÓN DETALLADA DE USUARIO (público)
# ======================================================
@router.get("/{user_id}/details")
def get_user_details(
    user_id: int,
    session: Session = Depends(get_session)
):
    """Obtiene información detallada de un usuario (público)"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return {
        "user_info": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "is_superuser": user.is_superuser,
            "created_at": user.created_at
        },
        "products_info": {
            "total_products": len(user.products),
            "products": [
                {
                    "id": product.id,
                    "name": product.name,
                    "price": product.price,
                    "quantity": product.quantity
                } for product in user.products
            ]
        },
        "stats": {
            "total_inventory_value": sum(product.price * product.quantity for product in user.products),
            "average_product_price": sum(product.price for product in user.products) / len(user.products) if user.products else 0
        }
    }

# ======================================================
# 🔄 CAMBIAR ROL DE USUARIO (público)
# ======================================================
@router.patch("/{user_id}/role")
def change_user_role(
    user_id: int,
    new_role: str,
    session: Session = Depends(get_session)
):
    """Cambia el rol de un usuario (público)"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Validar nuevo rol
    valid_roles = ["admin", "vendor", "customer"]
    if new_role not in valid_roles:
        raise HTTPException(
            status_code=400, 
            detail=f"Rol inválido. Debe ser uno de: {', '.join(valid_roles)}"
        )
    
    old_role = user.role
    user.role = new_role
    session.add(user)
    session.commit()
    
    return {
        "message": f"Rol de usuario '{user.username}' cambiado de '{old_role}' a '{new_role}'",
        "user": user
    }