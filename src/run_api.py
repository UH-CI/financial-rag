#!/usr/bin/env python3
"""
FastAPI Server Startup Script
Launches the House Finance Document API server
"""

import sys
import os
import uvicorn
import argparse
from pathlib import Path

def main():
    """Start the FastAPI server"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='House Finance Document API Server')
    parser.add_argument('--ingest', action='store_true', 
                       help='Ingest processed documents before starting the server')
    parser.add_argument('--ingest-only', action='store_true',
                       help='Only ingest documents, do not start the server')
    args = parser.parse_args()
    
    try:
        print("🚀 Starting House Finance Document API...")
        print("📚 Loading ChromaDB and embedding models...")
        
        # Set the current directory as the project root (src directory is now root)
        project_root = Path(__file__).parent
        sys.path.insert(0, str(project_root))
        
        # Change working directory to project root
        os.chdir(project_root)
        
        # Import here to catch any configuration errors early
        from settings import Settings
        config = Settings()
        
        print(f"✅ Configuration loaded:")
        print(f"   - Documents Path: {config.documents_path}")
        print(f"   - ChromaDB Path: {config.chroma_db_path}")
        print(f"   - Collection: {config.chroma_collection_name}")
        print(f"   - Embedding Model: {config.embedding_model} ({config.embedding_provider})")
        print("=" * 60)
        
        # Handle document ingestion if requested
        if args.ingest or args.ingest_only:
            print("\n📥 Ingesting processed documents...")
            try:
                from api import ingest_processed_documents, budget_manager, text_manager
                
                # Reset collections before ingestion to avoid duplicates
                print("🔄 Resetting collections to avoid duplicates...")
                budget_manager.reset_collection()
                text_manager.reset_collection()
                print("✅ Collections reset successfully")
                
                # Reinitialize the managers to get fresh collection references
                print("🔄 Reinitializing collection managers...")
                from api import BudgetChromeManager, TextChromeManager
                import api
                api.budget_manager = BudgetChromeManager()
                api.text_manager = TextChromeManager()
                print("✅ Collection managers reinitialized")
                
                # Now ingest the documents
                result = ingest_processed_documents()
                print(f"✅ Document ingestion completed: {result}")
            except Exception as e:
                print(f"❌ Error during document ingestion: {e}")
                if args.ingest_only:
                    sys.exit(1)
                else:
                    print("⚠️  Continuing with server startup despite ingestion error...")
        
        # Exit if only ingesting documents
        if args.ingest_only:
            print("✅ Document ingestion completed successfully. Exiting.")
            return
        
        print("\n🌐 Starting server at http://localhost:8000")
        print("📖 API Documentation: http://localhost:8000/docs")
        print("🔍 Interactive API: http://localhost:8000/redoc")
        print("\nPress Ctrl+C to stop the server\n")
        
        # Start the server
        uvicorn.run(
            "api:app",
            host="0.0.0.0",
            port=8000,
            reload=False,  # Disable reload to prevent import issues
            log_level="info",
            access_log=True
        )
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Make sure all dependencies are installed:")
        print("   pip install fastapi uvicorn python-multipart")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 