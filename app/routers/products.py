from fastapi import APIRouter, Depends, HTTPException, Form, Query, UploadFile, File
from sqlmodel import Session, select, and_, or_
from typing import List, Optional
from datetime import datetime, timedelta
from ..database import get_session
from ..models import Product, User, AuditLog
from ..utils.images import save_upload_file, delete_image_file
import uuid

router = APIRouter(prefix="/products", tags=["products"])

# ======================================================
# 🟢 CREAR PRODUCTO (público) - VERSIÓN CORREGIDA
# ======================================================
@router.post("/create")
async def create_product(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    price: float = Form(...),
    quantity: int = Form(...),
    image_file: Optional[UploadFile] = File(None),
    weight_kg: Optional[str] = Form(None),  # Cambiado a string para manejar mejor
    dimensions_cm: Optional[str] = Form(None),
    requires_shipping: bool = Form(True),
    owner_id: Optional[str] = Form(None),  # Cambiado a string para manejar mejor
    session: Session = Depends(get_session)
):
    """Crea un nuevo producto (público)"""
    
    # Debug: Mostrar datos recibidos
    print(f"🛠️ DEBUG CREATE PRODUCT - Name: {name}, Price: {price}, Quantity: {quantity}")
    print(f"🛠️ DEBUG - Image file: {image_file}")
    print(f"🛠️ DEBUG - Weight_kg: {weight_kg}, Type: {type(weight_kg)}")
    
    # Manejar campos opcionales que podrían venir como strings vacíos
    # Esto es crucial para evitar el error de parsing
    weight_kg_value = None
    if weight_kg and weight_kg.strip() and weight_kg != "null":
        try:
            weight_kg_value = float(weight_kg)
        except (ValueError, TypeError) as e:
            print(f"⚠️ WARN - Could not parse weight_kg '{weight_kg}': {e}")
            weight_kg_value = None
    
    dimensions_cm_value = None
    if dimensions_cm and dimensions_cm.strip() and dimensions_cm != "null":
        dimensions_cm_value = dimensions_cm.strip()
    
    description_value = None
    if description and description.strip() and description != "null":
        description_value = description.strip()
    
    # Si no se proporciona owner_id, usar un valor por defecto (admin)
    owner_id_value = None
    if owner_id and owner_id.strip() and owner_id != "null":
        try:
            owner_id_value = int(owner_id)
        except (ValueError, TypeError):
            # Buscar un usuario admin
            admin_user = session.exec(select(User).where(User.role == "admin").limit(1)).first()
            if admin_user:
                owner_id_value = admin_user.id
    else:
        # Buscar un usuario admin o crear uno dummy
        admin_user = session.exec(select(User).where(User.role == "admin").limit(1)).first()
        if admin_user:
            owner_id_value = admin_user.id
        else:
            # Si no hay admin, usar el primer usuario o None
            any_user = session.exec(select(User).limit(1)).first()
            owner_id_value = any_user.id if any_user else None
    
    print(f"🛠️ DEBUG - Valores procesados:")
    print(f"  - Weight: {weight_kg_value}")
    print(f"  - Dimensions: {dimensions_cm_value}")
    print(f"  - Description: {description_value}")
    print(f"  - Owner ID: {owner_id_value}")
    
    # Procesar imagen si se proporciona
    image_data = None
    if image_file and image_file.filename and image_file.filename != "undefined":
        try:
            print(f"🛠️ DEBUG - Procesando imagen: {image_file.filename}")
            image_data = save_upload_file(image_file, "products")
        except HTTPException as e:
            print(f"❌ ERROR - Error al procesar imagen: {e.detail}")
            raise e
        except Exception as e:
            print(f"❌ ERROR - Error inesperado con imagen: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error al procesar la imagen: {str(e)}"
            )
    else:
        print(f"🛠️ DEBUG - No se proporcionó imagen o es inválida")
    
    # Crear el producto
    product = Product(
        name=name.strip(),
        description=description_value,
        price=price,
        quantity=quantity,
        image_filename=image_data["filename"] if image_data else None,
        image_url=image_data["image_url"] if image_data else None,
        thumbnail_url=image_data["thumbnail_url"] if image_data else None,
        weight_kg=weight_kg_value,
        dimensions_cm=dimensions_cm_value,
        requires_shipping=requires_shipping,
        owner_id=owner_id_value
    )
    
    try:
        session.add(product)
        session.commit()
        session.refresh(product)
        
        print(f"✅ SUCCESS - Producto creado: ID={product.id}, Name={product.name}")
        
        return {
            "message": "Producto creado exitosamente",
            "product": {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": product.price,
                "quantity": product.quantity,
                "image_url": product.image_url,
                "weight_kg": product.weight_kg,
                "dimensions_cm": product.dimensions_cm,
                "requires_shipping": product.requires_shipping,
                "owner_id": product.owner_id,
                "created_at": product.created_at.isoformat() if product.created_at else None
            },
            "image_uploaded": image_data is not None
        }
        
    except Exception as e:
        session.rollback()
        print(f"❌ ERROR - Error al guardar en BD: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar el producto en la base de datos: {str(e)}"
        )

