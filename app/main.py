# app/main.py - VERSIÓN CORREGIDA PARA RENDER
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

# Intenta instalar pymysql si falta
try:
    import pymysql
    print("✅ pymysql disponible")
except ImportError:
    print("⚠️  pymysql no encontrado, intentando instalar...")
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pymysql==1.1.0"])
        import pymysql
        print("✅ pymysql instalado exitosamente")
    except Exception as e:
        print(f"❌ No se pudo instalar pymysql: {e}")

# ======================================================
# 🟦 2. IMPORTAR MÓDULOS CON MANEJO DE ERRORES
# ======================================================

# Importar modelos y configuración de base de datos
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
    version="1.3.0",  # Versión actualizada
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

# ======================================================
# 🟢 4. EVENTOS DE INICIO/SHUTDOWN - VERSIÓN RENDER
# ======================================================

async def initialize_database_background():
    """Inicializa la base de datos en segundo plano (NO BLOQUEANTE)"""
    try:
        logger.info("🔄 Inicializando base de datos en segundo plano...")
        
        if not DATABASE_AVAILABLE:
            logger.warning("⚠️  Módulo de base de datos no disponible")
            return
        
        # Pequeña pausa para que Render verifique health check
        await asyncio.sleep(1)
        
        # Probar conexión a la BD CORRECTA
        logger.info("🔌 Probando conexión a MySQL...")
        
        # Verificar el hostname CORRECTO
        correct_hostname = "bogydrre62bcscxkvuak-mysql.services.clever-cloud.com"
        try:
            ip = socket.gethostbyname(correct_hostname)
            logger.info(f"✅ DNS resuelto: {correct_hostname} → {ip}")
        except socket.gaierror:
            logger.warning(f"⚠️  No se puede resolver DNS para: {correct_hostname}")
        
        # Probar conexión MySQL
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
    port = os.getenv("PORT", "8000")
    logger.info(f"🌐 Puerto: {port}")
    logger.info(f"📁 Directorio: {os.getcwd()}")
    logger.info(f"🐍 Python: {sys.version[:20]}...")
    
    # Verificar módulos críticos
    logger.info("🔍 Verificando módulos...")
    logger.info(f"   Database: {'✅' if DATABASE_AVAILABLE else '❌'}")
    logger.info(f"   Models: {'✅' if MODELS_AVAILABLE else '❌'}")
    logger.info(f"   Routers: {'✅' if ROUTERS_AVAILABLE else '❌'}")
    
    # Iniciar BD en segundo plano (NO BLOQUEA EL INICIO)
    asyncio.create_task(initialize_database_background())
    
    logger.info("🎯 Aplicación lista para recibir peticiones")
    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """Evento que se ejecuta al cerrar la aplicación"""
    logger.info("🛑 Cerrando Tienda Virtual...")

# ======================================================
# 🟪 5. INCLUIR ROUTERS API
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
# 🟦 6. HEALTH CHECKS PARA RENDER (IMPORTANTE!)
# ======================================================

@app.get("/health", include_in_schema=False)
async def health_check_immediate():
    """Health check INMEDIATO que Render usa para verificar"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "service": "tienda-virtual",
            "timestamp": datetime.now().isoformat()
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
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "db_stats": stats,
        "app_version": "1.3.0",
        "render_deploy": True  # Indicar que está en Render
    })

# Resto de rutas HTML (mantén las que tienes)
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

# ... (mantén el resto de tus rutas HTML igual)

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
    
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "version": "1.3.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
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
            "port": os.getenv("PORT", "8000"),
            "python_version": sys.version[:20],
            "platform": sys.platform
        }
    }

@app.get("/api/debug")
async def debug_endpoint():
    """Endpoint para debugging en Render"""
    import pkg_resources
    
    packages = {}
    for dist in pkg_resources.working_set:
        packages[dist.project_name] = dist.version
    
    return {
        "pwd": os.getcwd(),
        "files_in_app": os.listdir("app") if os.path.exists("app") else [],
        "requirements": list(packages.keys())[:20],  # Primeros 20 paquetes
        "mysql_host": os.getenv("MYSQL_HOST", "No configurado"),
        "port": os.getenv("PORT", "8000"),
        "python_version": sys.version,
        "platform": sys.platform
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
# 🟥 10. EJECUCIÓN DIRECTA (LOCAL)
# ======================================================

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🚀 TIENDA VIRTUAL - MODO DESARROLLO LOCAL")
    print("=" * 60)
    print("🔧 Modo: Desarrollo")
    print(f"📁 Directorio: {os.getcwd()}")
    print(f"🐍 Python: {sys.version[:50]}...")
    print(f"🌐 URL: http://127.0.0.1:8000")
    print(f"📚 Docs: http://127.0.0.1:8000/docs")
    print(f"❤️  Health: http://127.0.0.1:8000/health")
    print("=" * 60)
    
    # Para desarrollo local, usa host 0.0.0.0
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # IMPORTANTE: 0.0.0.0 para Render
        port=port,        # Usar variable PORT
        reload=False,     # False en producción
        log_level="info"
    )
