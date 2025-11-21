# app/algorithms/router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Callable, Any
from ..database import get_session
from ..models import Product

# Importar algoritmos de ordenamiento
from .sorting import quicksort_with_steps, mergesort_with_steps, quicksort, mergesort

# Importar algoritmo greedy
from .greedy import greedy_best_products


router = APIRouter(
    prefix="/algorithms",
    tags=["algorithms"]
)

def product_to_dict(p: Product) -> dict:
    """Convierte un Product SQLModel a dict manejable para salida JSON."""
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "price": p.price,
        "quantity": p.quantity,
        "image_path": p.image_path,
        "owner_id": p.owner_id,
        "created_at": p.created_at,
    }

# ======================================================
# 🟦 ORDENAMIENTO: QuickSort / MergeSort
# ======================================================
@router.get("/sort")
def sort_products(
    method: str = Query("quicksort", regex="^(quicksort|mergesort)$"),
    by: str = Query("price", regex="^(price|name|quantity)$"),
    steps: bool = Query(False),
    session: Session = Depends(get_session)
):
    """
    Ordena productos reales de la base de datos.
    - method: 'quicksort' o 'mergesort'
    - by: 'price', 'name' o 'quantity'
    - steps: si True, devuelve snapshots de la evolución del algoritmo
    """
    products: List[Product] = session.exec(select(Product)).all()
    if not products:
        raise HTTPException(status_code=404, detail="No hay productos en la base de datos.")

    # define key function según 'by'
    if by == "price":
        key: Callable[[Product], Any] = lambda p: p.price
    elif by == "name":
        key = lambda p: p.name.lower() if p.name else ""
    elif by == "quantity":
        key = lambda p: p.quantity
    else:
        raise HTTPException(status_code=400, detail="Campo de ordenamiento inválido.")

    # QuickSort o MergeSort + steps opcional
    if method == "quicksort":
        if steps:
            sorted_products, trace = quicksort_with_steps(products, key)
        else:
            sorted_products = quicksort(products, key)
            trace = []
    else:  # mergesort
        if steps:
            sorted_products, trace = mergesort_with_steps(products, key)
        else:
            sorted_products = mergesort(products, key)
            trace = []

    sorted_dicts = [product_to_dict(p) for p in sorted_products]

    return {
        "method": method,
        "by": by,
        "count": len(sorted_dicts),
        "steps": trace if steps else None,
        "sorted": sorted_dicts
    }


# ======================================================
# 🟩 GREEDY: Selección óptima de productos con presupuesto
# ======================================================
@router.get("/greedy/best-products")
def greedy_products(
    budget: float = Query(..., gt=0, description="Presupuesto disponible"),
    session: Session = Depends(get_session)
):
    """
    Algoritmo voraz (Greedy) para seleccionar los mejores productos
    dentro de un presupuesto limitado.
    """
    products = session.exec(select(Product)).all()

    if not products:
        raise HTTPException(status_code=404, detail="No hay productos en la base de datos.")

    result = greedy_best_products(products, budget)

    # Convertimos los productos seleccionados a dict
    result["selected_products"] = [product_to_dict(p) for p in result["selected_products"]]

    return result