# ======================================================
# 🔵 LISTAR TODOS LOS PRODUCTOS (público)
# ======================================================
@router.get("/list", response_model=List[Product])
def list_products(session: Session = Depends(get_session)):
    products = session.exec(select(Product)).all()
    return products

# ======================================================
# 🟠 ACTUALIZAR PRODUCTO (público) - VERSIÓN CORREGIDA
# ======================================================
@router.put("/{product_id}")
async def update_product(
    product_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    quantity: Optional[int] = Form(None),
    image_file: Optional[UploadFile] = File(None),
    remove_image: Optional[bool] = Form(False),
    weight_kg: Optional[str] = Form(None),  # Cambiado a string
    dimensions_cm: Optional[str] = Form(None),
    requires_shipping: Optional[bool] = Form(None),
    session: Session = Depends(get_session)
):
    """Actualiza un producto (público)"""
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    print(f"🛠️ DEBUG UPDATE PRODUCT - ID: {product_id}")
    
    # Manejar campos que podrían venir como strings vacíos
    if name is not None:
        name = name.strip() if name.strip() else None
    
    if description is not None:
        description = description.strip() if description.strip() else None
    
    if dimensions_cm is not None:
        dimensions_cm = dimensions_cm.strip() if dimensions_cm.strip() else None
    
    # Manejo de peso
    if weight_kg is not None and weight_kg.strip() and weight_kg != "null":
        try:
            weight_kg_value = float(weight_kg)
        except (ValueError, TypeError):
            weight_kg_value = None
    else:
        weight_kg_value = None
    
    # Manejo de imagen
    old_image_filename = product.image_filename
    
    # 1. Eliminar imagen si se solicita
    if remove_image and old_image_filename:
        try:
            delete_image_file(old_image_filename, "products")
            product.image_filename = None
            product.image_url = None
            product.thumbnail_url = None
            print(f"🛠️ DEBUG - Imagen eliminada: {old_image_filename}")
        except Exception as e:
            print(f"⚠️ WARN - No se pudo eliminar imagen: {e}")
    
    # 2. Subir nueva imagen si se proporciona
    elif image_file and image_file.filename and image_file.filename != "undefined":
        try:
            # Eliminar imagen anterior si existe
            if old_image_filename:
                try:
                    delete_image_file(old_image_filename, "products")
                except:
                    pass  # Si falla, continuamos
            
            # Guardar nueva imagen
            image_data = save_upload_file(image_file, "products")
            
            product.image_filename = image_data["filename"]
            product.image_url = image_data["image_url"]
            product.thumbnail_url = image_data["thumbnail_url"]
            
            print(f"🛠️ DEBUG - Nueva imagen guardada: {image_data['filename']}")
            
        except HTTPException as e:
            raise e
        except Exception as e:
            print(f"❌ ERROR - Error al actualizar imagen: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error al actualizar la imagen: {str(e)}"
            )

    # Actualizar otros campos
    if name is not None:
        product.name = name
    if description is not None:
        product.description = description
    if price is not None:
        product.price = price
    if quantity is not None:
        product.quantity = quantity
    if weight_kg_value is not None:
        product.weight_kg = weight_kg_value
    if dimensions_cm is not None:
        product.dimensions_cm = dimensions_cm
    if requires_shipping is not None:
        product.requires_shipping = requires_shipping

    product.updated_at = datetime.utcnow()
    
    try:
        session.add(product)
        session.commit()
        session.refresh(product)
        
        print(f"✅ SUCCESS - Producto actualizado: ID={product.id}")
        
        return {
            "message": "Producto actualizado correctamente", 
            "product": {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": product.price,
                "quantity": product.quantity,
                "image_url": product.image_url,
                "weight_kg": product.weight_kg,
                "dimensions_cm": product.dimensions_cm,
                "requires_shipping": product.requires_shipping,
                "updated_at": product.updated_at.isoformat() if product.updated_at else None
            },
            "image_updated": image_file is not None or remove_image
        }
        
    except Exception as e:
        session.rollback()
        print(f"❌ ERROR - Error al actualizar en BD: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar el producto: {str(e)}"
        )

