FROM ghcr.io/uh-ci/rag-system-core-dependencies:latest


# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=1800 --retries=5 -r requirements.txt