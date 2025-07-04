"""
Configuration management for the Financial Document RAG System.
Centralized configuration with environment variable support and extensible settings.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    Designed for extensibility across different document types and deployment environments.
    """
    
    # API Keys
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    
    # Paths
    documents_path: Path = Field(default=Path("./output"), env="DOCUMENTS_PATH")
    chroma_db_path: Path = Field(default=Path("./chroma_db/data"), env="CHROMA_DB_PATH")
    
    # ChromaDB Configuration
    chroma_collection_name: str = Field(default="financial_documents", env="CHROMA_COLLECTION_NAME")
    chroma_distance_function: str = Field(default="cosine", env="CHROMA_DISTANCE_FUNCTION")
    # ChromaDB always runs in embedded mode
    
    # Embedding Configuration - Default to Google
    embedding_model: str = Field(default="text-embedding-004", env="EMBEDDING_MODEL")
    embedding_provider: str = Field(default="google", env="EMBEDDING_PROVIDER")  # google, sentence-transformers
    embedding_dimensions: int = Field(default=768, env="EMBEDDING_DIMENSIONS")
    
    # LLM Configuration - Default to Google
    llm_model: str = Field(default="gemini-1.5-flash", env="LLM_MODEL")
    llm_provider: str = Field(default="google", env="LLM_PROVIDER")  # google
    llm_temperature: float = Field(default=0.1, env="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=1000, env="LLM_MAX_TOKENS")
    
    # Chunking Configuration
    chunk_size: int = Field(default=1000, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, env="CHUNK_OVERLAP")
    
    # Retrieval Configuration
    default_k: int = Field(default=5, env="DEFAULT_K")
    max_k: int = Field(default=20, env="MAX_K")
    
    # Processing Configuration
    batch_size: int = Field(default=10, env="BATCH_SIZE")
    max_workers: int = Field(default=4, env="MAX_WORKERS")
    
    # Document Processing
    supported_file_types: list = Field(default=[".txt", ".pdf", ".json"], env="SUPPORTED_FILE_TYPES")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()

# Document type configurations
DOCUMENT_TYPE_CONFIGS = {
    "financial": {
        "chunk_size": 800,
        "chunk_overlap": 150,
        "preserve_tables": True,
        "extract_financial_entities": True,
        "system_prompt": """You are a financial analyst assistant specializing in government budget documents.
        Always preserve exact numerical values and include fund codes when relevant."""
    },
    "legislative": {
        "chunk_size": 1200,
        "chunk_overlap": 200,
        "preserve_sections": True,
        "extract_legal_entities": True,
        "system_prompt": """You are a legislative analyst assistant.
        Focus on policy implications and legal language."""
    },
    "general": {
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "preserve_context": True,
        "system_prompt": """You are a helpful assistant that answers questions based on the provided documents."""
    }
}

# Model configurations for different providers
MODEL_CONFIGS = {
    "google": {
        "gemini-1.5-flash": {
            "max_tokens": 8192,
            "supports_system_prompt": True,
            "cost_per_1k_tokens": 0.00015
        },
        "gemini-1.5-pro": {
            "max_tokens": 32768,
            "supports_system_prompt": True,
            "cost_per_1k_tokens": 0.00125
        }
    }
}

def get_document_config(doc_type: str = "general") -> Dict[str, Any]:
    """Get configuration for specific document type."""
    return DOCUMENT_TYPE_CONFIGS.get(doc_type, DOCUMENT_TYPE_CONFIGS["general"])

def get_model_config(provider: str, model: str) -> Dict[str, Any]:
    """Get configuration for specific model."""
    return MODEL_CONFIGS.get(provider, {}).get(model, {})

def ensure_directories():
    """Ensure all required directories exist."""
    settings.documents_path.mkdir(exist_ok=True)
    settings.chroma_db_path.mkdir(exist_ok=True)

def validate_settings() -> bool:
    """Validate that all required settings are properly configured."""
    # Check LLM provider and API key
    if settings.llm_provider == "google":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when using Google/Gemini models")
    
    # Check embedding provider and API key
    if settings.embedding_provider == "google":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when using Google embeddings")
    
    return True

# Initialize on import
ensure_directories()

if __name__ == "__main__":
    # Test configuration
    try:
        validate_settings()
        print("✅ Configuration valid")
        print(f"Documents path: {settings.documents_path}")
        print(f"ChromaDB path: {settings.chroma_db_path}")
        print(f"Embedding model: {settings.embedding_model} ({settings.embedding_provider})")
        print(f"LLM model: {settings.llm_model} ({settings.llm_provider})")
        
        # Show model capabilities
        model_config = get_model_config(settings.llm_provider, settings.llm_model)
        if model_config:
            print(f"Max tokens: {model_config.get('max_tokens', 'unknown')}")
            print(f"Cost per 1K tokens: ${model_config.get('cost_per_1k_tokens', 'unknown')}")
            
    except Exception as e:
        print(f"❌ Configuration error: {e}") 