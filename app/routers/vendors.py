from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Dict, Any
from datetime import datetime, timedelta
from ..database import get_session
from ..models import User, Product, Order, OrderItem, Cart, CartItem
from .auth_router import get_current_user

router = APIRouter(prefix="/vendors", tags=["vendors"])

# ======================================================
# 🔐 VERIFICAR SI ES VENDEDOR
# ======================================================
def get_vendor_user(current_user: User = Depends(get_current_user)):
    """Verifica que el usuario actual sea vendedor"""
    if current_user.role != "vendor":
        raise HTTPException(
            status_code=403, 
            detail="Se requieren permisos de vendedor"
        )
    return current_user

# ======================================================
# 📊 PANEL DE CONTROL DEL VENDEDOR
# ======================================================
@router.get("/dashboard")
def vendor_dashboard(
    days: int = Query(30, description="Estadísticas de últimos X días"),
    session: Session = Depends(get_session),
    vendor_user: User = Depends(get_vendor_user)
):
    """Panel de control principal para vendedores"""
    # Obtener productos del vendedor
    products = session.exec(
        select(Product).where(Product.owner_id == vendor_user.id)
    ).all()
    
    # Obtener todas las órdenes
    all_orders = session.exec(select(Order)).all()
    
    # Filtrar órdenes que contienen productos del vendedor
    vendor_orders = []
    vendor_revenue = 0
    vendor_items_sold = 0
    
    for order in all_orders:
        order_items = session.exec(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).all()
        
        # Verificar si la orden contiene productos del vendedor
        for item in order_items:
            product = session.get(Product, item.product_id)
            if product and product.owner_id == vendor_user.id:
                vendor_orders.append(order)
                vendor_revenue += item.subtotal
                vendor_items_sold += item.quantity
                break  # Solo contar la orden una vez
    
    # Calcular fechas para estadísticas recientes
    recent_date = datetime.utcnow() - timedelta(days=days)
    recent_orders = [o for o in vendor_orders if o.created_at >= recent_date]
    recent_revenue = sum(
        sum(item.subtotal for item in session.exec(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).all() if session.get(Product, item.product_id).owner_id == vendor_user.id)
        for order in recent_orders
    )
    
    # Productos más vendidos
    product_sales: Dict[int, Dict[str, Any]] = {}
    for order in vendor_orders:
        order_items = session.exec(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).all()
        
        for item in order_items:
            product = session.get(Product, item.product_id)
            if product and product.owner_id == vendor_user.id:
                if product.id not in product_sales:
                    product_sales[product.id] = {
                        "product_id": product.id,
                        "product_name": product.name,
                        "units_sold": 0,
                        "revenue": 0
                    }
                product_sales[product.id]["units_sold"] += item.quantity
                product_sales[product.id]["revenue"] += item.subtotal
    
    top_products = sorted(
        product_sales.values(), 
        key=lambda x: x["units_sold"], 
        reverse=True
    )[:5]
    
    return {
        "vendor_info": {
            "id": vendor_user.id,
            "username": vendor_user.username,
            "joined_date": vendor_user.created_at,
            "total_products": len(products)
        },
        "sales_overview": {
            "total_orders": len(vendor_orders),
            "total_revenue": round(vendor_revenue, 2),
            "total_items_sold": vendor_items_sold,
            "recent_orders": len(recent_orders),
            "recent_revenue": round(recent_revenue, 2)
        },
        "inventory_overview": {
            "total_products": len(products),
            "products_in_stock": sum(1 for p in products if p.quantity > 0),
            "products_out_of_stock": sum(1 for p in products if p.quantity == 0),
            "low_stock_products": sum(1 for p in products if 0 < p.quantity < 10),
            "total_inventory_value": round(sum(p.price * p.quantity for p in products), 2)
        },
        "top_products": top_products,
        "recent_activity": {
            "last_order_date": max(vendor_orders, key=lambda x: x.created_at).created_at if vendor_orders else None,
            "recent_period": f"Últimos {days} días",
            "recent_growth": f"+{len(recent_orders)} órdenes"
        }
    }

