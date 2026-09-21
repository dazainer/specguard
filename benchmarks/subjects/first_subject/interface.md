# Public interface

The target snapshot root is on the Python import path inside the future runner.

```python
from src.reservations import quote, cancellation_refund

def quote(nights: int, nightly_rate_cents: int, guests: int = 1, member: bool = False) -> int: ...
def cancellation_refund(total_cents: int, days_before: int) -> int: ...
```

The specification defines validation rules, discount order, rounding, and refund boundaries. Call these public functions directly. No fixtures, I/O, credentials, or external dependencies are required. Native tests are deliberately withheld from generation context.
