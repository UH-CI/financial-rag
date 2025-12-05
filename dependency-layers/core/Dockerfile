FROM python:3.11-slim

# Set working directory

# Install system dependencies including Chrome for Selenium
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    poppler-utils \
    build-essential \
    curl \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome for fiscal note generation web scraping
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* 

# Set environment variables to force CPU-only packages
ENV TORCH_CUDA_ARCH_LIST=""
ENV FORCE_CUDA="0"
ENV CUDA_VISIBLE_DEVICES=""

# Copy requirements and install Python dependencies
COPY requirements.txt .

# Install PyTorch CPU-only first to avoid CUDA dependencies
RUN pip install --no-cache-dir --timeout=1800 --retries=5 \
    torch==2.1.0+cpu torchvision==0.16.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies (without sentence-transformers)
RUN pip install --no-cache-dir --timeout=1800 --retries=5 -r requirements.txt

# Install sentence-transformers AFTER PyTorch CPU is locked in
RUN pip install --no-cache-dir --timeout=1800 --retries=5 sentence-transformers