# ======================================================
# 📈 VENTAS DEL VENDEDOR
# ======================================================
@router.get("/sales")
def vendor_sales(
    start_date: str = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: str = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    session: Session = Depends(get_session),
    vendor_user: User = Depends(get_vendor_user)
):
    """Reporte de ventas detallado del vendedor"""
    # Obtener todas las órdenes
    all_orders = session.exec(select(Order)).all()
    
    # Filtrar por fecha si se especifica
    if start_date:
        start = datetime.fromisoformat(start_date)
        all_orders = [o for o in all_orders if o.created_at >= start]
    
    if end_date:
        end = datetime.fromisoformat(end_date)
        all_orders = [o for o in all_orders if o.created_at <= end]
    
    # Procesar ventas del vendedor
    sales_data = []
    total_revenue = 0
    total_items = 0
    
    for order in all_orders:
        order_items = session.exec(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).all()
        
        order_vendor_items = []
        order_vendor_revenue = 0
        order_vendor_items_count = 0
        
        for item in order_items:
            product = session.get(Product, item.product_id)
            if product and product.owner_id == vendor_user.id:
                order_vendor_items.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "quantity": item.quantity,
                    "price": item.product_price,
                    "subtotal": item.subtotal
                })
                order_vendor_revenue += item.subtotal
                order_vendor_items_count += item.quantity
        
        if order_vendor_items:
            sales_data.append({
                "order_id": order.id,
                "order_number": order.order_number,
                "order_date": order.created_at,
                "customer_id": order.user_id,
                "status": order.status,
                "items": order_vendor_items,
                "order_revenue": order_vendor_revenue,
                "items_count": order_vendor_items_count
            })
            
            total_revenue += order_vendor_revenue
            total_items += order_vendor_items_count
    
    return {
        "period": {
            "start_date": start_date,
            "end_date": end_date
        },
        "summary": {
            "total_orders": len(sales_data),
            "total_revenue": round(total_revenue, 2),
            "total_items_sold": total_items,
            "average_order_value": round(total_revenue / len(sales_data), 2) if sales_data else 0
        },
        "sales": sales_data
    }

# ======================================================
# 📦 INVENTARIO DEL VENDEDOR
# ======================================================
@router.get("/inventory")
def vendor_inventory(
    in_stock: bool = Query(None, description="Filtrar por stock"),
    low_stock: bool = Query(None, description="Solo productos con stock bajo (<10)"),
    sort_by: str = Query("name", description="Ordenar por: name, price, quantity, created_at"),
    order: str = Query("asc", description="Orden: asc o desc"),
    session: Session = Depends(get_session),
    vendor_user: User = Depends(get_vendor_user)
):
    """Gestión de inventario del vendedor"""
    query = select(Product).where(Product.owner_id == vendor_user.id)
    
    # Aplicar filtros
    if in_stock is not None:
        if in_stock:
            query = query.where(Product.quantity > 0)
        else:
            query = query.where(Product.quantity == 0)
    
    if low_stock:
        query = query.where(Product.quantity < 10).where(Product.quantity > 0)
    
    # Aplicar ordenamiento
    valid_sort_fields = ["name", "price", "quantity", "created_at"]
    if sort_by not in valid_sort_fields:
        sort_by = "name"
    
    order_by_field = getattr(Product, sort_by)
    if order == "desc":
        order_by_field = order_by_field.desc()
    
    query = query.order_by(order_by_field)
    
    products = session.exec(query).all()
    
    inventory_stats = {
        "total_products": len(products),
        "total_value": round(sum(p.price * p.quantity for p in products), 2),
        "in_stock": sum(1 for p in products if p.quantity > 0),
        "out_of_stock": sum(1 for p in products if p.quantity == 0),
        "low_stock": sum(1 for p in products if 0 < p.quantity < 10),
        "needs_restock": [p.name for p in products if p.quantity == 0]
    }
    
    return {
        "stats": inventory_stats,
        "products": products
    }

