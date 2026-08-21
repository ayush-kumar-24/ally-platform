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
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
