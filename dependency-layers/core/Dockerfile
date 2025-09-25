FROM python:3.11-slim

# Set working directory

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    poppler-utils \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/* 

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt