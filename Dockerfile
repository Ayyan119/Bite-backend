# Build stage
FROM python:3.10-slim AS builder

WORKDIR /build

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy requirements file
COPY requirements.txt .

# Install dependencies into a temporary location without pytest/dev dependencies
RUN grep -v -E "pytest|pytest-asyncio" requirements.txt > reqs_prod.txt && \
    pip install --no-cache-dir --prefix=/install -r reqs_prod.txt

# Final runtime stage
FROM python:3.10-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

# Copy installed dependencies from builder stage
COPY --from=builder /install /usr/local

# Copy application source code and migrations
COPY app /app/app
COPY migrations /app/migrations

# Expose FastAPI default port
EXPOSE 8000

# Run FastAPI app with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
