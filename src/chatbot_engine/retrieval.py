"""
KG2RAG Online Retrieval and Graph Expansion
Handles semantic retrieval and knowledge graph-guided expansion
"""

import numpy as np
import logging
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict, deque
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import networkx as nx

try:
    from .schemas import (
        Chunk, KnowledgeGraph, Triplet, SemanticScore, 
        GraphEdge, KG2RAGConfig, RetrievalResult
    )
except ImportError:
    from schemas import (
        Chunk, KnowledgeGraph, Triplet, SemanticScore, 
        GraphEdge, KG2RAGConfig, RetrievalResult
    )

logger = logging.getLogger(__name__)

class SemanticRetriever:
    """Handles semantic similarity-based retrieval"""
    
    def __init__(self, config: KG2RAGConfig):
        self.config = config
        self.model = SentenceTransformer(config.embedding_model)
        self.chunk_embeddings = None
        self.chunks = None
    
    def index_chunks(self, chunks: List[Chunk]) -> None:
        """Create embeddings for all chunks"""
        logger.info(f"Creating embeddings for {len(chunks)} chunks...")
        
        self.chunks = chunks
        chunk_texts = [chunk.content for chunk in chunks]
        self.chunk_embeddings = self.model.encode(chunk_texts, show_progress_bar=True)
        
        logger.info("Chunk indexing complete")
    
    def retrieve_semantic(self, query: str) -> List[SemanticScore]:
        """Retrieve chunks based on semantic similarity"""
        if self.chunk_embeddings is None:
            raise ValueError("Chunks not indexed. Call index_chunks() first.")
        
        # Encode query
        query_embedding = self.model.encode([query])
        
        # Compute similarities
        similarities = cosine_similarity(query_embedding, self.chunk_embeddings)[0]
        
        # Create semantic scores
        scores = []
        for i, similarity in enumerate(similarities):
            score = SemanticScore(
                chunk_id=self.chunks[i].id,
                score=float(similarity)
            )
            scores.append(score)
        
        # Sort by similarity and return top-k
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores[:self.config.semantic_top_k]

class GraphExpander:
    """Handles knowledge graph-guided expansion"""
    
    def __init__(self, config: KG2RAGConfig):
        self.config = config
        self.kg = None
        self.chunk_to_triplets = defaultdict(list)
        self.entity_to_triplets = defaultdict(list)
    
    def index_knowledge_graph(self, kg: KnowledgeGraph) -> None:
        """Index knowledge graph for efficient traversal"""
        logger.info(f"Indexing knowledge graph with {len(kg.triplets)} triplets...")
        
        self.kg = kg
        
        # Build indexes
        for triplet in kg.triplets:
            self.chunk_to_triplets[triplet.chunk_id].append(triplet)
            self.entity_to_triplets[triplet.head].append(triplet)
            self.entity_to_triplets[triplet.tail].append(triplet)
        
        logger.info("Knowledge graph indexing complete")
    
    def expand_with_graph(self, seed_chunks: List[Chunk], 
                         semantic_scores: List[SemanticScore]) -> Tuple[List[Chunk], Set[Triplet]]:
        """Expand seed chunks using knowledge graph traversal"""
        if self.kg is None:
            raise ValueError("Knowledge graph not indexed. Call index_knowledge_graph() first.")
        
        # Get initial subgraph from seed chunks
        seed_chunk_ids = {chunk.id for chunk in seed_chunks}
        initial_triplets = set()
        
        for chunk_id in seed_chunk_ids:
            initial_triplets.update(self.chunk_to_triplets[chunk_id])
        
        # Extract entities from initial triplets
        seed_entities = set()
        for triplet in initial_triplets:
            seed_entities.add(triplet.head)
            seed_entities.add(triplet.tail)
        
        # Perform m-hop expansion
        expanded_triplets = self._traverse_graph(seed_entities, self.config.max_hops)
        
        # Get all chunks referenced by expanded triplets
        expanded_chunk_ids = {triplet.chunk_id for triplet in expanded_triplets}
        
        # Create chunk lookup
        chunk_lookup = {chunk.id: chunk for chunk in seed_chunks}
        # Add any missing chunks (this would require access to all chunks)
        # For now, we'll work with what we have
        
        expanded_chunks = [chunk_lookup[chunk_id] for chunk_id in expanded_chunk_ids 
                          if chunk_id in chunk_lookup]
        
        logger.info(f"Expanded from {len(seed_chunks)} to {len(expanded_chunks)} chunks "
                   f"using {len(expanded_triplets)} triplets")
        
        return expanded_chunks, expanded_triplets
    
    def _traverse_graph(self, seed_entities: Set[str], max_hops: int) -> Set[Triplet]:
        """Traverse knowledge graph using BFS for m hops"""
        visited_entities = set()
        current_entities = seed_entities.copy()
        all_triplets = set()
        
        for hop in range(max_hops):
            next_entities = set()
            
            for entity in current_entities:
                if entity in visited_entities:
                    continue
                
                visited_entities.add(entity)
                
                # Get all triplets involving this entity
                entity_triplets = self.entity_to_triplets[entity]
                all_triplets.update(entity_triplets)
                
                # Add connected entities for next hop
                for triplet in entity_triplets:
                    if triplet.head not in visited_entities:
                        next_entities.add(triplet.head)
                    if triplet.tail not in visited_entities:
                        next_entities.add(triplet.tail)
            
            current_entities = next_entities
            
            if not current_entities:  # No more entities to explore
                break
        
        return all_triplets

