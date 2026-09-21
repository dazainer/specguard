def overlap_length(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    if a_end < a_start or b_end < b_start:
        raise ValueError("reversed interval")
    return max(0, min(a_end, b_end) - max(a_start, b_start))
