# RAG System Template using ChromaDB

A document search and question-answering system built with ChromaDB and Google AI embeddings. Upload documents and ask questions about them using natural language.

This project uses financial PDFs as an example use case, but the system is designed to be adaptable to any document domain. The RAG pipeline can process various document types, with financial documents serving as the demonstration scenario.

While the example implementation shows how to handle financial documents (budgets, statements, etc.), users can adapt the document processing functions in the `/documents` directory to suit their specific domain needs. Different document types may require specialized pre-processing steps to optimize text extraction and chunking for the best search and question-answering results.

## 🚀 Quick Start

### Prerequisites
- Docker installed on your system
- Google API key (for embeddings)

### 1. Clone and Setup
```bash
git clone https://github.com/Tabalbar/RAG-template.git
cd RAG-template
```

### 2. Configure Environment
Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
# Edit .env and add your Google API key
```

Required environment variables:
```bash
GOOGLE_API_KEY=your_google_api_key_here
CHROMA_DB_PATH=./chroma_db/data
DOCUMENTS_PATH=./output
```

### 3. Start the Server

**Option A: Using Docker (Recommended)**
```bash
docker pull tabalbar/house-of-finance:latest
docker run -d -p 8000:8000 --env-file .env tabalbar/house-of-finance:latest
```

**Option B: Local Python**
```bash
pip install -r requirements.txt
python run_api.py
```

### 4. Test the System
```bash
# Run the test client to verify everything works
python tests/api_client_example.py
```

The server will be available at `http://localhost:8000`

## 📖 Using the API

### Web Interface
- **API Documentation**: http://localhost:8000/docs
- **Interactive Testing**: http://localhost:8000/redoc

### Upload Documents
```bash
curl -X POST "http://localhost:8000/upload" -F "files=@your-document.pdf"
```

### Search Documents
```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "budget allocation for education", "n_results": 3}'
```

### Get Statistics
```bash
curl http://localhost:8000/stats
```

## 📁 Project Structure

```
RAG-template/
├── api.py                    # Main FastAPI application
├── run_api.py               # Server startup script
├── settings.py              # Configuration
├── requirements.txt         # Python dependencies
├── Dockerfile              # Docker container definition
├── .dockerignore           # Docker build exclusions
├── .env.example            # Environment variables template
├── documents/              # Document processing modules
│   ├── document_processor.py
│   ├── embeddings.py
│   ├── gemini_text_cleaner.py
│   └── ingest_documents.py
├── chroma_db/              # Database setup and management
│   └── README.md
├── tests/                  # Testing utilities
│   └── api_client_example.py
├── output/                 # Place your documents here (created at runtime)
├── chroma_db/data/         # Database storage (created at runtime)
└── README.md               # This file
```

## 🔧 Development

### Ingest Documents
```bash
python documents/ingest_documents.py --source output/
```

### Run Tests
```bash
python -m pytest tests/
```

## 💡 Example Usage

1. **Start the server**: `python run_api.py`
2. **Upload a document** via the web interface at http://localhost:8000/docs
3. **Ask questions** like:
   - "What is the total budget allocation?"
   - "How much funding goes to education?"
   - "Show me all departments with budgets over $1 million"

## 🆘 Troubleshooting

**Server won't start?**
- Check that port 8000 is available
- Verify your Google API key is valid in `.env`
- Check logs: `docker logs <container-id>`

**No search results?**
- Make sure you've uploaded documents first
- Check if documents were processed: `curl http://localhost:8000/stats`

**Need help?**
- Check the full API documentation at http://localhost:8000/docs
- Run the test client: `python tests/api_client_example.py`

## 🔧 Configuration

The system uses environment variables for configuration. Copy `.env.example` to `.env` and configure:

- `GOOGLE_API_KEY`: Required for embeddings and LLM
- `CHROMA_DB_PATH`: Database storage location
- `DOCUMENTS_PATH`: Document upload directory
- `EMBEDDING_MODEL`: Default is `text-embedding-004`
- `LLM_MODEL`: Default is `gemini-1.5-flash`

## 📄 License

MIT License - Feel free to use this template for your own RAG applications! 