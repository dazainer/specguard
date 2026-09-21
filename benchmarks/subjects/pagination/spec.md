# pagination contract

For integer inputs, return the zero-based half-open (start, stop) slice of a page. Pages are one-based; size is positive; total is nonnegative. Clamp both endpoints to total. Reject total < 0, page < 1, or size < 1 with ValueError. Other input types are outside this contract.
