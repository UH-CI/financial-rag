"""
KG2RAG Input/Output Schemas
Defines the data structures for the KG2RAG system
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set
from enum import Enum
import json

@dataclass
class Document:
    """Input document for processing"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Chunk:
    """Text chunk with metadata"""
    id: str
    content: str
    document_id: str
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Triplet:
    """Knowledge graph triplet"""
    head: str
    relation: str
    tail: str
    chunk_id: str
    confidence: float = 1.0

@dataclass
class KnowledgeGraph:
    """Complete knowledge graph structure"""
    triplets: List[Triplet]
    entities: Set[str] = field(default_factory=set)
    relations: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        if not self.entities or not self.relations:
            for triplet in self.triplets:
                self.entities.add(triplet.head)
                self.entities.add(triplet.tail)
                self.relations.add(triplet.relation)

@dataclass
class SemanticScore:
    """Semantic similarity score for a chunk"""
    chunk_id: str
    score: float

@dataclass(frozen=True)
class GraphEdge:
    """Weighted undirected graph edge for organization"""
    head: str
    tail: str
    relation: str
    chunk_id: str
    weight: float

@dataclass
class ConnectedComponent:
    """Connected component in the graph"""
    entities: Set[str]
    edges: List[GraphEdge]
    mst_edges: List[GraphEdge] = field(default_factory=list)
    text_representation: str = ""
    triplet_representation: str = ""
    relevance_score: float = 0.0

@dataclass
class KG2RAGConfig:
    """Configuration parameters for KG2RAG"""
    # Chunking parameters
    chunk_size: int = 512 # Should test with 1024, 2048, 4096, 8192
    chunk_overlap: int = 50 # Should test with 100, 200, 400, 800
    
    # Semantic retrieval parameters
    semantic_top_k: int = 5 # Should test with 10, 20, 30, 40, 50
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Graph expansion parameters
    max_hops: int = 2 # Should test with 1, 2, 3, 4, 5
    
    # Context organization parameters
    max_context_chunks: int = 10 # Should test with 5, 10, 15, 20, 25
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # LLM parameters
    llm_model: str = "gemini-1.5-flash"
    max_tokens: int = 2000
    temperature: float = 0.1

@dataclass
class QueryInput:
    """Input for a KG2RAG query"""
    query: str
    config: KG2RAGConfig = field(default_factory=KG2RAGConfig)

@dataclass
class RetrievalResult:
    """Result from semantic retrieval step"""
    query: str
    retrieved_chunks: List[Chunk]
    semantic_scores: List[SemanticScore]
    expanded_chunks: List[Chunk] = field(default_factory=list)
    organized_components: List[ConnectedComponent] = field(default_factory=list)

@dataclass
class KG2RAGResponse:
    """Final response from KG2RAG system"""
    query: str
    answer: str
    retrieval_result: RetrievalResult
    context_used: str
    confidence: float
    processing_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)

class ProcessingStage(Enum):
    """Processing stages for the KG2RAG pipeline"""
    CHUNKING = "chunking"
    KG_BUILDING = "kg_building"
    SEMANTIC_RETRIEVAL = "semantic_retrieval"
    GRAPH_EXPANSION = "graph_expansion"
    CONTEXT_ORGANIZATION = "context_organization"
    ANSWER_GENERATION = "answer_generation"

@dataclass
class ProcessingStatus:
    """Status tracking for pipeline processing"""
    stage: ProcessingStage
    progress: float  # 0.0 to 1.0
    message: str
    error: Optional[str] = None

# Validation functions
def validate_documents(documents: List[Document]) -> bool:
    """Validate input documents"""
    if not documents:
        raise ValueError("Documents list cannot be empty")
    
    doc_ids = set()
    for doc in documents:
        if not doc.id or not doc.content:
            raise ValueError(f"Document {doc.id} must have id and content")
        if doc.id in doc_ids:
            raise ValueError(f"Duplicate document ID: {doc.id}")
        doc_ids.add(doc.id)
    
    return True

def validate_config(config: KG2RAGConfig) -> bool:
    """Validate configuration parameters"""
    if config.chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if config.semantic_top_k <= 0:
        raise ValueError("semantic_top_k must be positive")
    if config.max_hops < 1:
        raise ValueError("max_hops must be at least 1")
    if config.max_context_chunks <= 0:
        raise ValueError("max_context_chunks must be positive")
    if not (0 <= config.temperature <= 2):
        raise ValueError("temperature must be between 0 and 2")
    
    return True

def validate_query_input(query_input: QueryInput) -> bool:
    """Validate query input"""
    if not query_input.query.strip():
        raise ValueError("Query cannot be empty")
    
    validate_config(query_input.config)
    return True

# Example test data
def create_test_documents() -> List[Document]:
    """Create test documents for validation"""
    return [
        Document(
            id="doc1",
            content="Big Stone Gap is a 2014 American drama film written and directed by Adriana Trigiani, based on her 2000 novel of the same name. The film stars Ashley Judd, Patrick Wilson, Whoopi Goldberg, and Jane Krakowski.",
            metadata={"source": "wikipedia", "year": 2014}
        ),
        Document(
            id="doc2", 
            content="Adriana Trigiani is an American novelist, television writer, film director, and playwright. She is based in Greenwich Village, New York City, and has written several bestselling novels.",
            metadata={"source": "biography", "location": "NYC"}
        ),
        Document(
            id="doc3",
            content="Greenwich Village is a neighborhood in the western part of Lower Manhattan in New York City. It has been known as an artists' quarter and bohemian capital for decades.",
            metadata={"source": "travel_guide", "borough": "Manhattan"}
        )
    ]

def create_test_query() -> QueryInput:
    """Create test query input"""
    return QueryInput(
        query="In which part of NYC is the director of Big Stone Gap based?",
        config=KG2RAGConfig(
            chunk_size=256,
            semantic_top_k=3,
            max_hops=2,
            max_context_chunks=5
        )
    )

if __name__ == "__main__":
    # Test schema validation
    test_docs = create_test_documents()
    test_query = create_test_query()
    
    print("Testing document validation...")
    assert validate_documents(test_docs)
    print("✓ Documents valid")
    
    print("Testing query validation...")
    assert validate_query_input(test_query)
    print("✓ Query valid")
    
    print("Testing serialization...")
    query_json = json.dumps(test_query, default=lambda x: x.__dict__, indent=2)
    print("✓ Serialization works")
    
    print("\nAll schema tests passed!")
