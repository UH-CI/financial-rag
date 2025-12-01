# API Migration Plan V2 - Structured Format

## Overview

This plan outlines the migration from the monolithic `api.py` (3160 lines) to a clean, modular structure while preserving the complex fiscal notes citation system that dynamically creates detailed citations like `[1.2]`, `[1.20]`.

## Current Working System Analysis

### ✅ **What's Working**
- **Backend**: Original `api.py` with structured citation processing
- **Frontend**: Dynamic citation creation in `FiscalNoteContent.tsx`
- **Data Flow**: `chunk_text_map` with `chunk_id` → detailed citations
- **API Response**: Correct data structures for frontend consumption

### 🎯 **Migration Goals**
1. **Zero Functionality Loss**: All citations must work identically
2. **Clean Architecture**: Modular, maintainable, testable code
3. **Type Safety**: Full TypeScript-style type hints
4. **Performance**: No regression in response times
5. **Maintainability**: Clear separation of concerns

## Proposed Architecture

### Directory Structure
```
src/api/
├── __init__.py                     # App factory and configuration
├── main.py                         # Application entry point
├── core/
│   ├── __init__.py
│   ├── citations/
│   │   ├── __init__.py
│   │   ├── structured_processor.py # process_fiscal_note_references_structured()
│   │   ├── simple_processor.py     # process_fiscal_note_references()
│   │   └── helpers.py              # Citation helper functions
│   ├── models/
│   │   ├── __init__.py
│   │   ├── fiscal_notes.py         # Pydantic models for fiscal notes
│   │   ├── documents.py            # Document-related models
│   │   └── responses.py            # API response models
│   └── exceptions.py               # Custom exception classes
├── services/
│   ├── __init__.py
│   ├── fiscal_notes/
│   │   ├── __init__.py
│   │   ├── generator.py            # Fiscal note generation logic
│   │   ├── processor.py            # Data processing and metadata loading
│   │   └── validator.py            # Data validation
│   ├── documents/
│   │   ├── __init__.py
│   │   ├── manager.py              # Document management
│   │   └── classifier.py           # Document type classification
│   ├── collections/
│   │   ├── __init__.py
│   │   └── manager.py              # Collection management
│   ├── search/
│   │   ├── __init__.py
│   │   ├── query_processor.py      # Query processing
│   │   └── nlp_backend.py          # NLP backend integration
│   ├── jobs/
│   │   ├── __init__.py
│   │   └── manager.py              # Background job management
│   └── websocket/
│       ├── __init__.py
│       └── manager.py              # WebSocket connection management
├── routes/
│   ├── __init__.py
│   ├── fiscal_notes.py             # Fiscal note endpoints
│   ├── documents.py                # Document endpoints
│   ├── collections.py              # Collection endpoints
│   ├── search.py                   # Search endpoints
│   ├── chat.py                     # Chat endpoints
│   ├── bill_similarity.py          # Bill similarity endpoints
│   ├── property_prompts.py         # Property prompt endpoints
│   ├── health.py                   # Health check endpoints
│   └── websockets.py               # WebSocket endpoints
├── config/
│   ├── __init__.py
│   ├── settings.py                 # Application settings
│   ├── database.py                 # Database configuration
│   └── dependencies.py             # Dependency injection
└── utils/
    ├── __init__.py
    ├── logging.py                  # Logging configuration
    ├── slack.py                    # Slack notifications
    └── helpers.py                  # General utility functions
```

## Migration Strategy

### Phase 1: Foundation Setup

#### 1.1 Create Base Structure
```python
# api/__init__.py
from fastapi import FastAPI
from .config.settings import get_settings
from .config.dependencies import setup_dependencies
from .routes import register_routes

def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    settings = get_settings()
    app = FastAPI(
        title="Document RAG API",
        version="2.0.0",
        description="Modular Document RAG API with fiscal notes citation system"
    )
    
    # Setup dependencies
    setup_dependencies(app)
    
    # Register routes
    register_routes(app)
    
    return app
```

#### 1.2 Configuration Management
```python
# api/config/settings.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Redis configuration
    redis_url: str = "redis://localhost:6379"
    use_redis: bool = True
    
    # API configuration
    host: str = "0.0.0.0"
    port: int = 8200
    debug: bool = False
    
    # Fiscal notes configuration
    fiscal_notes_dir: str = "./fiscal_notes/generation"
    
    # Model configuration
    gemini_api_key: Optional[str] = None
    
    class Config:
        env_file = ".env"

def get_settings() -> Settings:
    return Settings()
```

### Phase 2: Core Citation System Migration

