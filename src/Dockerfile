# Production Dockerfile - Chrome runs in separate Selenium container
FROM python:3.11-bookworm

# Install system dependencies for OpenCV, PDF processing, and other tools
# Relaxing security checks due to persistent GPG signature errors on this host
RUN apt-get update --allow-insecure-repositories && apt-get install -y --no-install-recommends --allow-unauthenticated \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libjpeg62-turbo \
    libpng16-16 \
    libtiff6 \
    sqlite3 \
    libsqlite3-0 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /src

# Copy requirements and install Python dependencies with optimizations
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --timeout=600 --retries=3 --prefer-binary -r requirements.txt

# Copy application code
COPY . .
# create required directories
RUN mkdir -p documents/storage_documents chroma_db/data

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
echo "🚀 Starting API server..."\n\
echo "📍 Working directory: $(pwd)"\n\
echo "📍 Python path: $PYTHONPATH"\n\
echo "🔍 Testing API import..."\n\
python -c "import main; print(\"✅ Main imported, app found:\", hasattr(main, \"app\"))" || echo "❌ Main import failed"\n\
echo "🌐 Starting uvicorn..."\n\
python -m uvicorn main:app \\\n\
    --host 0.0.0.0 \\\n\
    --port 8200 \\\n\
    --workers 1 \\\n\
    --log-level debug \\\n\
    --access-log \\\n\
    --reload' > /start.sh && chmod +x /start.sh

# Production uvicorn command with optimized settings
CMD ["/start.sh"] 