# ======================================================
# 🔴 ELIMINAR PRODUCTO (público)
# ======================================================
@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    session: Session = Depends(get_session)
):
    """Elimina un producto (público)"""
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Eliminar imagen asociada si existe
    image_deleted = False
    if product.image_filename:
        try:
            delete_image_file(product.image_filename, "products")
            image_deleted = True
        except:
            pass  # Continuar aunque falle eliminar la imagen

    # Registrar en historial
    audit_log = AuditLog(
        action="DELETE_PRODUCT",
        target_id=product_id,
        target_name=product.name,
        performed_by="system",
        details=f"Producto '{product.name}' eliminado sin autenticación"
    )
    session.add(audit_log)
    
    session.delete(product)
    session.commit()
    
    return {
        "message": f"Producto '{product.name}' eliminado exitosamente",
        "image_deleted": image_deleted
    }

# ======================================================
# 🔍 BÚSQUEDA AVANZADA CON FILTROS MÚLTIPLES (público)
# ======================================================
@router.get("/search", response_model=List[Product])
def search_products(
    name: Optional[str] = Query(None, description="Buscar por nombre (búsqueda parcial)"),
    description: Optional[str] = Query(None, description="Buscar en descripción"),
    min_price: Optional[float] = Query(None, ge=0, description="Precio mínimo"),
    max_price: Optional[float] = Query(None, ge=0, description="Precio máximo"),
    min_quantity: Optional[int] = Query(None, ge=0, description="Cantidad mínima"),
    max_quantity: Optional[int] = Query(None, ge=0, description="Cantidad máxima"),
    in_stock: Optional[bool] = Query(None, description="Solo productos con stock"),
    has_image: Optional[bool] = Query(None, description="Solo productos con imagen"),
    owner_id: Optional[int] = Query(None, description="Productos de un usuario específico"),
    created_after: Optional[str] = Query(None, description="Creados después de (YYYY-MM-DD)"),
    session: Session = Depends(get_session)
):
    """Búsqueda avanzada de productos (público)"""
    query = select(Product)
    
    # Filtros de texto
    text_filters = []
    if name:
        text_filters.append(Product.name.ilike(f"%{name}%"))
    if description:
        text_filters.append(Product.description.ilike(f"%{description}%"))
    
    if text_filters:
        query = query.where(or_(*text_filters))
    
    # Filtros numéricos
    numeric_filters = []
    if min_price is not None:
        numeric_filters.append(Product.price >= min_price)
    if max_price is not None:
        numeric_filters.append(Product.price <= max_price)
    if min_quantity is not None:
        numeric_filters.append(Product.quantity >= min_quantity)
    if max_quantity is not None:
        numeric_filters.append(Product.quantity <= max_quantity)
    
    if numeric_filters:
        query = query.where(and_(*numeric_filters))
    
    # Filtro de stock
    if in_stock is not None and in_stock:
        query = query.where(Product.quantity > 0)
    
    # Filtro de imagen
    if has_image is not None:
        if has_image:
            query = query.where(Product.image_url.isnot(None))
        else:
            query = query.where(Product.image_url.is_(None))
    
    # Filtro de dueño
    if owner_id:
        query = query.where(Product.owner_id == owner_id)
    
    # Filtro de fecha
    if created_after:
        try:
            after_date = datetime.fromisoformat(created_after)
            query = query.where(Product.created_at >= after_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido para created_after")
    
    products = session.exec(query).all()
    
    return {
        "filters_applied": {
            "name": name,
            "description": description,
            "price_range": f"{min_price}-{max_price}" if min_price or max_price else None,
            "quantity_range": f"{min_quantity}-{max_quantity}" if min_quantity or max_quantity else None,
            "in_stock": in_stock,
            "has_image": has_image,
            "owner_id": owner_id,
            "created_after": created_after
        },
        "results_count": len(products),
        "products": products
    }

# ======================================================
# 📊 LISTAR PRODUCTOS CON PAGINACIÓN Y ORDENAMIENTO (público)
# ======================================================
@router.get("/all", response_model=List[Product])
def get_all_products(
    skip: int = 0,
    limit: int = 100,
    sort_by: str = Query("name", description="Campo para ordenar: name, price, quantity, created_at"),
    order: str = Query("asc", description="Orden: asc o desc"),
    session: Session = Depends(get_session)
):
    """Lista productos con paginación y ordenamiento (público)"""
    valid_sort_fields = ["name", "price", "quantity", "created_at"]
    if sort_by not in valid_sort_fields:
        sort_by = "name"
    
    order_by_field = getattr(Product, sort_by)
    if order == "desc":
        order_by_field = order_by_field.desc()
    
    query = select(Product).order_by(order_by_field).offset(skip).limit(limit)
    products = session.exec(query).all()
    return products

# ======================================================
# 🔍 VER INFORMACIÓN DEL DUEÑO DE UN PRODUCTO (público)
# ======================================================
@router.get("/{product_id}/owner")
def get_product_owner(
    product_id: int,
    session: Session = Depends(get_session)
):
    """Obtiene información del usuario dueño de un producto (público)"""
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    if not product.owner:
        return {"message": "Este producto no tiene dueño asignado"}
    
    return {
        "owner_id": product.owner.id,
        "owner_username": product.owner.username,
        "owner_role": product.owner.role,
        "owner_created_at": product.owner.created_at
    }

# ======================================================
# 🏆 PRODUCTOS DESTACADOS (público)
# ======================================================
@router.get("/featured")
def get_featured_products(
    category: Optional[str] = Query(None, description="Filtrar por categoría futura"),
    limit: int = Query(10, le=50, description="Límite de productos"),
    require_images: bool = Query(True, description="Solo productos con imágenes"),
    session: Session = Depends(get_session)
):
    """Obtiene productos destacados (público)"""
    query = select(Product).where(Product.quantity > 0)
    
    if require_images:
        query = query.where(Product.image_url.isnot(None))
    
    query = query.order_by(
        Product.quantity.desc(),
        Product.price.asc()
    ).limit(limit)
    
    featured_products = session.exec(query).all()
    
    return {
        "featured_criteria": "High stock & best price" + (" with images" if require_images else ""),
        "products": featured_products
    }

# ======================================================
# 📸 ENDPOINTS ESPECÍFICOS PARA IMÁGENES (público)
# ======================================================

@router.post("/{product_id}/upload-image")
async def upload_product_image(
    product_id: int,
    image_file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """Sube o reemplaza la imagen de un producto (público)"""
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Eliminar imagen anterior si existe
    if product.image_filename:
        try:
            delete_image_file(product.image_filename, "products")
        except:
            pass  # Continuar si falla
    
    # Guardar nueva imagen
    try:
        image_data = save_upload_file(image_file, "products")
        
        # Actualizar producto
        product.image_filename = image_data["filename"]
        product.image_url = image_data["image_url"]
        product.thumbnail_url = image_data["thumbnail_url"]
        
        session.add(product)
        session.commit()
        
        return {
            "message": "Imagen subida exitosamente",
            "product_id": product_id,
            "product_name": product.name,
            "image_url": product.image_url,
            "thumbnail_url": product.thumbnail_url
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al subir imagen: {str(e)}"
        )

@router.delete("/{product_id}/image")
def delete_product_image(
    product_id: int,
    session: Session = Depends(get_session)
):
    """Elimina solo la imagen de un producto (público)"""
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    if not product.image_filename:
        raise HTTPException(status_code=400, detail="El producto no tiene imagen")
    
    # Eliminar imagen
    try:
        deleted = delete_image_file(product.image_filename, "products")
        
        if deleted:
            # Actualizar producto
            product.image_filename = None
            product.image_url = None
            product.thumbnail_url = None
            
            session.add(product)
            session.commit()
            
            return {
                "message": "Imagen eliminada exitosamente",
                "product_id": product_id,
                "product_name": product.name
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="No se pudo eliminar la imagen"
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar imagen: {str(e)}"
        )