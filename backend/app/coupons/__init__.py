"""Coupons -- a redeemable discount on the single payment a founder makes.

The discount is applied where the price is decided (PaymentService.
start_checkout), never at the gateway: `payments.amount_inr` is what the admin
revenue views read, so charging one number and recording another would make
every revenue figure a small lie. See the migration a7f2c81d94e3 for the full
reasoning, including why a redemption is a row rather than a counter.
"""
