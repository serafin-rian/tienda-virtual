from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

# ======================================================
# 👤 Modelo Usuario
# ======================================================
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    is_superuser: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    role: str = Field(default="client")  # "admin" o "client"

    # Relación con productos
    products: List["Product"] = Relationship(back_populates="owner")

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
# 📝 Modelo Historial (Auditoría) - 🔥 AGREGAR ESTO
# ======================================================
class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    action: str  # "DELETE_USER", "DELETE_PRODUCT", etc.
    target_id: int  # ID del elemento eliminado
    target_name: str  # Nombre del elemento eliminado
    performed_by: str  # Usuario que realizó la acción
    performed_at: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[str] = None  # Información adicional