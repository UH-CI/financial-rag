#!/usr/bin/env python3
"""
Document Ingestion Script for House Finance RAG System
Processes and ingests documents from a source directory into ChromaDB
"""

import sys
import os
import argparse
from pathlib import Path
from typing import List, Dict, Any
import logging
from datetime import datetime

# Add src directory to Python path
project_root = Path(__file__).parent.parent.parent  # Go up to project root
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))  # Add src directory to path

from settings import settings, validate_settings, get_document_config
from documents.embeddings import get_chroma_manager
from documents.document_processor import DocumentProcessor, DocumentChunk

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def ingest_documents(source_dir: Path, doc_type: str = "financial", 
                    batch_size: int = None, reset_collection: bool = False) -> bool:
    """
    Ingest documents from source directory into ChromaDB.
    
    Args:
        source_dir: Directory containing documents to ingest
        doc_type: Type of documents (financial, legislative, general)
        batch_size: Number of chunks to process at once
        reset_collection: Whether to clear existing collection first
        
    Returns:
        True if successful, False otherwise
    """
    print("📚 Document Ingestion for Financial RAG System")
    print("=" * 50)
    
    try:
        # Validate configuration
        print("📋 Validating configuration...")
        validate_settings()
        print("✅ Configuration valid")
        
        # Check source directory
        if not source_dir.exists():
            print(f"❌ Source directory not found: {source_dir}")
            return False
        
        print(f"📁 Source directory: {source_dir}")
        print(f"📄 Document type: {doc_type}")
        
        # Initialize components
        print("\n🔧 Initializing components...")
        
        # Get ChromaDB manager
        chroma_manager = get_chroma_manager()
        print("✅ ChromaDB manager initialized")
        
        # Reset collection if requested
        if reset_collection:
            print("⚠️  Resetting collection...")
            success = chroma_manager.reset_collection()
            if success:
                print("✅ Collection reset successfully")
            else:
                print("❌ Failed to reset collection")
                return False
        
        # Initialize document processor
        doc_processor = DocumentProcessor(doc_type)
        print("✅ Document processor initialized")
        
        # Process documents
        print(f"\n📖 Processing documents from {source_dir}...")
        all_chunks = doc_processor.process_directory(source_dir)
        
        if not all_chunks:
            print("❌ No documents found or processed")
            return False
        
        print(f"✅ Created {len(all_chunks)} chunks from documents")
        
        # Prepare data for ChromaDB
        print("\n🔄 Preparing data for database...")
        documents = [chunk.content for chunk in all_chunks]
        metadatas = [chunk.metadata for chunk in all_chunks]
        ids = [chunk.chunk_id for chunk in all_chunks]
        
        # Show sample data
        print(f"📊 Sample chunk preview:")
        sample_chunk = all_chunks[0]
        print(f"   ID: {sample_chunk.chunk_id}")
        print(f"   Content: {sample_chunk.content[:100]}...")
        print(f"   Metadata keys: {list(sample_chunk.metadata.keys())}")
        
        # Ingest into ChromaDB
        print(f"\n💾 Ingesting {len(documents)} chunks into ChromaDB...")
        success = chroma_manager.add_documents(documents, metadatas, ids)
        
        if success:
            print("✅ Documents ingested successfully!")
            
            # Show final statistics
            stats = chroma_manager.get_collection_stats()
            print(f"\n📊 Final Statistics:")
            print(f"   Collection: {stats.get('name', 'N/A')}")
            print(f"   Total documents: {stats.get('document_count', 0)}")
            print(f"   Embedding model: {stats.get('embedding_model', 'N/A')}")
            print(f"   Dimensions: {stats.get('embedding_dimensions', 'N/A')}")
            
            # Test query
            print(f"\n🧪 Testing search functionality...")
            test_results = chroma_manager.query_documents(
                "budget appropriation", 
                n_results=3
            )
            
            if test_results['documents'][0]:
                print(f"✅ Search test successful - found {len(test_results['documents'][0])} results")
                print(f"   Sample result: {test_results['documents'][0][0][:100]}...")
            else:
                print("⚠️  Search test returned no results")
            
            print("\n🎉 Document ingestion completed successfully!")
            print("=" * 50)
            print("Next steps:")
            print("1. Test queries with your documents")
            print("2. Build query interface for interactive search")
            
            return True
        else:
            print("❌ Failed to ingest documents into ChromaDB")
            return False
            
    except Exception as e:
        print(f"❌ Ingestion failed: {str(e)}")
        logger.error(f"Document ingestion failed: {str(e)}", exc_info=True)
        return False

def show_source_info(source_dir: Path):
    """Show information about source directory."""
    print(f"📁 Source Directory Analysis: {source_dir}")
    print("=" * 40)
    
    if not source_dir.exists():
        print("❌ Directory does not exist")
        return
    
    # Count files by type
    file_counts = {}
    total_size = 0
    
    for file_path in source_dir.rglob("*"):
        if file_path.is_file():
            ext = file_path.suffix.lower()
            file_counts[ext] = file_counts.get(ext, 0) + 1
            total_size += file_path.stat().st_size
    
    print(f"📊 File Summary:")
    for ext, count in sorted(file_counts.items()):
        supported = "✅" if ext in settings.supported_file_types else "❌"
        print(f"   {ext}: {count} files {supported}")
    
    print(f"📏 Total size: {total_size / 1024 / 1024:.1f} MB")
    
    # Show supported files
    supported_files = []
    for ext in settings.supported_file_types:
        supported_files.extend(list(source_dir.glob(f"*{ext}")))
    
    print(f"\n📄 Supported files to process: {len(supported_files)}")
    for file_path in supported_files[:5]:  # Show first 5
        size_kb = file_path.stat().st_size / 1024
        print(f"   {file_path.name} ({size_kb:.1f} KB)")
    
    if len(supported_files) > 5:
        print(f"   ... and {len(supported_files) - 5} more files")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into ChromaDB")
    parser.add_argument(
        "--source", 
        type=Path, 
        default=settings.documents_path,
        help=f"Source directory containing documents (default: {settings.documents_path})"
    )
    parser.add_argument(
        "--doc-type", 
        choices=["financial", "legislative", "general"], 
        default="financial",
        help="Type of documents to process (default: financial)"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=settings.batch_size,
        help=f"Batch size for processing (default: {settings.batch_size})"
    )
    parser.add_argument(
        "--reset", 
        action="store_true",
        help="Reset (clear) the collection before ingesting"
    )
    parser.add_argument(
        "--info", 
        action="store_true",
        help="Show source directory information only"
    )
    
    args = parser.parse_args()
    
    if args.info:
        show_source_info(args.source)
        sys.exit(0)
    
    success = ingest_documents(
        source_dir=args.source,
        doc_type=args.doc_type,
        batch_size=args.batch_size,
        reset_collection=args.reset
    )
    
    sys.exit(0 if success else 1) 