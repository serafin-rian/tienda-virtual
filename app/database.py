# app/database.py
from sqlmodel import SQLModel, create_engine, Session, text
from typing import Generator
import os
import socket
from dotenv import load_dotenv
import time

# Cargar variables de entorno
load_dotenv()

# ======================================================
# 🟦 CREDENCIALES MYSQL CLEVER CLOUD
# ======================================================

# VERIFICA ESTOS DATOS EXACTAMENTE COMO ESTÁN EN CLEVER CLOUD
MYSQL_CONFIG = {
    "host": "b9maju0nm8eaq2enhzhd-mysql.services.clever-cloud.com",
    "port": 3306,
    "database": "b9maju0nm8eaq2enhzhd",
    "username": "uwfhtgrqz7c8pjdg",
    "password": "3fAP9h7uGC22092N02mm",
    "charset": "utf8mb4"
}

def test_dns_resolution():
    """Prueba la resolución DNS del host"""
    try:
        print(f"🔍 Resolviendo DNS: {MYSQL_CONFIG['host']}")
        ip_address = socket.gethostbyname(MYSQL_CONFIG['host'])
        print(f"✅ DNS resuelto → {ip_address}")
        return True
    except socket.gaierror as e:
        print(f"❌ ERROR DNS: No se puede resolver '{MYSQL_CONFIG['host']}'")
        print(f"   Código error: {e}")
        print("\n🛠️  SOLUCIONES:")
        print("   1. Verifica el nombre del host")
        print("   2. Prueba con estos comandos en PowerShell:")
        print(f'      nslookup {MYSQL_CONFIG["host"]}')
        print('      ping 8.8.8.8 (para verificar internet)')
        print("   3. Cambia DNS a Google (8.8.8.8 y 8.8.4.4)")
        return False

# Probar DNS antes de crear la conexión
if not test_dns_resolution():
    print("\n⚠️  ADVERTENCIA: Problemas de DNS detectados")
    print("   La aplicación intentará continuar...")

# String de conexión
DATABASE_URL = f"mysql+pymysql://{MYSQL_CONFIG['username']}:{MYSQL_CONFIG['password']}@{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}?charset={MYSQL_CONFIG['charset']}"

# Crear engine con timeout extendido
engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,  # Timeout extendido
    connect_args={
        'connect_timeout': 15  # Timeout de conexión extendido
    }
)

# ======================================================
# 🟢 FUNCIONES DE BASE DE DATOS
# ======================================================

def init_db():
    """Crea todas las tablas en la base de datos MySQL"""
    try:
        print("🔄 Creando tablas en MySQL (Clever Cloud)...")
        
        # Intentar conexión con retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                SQLModel.metadata.create_all(engine)
                print("✅ Tablas creadas exitosamente")
                
                # Verificar conexión
                with Session(engine) as session:
                    result = session.exec(text("SELECT 1"))
                    print(f"✅ Conexión verificada")
                
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️  Intento {attempt + 1} fallido, reintentando...")
                    time.sleep(2)
                else:
                    raise e
                
    except Exception as e:
        print(f"❌ Error al inicializar la base de datos: {str(e)}")
        print("\n🔧 SOLUCIÓN ALTERNATIVA:")
        print("   1. Verifica en Clever Cloud que la BD esté 'Running'")
        print("   2. Whitelist de IPs: Agrega 0.0.0.0/0 temporalmente")
        print("   3. Usa conexión alternativa sin SSL")
        raise


def get_session() -> Generator[Session, None, None]:
    """Generador de sesiones para usar con FastAPI Depends"""
    with Session(engine) as session:
        try:
            yield session
        finally:
            session.close()


def test_connection():
    """Prueba la conexión a la base de datos MySQL"""
    try:
        print(f"🔌 Probando conexión a: {MYSQL_CONFIG['host']}")
        with Session(engine) as session:
            result = session.exec(text("SELECT VERSION()"))
            version = result.first()
            print(f"✅ Conectado a MySQL versión: {version}")
            
            # También probar acceso a la base de datos
            result = session.exec(text("SELECT DATABASE()"))
            db_name = result.first()
            print(f"📊 Base de datos actual: {db_name}")
            
            return True
    except Exception as e:
        print(f"❌ Error de conexión: {str(e)}")
        
        # Diagnóstico detallado
        print("\n🔍 DIAGNÓSTICO:")
        
        # 1. Verificar hostname
        print(f"   1. Hostname: {MYSQL_CONFIG['host']}")
        
        # 2. Verificar puerto
        print(f"   2. Puerto: {MYSQL_CONFIG['port']}")
        
        # 3. Verificar usuario
        print(f"   3. Usuario: {MYSQL_CONFIG['username']}")
        
        # 4. Verificar base de datos
        print(f"   4. Base de datos: {MYSQL_CONFIG['database']}")
        
        # 5. Sugerir prueba manual
        print("\n🧪 Prueba manual con:")
        print(f'   mysql -h {MYSQL_CONFIG["host"]} -P {MYSQL_CONFIG["port"]} \\')
        print(f'   -u {MYSQL_CONFIG["username"]} -p {MYSQL_CONFIG["database"]}')
        
        return False


# Resto del archivo igual al anterior...
def get_database_info():
    """Obtiene información sobre la base de datos"""
    try:
        with Session(engine) as session:
            result = session.exec(text("SHOW TABLES"))
            tables = [row[0] for row in result.fetchall()]
            
            return {
                "database": MYSQL_CONFIG['database'],
                "tables": tables,
                "connection": "✅ Activa",
                "host": MYSQL_CONFIG['host']
            }
    except Exception as e:
        return {
            "error": str(e),
            "connection": "❌ Fallida",
            "host": MYSQL_CONFIG['host']
        }