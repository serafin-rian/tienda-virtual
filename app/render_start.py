# render_start.py - ARCHIVO ESPECÍFICO PARA RENDER
import os
import sys
import uvicorn

def main():
    """Punto de entrada específico para Render"""
    print("=" * 60)
    print("🚀 TIENDA VIRTUAL - INICIO EN RENDER")
    print("=" * 60)
    
    # Obtener puerto de Render (IMPORTANTE)
    port = int(os.environ.get("PORT", 10000))
    
    print(f"🔧 Configuración:")
    print(f"   Host: 0.0.0.0")
    print(f"   Puerto: {port}")
    print(f"   App: app.main:app")
    print(f"   Directorio actual: {os.getcwd()}")
    print(f"   Archivos en directorio: {os.listdir('.')[:5]}")
    print("=" * 60)
    
    # Verificar que app existe
    if not os.path.exists("app"):
        print("❌ ERROR: No existe carpeta 'app'")
        print("   Directorio actual:", os.listdir('.'))
        sys.exit(1)
    
    # Iniciar Uvicorn CONFIGURADO PARA RENDER
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",      # CRÍTICO: 0.0.0.0, no localhost
        port=port,           # Usar puerto de Render
        reload=False,        # No reload en producción
        log_level="info",
        access_log=True,
        workers=1
    )

if __name__ == "__main__":
    main()
