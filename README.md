 
Tienda Virtual - Proyecto Académico
Descripción del Proyecto
Sistema de comercio electrónico completo desarrollado con FastAPI (backend) y MaterializeCSS (frontend), integrando Desarrollo de Software con Análisis de Algoritmos. El proyecto incluye gestión de productos, carrito de compras, sistema de usuarios, envíos y algoritmos personalizados.

Características Principales:
✅ Sin autenticación requerida - Todos los endpoints son accesibles libremente

✅ Interfaz web completa - Templates HTML con MaterializeCSS

✅ API RESTful completa - Documentación automática con Swagger

✅ Base de datos SQLite - Persistencia de datos con SQLModel

✅ Sistema de carrito de compras - Con checkout completo

✅ Gestión de usuarios - Roles: admin, vendor, customer

✅ Sistema de envíos - Seguimiento de paquetes y etiquetas

✅ Algoritmos integrados - QuickSort, MergeSort, Greedy

✅ Subida de imágenes - Procesamiento automático de thumbnails

✅ Panel de vendedor - Dashboard con estadísticas


Estructura del Proyecto
```markdown
# Estructura del Proyecto

## Raíz (`app/`)

- `main.py` – Punto de entrada principal
- `database.py` – Configuración de base de datos
- `auth.py` – Funciones de autenticación
- `models.py` – Modelos SQLModel
- `permissions.py` – Sistema de permisos por roles

## Directorio `utils/`
- `images.py` – Utilidades para procesar imágenes
- `algoritmos/` – Implementaciones de algoritmos
  - `router.py`
  - `sorting.py` – QuickSort y MergeSort
  - `greedy.py` – Algoritmo voraz

## Directorio `routers/` (Endpoints de la API)
- `auth_router.py` – Registro de usuarios
- `users.py` – Gestión de usuarios
- `products.py` – Productos CRUD
- `cart.py` – Carrito de compras
- `orders.py` – Gestión de pedidos
- `vendors.py` – Panel de vendedor
- `addresses.py` – Direcciones de envío
- `shipping.py` – Sistema de envíos
- `audit.py` – Historial de auditoría
- `shipping_service.py` – Lógica de negocio envíos

## Directorio `templates/` (Plantillas HTML)
- `base.html` – Layout base
- `index.html` – Página principal
- `login_simple.html` – Página de acceso
- `register.html` – Registro de usuarios
- `usuarios.html` – Lista de usuarios
- `profile.html` – Perfil de usuario
- `algorithms.html` – Prueba de algoritmos

### Subdirectorios de plantillas:
- `products/`
  - `list.html` – Catálogo
  - `create.html` – Crear producto
  - `cart.html` – Carrito de compras
- `shipping/`
  - `track.html` – Seguimiento
- `vendors/`
  - `dashboard.html`

## Directorio `static/`
- `js/auth.js` – Gestión de autenticación (simplificado)

## Directorio `uploads/`
- Imágenes subidas



# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

Paso 4: Acceder a la Aplicación
 Aplicación Web: http://localhost:8000

 Documentación API: http://localhost:8000/docs

 API alternativa: http://localhost:8000/redoc

Base de Datos - Modelos SQLModel

Tablas Principales:
👤 User - Usuarios del sistema
id: int (PK)
username: str (unique)
hashed_password: str
role: str = "customer"  # admin, vendor, customer
is_superuser: bool = False
created_at: datetime

🛍️ Product - Productos en venta
id: int (PK)
name: str
description: str (optional)
price: float
quantity: int
image_url: str (optional)
weight_kg: float (optional)
requires_shipping: bool = True
owner_id: int (FK → User.id)  # Vendedor
created_at: datetime

🛒 Cart - Carrito de compras
id: int (PK)
user_id: int (FK → User.id)
created_at: datetime
updated_at: datetime

📦 Order - Pedidos realizados
id: int (PK)
user_id: int (FK → User.id)
order_number: str (unique)
total_amount: float
status: str = "pending"  # pending, confirmed, shipped, delivered, cancelled
shipping_address_text: str (optional)
shipping_cost: float = 0.0
created_at: datetime

📍ShippingAddress - Direcciones de envío
id: int (PK)
user_id: int (FK → User.id)
full_name: str
address_line1: str
city: str
postal_code: str
country: str = "ES"

🔌 Endpoints de la API

🔐 Autenticación y Usuarios
Método	Endpoint	Descripción	Acceso
POST	/auth/register	Crear nuevo usuario	Público
GET	/users	Listar todos los usuarios	Público
GET	/users/{user_id}	Obtener usuario específico	Público
GET	/users/search	Buscar usuarios	Público
GET	/users/stats	Estadísticas de usuarios	Público
PUT	/users/{user_id}	Actualizar usuario	Público
DELETE	/users/{user_id}	Eliminar usuario	Público
🛍️ Productos
Método	Endpoint	Descripción	Acceso
POST	/products/create	Crear nuevo producto	Público
GET	/products/list	Listar todos los productos	Público
GET	/products/all	Productos con paginación	Público
GET	/products/search	Búsqueda avanzada	Público
GET	/products/featured	Productos destacados	Público
GET	/products/{product_id}	Obtener producto específico	Público
PUT	/products/{product_id}	Actualizar producto	Público
DELETE	/products/{product_id}	Eliminar producto	Público
POST	/products/{product_id}/upload-image	Subir imagen	Público
DELETE	/products/{product_id}/image	Eliminar imagen	Público
🛒 Carrito de Compras
Método	Endpoint	Descripción	Acceso
GET	/cart/	Obtener carrito del usuario	Público
GET	/cart/summary	Resumen del carrito	Público
GET	/cart/check-stock	Verificar disponibilidad	Público
POST	/cart/add/{product_id}	Agregar al carrito	Público
PUT	/cart/update/{product_id}	Actualizar cantidad	Público
DELETE	/cart/remove/{product_id}	Eliminar del carrito	Público
DELETE	/cart/clear	Vaciar carrito	Público
POST	/cart/checkout	Finalizar compra	Público
📦 Pedidos
Método	Endpoint	Descripción	Acceso
GET	/orders/my-orders	Mis pedidos	Usuario
GET	/orders/	Todos los pedidos (admin)	Admin
GET	/orders/{order_id}	Detalles del pedido	Usuario/Admin
PUT	/orders/{order_id}/status	Actualizar estado	Admin
PUT	/orders/{order_id}/cancel	Cancelar pedido	Usuario/Admin
POST	/orders/{order_id}/reorder	Reordenar pedido	Usuario
GET	/orders/stats/summary	Estadísticas	Admin/Vendor
🚚 Envíos
Método	Endpoint	Descripción	Acceso
POST	/shipping/addresses	Crear dirección	Usuario
GET	/shipping/addresses	Mis direcciones	Usuario
GET	/shipping/addresses/{address_id}	Obtener dirección	Usuario
PUT	/shipping/addresses/{address_id}	Actualizar dirección	Usuario
DELETE	/shipping/addresses/{address_id}	Eliminar dirección	Usuario
GET	/shipping/methods	Métodos de envío	Público
POST	/shipping/calculate	Calcular costo envío	Público
POST	/shipping/orders/{order_id}/shipments	Crear envío	Vendor/Admin
GET	/shipping/shipments	Listar envíos	Vendor/Admin
GET	/shipping/track/{tracking_number}	Rastrear envío	Usuario
PUT	/shipping/shipments/{shipment_id}/status	Actualizar estado	Vendor/Admin
📍 Direcciones
Método	Endpoint	Descripción	Acceso
GET	/addresses/me	Mis direcciones	Usuario
GET	/addresses/{address_id}	Obtener dirección	Usuario
POST	/addresses/	Crear dirección	Usuario
PUT	/addresses/{address_id}	Actualizar dirección	Usuario
DELETE	/addresses/{address_id}	Eliminar dirección	Usuario
POST	/addresses/{address_id}/set-default	Establecer predeterminada	Usuario
POST	/addresses/validate	Validar dirección	Público
🏪 Panel de Vendedor
Método	Endpoint	Descripción	Acceso
GET	/vendors/dashboard	Dashboard principal	Vendor
GET	/vendors/sales	Reporte de ventas	Vendor
GET	/vendors/inventory	Gestión de inventario	Vendor
GET	/vendors/customers	Clientes del vendedor	Vendor
GET	/vendors/products/sales-stats	Estadísticas por producto	Vendor
POST	/vendors/inventory/sync	Sincronizar inventario	Vendor
🧮 Algoritmos
Método	Endpoint	Descripción	Parámetros
GET	/algorithms/sort	Ordenar productos	`method=quicksort	mergesort,by=price	name	quantity,steps=true	false`
GET	/algorithms/greedy/best-products	Selección voraz de productos	budget=float (presupuesto)
📊 Auditoría
Método	Endpoint	Descripción	Acceso
GET	/audit/history	Historial completo	Admin
GET	/audit/search	Búsqueda avanzada	Admin
GET	/audit/stats	Estadísticas	Admin
GET	/audit/user/{username}	Acciones por usuario	Admin
DELETE	/audit/cleanup	Limpiar registros antiguos	Super Admin
🌐 Páginas Web Disponibles
Página	URL	Descripción
🏠 Inicio	/	Página principal con características
🛍️ Catálogo	/catalogo	Lista de productos para comprar
➕ Crear Producto	/crear-producto	Formulario para agregar productos
📊 Panel Vendedor	/panel	Dashboard para vendedores
🛒 Mi Carrito	/mi-carrito	Carrito de compras
📦 Mis Pedidos	/mis-pedidos	Historial de pedidos
🚚 Seguimiento	/seguimiento	Rastreo de envíos
👥 Usuarios	/usuarios	Lista de usuarios registrados
📝 Registro	/registro	Crear nueva cuenta
🔐 Acceder	/acceder	Información de acceso
🧮 Algoritmos	/algoritmos	Prueba de algoritmos
👤 Perfil	/perfil	Perfil de usuario

🎭 Roles de Usuario
👑 Administrador (admin)
Acceso completo a todas las funciones

Puede gestionar usuarios

Puede ver todas las órdenes

Puede eliminar cualquier producto

🏪 Vendedor (vendor)
Puede crear y gestionar sus propios productos

Puede ver sus ventas y estadísticas

Tiene acceso al panel de vendedor

Puede gestionar inventario

👤 Cliente (customer)
Puede comprar productos

Tiene carrito de compras

Puede ver su historial de pedidos

Puede gestionar direcciones de envío


🎭 Roles de Usuario
👑 Administrador (admin)
Acceso completo a todas las funciones

Puede gestionar usuarios

Puede ver todas las órdenes

Puede eliminar cualquier producto

🏪 Vendedor (vendor)
Puede crear y gestionar sus propios productos

Puede ver sus ventas y estadísticas

Tiene acceso al panel de vendedor

Puede gestionar inventario

👤 Cliente (customer)
Puede comprar productos

Tiene carrito de compras

Puede ver su historial de pedidos

Puede gestionar direcciones de envío


