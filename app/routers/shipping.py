from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from sqlmodel import Session, select, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import uuid

from ..database import get_session
from ..models import (
    User, Order, Shipment, ShippingAddress, ShippingMethodConfig,
    ShippingLabel, ShippingStatus, ShippingMethod, Carrier,
    Product, OrderItem
)
from .auth_router import get_current_user
from ..permissions import require_admin, require_admin_or_vendor, PermissionChecker

router = APIRouter(prefix="/shipping", tags=["shipping"])

# ======================================================
# 📍 DIRECCIONES DE ENVÍO
# ======================================================

@router.post("/addresses", response_model=ShippingAddress)
def create_shipping_address(
    full_name: str = Body(...),
    phone_number: str = Body(...),
    address_line1: str = Body(...),
    address_line2: Optional[str] = Body(None),
    city: str = Body(...),
    state_province: str = Body(...),
    postal_code: str = Body(...),
    country: str = Body("ES"),
    is_default: bool = Body(False),
    instructions: Optional[str] = Body(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Crea una nueva dirección de envío para el usuario"""
    # Si se marca como default, quitar default de otras direcciones
    if is_default:
        existing_defaults = session.exec(
            select(ShippingAddress)
            .where(ShippingAddress.user_id == current_user.id)
            .where(ShippingAddress.is_default == True)
        ).all()
        
        for addr in existing_defaults:
            addr.is_default = False
            session.add(addr)
    
    address = ShippingAddress(
        user_id=current_user.id,
        full_name=full_name,
        phone_number=phone_number,
        address_line1=address_line1,
        address_line2=address_line2,
        city=city,
        state_province=state_province,
        postal_code=postal_code,
        country=country,
        is_default=is_default,
        instructions=instructions
    )
    
    session.add(address)
    session.commit()
    session.refresh(address)
    return address

@router.get("/addresses", response_model=List[ShippingAddress])
def get_my_shipping_addresses(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene todas las direcciones de envío del usuario"""
    addresses = session.exec(
        select(ShippingAddress)
        .where(ShippingAddress.user_id == current_user.id)
        .order_by(ShippingAddress.is_default.desc(), ShippingAddress.updated_at.desc())
    ).all()
    return addresses

@router.get("/addresses/{address_id}", response_model=ShippingAddress)
def get_shipping_address(
    address_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene una dirección de envío específica"""
    address = session.get(ShippingAddress, address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Dirección no encontrada")
    
    # Verificar que pertenece al usuario (o es admin)
    if address.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para ver esta dirección")
    
    return address

@router.put("/addresses/{address_id}", response_model=ShippingAddress)
def update_shipping_address(
    address_id: int,
    full_name: Optional[str] = Body(None),
    phone_number: Optional[str] = Body(None),
    address_line1: Optional[str] = Body(None),
    address_line2: Optional[str] = Body(None),
    city: Optional[str] = Body(None),
    state_province: Optional[str] = Body(None),
    postal_code: Optional[str] = Body(None),
    country: Optional[str] = Body(None),
    is_default: Optional[bool] = Body(None),
    instructions: Optional[str] = Body(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Actualiza una dirección de envío"""
    address = session.get(ShippingAddress, address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Dirección no encontrada")
    
    # Verificar permisos
    if address.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para actualizar esta dirección")
    
    # Si se marca como default, quitar default de otras direcciones
    if is_default is not None and is_default:
        existing_defaults = session.exec(
            select(ShippingAddress)
            .where(ShippingAddress.user_id == current_user.id)
            .where(ShippingAddress.is_default == True)
            .where(ShippingAddress.id != address_id)
        ).all()
        
        for addr in existing_defaults:
            addr.is_default = False
            session.add(addr)
    
    # Actualizar campos
    update_fields = {
        "full_name": full_name,
        "phone_number": phone_number,
        "address_line1": address_line1,
        "address_line2": address_line2,
        "city": city,
        "state_province": state_province,
        "postal_code": postal_code,
        "country": country,
        "is_default": is_default,
        "instructions": instructions
    }
    
    for field, value in update_fields.items():
        if value is not None:
            setattr(address, field, value)
    
    address.updated_at = datetime.utcnow()
    session.add(address)
    session.commit()
    session.refresh(address)
    return address

@router.delete("/addresses/{address_id}")
def delete_shipping_address(
    address_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Elimina una dirección de envío"""
    address = session.get(ShippingAddress, address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Dirección no encontrada")
    
    # Verificar permisos
    if address.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para eliminar esta dirección")
    
    # Verificar que no esté en uso por algún envío
    shipments = session.exec(
        select(Shipment).where(Shipment.shipping_address_id == address_id)
    ).all()
    
    if shipments:
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar esta dirección porque está asociada a envíos existentes"
        )
    
    session.delete(address)
    session.commit()
    return {"message": "Dirección eliminada correctamente"}

# ======================================================
# 🚚 MÉTODOS DE ENVÍO
# ======================================================

@router.get("/methods", response_model=List[ShippingMethodConfig])
def get_shipping_methods(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    weight_kg: Optional[float] = Query(None, description="Peso del paquete en kg"),
    session: Session = Depends(get_session)
):
    """Obtiene los métodos de envío disponibles"""
    query = select(ShippingMethodConfig).where(ShippingMethodConfig.is_active == True)
    
    # Filtrar por país si se especifica
    if country:
        # TODO: Implementar filtro por países disponibles
        pass
    
    # Filtrar por peso si se especifica
    if weight_kg is not None:
        query = query.where(
            or_(
                ShippingMethodConfig.max_weight_kg.is_(None),
                ShippingMethodConfig.max_weight_kg >= weight_kg
            )
        ).where(ShippingMethodConfig.min_weight_kg <= weight_kg)
    
    methods = session.exec(query.order_by(ShippingMethodConfig.base_cost)).all()
    return methods

@router.post("/methods", response_model=ShippingMethodConfig)
@require_admin
def create_shipping_method(
    name: str = Body(...),
    code: ShippingMethod = Body(...),
    carrier: Carrier = Body(...),
    base_cost: float = Body(0.0),
    cost_per_kg: Optional[float] = Body(None),
    min_weight_kg: float = Body(0.0),
    max_weight_kg: Optional[float] = Body(None),
    estimated_days_min: int = Body(3),
    estimated_days_max: int = Body(5),
    available_countries: Optional[str] = Body(None),
    requires_signature: bool = Body(False),
    has_tracking: bool = Body(True),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Crea un nuevo método de envío (solo admin)"""
    method = ShippingMethodConfig(
        name=name,
        code=code,
        carrier=carrier,
        base_cost=base_cost,
        cost_per_kg=cost_per_kg,
        min_weight_kg=min_weight_kg,
        max_weight_kg=max_weight_kg,
        estimated_days_min=estimated_days_min,
        estimated_days_max=estimated_days_max,
        available_countries=available_countries,
        requires_signature=requires_signature,
        has_tracking=has_tracking
    )
    
    session.add(method)
    session.commit()
    session.refresh(method)
    return method

@router.put("/methods/{method_id}", response_model=ShippingMethodConfig)
@require_admin
def update_shipping_method(
    method_id: int,
    name: Optional[str] = Body(None),
    code: Optional[ShippingMethod] = Body(None),
    carrier: Optional[Carrier] = Body(None),
    base_cost: Optional[float] = Body(None),
    cost_per_kg: Optional[float] = Body(None),
    min_weight_kg: Optional[float] = Body(None),
    max_weight_kg: Optional[float] = Body(None),
    estimated_days_min: Optional[int] = Body(None),
    estimated_days_max: Optional[int] = Body(None),
    is_active: Optional[bool] = Body(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Actualiza un método de envío (solo admin)"""
    method = session.get(ShippingMethodConfig, method_id)
    if not method:
        raise HTTPException(status_code=404, detail="Método de envío no encontrado")
    
    update_fields = {
        "name": name,
        "code": code,
        "carrier": carrier,
        "base_cost": base_cost,
        "cost_per_kg": cost_per_kg,
        "min_weight_kg": min_weight_kg,
        "max_weight_kg": max_weight_kg,
        "estimated_days_min": estimated_days_min,
        "estimated_days_max": estimated_days_max,
        "is_active": is_active
    }
    
    for field, value in update_fields.items():
        if value is not None:
            setattr(method, field, value)
    
    session.add(method)
    session.commit()
    session.refresh(method)
    return method

# ======================================================
# 📦 CALCULAR COSTO DE ENVÍO
# ======================================================

@router.post("/calculate")
def calculate_shipping_cost(
    items: List[Dict[str, Any]] = Body(...),
    destination_country: str = Body("ES"),
    destination_postal_code: Optional[str] = Body(None),
    shipping_method_code: Optional[ShippingMethod] = Body(None),
    session: Session = Depends(get_session)
):
    """Calcula el costo de envío para una lista de productos"""
    # Calcular peso total
    total_weight = 0.0
    requires_shipping = True
    
    for item in items:
        product_id = item.get("product_id")
        quantity = item.get("quantity", 1)
        
        product = session.get(Product, product_id)
        if not product:
            continue
        
        if product.weight_kg:
            total_weight += product.weight_kg * quantity
        
        # Si algún producto no requiere envío
        if not product.requires_shipping:
            requires_shipping = False
    
    if not requires_shipping:
        return {
            "requires_shipping": False,
            "shipping_cost": 0.0,
            "available_methods": [],
            "message": "Los productos no requieren envío físico"
        }
    
    # Obtener métodos de envío disponibles
    query = select(ShippingMethodConfig).where(
        ShippingMethodConfig.is_active == True
    )
    
    if total_weight > 0:
        query = query.where(
            or_(
                ShippingMethodConfig.max_weight_kg.is_(None),
                ShippingMethodConfig.max_weight_kg >= total_weight
            )
        ).where(ShippingMethodConfig.min_weight_kg <= total_weight)
    
    methods = session.exec(query.order_by(ShippingMethodConfig.base_cost)).all()
    
    # Calcular costos para cada método
    available_methods = []
    for method in methods:
        shipping_cost = method.base_cost
        
        if method.cost_per_kg and total_weight > 0:
            shipping_cost += method.cost_per_kg * total_weight
        
        available_methods.append({
            "method_id": method.id,
            "name": method.name,
            "code": method.code,
            "carrier": method.carrier,
            "cost": round(shipping_cost, 2),
            "estimated_days_min": method.estimated_days_min,
            "estimated_days_max": method.estimated_days_max,
            "requires_signature": method.requires_signature,
            "has_tracking": method.has_tracking
        })
    
    # Si se especificó un método, calcular solo ese
    if shipping_method_code:
        filtered_methods = [m for m in available_methods if m["code"] == shipping_method_code]
        if filtered_methods:
            selected_method = filtered_methods[0]
        else:
            selected_method = None
    else:
        selected_method = available_methods[0] if available_methods else None
    
    return {
        "requires_shipping": True,
        "total_weight_kg": round(total_weight, 2),
        "available_methods": available_methods,
        "recommended_method": selected_method,
        "destination_country": destination_country
    }

# ======================================================
# 📦 GESTIÓN DE ENVÍOS (SHIPMENTS)
# ======================================================

@router.post("/orders/{order_id}/shipments")
@require_admin_or_vendor
def create_shipment(
    order_id: int,
    shipping_address_id: int = Body(...),
    shipping_method_id: int = Body(...),
    weight_kg: Optional[float] = Body(None),
    package_count: int = Body(1),
    insurance_cost: float = Body(0.0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Crea un envío para una orden (admin o vendedor)"""
    # Verificar que la orden existe
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    
    # Verificar permisos (admin o vendedor dueño de productos)
    if current_user.role != "admin":
        # Verificar que el vendedor tiene productos en esta orden
        order_items = session.exec(
            select(OrderItem).where(OrderItem.order_id == order_id)
        ).all()
        
        has_vendor_products = False
        for item in order_items:
            product = session.get(Product, item.product_id)
            if product and product.owner_id == current_user.id:
                has_vendor_products = True
                break
        
        if not has_vendor_products:
            raise HTTPException(
                status_code=403,
                detail="No tienes productos en esta orden"
            )
    
    # Verificar dirección de envío
    address = session.get(ShippingAddress, shipping_address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Dirección de envío no encontrada")
    
    # Verificar método de envío
    method = session.get(ShippingMethodConfig, shipping_method_id)
    if not method:
        raise HTTPException(status_code=404, detail="Método de envío no encontrado")
    
    # Calcular costo de envío
    shipping_cost = method.base_cost
    if weight_kg and method.cost_per_kg:
        shipping_cost += method.cost_per_kg * weight_kg
    
    total_cost = shipping_cost + insurance_cost
    
    # Generar número de tracking único
    tracking_number = f"{method.carrier.upper()}{uuid.uuid4().hex[:12].upper()}"
    
    # Calcular fechas estimadas de entrega
    estimated_delivery_start = datetime.utcnow() + timedelta(days=method.estimated_days_min)
    estimated_delivery_end = datetime.utcnow() + timedelta(days=method.estimated_days_max)
    
    shipment = Shipment(
        order_id=order_id,
        shipping_address_id=shipping_address_id,
        shipping_method_id=shipping_method_id,
        tracking_number=tracking_number,
        carrier=method.carrier,
        weight_kg=weight_kg,
        package_count=package_count,
        shipping_cost=shipping_cost,
        insurance_cost=insurance_cost,
        total_cost=total_cost,
        estimated_delivery_start=estimated_delivery_start,
        estimated_delivery_end=estimated_delivery_end,
        status=ShippingStatus.PENDING
    )
    
    session.add(shipment)
    
    # Actualizar estado de la orden si es necesario
    if order.status == "confirmed":
        order.status = "processing"
        session.add(order)
    
    session.commit()
    session.refresh(shipment)
    
    return {
        "message": "Envío creado exitosamente",
        "shipment": shipment,
        "tracking_number": tracking_number
    }

@router.get("/shipments", response_model=List[Shipment])
@require_admin_or_vendor
def get_shipments(
    status: Optional[ShippingStatus] = Query(None),
    carrier: Optional[Carrier] = Query(None),
    start_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    order_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene envíos (admin o vendedor)"""
    query = select(Shipment)
    
    # Si es vendedor, solo sus envíos
    if current_user.role == "vendor":
        # Obtener órdenes que contienen productos del vendedor
        vendor_orders = []
        all_orders = session.exec(select(Order)).all()
        
        for order in all_orders:
            order_items = session.exec(
                select(OrderItem).where(OrderItem.order_id == order.id)
            ).all()
            
            for item in order_items:
                product = session.get(Product, item.product_id)
                if product and product.owner_id == current_user.id:
                    vendor_orders.append(order.id)
                    break
        
        if not vendor_orders:
            return []
        
        query = query.where(Shipment.order_id.in_(vendor_orders))
    
    # Aplicar filtros
    if status:
        query = query.where(Shipment.status == status)
    if carrier:
        query = query.where(Shipment.carrier == carrier)
    if order_id:
        query = query.where(Shipment.order_id == order_id)
    
    # Filtros de fecha
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query = query.where(Shipment.created_at >= start)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido")
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query = query.where(Shipment.created_at <= end)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido")
    
    shipments = session.exec(
        query.order_by(Shipment.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    
    return shipments

@router.get("/shipments/{shipment_id}", response_model=Shipment)
def get_shipment(
    shipment_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene un envío específico"""
    shipment = session.get(Shipment, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    
    # Verificar permisos
    order = session.get(Order, shipment.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    
    if current_user.role != "admin":
        # Es el dueño de la orden?
        if order.user_id != current_user.id:
            # Es vendedor con productos en esta orden?
            if current_user.role == "vendor":
                order_items = session.exec(
                    select(OrderItem).where(OrderItem.order_id == order.id)
                ).all()
                
                has_vendor_products = False
                for item in order_items:
                    product = session.get(Product, item.product_id)
                    if product and product.owner_id == current_user.id:
                        has_vendor_products = True
                        break
                
                if not has_vendor_products:
                    raise HTTPException(
                        status_code=403,
                        detail="No tienes permisos para ver este envío"
                    )
            else:
                raise HTTPException(
                    status_code=403,
                    detail="No tienes permisos para ver este envío"
                )
    
    return shipment

@router.put("/shipments/{shipment_id}/status")
@require_admin_or_vendor
def update_shipment_status(
    shipment_id: int,
    new_status: ShippingStatus = Body(...),
    tracking_number: Optional[str] = Body(None),
    tracking_url: Optional[str] = Body(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Actualiza el estado de un envío (admin o vendedor)"""
    shipment = session.get(Shipment, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    
    # Verificar permisos (similar a get_shipment)
    order = session.get(Order, shipment.order_id)
    if current_user.role == "vendor":
        order_items = session.exec(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).all()
        
        has_vendor_products = False
        for item in order_items:
            product = session.get(Product, item.product_id)
            if product and product.owner_id == current_user.id:
                has_vendor_products = True
                break
        
        if not has_vendor_products:
            raise HTTPException(
                status_code=403,
                detail="No tienes permisos para actualizar este envío"
            )
    
    old_status = shipment.status
    shipment.status = new_status
    shipment.updated_at = datetime.utcnow()
    
    # Actualizar fechas según el estado
    if new_status == ShippingStatus.IN_TRANSIT and not shipment.shipped_at:
        shipment.shipped_at = datetime.utcnow()
    elif new_status == ShippingStatus.DELIVERED and not shipment.delivered_at:
        shipment.delivered_at = datetime.utcnow()
        # Actualizar estado de la orden también
        order.status = "delivered"
        session.add(order)
    
    # Actualizar información de tracking
    if tracking_number:
        shipment.tracking_number = tracking_number
    if tracking_url:
        shipment.tracking_url = tracking_url
    
    session.add(shipment)
    session.commit()
    session.refresh(shipment)
    
    return {
        "message": f"Estado del envío actualizado de '{old_status}' a '{new_status}'",
        "shipment": shipment
    }

@router.get("/track/{tracking_number}")
def track_shipment(
    tracking_number: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene información de seguimiento de un envío"""
    shipment = session.exec(
        select(Shipment).where(Shipment.tracking_number == tracking_number)
    ).first()
    
    if not shipment:
        raise HTTPException(status_code=404, detail="Número de tracking no encontrado")
    
    # Verificar permisos
    order = session.get(Order, shipment.order_id)
    if order.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para rastrear este envío"
        )
    
    # Simular eventos de tracking (en producción esto vendría de la API del carrier)
    tracking_events = []
    if shipment.tracking_events_json:
        tracking_events = json.loads(shipment.tracking_events_json)
    else:
        # Generar eventos simulados basados en el estado
        base_date = shipment.created_at
        events = [
            {"date": base_date, "status": "Envío creado", "location": "Almacén central"},
        ]
        
        if shipment.status in [ShippingStatus.PROCESSING, ShippingStatus.READY_FOR_PICKUP, 
                              ShippingStatus.IN_TRANSIT, ShippingStatus.OUT_FOR_DELIVERY, 
                              ShippingStatus.DELIVERED]:
            events.append({
                "date": base_date + timedelta(hours=2),
                "status": "Procesado en almacén",
                "location": "Centro de distribución"
            })
        
        if shipment.status in [ShippingStatus.IN_TRANSIT, ShippingStatus.OUT_FOR_DELIVERY, 
                              ShippingStatus.DELIVERED]:
            events.append({
                "date": base_date + timedelta(days=1),
                "status": "En tránsito",
                "location": f"En ruta a {shipment.address.city}"
            })
        
        if shipment.status in [ShippingStatus.OUT_FOR_DELIVERY, ShippingStatus.DELIVERED]:
            events.append({
                "date": base_date + timedelta(days=2),
                "status": "En reparto",
                "location": f"Repartidor asignado en {shipment.address.city}"
            })
        
        if shipment.status == ShippingStatus.DELIVERED and shipment.delivered_at:
            events.append({
                "date": shipment.delivered_at,
                "status": "Entregado",
                "location": shipment.address.address_line1
            })
        
        tracking_events = events
    
    return {
        "tracking_number": shipment.tracking_number,
        "carrier": shipment.carrier,
        "status": shipment.status,
        "estimated_delivery": {
            "start": shipment.estimated_delivery_start,
            "end": shipment.estimated_delivery_end
        },
        "destination": {
            "address": f"{shipment.address.address_line1}, {shipment.address.city}",
            "recipient": shipment.address.full_name
        },
        "tracking_events": tracking_events,
        "tracking_url": shipment.tracking_url
    }

# ======================================================
# 📊 ESTADÍSTICAS DE ENVÍOS
# ======================================================

@router.get("/stats")
@require_admin_or_vendor
def get_shipping_stats(
    days: int = Query(30, description="Estadísticas de últimos X días"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Estadísticas de envíos (admin o vendedor)"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = select(Shipment).where(Shipment.created_at >= start_date)
    
    # Filtrar por vendedor si es necesario
    if current_user.role == "vendor":
        vendor_orders = []
        all_orders = session.exec(select(Order)).all()
        
        for order in all_orders:
            order_items = session.exec(
                select(OrderItem).where(OrderItem.order_id == order.id)
            ).all()
            
            for item in order_items:
                product = session.get(Product, item.product_id)
                if product and product.owner_id == current_user.id:
                    vendor_orders.append(order.id)
                    break
        
        if vendor_orders:
            query = query.where(Shipment.order_id.in_(vendor_orders))
        else:
            # Si no tiene órdenes, retornar estadísticas vacías
            return {
                "period_days": days,
                "total_shipments": 0,
                "shipments_by_status": {},
                "shipments_by_carrier": {},
                "total_shipping_cost": 0,
                "average_delivery_time": 0
            }
    
    shipments = session.exec(query).all()
    
    total_shipments = len(shipments)
    
    # Envíos por estado
    shipments_by_status = {}
    for shipment in shipments:
        shipments_by_status[shipment.status] = shipments_by_status.get(shipment.status, 0) + 1
    
    # Envíos por carrier
    shipments_by_carrier = {}
    for shipment in shipments:
        shipments_by_carrier[shipment.carrier] = shipments_by_carrier.get(shipment.carrier, 0) + 1
    
    # Costos totales
    total_shipping_cost = sum(shipment.total_cost for shipment in shipments)
    
    # Tiempo promedio de entrega
    delivered_shipments = [s for s in shipments if s.delivered_at and s.shipped_at]
    if delivered_shipments:
        delivery_times = [(s.delivered_at - s.shipped_at).days for s in delivered_shipments]
        avg_delivery_time = sum(delivery_times) / len(delivery_times)
    else:
        avg_delivery_time = 0
    
    # Envíos recientes
    recent_shipments = sorted(shipments, key=lambda x: x.created_at, reverse=True)[:5]
    
    return {
        "period_days": days,
        "total_shipments": total_shipments,
        "shipments_by_status": shipments_by_status,
        "shipments_by_carrier": shipments_by_carrier,
        "total_shipping_cost": round(total_shipping_cost, 2),
        "average_delivery_time": round(avg_delivery_time, 1),
        "recent_shipments": [
            {
                "id": s.id,
                "tracking_number": s.tracking_number,
                "order_id": s.order_id,
                "status": s.status,
                "carrier": s.carrier,
                "created_at": s.created_at
            }
            for s in recent_shipments
        ]
    }

# ======================================================
# 🏷️ ETIQUETAS DE ENVÍO
# ======================================================

@router.post("/shipments/{shipment_id}/labels")
@require_admin_or_vendor
def generate_shipping_label(
    shipment_id: int,
    format: str = Body("PDF", description="Formato de la etiqueta: PDF, ZPL, PNG"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Genera una etiqueta de envío (admin o vendedor)"""
    shipment = session.get(Shipment, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    
    # Verificar permisos
    order = session.get(Order, shipment.order_id)
    if current_user.role == "vendor":
        order_items = session.exec(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).all()
        
        has_vendor_products = False
        for item in order_items:
            product = session.get(Product, item.product_id)
            if product and product.owner_id == current_user.id:
                has_vendor_products = True
                break
        
        if not has_vendor_products:
            raise HTTPException(
                status_code=403,
                detail="No tienes permisos para generar etiquetas para este envío"
            )
    
    # Simular generación de etiqueta (en producción integrar con API del carrier)
    label_id = f"LABEL-{uuid.uuid4().hex[:8].upper()}"
    
    # Datos de la etiqueta simulada
    label_data = {
        "shipment_id": shipment.id,
        "tracking_number": shipment.tracking_number,
        "carrier": shipment.carrier,
        "from": {
            "name": "Tienda Virtual",
            "address": "Calle Principal 123, Ciudad"
        },
        "to": {
            "name": shipment.address.full_name,
            "address": f"{shipment.address.address_line1}, {shipment.address.postal_code} {shipment.address.city}",
            "phone": shipment.address.phone_number
        },
        "weight": shipment.weight_kg,
        "service": shipment.shipping_method.name if shipment.shipping_method else "Standard",
        "barcode": shipment.tracking_number
    }
    
    label = ShippingLabel(
        shipment_id=shipment_id,
        label_url=f"/api/shipping/labels/{label_id}/download",
        label_data=json.dumps(label_data),  # En producción sería base64 del PDF
        format=format,
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    
    session.add(label)
    session.commit()
    session.refresh(label)
    
    return {
        "message": "Etiqueta generada exitosamente",
        "label": label,
        "download_url": f"/api/shipping/labels/{label.id}/download"
    }

@router.get("/labels/{label_id}/download")
def download_shipping_label(
    label_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Descarga una etiqueta de envío"""
    label = session.get(ShippingLabel, label_id)
    if not label:
        raise HTTPException(status_code=404, detail="Etiqueta no encontrada")
    
    # Verificar permisos
    shipment = session.get(Shipment, label.shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    
    order = session.get(Order, shipment.order_id)
    if order.user_id != current_user.id and current_user.role != "admin":
        # Verificar si es vendedor
        if current_user.role == "vendor":
            order_items = session.exec(
                select(OrderItem).where(OrderItem.order_id == order.id)
            ).all()
            
            has_vendor_products = False
            for item in order_items:
                product = session.get(Product, item.product_id)
                if product and product.owner_id == current_user.id:
                    has_vendor_products = True
                    break
            
            if not has_vendor_products:
                raise HTTPException(
                    status_code=403,
                    detail="No tienes permisos para descargar esta etiqueta"
                )
        else:
            raise HTTPException(
                status_code=403,
                detail="No tienes permisos para descargar esta etiqueta"
            )
    
    # En producción, esto devolvería el archivo real
    # Por ahora devolvemos los datos simulados
    if label.label_data:
        label_info = json.loads(label.label_data)
    else:
         label_info = {"message": "Datos de etiqueta no disponibles"}
    
    return {
        "label_info": label_info,
        "download_url": label.label_url,
        "format": label.format,
        "expires_at": label.expires_at
    }