# shipping contract

For integer weight in grams and subtotal in cents, require weight > 0 and subtotal >= 0 or raise ValueError. Validate before applying free shipping. Shipping is free when subtotal >= 5000; otherwise costs 700 cents for weight > 1000 and 400 cents for weight <= 1000. Other types are outside the contract.
