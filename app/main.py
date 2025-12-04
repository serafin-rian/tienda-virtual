# app/main.py - VERSIÓN FINAL PARA RENDER
import os
import sys
import socket
import asyncio
from datetime import datetime
import logging
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select, text

# ======================================================
# 🟦 1. VERIFICAR E INSTALAR DEPENDENCIAS FALTANTES
# ======================================================

# Intenta instalar pymysql si falta (solo en desarrollo)
if os.getenv("ENVIRONMENT", "development") == "development":
    try:
        import pymysql
        print("✅ pymysql disponible")
    except ImportError:
        print("⚠️  pymysql no encontrado en desarrollo")
else:
    # En producción, asumimos que está instalado
    import pymysql

# ======================================================
# 🟦 2. IMPORTAR MÓDULOS CON MANEJO DE ERRORES
# ======================================================

# Importar configuración de base de datos
try:
    from .database import init_db, get_session, test_connection, get_database_info
    DATABASE_AVAILABLE = True
    print("✅ Módulo database disponible")
except Exception as e:
    print(f"⚠️  No se pudo importar database.py: {e}")
    DATABASE_AVAILABLE = False
    # Crear funciones dummy
    def init_db(): 
        print("⚠️  init_db dummy - BD no disponible")
    def get_session(): 
        yield None
    def test_connection(): 
        return False
    def get_database_info(): 
        return {"connection": "❌ No disponible", "error": "Módulo no cargado"}

# Intentar importar modelos
try:
    from .models import Product, User, Order, Cart, OrderItem, CartItem, ShippingAddress
    MODELS_AVAILABLE = True
    print("✅ Modelos disponibles")
except Exception as e:
    print(f"⚠️  No se pudo importar models: {e}")
    MODELS_AVAILABLE = False

# Routers principales con manejo de errores
ROUTERS_LOADED = []
try:
    from .routers import users, auth_router, products, audit, cart, orders, vendors, addresses
    ROUTERS = {
        'auth': auth_router,
        'users': users,
        'products': products,
        'cart': cart,
        'orders': orders,
        'vendors': vendors,
        'addresses': addresses,
        'audit': audit
    }
    ROUTERS_AVAILABLE = True
    print("✅ Routers principales disponibles")
except Exception as e:
    print(f"⚠️  No se pudo importar routers principales: {e}")
    ROUTERS_AVAILABLE = False
    ROUTERS = {}

# Shipping
try:
    from .routers import shipping
    SHIPPING_AVAILABLE = True
    print("✅ Módulo shipping disponible")
except ImportError:
    shipping = None
    SHIPPING_AVAILABLE = False
    print("⚠️  Módulo shipping no disponible")

# Algoritmos
try:
    from app.algorithms.router import router as algorithms_router
    ALGORITHMS_AVAILABLE = True
    print("✅ Módulo algoritmos disponible")
except ImportError:
    algorithms_router = None
    ALGORITHMS_AVAILABLE = False
    print("⚠️  Módulo algoritmos no disponible")

# ======================================================
# 🟦 3. CONFIGURACIÓN BÁSICA
# ======================================================

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Tienda Virtual - MySQL Clever Cloud",
    version="2.0.0",  # Nueva versión
    description="Tienda virtual con base de datos MySQL en la nube",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Static + Templates
try:
    templates = Jinja2Templates(directory="app/templates")
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    print("✅ Templates y static configurados")
except Exception as e:
    print(f"⚠️  No se pudo configurar templates/static: {e}")
    # Crear templates dummy
    class DummyTemplates:
        def TemplateResponse(self, *args, **kwargs):
            return HTMLResponse("<h1>Error: Templates no disponibles</h1>")
    templates = DummyTemplates()

# ======================================================
# 🟢 4. HEALTH CHECKS PARA RENDER (DEBE SER LO PRIMERO)
# ======================================================

