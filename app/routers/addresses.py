from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime

from ..database import get_session
from ..models import ShippingAddress, User
from .auth_router import get_current_user
from ..permissions import require_admin

router = APIRouter(prefix="/addresses", tags=["addresses"])

# ======================================================
# 📍 OBTENER MIS DIRECCIONES
# ======================================================
@router.get("/me", response_model=List[ShippingAddress])
def get_my_addresses(
    default_only: bool = Query(False, description="Solo la dirección por defecto"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene las direcciones de envío del usuario actual"""
    query = select(ShippingAddress).where(ShippingAddress.user_id == current_user.id)
    
    if default_only:
        query = query.where(ShippingAddress.is_default == True)
    
    addresses = session.exec(
        query.order_by(ShippingAddress.is_default.desc(), ShippingAddress.updated_at.desc())
    ).all()
    
    return addresses

# ======================================================
# 📍 OBTENER DIRECCIÓN POR ID
# ======================================================
@router.get("/{address_id}", response_model=ShippingAddress)
def get_address(
    address_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene una dirección específica por ID"""
    address = session.get(ShippingAddress, address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Dirección no encontrada")
    
    # Verificar permisos
    if address.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=403, 
            detail="No tienes permisos para ver esta dirección"
        )
    
    return address

# ======================================================
# 📍 CREAR NUEVA DIRECCIÓN
# ======================================================
@router.post("/", response_model=ShippingAddress)
def create_address(
    full_name: str = Body(..., min_length=2, max_length=100),
    phone_number: str = Body(..., min_length=5, max_length=20),
    address_line1: str = Body(..., min_length=5, max_length=200),
    address_line2: Optional[str] = Body(None, max_length=200),
    city: str = Body(..., min_length=2, max_length=100),
    state_province: str = Body(..., min_length=2, max_length=100),
    postal_code: str = Body(..., min_length=3, max_length=20),
    country: str = Body("ES", min_length=2, max_length=2),
    is_default: bool = Body(False),
    instructions: Optional[str] = Body(None, max_length=500),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Crea una nueva dirección de envío"""
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
        country=country.upper(),
        is_default=is_default,
        instructions=instructions
    )
    
    session.add(address)
    session.commit()
    session.refresh(address)
    
    return address

# ======================================================
# 📍 ACTUALIZAR DIRECCIÓN
# ======================================================
@router.put("/{address_id}", response_model=ShippingAddress)
def update_address(
    address_id: int,
    full_name: Optional[str] = Body(None, min_length=2, max_length=100),
    phone_number: Optional[str] = Body(None, min_length=5, max_length=20),
    address_line1: Optional[str] = Body(None, min_length=5, max_length=200),
    address_line2: Optional[str] = Body(None, max_length=200),
    city: Optional[str] = Body(None, min_length=2, max_length=100),
    state_province: Optional[str] = Body(None, min_length=2, max_length=100),
    postal_code: Optional[str] = Body(None, min_length=3, max_length=20),
    country: Optional[str] = Body(None, min_length=2, max_length=2),
    is_default: Optional[bool] = Body(None),
    instructions: Optional[str] = Body(None, max_length=500),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Actualiza una dirección de envío existente"""
    address = session.get(ShippingAddress, address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Dirección no encontrada")
    
    # Verificar permisos
    if address.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=403, 
            detail="No tienes permisos para actualizar esta dirección"
        )
    
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
    update_data = {
        "full_name": full_name,
        "phone_number": phone_number,
        "address_line1": address_line1,
        "address_line2": address_line2,
        "city": city,
        "state_province": state_province,
        "postal_code": postal_code,
        "country": country.upper() if country else None,
        "is_default": is_default,
        "instructions": instructions
    }
    
    for field, value in update_data.items():
        if value is not None:
            setattr(address, field, value)
    
    address.updated_at = datetime.utcnow()
    session.add(address)
    session.commit()
    session.refresh(address)
    
    return address

# ======================================================
# 📍 ELIMINAR DIRECCIÓN
# ======================================================
@router.delete("/{address_id}")
def delete_address(
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
        raise HTTPException(
            status_code=403, 
            detail="No tienes permisos para eliminar esta dirección"
        )
    
    # Verificar que no sea la única dirección
    user_addresses = session.exec(
        select(ShippingAddress).where(ShippingAddress.user_id == current_user.id)
    ).all()
    
    if len(user_addresses) <= 1:
        raise HTTPException(
            status_code=400,
            detail="No puedes eliminar tu única dirección de envío"
        )
    
    # Verificar que no esté en uso por algún envío
    from ..models import Shipment
    shipments = session.exec(
        select(Shipment).where(Shipment.shipping_address_id == address_id)
    ).all()
    
    if shipments:
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar esta dirección porque está asociada a envíos existentes"
        )
    
    # Si es la dirección por defecto, asignar otra como default
    if address.is_default:
        other_address = session.exec(
            select(ShippingAddress)
            .where(ShippingAddress.user_id == current_user.id)
            .where(ShippingAddress.id != address_id)
            .limit(1)
        ).first()
        
        if other_address:
            other_address.is_default = True
            session.add(other_address)
    
    session.delete(address)
    session.commit()
    
    return {"message": "Dirección eliminada correctamente"}

# ======================================================
# 📍 ESTABLECER DIRECCIÓN POR DEFECTO
# ======================================================
@router.post("/{address_id}/set-default")
def set_default_address(
    address_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Establece una dirección como la predeterminada"""
    address = session.get(ShippingAddress, address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Dirección no encontrada")
    
    # Verificar permisos
    if address.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=403, 
            detail="No tienes permisos para modificar esta dirección"
        )
    
    # Quitar default de otras direcciones
    existing_defaults = session.exec(
        select(ShippingAddress)
        .where(ShippingAddress.user_id == current_user.id)
        .where(ShippingAddress.is_default == True)
        .where(ShippingAddress.id != address_id)
    ).all()
    
    for addr in existing_defaults:
        addr.is_default = False
        session.add(addr)
    
    # Establecer esta como default
    address.is_default = True
    address.updated_at = datetime.utcnow()
    session.add(address)
    session.commit()
    
    return {"message": f"Dirección '{address.full_name}' establecida como predeterminada"}

# ======================================================
# 📍 VALIDAR DIRECCIÓN
# ======================================================
@router.post("/validate")
def validate_address(
    address_line1: str = Body(..., min_length=5, max_length=200),
    city: str = Body(..., min_length=2, max_length=100),
    postal_code: str = Body(..., min_length=3, max_length=20),
    country: str = Body("ES", min_length=2, max_length=2),
    session: Session = Depends(get_session)
):
    """Valida una dirección (simulación)"""
    # En producción, aquí se integraría con una API de validación de direcciones
    # como Google Maps API, SmartyStreets, etc.
    
    # Simulación simple de validación
    validation_result = {
        "is_valid": True,
        "normalized_address": {
            "address_line1": address_line1.title(),
            "city": city.title(),
            "postal_code": postal_code.upper(),
            "country": country.upper()
        },
        "suggestions": [],
        "validation_notes": "Dirección válida (validación simulada)"
    }
    
    # Simular algunas validaciones básicas
    if len(postal_code) < 4:
        validation_result["is_valid"] = False
        validation_result["suggestions"].append("El código postal parece demasiado corto")
    
    if country.upper() == "ES" and not postal_code.isdigit():
        validation_result["is_valid"] = False
        validation_result["suggestions"].append("El código postal español debe contener solo números")
    
    return validation_result

# ======================================================
# 📍 OBTENER DIRECCIONES POR USUARIO (admin)
# ======================================================
@router.get("/user/{user_id}", response_model=List[ShippingAddress])
@require_admin
def get_user_addresses(
    user_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene las direcciones de un usuario específico (solo admin)"""
    # Verificar que el usuario existe
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    addresses = session.exec(
        select(ShippingAddress)
        .where(ShippingAddress.user_id == user_id)
        .order_by(ShippingAddress.is_default.desc(), ShippingAddress.updated_at.desc())
    ).all()
    
    return addresses

# ======================================================
# 📍 BUSCAR DIRECCIONES
# ======================================================
@router.get("/search")
@require_admin
def search_addresses(
    city: Optional[str] = Query(None, description="Buscar por ciudad"),
    postal_code: Optional[str] = Query(None, description="Buscar por código postal"),
    country: Optional[str] = Query(None, description="Buscar por país"),
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Busca direcciones (solo admin)"""
    query = select(ShippingAddress)
    
    if city:
        query = query.where(ShippingAddress.city.ilike(f"%{city}%"))
    if postal_code:
        query = query.where(ShippingAddress.postal_code.ilike(f"%{postal_code}%"))
    if country:
        query = query.where(ShippingAddress.country.ilike(f"%{country}%"))
    
    addresses = session.exec(
        query.order_by(ShippingAddress.country, ShippingAddress.city)
        .limit(limit)
    ).all()
    
    return {
        "total_results": len(addresses),
        "addresses": addresses
    }

# ======================================================
# 📍 ESTADÍSTICAS DE DIRECCIONES
# ======================================================
@router.get("/stats/countries")
@require_admin
def get_country_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Estadísticas de direcciones por país (solo admin)"""
    addresses = session.exec(select(ShippingAddress)).all()
    
    country_stats = {}
    for address in addresses:
        country = address.country
        country_stats[country] = country_stats.get(country, 0) + 1
    
    # Ordenar por cantidad descendente
    sorted_stats = sorted(country_stats.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "total_addresses": len(addresses),
        "unique_countries": len(country_stats),
        "countries": [
            {"country": country, "count": count}
            for country, count in sorted_stats
        ]
    }