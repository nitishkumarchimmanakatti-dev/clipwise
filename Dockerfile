# Production Dockerfile for Clipwise Web Application
FROM python:3.11-slim

# Install system dependencies: ffmpeg with libass, git, curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libass-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency requirements
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose default port
EXPOSE 8000

# Start FastAPI server using Railway's PORT or fallback to 8000
CMD ["sh", "-c", "uvicorn clipwise.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
