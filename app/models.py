from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

# ======================================================
# 👤 Modelo Usuario - SOLO UNA VEZ
# ======================================================
class User(SQLModel, table=True, extend_existing=True):  # ✅ Agregar extend_existing
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    is_superuser: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    role: str = Field(default="customer")  # "admin", "vendor", "customer"

    # Relación con productos
    products: List["Product"] = Relationship(back_populates="owner")
    
    # 🔥 NUEVAS RELACIONES para FASE 2
    carts: List["Cart"] = Relationship(back_populates="user")
    orders: List["Order"] = Relationship(back_populates="user")

# ======================================================
# 🛍️ Modelo Producto / Objeto Virtual
# ======================================================
class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    price: float
    quantity: int = Field(default=0)
    image_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relación con el usuario dueño
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")
    owner: Optional[User] = Relationship(back_populates="products")

# ======================================================
# 📝 Modelo Historial (Auditoría)
# ======================================================
class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    action: str  # "DELETE_USER", "DELETE_PRODUCT", etc.
    target_id: int  # ID del elemento eliminado
    target_name: str  # Nombre del elemento eliminado
    performed_by: str  # Usuario que realizó la acción
    performed_at: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[str] = None  # Información adicional

# ======================================================
# 🛒 MODELOS PARA CARRITO Y ÓRDENES
# ======================================================

# ======================================================
# 🛍️ Carrito de Compras
# ======================================================
class Cart(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relaciones
    user: User = Relationship(back_populates="carts")
    items: List["CartItem"] = Relationship(back_populates="cart")

# ======================================================
# 📦 Item del Carrito
# ======================================================
class CartItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    cart_id: int = Field(foreign_key="cart.id")
    product_id: int = Field(foreign_key="product.id")
    quantity: int = Field(default=1, ge=1)
    added_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relaciones
    cart: Cart = Relationship(back_populates="items")
    product: Product = Relationship()

# ======================================================
# 📋 Orden de Compra
# ======================================================
class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    order_number: str = Field(unique=True, index=True)
    total_amount: float = Field(default=0.0, ge=0)
    status: str = Field(default="pending")  # pending, confirmed, shipped, delivered, cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    shipping_address: Optional[str] = None
    payment_method: Optional[str] = None
    
    # Relaciones
    user: User = Relationship(back_populates="orders")
    items: List["OrderItem"] = Relationship(back_populates="order")

# ======================================================
# 📝 Item de la Orden
# ======================================================
class OrderItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id")
    product_id: int = Field(foreign_key="product.id")
    product_name: str  # Guardamos nombre por si el producto se elimina
    product_price: float  # Guardamos precio al momento de la compra
    quantity: int = Field(ge=1)
    subtotal: float = Field(ge=0)
    
    # Relaciones
    order: Order = Relationship(back_populates="items")
    product: Product = Relationship()