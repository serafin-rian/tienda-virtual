# app/routers/auth_router.py
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlmodel import Session, select  
from ..database import get_session
from ..models import User
from ..auth import hash_password
from typing import Optional  

router = APIRouter(prefix="/auth", tags=["auth"])

# ======================================================
# 👤 CREAR USUARIO (público)
# ======================================================
@router.post("/register")
def register_user(
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("customer"),
    session: Session = Depends(get_session)
):
    """Crea un nuevo usuario sin necesidad de autenticación"""
    # Verificar si el usuario ya existe
    db_user = session.exec(select(User).where(User.username == username)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe.")

    # Validar rol
    valid_roles = ["admin", "vendor", "customer"]
    if role not in valid_roles:
        raise HTTPException(
            status_code=400, 
            detail=f"Rol inválido. Debe ser uno de: {', '.join(valid_roles)}"
        )

    # Hashear la contraseña antes de guardar
    hashed_password = hash_password(password)
    
    user = User(
        username=username,
        hashed_password=hashed_password,
        role=role
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return {
        "message": "Usuario creado exitosamente",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "created_at": user.created_at
        }
    }

# ======================================================
# 👤 OBTENER USUARIO POR ID (público)
# ======================================================
@router.get("/user/{user_id}")
def get_user(
    user_id: int,
    session: Session = Depends(get_session)
):
    """Obtiene información de un usuario por ID"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_superuser": user.is_superuser,
        "created_at": user.created_at
    }

# ======================================================
# 📋 LISTAR TODOS LOS USUARIOS (público)
# ======================================================
@router.get("/users")
def list_users(session: Session = Depends(get_session)):
    """Lista todos los usuarios"""
    users = session.exec(select(User)).all()
    return users

# ======================================================
# 🔍 BUSCAR USUARIOS (público)
# ======================================================
@router.get("/users/search")
def search_users(
    username: Optional[str] = None,
    role: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Busca usuarios por nombre o rol"""
    query = select(User)
    
    if username:
        query = query.where(User.username.ilike(f"%{username}%"))
    if role:
        query = query.where(User.role == role)
    
    users = session.exec(query).all()
    return users

# Función dummy para mantener compatibilidad
def get_current_user():
    """Función dummy para mantener compatibilidad con otros routers"""
    return None

def get_admin_user():
    """Función dummy para mantener compatibilidad"""
    return None