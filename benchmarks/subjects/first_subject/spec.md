# Reservation pricing specification

All monetary amounts are integer cents. Calculations are deterministic and use no network, clock, filesystem, or external service.

- R1: A quote accepts 1–30 nights, a nightly rate of 0–100000 cents, and 1–6 guests, inclusively. Guests default to 1 and membership defaults to false.
- R2: Nights, nightly rate, and guests must be Python integers; booleans are not accepted as integers. Wrong types raise `TypeError`; out-of-range integers raise `ValueError`. Membership must be a boolean or raises `TypeError`.
- R3: The first two guests are included in the nightly rate. Each additional guest costs 2000 cents per night.
- R4: Stays of at least seven nights receive a 10% discount on the whole subtotal, including extra-guest charges. Round down to whole cents immediately after this discount.
- R5: Members receive a further 5% discount on the resulting total, rounded down to whole cents. Apply this after the long-stay discount; nonmembers receive no membership discount.
- R6: A cancellation refund accepts a paid total of 0–10000000 cents and 0–365 days before arrival, inclusively. Both arguments must be integers, excluding booleans. Wrong types raise `TypeError`; out-of-range integers raise `ValueError`.
- R7: Cancellation at least seven days before arrival refunds the entire total. Cancellation two through six days before arrival refunds half, rounded down to whole cents. Cancellation zero or one day before arrival refunds zero.
- R8: Both functions return integer cents and do not mutate inputs or maintain state.
