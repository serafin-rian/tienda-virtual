# test_connection.py
import socket
import pymysql
from pymysql.constants import CLIENT

def test_dns():
    """Prueba la resolución DNS"""
    hostname = "b9maju0nm8eaq2enhzhd-mysql.services.clever-cloud.com"
    
    try:
        print(f"🔍 Resolviendo DNS para: {hostname}")
        ip_address = socket.gethostbyname(hostname)
        print(f"✅ DNS resuelto: {hostname} → {ip_address}")
        return ip_address
    except socket.gaierror as e:
        print(f"❌ Error DNS: {e}")
        print("Posibles soluciones:")
        print("1. Verifica tu conexión a internet")
        print("2. Cambia servidores DNS (usa Google DNS: 8.8.8.8)")
        print("3. El hostname podría ser incorrecto")
        return None

def test_mysql_connection():
    """Prueba conexión directa a MySQL"""
    config = {
        'host': 'b9maju0nm8eaq2enhzhd-mysql.services.clever-cloud.com',
        'port': 3306,
        'user': 'uwfhtgrqz7c8pjdg',
        'password': '3fAP9h7uGC22092N02mm',
        'database': 'b9maju0nm8eaq2enhzhd',
        'client_flag': CLIENT.MULTI_STATEMENTS,
        'connect_timeout': 10
    }
    
    try:
        print("\n🔌 Intentando conexión MySQL...")
        connection = pymysql.connect(**config)
        print("✅ ¡Conexión MySQL exitosa!")
        
        # Probar consulta simple
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"📊 Versión MySQL: {version[0]}")
            
            # Verificar tablas
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"📊 Tablas existentes: {len(tables)}")
            
        connection.close()
        return True
    except pymysql.MySQLError as e:
        print(f"❌ Error MySQL: {e}")
        return False
    except Exception as e:
        print(f"❌ Error general: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 PRUEBA DE CONEXIÓN MYSQL CLEVER CLOUD")
    print("=" * 60)
    
    # Paso 1: DNS
    ip = test_dns()
    
    # Paso 2: Conexión MySQL (solo si DNS funciona)
    if ip:
        test_mysql_connection()
    
    print("\n" + "=" * 60)