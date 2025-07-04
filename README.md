# House Finance Document RAG System

A document search and question-answering system built with ChromaDB and Google AI embeddings. Upload financial documents and ask questions about them using natural language.

## 🚀 Production Deployment (Recommended)

**For production servers - no code download needed!**

### Prerequisites
- Docker installed on your system
- Google API key (for embeddings)

### 1. Create Environment File
Create a `.env` file with your configuration:
```bash
GOOGLE_API_KEY=your_google_api_key_here
CHROMA_DB_PATH=./chroma_db/data
DOCUMENTS_PATH=./output
```

### 2. Deploy with Docker
```bash
# Pull and run the pre-built image
docker pull tabalbar/house-of-finance:v1.0.0
docker run -d -p 8000:8000 --env-file .env --name house-finance tabalbar/house-of-finance:v1.0.0
docker run -d -p 8000:8000 --env-file .env --name house-finance tabalbar/house-of-finance:latest
```

### 3. Verify Deployment
```bash
# Check if the service is running
curl http://localhost:8000/

# Check database status
curl http://localhost:8000/stats
```

**That's it! 🎉** Your API is running at `http://localhost:8000`

---

## 🛠️ Development Setup

**For developers who want to modify the code**

### Prerequisites
- Python 3.11+
- Git
- Google API key

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd house-finance
```

### 2. Install Dependencies
```bash
pip install -r src/requirements.txt
```

### 3. Configure Environment
```bash
cp src/.env.example .env
# Edit .env with your Google API key
```

### 4. Run Locally
```bash
python src/run_api.py
```

### 5. Test the System
```bash
python src/tests/api_client_example.py
```

---

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
house-finance/
├── src/
│   ├── api.py                    # Main FastAPI application
│   ├── run_api.py               # Server startup script
│   ├── settings.py              # Configuration
│   ├── documents/               # Document processing
│   │   ├── document_processor.py
│   │   ├── embeddings.py
│   │   └── ingest_documents.py
│   ├── chroma_db/              # Database setup
│   └── tests/                  # Testing utilities
├── output/                     # Place your documents here
├── chroma_db/                  # Database storage (created automatically)
└── README.md                   # This file
```

## 🔧 Development Commands

### Ingest Documents
```bash
python src/documents/ingest_documents.py --source output/
```

### Build Docker Image
```bash
cd src
docker build -t house-finance .
```

## 💡 Example Usage

1. **Start the server** (production or development)
2. **Upload a financial document** via the web interface at http://localhost:8000/docs
3. **Ask questions** like:
   - "What is the total budget allocation?"
   - "How much funding goes to education?"
   - "Show me all departments with budgets over $1 million"

## 🆘 Troubleshooting

**Server won't start?**
- Check that port 8000 is available: `lsof -i :8000`
- Verify your Google API key is valid
- For Docker: Check logs with `docker logs house-finance`

**No search results?**
- Make sure you've uploaded documents first
- Check if documents were processed: `curl http://localhost:8000/stats`
- Verify the database has content (should show document_count > 0)

**Docker issues?**
- Ensure Docker is running: `docker info`
- Check if image exists: `docker images | grep house-finance`
- Restart container: `docker restart house-finance`

**Need help?**
- Check the full API documentation at http://localhost:8000/docs
- Run the test client: `python src/tests/api_client_example.py`

## 🔄 Updates

**Production:** Pull the latest image and restart
```bash
docker pull tabalbar/house-of-finance:latest
docker stop house-finance && docker rm house-finance
docker run -d -p 8000:8000 --env-file .env --name house-finance tabalbar/house-of-finance:latest
```

**Development:** Pull latest code and restart
```bash
git pull origin main
python src/run_api.py
```

## 📄 License

[Your License Here] 