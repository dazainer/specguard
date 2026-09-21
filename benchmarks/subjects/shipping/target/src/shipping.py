def shipping_charge(weight: int, subtotal: int) -> int:
    if weight <= 0 or subtotal < 0:
        raise ValueError("range")
    if subtotal >= 5000:
        return 0
    return 700 if weight > 1000 else 400