#### 2.1 Extract Structured Citation Processor (CRITICAL)
```python
# api/core/citations/structured_processor.py
"""
Structured citation processor that creates detailed citations like [1.2], [1.20]
CRITICAL: This must be copied EXACTLY from the original api.py
"""
from typing import Dict, Any, List, Optional

def process_fiscal_note_references_structured(
    fiscal_note_data: Dict[str, Any], 
    document_mapping: Dict[str, int],
    numbers_data: Optional[List] = None, 
    chunks_data: Optional[List] = None, 
    sentence_attributions: Optional[List] = None, 
    global_amount_to_citation: Optional[Dict] = None, 
    global_next_citation_number: Optional[int] = None, 
    fiscal_note_documents: Optional[List] = None
) -> Dict[str, Any]:
    """
    Process fiscal note data to create detailed citations with chunk-level granularity.
    
    CRITICAL: This function must be copied EXACTLY from the original api.py
    Any changes will break the citation system.
    
    Returns:
        Processed fiscal note data with special metadata keys:
        - _number_citation_map: Financial citation mapping
        - _chunk_text_map: Chunk text mapping for detailed citations
        - _updated_next_citation_number: Updated global citation counter
    """
    # COPY EXACT IMPLEMENTATION FROM ORIGINAL api.py lines 1444-1925
    pass
```

#### 2.2 Extract Simple Citation Processor
```python
# api/core/citations/simple_processor.py
"""
Simple citation processor for basic [1] citations
"""
from typing import Dict, Any

def process_fiscal_note_references(
    fiscal_note_data: Dict[str, Any], 
    document_mapping: Dict[str, int]
) -> Dict[str, Any]:
    """
    Process fiscal note data to create simple citations like [1]
    
    COPY EXACT IMPLEMENTATION FROM ORIGINAL api.py
    """
    pass
```

#### 2.3 Citation Helper Functions
```python
# api/core/citations/helpers.py
"""
Helper functions for citation processing
"""

def classify_document_type(document_name: str) -> str:
    """COPY FROM ORIGINAL"""
    pass

def get_document_type_description(doc_type: str) -> str:
    """COPY FROM ORIGINAL"""
    pass

def get_document_type_icon(doc_type: str) -> str:
    """COPY FROM ORIGINAL"""
    pass

# Copy all other citation helper functions EXACTLY
```

### Phase 3: Service Layer Migration

#### 3.1 Fiscal Notes Service
```python
# api/services/fiscal_notes/processor.py
"""
Fiscal note data processing and metadata loading
"""
from typing import Dict, Any, List, Tuple
from ...core.citations.structured_processor import process_fiscal_note_references_structured
from ...core.citations.simple_processor import process_fiscal_note_references

class FiscalNoteProcessor:
    """Handles fiscal note data processing and citation generation"""
    
    def __init__(self, fiscal_notes_dir: str):
        self.fiscal_notes_dir = fiscal_notes_dir
    
    def process_fiscal_note_data(
        self,
        fiscal_note_data: Dict[str, Any],
        document_mapping: Dict[str, int],
        use_structured_processing: bool = True,
        **kwargs
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        Process fiscal note data and return processed data with metadata
        
        Returns:
            Tuple of (processed_data, number_citation_map, chunk_text_map)
        """
        if use_structured_processing:
            processed_data = process_fiscal_note_references_structured(
                fiscal_note_data, document_mapping, **kwargs
            )
            
            # Extract metadata (CRITICAL: exact extraction logic)
            number_citation_map = processed_data.pop('_number_citation_map', {})
            chunk_text_map = processed_data.pop('_chunk_text_map', {})
            
            return processed_data, number_citation_map, chunk_text_map
        else:
            processed_data = process_fiscal_note_references(
                fiscal_note_data, document_mapping
            )
            return processed_data, {}, {}
    
    def load_metadata(self, fiscal_notes_path: str, filename: str) -> Dict[str, Any]:
        """Load metadata file for a fiscal note"""
        # COPY EXACT METADATA LOADING LOGIC FROM ORIGINAL
        pass
```

### Phase 4: Route Migration

#### 4.1 Fiscal Notes Routes
```python
# api/routes/fiscal_notes.py
"""
Fiscal notes API endpoints
CRITICAL: Must return identical responses to original
"""
from fastapi import APIRouter, Request, HTTPException
from ..services.fiscal_notes.processor import FiscalNoteProcessor
from ..config.dependencies import get_fiscal_note_processor

router = APIRouter(prefix="/fiscal-notes", tags=["fiscal-notes"])

@router.post("/get_fiscal_note_data")
async def get_fiscal_note_data(
    bill_type: str,
    bill_number: str,
    year: str = "2025",
    processor: FiscalNoteProcessor = Depends(get_fiscal_note_processor)
):
    """
    Get fiscal note data with detailed citations
    CRITICAL: Must return exact same structure as original
    """
    # COPY EXACT LOGIC FROM ORIGINAL /get_fiscal_note_data endpoint
    # Ensure chunk_text_map and number_citation_map are included
    pass

@router.post("/get_fiscal_note")
async def get_fiscal_note(
    request: Request,
    bill_type: str,
    bill_number: str,
    year: str = "2025"
):
    """
    Get fiscal note HTML template response
    COPY EXACT LOGIC FROM ORIGINAL
    """
    pass
```

### Phase 5: Dependency Injection

