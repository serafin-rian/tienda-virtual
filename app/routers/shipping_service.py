from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import uuid
from sqlmodel import Session, select
from ..models import (
    Product, ShippingMethodConfig, Shipment, ShippingAddress,
    ShippingStatus, Carrier, Order, OrderItem
)

class ShippingService:
    """Servicio para lógica de negocio de envíos"""
    
    @staticmethod
    def calculate_package_weight(order_items: List[Dict[str, Any]], session: Session) -> float:
        """Calcula el peso total de un paquete basado en los productos"""
        total_weight = 0.0
        
        for item in order_items:
            product_id = item.get("product_id")
            quantity = item.get("quantity", 1)
            
            product = session.get(Product, product_id)
            if product and product.weight_kg:
                total_weight += product.weight_kg * quantity
            else:
                # Peso por defecto si no está definido
                total_weight += 0.5 * quantity  # 500g por producto
        
        return round(total_weight, 2)
    
    @staticmethod
    def get_available_shipping_methods(
        weight_kg: float,
        destination_country: str,
        session: Session
    ) -> List[ShippingMethodConfig]:
        """Obtiene métodos de envío disponibles para un peso y destino"""
        query = select(ShippingMethodConfig).where(
            ShippingMethodConfig.is_active == True,
            ShippingMethodConfig.min_weight_kg <= weight_kg,
            # Verificar máximo peso si está definido
            (ShippingMethodConfig.max_weight_kg.is_(None) | 
             (ShippingMethodConfig.max_weight_kg >= weight_kg))
        )
        
        methods = session.exec(query.order_by(ShippingMethodConfig.base_cost)).all()
        
        # Filtrar por país si es necesario
        available_methods = []
        for method in methods:
            if ShippingService._is_method_available_for_country(method, destination_country):
                available_methods.append(method)
        
        return available_methods
    
    @staticmethod
    def _is_method_available_for_country(method: ShippingMethodConfig, country: str) -> bool:
        """Verifica si un método está disponible para un país específico"""
        if not method.available_countries:
            return True
        
        try:
            available_countries = json.loads(method.available_countries)
            return country.upper() in available_countries
        except:
            return True
    
    @staticmethod
    def calculate_shipping_cost(
        method: ShippingMethodConfig,
        weight_kg: float,
        insurance_value: float = 0.0
    ) -> Dict[str, Any]:
        """Calcula el costo total de envío"""
        shipping_cost = method.base_cost
        
        if method.cost_per_kg and weight_kg > 0:
            shipping_cost += method.cost_per_kg * weight_kg
        
        # Calcular seguro (1% del valor asegurado)
        insurance_cost = insurance_value * 0.01 if insurance_value > 0 else 0.0
        
        total_cost = shipping_cost + insurance_cost
        
        return {
            "shipping_cost": round(shipping_cost, 2),
            "insurance_cost": round(insurance_cost, 2),
            "total_cost": round(total_cost, 2),
            "estimated_days": {
                "min": method.estimated_days_min,
                "max": method.estimated_days_max
            }
        }
    
    @staticmethod
    def generate_tracking_number(carrier: Carrier) -> str:
        """Genera un número de tracking único"""
        prefix = carrier.upper()
        unique_id = uuid.uuid4().hex[:12].upper()  # 12 caracteres hexadecimales
        return f"{prefix}{unique_id}"
    
    @staticmethod
    def create_shipment(
        order_id: int,
        shipping_address_id: int,
        shipping_method_id: int,
        weight_kg: Optional[float],
        package_count: int,
        insurance_value: float,
        session: Session
    ) -> Tuple[Shipment, str]:
        """Crea un nuevo envío con todos los datos necesarios"""
        # Obtener datos necesarios
        order = session.get(Order, order_id)
        address = session.get(ShippingAddress, shipping_address_id)
        method = session.get(ShippingMethodConfig, shipping_method_id)
        
        if not all([order, address, method]):
            raise ValueError("Datos de envío incompletos")
        
        # Calcular peso si no se proporciona
        if weight_kg is None:
            order_items = session.exec(
                select(OrderItem).where(OrderItem.order_id == order_id)
            ).all()
            
            weight_items = []
            for item in order_items:
                weight_items.append({
                    "product_id": item.product_id,
                    "quantity": item.quantity
                })
            
            weight_kg = ShippingService.calculate_package_weight(weight_items, session)
        
        # Calcular costos
        costs = ShippingService.calculate_shipping_cost(method, weight_kg, insurance_value)
        
        # Generar tracking
        tracking_number = ShippingService.generate_tracking_number(method.carrier)
        
        # Calcular fechas estimadas
        estimated_start = datetime.utcnow() + timedelta(days=method.estimated_days_min)
        estimated_end = datetime.utcnow() + timedelta(days=method.estimated_days_max)
        
        # Crear el envío
        shipment = Shipment(
            order_id=order_id,
            shipping_address_id=shipping_address_id,
            shipping_method_id=shipping_method_id,
            tracking_number=tracking_number,
            carrier=method.carrier,
            weight_kg=weight_kg,
            package_count=package_count,
            shipping_cost=costs["shipping_cost"],
            insurance_cost=costs["insurance_cost"],
            total_cost=costs["total_cost"],
            estimated_delivery_start=estimated_start,
            estimated_delivery_end=estimated_end,
            status=ShippingStatus.PENDING
        )
        
        return shipment, tracking_number
    
    @staticmethod
    def update_shipment_status(
        shipment: Shipment,
        new_status: ShippingStatus,
        tracking_data: Optional[Dict[str, Any]] = None
    ) -> Shipment:
        """Actualiza el estado de un envío y registra eventos de tracking"""
        shipment.status = new_status
        shipment.updated_at = datetime.utcnow()
        
        # Registrar eventos importantes
        if new_status == ShippingStatus.IN_TRANSIT and not shipment.shipped_at:
            shipment.shipped_at = datetime.utcnow()
        elif new_status == ShippingStatus.DELIVERED and not shipment.delivered_at:
            shipment.delivered_at = datetime.utcnow()
        
        # Actualizar eventos de tracking
        if tracking_data:
            events = []
            if shipment.tracking_events_json:
                try:
                    events = json.loads(shipment.tracking_events_json)
                except:
                    events = []
            
            new_event = {
                "timestamp": datetime.utcnow().isoformat(),
                "status": new_status.value,
                "description": tracking_data.get("description", ""),
                "location": tracking_data.get("location", ""),
                "details": tracking_data.get("details", {})
            }
            
            events.append(new_event)
            shipment.tracking_events_json = json.dumps(events, default=str)
            shipment.last_tracking_update = datetime.utcnow()
        
        return shipment
    
    @staticmethod
    def generate_shipment_label_data(shipment: Shipment, session: Session) -> Dict[str, Any]:
        """Genera datos para la etiqueta de envío"""
        address = shipment.address
        method = shipment.shipping_method
        
        label_data = {
            "shipment_id": shipment.id,
            "tracking_number": shipment.tracking_number,
            "carrier": shipment.carrier.value,
            "created_at": shipment.created_at.isoformat(),
            "from_address": {
                "company": "Tienda Virtual",
                "name": "Departamento de Envíos",
                "street": "Calle Comercio 123",
                "city": "Madrid",
                "postal_code": "28001",
                "country": "ES",
                "phone": "+34 910 000 000"
            },
            "to_address": {
                "name": address.full_name,
                "street": address.address_line1,
                "street2": address.address_line2 or "",
                "city": address.city,
                "state": address.state_province,
                "postal_code": address.postal_code,
                "country": address.country,
                "phone": address.phone_number
            },
            "package_details": {
                "weight_kg": shipment.weight_kg,
                "package_count": shipment.package_count,
                "service": method.name if method else "Standard",
                "requires_signature": method.requires_signature if method else False
            },
            "barcode_data": shipment.tracking_number,
            "instructions": address.instructions or "Entregar en puerta"
        }
        
        return label_data
    
    @staticmethod
    def validate_address(address_data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Valida una dirección y devuelve sugerencias de normalización"""
        errors = []
        suggestions = {}
        
        # Validaciones básicas
        required_fields = ["address_line1", "city", "postal_code", "country"]
        for field in required_fields:
            if not address_data.get(field):
                errors.append(f"El campo '{field}' es requerido")
        
        # Validar país (código de 2 letras)
        country = address_data.get("country", "").upper()
        if country and len(country) != 2:
            errors.append("El código de país debe tener 2 letras (ej: ES, US, FR)")
        
        # Validar código postal
        postal_code = address_data.get("postal_code", "")
        if postal_code and country == "ES" and not postal_code.isdigit():
            errors.append("El código postal español debe contener solo números")
        
        # Sugerencias de normalización
        if not errors:
            suggestions = {
                "city": address_data.get("city", "").title(),
                "state_province": address_data.get("state_province", "").title(),
                "postal_code": postal_code.upper(),
                "country": country
            }
        
        is_valid = len(errors) == 0
        return is_valid, errors, suggestions
    
    @staticmethod
    def get_shipment_timeline(shipment: Shipment) -> List[Dict[str, Any]]:
        """Genera una línea de tiempo de eventos del envío"""
        timeline = []
        
        # Evento: Creación
        timeline.append({
            "date": shipment.created_at,
            "event": "Envío creado",
            "status": "created",
            "description": "El envío ha sido creado en el sistema"
        })
        
        # Evento: Procesado (si aplica)
        if shipment.status in [ShippingStatus.PROCESSING, ShippingStatus.READY_FOR_PICKUP,
                              ShippingStatus.IN_TRANSIT, ShippingStatus.OUT_FOR_DELIVERY,
                              ShippingStatus.DELIVERED]:
            processing_time = shipment.created_at + timedelta(hours=2)
            timeline.append({
                "date": processing_time,
                "event": "Procesado",
                "status": "processing",
                "description": "El paquete ha sido procesado en el almacén"
            })
        
        # Evento: En tránsito
        if shipment.status in [ShippingStatus.IN_TRANSIT, ShippingStatus.OUT_FOR_DELIVERY,
                              ShippingStatus.DELIVERED] and shipment.shipped_at:
            timeline.append({
                "date": shipment.shipped_at,
                "event": "Enviado",
                "status": "shipped",
                "description": "El paquete ha sido enviado"
            })
        
        # Evento: En reparto
        if shipment.status in [ShippingStatus.OUT_FOR_DELIVERY, ShippingStatus.DELIVERED]:
            out_for_delivery = shipment.shipped_at + timedelta(days=1) if shipment.shipped_at else None
            if out_for_delivery:
                timeline.append({
                    "date": out_for_delivery,
                    "event": "En reparto",
                    "status": "out_for_delivery",
                    "description": "El paquete está siendo entregado"
                })
        
        # Evento: Entregado
        if shipment.status == ShippingStatus.DELIVERED and shipment.delivered_at:
            timeline.append({
                "date": shipment.delivered_at,
                "event": "Entregado",
                "status": "delivered",
                "description": "El paquete ha sido entregado"
            })
        
        # Ordenar por fecha
        timeline.sort(key=lambda x: x["date"])
        
        # Agregar eventos de tracking si existen
        if shipment.tracking_events_json:
            try:
                tracking_events = json.loads(shipment.tracking_events_json)
                for event in tracking_events:
                    timeline.append({
                        "date": datetime.fromisoformat(event["timestamp"]),
                        "event": event.get("description", "Actualización"),
                        "status": event.get("status", "update"),
                        "description": event.get("details", {}).get("message", "Actualización de tracking")
                    })
            except:
                pass
        
        # Ordenar nuevamente
        timeline.sort(key=lambda x: x["date"])
        
        return timeline
    
    @staticmethod
    def calculate_delivery_performance(shipments: List[Shipment]) -> Dict[str, Any]:
        """Calcula métricas de desempeño de entregas"""
        delivered_shipments = [s for s in shipments if s.status == ShippingStatus.DELIVERED]
        
        if not delivered_shipments:
            return {
                "total_shipments": len(shipments),
                "delivered_count": 0,
                "on_time_percentage": 0,
                "average_delivery_time": 0,
                "carrier_performance": {}
            }
        
        # Calcular entregas a tiempo
        on_time_count = 0
        delivery_times = []
        carrier_stats = {}
        
        for shipment in delivered_shipments:
            if shipment.shipped_at and shipment.delivered_at:
                # Tiempo de entrega real
                actual_days = (shipment.delivered_at - shipment.shipped_at).days
                delivery_times.append(actual_days)
                
                # Tiempo estimado
                estimated_max = shipment.shipping_method.estimated_days_max if shipment.shipping_method else 5
                
                # Verificar si fue a tiempo
                if actual_days <= estimated_max:
                    on_time_count += 1
                
                # Estadísticas por carrier
                carrier = shipment.carrier.value
                if carrier not in carrier_stats:
                    carrier_stats[carrier] = {
                        "count": 0,
                        "on_time": 0,
                        "delivery_times": []
                    }
                
                carrier_stats[carrier]["count"] += 1
                if actual_days <= estimated_max:
                    carrier_stats[carrier]["on_time"] += 1
                carrier_stats[carrier]["delivery_times"].append(actual_days)
        
        # Calcular porcentajes
        on_time_percentage = (on_time_count / len(delivered_shipments)) * 100 if delivered_shipments else 0
        avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0
        
        # Calcular métricas por carrier
        carrier_performance = {}
        for carrier, stats in carrier_stats.items():
            carrier_performance[carrier] = {
                "total_shipments": stats["count"],
                "on_time_percentage": (stats["on_time"] / stats["count"]) * 100 if stats["count"] > 0 else 0,
                "avg_delivery_time": sum(stats["delivery_times"]) / len(stats["delivery_times"]) if stats["delivery_times"] else 0,
                "reliability": "Alta" if (stats["on_time"] / stats["count"]) >= 0.9 else 
                              "Media" if (stats["on_time"] / stats["count"]) >= 0.7 else "Baja"
            }
        
        return {
            "total_shipments": len(shipments),
            "delivered_count": len(delivered_shipments),
            "on_time_percentage": round(on_time_percentage, 1),
            "average_delivery_time": round(avg_delivery_time, 1),
            "carrier_performance": carrier_performance
        }
    
    @staticmethod
    def get_shipping_quote(
        items: List[Dict[str, Any]],
        destination_country: str,
        destination_postal_code: Optional[str],
        session: Session
    ) -> Dict[str, Any]:
        """Genera una cotización de envío detallada"""
        # Calcular peso
        total_weight = ShippingService.calculate_package_weight(items, session)
        
        # Verificar si algún producto no requiere envío
        requires_shipping = True
        for item in items:
            product_id = item.get("product_id")
            product = session.get(Product, product_id)
            if product and not product.requires_shipping:
                requires_shipping = False
                break
        
        if not requires_shipping:
            return {
                "requires_shipping": False,
                "message": "Los productos no requieren envío físico",
                "shipping_cost": 0.0,
                "total_weight": 0.0
            }
        
        # Obtener métodos disponibles
        available_methods = ShippingService.get_available_shipping_methods(
            total_weight, destination_country, session
        )
        
        # Generar cotizaciones para cada método
        quotes = []
        for method in available_methods:
            cost_info = ShippingService.calculate_shipping_cost(method, total_weight)
            
            quote = {
                "method_id": method.id,
                "name": method.name,
                "code": method.code.value,
                "carrier": method.carrier.value,
                "shipping_cost": cost_info["shipping_cost"],
                "insurance_cost": cost_info["insurance_cost"],
                "total_cost": cost_info["total_cost"],
                "estimated_days": cost_info["estimated_days"],
                "has_tracking": method.has_tracking,
                "requires_signature": method.requires_signature,
                "features": []
            }
            
            # Agregar features
            if method.has_tracking:
                quote["features"].append("Seguimiento en tiempo real")
            if method.requires_signature:
                quote["features"].append("Requiere firma")
            if method.code == ShippingMethod.EXPRESS:
                quote["features"].append("Entrega express")
            elif method.code == ShippingMethod.NEXT_DAY:
                quote["features"].append("Entrega al día siguiente")
            
            quotes.append(quote)
        
        # Ordenar por costo
        quotes.sort(key=lambda x: x["total_cost"])
        
        return {
            "requires_shipping": True,
            "total_weight_kg": total_weight,
            "destination": {
                "country": destination_country,
                "postal_code": destination_postal_code
            },
            "available_quotes": quotes,
            "recommended_quote": quotes[0] if quotes else None
        }