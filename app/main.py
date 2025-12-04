# app/main.py
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select, text
import os
import socket
from datetime import datetime
import logging
import time

# Importar modelos y configuración de base de datos
try:
    from .database import init_db, get_session, test_connection, get_database_info
    DATABASE_AVAILABLE = True
except Exception as e:
    print(f"⚠️  Advertencia: No se pudo importar database.py: {e}")
    DATABASE_AVAILABLE = False
    # Crear funciones dummy para continuar
    def init_db(): pass
    def get_session(): yield None
    def test_connection(): return False
    def get_database_info(): return {"connection": "❌ No disponible", "error": str(e)}

try:
    from .models import Product, User, Order, Cart, OrderItem, CartItem, ShippingAddress
    MODELS_AVAILABLE = True
except Exception as e:
    print(f"⚠️  Advertencia: No se pudo importar models: {e}")
    MODELS_AVAILABLE = False

# Routers principales
try:
    from .routers import users, auth_router, products, audit, cart, orders, vendors, addresses
    ROUTERS_AVAILABLE = True
except Exception as e:
    print(f"⚠️  Advertencia: No se pudo importar routers: {e}")
    ROUTERS_AVAILABLE = False

# Shipping
try:
    from .routers import shipping
    SHIPPING_AVAILABLE = True
except ImportError:
    shipping = None
    SHIPPING_AVAILABLE = False

# Algoritmos
try:
    from app.algorithms.router import router as algorithms_router
    ALGORITHMS_AVAILABLE = True
except ImportError:
    algorithms_router = None
    ALGORITHMS_AVAILABLE = False

# ======================================================
# 🟦 CONFIGURACIÓN BÁSICA
# ======================================================

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Tienda Virtual - MySQL Clever Cloud",
    version="1.2.0",
    description="Tienda virtual con base de datos MySQL en la nube",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, restringe esto
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Static + Templates
try:
    templates = Jinja2Templates(directory="app/templates")
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except Exception as e:
    logger.warning(f"No se pudo configurar templates/static: {e}")

# Crear carpetas necesarias
try:
    os.makedirs("app/static/uploads/products", exist_ok=True)
    os.makedirs("app/static/uploads/users", exist_ok=True)
    os.makedirs("app/templates", exist_ok=True)
    os.makedirs("app/static/js", exist_ok=True)
except Exception as e:
    logger.warning(f"No se pudieron crear carpetas: {e}")

