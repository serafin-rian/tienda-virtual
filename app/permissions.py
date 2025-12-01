from typing import Optional
from .models import User, Product, Order, OrderItem

# ======================================================
# 🎯 PERMISOS PARA PRODUCTOS
# ======================================================
class ProductPermissions:
    @staticmethod
    def can_create_product(user: User) -> bool:
        """Verifica si el usuario puede crear productos"""
        return user.role in ["admin", "vendor"]
    
    @staticmethod
    def can_view_product(user: User, product: Product) -> bool:
        """Verifica si el usuario puede ver un producto"""
        # Todos pueden ver productos públicos
        return True
    
    @staticmethod
    def can_edit_product(user: User, product: Product) -> bool:
        """Verifica si el usuario puede editar un producto"""
        if user.role == "admin":
            return True
        if user.role == "vendor" and product.owner_id == user.id:
            return True
        return False
    
    @staticmethod
    def can_delete_product(user: User, product: Product) -> bool:
        """Verifica si el usuario puede eliminar un producto"""
        return ProductPermissions.can_edit_product(user, product)
    
    @staticmethod
    def can_update_stock(user: User, product: Product) -> bool:
        """Verifica si el usuario puede actualizar el stock"""
        return ProductPermissions.can_edit_product(user, product)

# ======================================================
# 🛒 PERMISOS PARA CARRITO
# ======================================================
class CartPermissions:
    @staticmethod
    def can_view_cart(user: User, cart_user_id: int) -> bool:
        """Verifica si el usuario puede ver un carrito"""
        if user.role == "admin":
            return True
        return user.id == cart_user_id
    
    @staticmethod
    def can_modify_cart(user: User, cart_user_id: int) -> bool:
        """Verifica si el usuario puede modificar un carrito"""
        return CartPermissions.can_view_cart(user, cart_user_id)

# ======================================================
# 📦 PERMISOS PARA ÓRDENES
# ======================================================
class OrderPermissions:
    @staticmethod
    def can_view_order(user: User, order: Order) -> bool:
        """Verifica si el usuario puede ver una orden"""
        if user.role == "admin":
            return True
        if user.role == "vendor":
            # Verificar si la orden contiene productos del vendedor
            return True  # Se implementará en el endpoint
        return user.id == order.user_id
    
    @staticmethod
    def can_update_order_status(user: User, order: Order) -> bool:
        """Verifica si el usuario puede actualizar el estado de una orden"""
        return user.role == "admin"
    
    @staticmethod
    def can_cancel_order(user: User, order: Order) -> bool:
        """Verifica si el usuario puede cancelar una orden"""
        if user.role == "admin":
            return True
        if user.id == order.user_id and order.status in ["pending", "confirmed"]:
            return True
        return False

# ======================================================
# 👥 PERMISOS PARA USUARIOS
# ======================================================
class UserPermissions:
    @staticmethod
    def can_view_user(user: User, target_user_id: int) -> bool:
        """Verifica si el usuario puede ver otro usuario"""
        if user.role == "admin":
            return True
        return user.id == target_user_id
    
    @staticmethod
    def can_edit_user(user: User, target_user_id: int) -> bool:
        """Verifica si el usuario puede editar otro usuario"""
        return UserPermissions.can_view_user(user, target_user_id)
    
    @staticmethod
    def can_delete_user(user: User, target_user_id: int) -> bool:
        """Verifica si el usuario puede eliminar otro usuario"""
        return user.role == "admin"
    
    @staticmethod
    def can_change_user_role(user: User) -> bool:
        """Verifica si el usuario puede cambiar roles"""
        return user.role == "admin"

# ======================================================
# 📊 PERMISOS PARA ESTADÍSTICAS
# ======================================================
class StatsPermissions:
    @staticmethod
    def can_view_sales_stats(user: User) -> bool:
        """Verifica si el usuario puede ver estadísticas de ventas"""
        return user.role in ["admin", "vendor"]
    
    @staticmethod
    def can_view_user_stats(user: User) -> bool:
        """Verifica si el usuario puede ver estadísticas de usuarios"""
        return user.role == "admin"
    
    @staticmethod
    def can_view_system_stats(user: User) -> bool:
        """Verifica si el usuario puede ver estadísticas del sistema"""
        return user.role == "admin"

