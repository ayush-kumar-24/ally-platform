# Production image for AWS ECS Fargate (or any container host).
#
# Hosted environments provide configuration through environment variables.
# Uvicorn runs without --reload in production.

FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so Docker can reuse this layer when only
# application code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run the application as a non-root user.
# The uploads directory must be writable by the application user.
RUN useradd --create-home --shell /bin/bash ally && \
    mkdir -p /app/uploads/avatars && \
    chown -R ally:ally /app

USER ally

EXPOSE 8000

# IMPORTANT:
# Database migrations are NOT run automatically when each ECS task starts.
# The CI/CD deployment workflow will run Alembic once before updating ECS.
# This avoids multiple ECS tasks trying to migrate the database concurrently.
# --proxy-headers: without it uvicorn ignores X-Forwarded-Proto and believes
# every request arrived over plain HTTP, because the TLS terminates at the load
# balancer. Confirmed in production on 2026-08-22: a trailing-slash request to
# api.goxlally.ai answered
#
#     307 -> location: http://origin-api.goxlally.ai/api/v1/planning/plans
#
# An http:// redirect from an https:// page is blocked as mixed content, so any
# URL a browser reaches with a trailing slash is simply broken.
#
# --forwarded-allow-ips "*" trusts those headers from any peer. Safe HERE and
# only here: the container sits in a private subnet and is reachable solely
# through the load balancer, so nothing else can set them. If this service is
# ever exposed directly, narrow it to the balancer's CIDR — an attacker who can
# reach uvicorn without going through the proxy could otherwise forge the
# client IP and scheme.
#
# NOTE this fixes the SCHEME only. The origin-api hostname above comes from the
# Host header, and uvicorn's proxy middleware deliberately does not read
# X-Forwarded-Host — verified against uvicorn 0.51.0. Correcting the host needs
# the CDN to forward the original Host. Until then, PUBLIC_APP_URL is what keeps
# founder-facing links right, because it bypasses request.base_url entirely.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
