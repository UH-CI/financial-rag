# House Finance Document API

A FastAPI-based REST API for managing and searching financial documents using ChromaDB and Google AI embeddings.

## Quick Start

### 1. Start the API Server

```bash
# Option 1: Using the startup script
python run_api.py

# Option 2: Direct uvicorn command
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

The server will start at `http://localhost:8000`

### 2. Access API Documentation

- **Interactive API Docs**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc (ReDoc)

### 3. Test the API

```bash
# Run the example client
python tests/api_client_example.py
```

## API Endpoints

### Health Check
- **GET** `/` - Check API status and configuration

### Document Management
- **POST** `/upload` - Upload files for processing
- **POST** `/ingest-directory` - Process all documents in a directory
- **DELETE** `/reset` - Clear all documents from the collection

### Search & Retrieval
- **POST** `/search` - Search documents using semantic similarity
- **GET** `/documents/{document_id}` - Get a specific document by ID
- **GET** `/stats` - Get collection statistics

## Usage Examples

### 1. Health Check

```bash
curl http://localhost:8000/
```

Response:
```json
{
  "message": "House Finance Document API",
  "status": "healthy",
  "embedding_model": "text-embedding-004",
  "embedding_provider": "google"
}
```

### 2. Get Collection Statistics

```bash
curl http://localhost:8000/stats
```

Response:
```json
{
  "collection_name": "financial_documents",
  "document_count": 156,
  "embedding_model": "text-embedding-004",
  "embedding_dimensions": 768
}
```

### 3. Search Documents

```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "budget allocation for education",
    "n_results": 3,
    "include_metadata": true
  }'
```

Response:
```json
{
  "query": "budget allocation for education",
  "results": [
    {
      "id": "doc_123_chunk_5",
      "content": "The Department of Education shall receive $2.5 billion...",
      "score": 0.892,
      "metadata": {
        "filename": "HB300_HD1.pdf",
        "fiscal_year": "2024-2025",
        "department": "Department of Education",
        "chunk_index": 5
      }
    }
  ],
  "total_results": 3
}
```

### 4. Upload Files

```bash
curl -X POST "http://localhost:8000/upload" \
  -F "files=@/path/to/document1.pdf" \
  -F "files=@/path/to/document2.pdf"
```

### 5. Ingest Directory

```bash
curl -X POST "http://localhost:8000/ingest-directory?directory_path=/path/to/documents"
```

### 6. Reset Collection

```bash
curl -X DELETE "http://localhost:8000/reset"
```

## Python Client Example

```python
import requests

# Initialize client
base_url = "http://localhost:8000"

# Search documents
search_payload = {
    "query": "healthcare funding",
    "n_results": 5,
    "include_metadata": True
}

response = requests.post(f"{base_url}/search", json=search_payload)
results = response.json()

for result in results["results"]:
    print(f"Score: {result['score']:.3f}")
    print(f"Content: {result['content'][:200]}...")
    print(f"Metadata: {result['metadata']}")
    print("-" * 50)
```

## Request/Response Models

### SearchQuery
```json
{
  "query": "string",           // Required: search text
  "n_results": 5,             // Optional: number of results (1-50)
  "include_metadata": true    // Optional: include metadata
}
```

### SearchResult
```json
{
  "id": "string",             // Document chunk ID
  "content": "string",        // Document content
  "score": 0.892,            // Similarity score (0-1)
  "metadata": {              // Optional metadata
    "filename": "string",
    "fiscal_year": "string",
    "department": "string",
    "chunk_index": 0
  }
}
```

### IngestionResponse
```json
{
  "success": true,
  "message": "Successfully processed 4 documents with 156 chunks",
  "documents": [
    {
      "filename": "HB300.pdf",
      "size": 1048576,
      "chunks_created": 39,
      "metadata": {
        "fiscal_year": "2024-2025",
        "bill_version": "Original"
      }
    }
  ]
}
```

## Configuration

The API uses the same configuration as the core system:

- **Environment Variables**: `.env` file
- **Google API Key**: Required for embeddings
- **ChromaDB**: Always runs in embedded mode
- **Embedding Model**: `text-embedding-004` (default)

## Error Handling

The API returns standard HTTP status codes:

- **200**: Success
- **400**: Bad Request (invalid parameters)
- **404**: Not Found (document/endpoint not found)
- **500**: Internal Server Error

Error responses include detailed messages:
```json
{
  "detail": "Error message describing what went wrong"
}
```

## Production Deployment

For production deployment:

1. **Use Gunicorn** instead of uvicorn for better performance:
   ```bash
   gunicorn src.api:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

2. **Configure CORS** appropriately in `api.py`

3. **Use HTTPS** with a reverse proxy (nginx/Apache)

4. **Set up authentication** if needed

5. **Ensure sufficient disk space** for the embedded database

6. **Regular backups** of the `chroma_db/data/` directory

## Integration Examples

### JavaScript/TypeScript
```javascript
const searchDocuments = async (query) => {
  const response = await fetch('http://localhost:8000/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, n_results: 5 })
  });
  return await response.json();
};
```

### Python with requests
```python
import requests

def search_documents(query, n_results=5):
    response = requests.post(
        'http://localhost:8000/search',
        json={'query': query, 'n_results': n_results}
    )
    return response.json()
```

### cURL for testing
```bash
# Search
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "budget", "n_results": 3}'

# Upload
curl -X POST "http://localhost:8000/upload" \
  -F "files=@document.pdf"
```

This API provides a clean, RESTful interface to your ChromaDB document system, making it easy to integrate with web applications, mobile apps, or other services. 