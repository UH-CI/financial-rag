"""
Embedding system for the Financial Document RAG System.
Integrates ChromaDB with Google AI embeddings for document storage and retrieval.
"""

import os
import time
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings
import google.generativeai as genai

# Handle both relative and absolute imports
try:
    from ..settings import settings, validate_settings
except ImportError:
    from settings import settings, validate_settings

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleEmbeddingFunction:
    """Custom embedding function for Google AI embeddings."""
    
    def __init__(self, api_key: str, model_name: str = "text-embedding-004"):
        """Initialize Google embedding function.
        
        Args:
            api_key: Google AI API key
            model_name: Name of the embedding model to use
        """
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=api_key)
        logger.info(f"Initialized Google embeddings with model: {model_name}")
    
    def name(self) -> str:
        """Return the name of this embedding function."""
        return f"google_{self.model_name}"
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """Generate embeddings for input texts.
        
        Args:
            input: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        
        for text in input:
            try:
                # Generate embedding using Google AI
                result = genai.embed_content(
                    model=f"models/{self.model_name}",
                    content=text,
                    task_type="retrieval_document"
                )
                embeddings.append(result['embedding'])
                
                # Add small delay to respect rate limits
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error generating embedding for text: {str(e)}")
                # Return zero vector as fallback
                embeddings.append([0.0] * 768)  # Default dimension for Google embeddings
        
        return embeddings

class ChromaDBManager:
    """Manages ChromaDB operations with Google embeddings."""
    
    def __init__(self):
        """Initialize ChromaDB manager."""
        validate_settings()
        
        self.client = None
        self.collection = None
        self.embedding_function = None
        
        self._initialize_client()
        self._initialize_embedding_function()
        self._initialize_collection()
    
    def _initialize_client(self):
        """Initialize ChromaDB client."""
        try:
            # Create ChromaDB client with persistent storage (embedded mode only)
            self.client = chromadb.PersistentClient(
                path=str(settings.chroma_db_path),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info(f"ChromaDB persistent client initialized at: {settings.chroma_db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {str(e)}")
            raise
    
    def _initialize_embedding_function(self):
        """Initialize Google embedding function."""
        try:
            self.embedding_function = GoogleEmbeddingFunction(
                api_key=settings.google_api_key,
                model_name=settings.embedding_model
            )
            logger.info("Google embedding function initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize embedding function: {str(e)}")
            raise
    
    def _initialize_collection(self):
        """Initialize or get existing collection."""
        try:
            # Try to get existing collection
            try:
                self.collection = self.client.get_collection(
                    name=settings.chroma_collection_name,
                    embedding_function=self.embedding_function
                )
                logger.info(f"Retrieved existing collection: {settings.chroma_collection_name}")
                
            except Exception:
                # Create new collection if it doesn't exist
                self.collection = self.client.create_collection(
                    name=settings.chroma_collection_name,
                    embedding_function=self.embedding_function,
                    metadata={"hnsw:space": settings.chroma_distance_function}
                )
                logger.info(f"Created new collection: {settings.chroma_collection_name}")
                
        except Exception as e:
            logger.error(f"Failed to initialize collection: {str(e)}")
            raise
    
    def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]) -> bool:
        """Add documents to the collection.
        
        Args:
            documents: List of document texts
            metadatas: List of metadata dictionaries
            ids: List of unique document IDs
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Adding {len(documents)} documents to collection")
            
            # Clean metadata to remove None values that ChromaDB can't handle
            cleaned_metadatas = []
            for metadata in metadatas:
                cleaned_meta = {}
                for key, value in metadata.items():
                    if value is not None:
                        # Convert all values to strings, ints, floats, or bools only
                        if isinstance(value, (str, int, float, bool)):
                            cleaned_meta[key] = value
                        else:
                            cleaned_meta[key] = str(value)
                cleaned_metadatas.append(cleaned_meta)
            
            # Add documents in batches to avoid memory issues
            batch_size = settings.batch_size
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i + batch_size]
                batch_metas = cleaned_metadatas[i:i + batch_size]
                batch_ids = ids[i:i + batch_size]
                
                self.collection.add(
                    documents=batch_docs,
                    metadatas=batch_metas,
                    ids=batch_ids
                )
                
                logger.info(f"Added batch {i//batch_size + 1}/{(len(documents) + batch_size - 1)//batch_size}")
                
                # Small delay between batches
                time.sleep(0.5)
            
            logger.info("Successfully added all documents")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add documents: {str(e)}")
            return False
    
    def add_document_chunks(self, chunks) -> bool:
        """Add DocumentChunk objects to the collection.
        
        Args:
            chunks: List of DocumentChunk objects
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert DocumentChunk objects to lists
            documents = [chunk.content for chunk in chunks]
            metadatas = [chunk.metadata for chunk in chunks]
            ids = [chunk.chunk_id for chunk in chunks]
            
            return self.add_documents(documents, metadatas, ids)
            
        except Exception as e:
            logger.error(f"Failed to add document chunks: {str(e)}")
            return False
    
    def query_documents(self, query_text: str, n_results: int = None, 
                       where: Dict[str, Any] = None) -> Dict[str, Any]:
        """Query documents from the collection.
        
        Args:
            query_text: Query text
            n_results: Number of results to return
            where: Metadata filter conditions
            
        Returns:
            Query results dictionary
        """
        try:
            if n_results is None:
                n_results = settings.default_k
            
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where
            )
            
            logger.info(f"Query returned {len(results['documents'][0])} results")
            return results
            
        except Exception as e:
            logger.error(f"Failed to query documents: {str(e)}")
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics.
        
        Returns:
            Dictionary with collection statistics
        """
        try:
            count = self.collection.count()
            return {
                "collection_name": settings.chroma_collection_name,
                "document_count": count,
                "embedding_model": settings.embedding_model,
                "embedding_dimensions": settings.embedding_dimensions
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {str(e)}")
            return {}
    
    def reset_collection(self) -> bool:
        """Reset (clear) the collection.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.delete_collection(name=settings.chroma_collection_name)
            self._initialize_collection()
            logger.info("Collection reset successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset collection: {str(e)}")
            return False

# Global instance
_chroma_manager = None

def get_chroma_manager() -> ChromaDBManager:
    """Get global ChromaDB manager instance."""
    global _chroma_manager
    if _chroma_manager is None:
        _chroma_manager = ChromaDBManager()
    return _chroma_manager

if __name__ == "__main__":
    # Test the embedding system
    try:
        print("Testing ChromaDB setup...")
        manager = get_chroma_manager()
        
        # Test adding a document
        test_docs = ["This is a test document about financial data."]
        test_metas = [{"source": "test", "type": "financial"}]
        test_ids = ["test_doc_1"]
        
        success = manager.add_documents(test_docs, test_metas, test_ids)
        print(f"Document addition: {'✅ Success' if success else '❌ Failed'}")
        
        # Test querying
        results = manager.query_documents("financial data", n_results=1)
        print(f"Query test: {'✅ Success' if results['documents'][0] else '❌ Failed'}")
        
        # Show stats
        stats = manager.get_collection_stats()
        print(f"Collection stats: {stats}")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}") 