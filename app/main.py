from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
import os
from datetime import datetime

from .database import init_db, get_session
from sqlmodel import select, Session

# Modelos
from .models import Product, User

# Routers principales
from .routers import users, auth_router, products, audit, cart, orders, vendors, addresses

# Shipping
try:
    from .routers import shipping
except ImportError:
    shipping = None

# Algoritmos
try:
    from app.algorithms.router import router as algorithms_router
except ImportError:
    algorithms_router = None

# ======================================================
# 🟦 CREACIÓN DE APP
# ======================================================

app = FastAPI(title="Tienda Virtual", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Static + Templates
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Crear carpetas necesarias
os.makedirs("app/static/uploads/products", exist_ok=True)
os.makedirs("app/static/uploads/users", exist_ok=True)
os.makedirs("app/templates", exist_ok=True)
os.makedirs("app/static/js", exist_ok=True)

# ======================================================
# 🟩 INICIALIZACIÓN BD Y DATOS DE PRUEBA
# ======================================================
@app.on_event("startup")
def startup():
    # Inicializar base de datos (crea tablas en MySQL)
    init_db()

    # ← AQUÍ ESTABA EL ERROR: usabas SQLite
    # Ahora usamos el mismo engine que creaste en database.py (MySQL)
    from .database import engine, get_session
    from sqlmodel import Session, select

    with Session(engine) as session:
        # Verificar si existe algún usuario
        users_count = len(session.exec(select(User)).all())

        if users_count == 0:
            print("Creando usuario administrador por defecto...")
            from .auth import hash_password

            admin_user = User(
                username="admin",
                hashed_password=hash_password("admin123"),
                role="admin",
                is_superuser=True
            )
            session.add(admin_user)
            session.commit()
            print("Usuario admin creado")

        # Verificar productos
        products_count = len(session.exec(select(Product)).all())

        if products_count == 0:
            print("Creando productos de ejemplo...")
            admin_user = session.exec(select(User).where(User.username == "admin")).first()
            if admin_user:
                product1 = Product(
                    name="Laptop Gaming Pro",
                    description="Potente laptop para gaming y edición",
                    price=1499.99,
                    quantity=5,
                    weight_kg=2.8,
                    dimensions_cm="38x26x3",
                    requires_shipping=True,
                    owner_id=admin_user.id
                )
                session.add(product1)
                session.commit()
            print("Productos de ejemplo creados")

    print("Base de datos lista con datos iniciales.")

# ======================================================
# 🟪 INCLUIR ROUTERS API /api/...
# ======================================================

# NOTA: auth_router se mantiene pero solo para crear usuarios
app.include_router(auth_router.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(cart.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(vendors.router, prefix="/api")
app.include_router(addresses.router, prefix="/api")
app.include_router(audit.router, prefix="/api")

if shipping:
    app.include_router(shipping.router, prefix="/api")

if algorithms_router:
    app.include_router(algorithms_router, prefix="/api")

# ======================================================
# 🟦 RUTAS HTML DEL FRONTEND
# ======================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Página principal usando templates"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/catalogo", response_class=HTMLResponse)
async def catalogo(request: Request):
    return templates.TemplateResponse("products/list.html", {"request": request})

@app.get("/mi-carrito", response_class=HTMLResponse)
async def carrito(request: Request):
    return templates.TemplateResponse("cart.html", {"request": request})

@app.get("/mis-pedidos", response_class=HTMLResponse)
async def pedidos(request: Request):
    return templates.TemplateResponse("orders.html", {"request": request})

@app.get("/seguimiento", response_class=HTMLResponse)
async def seguimiento(request: Request):
    return templates.TemplateResponse("shipping/track.html", {"request": request})

@app.get("/algoritmos", response_class=HTMLResponse)
async def algoritmos(request: Request):
    """Página para probar algoritmos"""
    return templates.TemplateResponse("algorithms.html", {"request": request})

@app.get("/perfil", response_class=HTMLResponse)
async def perfil(request: Request):
    """Página de perfil de usuario"""
    return templates.TemplateResponse("profile.html", {"request": request})

@app.get("/registro", response_class=HTMLResponse)
async def registro(request: Request):
    """Página para crear nuevos usuarios"""
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/usuarios", response_class=HTMLResponse)
async def usuarios(request: Request):
    """Página para ver todos los usuarios"""
    return templates.TemplateResponse("usuarios.html", {"request": request})

@app.get("/acceder", response_class=HTMLResponse)
async def acceder(request: Request):
    """Página de acceso (simbólica)"""
    return templates.TemplateResponse("login_simple.html", {"request": request})

@app.get("/crear-producto", response_class=HTMLResponse)
async def crear_producto(request: Request):
    """Página para crear nuevos productos"""
    return templates.TemplateResponse("products/create.html", {"request": request})

@app.get("/panel", response_class=HTMLResponse)
async def panel_vendedor(request: Request):
    """Panel de control para vendedores"""
    return templates.TemplateResponse("vendors/dashboard.html", {"request": request})

# ======================================================
# 🟢 RUTAS DE REDIRECCIÓN PARA COMPATIBILIDAD
# ======================================================

@app.get("/auth/login")
async def redirect_to_acceder():
    """Redirige /auth/login a /acceder"""
    return RedirectResponse(url="/acceder")

@app.get("/login")
async def redirect_login():
    """Redirige /login a /acceder"""
    return RedirectResponse(url="/acceder")

@app.get("/auth/logout")
async def redirect_logout():
    """Redirige /auth/logout a / (home)"""
    return RedirectResponse(url="/")

# ======================================================
# 🟩 ENDPOINTS DE ESTADO / TEST
# ======================================================

@app.get("/api/status")
def api_status():
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "routes_ok": True,
        "features": ["auth", "products", "cart", "orders", "algorithms", "shipping"],
    }

@app.get("/debug")
def debug():
    return {
        "pwd": os.getcwd(),
        "templates": os.listdir("app/templates"),
        "static": os.listdir("app/static") if os.path.exists("app/static") else [],
        "url": "http://127.0.0.1:8000",
    }

# ======================================================
# 🟧 EJECUCIÓN DIRECTA (NO INCLUIDA EN app.main)
# ======================================================
# NOTA: Esta parte se ejecuta solo si ejecutas este archivo directamente
# No es parte de la aplicación FastAPI normal
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
