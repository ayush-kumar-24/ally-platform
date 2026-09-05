"""Founder-facing payments HTTP API. See app/payments/__init__.py for the
domain layer; the Razorpay webhook itself lives at
app/api/v1/webhooks/razorpay.py, not here -- it carries no founder identity
and is authenticated a completely different way (a signed payload, not a
bearer token)."""

from app.api.v1.payments.router import router

__all__ = ["router"]
