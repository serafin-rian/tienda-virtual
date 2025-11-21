def greedy_best_products(products, budget):
    """
    Selecciona productos maximizando valor/precio usando algoritmo voraz.
    """
    # 1. Ordenar productos por valor/precio descendente
    sorted_products = sorted(products, key=lambda p: p.price / (p.quantity if p.quantity > 0 else 1), reverse=True)

    selected = []
    total_cost = 0

    for p in sorted_products:
        if total_cost + p.price <= budget:
            selected.append(p)
            total_cost += p.price

    return {
        "budget": budget,
        "total_spent": total_cost,
        "selected_products": selected,
    }