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

# Set environment variables to force CPU-only packages
ENV TORCH_CUDA_ARCH_LIST=""
ENV FORCE_CUDA="0"
ENV CUDA_VISIBLE_DEVICES=""

# Copy requirements and install Python dependencies with optimizations
COPY requirements.txt .

# Install PyTorch CPU-only first to avoid CUDA dependencies
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir --timeout=1800 --retries=5 \
    torch==2.1.0+cpu torchvision==0.16.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies (without chromadb, sentence-transformers, camelot-py)
RUN pip install --no-cache-dir --timeout=1800 --retries=5 --prefer-binary -r requirements.txt

# Install packages that might pull CUDA AFTER PyTorch CPU is locked in
RUN pip install --no-cache-dir --timeout=1800 --retries=5 chromadb camelot-py

# Install sentence-transformers dependencies manually, then sentence-transformers with --no-deps
RUN pip install --no-cache-dir --timeout=1800 --retries=5 \
    transformers tqdm requests filelock huggingface-hub tokenizers safetensors
RUN pip install --no-cache-dir --timeout=1800 --retries=5 --no-deps sentence-transformers

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