# ======================================================
# 🟢 EVENTOS DE INICIO/SHUTDOWN - MEJORADO
# ======================================================
@app.on_event("startup")
async def startup_event():
    """Evento que se ejecuta al iniciar la aplicación"""
    logger.info("=" * 60)
    logger.info("🚀 INICIANDO TIENDA VIRTUAL")
    logger.info("=" * 60)
    
    try:
        # 1. Primero, probar resolución DNS
        logger.info("🔍 Probando resolución DNS...")
        test_hostname = "b9maju0nm8eaq2enhzhd-mysql.services.clever-cloud.com"
        
        try:
            ip_address = socket.gethostbyname(test_hostname)
            logger.info(f"✅ DNS resuelto: {test_hostname} → {ip_address}")
        except socket.gaierror as e:
            logger.error(f"❌ ERROR DNS: No se puede resolver '{test_hostname}'")
            logger.warning(f"   Código error: {e}")
            logger.warning("   La aplicación continuará pero la BD puede fallar")
            
            # Prueba con Google DNS
            logger.info("   Probando con DNS alternativo (Google)...")
            try:
                import dns.resolver
                resolver = dns.resolver.Resolver()
                resolver.nameservers = ['8.8.8.8', '8.8.4.4']
                answers = resolver.resolve(test_hostname, 'A')
                for answer in answers:
                    logger.info(f"   Google DNS resuelve a: {answer.address}")
            except Exception as dns_error:
                logger.warning(f"   También falló con Google DNS: {dns_error}")
        
        # 2. Inicializar base de datos MySQL (con manejo de errores)
        if DATABASE_AVAILABLE:
            logger.info("🔄 Intentando conectar a MySQL Clever Cloud...")
            
            # Intentar con retry
            max_retries = 3
            db_connected = False
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"   Intento {attempt + 1}/{max_retries}...")
                    
                    if attempt == 0:
                        # Primero solo probar conexión
                        if test_connection():
                            logger.info("   ✅ Conexión de prueba exitosa")
                            db_connected = True
                    
                    # Intentar inicializar DB
                    init_db()
                    logger.info("   ✅ Base de datos inicializada")
                    db_connected = True
                    break
                    
                except Exception as db_error:
                    if attempt < max_retries - 1:
                        wait_time = 2 * (attempt + 1)
                        logger.warning(f"   ⚠️  Intento fallido. Reintentando en {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"   ❌ Error después de {max_retries} intentos: {db_error}")
                        logger.warning("   La aplicación iniciará sin base de datos activa")
            
            if db_connected:
                # Obtener información de la BD
                info = get_database_info()
                logger.info(f"📊 Base de datos: {info.get('database', 'Desconocida')}")
                logger.info(f"📊 Estado: {info.get('connection', 'Desconocido')}")
                
                if info.get('tables'):
                    logger.info(f"📊 Tablas encontradas: {len(info.get('tables'))}")
                else:
                    logger.warning("📊 No se encontraron tablas")
        else:
            logger.warning("⚠️  Módulo de base de datos no disponible")
        
        logger.info("🎯 Aplicación lista para recibir peticiones")
        logger.info(f"🌐 URL: http://127.0.0.1:8000")
        logger.info(f"📚 Documentación: http://127.0.0.1:8000/docs")
        
    except Exception as e:
        logger.error(f"❌ Error crítico durante el startup: {str(e)}")
        logger.warning("La aplicación continuará en modo limitado...")
    
    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """Evento que se ejecuta al cerrar la aplicación"""
    logger.info("🛑 Cerrando Tienda Virtual...")

# ======================================================
# 🟪 INCLUIR ROUTERS API /api/...
# ======================================================

# Routers principales
if ROUTERS_AVAILABLE:
    try:
        app.include_router(auth_router.router, prefix="/api", tags=["Autenticación"])
        app.include_router(users.router, prefix="/api", tags=["Usuarios"])
        app.include_router(products.router, prefix="/api", tags=["Productos"])
        app.include_router(cart.router, prefix="/api", tags=["Carrito"])
        app.include_router(orders.router, prefix="/api", tags=["Órdenes"])
        app.include_router(vendors.router, prefix="/api", tags=["Vendedores"])
        app.include_router(addresses.router, prefix="/api", tags=["Direcciones"])
        app.include_router(audit.router, prefix="/api", tags=["Auditoría"])
        logger.info("✅ Routers principales cargados")
    except Exception as e:
        logger.error(f"❌ Error cargando routers: {e}")
else:
    logger.warning("⚠️  Routers no disponibles")

# Routers condicionales
if SHIPPING_AVAILABLE:
    try:
        app.include_router(shipping.router, prefix="/api", tags=["Envíos"])
        logger.info("✅ Módulo de envíos cargado")
    except Exception as e:
        logger.error(f"❌ Error cargando shipping: {e}")

if ALGORITHMS_AVAILABLE:
    try:
        app.include_router(algorithms_router, prefix="/api", tags=["Algoritmos"])
        logger.info("✅ Módulo de algoritmos cargado")
    except Exception as e:
        logger.error(f"❌ Error cargando algoritmos: {e}")

# ======================================================
# 🟦 RUTAS HTML DEL FRONTEND
# ======================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Página principal usando templates"""
    # Obtener estadísticas de la base de datos
    try:
        db_info = get_database_info()
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
        "app_version": "1.2.0"
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
    """Página para probar algoritmos"""
    if ALGORITHMS_AVAILABLE:
        return templates.TemplateResponse("algorithms.html", {"request": request})
    else:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Módulo de algoritmos no disponible"
        })

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
# 🟩 ENDPOINTS DE ESTADO / MONITOREO / ADMIN
# ======================================================

