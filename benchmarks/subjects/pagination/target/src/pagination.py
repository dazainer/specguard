def page_slice(total: int, page: int, size: int) -> tuple[int, int]:
    if total < 0 or page < 1 or size < 1:
        raise ValueError("range")
    start = (page - 1) * size
    return min(start, total), min(start + size, total)