@app.get("/health", include_in_schema=False)
async def health_check_immediate():
    """Health check INMEDIATO que Render usa para verificar"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "service": "tienda-virtual",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0"
        }
    )

@app.get("/ready", include_in_schema=False)
async def readiness_check():
    """Verifica si la app está lista para recibir tráfico"""
    db_connected = False
    if DATABASE_AVAILABLE:
        try:
            db_connected = test_connection()
        except:
            db_connected = False
    
    status = "ready" if len(ROUTERS_LOADED) > 0 else "degraded"
    
    return JSONResponse(
        status_code=200 if status == "ready" else 503,
        content={
            "status": status,
            "database": "connected" if db_connected else "disconnected",
            "routers_loaded": len(ROUTERS_LOADED),
            "timestamp": datetime.now().isoformat()
        }
    )

# ======================================================
# 🟢 5. EVENTOS DE INICIO/SHUTDOWN - VERSIÓN RENDER
# ======================================================

async def initialize_database_background():
    """Inicializa la base de datos en segundo plano (NO BLOQUEANTE)"""
    try:
        logger.info("🔄 Inicializando base de datos en segundo plano...")
        
        if not DATABASE_AVAILABLE:
            logger.warning("⚠️  Módulo de base de datos no disponible")
            return
        
        # Pequeña pausa para que Render verifique health check
        await asyncio.sleep(2)
        
        # Probar conexión a la BD
        logger.info("🔌 Probando conexión a MySQL...")
        
        if test_connection():
            logger.info("✅ Conexión a MySQL exitosa")
            try:
                init_db()
                info = get_database_info()
                logger.info(f"📊 Base de datos: {info.get('database', 'Desconocida')}")
                logger.info(f"📊 Tablas: {len(info.get('tables', []))}")
            except Exception as e:
                logger.warning(f"⚠️  Error inicializando tablas: {e}")
        else:
            logger.warning("⚠️  No se pudo conectar a MySQL. La app funcionará en modo limitado.")
            
    except Exception as e:
        logger.error(f"❌ Error en inicialización de BD: {e}")

@app.on_event("startup")
async def startup_event():
    """Evento de inicio - VERSIÓN OPTIMIZADA PARA RENDER"""
    logger.info("=" * 60)
    logger.info("🚀 INICIANDO TIENDA VIRTUAL EN RENDER")
    logger.info("=" * 60)
    
    # Información del sistema
    port = os.getenv("PORT", "10000")
    environment = os.getenv("ENVIRONMENT", "development")
    logger.info(f"🌐 Puerto: {port}")
    logger.info(f"🌍 Entorno: {environment}")
    logger.info(f"📁 Directorio: {os.getcwd()}")
    logger.info(f"🐍 Python: {sys.version[:50]}...")
    
    # Verificar módulos críticos
    logger.info("🔍 Verificando módulos...")
    logger.info(f"   Database: {'✅' if DATABASE_AVAILABLE else '❌'}")
    logger.info(f"   Models: {'✅' if MODELS_AVAILABLE else '❌'}")
    
    # Iniciar BD en segundo plano (NO BLOQUEA EL INICIO)
    asyncio.create_task(initialize_database_background())
    
    logger.info("🎯 Aplicación lista para recibir peticiones")
    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """Evento que se ejecuta al cerrar la aplicación"""
    logger.info("🛑 Cerrando Tienda Virtual...")

# ======================================================
# 🟪 6. INCLUIR ROUTERS API
# ======================================================

# Routers principales
if ROUTERS_AVAILABLE:
    for name, router in ROUTERS.items():
        try:
            app.include_router(router.router, prefix="/api", tags=[name.capitalize()])
            ROUTERS_LOADED.append(name)
            logger.info(f"✅ Router {name} cargado")
        except Exception as e:
            logger.error(f"❌ Error cargando router {name}: {e}")
else:
    logger.warning("⚠️  No se cargaron routers principales")

# Routers condicionales
if SHIPPING_AVAILABLE:
    try:
        app.include_router(shipping.router, prefix="/api", tags=["Envíos"])
        ROUTERS_LOADED.append("shipping")
        logger.info("✅ Módulo de envíos cargado")
    except Exception as e:
        logger.error(f"❌ Error cargando shipping: {e}")

if ALGORITHMS_AVAILABLE:
    try:
        app.include_router(algorithms_router, prefix="/api", tags=["Algoritmos"])
        ROUTERS_LOADED.append("algorithms")
        logger.info("✅ Módulo de algoritmos cargado")
    except Exception as e:
        logger.error(f"❌ Error cargando algoritmos: {e}")

# ======================================================
# 🟦 7. RUTAS HTML DEL FRONTEND
# ======================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Página principal"""
    try:
        db_info = get_database_info() if DATABASE_AVAILABLE else {}
        stats = {
            "tables_count": len(db_info.get('tables', [])) if db_info.get('tables') else 0,
            "connection_status": db_info.get('connection', '❌ No disponible'),
            "database_name": db_info.get('database', 'MySQL Clever Cloud'),
            "error": db_info.get('error', None)
        }
    except Exception as e:
        stats = {
            "tables_count": 0,
            "connection_status": f"❌ Error: {str(e)[:50]}...",
            "database_name": "No disponible",
            "error": str(e)
        }
    
    # Determinar si estamos en Render
    is_render = "render.com" in os.getenv("RENDER_EXTERNAL_URL", "")
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "db_stats": stats,
        "app_version": "2.0.0",
        "is_render": is_render,
        "port": os.getenv("PORT", "10000")
    })

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
    if SHIPPING_AVAILABLE:
        return templates.TemplateResponse("shipping/track.html", {"request": request})
    else:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Módulo de envíos no disponible"
        })

