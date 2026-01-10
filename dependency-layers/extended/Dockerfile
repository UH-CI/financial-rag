FROM ghcr.io/uh-ci/rag-system-core-dependencies:latest


# Copy requirements and install Python dependenciesf
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=600 --retries=5 -r requirements.txt