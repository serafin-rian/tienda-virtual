from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from ..database import get_session
from ..models import User
import hashlib

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or user.hashed_password != hash_password(password):
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Usuario o contraseña incorrectos."}
        )
    
    # Por ahora solo redirigimos, luego agregaremos sesiones real
    response = RedirectResponse(url="/", status_code=303)
    return response
