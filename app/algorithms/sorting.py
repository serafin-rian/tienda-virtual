from typing import Callable, List, Tuple, Any

def _keys_snapshot(items: List[Any], key: Callable) -> List:
    """Helper: devuelve la lista de claves (para registro de pasos)."""
    return [key(x) for x in items]

# -------------------------
# QuickSort (con pasos)
# -------------------------
def quicksort_with_steps(items: List, key: Callable, steps: List[List] = None) -> Tuple[List, List]:
    """Ordena 'items' usando quicksort y registra snapshots de las claves."""
    if steps is None:
        steps = []

    def _quicksort(arr: List):
        if len(arr) <= 1:
            return arr
        pivot = key(arr[len(arr) // 2])
        left = [x for x in arr if key(x) < pivot]
        middle = [x for x in arr if key(x) == pivot]
        right = [x for x in arr if key(x) > pivot]

        # registrar estado actual para visualización
        steps.append(_keys_snapshot(left + middle + right, key))
        sorted_left = _quicksort(left)
        sorted_right = _quicksort(right)
        merged = sorted_left + middle + sorted_right
        steps.append(_keys_snapshot(merged, key))
        return merged

    sorted_items = _quicksort(items)
    return sorted_items, steps

# -------------------------
# MergeSort (con pasos)
# -------------------------
def mergesort_with_steps(items: List, key: Callable, steps: List[List] = None) -> Tuple[List, List]:
    """Ordena 'items' usando mergesort y registra snapshots de las claves."""
    if steps is None:
        steps = []

    def _merge(left: List, right: List):
        merged = []
        i = j = 0
        while i < len(left) and j < len(right):
            if key(left[i]) <= key(right[j]):
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                j += 1
        merged.extend(left[i:])
        merged.extend(right[j:])
        steps.append(_keys_snapshot(merged, key))
        return merged

    def _mergesort(arr: List):
        if len(arr) <= 1:
            return arr
        mid = len(arr) // 2
        left = _mergesort(arr[:mid])
        right = _mergesort(arr[mid:])
        return _merge(left, right)

    sorted_items = _mergesort(items)
    return sorted_items, steps

# -------------------------
# Wrapper simple (sin pasos)
# -------------------------
def quicksort(items: List, key: Callable):
    sorted_items, _ = quicksort_with_steps(list(items), key, steps=[])
    return sorted_items

def mergesort(items: List, key: Callable):
    sorted_items, _ = mergesort_with_steps(list(items), key, steps=[])
    return sorted_items