# ======================================================
# 🏪 PERMISOS PARA VENDEDORES
# ======================================================
class VendorPermissions:
    @staticmethod
    def can_view_vendor_dashboard(user: User) -> bool:
        """Verifica si el usuario puede ver el dashboard de vendedor"""
        return user.role in ["admin", "vendor"]
    
    @staticmethod
    def can_view_vendor_sales(user: User, vendor_id: int) -> bool:
        """Verifica si el usuario puede ver las ventas de un vendedor"""
        if user.role == "admin":
            return True
        return user.role == "vendor" and user.id == vendor_id
    
    @staticmethod
    def can_view_vendor_customers(user: User, vendor_id: int) -> bool:
        """Verifica si el usuario puede ver los clientes de un vendedor"""
        return VendorPermissions.can_view_vendor_sales(user, vendor_id)
    
    @staticmethod
    def can_view_vendor_inventory(user: User, vendor_id: int) -> bool:
        """Verifica si el usuario puede ver el inventario de un vendedor"""
        return VendorPermissions.can_view_vendor_sales(user, vendor_id)

# ======================================================
# 🔐 VERIFICADOR DE PERMISOS CENTRALIZADO
# ======================================================
class PermissionChecker:
    """Clase central para verificar todos los permisos"""
    
    @staticmethod
    def check(has_permission: bool, error_message: str = "No tienes permisos"):
        """Verifica un permiso y lanza excepción si no se cumple"""
        if not has_permission:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail=error_message)
    
    @staticmethod
    def check_product_create(user: User):
        """Verifica si el usuario puede crear productos"""
        PermissionChecker.check(
            ProductPermissions.can_create_product(user),
            "Solo administradores y vendedores pueden crear productos"
        )
    
    @staticmethod
    def check_product_edit(user: User, product: Product):
        """Verifica si el usuario puede editar un producto"""
        PermissionChecker.check(
            ProductPermissions.can_edit_product(user, product),
            "No tienes permisos para editar este producto. Solo administradores o el vendedor dueño pueden editarlo."
        )
    
    @staticmethod
    def check_product_delete(user: User, product: Product):
        """Verifica si el usuario puede eliminar un producto"""
        PermissionChecker.check(
            ProductPermissions.can_delete_product(user, product),
            "No tienes permisos para eliminar este producto. Solo administradores o el vendedor dueño pueden eliminarlo."
        )
    
    @staticmethod
    def check_cart_view(user: User, cart_user_id: int):
        """Verifica si el usuario puede ver un carrito"""
        PermissionChecker.check(
            CartPermissions.can_view_cart(user, cart_user_id),
            "No tienes permisos para ver este carrito"
        )
    
    @staticmethod
    def check_order_view(user: User, order: Order):
        """Verifica si el usuario puede ver una orden"""
        PermissionChecker.check(
            OrderPermissions.can_view_order(user, order),
            "No tienes permisos para ver esta orden"
        )
    
    @staticmethod
    def check_order_status_update(user: User, order: Order):
        """Verifica si el usuario puede actualizar el estado de una orden"""
        PermissionChecker.check(
            OrderPermissions.can_update_order_status(user, order),
            "Solo administradores pueden actualizar el estado de las órdenes"
        )
    
    @staticmethod
    def check_vendor_dashboard(user: User):
        """Verifica si el usuario puede ver el dashboard de vendedor"""
        PermissionChecker.check(
            VendorPermissions.can_view_vendor_dashboard(user),
            "Solo administradores y vendedores pueden ver el dashboard"
        )
    
    @staticmethod
    def check_vendor_sales(user: User, vendor_id: int):
        """Verifica si el usuario puede ver las ventas de un vendedor"""
        PermissionChecker.check(
            VendorPermissions.can_view_vendor_sales(user, vendor_id),
            "No tienes permisos para ver las ventas de este vendedor"
        )

# ======================================================
# 🎭 DECORADORES PARA PERMISOS
# ======================================================
def require_role(*allowed_roles: str):
    """Decorador para verificar que el usuario tiene uno de los roles permitidos"""
    from functools import wraps
    from fastapi import Depends, HTTPException
    from .routers.auth_router import get_current_user
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: User = Depends(get_current_user), **kwargs):
            if current_user.role not in allowed_roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Se requiere uno de los siguientes roles: {', '.join(allowed_roles)}"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

def require_admin(func):
    """Decorador para verificar que el usuario es administrador"""
    return require_role("admin")(func)

def require_vendor(func):
    """Decorador para verificar que el usuario es vendedor"""
    return require_role("vendor")(func)

def require_admin_or_vendor(func):
    """Decorador para verificar que el usuario es admin o vendedor"""
    return require_role("admin", "vendor")(func)

def require_customer(func):
    """Decorador para verificar que el usuario es cliente"""
    return require_role("customer")(func)