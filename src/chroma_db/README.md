# ChromaDB Embedded Storage

This directory contains the embedded ChromaDB database for the Financial Document RAG System.

## Overview

ChromaDB runs in **embedded mode only**, storing data locally in the `data/` directory. This provides:

- **Simplicity**: No separate server process needed
- **Performance**: Direct database access without HTTP overhead  
- **Reliability**: No network dependencies or connection issues
- **Data Persistence**: All data stored locally in SQLite

## Directory Structure

```
chroma_db/
├── data/                     # ChromaDB persistent storage
│   ├── chroma.sqlite3       # Main database file
│   └── [collection-id]/     # Collection-specific data
└── README.md               # This file
```

## Configuration

The system is configured via `settings.py`:

```python
# ChromaDB Configuration
chroma_db_path: Path = Field(default=Path("./chroma_db/data"))
chroma_collection_name: str = Field(default="financial_documents")
chroma_distance_function: str = Field(default="cosine")
```

## Usage

ChromaDB is automatically initialized when you:

1. **Run the API**: `python run_api.py`
2. **Use the embeddings module**: Import from `documents.embeddings`

## Database Management

### Backup Data
```bash
cp -r chroma_db/data/ backup_$(date +%Y%m%d)/
```

## Data Storage

- **Database**: SQLite file at `data/chroma.sqlite3`
- **Embeddings**: Stored as vectors in the database
- **Metadata**: Document metadata and chunk information
- **Collections**: Organized by document type (financial_documents)

## Performance

Embedded mode provides:
- **Fast queries**: No HTTP latency
- **Efficient storage**: Local SQLite database
- **Low memory**: Only loads what's needed
- **Concurrent access**: Multiple threads can access safely

## Troubleshooting

### Database Locked
If you get "database is locked" errors:
```bash
# Stop any running processes
pkill -f "python.*api"
# Then restart your application
```

### Permissions Issues
```bash
chmod -R 755 chroma_db/data/
```

### Disk Space
Monitor the `data/` directory size:
```bash
du -sh chroma_db/data/
```

## Migration Notes

This system previously supported server mode but has been simplified to embedded-only for:
- Reduced complexity
- Better reliability  
- Easier deployment
- Lower resource usage

All data from previous server setups has been preserved in the embedded database.