# ======================================================
# 👥 CLIENTES DEL VENDEDOR
# ======================================================
@router.get("/customers")
def vendor_customers(
    session: Session = Depends(get_session),
    vendor_user: User = Depends(get_vendor_user)
):
    """Clientes que han comprado productos del vendedor"""
    all_orders = session.exec(select(Order)).all()
    
    customers = {}
    
    for order in all_orders:
        order_items = session.exec(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).all()
        
        # Verificar si la orden contiene productos del vendedor
        has_vendor_products = False
        order_vendor_total = 0
        
        for item in order_items:
            product = session.get(Product, item.product_id)
            if product and product.owner_id == vendor_user.id:
                has_vendor_products = True
                order_vendor_total += item.subtotal
        
        if has_vendor_products:
            customer_id = order.user_id
            customer = session.get(User, customer_id)
            
            if customer_id not in customers:
                customers[customer_id] = {
                    "customer_id": customer_id,
                    "username": customer.username if customer else "Unknown",
                    "first_purchase": order.created_at,
                    "last_purchase": order.created_at,
                    "total_orders": 0,
                    "total_spent": 0,
                    "products_purchased": []
                }
            
            customers[customer_id]["total_orders"] += 1
            customers[customer_id]["total_spent"] += order_vendor_total
            customers[customer_id]["last_purchase"] = max(
                customers[customer_id]["last_purchase"], 
                order.created_at
            )
    
    # Convertir a lista y ordenar por total gastado
    customers_list = sorted(
        customers.values(), 
        key=lambda x: x["total_spent"], 
        reverse=True
    )
    
    return {
        "total_customers": len(customers_list),
        "top_customers": customers_list[:10],
        "total_revenue_from_customers": round(sum(c["total_spent"] for c in customers_list), 2)
    }

# ======================================================
# 📊 ESTADÍSTICAS DE VENTAS POR PRODUCTO
# ======================================================
@router.get("/products/sales-stats")
def vendor_products_sales_stats(
    days: int = Query(30, description="Período en días"),
    session: Session = Depends(get_session),
    vendor_user: User = Depends(get_vendor_user)
):
    """Estadísticas de ventas por producto"""
    # Obtener productos del vendedor
    products = session.exec(
        select(Product).where(Product.owner_id == vendor_user.id)
    ).all()
    
    # Período de tiempo
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    product_stats = []
    
    for product in products:
        # Obtener órdenes que contienen este producto
        order_items = session.exec(
            select(OrderItem).where(OrderItem.product_id == product.id)
        ).all()
        
        # Filtrar por período
        recent_items = [
            item for item in order_items 
            if session.get(Order, item.order_id).created_at >= cutoff_date
        ]
        
        total_sold = sum(item.quantity for item in order_items)
        recent_sold = sum(item.quantity for item in recent_items)
        total_revenue = sum(item.subtotal for item in order_items)
        recent_revenue = sum(item.subtotal for item in recent_items)
        
        product_stats.append({
            "product_id": product.id,
            "product_name": product.name,
            "current_price": product.price,
            "current_stock": product.quantity,
            "total_sold": total_sold,
            "total_revenue": round(total_revenue, 2),
            "recent_sold": recent_sold,
            "recent_revenue": round(recent_revenue, 2),
            "sell_through_rate": round((total_sold / (total_sold + product.quantity)) * 100, 2) if (total_sold + product.quantity) > 0 else 0,
            "needs_restock": product.quantity == 0,
            "low_stock": 0 < product.quantity < 10
        })
    
    # Ordenar por revenue reciente
    product_stats.sort(key=lambda x: x["recent_revenue"], reverse=True)
    
    return {
        "period_days": days,
        "total_products": len(products),
        "top_performing": product_stats[:5],
        "needs_attention": [
            p for p in product_stats 
            if p["needs_restock"] or p["low_stock"]
        ],
        "all_products_stats": product_stats
    }