#### 5.1 Dependencies Configuration
```python
# api/config/dependencies.py
"""
Dependency injection setup
"""
from fastapi import FastAPI, Depends
from .settings import get_settings, Settings
from ..services.fiscal_notes.processor import FiscalNoteProcessor

# Global instances (maintain original global state)
_fiscal_note_processor: Optional[FiscalNoteProcessor] = None

def setup_dependencies(app: FastAPI):
    """Setup all application dependencies"""
    global _fiscal_note_processor
    
    settings = get_settings()
    
    # Initialize fiscal note processor
    _fiscal_note_processor = FiscalNoteProcessor(settings.fiscal_notes_dir)
    
    # Setup other dependencies (Redis, ChromaDB, etc.)
    # COPY EXACT INITIALIZATION LOGIC FROM ORIGINAL

def get_fiscal_note_processor() -> FiscalNoteProcessor:
    """Get fiscal note processor instance"""
    if _fiscal_note_processor is None:
        raise RuntimeError("Fiscal note processor not initialized")
    return _fiscal_note_processor
```

## Testing Strategy

### Critical Test Cases

#### 1. Citation Format Verification
```python
# tests/test_citations.py
import pytest
from api.core.citations.structured_processor import process_fiscal_note_references_structured

def test_detailed_citations():
    """Test that detailed citations [1.2] are created correctly"""
    # Test with sample data that has chunk_id
    result = process_fiscal_note_references_structured(...)
    
    # Verify chunk_text_map contains chunk_id
    chunk_map = result.get('_chunk_text_map', {})
    assert '1' in chunk_map
    assert chunk_map['1'][0]['chunk_id'] == 2
    
def test_frontend_data_structure():
    """Test that API returns data in format expected by frontend"""
    response = client.post("/get_fiscal_note_data?bill_type=HB&bill_number=1169&year=2025")
    data = response.json()
    
    # Verify structure matches frontend expectations
    assert 'chunk_text_map' in data
    assert 'number_citation_map' in data
    assert 'fiscal_notes' in data
```

#### 2. End-to-End Integration Tests
```python
def test_fiscal_note_citations_integration():
    """Test complete flow from API to frontend citation rendering"""
    # 1. Call API endpoint
    response = client.post("/get_fiscal_note_data?bill_type=HB&bill_number=1169&year=2025")
    
    # 2. Verify response structure
    data = response.json()
    chunk_map = data['chunk_text_map']
    
    # 3. Simulate frontend citation processing
    citation_number = 1
    chunk_info = chunk_map['1'][0]
    display_number = f"{citation_number}.{chunk_info['chunk_id']}"
    
    # 4. Verify detailed citation format
    assert display_number == "1.2"  # Should create [1.2]
```

## Migration Execution Plan

### Week 1: Foundation
- [ ] Create base directory structure
- [ ] Setup configuration management
- [ ] Create Pydantic models
- [ ] Setup testing framework

### Week 2: Core Citation System
- [ ] Extract structured citation processor (CRITICAL)
- [ ] Extract simple citation processor
- [ ] Extract all helper functions
- [ ] Test citation processing in isolation

### Week 3: Service Layer
- [ ] Create fiscal note processor service
- [ ] Migrate metadata loading logic
- [ ] Create other service classes
- [ ] Test service layer integration

### Week 4: Routes and Integration
- [ ] Migrate fiscal note routes
- [ ] Migrate other route modules
- [ ] Setup dependency injection
- [ ] End-to-end integration testing

### Week 5: Validation and Deployment
- [ ] Comprehensive testing
- [ ] Performance validation
- [ ] Documentation updates
- [ ] Production deployment

## Risk Mitigation

### High-Risk Components
1. **Citation Processing**: Most complex, highest risk of breaking
2. **Metadata Extraction**: Easy to break the special key extraction
3. **Global State**: Citation counters and job management
4. **File Paths**: Metadata and chunk mapping file loading

### Mitigation Strategies
1. **Exact Copy Rule**: Never modify during initial extraction
2. **Incremental Testing**: Test each component as migrated
3. **Parallel Development**: Keep original running alongside new version
4. **Rollback Plan**: Ability to quickly revert to original
5. **Comprehensive Logging**: Track data flow through entire system

## Success Criteria

### Functional Requirements
- [ ] All API endpoints return identical responses
- [ ] Fiscal notes show detailed citations `[1.2]`, `[1.20]`
- [ ] Frontend receives correct data structures
- [ ] No performance regression
- [ ] All background jobs work correctly

### Code Quality Requirements
- [ ] Clean modular architecture
- [ ] Comprehensive type hints
- [ ] Full test coverage (>90%)
- [ ] Clear documentation
- [ ] Maintainable codebase

## Conclusion

This migration plan prioritizes **zero functionality loss** while achieving a clean, modular architecture. The critical success factor is preserving the exact citation processing logic that creates detailed citations for the frontend.

The plan emphasizes:
1. **Exact copying** of critical functions first
2. **Incremental testing** at each step
3. **Comprehensive validation** of citation functionality
4. **Clear rollback strategy** if issues arise

By following this plan, we can achieve a maintainable, modular codebase while preserving the complex fiscal notes citation system that users depend on.
