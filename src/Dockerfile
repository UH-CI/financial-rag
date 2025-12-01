# Production Dockerfile - Chrome runs in separate Selenium container
FROM python:3.11-slim

# Install system dependencies for OpenCV, PDF processing, and other tools
RUN apt-get update && apt-get install -y \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgtk-3-0 \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    libjpeg62-turbo \
    libpng16-16 \
    libtiff6 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /src

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
# create storage_documents dir
RUN mkdir -p documents/storage_documents

# Set environment variables
ENV PYTHONPATH=/src
ENV PYTHONUNBUFFERED=1
ENV DOCKER_ENV=true

# Expose ports (8200 for API, 8280 for test interface)
EXPOSE 8200 8280

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8200/ || exit 1

# Create startup script for flexible uvicorn configuration
RUN echo '#!/bin/bash\n\
uvicorn api:app \\\n\
    --host 0.0.0.0 \\\n\
    --port 8200 \\\n\
    --workers ${WORKERS:-4} \\\n\
    --log-level ${LOG_LEVEL:-info} \\\n\
    --access-log \\\n\
    --loop uvloop \\\n\
    --http httptools \\\n\
    --ws websockets \\\n\
    --lifespan on \\\n\
    --timeout-keep-alive 30 \\\n\
    --timeout-graceful-shutdown 30 \\\n\
    --backlog 2048' > /start.sh && chmod +x /start.sh

# Production uvicorn command with optimized settings
CMD ["/start.sh"] 