@app.get("/api/status")
def api_status():
    """Endpoint de estado del sistema"""
    try:
        # Obtener información de la base de datos
        db_info = get_database_info()
        
        # Intentar contar registros si la BD está disponible
        users_count = 0
        products_count = 0
        orders_count = 0
        
        if DATABASE_AVAILABLE and MODELS_AVAILABLE:
            try:
                session_gen = get_session()
                session = next(session_gen)
                users_count = len(session.exec(select(User)).all())
                products_count = len(session.exec(select(Product)).all())
                orders_count = len(session.exec(select(Order)).all())
            except:
                pass
        
        return {
            "status": "online",
            "timestamp": datetime.now().isoformat(),
            "version": "1.2.0",
            "database": {
                "name": db_info.get('database', 'No disponible'),
                "tables": len(db_info.get('tables', [])),
                "connection": db_info.get('connection', '❌ No disponible'),
                "error": db_info.get('error', None)
            },
            "stats": {
                "users": users_count,
                "products": products_count,
                "orders": orders_count
            },
            "modules": {
                "database": DATABASE_AVAILABLE,
                "models": MODELS_AVAILABLE,
                "routers": ROUTERS_AVAILABLE,
                "auth": ROUTERS_AVAILABLE,
                "products": ROUTERS_AVAILABLE,
                "cart": ROUTERS_AVAILABLE,
                "orders": ROUTERS_AVAILABLE,
                "shipping": SHIPPING_AVAILABLE,
                "algorithms": ALGORITHMS_AVAILABLE,
                "vendors": ROUTERS_AVAILABLE,
                "audit": ROUTERS_AVAILABLE
            },
            "environment": os.getenv("ENVIRONMENT", "development")
        }
    except Exception as e:
        return {
            "status": "online",
            "database_connection": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
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

@app.get("/api/diagnostic")
def diagnostic():
    """Diagnóstico completo del sistema"""
    results = {
        "timestamp": datetime.now().isoformat(),
        "system": {
            "python_version": os.sys.version,
            "platform": os.sys.platform,
            "current_directory": os.getcwd(),
            "environment": os.getenv("ENVIRONMENT", "development")
        },
        "dns_test": {},
        "database_test": {},
        "import_tests": {}
    }
    
    # Test DNS
    test_hostname = "b9maju0nm8eaq2enhzhd-mysql.services.clever-cloud.com"
    try:
        ip_address = socket.gethostbyname(test_hostname)
        results["dns_test"] = {
            "status": "✅ Resuelto",
            "hostname": test_hostname,
            "ip_address": ip_address
        }
    except socket.gaierror as e:
        results["dns_test"] = {
            "status": "❌ Error",
            "hostname": test_hostname,
            "error": str(e),
            "error_code": e.errno
        }
    
    # Test Database
    if DATABASE_AVAILABLE:
        try:
            conn_ok = test_connection()
            results["database_test"] = {
                "status": "✅ Conectado" if conn_ok else "❌ Falló",
                "available": True,
                "connection_test": conn_ok
            }
        except Exception as e:
            results["database_test"] = {
                "status": "❌ Error",
                "available": True,
                "error": str(e)
            }
    else:
        results["database_test"] = {
            "status": "❌ No disponible",
            "available": False
        }
    
    # Test imports
    imports_to_test = [
        ("sqlmodel", "SQLModel"),
        ("fastapi", "FastAPI"),
        ("pymysql", "connect"),
        ("dotenv", "load_dotenv")
    ]
    
    for module_name, attr_name in imports_to_test:
        try:
            __import__(module_name)
            results["import_tests"][module_name] = "✅ OK"
        except ImportError as e:
            results["import_tests"][module_name] = f"❌ Error: {e}"
    
    return results

@app.get("/api/health")
def health_check():
    """Health check simple para monitoreo"""
    try:
        if DATABASE_AVAILABLE:
            connection_ok = test_connection()
            status = "healthy" if connection_ok else "unhealthy"
            db_status = "connected" if connection_ok else "disconnected"
        else:
            status = "degraded"
            db_status = "module_missing"
        
        return JSONResponse(
            status_code=200 if status == "healthy" else 503,
            content={
                "status": status,
                "database": db_status,
                "timestamp": datetime.now().isoformat(),
                "version": "1.2.0"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

# ======================================================
# 🟨 MANEJADOR DE ERRORES GLOBAL
# ======================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Manejador global de excepciones"""
    logger.error(f"Error no manejado en {request.url.path}: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Error interno del servidor",
            "message": str(exc) if os.getenv("ENVIRONMENT") == "development" else "Contacte al administrador",
            "path": request.url.path,
            "timestamp": datetime.now().isoformat(),
            "request_id": getattr(request.state, 'request_id', 'N/A')
        }
    )

# ======================================================
# 🟥 EJECUCIÓN DIRECTA
# ======================================================

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🚀 TIENDA VIRTUAL CON MYSQL CLEVER CLOUD")
    print("=" * 60)
    print("🔧 Modo: Desarrollo")
    print(f"📁 Directorio: {os.getcwd()}")
    print(f"🐍 Python: {os.sys.version}")
    print(f"🌐 URL: http://127.0.0.1:8000")
    print(f"📚 Docs: http://127.0.0.1:8000/docs")
    print(f"🔍 Diagnostic: http://127.0.0.1:8000/api/diagnostic")
    print("=" * 60)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )