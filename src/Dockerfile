FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Note: ChromaDB data will be provided via volume mount in production
# (chroma_db/ should be excluded via .dockerignore to avoid conflicts)

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose ports (8000 for API, 8080 for test interface)
EXPOSE 8000 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Default command runs API server
CMD ["python", "run_api.py"]

# Alternative commands:
# docker run -p 8000:8000 your-image                    # API server
# docker run -p 8080:8080 your-image python tests/test_server.py  # Test interface
# docker run -p 8000:8000 -p 8080:8080 your-image bash # Interactive 