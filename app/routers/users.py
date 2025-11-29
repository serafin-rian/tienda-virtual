from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
from ..database import get_session
from ..models import User, AuditLog, Product
from ..auth import hash_password
from .auth_router import get_current_user

router = APIRouter(prefix="/users", tags=["users"])

# ======================================================
# 👤 CREAR USUARIO
# ======================================================
@router.post("/", response_model=User)
def create_user(user: User, session: Session = Depends(get_session)):
    # Verificar si el usuario ya existe
    db_user = session.exec(select(User).where(User.username == user.username)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe.")

    # Hashear la contraseña antes de guardar
    user.hashed_password = hash_password(user.hashed_password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

# ======================================================
# 📋 LISTAR TODOS LOS USUARIOS (solo admin)
# ======================================================
@router.get("/", response_model=List[User])
def list_users(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver esta lista."
        )

    users = session.exec(select(User)).all()
    return users

# ======================================================
# ✏️ ACTUALIZAR USUARIO (solo admin)
# ======================================================
@router.put("/{user_id}", response_model=User)
def update_user(
    user_id: int,
    updated_user: User,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Solo los administradores pueden editar usuarios
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para editar usuarios")

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

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
# 🗑️ ELIMINAR USUARIO (solo admin) - CON HISTORIAL
# ======================================================
@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Solo los administradores pueden eliminar usuarios
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para eliminar usuarios")

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # 🔥 REGISTRAR EN HISTORIAL ANTES de eliminar
    audit_log = AuditLog(
        action="DELETE_USER",
        target_id=user_id,
        target_name=user.username,
        performed_by=current_user.username,
        details=f"Usuario '{user.username}' (Rol: {user.role}) eliminado por {current_user.username}. Productos asociados: {len(user.products)}"
    )
    session.add(audit_log)
    
    session.delete(user)
    session.commit()
    return {"message": f"Usuario '{user.username}' eliminado correctamente"}

# ======================================================
# 🔍 BUSCAR USUARIOS (solo admin)
# ======================================================
@router.get("/search", response_model=List[User])
def search_users(
    username: Optional[str] = None,
    role: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Busca usuarios por nombre o rol (solo admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para buscar usuarios")
    
    query = select(User)
    
    if username:
        query = query.where(User.username.ilike(f"%{username}%"))
    if role:
        query = query.where(User.role == role)
    
    users = session.exec(query).all()
    return users

# ======================================================
# 📊 ESTADÍSTICAS DE USUARIOS (solo admin)
# ======================================================
@router.get("/stats")
def get_users_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Estadísticas de usuarios (solo admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para ver estadísticas")
    
    users = session.exec(select(User)).all()
    
    total_users = len(users)
    admin_count = sum(1 for user in users if user.role == "admin")
    client_count = sum(1 for user in users if user.role == "client")
    
    # Usuarios con productos
    users_with_products = sum(1 for user in users if len(user.products) > 0)
    total_products = sum(len(user.products) for user in users)
    
    # Usuario más reciente
    latest_user = max(users, key=lambda u: u.created_at) if users else None
    
    return {
        "total_users": total_users,
        "admin_users": admin_count,
        "client_users": client_count,
        "users_with_products": users_with_products,
        "total_products": total_products,
        "average_products_per_user": round(total_products / total_users, 2) if total_users > 0 else 0,
        "latest_user": {
            "username": latest_user.username if latest_user else None,
            "created_at": latest_user.created_at if latest_user else None
        }
    }

# ======================================================
# 🛍️ VER PRODUCTOS DE UN USUARIO ESPECÍFICO
# ======================================================
@router.get("/{user_id}/products", response_model=List[Product])
def get_user_products(
    user_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene todos los productos de un usuario específico"""
    # Verificar que el usuario existe
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Solo admin puede ver productos de otros usuarios, usuarios normales solo los suyos
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=403, 
            detail="No tienes permisos para ver productos de otros usuarios"
        )
    
    return user.products

# ======================================================
# 👤 INFORMACIÓN DETALLADA DE USUARIO
# ======================================================
@router.get("/{user_id}/details")
def get_user_details(
    user_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene información detallada de un usuario"""
    # Verificar permisos
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="No tienes permisos para ver esta información")
    
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