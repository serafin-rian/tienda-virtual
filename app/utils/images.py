import os
import uuid
from fastapi import UploadFile, HTTPException
from PIL import Image
import io
from typing import Dict, Optional

# Configuración
UPLOAD_DIR = "app/static/uploads"
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_SIZE_MB = 10  # 10MB máximo por imagen
THUMBNAIL_SIZE = (300, 300)  # Tamaño de miniatura

def validate_image_file(upload_file: UploadFile) -> None:
    """Valida el archivo de imagen"""
    # Validar extensión
    filename = upload_file.filename.lower()
    ext = os.path.splitext(filename)[1]
    
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de imagen no permitido. Formatos aceptados: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Validar tipo MIME
    content_type = upload_file.content_type
    if not content_type or not content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail="El archivo debe ser una imagen"
        )

def save_upload_file(upload_file: UploadFile, subfolder: str = "products") -> Dict[str, str]:
    """
    Guarda un archivo de imagen subido y crea una miniatura.
    
    Args:
        upload_file: Archivo subido via FastAPI UploadFile
        subfolder: Subcarpeta dentro de uploads (products, users, etc.)
    
    Returns:
        Diccionario con información del archivo guardado
    """
    # Validar archivo
    validate_image_file(upload_file)
    
    # Leer contenido
    contents = upload_file.file.read()
    
    # Validar tamaño
    if len(contents) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"Imagen demasiado grande. Tamaño máximo: {MAX_SIZE_MB}MB"
        )
    
    # Generar nombre único
    original_filename = upload_file.filename
    ext = os.path.splitext(original_filename)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    
    # Rutas
    folder_path = os.path.join(UPLOAD_DIR, subfolder)
    thumb_folder_path = os.path.join(folder_path, "thumbnails")
    
    # Crear directorios si no existen
    os.makedirs(folder_path, exist_ok=True)
    os.makedirs(thumb_folder_path, exist_ok=True)
    
    # Rutas completas
    file_path = os.path.join(folder_path, unique_filename)
    thumb_path = os.path.join(thumb_folder_path, unique_filename)
    
    try:
        # Guardar imagen original
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Crear y guardar miniatura
        create_thumbnail(contents, thumb_path)
        
        # URLs relativas
        image_url = f"/static/uploads/{subfolder}/{unique_filename}"
        thumbnail_url = f"/static/uploads/{subfolder}/thumbnails/{unique_filename}"
        
        return {
            "original_filename": original_filename,
            "filename": unique_filename,
            "file_path": file_path,
            "image_url": image_url,
            "thumbnail_url": thumbnail_url,
            "content_type": upload_file.content_type,
            "size_bytes": len(contents)
        }
        
    except Exception as e:
        # Limpiar en caso de error
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar la imagen: {str(e)}"
        )

def create_thumbnail(image_data: bytes, output_path: str, size: tuple = THUMBNAIL_SIZE) -> None:
    """Crea una miniatura de la imagen"""
    try:
        # Abrir imagen desde bytes
        image = Image.open(io.BytesIO(image_data))
        
        # Convertir a RGB si es necesario
        if image.mode in ('RGBA', 'LA', 'P'):
            # Crear fondo blanco para imágenes con transparencia
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Calcular nuevo tamaño manteniendo aspecto
        image.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Guardar miniatura
        image.save(output_path, 'JPEG', quality=85, optimize=True)
        
    except Exception as e:
        raise Exception(f"Error al crear miniatura: {str(e)}")

def delete_image_file(filename: str, subfolder: str = "products") -> bool:
    """
    Elimina una imagen y su miniatura
    
    Args:
        filename: Nombre del archivo a eliminar
        subfolder: Subcarpeta donde se encuentra
    
    Returns:
        True si se eliminó correctamente
    """
    try:
        # Rutas
        file_path = os.path.join(UPLOAD_DIR, subfolder, filename)
        thumb_path = os.path.join(UPLOAD_DIR, subfolder, "thumbnails", filename)
        
        # Eliminar archivos si existen
        deleted = False
        if os.path.exists(file_path):
            os.remove(file_path)
            deleted = True
        
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        
        return deleted
        
    except Exception as e:
        print(f"Error al eliminar imagen {filename}: {str(e)}")
        return False

def get_image_info(filename: str, subfolder: str = "products") -> Optional[Dict]:
    """
    Obtiene información de una imagen guardada
    
    Args:
        filename: Nombre del archivo
        subfolder: Subcarpeta donde se encuentra
    
    Returns:
        Diccionario con información o None si no existe
    """
    file_path = os.path.join(UPLOAD_DIR, subfolder, filename)
    thumb_path = os.path.join(UPLOAD_DIR, subfolder, "thumbnails", filename)
    
    if not os.path.exists(file_path):
        return None
    
    try:
        # Obtener información del archivo
        stat_info = os.stat(file_path)
        
        # Obtener dimensiones de la imagen
        with Image.open(file_path) as img:
            width, height = img.size
        
        return {
            "filename": filename,
            "file_path": file_path,
            "image_url": f"/static/uploads/{subfolder}/{filename}",
            "thumbnail_url": f"/static/uploads/{subfolder}/thumbnails/{filename}" 
                       if os.path.exists(thumb_path) else None,
            "size_bytes": stat_info.st_size,
            "created_at": stat_info.st_ctime,
            "modified_at": stat_info.st_mtime,
            "dimensions": {
                "width": width,
                "height": height
            },
            "exists": True
        }
        
    except Exception as e:
        print(f"Error al obtener información de imagen {filename}: {str(e)}")
        return None

def cleanup_old_images(days_old: int = 30, subfolder: str = "temp") -> Dict[str, int]:
    """
    Elimina imágenes antiguas no utilizadas
    
    Args:
        days_old: Días de antigüedad para considerar como "viejo"
        subfolder: Subcarpeta a limpiar
    
    Returns:
        Diccionario con estadísticas de limpieza
    """
    import time
    from datetime import datetime, timedelta
    
    folder_path = os.path.join(UPLOAD_DIR, subfolder)
    thumb_folder_path = os.path.join(folder_path, "thumbnails")
    
    if not os.path.exists(folder_path):
        return {"deleted": 0, "errors": 0}
    
    cutoff_time = time.time() - (days_old * 24 * 60 * 60)
    deleted_count = 0
    error_count = 0
    
    # Limpiar carpeta principal
    for filename in os.listdir(folder_path):
        if filename == "thumbnails":
            continue
            
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path):
                file_mtime = os.path.getmtime(file_path)
                if file_mtime < cutoff_time:
                    os.remove(file_path)
                    deleted_count += 1
                    
                    # También eliminar miniatura si existe
                    thumb_path = os.path.join(thumb_folder_path, filename)
                    if os.path.exists(thumb_path):
                        os.remove(thumb_path)
                        
        except Exception as e:
            print(f"Error al eliminar {filename}: {str(e)}")
            error_count += 1
    
    # Limpiar thumbnails (por si hay archivos huérfanos)
    if os.path.exists(thumb_folder_path):
        for filename in os.listdir(thumb_folder_path):
            thumb_path = os.path.join(thumb_folder_path, filename)
            original_path = os.path.join(folder_path, filename)
            
            if not os.path.exists(original_path):
                try:
                    os.remove(thumb_path)
                    deleted_count += 1
                except:
                    error_count += 1
    
    return {
        "deleted_files": deleted_count,
        "errors": error_count,
        "cutoff_date": datetime.fromtimestamp(cutoff_time).isoformat()
    }