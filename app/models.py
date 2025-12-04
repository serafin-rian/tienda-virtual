from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from enum import Enum

# ======================================================
# 📦 ENUMS PARA EL SISTEMA DE ENVÍOS
# ======================================================
class ShippingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY_FOR_PICKUP = "ready_for_pickup"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED_ATTEMPT = "failed_attempt"
    RETURNED = "returned"
    CANCELLED = "cancelled"

class ShippingMethod(str, Enum):
    STANDARD = "standard"
    EXPRESS = "express"
    NEXT_DAY = "next_day"
    SAME_DAY = "same_day"
    PICKUP_STORE = "pickup_store"
    INTERNATIONAL = "international"

class Carrier(str, Enum):
    DHL = "dhl"
    UPS = "ups"
    FEDEX = "fedex"
    USPS = "usps"
    CORREOS = "correos"
    SEUR = "seur"
    MRW = "mrw"
    LOCAL = "local"
    OWN = "own"

# ======================================================
# 👤 Modelo Usuario
# ======================================================
class User(SQLModel, table=True, extend_existing=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    is_superuser: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    role: str = Field(default="customer")

    # Relaciones
    products: List["Product"] = Relationship(back_populates="owner")
    carts: List["Cart"] = Relationship(back_populates="user")
    orders: List["Order"] = Relationship(back_populates="user")
    shipping_addresses: List["ShippingAddress"] = Relationship(back_populates="user")

# ======================================================
# 🛍️ Modelo Producto / Objeto Virtual
# ======================================================
class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    price: float
    quantity: int = Field(default=0)
    
    # Campos de imagen mejorados
    image_filename: Optional[str] = None
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Información de envío del producto
    weight_kg: Optional[float] = Field(default=None)  # IMPORTANTE: Acepta None
    dimensions_cm: Optional[str] = None
    requires_shipping: bool = Field(default=True)

    # Relación con el usuario dueño
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")
    owner: Optional[User] = Relationship(back_populates="products")
    
    # Campo para actualización
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

# ======================================================
# 📝 Modelo Historial (Auditoría)
# ======================================================
class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    action: str
    target_id: int
    target_name: str
    performed_by: str
    performed_at: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[str] = None

# ======================================================
# 🛒 MODELOS PARA CARRITO Y ÓRDENES
# ======================================================

class Cart(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    user: User = Relationship(back_populates="carts")
    items: List["CartItem"] = Relationship(back_populates="cart")

class CartItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    cart_id: int = Field(foreign_key="cart.id")
    product_id: int = Field(foreign_key="product.id")
    quantity: int = Field(default=1, ge=1)
    added_at: datetime = Field(default_factory=datetime.utcnow)
    
    cart: Cart = Relationship(back_populates="items")
    product: Product = Relationship()

class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    order_number: str = Field(unique=True, index=True)
    total_amount: float = Field(default=0.0, ge=0)
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    shipping_address_text: Optional[str] = None
    shipping_method_name: Optional[str] = None
    shipping_cost: float = Field(default=0.0, ge=0)
    requires_shipping: bool = Field(default=True)
    
    shipping_address: Optional[str] = None
    payment_method: Optional[str] = None
    
    user: User = Relationship(back_populates="orders")
    items: List["OrderItem"] = Relationship(back_populates="order")
    shipments: List["Shipment"] = Relationship(back_populates="order")

class OrderItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id")
    product_id: int = Field(foreign_key="product.id")
    product_name: str
    product_price: float
    quantity: int = Field(ge=1)
    subtotal: float = Field(ge=0)
    
    order: Order = Relationship(back_populates="items")
    product: Product = Relationship()

# ======================================================
# 📍 MODELOS PARA SISTEMA DE ENVÍOS
# ======================================================

class ShippingAddress(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    
    full_name: str
    phone_number: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state_province: str
    postal_code: str
    country: str = Field(default="ES")
    
    is_default: bool = Field(default=False)
    instructions: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    user: User = Relationship(back_populates="shipping_addresses")
    shipments: List["Shipment"] = Relationship(back_populates="address")

class ShippingMethodConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    code: ShippingMethod = Field(default=ShippingMethod.STANDARD)
    carrier: Carrier = Field(default=Carrier.LOCAL)
    
    base_cost: float = Field(default=0.0, ge=0)
    cost_per_kg: Optional[float] = Field(default=None, ge=0)
    min_weight_kg: float = Field(default=0.0, ge=0)
    max_weight_kg: Optional[float] = Field(default=None, ge=0)
    
    estimated_days_min: int = Field(default=3, ge=1)
    estimated_days_max: int = Field(default=5, ge=1)
    
    available_countries: Optional[str] = None
    is_active: bool = Field(default=True)
    requires_signature: bool = Field(default=False)
    has_tracking: bool = Field(default=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Shipment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id")
    shipping_address_id: int = Field(foreign_key="shippingaddress.id")
    shipping_method_id: Optional[int] = Field(default=None, foreign_key="shippingmethodconfig.id")
    
    tracking_number: Optional[str] = Field(default=None, unique=True, index=True)
    carrier: Carrier = Field(default=Carrier.LOCAL)
    status: ShippingStatus = Field(default=ShippingStatus.PENDING)
    
    weight_kg: Optional[float] = Field(default=None, ge=0)
    dimensions: Optional[str] = None
    package_count: int = Field(default=1, ge=1)
    
    shipping_cost: float = Field(default=0.0, ge=0)
    insurance_cost: float = Field(default=0.0, ge=0)
    total_cost: float = Field(default=0.0, ge=0)
    
    estimated_delivery_start: Optional[datetime] = None
    estimated_delivery_end: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    
    tracking_url: Optional[str] = None
    last_tracking_update: Optional[datetime] = None
    tracking_events_json: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    order: Order = Relationship(back_populates="shipments")
    address: ShippingAddress = Relationship(back_populates="shipments")
    shipping_method: Optional[ShippingMethodConfig] = Relationship()
    labels: List["ShippingLabel"] = Relationship(back_populates="shipment")

class ShippingLabel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    shipment_id: int = Field(foreign_key="shipment.id")
    
    label_url: Optional[str] = None
    label_data: Optional[str] = None
    format: str = Field(default="PDF")
    
    invoice_url: Optional[str] = None
    customs_document_url: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    shipment: Shipment = Relationship(back_populates="labels")