class OnlineRetriever:
    """Main class for online retrieval pipeline"""
    
    def __init__(self, config: KG2RAGConfig):
        self.config = config
        self.semantic_retriever = SemanticRetriever(config)
        self.graph_expander = GraphExpander(config)
        self.all_chunks = None
    
    def index_data(self, chunks: List[Chunk], kg: KnowledgeGraph) -> None:
        """Index chunks and knowledge graph for retrieval"""
        self.all_chunks = {chunk.id: chunk for chunk in chunks}
        self.semantic_retriever.index_chunks(chunks)
        self.graph_expander.index_knowledge_graph(kg)
    
    def retrieve(self, query: str) -> RetrievalResult:
        """Perform complete retrieval pipeline"""
        logger.info(f"Processing query: {query}")
        
        # Step 1: Semantic retrieval
        semantic_scores = self.semantic_retriever.retrieve_semantic(query)
        
        # Get seed chunks
        seed_chunks = []
        for score in semantic_scores:
            if score.chunk_id in self.all_chunks:
                seed_chunks.append(self.all_chunks[score.chunk_id])
        
        logger.info(f"Retrieved {len(seed_chunks)} seed chunks")
        
        # Step 2: Graph expansion
        expanded_chunks, expanded_triplets = self.graph_expander.expand_with_graph(
            seed_chunks, semantic_scores
        )
        
        # Create retrieval result
        result = RetrievalResult(
            query=query,
            retrieved_chunks=seed_chunks,
            semantic_scores=semantic_scores,
            expanded_chunks=expanded_chunks
        )
        
        return result

if __name__ == "__main__":
    # Test retrieval
    try:
        from .schemas import create_test_documents, create_test_query, KG2RAGConfig
        from .preprocessing import OfflinePreprocessor
    except ImportError:
        from schemas import create_test_documents, create_test_query, KG2RAGConfig
        from preprocessing import OfflinePreprocessor
    import os
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Get Gemini API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable")
        exit(1)
    
    # Create test data
    documents = create_test_documents()
    config = KG2RAGConfig(chunk_size=256, semantic_top_k=3, max_hops=2)
    
    # Preprocess
    preprocessor = OfflinePreprocessor(config, api_key)
    chunks, kg = preprocessor.process_documents(documents)
    
    # Test retrieval
    retriever = OnlineRetriever(config)
    retriever.index_data(chunks, kg)
    
    query = "In which part of NYC is the director of Big Stone Gap based?"
    result = retriever.retrieve(query)
    
    print(f"\nQuery: {result.query}")
    print(f"Retrieved {len(result.retrieved_chunks)} seed chunks")
    print(f"Expanded to {len(result.expanded_chunks)} chunks")
    
    print("\nRetrieval test completed!")
