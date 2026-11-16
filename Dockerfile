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

# Expose server port
EXPOSE 8000

ENV PYTHONUNBUFFERED=1

# Start FastAPI server
CMD ["uvicorn", "clipwise.app:app", "--host", "0.0.0.0", "--port", "8000"]