@app.get("/algoritmos", response_class=HTMLResponse)
async def algoritmos(request: Request):
    if ALGORITHMS_AVAILABLE:
        return templates.TemplateResponse("algorithms.html", {"request": request})
    else:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Módulo de algoritmos no disponible"
        })

@app.get("/perfil", response_class=HTMLResponse)
async def perfil(request: Request):
    return templates.TemplateResponse("profile.html", {"request": request})

@app.get("/registro", response_class=HTMLResponse)
async def registro(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/usuarios", response_class=HTMLResponse)
async def usuarios(request: Request):
    return templates.TemplateResponse("usuarios.html", {"request": request})

@app.get("/acceder", response_class=HTMLResponse)
async def acceder(request: Request):
    return templates.TemplateResponse("login_simple.html", {"request": request})

@app.get("/crear-producto", response_class=HTMLResponse)
async def crear_producto(request: Request):
    return templates.TemplateResponse("products/create.html", {"request": request})

@app.get("/panel", response_class=HTMLResponse)
async def panel_vendedor(request: Request):
    return templates.TemplateResponse("vendors/dashboard.html", {"request": request})

# ======================================================
# 🟢 RUTAS DE REDIRECCIÓN PARA COMPATIBILIDAD
# ======================================================

@app.get("/auth/login")
async def redirect_to_acceder():
    return RedirectResponse(url="/acceder")

@app.get("/login")
async def redirect_login():
    return RedirectResponse(url="/acceder")

@app.get("/auth/logout")
async def redirect_logout():
    return RedirectResponse(url="/")

# ======================================================
# 🟩 8. ENDPOINTS DE ESTADO / MONITOREO
# ======================================================

@app.get("/api/status")
async def api_status():
    """Endpoint de estado del sistema"""
    db_connected = False
    db_info = {}
    
    if DATABASE_AVAILABLE:
        try:
            db_connected = test_connection()
            db_info = get_database_info()
        except:
            db_connected = False
            db_info = {"error": "Error obteniendo información"}
    
    # Obtener URL de Render si existe
    render_url = os.getenv("RENDER_EXTERNAL_URL", "No disponible")
    
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "deployment": {
            "platform": "Render" if "RENDER" in os.environ else "Local",
            "url": render_url,
            "port": os.getenv("PORT", "10000")
        },
        "database": {
            "available": DATABASE_AVAILABLE,
            "connected": db_connected,
            "name": db_info.get('database', 'No disponible'),
            "tables": len(db_info.get('tables', [])),
            "status": db_info.get('connection', 'Desconocido')
        },
        "modules": {
            "database": DATABASE_AVAILABLE,
            "models": MODELS_AVAILABLE,
            "routers_loaded": ROUTERS_LOADED,
            "shipping": SHIPPING_AVAILABLE,
            "algorithms": ALGORITHMS_AVAILABLE
        },
        "system": {
            "python_version": sys.version[:20],
            "platform": sys.platform,
            "host": socket.gethostname()
        }
    }

