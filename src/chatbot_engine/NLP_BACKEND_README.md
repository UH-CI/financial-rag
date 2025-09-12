# Advanced NLP Backend for Financial RAG System

A sophisticated 6-step pipeline that uses LLM-guided decision making for intelligent document retrieval and response generation.

## Architecture Overview

The NLP backend implements a multi-step pipeline where each step is guided by LLM decisions:

```
User Query → Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6 → Response
            Decision  Query    Retrieval Document  Rerank   Answer
            Making    Generation          Selection         Generation
```

## Step-by-Step Process

### Step 1: Document Retrieval Decision
**LLM decides:**
- Number of documents to retrieve (1-10)
- Whether to retrieve full documents or chunks
- Query classification: "new_document" vs "follow_up"

**Follow-up queries skip retrieval steps and use existing context.**

### Step 2: Query Generation  
**LLM generates:**
- 3-5 search terms/keywords/phrases
- Selects retrieval method from 4 options:
  - `keyword_matching`: Basic text matching
  - `dense_encoder`: Semantic similarity (Gemini embeddings)
  - `sparse_encoder`: BM25 statistical matching
  - `multi_hop_reasoning`: Knowledge graph traversal

### Step 3: Retrieval Execution
**Four retrieval methods implemented:**

1. **Keyword Matching**: Simple text search with keyword frequency scoring
2. **Dense Encoder**: Uses Gemini embeddings with cosine similarity
3. **Sparse Encoder**: BM25-style statistical matching
4. **Multi-hop Reasoning**: Uses existing KG2RAG system for graph traversal

### Step 4: Document Selection
Based on Step 1 decision:
- **Full documents**: Retrieves complete documents for comprehensive analysis
- **Chunks**: Uses retrieved text chunks for targeted information

### Step 5: Reranking
**LLM reranks chunks** based on relevance to user query for better precision.
(Skipped for full documents)

### Step 6: Answer Generation
**LLM generates final answer** using:
- Retrieved context
- Conversation history
- Global state tracking

## Global State Management

The system maintains conversation state including:
- **Current documents**: Tracks documents in conversation context
- **Decision history**: Records all LLM decisions made
- **Context history**: Maintains conversation flow
- **Last methods used**: Remembers retrieval patterns

## Key Features

### 🤖 LLM-Guided Intelligence
- Every major decision is made by the LLM based on query analysis
- Adaptive retrieval strategies based on query complexity
- Context-aware follow-up handling

### 🔄 Conversation Continuity
- Maintains state across multiple queries
- Distinguishes between new requests and follow-ups
- Builds context progressively

### 📊 Multiple Retrieval Methods
- Four different retrieval strategies
- Automatic method selection based on query type
- Fallback mechanisms for robustness

### 🎯 Intelligent Reranking
- LLM-based relevance scoring
- Query-specific chunk prioritization
- Improved precision for final results

## Usage Examples

### Basic Usage
```python
from nlp_backend import NLPBackend

# Initialize with your collection managers and config
nlp_backend = NLPBackend(collection_managers, config)

# Process a query
result = nlp_backend.process_query(
    "How much funding does House Bill 1234 provide?",
    conversation_id="user_session_123"
)

print(result['answer'])
print(f"Used {result['context_used']} sources")
```

### Conversation Flow
```python
# First query - new document retrieval
result1 = nlp_backend.process_query(
    "What are the education budget allocations?", 
    "conversation_1"
)

# Follow-up query - uses existing context
result2 = nlp_backend.process_query(
    "Which specific programs are included?",
    "conversation_1"  # Same conversation ID
)
```

### State Management
```python
# Check conversation state
state = nlp_backend.get_conversation_state("conversation_1")
print(f"Documents: {len(state['current_documents'])}")
print(f"Decisions: {state['decision_count']}")

# Reset conversation
nlp_backend.reset_conversation("conversation_1")
```

## Integration with Existing System

### Option 1: Replace Existing Query Processor
```python
# Replace your current query processor
from nlp_backend import NLPBackend
processor = NLPBackend(collection_managers, config)
```

### Option 2: Hybrid Approach
```python
from nlp_backend_integration import IntegratedNLPSystem

# Use both systems with intelligent switching
integrated = IntegratedNLPSystem(collection_managers, config)
result = integrated.process_query(query, use_advanced_pipeline=True)
```

## Configuration

The system uses your existing `config.json` with these key settings:

```json
{
  "collections": ["bills"],
  "system": {
    "llm_model": "gemini-1.5-flash",
    "embedding_model": "text-embedding-004",
    "chroma_db_path": "./chroma_db/data"
  }
}
```

## Response Format

```python
{
    "answer": "Generated response text",
    "sources": [
        {
            "content": "Source text...",
            "metadata": {...},
            "rank": 1
        }
    ],
    "context_used": 3,
    "conversation_id": "session_123",
    "processing_time": 2.45,
    "pipeline_steps": {
        "step1_decision": {
            "query_type": "new_document",
            "num_documents": 3,
            "retrieve_full_document": false
        },
        "step2_query_generation": {
            "search_terms": ["education", "budget", "allocation"],
            "retrieval_method": "dense_encoder"
        },
        "step3_retrieval_method": "dense_encoder",
        "step4_content_selected": 3,
        "step5_reranked": 3
    }
}
```

## Testing

### Run Basic Tests
```bash
cd src
python test_nlp_backend.py
```

### Run Integration Demo
```bash
cd src  
python nlp_backend_integration.py
```

### Test Scenarios Included
- Simple factual queries
- Complex analysis requests
- Follow-up questions
- Multi-document research
- Specific bill lookups
- Conceptual queries

## Dependencies

```python
google-generativeai>=0.3.0
sentence-transformers>=2.2.0
scikit-learn>=1.3.0
networkx>=3.0
numpy>=1.24.0
```

## Environment Setup

```bash
export GEMINI_API_KEY="your_gemini_api_key"
```

## Performance Characteristics

- **Average processing time**: 2-5 seconds per query
- **Memory usage**: Moderate (embeddings cached)
- **Scalability**: Handles 10-100 concurrent conversations
- **Accuracy**: Improved precision through multi-step reasoning

## Advanced Features

### Custom Retrieval Methods
Extend the system by implementing new retrieval methods:

```python
def _custom_retrieval_method(self, search_terms: List[str], num_docs: int) -> RetrievalResult:
    # Your custom retrieval logic
    pass
```

### State Persistence
The system maintains in-memory state. For persistence across restarts:

```python
# Save state
state_data = nlp_backend.get_conversation_state(conversation_id)
# Store state_data to database/file

# Restore state
# Load state_data and reinitialize conversation
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
2. **API Key Issues**: Verify GEMINI_API_KEY is set correctly
3. **Memory Issues**: Reduce batch sizes or chunk sizes
4. **Slow Performance**: Check network connectivity to Gemini API

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

- [ ] Persistent state storage
- [ ] Custom embedding models
- [ ] Advanced graph reasoning
- [ ] Multi-language support
- [ ] Streaming responses
- [ ] Caching optimizations

## Contributing

The system is modular and extensible. Key extension points:
- New retrieval methods in Step 3
- Custom reranking algorithms in Step 5
- Enhanced state management
- Additional LLM providers
