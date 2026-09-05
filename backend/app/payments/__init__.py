"""Payments -- Admin Panel Proposal Phase 4: "Connect the real payment gateway
so a plan is granted only when money is actually received."

Before this, checkout (frontend/src/pages/Billing.jsx) collected a card
number, expiry and CVV into a form, waited 2.2 seconds, and reported success
-- the code's own comment already flagged it: "this does not charge anything
... there is no processor integration behind this screen yet." No backend
endpoint existed that could grant a plan from a payment at all; the only way
a founder's plan_type ever changed was an admin doing it by hand
(PATCH /admin/users/{id}/subscription).

Layout:
    gateway.py     PaymentGateway protocol + RazorpayGateway (httpx, no SDK
                    dependency -- a thin wrapper over Razorpay's plain REST
                    API, same shape as object_storage.py's S3ObjectStorage).
    models.py       Domain dataclasses: CheckoutSession, WebhookOutcome.
    repository.py   Raw-SQL reads/writes against payments/subscriptions/
                    founders -- same style as app/admin/users_db_repository.py.
    service.py      PaymentService: start_checkout, handle_webhook.

Money-safety is the organizing constraint throughout, not an afterthought:
- Unconfigured (no Razorpay keys) refuses to create an order (503) rather
  than faking a successful checkout -- unlike, say, email.py's stub mode,
  a stub "payment succeeded" here would hand out a paid plan for nothing.
- The webhook handler is idempotent on `gateway_payment_id`: Razorpay
  retries webhook deliveries, and a plan/credit grant must never apply
  twice for the same payment.
- The plan is granted from the webhook (server-to-server, signed), never
  from the frontend's post-checkout redirect -- a founder closing the tab,
  or forging that redirect, must not be able to grant themselves a plan.
"""
