"""Integer-only reservation pricing and cancellation refunds."""


def _integer(value, name, minimum, maximum):
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} is out of range")


def quote(nights: int, nightly_rate_cents: int, guests: int = 1, member: bool = False) -> int:
    _integer(nights, "nights", 1, 30)
    _integer(nightly_rate_cents, "nightly_rate_cents", 0, 100000)
    _integer(guests, "guests", 1, 6)
    if type(member) is not bool:
        raise TypeError("member must be a boolean")
    total = nights * (nightly_rate_cents + max(guests - 2, 0) * 2000)
    if nights >= 7:
        total = total * 90 // 100
    if member:
        total = total * 95 // 100
    return total


def cancellation_refund(total_cents: int, days_before: int) -> int:
    _integer(total_cents, "total_cents", 0, 10000000)
    _integer(days_before, "days_before", 0, 365)
    if days_before >= 7:
        return total_cents
    if days_before >= 2:
        return total_cents // 2
    return 0
