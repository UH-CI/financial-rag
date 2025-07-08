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
    parser = argparse.ArgumentParser(
        description='House Finance Document API Server',
        epilog='''
Examples:
  python run_api.py                                    # Start server only
  python run_api.py --ingest                          # Reset collections and ingest standard docs
  python run_api.py --ingest --append                 # Add standard docs to existing collections
  python run_api.py --ingest --ingest-type worksheets # Reset and ingest worksheets
  python run_api.py --ingest --ingest-type worksheets --append  # Add worksheets to existing data
  python run_api.py --ingest-only --append --ingest-file documents/my_file.json  # Append specific file
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--ingest', action='store_true', 
                       help='Ingest processed documents before starting the server')
    parser.add_argument('--ingest-only', action='store_true',
                       help='Only ingest documents, do not start the server')
    parser.add_argument('--ingest-file', default='documents/processed_all_documents_geminiV4_expanded.json',
                       help='Path to the processed JSON file to ingest (relative to src directory)')
    parser.add_argument('--ingest-type', choices=['standard', 'worksheets'], default='standard',
                       help='Type of documents to ingest: standard or worksheets')
    parser.add_argument('--no-reset', action='store_true',
                       help='Do not reset collections before ingestion (append to existing data)')
    parser.add_argument('--append', action='store_true',
                       help='Append documents to existing collections without resetting (same as --no-reset)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind server to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind server to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    parser.add_argument('--log-level', choices=['debug', 'info', 'warning', 'error'], default='info',
                       help='Log level')
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
            print(f"\n📥 Ingesting {args.ingest_type} documents from {args.ingest_file}...")
            
            # Determine if we should reset collections
            reset_collections = not (args.no_reset or args.append)
            
            if reset_collections:
                print("🔄 Collections will be reset before ingestion")
            else:
                print("➕ Documents will be appended to existing collections")
            
            try:
                # Import the appropriate ingestion function
                if args.ingest_type == 'worksheets':
                    from api import ingest_budget_worksheets, budget_manager, text_manager
                    ingestion_func = ingest_budget_worksheets
                else:
                    from api import ingest_processed_documents, budget_manager, text_manager
                    ingestion_func = ingest_processed_documents
                
                # Reset collections before ingestion to avoid duplicates (if requested)
                if reset_collections:
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
                else:
                    print("📊 Using existing collections (no reset)")
                
                # Now ingest the documents
                result = ingestion_func(args.ingest_file, reset_collections)
                
                if result.get('success', False):
                    if args.ingest_type == 'worksheets':
                        print(f"✅ Document ingestion completed:")
                        print(f"   - Worksheet items: {result.get('worksheet_items_ingested', 0)}")
                        print(f"   - Text items: {result.get('text_items_ingested', 0)}")
                    else:
                        print(f"✅ Document ingestion completed:")
                        print(f"   - Budget items: {result.get('budget_items_ingested', 0)}")
                        print(f"   - Text items: {result.get('text_items_ingested', 0)}")
                    
                    print(f"   - Processing time: {result.get('processing_time_seconds', 0):.2f} seconds")
                    print(f"   - Rate: {result.get('items_per_second', 0):.1f} items/second")
                    
                    if result.get('errors'):
                        print(f"   - Errors: {len(result['errors'])} (check logs for details)")
                else:
                    raise Exception(result.get('error', 'Unknown ingestion error'))
                    
            except FileNotFoundError as e:
                print(f"❌ File not found: {e}")
                print(f"💡 Make sure the file exists: {args.ingest_file}")
                if args.ingest_only:
                    sys.exit(1)
                else:
                    print("⚠️  Continuing with server startup despite ingestion error...")
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
        
        print(f"\n🌐 Starting server at http://{args.host}:{args.port}")
        print(f"📖 API Documentation: http://localhost:{args.port}/docs")
        print(f"🔍 Interactive API: http://localhost:{args.port}/redoc")
        print("\nPress Ctrl+C to stop the server\n")
        
        # Start the server
        uvicorn.run(
            "api:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
            access_log=True
        )
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Make sure all dependencies are installed:")
        print("   pip install fastapi uvicorn python-multipart chromadb sentence-transformers google-generativeai python-dotenv pydantic")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 