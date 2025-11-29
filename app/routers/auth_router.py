from fastapi import APIRouter, Depends, HTTPException, Form, Cookie, Response, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select  
from ..database import get_session
from ..models import User
from ..auth import verify_password
from typing import Optional  


router = APIRouter(prefix="/auth", tags=["auth"])

# Ruta donde estarán las plantillas HTML
templates = Jinja2Templates(directory="app/templates")

# ------------------------------------------------------------
# 🧩 Mostrar formulario de login (para navegador)
# ------------------------------------------------------------
@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    """Renderiza el formulario de inicio de sesión (HTML)."""
    return templates.TemplateResponse("login.html", {"request": request})

# ------------------------------------------------------------
# 🔐 Procesar login (compatible con Swagger y navegador)
# ------------------------------------------------------------
@router.post("/login")
def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)  # ✅ Cambiar db → session
):
    """Procesa el inicio de sesión (HTML o Swagger)."""
    # ✅ Cambiar a SQLModel
    user = session.exec(select(User).where(User.username == username)).first()

    if not user or not verify_password(password, user.hashed_password):
        # Si es desde navegador, mostrar error en la página HTML
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Usuario o contraseña incorrectos"},
            status_code=401
        )

    # Guardamos cookie (válido para navegador y Swagger)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="user", value=username, httponly=True)
    return response

# ------------------------------------------------------------
# 🚪 Logout
# ------------------------------------------------------------
@router.get("/logout")
def logout(response: Response):
    """Cierra sesión eliminando cookie"""
    response.delete_cookie(key="user")
    return {"message": "Sesión cerrada"}

# ------------------------------------------------------------
# 👤 Obtener usuario actual (para roles)
# ------------------------------------------------------------
def get_current_user(
    user: str = Cookie(None), 
    session: Session = Depends(get_session)  # ✅ Cambiar db → session
):
    """Devuelve el usuario autenticado basado en la cookie"""
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    # ✅ Cambiar a SQLModel
    db_user = session.exec(select(User).where(User.username == user)).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    return db_user

# ------------------------------------------------------------
# 🔐 Verificar credenciales (helper function)
# ------------------------------------------------------------
def authenticate_user(username: str, password: str, session: Session):
    """Verifica si las credenciales son válidas"""
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# ------------------------------------------------------------
# 📊 Información del usuario actual
# ------------------------------------------------------------
@router.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Obtiene información del usuario actualmente autenticado"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "is_superuser": current_user.is_superuser,
        "created_at": current_user.created_at
    }

# ------------------------------------------------------------
# 🔄 Cambiar contraseña
# ------------------------------------------------------------
@router.post("/change-password")
def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Permite al usuario cambiar su contraseña"""
    # Verificar contraseña actual
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    
    # Actualizar contraseña
    from ..auth import hash_password
    current_user.hashed_password = hash_password(new_password)
    session.add(current_user)
    session.commit()
    
    return {"message": "Contraseña actualizada exitosamente"}

# ------------------------------------------------------------
# 👥 Verificar permisos de administrador
# ------------------------------------------------------------
def get_admin_user(current_user: User = Depends(get_current_user)):
    """Verifica que el usuario actual sea administrador"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403, 
            detail="Se requieren permisos de administrador"
        )
    return current_user

# ------------------------------------------------------------
# 🔍 Buscar usuarios (solo admin)
# ------------------------------------------------------------
@router.get("/users/search")
def search_users(
    username: Optional[str] = None,
    role: Optional[str] = None,
    session: Session = Depends(get_session),
    admin_user: User = Depends(get_admin_user)
):
    """Busca usuarios por nombre o rol (solo admin)"""
    query = select(User)
    
    if username:
        query = query.where(User.username.ilike(f"%{username}%"))
    if role:
        query = query.where(User.role == role)
    
    users = session.exec(query).all()
    return users

# ------------------------------------------------------------
# 📈 Estadísticas de autenticación
# ------------------------------------------------------------
@router.get("/stats")
def get_auth_stats(
    session: Session = Depends(get_session),
    admin_user: User = Depends(get_admin_user)
):
    """Estadísticas de usuarios y autenticación (solo admin)"""
    users = session.exec(select(User)).all()
    
    total_users = len(users)
    admin_count = sum(1 for user in users if user.role == "admin")
    client_count = sum(1 for user in users if user.role == "client")
    
    return {
        "total_users": total_users,
        "admin_users": admin_count,
        "client_users": client_count,
        "superusers": sum(1 for user in users if user.is_superuser),
        "recent_users": len([user for user in users if user.created_at]),
        "users_by_role": {
            "admin": admin_count,
            "client": client_count
        }
    }