@app.get("/api/db/status")
def db_status():
    """Endpoint para verificar el estado de la base de datos"""
    if not DATABASE_AVAILABLE:
        return {
            "database": "MySQL Clever Cloud",
            "connection": "❌ Módulo no disponible",
            "database_name": "No disponible",
            "error": "No se pudo importar database.py",
            "timestamp": datetime.now().isoformat()
        }
    
    connection_ok = test_connection()
    info = get_database_info()
    
    return {
        "database": "MySQL Clever Cloud",
        "connection": "✅ Activa" if connection_ok else "❌ Fallida",
        "database_name": info.get('database', 'No disponible'),
        "tables_count": len(info.get('tables', [])),
        "tables_list": info.get('tables', []),
        "size_mb": info.get('size_mb', 0),
        "host": info.get('host', 'No configurado'),
        "error": info.get('error', None),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/debug")
async def debug_endpoint():
    """Endpoint para debugging"""
    import pkg_resources
    
    # Obtener paquetes instalados
    packages = {}
    try:
        for dist in pkg_resources.working_set:
            packages[dist.project_name] = dist.version
    except:
        packages = {"error": "No se pudieron obtener paquetes"}
    
    # Verificar archivos importantes
    files_exist = {
        "app/": os.path.exists("app"),
        "app/database.py": os.path.exists("app/database.py"),
        "app/models.py": os.path.exists("app/models.py"),
        "requirements.txt": os.path.exists("requirements.txt"),
    }
    
    return {
        "timestamp": datetime.now().isoformat(),
        "system": {
            "cwd": os.getcwd(),
            "files": os.listdir(".")[:10],
            "files_exist": files_exist
        },
        "environment": {
            "PORT": os.getenv("PORT", "No configurado"),
            "ENVIRONMENT": os.getenv("ENVIRONMENT", "development"),
            "MYSQL_HOST": os.getenv("MYSQL_HOST", "No configurado"),
            "RENDER": "RENDER" in os.environ
        },
        "packages": {k: v for k, v in list(packages.items())[:10]}  # Primeros 10 paquetes
    }

# ======================================================
# 🟨 9. MANEJADOR DE ERRORES GLOBAL
# ======================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Manejador global de excepciones"""
    logger.error(f"Error en {request.url.path}: {str(exc)}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Error interno del servidor",
            "message": str(exc) if os.getenv("ENVIRONMENT") == "development" else "Contacte al administrador",
            "path": request.url.path,
            "timestamp": datetime.now().isoformat()
        }
    )

# ======================================================
# 🟥 10. EJECUCIÓN DIRECTA SOLO PARA DESARROLLO LOCAL
# ======================================================

if __name__ == "__main__":
    # ESTO SOLO SE EJECUTA EN DESARROLLO LOCAL
    # EN RENDER, SE USA EL START COMMAND
    
    import uvicorn
    
    print("=" * 60)
    print("🚀 TIENDA VIRTUAL - MODO DESARROLLO LOCAL")
    print("=" * 60)
    print("🔧 Este archivo solo para desarrollo local")
    print("📌 En Render usa: uvicorn app.main:app --host 0.0.0.0 --port $PORT")
    print("=" * 60)
    
    # Para desarrollo local
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # Usar 0.0.0.0 para compatibilidad
        port=8000,
        reload=True,
        log_level="info"
    )
