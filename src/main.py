from fastapi import FastAPI, HTTPException, Query, Form, File, UploadFile, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List, Dict, Any, Optional, Union
import os
from pathlib import Path
import json
import google.generativeai as genai
from document_type_classifier import classify_document_type, get_document_type_description, get_document_type_icon
from tqdm import tqdm
import logging
from datetime import datetime
from documents.step0_document_upload.web_scraper import ai_crawler
from typing import Generator
from fastapi.templating import Jinja2Templates

from fiscal_notes.generation.step1_get_context import fetch_documents
from fiscal_notes.generation.step2_reorder_context import reorder_documents
from fiscal_notes.generation.step3_retrieve_docs import retrieve_documents
from fiscal_notes.generation.step4_get_numbers import extract_number_context
from fiscal_notes.generation.step5_fiscal_note_gen import generate_fiscal_notes
from fiscal_notes.generation.step6_enhance_numbers import enhance_numbers_for_bill
from fiscal_notes.generation.step7_track_chronological import track_chronological_changes

import shutil
from enum import Enum
import requests


from app_types.requests import (
    CollectionRequest, SearchRequest, QueryRequest,
    ChunkingRequest, DocumentResponse, CrawlRequest,
    ChatWithPDFRequest, DriveUploadRequest,
    CollectionStatistics, CollectionsStatsResponse, LLMRequest
)

from documents.step0_document_upload.google_upload import download_pdfs_from_drive
from documents.step1_text_extraction.pdf_text_extractor import extract_pdf_text
from documents.step2_chunking.chunker import chunk_document
from documents.step0_document_upload.web_scraper import scrape_bill_page_links


from settings import Settings, settings
from documents.embeddings import DynamicChromeManager
from query_processor import QueryProcessor
from langgraph_agent import LangGraphRAGAgent
from chatbot_engine.nlp_backend import NLPBackend

from bill_data.bill_similarity_search import BillSimilaritySearcher

# User permissions system imports
from api.users import router as users_router
from api.admin import router as admin_router
from api.protected_tools import router as tools_router

# ============================================================================
# FEATURE FLAGS - Fiscal Note Generation Pipeline
# ============================================================================
# Set these to True/False to enable/disable specific steps in the pipeline
ENABLE_STEP6_ENHANCE_NUMBERS = False  # Step 6: Enhance numbers with RAG agent
ENABLE_STEP7_TRACK_CHRONOLOGICAL = False  # Step 7: Track chronological changes
# ============================================================================

# Load configuration
def load_config() -> Dict[str, Any]:
    """Load configuration from config.json"""
    try:
        # Try to use __file__ if available (normal module import)
        config_path = Path(__file__).parent / "config.json"
    except NameError:
        # Fallback for direct execution or when __file__ is not defined
        config_path = Path("config.json")
    
    with open(config_path, 'r') as f:
        return json.load(f)

config = load_config()

# Initialize FastAPI app with config
app = FastAPI(
    title=config["api"]["title"],
    description=config["api"]["description"],
    version=config["api"]["version"],
    # Temporarily disable automatic OpenAPI schema generation to work around FastAPI bug
    openapi_url=None,
    docs_url=None,
    redoc_url=None
)

templates_path = Path(__file__).parent / "fiscal_notes" / "templates"
templates = Jinja2Templates(directory=templates_path)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include user permissions system routers
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(tools_router)

# Initialize BillSimilaritySearcher
bill_similarity_searcher = BillSimilaritySearcher("./bill_data/introduction_document_vectors.json")
bill_similarity_searcher.load_data()

model = genai.GenerativeModel('gemini-2.5-pro')

# Create collection managers dynamically from config
collection_names = config["collections"]
collection_managers: Dict[str, DynamicChromeManager] = {}

for collection_name in collection_names:
    collection_managers[collection_name] = DynamicChromeManager(collection_name)

# Initialize query processor with collection managers and config
query_processor = QueryProcessor(collection_managers, config)

# Initialize NLP Backend
try:
    nlp_backend = NLPBackend(collection_managers, config)
    print("✅ NLP Backend initialized successfully")
    USE_NLP_BACKEND = True
except Exception as e:
    print(f"⚠️  NLP Backend initialization failed: {e}")
    print("🔄 Falling back to traditional QueryProcessor")
    nlp_backend = None
    USE_NLP_BACKEND = False

# Initialize LangGraph RAG Agent
try:
    langgraph_agent = LangGraphRAGAgent(collection_managers, config)
    print("✅ LangGraph RAG Agent initialized successfully")
    USE_LANGGRAPH = True
except Exception as e:
    print(f"⚠️  LangGraph Agent initialization failed: {e}")
    print("🔄 Falling back to traditional QueryProcessor")
    langgraph_agent = None
    USE_LANGGRAPH = False

def send_error_to_slack(error_message):
    slack_webhook = os.getenv("SLACK_WEBHOOK")
    slack_payload = {
        "text": error_message,
        "username": "RAG-System Error",
        "icon_emoji": ":warning:",
        "webhook_url": slack_webhook
    }
    requests.post(slack_webhook, json=slack_payload)

def send_success_msg_to_slack(success_message):
    slack_webhook = os.getenv("SLACK_WEBHOOK")
    slack_payload = {
        "text": success_message,
        "username": "RAG-System Success",
        "icon_emoji": ":white_check_mark:",
        "webhook_url": slack_webhook
    }
    requests.post(slack_webhook, json=slack_payload)

# Helper functions for collection management
def get_collection_manager(collection_name: str) -> DynamicChromeManager:
    """Get collection manager by name"""
    if collection_name not in collection_managers:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
    
    return collection_managers[collection_name]


def get_collection_stats(collection_manager: DynamicChromeManager) -> Dict[str, Any]:
    """Get statistics for a collection"""
    try:
        count = collection_manager.collection.count()
        return {
            "collection_name": collection_manager.collection_name,
            "document_count": count,
            "embedding_model": settings.embedding_model
        }
    except Exception as e:
        print(f"Error getting stats for collection {collection_manager.collection_name}: {str(e)}")
        return {
            "collection_name": collection_manager.collection_name,
            "document_count": 0,
            "error": str(e)
        }

def get_ingestion_config(collection_name: str) -> dict:
    """Get ingestion configuration for a specific collection"""
    for config_item in config.get("ingestion_configs", []):
        if config_item.get("collection_name") == collection_name:
            return config_item
    
    # Return default if not found
    return {
        "collection_name": collection_name,
        "contents_to_embed": ["text", "content", "description"]
    }

def get_default_collection_manager() -> DynamicChromeManager:
    """Get the default collection manager"""
    default_collection = config.get("default_collection", collection_names[0])
    if default_collection not in collection_managers:
        # If default collection doesn't exist, use first available collection
        default_collection = collection_names[0]
    return get_collection_manager(default_collection)

def ingest_from_source_file(collection_name: str, source_file: str, ingestion_config: dict) -> dict:
    """Ingest documents from a source file into a specific collection"""
    try:
        from settings import settings
        import os
        
        # Construct full file path
        file_path = os.path.join(settings.documents_path, source_file)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file not found: {file_path}")
        
        # Load and parse JSON file
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Expect JSON to be an array of documents
        if not isinstance(data, list):
            raise Exception(f"JSON file must contain an array of documents, got {type(data)}")
        
        documents = data
        manager = get_collection_manager(collection_name)
        
        # Ingest documents
        ingested_count = 0
        errors = []
        
        print(f"📥 Ingesting {len(documents)} documents from '{source_file}' into '{collection_name}'...")
        print(f"🎯 Embedding fields: {ingestion_config.get('contents_to_embed', [])}")
        
        for i, doc in enumerate(tqdm(documents, desc=f"Processing {source_file}")):
            try:
                if manager.add_document(doc, ingestion_config):
                    ingested_count += 1
                else:
                    errors.append(f"Document {i}: Failed to add to collection")
            except Exception as e:
                errors.append(f"Document {i}: {str(e)}")
                continue
        
        return {
            "success": True,
            "collection_name": collection_name,
            "source_file": source_file,
            "ingested_count": ingested_count,
            "total_documents": len(documents),
            "embedded_fields": ingestion_config.get('contents_to_embed', []),
            "errors": errors[:10]
        }
        
    except Exception as e:
        return {
            "success": False,
            "collection_name": collection_name,
            "source_file": source_file,
            "error": str(e),
            "ingested_count": 0,
            "total_documents": 0
        }


def get_search_params(num_results: Optional[int] = None) -> int:
    """Get search parameters with config defaults"""
    if num_results is None:
        return config["search"]["default_results"]
    return min(num_results, config["search"]["max_results"])

def process_pdf_file( file_location: str,
    output_json_path: str,
    chunked_json_path: str,
    contains_tables: bool = Query(False, description="Set to True if the PDF contains tables."),
    contains_images_of_text: bool = Query(False, description="Set to True if the PDF has images containing text."),
    contains_images_of_nontext: bool = Query(False, description="Set to True for non-text images (uses OCR as a placeholder)."),
    # New parameters for chunking
    use_ai: bool = Query(False, description="If True, uses AI-powered chunking; otherwise, simple chunking."),
    chosen_methods: Optional[List[str]] = Query(None, description="For AI chunking: list of text fields to combine (e.g., ['pymupdf_extraction_text'])."),
    prompt_description: Optional[str] = Query(None, description="For AI chunking: prompt for LLM on how to extract items."),
    previous_pages_to_include: int = Query(1, description="For AI chunking: number of previous pages for context."),
    context_items_to_show: int = Query(2, description="For AI chunking: number of previously extracted items for few-shot examples."),
    rewrite_query: bool = Query(False, description="For AI chunking: If True, refine prompt_description with LLM."),
    chosen_method: Optional[str] = Query(None, description="For simple chunking: single text field to chunk (e.g., 'pymupdf_extraction_text')."),
    chunk_size: int = Query(1000, description="For simple chunking: character count per chunk."),
    overlap: int = Query(100, description="For simple chunking: character overlap between chunks.")):
    # Call the PDF text extraction function
    # Based on your instruction, we assume 'extract_pdf_text' will be modified
    # to *not* take an 'output_path' and instead return the extracted data directly.
    # The API endpoint will then be responsible for saving this data.
    try:
        print(f"Starting text extraction for {file.filename}...")
        extracted_data = extract_pdf_text(
            pdf_file_path=file_location,
            output_path=output_json_path,
            contains_tables=contains_tables,
            contains_images_of_text=contains_images_of_text,
            contains_images_of_nontext=contains_images_of_nontext
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting text: {str(e)}")
    
    try:    
        # Save the extracted data to a JSON file
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(extracted_data, f, indent=2, ensure_ascii=False)
        print(f"Extracted text saved to: {output_json_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving extracted text: {str(e)}")

    try:
        # Call the chunking function
        print(f"Starting chunking for {file.filename}...")
        from documents.step2_chunking.chunker import chunk_document # Import locally to avoid circular dependency issues if any
        chunk_document(
            input_json_path=output_json_path, # Input for chunking is the output from extraction
        output_json_path=chunked_json_path,
        use_ai=use_ai,
        chosen_methods=chosen_methods,
        prompt_description=prompt_description,
        previous_pages_to_include=previous_pages_to_include,
        context_items_to_show=context_items_to_show,
        rewrite_query=rewrite_query,
        chosen_method=chosen_method,
        chunk_size=chunk_size,
        overlap=overlap
    )
        print(f"Chunked data saved to: {chunked_json_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error chunking document: {str(e)}")
    return {"message": "PDF processed successfully"}


def search_relevant_documents(query: str, collections: Optional[List[str]] = None, num_results: int = None) -> List[Dict[str, Any]]:
    """Search for relevant documents across collections"""
    if num_results is None:
        num_results = get_search_params()
    
    search_collections = collections or collection_names
    all_results = []
    
    for collection_name in search_collections:
        try:
            manager = get_collection_manager(collection_name)
            results = manager.search_similar_chunks(query, num_results)
            
            for result in results:
                result["metadata"]["collection"] = collection_name
                all_results.append(result)
        except Exception as e:
            print(f"Error searching collection {collection_name}: {e}")
            continue
                            
    # Sort by score and return top results
    if all_results and "score" in all_results[0]:
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    return all_results[:num_results]

# Custom OpenAPI endpoint with error handling
from fastapi.openapi.utils import get_openapi as fastapi_get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    try:
        openapi_schema = fastapi_get_openapi(
            title=config["api"]["title"],
            version=config["api"]["version"],
            description=config["api"]["description"],
            routes=app.routes,
        )
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    except Exception as e:
        # Return a minimal schema if generation fails
        return {
            "openapi": "3.1.0",
            "info": {
                "title": config["api"]["title"],
                "version": config["api"]["version"],
                "description": f"{config['api']['description']} (Schema generation error: {str(e)})"
            },
            "paths": {}
        }

app.openapi = custom_openapi

# Re-enable docs with custom schema
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{config['api']['title']} - Swagger UI"
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{config['api']['title']} - ReDoc"
    )

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    return JSONResponse(custom_openapi())

@app.get("/")
async def root():
    if USE_NLP_BACKEND:
        processing_method = "Advanced NLP Backend (6-step pipeline)"
    elif USE_LANGGRAPH:
        processing_method = "LangGraph Agentic Workflow"
    else:
        processing_method = "Multi-step Reasoning"
    
    return {
        "message": f"Welcome to {config['api']['title']}",
        "version": config['api']['version'],
        "available_collections": collection_names,
        "processing_method": processing_method,
        "features": [
            "🧠 Advanced NLP Backend with 6-step pipeline" if USE_NLP_BACKEND else ("🤖 Agentic query processing with LangGraph tools" if USE_LANGGRAPH else "Multi-step query processing with reasoning"),
            "🔍 LLM-guided retrieval method selection" if USE_NLP_BACKEND else ("Intelligent tool-based document search" if USE_LANGGRAPH else "Semantic search across collections"),
            "📊 Dynamic context building and analysis",
            "📚 Document ingestion and management",
            "📈 Collection statistics and management"
        ],
        "endpoints": ["/search", "/query", "/ingest", "/reset", "/collections"],
        "nlp_backend_features": [
            "LLM-guided document retrieval decisions",
            "Intelligent query generation and method selection",
            "4 retrieval methods: keyword, dense encoder, BM25, multi-hop",
            "Conversation state management and follow-up detection",
            "LLM-based reranking for improved precision",
            "Context-aware answer generation with history"
        ] if USE_NLP_BACKEND else None,
        "agentic_features": [
            "Query analysis and intent detection",
            "Strategic tool-based search execution", 
            "Context-aware answer generation",
            "Multi-collection intelligent search"
        ] if USE_LANGGRAPH else None
    }

@app.post("/health")
async def health_check():
    slack_webhook = os.getenv("SLACK_WEBHOOK")
    slack_payload = {
        "text": "Health check passed",
        "username": "RAG-System Health Check",
        "icon_emoji": ":ok:",
        "webhook_url": slack_webhook
    }
    requests.post(slack_webhook, json=slack_payload)
    return {"status": "ok"}

@app.get("/chunked_text")
async def get_chunked_text():
    """Get chunked text stored in documents/chunked_text folder"""
    chunked_text = []
    for filename in os.listdir("documents/chunked_text"):
        chunked_text.append({
            "filename": filename,
            "path": os.path.join("documents/chunked_text", filename)
        })
    
    return {
        "chunked_text": chunked_text,
        "total_chunked_text": len(chunked_text)
    }

@app.get("/documents")
async def get_documents():
    """Get documents stored in documents/storage_documents folder"""
    documents = []
    for filename in os.listdir("documents/storage_documents"):
        documents.append({
            "filename": filename,
            "path": os.path.join("documents/storage_documents", filename)
        })
    
    return {
        "documents": documents,
        "total_documents": len(documents)
    }

@app.get("/collections")
async def get_collections():
    """Get list of collections stored in documents/storage_documents folder, 
    AKA, list of directories in documents/storage_documents folder"""
    base_path = "documents/storage_documents"
    collections = []

    for entry in os.listdir(base_path):
        full_path = os.path.join(base_path, entry)
        if os.path.isdir(full_path):
            num_documents = len(os.listdir(full_path))
        else:
            # Skip files like .DS_Store
            continue
        if os.path.isdir(full_path):
            print(f"Found collection: {entry}")
            collections.append({
                "name": entry,
                "num_documents": num_documents
            })

    return {
        "collections": collections,
        "total_collections": len(collections)
    }


@app.get("/collections/stats")
async def get_collections_statistics():
    """Get statistics about all collections in ChromaDB
    
    Returns:
        CollectionsStatsResponse: Statistics for all collections including document counts
    """
    # Gather stats for all collections
    collections_stats = []
    total_documents = 0
    
    for collection_name, manager in collection_managers.items():
        stats = get_collection_stats(manager)
        collections_stats.append(CollectionStatistics(**stats))
        
        # Update total document count
        total_documents += stats.get("document_count", 0)
    
    return CollectionsStatsResponse(
        collections=collections_stats,
        total_collections=len(collections_stats),
        total_documents=total_documents
    )

@app.post("/search")
async def search_documents(request: SearchRequest):
    """Search documents across specified collections"""
    num_results = get_search_params(request.num_results)
    search_collections = request.collections or collection_names
    
    # Validate collections
    for collection_name in search_collections:
        if collection_name not in collection_managers:
            raise HTTPException(status_code=400, detail=f"Collection '{collection_name}' not found")
    
    all_results = []
    
    for collection_name in search_collections:
        try:
            manager = get_collection_manager(collection_name)
            results = manager.search_similar_chunks(request.query, num_results)
            
            # Add collection info to metadata
            for result in results:
                result["metadata"]["collection"] = collection_name
                all_results.append(DocumentResponse(
                    content=result["content"],
                    metadata=result["metadata"],
                    score=result.get("score")
                ))
        except Exception as e:
            print(f"Error searching collection {collection_name}: {e}")
            continue
            
    # Sort by score if available and limit results
    if all_results and all_results[0].score is not None:
        all_results.sort(key=lambda x: x.score, reverse=True)
    
    return all_results[:num_results]



@app.post("/query")
async def query_documents(request: QueryRequest):
    """Advanced query processing with agentic LangGraph workflow or multi-step reasoning fallback"""
    try:
        # Use conversation ID from request or generate one
        conversation_id = request.conversation_id or f"api_session_{hash(request.query) % 10000}"
        
        if USE_NLP_BACKEND and nlp_backend is not None:
            # Use Advanced NLP Backend (6-step pipeline)
            print(f"🧠 Using NLP Backend for query: '{request.query}'")
            result = nlp_backend.process_query(request.query, conversation_id=conversation_id)
            
            # Add metadata about the request
            result["query"] = request.query
            result["collections_available"] = collection_names
            result["processing_method"] = "nlp-backend-6-step"
            result["conversation_id"] = conversation_id
            
        elif USE_LANGGRAPH and langgraph_agent is not None:
            # Use LangGraph RAG Agent (agentic approach)
            print(f"🤖 Using LangGraph Agent for query: '{request.query}'")
            result = langgraph_agent.process_query(request.query, threshold=request.threshold)
            
            # Add metadata about the request
            result["query"] = request.query
            result["collections_available"] = collection_names
            result["processing_method"] = "langgraph-agentic"
            result["threshold_used"] = request.threshold
            
        else:
            # Fallback to traditional multi-step query processor
            print(f"🔄 Using traditional QueryProcessor for query: '{request.query}'")
            result = query_processor.process_query(request.query, threshold=request.threshold)
            
            # Add metadata about the request
            result["query"] = request.query
            result["collections_available"] = collection_names
            result["processing_method"] = "multi-step-reasoning"
            result["threshold_used"] = request.threshold
        
        return result
                            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


# NLP Backend conversation management endpoints
@app.get("/conversation/{conversation_id}")
async def get_conversation_state(conversation_id: str):
    """Get the current state of a conversation (NLP Backend only)"""
    if not USE_NLP_BACKEND or nlp_backend is None:
        raise HTTPException(status_code=404, detail="NLP Backend not available")
    
    try:
        state = nlp_backend.get_conversation_state(conversation_id)
        return state
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting conversation state: {str(e)}")

@app.delete("/conversation/{conversation_id}")
async def reset_conversation(conversation_id: str):
    """Reset a conversation state (NLP Backend only)"""
    if not USE_NLP_BACKEND or nlp_backend is None:
        raise HTTPException(status_code=404, detail="NLP Backend not available")
    
    try:
        success = nlp_backend.reset_conversation(conversation_id)
        return {
            "success": success, 
            "conversation_id": conversation_id, 
            "message": "Conversation reset successfully" if success else "Conversation not found"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting conversation: {str(e)}")


@app.post("/step2-chunking")
async def step2_chunking(payload: ChunkingRequest):
    """
    Chunk extracted text from all JSON files in a specific collection.
    
    Args:
        collection_name (str): Name of the collection to process.
        chosen_methods (List[str]): Methods to use for chunking.
        identifier (str): Identifier for the chunking process.
        chunk_size (int): Size of each chunk.
        chunk_overlap (int): Overlap between chunks.
        use_ai (bool): Whether to use AI for chunking.
        prompt_description (Optional[str]): Prompt description for AI chunking.
        previous_pages_to_include (int): Number of previous pages for context.
        context_items_to_show (int): Number of context items to show.
        rewrite_query (bool): Whether to rewrite the query.
    """
    logging.info(f"Starting chunking for collection '{payload.collection_name}'")
    # Define paths
    collection_extracted_dir = os.path.join("documents", "extracted_text", payload.collection_name)
    collection_chunked_dir = os.path.join("documents", "chunked_text", payload.collection_name)

    # Check if collection extracted directory exists
    if not os.path.exists(collection_extracted_dir):
        raise HTTPException(status_code=404, detail=f"Collection '{payload.collection_name}' not found in extracted text")
    
    # Create chunked text directory for collection
    os.makedirs(collection_chunked_dir, exist_ok=True)
    
    # Get all JSON files in the extracted text collection
    json_files = [f for f in os.listdir(collection_extracted_dir) if f.lower().endswith('.json')]
    logging.info(f"Found {len(json_files)} JSON files in collection '{payload.collection_name}'")
    if not json_files:
        raise HTTPException(status_code=404, detail=f"No extracted text files found in collection '{payload.collection_name}'")
    
    processed_files = []
    errors = []
    
    logging.info(f"Starting chunking for collection '{payload.collection_name}' with {len(json_files)} files...")
    
    for filename in json_files:
        try:
            file_path = os.path.join(collection_extracted_dir, filename)
            output_json_path = os.path.join(collection_chunked_dir, filename)
            logging.info(f"Processing file: {filename}")
            chunked_data = chunk_document(
                input_json_path=file_path,
                output_json_path=output_json_path,
                chosen_methods=payload.chosen_methods,
                identifier=payload.identifier,
                use_ai=payload.use_ai,
                prompt_description=payload.prompt_description,
                previous_pages_to_include=payload.previous_pages_to_include,
                context_items_to_show=payload.context_items_to_show,
                rewrite_query=payload.rewrite_query,
                chunk_size=payload.chunk_size,
                overlap=payload.chunk_overlap
            )
            
            # Save the chunked data to a JSON file
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(chunked_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Chunked text saved to: {output_json_path}")
            processed_files.append({
                "filename": filename,
                "output_path": output_json_path,
                "chunks_created": len(chunked_data) if isinstance(chunked_data, list) else 1
            })
            
        except Exception as e:
            error_msg = f"Error processing {filename}: {str(e)}"
            print(f"❌ {error_msg}")
            errors.append(error_msg)
    
    if not processed_files:
        raise HTTPException(status_code=500, detail=f"Failed to chunk any files in collection '{payload.collection_name}'. Errors: {'; '.join(errors)}")
    
    return {
        "message": f"Chunking completed for collection '{payload.collection_name}'",
        "collection_name": payload.collection_name,
        "processed_files": processed_files,
        "total_processed": len(processed_files),
        "errors": errors
    }

@app.post("/chat-with-pdf")
async def chat_with_pdf(payload: ChatWithPDFRequest):
    """
    Chat with a specific document (session collection) using additional collections as context.
    
    This is a generalized endpoint that allows users to:
    1. Upload a document to a unique session collection
    2. Ask questions about that document
    3. Use other collections as additional context for better answers
    
    Args:
        payload: ChatWithPDFRequest containing query, session_collection, context_collections, and threshold
    """
    try:
        # Combine session collection with context collections
        all_collections = [payload.session_collection] + payload.context_collections
        
        # Filter out any collections that don't exist
        valid_collections = []
        for collection_name in all_collections:
            collection_path = os.path.join("documents", "chunked_text", collection_name)
            if os.path.exists(collection_path) and os.listdir(collection_path):
                valid_collections.append(collection_name)
            else:
                logging.warning(f"Collection '{collection_name}' not found or empty, skipping")
        
        if not valid_collections:
            raise HTTPException(
                status_code=404, 
                detail=f"No valid collections found. Session collection '{payload.session_collection}' and context collections {payload.context_collections} are either missing or empty."
            )
        
        logging.info(f"Processing chat query with collections: {valid_collections}")
        
        # Use the specialized single PDF method with primary collection and context collections
        response = langgraph_agent.process_query_with_single_pdf(
            query=payload.query,
            primary_collection=payload.session_collection,
            context_collections=payload.context_collections,
            threshold=payload.threshold
        )
        
        return {
            "response": response.get("response", "No response generated"),
            "rest_of_response": response,
            "sources": response.get("sources", []),
            "session_collection": payload.session_collection,
            "context_collections": payload.context_collections,
            "valid_collections_used": valid_collections,
            "query": payload.query
        }
        
    except Exception as e:
        logging.error(f"Error in chat-with-pdf: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing chat query: {str(e)}")

def generate_stream(request: ChatWithPDFRequest) -> Generator[str, None, None]:
    try:
        print(f"📡 Starting stream generation...")
        
        # Validate collections by checking if they exist on disk
        valid_collections = []
        
        def collection_exists_on_disk(collection_name: str) -> bool:
            """Check if collection directory exists in storage_documents"""
            collection_path = os.path.join("documents", "storage_documents", collection_name)
            return os.path.exists(collection_path) and os.path.isdir(collection_path)
        
        # Check session collection
        if request.session_collection:
            if collection_exists_on_disk(request.session_collection):
                valid_collections.append(request.session_collection)
                print(f"✅ Valid session collection: {request.session_collection}")
                # Load into memory if not already loaded
                if request.session_collection not in collection_managers:
                    collection_managers[request.session_collection] = DynamicChromeManager(request.session_collection)
                    print(f"📥 Loaded session collection into memory: {request.session_collection}")
            else:
                print(f"❌ Invalid session collection (not found on disk): {request.session_collection}")
        
        # Check context collections
        if request.context_collections:
            for collection in request.context_collections:
                if collection_exists_on_disk(collection):
                    valid_collections.append(collection)
                    print(f"✅ Valid context collection: {collection}")
                    # Load into memory if not already loaded
                    if collection not in collection_managers:
                        collection_managers[collection] = DynamicChromeManager(collection)
                        print(f"📥 Loaded context collection into memory: {collection}")
                else:
                    print(f"❌ Invalid context collection (not found on disk): {collection}")
        
        if not valid_collections:
            error_msg = f"data: {json.dumps({'type': 'error', 'message': 'No valid collections found'})}\n\n"
            print(f"❌ No valid collections, sending: {error_msg}")
            yield error_msg
            return
        
        # Send initial status
        initial_status = f"data: {json.dumps({'type': 'status', 'message': 'Starting analysis...', 'timestamp': datetime.now().isoformat()})}\n\n"
        print(f"📤 Sending initial status: {initial_status.strip()}")
        yield initial_status
        
        # Send a test message to verify streaming is working
        test_message = f"data: {json.dumps({'type': 'status', 'message': 'TEST: Streaming connection established!', 'timestamp': datetime.now().isoformat()})}\n\n"
        print(f"📤 Sending test message: {test_message.strip()}")
        yield test_message
        
        # Create a streaming version of the LangGraph agent
        print(f"🔄 Starting streaming agent with collections: {valid_collections}")
        for update in langgraph_agent.process_query_with_single_pdf_stream(
            query=request.query,
            primary_collection=request.session_collection,
            context_collections=request.context_collections,
            threshold=request.threshold
        ):
            stream_data = f"data: {json.dumps(update)}\n\n"
            print(f"📤 Streaming update: {update.get('type', 'unknown')} - {update.get('message', '')[:100]}...")
            yield stream_data
            
    except Exception as e:
        logging.error(f"Error in streaming chat-with-pdf: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

@app.post("/chat-with-pdf-stream")
async def chat_with_pdf_stream(request: ChatWithPDFRequest):
    """Streaming version of chat-with-pdf that provides real-time updates"""
    
    print(f"🚀 STREAMING ENDPOINT CALLED: query='{request.query[:50]}...', session_collection='{request.session_collection}'")
    
    return StreamingResponse(
        generate_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@app.post("/step1-text-extraction") 
async def step1_text_extraction(
    collection_name: str, 
    contains_tables: bool = False, 
    contains_images_of_text: bool = False, 
    contains_images_of_nontext: bool = False
):
    """
    Extract text from all PDF files in a specific collection.
    
    Args:
        collection_name (str): Name of the collection to process.
        contains_tables (bool): Whether PDFs contain tables that should be extracted.
        contains_images_of_text (bool): Whether PDFs contain images with text that should be OCR'd.
        contains_images_of_nontext (bool): Whether PDFs contain non-text images.
    """
    # Define paths
    collection_storage_dir = os.path.join("documents", "storage_documents", collection_name)
    collection_extracted_dir = os.path.join("documents", "extracted_text", collection_name)
    
    # Check if collection storage directory exists
    if not os.path.exists(collection_storage_dir):
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found in storage documents")
    
    # Create extracted text directory for collection
    os.makedirs(collection_extracted_dir, exist_ok=True)
    
    # Get all PDF files in the collection
    pdf_files = [f for f in os.listdir(collection_storage_dir) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        raise HTTPException(status_code=404, detail=f"No PDF files found in collection '{collection_name}'")
    
    processed_files = []
    errors = []
    
    print(f"Starting text extraction for collection '{collection_name}' with {len(pdf_files)} files...")
    
    for filename in pdf_files:
        try:
            file_path = os.path.join(collection_storage_dir, filename)
            output_json_path = os.path.join(collection_extracted_dir, filename.replace(".pdf", ".json"))
            
            extracted_data = extract_pdf_text(
                pdf_file_path=file_path,
                output_path=output_json_path,
                contains_tables=contains_tables,
                contains_images_of_text=contains_images_of_text,
                contains_images_of_nontext=contains_images_of_nontext
            )
            
            # Save the extracted data to a JSON file
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, indent=2, ensure_ascii=False)
            
            print(f"Extracted text saved to: {output_json_path}")
            processed_files.append({
                "filename": filename,
                "output_path": output_json_path,
                "pages_extracted": len(extracted_data) if isinstance(extracted_data, list) else 1
            })
            
        except Exception as e:
            error_msg = f"Error processing {filename}: {str(e)}"
            print(f"❌ {error_msg}")
            errors.append(error_msg)
    
    if not processed_files:
        raise HTTPException(status_code=500, detail=f"Failed to extract text from any files in collection '{collection_name}'. Errors: {'; '.join(errors)}")
    
    return {
        "message": f"Text extraction completed for collection '{collection_name}'",
        "collection_name": collection_name,
        "processed_files": processed_files,
        "total_processed": len(processed_files),
        "errors": errors
    }



@app.post("/crawl-through-web")
async def crawl_through_web(
    payload: CrawlRequest
):
    try:
        # Save to src/documents/storage_documents
        stats = ai_crawler(
            start_url=  payload.start_url,
            extraction_prompt=payload.extraction_prompt,
            collection_name=payload.collection_name,
            null_is_okay=payload.null_is_okay
        )
        return {"message": f"Crawling completed successfully for {payload.collection_name} with {len(stats)} items created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading PDFs: {str(e)}")

@app.post("/upload-through-google-drive")
async def upload_through_google_drive(payload: DriveUploadRequest):
    try:
        # Save to src/documents/storage_documents
        download_path = os.path.join("documents", "storage_documents")
        stats = download_pdfs_from_drive(
            drive_url=payload.drive_url,
            download_path=download_path,
            recursive=payload.recursive
        )
        return {"downloaded": stats["downloaded"], "failed": stats["failed"], "folders_processed": stats["folders_processed"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading PDFs: {str(e)}")

    
@app.post("/create-collection")
async def create_collection(payload: CollectionRequest):
    collection_name = payload.collection_name

    if not collection_name or not collection_name.strip():
        raise HTTPException(status_code=400, detail="Collection name cannot be empty")
    
    sanitized_name = collection_name.strip().lower().replace(' ', '_')
    
    collection_storage_dir = os.path.join("./documents/storage_documents", sanitized_name)
    collection_extracted_dir = os.path.join("./documents/extracted_text", sanitized_name)
    collection_chunked_dir = os.path.join("./documents/chunked_text", sanitized_name)

    try:
        os.makedirs(collection_storage_dir, exist_ok=True)
        os.makedirs(collection_extracted_dir, exist_ok=True)
        os.makedirs(collection_chunked_dir, exist_ok=True)

        return {
            "message": f"Collection '{sanitized_name}' created successfully",
            "collection_name": sanitized_name,
            "directories_created": {
                "storage": collection_storage_dir,
                "extracted_text": collection_extracted_dir,
                "chunked_text": collection_chunked_dir
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create collection '{sanitized_name}': {str(e)}")



@app.post("/upload-pdf")
async def upload_pdf(
    collection_name: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """
    Uploads PDF files to a specific collection directory.

    Args:
        collection_name (str): Name of the collection to organize files under.
        files (List[UploadFile]): List of PDF files to upload.
    """
    # Create collection-specific directory structure
    collection_storage_dir = os.path.join("./documents/storage_documents", collection_name)
    
    # Ensure collection directory exists
    os.makedirs(collection_storage_dir, exist_ok=True)
    
    uploaded_files = []
    
    for file in files:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")
        
        file_location = os.path.join(collection_storage_dir, file.filename)
        
        try:
            # Write the file in chunks to handle potentially large files
            with open(file_location, "wb") as buffer:
                while contents := await file.read(1024 * 1024): # Read 1MB chunks
                    buffer.write(contents)
            
            print(f"Successfully uploaded {file.filename} to {file_location}")
            uploaded_files.append({
                "filename": file.filename,
                "path": file_location,
                "size": os.path.getsize(file_location)
            })
            
        except Exception as e:
            # Clean up the uploaded PDF if upload fails
            if os.path.exists(file_location):
                os.remove(file_location)
            # Convert exception to string representation to avoid binary encoding issues
            error_msg = str(e)
            raise HTTPException(status_code=500, detail=f"Could not upload file {file.filename}: {error_msg}")
    
    return {
        "message": f"Successfully uploaded {len(uploaded_files)} PDF file(s) to collection '{collection_name}'",
        "collection_name": collection_name,
        "uploaded_files": uploaded_files,
        "total_files": len(uploaded_files)
    }

@app.post("/extract-bill-links")
async def extract_bill_links(bill_name: str = Form(...), year: str = Form(...)):
    """
    Extracts document links for a given bill and year from the Hawaii Capitol website.
    """
    try:
        links = scrape_bill_page_links(bill_name, year)
        return {"links": links}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/reset")
async def reset_collections(collections: Optional[List[str]] = None):
    """Reset specified collections or all collections"""
    target_collections = collections or collection_names
    
    reset_results = {}
    
    for collection_name in target_collections:
        try:
            if collection_name in collection_managers:
                manager = collection_managers[collection_name]
                manager.reset_collection()
                reset_results[collection_name] = "success"
                print(f"✅ Reset collection: {collection_name}")
            else:
                reset_results[collection_name] = "collection not found"
        except Exception as e:
            reset_results[collection_name] = f"error: {str(e)}"
            print(f"❌ Error resetting {collection_name}: {e}")
        
        return {
        "message": f"Reset operation completed for collections: {list(target_collections)}",
        "results": reset_results
    }

# Debug endpoint for collection managers
@app.get("/debug/managers")
async def debug_managers():
    """Debug endpoint to check collection managers"""
    return {
        "config_collections": collection_names,
        "active_managers": list(collection_managers.keys()),
        "config": config
    }







# Ordered list of fiscal note JSON files
# fiscal_note_files = [
#     "HB400.json",
#     "HB400_HSCR286_.json",
#     "HB400_HD1_HSCR1171_.json",
#     "HB400_SD1_SSCR1253_.json",
#     "HB400_SD2_SSCR1841_.json",
#         "HB400_CD1_CCR157_.json"
# ]

# timeline_data = [
#     {'date': '1/16/2025', 'text': 'Pending introduction.', 'documents': []},
#     {'date': '1/17/2025', 'text': 'Introduced and Pass First Reading.', 'documents': ['HB400.json']},
#     {'date': '1/21/2025', 'text': 'Referred to JHA, FIN, referral sheet 1', 'documents': []},
#     {'date': '1/24/2025', 'text': 'Bill scheduled to be heard by JHA on Thursday, 01-30-25 2:00PM in House conference room 325 VIA VIDEOCONFERENCE.', 'documents': ['HB400_TESTIMONY_JHA_01-30-25_.json']},
#     {'date': '1/30/2025', 'text': 'The committee on JHA recommend that the measure be PASSED, UNAMENDED. The votes were as follows: 8 Ayes: Representative(s) Tarnas, Poepoe, Belatti, Kahaloa, Perruso, Takayama, Garcia, Shimizu; Ayes with reservations: none;  Noes: none; and 3 Excused: Representative(s) Cochran, Hashem, Todd.', 'documents': []},
#     {'date': '2/10/2025', 'text': 'Reported from JHA (Stand. Com. Rep. No. 286), recommending passage on Second Reading and referral to FIN.', 'documents': ['HB400_HSCR286_.json']},
#     {'date': '2/10/2025', 'text': 'Passed Second Reading and referred to the committee(s) on FIN with none voting aye with reservations; none voting no (0) and Representative(s) Belatti, Cochran, Kila, Ward excused (4).', 'documents': []},
#     {'date': '3/3/2025', 'text': 'Bill scheduled to be heard by FIN on Wednesday, 03-05-25 9:00AM in House conference room 308 VIA VIDEOCONFERENCE.', 'documents': ['HB400_TESTIMONY_FIN_03-05-25_.json']},
#     {'date': '3/5/2025', 'text': 'The committee on FIN recommend that the measure be PASSED, WITH AMENDMENTS. The votes were as follows: 14 Ayes: Representative(s) Yamashita, Takenouchi, Grandinetti, Holt, Keohokapu-Lee Loy, Kitagawa, Kusch, Lamosao, Lee, M., Miyake, Morikawa, Templo, Alcos, Reyes Oda; Ayes with reservations: none;  Noes: none; and 2 Excused: Representative(s) Hussey, Ward.', 'documents': []},
#     {'date': '3/10/2025', 'text': 'Reported from FIN (Stand. Com. Rep. No. 1171) as amended in HD 1, recommending passage on Third Reading.', 'documents': ['HB400_HD1.json', 'HB400_HD1_HSCR1171_.json']},
#     {'date': '3/10/2025', 'text': 'Forty-eight (48) hours notice Wednesday,  03-12-25.', 'documents': []},
#     {'date': '3/12/2025', 'text': 'Passed Third Reading as amended in HD 1 with none voting aye with reservations; none voting no (0) and Representative(s) Alcos, Cochran, Holt, Sayama, Ward excused (5).  Transmitted to Senate.', 'documents': []},
#     {'date': '3/13/2025', 'text': 'Received from House (Hse. Com. No. 382).', 'documents': []},
#     {'date': '3/13/2025', 'text': 'Passed First Reading.', 'documents': []},
#     {'date': '3/13/2025', 'text': 'Referred to JDC, WAM.', 'documents': []},
#     {'date': '3/14/2025', 'text': 'The committee(s) on JDC has scheduled a public hearing on 03-19-25 9:45AM; Conference Room 016 & Videoconference.', 'documents': ['HB400_HD1_TESTIMONY_JDC_03-19-25_.json']},
#     {'date': '3/19/2025', 'text': 'The committee(s) on  JDC recommend(s) that the measure be PASSED, WITH AMENDMENTS.  The votes in JDC were as follows: 4 Aye(s): Senator(s) Rhoads, Gabbard, San Buenaventura, Awa; Aye(s) with reservations: none ; 0 No(es): none; and 1 Excused: Senator(s) Chang.', 'documents': []},
#     {'date': '3/21/2025', 'text': 'Reported from JDC (Stand. Com. Rep. No. 1253) with recommendation of passage on Second Reading, as amended (SD 1) and referral to WAM.', 'documents': ['HB400_SD1.json', 'HB400_SD1_SSCR1253_.json']},
#     {'date': '3/21/2025', 'text': 'Report adopted; Passed Second Reading, as amended (SD 1) and referred to WAM.', 'documents': []},
#     {'date': '3/24/2025', 'text': 'The committee(s) on WAM will hold a public decision making on 03-31-25 10:01AM; Conference Room 211 & Videoconference.', 'documents': ['HB400_SD1_TESTIMONY_WAM_03-31-25_.json']},
#     {'date': '3/31/2025', 'text': 'The committee(s) on  WAM recommend(s) that the measure be PASSED, WITH AMENDMENTS.  The votes in WAM were as follows: 13 Aye(s): Senator(s) Dela Cruz, Moriwaki, Aquino, DeCoite, Elefante, Hashimoto, Inouye, Kanuha, Kidani, Kim, Lee, C., Wakai, Fevella; Aye(s) with reservations: none ; 0 No(es): none; and 0 Excused: none.', 'documents': []},
#     {'date': '4/4/2025', 'text': 'Reported from WAM (Stand. Com. Rep. No. 1841) with recommendation of passage on Third Reading, as amended (SD 2).', 'documents': ['HB400_SD2.json', 'HB400_SD2_SSCR1841_.json']},
#     {'date': '4/4/2025', 'text': '48 Hrs. Notice 04-08-25.', 'documents': []},
#     {'date': '4/8/2025', 'text': 'Report adopted; Passed Third Reading, as amended (SD  2). Ayes, 25; Aye(s) with reservations: none .  Noes, 0 (none). Excused, 0 (none).  Transmitted to House.', 'documents': []},
#     {'date': '4/8/2025', 'text': 'Returned from Senate (Sen. Com. No.  628) in amended form (SD 2).', 'documents': []},
#     {'date': '4/10/2025', 'text': 'House disagrees with Senate amendment (s).', 'documents': []},
#     {'date': '4/11/2025', 'text': 'Received notice of disagreement (Hse. Com. No. 704).', 'documents': []},
#     {'date': '4/14/2025', 'text': 'House Conferees Appointed: Tarnas, Yamashita Co-Chairs; Poepoe, Takenouchi, Garcia.', 'documents': []},
#     {'date': '4/15/2025', 'text': 'Senate Conferees Appointed: Rhoads Chair; Moriwaki Co-Chair; Awa.', 'documents': []},
#     {'date': '4/15/2025', 'text': 'Received notice of appointment of House conferees (Hse. Com. No. 732).', 'documents': []},
#     {'date': '4/15/2025', 'text': 'Received notice of Senate conferees (Sen. Com. No. 790).', 'documents': []},
#     {'date': '4/16/2025', 'text': 'Bill scheduled for Conference Committee Meeting on Thursday, 04-17-25 3:46PM in conference room 325.', 'documents': []},
#     {'date': '4/17/2025', 'text': 'Conference Committee Meeting will reconvene on Monday 04-21-25 2:05PM in conference room 325.', 'documents': []},
#     {'date': '4/21/2025', 'text': 'The Conference Committee recommends that the measure be Passed, with Amendments. The votes were as follows: 5 Ayes: Representative(s) Tarnas, Yamashita, Poepoe, Takenouchi, Garcia; Ayes with reservations: none; 0 Noes: none; and 0 Excused: none.', 'documents': []},
#     {'date': '4/21/2025', 'text': 'The Conference committee recommends that the measure be PASSED, WITH AMENDMENTS. The votes of the Senate Conference Managers were as follows: 2 Aye(s): Senator(s) Rhoads, Moriwaki; Aye(s) with reservations: none ; 0 No(es): none; and 1 Excused: Senator(s) Awa.', 'documents': []},
#     {'date': '4/21/2025', 'text': 'Conference Committee Meeting will reconvene on Monday, 04-21-25 at 5:10PM in Conference Room 309.', 'documents': []},
#     {'date': '4/25/2025', 'text': 'Reported from Conference Committee (Conf Com. Rep. No. 157) as amended in (CD 1).', 'documents': ['HB400_CD1.json', 'HB400_CD1_CCR157_.json']},
#     {'date': '4/25/2025', 'text': 'Forty-eight (48) hours notice Wednesday, 04-30-25.', 'documents': []},
#     {'date': '4/30/2025', 'text': 'Passed Final Reading, as amended (CD 1). Ayes, 25; Aye(s) with reservations: none . 0 No(es): none.  0 Excused: none.', 'documents': []},
#     {'date': '4/30/2025', 'text': 'Passed Final Reading as amended in CD 1 with none voting aye with reservations; none voting no (0) and Representative(s) Cochran, Pierick excused (2).', 'documents': []},
#     {'date': '5/1/2025', 'text': 'Received notice of Final Reading (Sen. Com. No. 888).', 'documents': []},
#     {'date': '5/1/2025', 'text': 'Transmitted to Governor.', 'documents': []},
#     {'date': '5/2/2025', 'text': 'Received notice of passage on Final Reading in House (Hse. Com. No. 821).', 'documents': []},
#     {'date': '6/26/2025', 'text': 'Act 227, on 06/26/2025 (Gov. Msg. No. 1329).', 'documents': []}
# ]

# Get the correct path to the fiscal notes directory
# The api.py file and fiscal_notes directory are both in src/

# For multi-worker setup, we need shared state
# Option 1: Redis (recommended)
try:
    import redis
    import os
    
    # Use Redis URL from environment or fallback to localhost
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    redis_client = redis.from_url(redis_url, decode_responses=True)
    
    # Test connection
    redis_client.ping()
    USE_REDIS = True
    print(f"✅ Redis connected for multi-worker job tracking at {redis_url}")
except Exception as e:
    print(f"⚠️  Redis not available: {e}")
    print("🔄 Falling back to in-memory jobs (single worker only)")
    USE_REDIS = False
    jobs = {}
fiscal_notes_dir = Path(__file__).parent /"fiscal_notes" / "generation"
fiscal_notes_dir_september = Path(__file__).parent /"fiscal_notes" /"generation" / "september_archive"

# Job management functions that work with both Redis and in-memory
def set_job_status(job_id: str, status: bool):
    """Set job status - works with Redis or in-memory"""
    if USE_REDIS:
        if status:
            redis_client.set(f"job:{job_id}", "true", ex=3600)  # Expire after 1 hour
        else:
            redis_client.delete(f"job:{job_id}")
    else:
        jobs[job_id] = status

def get_job_status(job_id: str) -> bool:
    """Get job status - works with Redis or in-memory"""
    if USE_REDIS:
        return redis_client.exists(f"job:{job_id}") > 0
    else:
        return job_id in jobs

def cleanup_job(job_id: str):
    """Clean up job status"""
    if USE_REDIS:
        redis_client.delete(f"job:{job_id}")
    else:
        jobs.pop(job_id, None)

def cleanup_selenium_temp_files():
    """Clean up temporary files in Selenium containers to prevent disk space issues"""
    try:
        import subprocess
        import os
        
        # Only run if we're in a Docker environment
        if os.environ.get('DOCKER_ENV'):
            print("🧹 Cleaning up Selenium temporary files...")
            
            # Get list of Selenium containers
            result = subprocess.run(['docker', 'ps', '--filter', 'name=selenium', '--format', '{{.Names}}'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                containers = result.stdout.strip().split('\n')
                containers = [c for c in containers if c]  # Remove empty strings
                
                for container in containers:
                    try:
                        # Clean up Chrome temp directories older than 1 hour
                        subprocess.run([
                            'docker', 'exec', container, 'find', '/tmp', 
                            '-name', '.org.chromium.*', '-type', 'd', 
                            '-mmin', '+60', '-exec', 'rm', '-rf', '{}', '+'], 
                            timeout=30, capture_output=True)
                        
                        # Clean up other temp files older than 1 hour
                        subprocess.run([
                            'docker', 'exec', container, 'find', '/tmp', 
                            '-type', 'f', '-mmin', '+60', '-name', 'tmp*', 
                            '-exec', 'rm', '-f', '{}', '+'], 
                            timeout=30, capture_output=True)
                        
                        print(f"✅ Cleaned temp files in {container}")
                    except Exception as e:
                        print(f"⚠️ Failed to clean {container}: {e}")
            else:
                print("⚠️ No Selenium containers found")
                
    except Exception as e:
        print(f"⚠️ Selenium cleanup failed: {e}")
        # Don't raise - this is non-critical

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._redis_listener_started = False
        if USE_REDIS:
            # Subscribe to Redis for cross-worker broadcasts
            self.pubsub = redis_client.pubsub()
            self.pubsub.subscribe('fiscal_note_updates')
            # Redis listener will be started when first connection is made

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Start Redis listener if not already started
        if USE_REDIS and not self._redis_listener_started:
            self._redis_listener_started = True
            asyncio.create_task(self._redis_listener())

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            print(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: str):
        # Broadcast to local connections
        await self._local_broadcast(message)
        
        # If using Redis, also publish to other workers
        if USE_REDIS:
            try:
                redis_client.publish('fiscal_note_updates', message)
            except Exception as e:
                print(f"Error publishing to Redis: {e}")

    async def _local_broadcast(self, message: str):
        """Broadcast to connections on this worker only"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)

    async def _redis_listener(self):
        """Listen for Redis messages from other workers"""
        if not USE_REDIS:
            return
            
        try:
            while True:
                message = self.pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'message':
                    # Broadcast Redis message to local connections
                    await self._local_broadcast(message['data'])
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Redis listener error: {e}")

manager = ConnectionManager()

class Bill_type_options(str, Enum):
    HB = "HB"
    SB = "SB"

class Year_options(str, Enum):
    YEAR_2025 = "2025"

@app.post("/delete_fiscal_note")
async def delete_fiscal_note(request: Request, bill_type: Bill_type_options, bill_number: str, year: Year_options = Year_options.YEAR_2025):
    bill_type = bill_type
    bill_number = bill_number
    year = year
    job_id = f"{bill_type.value}_{bill_number}_{year}"
    fiscal_notes_path = os.path.join(fiscal_notes_dir, f"{bill_type.value}_{bill_number}_{year.value}")
    print("Before checking if fiscal notes path exists", fiscal_notes_path)
    if os.path.exists(fiscal_notes_path):
        print(f"Fiscal notes path: {fiscal_notes_path}")
        shutil.rmtree(fiscal_notes_path)
        cleanup_job(job_id)
        return {
            "message": "Fiscal note generation deleted"
        }
    else:
        return {
            "message": "Fiscal note generation not found"
        }

@app.get("/get_fiscal_note_files_september")
async def get_fiscal_note_files_september():
    files = os.listdir(fiscal_notes_dir_september)
    dirs = []
    for file in files:
        if os.path.isdir(os.path.join(fiscal_notes_dir_september, file)) and not file.startswith('.') and not file.startswith("__"):
            print(f"Directory: {file}")
            # Check if this directory name matches any active job_id
            is_generating = get_job_status(file)
            print(f"Is generating: {is_generating} for {file}")
            if is_generating:
                dirs.append({"name": file, "status": "generating"})
            else:
                if os.path.exists(os.path.join(fiscal_notes_dir_september, file, "fiscal_notes")) and len(os.listdir(os.path.join(fiscal_notes_dir_september, file, "fiscal_notes"))) > 0:
                    dirs.append({"name": file, "status": "ready"})
                else:
                    dirs.append({"name": file, "status": "error"})
    return dirs

@app.get("/get_fiscal_note_files")
async def get_fiscal_note_files():
    files = os.listdir(fiscal_notes_dir)
    dirs = []
    for file in files:
        if os.path.isdir(os.path.join(fiscal_notes_dir, file)) and not file.startswith('.') and not file.startswith("__"):
            print(f"Directory: {file}")
            if file == "september_archive":
                continue
            # Check if this directory name matches any active job_id
            is_generating = get_job_status(file)
            print(f"Is generating: {is_generating} for {file}")
            if is_generating:
                dirs.append({"name": file, "status": "generating"})
            else:
                if os.path.exists(os.path.join(fiscal_notes_dir, file, "fiscal_notes")) and len(os.listdir(os.path.join(fiscal_notes_dir, file, "fiscal_notes"))) > 0:
                    dirs.append({"name": file, "status": "ready"})
                else:
                    dirs.append({"name": file, "status": "error"})
    return dirs

def process_fiscal_note_references(fiscal_note_data, document_mapping):
    """
    Process fiscal note data to replace filename references with numbered references and clickable links.
    """
    import re
    
    def get_document_info(doc_name):
        """
        Get document URL and type information based on document name.
        Returns tuple: (url, document_type, description)
        """
        base_url = "https://www.capitol.hawaii.gov/sessions/session2025"
        
        # Check document type based on filename patterns
        if "TESTIMONY" in doc_name.upper():
            url = f"{base_url}/Testimony/{doc_name}.PDF"
            return url, "Testimony", f"Public testimony document"
        elif doc_name.startswith(("HB", "SB")) and not any(pattern in doc_name.upper() for pattern in ["TESTIMONY", "HSCR", "CCR", "SSCR"]):
            # This is a bill version (original or amended)
            url = f"{base_url}/bills/{doc_name}_.HTM"
            if any(suffix in doc_name for suffix in ["_HD", "_SD", "_CD"]):
                return url, "Version of Bill", f"Amended version of the bill"
            else:
                return url, "Version of Bill", f"Original version of the bill"
        else:
            # Default fallback - assume committee report
            url = f"{base_url}/CommReports/{doc_name}.htm"
            return url, "Committee Report", f"Legislative committee report"
    
    def replace_filename_with_number(text):
        if not isinstance(text, str):
            return text
        
        # Pattern to match any content in parentheses that looks like a document reference
        pattern = r'\(([^)]+)\)'
        
        def replacement(match):
            content = match.group(1)
            
            # Look for the content in the document mapping (exact match first)
            for doc_name, doc_number in document_mapping.items():
                if doc_name == content:
                    url, doc_type, description = get_document_info(doc_name)
                    tooltip_content = f"<h1>{doc_type}</h1><div class='tooltip-body'>{doc_name}<br/><small>{description}</small></div>"
                    return f'<a href="{url}" target="_blank" class="doc-reference" data-tooltip-html="{tooltip_content}" title="{doc_type}: {doc_name}">[{doc_number}]</a>'
            
            # Try partial matches - check if content contains any document name
            for doc_name, doc_number in document_mapping.items():
                if doc_name in content or content in doc_name:
                    url, doc_type, description = get_document_info(doc_name)
                    tooltip_content = f"<h1>{doc_type}</h1><div class='tooltip-body'>{doc_name}<br/><small>{description}</small></div>"
                    return f'<a href="{url}" target="_blank" class="doc-reference" data-tooltip-html="{tooltip_content}" title="{doc_type}: {doc_name}">[{doc_number}]</a>'
            
            # If not found, return original
            return match.group(0)
        
        return re.sub(pattern, replacement, text)
    
    # Process all string values in the fiscal note data
    processed_data = {}
    for key, value in fiscal_note_data.items():
        if isinstance(value, str):
            processed_data[key] = replace_filename_with_number(value)
        elif isinstance(value, dict):
            processed_data[key] = process_fiscal_note_references(value, document_mapping)
        elif isinstance(value, list):
            processed_data[key] = [
                process_fiscal_note_references(item, document_mapping) if isinstance(item, dict)
                else replace_filename_with_number(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            processed_data[key] = value
    
    return processed_data

def process_fiscal_note_references_structured(fiscal_note_data, document_mapping, numbers_data=None, chunks_data=None, sentence_attributions=None, global_amount_to_citation=None, global_next_citation_number=None, fiscal_note_documents=None):
    """
    Process fiscal note data to replace document references with structured citation numbers.
    Now supports financial citations with numbers_data and chunk text mapping with chunks_data.
    Added fiscal_note_documents parameter to filter numbers by documents used in fiscal note.
    """
    import re
    import json
    
    # Use global citation mapping if provided, otherwise create local one
    if global_amount_to_citation is not None and global_next_citation_number is not None:
        amount_to_citation = global_amount_to_citation
        next_citation_number = global_next_citation_number
    else:
        amount_to_citation = {}
        next_citation_number = max(document_mapping.values()) + 1 if document_mapping else 1
    
    # Map citation numbers to specific financial amounts
    number_citation_map = {}
    
    def replace_financial_citations(text, sentence_context="", fiscal_note_documents=None):
        """
        Replace financial citations like $514,900 (filename) with $514,900 [5]
        Now filters by documents used in the fiscal note and uses TF-IDF for disambiguation.
        """
        if not isinstance(text, str):
            return text
        
        # Pattern to match financial amounts with parenthetical citations
        # Matches: $514,900 (filename.txt) or $557,000 (filename)
        # Also matches: $10,000 fine and/or up to five years imprisonment (filename)
        # Also matches: `$10,000` (filename) - with backticks
        pattern = r'`?\$([0-9,]+(?:\.[0-9]+)?)`?(?:\s+[^()]*?)?\s*\(([^)]+)\)'
        
        def replacement(match):
            nonlocal next_citation_number
            full_match = match.group(0)
            amount_str = match.group(1).replace(',', '')
            filename = match.group(2)
            
            # Extract the text between the dollar amount and the parentheses
            dollar_part = f"${match.group(1)}"
            citation_part = f"({filename})"
            middle_text = full_match.replace(dollar_part, "").replace(citation_part, "").strip()
            
            try:
                amount = float(amount_str)
                
                # STEP 1: Filter numbers_data by documents used in this fiscal note
                filtered_numbers = []
                if numbers_data and fiscal_note_documents:
                    # Normalize document names for matching
                    doc_bases = []
                    for doc in fiscal_note_documents:
                        # Remove common extensions
                        base = doc.replace('.txt', '').replace('.PDF', '').replace('.HTM', '').replace('_.', '')
                        doc_bases.append((doc, base))
                    
                    for item in numbers_data:
                        item_filename = item.get('filename', '')
                        # Check if this number's document is in the fiscal note's documents
                        for doc, base in doc_bases:
                            if base in item_filename or doc in item_filename:
                                filtered_numbers.append(item)
                                break
                elif numbers_data:
                    # Fallback: use all numbers if no filter provided
                    filtered_numbers = numbers_data
                
                # STEP 2: Find matching numbers by amount
                matching_items = []
                for item in filtered_numbers:
                    if abs(item.get('number', 0) - amount) < 0.01:  # Handle floating point precision
                        matching_items.append(item)
                
                # STEP 3: If multiple matches, use TF-IDF to find most similar
                matching_item = None
                if len(matching_items) > 1 and sentence_context:
                    # Use simple TF-IDF-like scoring
                    from sklearn.feature_extraction.text import TfidfVectorizer
                    from sklearn.metrics.pairwise import cosine_similarity
                    
                    try:
                        texts = [sentence_context] + [item.get('text', '') for item in matching_items]
                        vectorizer = TfidfVectorizer(stop_words='english')
                        tfidf_matrix = vectorizer.fit_transform(texts)
                        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
                        best_idx = similarities.argmax()
                        matching_item = matching_items[best_idx]
                    except:
                        # Fallback to first match if TF-IDF fails
                        matching_item = matching_items[0]
                elif len(matching_items) == 1:
                    matching_item = matching_items[0]
                elif len(matching_items) == 0:
                    matching_item = None
                
                # Find the document name for URL generation
                # Use longest match to avoid HB727_SD1 matching HB727
                base_filename = filename.replace('.txt', '').replace('.HTM', '').replace('.PDF', '')
                document_name = base_filename
                best_match = None
                best_match_length = 0
                for doc_name in document_mapping.keys():
                    if doc_name in base_filename and len(doc_name) > best_match_length:
                        best_match = doc_name
                        best_match_length = len(doc_name)
                if best_match:
                    document_name = best_match
                
                # Create a key for this amount and document combination
                amount_key = (amount, document_name)
                
                # Check if we already have a citation number for this amount
                if amount_key in amount_to_citation:
                    citation_num = amount_to_citation[amount_key]
                else:
                    # Create new citation number for this amount
                    citation_num = next_citation_number
                    next_citation_number += 1
                    amount_to_citation[amount_key] = citation_num
                
                # Store the citation mapping with specific amount data
                number_citation_map[citation_num] = {
                    'amount': amount,
                    'filename': filename,
                    'document_name': document_name,
                    'data': matching_item
                }
                
                # Format the amount with commas for display
                formatted_amount = f"{int(amount):,}" if amount == int(amount) else f"{amount:,.2f}".rstrip('0').rstrip('.')
                
                # Return the replacement text with unique citation marker, preserving middle text
                if middle_text:
                    return f"${formatted_amount} {middle_text} [{citation_num}]"
                else:
                    return f"${formatted_amount} [{citation_num}]"
            except ValueError:
                # If amount parsing fails, return original
                return match.group(0)
        
        return re.sub(pattern, replacement, text)
    
    # Create chunk text mapping for document citations using sentence attributions
    chunk_text_map = {}
    if chunks_data and sentence_attributions:
        # Create individual citation numbers for each chunk to show different tooltips
        # sentence_attributions is a dict with chunk_usage_stats, not a list
        if isinstance(sentence_attributions, dict):
            chunk_usage_stats = sentence_attributions.get('chunk_usage_stats', {})
        else:
            # If it's a list, we need to extract chunk usage from the list items
            chunk_usage_stats = {}
            if isinstance(sentence_attributions, list):
                for attribution in sentence_attributions:
                    if isinstance(attribution, dict):
                        chunk_id = attribution.get('attributed_chunk_id')
                        if chunk_id and isinstance(chunk_id, int):
                            if chunk_id not in chunk_usage_stats:
                                chunk_usage_stats[str(chunk_id)] = {
                                    'usage_count': 0,
                                    'document_name': None
                                }
                            chunk_usage_stats[str(chunk_id)]['usage_count'] += 1
                            
                            # Find document name for this chunk
                            for chunk in chunks_data:
                                if chunk['chunk_id'] == chunk_id:
                                    chunk_usage_stats[str(chunk_id)]['document_name'] = chunk['document_name']
                                    break
        
        # Find chunks that were actually used by the LLM
        used_chunks = []
        for chunk_id, stats in chunk_usage_stats.items():
            if isinstance(stats, dict) and stats.get('usage_count', 0) > 0:
                try:
                    chunk_id_int = int(chunk_id)
                    # Find the chunk data
                    chunk_data = None
                    for chunk in chunks_data:
                        if chunk['chunk_id'] == chunk_id_int:
                            chunk_data = chunk
                            break
                    
                    if chunk_data:
                        used_chunks.append({
                            'chunk_id': chunk_id_int,
                            'usage_count': stats['usage_count'],
                            'chunk_data': chunk_data,
                            'document_name': chunk_data['document_name']
                        })
                except (ValueError, KeyError):
                    continue
        
        # Sort by usage count (most used first)
        used_chunks.sort(key=lambda x: x['usage_count'], reverse=True)
        
        # Create chunk_text_map based on actual LLM chunk references from sentence_attributions
        # Each citation occurrence should map to the specific chunk the LLM referenced
        
        # Process sentence_attributions to get LLM's actual chunk references
        if isinstance(sentence_attributions, list):
            citation_occurrence_map = {}  # Maps citation_number to list of specific chunks in order
            
            for attribution in sentence_attributions:
                if isinstance(attribution, dict):
                    chunk_id = attribution.get('attributed_chunk_id')
                    if chunk_id and isinstance(chunk_id, int):
                        # Find the chunk data
                        for chunk in chunks_data:
                            if chunk['chunk_id'] == chunk_id:
                                doc_name = chunk['document_name']
                                citation_number = document_mapping.get(doc_name, 1)
                                
                                # Add this specific chunk to the citation's list
                                if citation_number not in citation_occurrence_map:
                                    citation_occurrence_map[citation_number] = []
                                
                                citation_occurrence_map[citation_number].append({
                                    "chunk_text": chunk['chunk_text'],
                                    "attribution_score": 1.0,
                                    "attribution_method": "llm_reference",
                                    "sentence": attribution.get('sentence', ''),
                                    "chunk_id": chunk_id,
                                    "llm_reference": True
                                })
                                break
            
            # Update chunk_text_map with the LLM's specific chunk references
            chunk_text_map.update(citation_occurrence_map)
        
        # Individual citation logic above handles all chunk text mapping
    
    # End of chunk text mapping logic
    
    def replace_filename_with_structured_reference(text, field_name=""):
        # Find which document this chunk belongs to
        chunk_info = next((c for c in chunks_data if c['chunk_id'] == attributed_chunk_id), None)
        if chunk_info:
            chunk_doc_name = chunk_info.get('document_name', '')
            # Try to match chunk document name to document mapping
            # Prioritize exact matches, then longest partial matches
            best_match = None
            best_match_length = 0
            
            for doc_name, doc_num in document_mapping.items():
                if chunk_doc_name == doc_name:
                    # Exact match - use this immediately
                    best_match = (doc_name, doc_num)
                    break
                elif (chunk_doc_name.startswith(doc_name) or doc_name.startswith(chunk_doc_name)):
                    # Partial match - keep track of longest match
                    match_length = len(doc_name) if chunk_doc_name.startswith(doc_name) else len(chunk_doc_name)
                    if match_length > best_match_length:
                        best_match = (doc_name, doc_num)
                        best_match_length = match_length
            
            if best_match:
                doc_name, doc_num = best_match
                chunk_text_map[doc_num].append({
                    'chunk_text': chunk_text,
                    'attribution_score': attribution.get('attribution_score', 0.0),
                    'attribution_method': attribution.get('attribution_method', 'unknown'),
                    'sentence': sentence[:100] + '...' if len(sentence) > 100 else sentence
                })
        else:
            # Process explicit document citations in the sentence
            for match in matches:
                # Find the document mapping number for this citation
                # Prioritize exact matches, then longest partial matches
                best_match = None
                best_match_length = 0
                
                for doc_name, doc_num in document_mapping.items():
                    if match == doc_name:
                        # Exact match - use this immediately
                        best_match = (doc_name, doc_num)
                        break
                    elif (match.startswith(doc_name) or doc_name.startswith(match)):
                        # Partial match - keep track of longest match
                        match_length = len(doc_name) if match.startswith(doc_name) else len(match)
                        if match_length > best_match_length:
                            best_match = (doc_name, doc_num)
                            best_match_length = match_length
                
                if best_match:
                    doc_name, doc_num = best_match
                    chunk_text_map[doc_num].append({
                        'chunk_text': chunk_text,
                        'attribution_score': attribution.get('attribution_score', 0.0),
                        'attribution_method': attribution.get('attribution_method', 'unknown'),
                        'sentence': sentence[:100] + '...' if len(sentence) > 100 else sentence
                    })
        
        # Debug: Print detailed chunk text mapping analysis
        print(f"📊 Chunk text mapping analysis for fiscal note:")
        print(f"   - Chunks data available: {len(chunks_data) if chunks_data else 0}")
        print(f"   - Sentence attributions available: {len(sentence_attributions) if sentence_attributions else 0}")
        
        if sentence_attributions:
            print(f"   - Sample sentence attribution:")
            sample_attr = sentence_attributions[0] if sentence_attributions else {}
            print(f"     Sentence: {sample_attr.get('sentence', '')[:100]}...")
            print(f"     Chunk ID: {sample_attr.get('attributed_chunk_id', 'N/A')}")
            print(f"     Method: {sample_attr.get('attribution_method', 'N/A')}")
        
        print(f"📊 Chunk text mapping created:")
        for doc_num, chunks in chunk_text_map.items():
            doc_name = next((name for name, num in document_mapping.items() if num == doc_num), f"Document {doc_num}")
            print(f"  [{doc_num}] {doc_name}: {len(chunks)} chunks")
            for i, chunk in enumerate(chunks[:1]):  # Show first chunk
                print(f"    {i+1}. Score: {chunk['attribution_score']:.3f}, Method: {chunk['attribution_method']}")
                print(f"       Text: {chunk['chunk_text'][:60]}...")
    
    def replace_filename_with_structured_reference(text, field_name=""):
        if not isinstance(text, str):
            return text
        
        # Pattern to match any content in parentheses that looks like a document reference
        pattern = r'\(([^)]+)\)'
        
        def replacement(match):
            content = match.group(1)
            
            # Skip single-digit citations - these are list items, not document references
            if content.isdigit() and len(content) <= 2:
                return match.group(0)  # Return original (1), (2), etc.
            
            # Skip single letters - these are also likely list items
            if len(content) == 1 and content.isalpha():
                return match.group(0)  # Return original (a), (b), etc.
            
            # CRITICAL FIX: Skip parenthetical content that immediately follows financial amounts
            # This prevents financial citations from being converted to document citations
            start_pos = match.start()
            if start_pos > 0:
                # Look backwards to see if this parenthesis follows a financial amount
                preceding_text = text[:start_pos].strip()
                # Check if the preceding text ends with a dollar amount (with optional text in between)
                financial_pattern = r'\$[0-9,]+(?:\.[0-9]+)?\s*(?:[^$()]*)?$'
                if re.search(financial_pattern, preceding_text):
                    return match.group(0)  # Keep original - this is part of a financial citation
            
            # Look for the content in the document mapping (exact match first)
            for doc_name, doc_number in document_mapping.items():
                if doc_name == content:
                    # Return simple [number] citation format instead of DOCREF
                    return f'[{doc_number}]'
            
            # Try partial matches - find the LONGEST/MOST SPECIFIC match
            best_match = None
            best_match_length = 0
            
            for doc_name, doc_number in document_mapping.items():
                # Check if document name is contained in the citation content
                if doc_name in content:
                    # Prioritize longer matches (more specific)
                    if len(doc_name) > best_match_length:
                        best_match = (doc_name, doc_number)
                        best_match_length = len(doc_name)
                # Also check reverse (citation content in document name) but with lower priority
                elif content in doc_name and len(content) > best_match_length:
                    best_match = (doc_name, doc_number)
                    best_match_length = len(content)
            
            if best_match:
                doc_name, doc_number = best_match
                return f'[{doc_number}]'
            
            # If not found, return original
            return match.group(0)
        
        return re.sub(pattern, replacement, text)
    
    def replace_square_bracket_citations(text):
        """
        Clean up LLM-generated square bracket markers.
        - [CHUNK_36, NUMBER_0] -> [doc_citation] (convert chunk to document citation)
        - [CHUNK_61, NUMBER_3, NUMBER_4] -> [doc_citation] (remove numbers, keep chunk->doc)
        - [filename.txt] -> [citation_number] (convert filename citations)
        - [5] -> keep as-is (already proper citation numbers)
        """
        if not isinstance(text, str):
            return text
        
        # Step 1: Convert [CHUNK_X, NUMBER_Y, ...] to document citations
        # Extract chunk ID and convert to document citation, removing NUMBER parts
        def replace_chunk_citation(match):
            full_match = match.group(0)
            # Extract the chunk number from CHUNK_X
            chunk_match = re.search(r'CHUNK_(\d+)', full_match)
            if not chunk_match:
                return full_match
            
            chunk_id = int(chunk_match.group(1))
            
            # Find the chunk in chunks_data to get its document
            chunk_info = next((c for c in chunks_data if c.get('chunk_id') == chunk_id), None)
            if chunk_info:
                doc_name = chunk_info.get('document_name')
                # Look up document citation number
                if doc_name in document_mapping:
                    doc_citation = document_mapping[doc_name]
                    return f' [{doc_citation}]'
            
            # If we can't find it, remove it
            return ''
        
        text = re.sub(r'\s*\[CHUNK_\d+(?:,\s*NUMBER_\d+)+\]', replace_chunk_citation, text)
        
        # Step 2: Replace [filename.txt] with [citation_number]
        # Only process brackets that contain filenames (have .txt, .HTM, .PDF, etc.)
        pattern = r'\[([^\]]*\.(?:txt|HTM|htm|PDF)[^\]]*)\]'
        
        def replacement(match):
            content = match.group(1).strip()
            
            # Try to find this filename in document mapping
            # First try exact match
            for doc_name, doc_number in document_mapping.items():
                if doc_name in content or content in doc_name:
                    return f'[{doc_number}]'
            
            # If not found, return original
            return match.group(0)
        
        return re.sub(pattern, replacement, text)
    
    # Process all string values in the fiscal note data
    # Function to replace document citations with individual citation numbers
    def replace_document_citations_with_individual(text):
        """Keep same citation numbers but populate chunk_text_map with multiple chunks per citation."""
        # Don't modify the text, just return it as-is
        # The chunk assignment happens in the chunk_text_map creation above
        return text
    
    processed_data = {}
    # fiscal_note_documents is now passed as a parameter
    # If not provided, extract from metadata in the data (for backward compatibility)
    if fiscal_note_documents is None:
        if isinstance(fiscal_note_data, dict) and '_fiscal_note_metadata' in fiscal_note_data:
            metadata = fiscal_note_data.get('_fiscal_note_metadata', {})
            fiscal_note_documents = metadata.get('new_documents_processed', [])
        else:
            fiscal_note_documents = []
    
    for key, value in fiscal_note_data.items():
        if isinstance(value, str):
            # Processing order:
            # 1. Replace financial citations: $amount (filename) -> $amount [citation]
            # 2. Replace square bracket citations: [filename] -> [citation], remove [CHUNK_X, NUMBER_Y]
            # 3. Replace parentheses citations: (filename) -> [citation]
            processed_value = replace_financial_citations(value, sentence_context=value, fiscal_note_documents=fiscal_note_documents)
            processed_value = replace_square_bracket_citations(processed_value)
            processed_value = replace_document_citations_with_individual(processed_value)
            processed_data[key] = replace_filename_with_structured_reference(processed_value, key)
        elif isinstance(value, dict):
            # Pass fiscal_note_documents as parameter to recursive call
            processed_data[key] = process_fiscal_note_references_structured(value, document_mapping, numbers_data, chunks_data, sentence_attributions, global_amount_to_citation, global_next_citation_number, fiscal_note_documents)
        elif isinstance(value, list):
            processed_items = []
            for item in value:
                if isinstance(item, dict):
                    # Pass fiscal_note_documents as parameter to recursive call
                    processed_items.append(process_fiscal_note_references_structured(item, document_mapping, numbers_data, chunks_data, sentence_attributions, global_amount_to_citation, global_next_citation_number, fiscal_note_documents))
                elif isinstance(item, str):
                    processed_item = replace_financial_citations(item, sentence_context=item, fiscal_note_documents=fiscal_note_documents)
                    processed_item = replace_square_bracket_citations(processed_item)
                    processed_items.append(replace_filename_with_structured_reference(processed_item, key))
                else:
                    processed_items.append(item)
            processed_data[key] = processed_items
        else:
            processed_data[key] = value
    
    # Add the number citation mapping to the processed data
    processed_data['_number_citation_map'] = number_citation_map
    processed_data['_chunk_text_map'] = chunk_text_map
    processed_data['_updated_next_citation_number'] = next_citation_number
    
    return processed_data

@app.post("/get_fiscal_note_september")
async def get_fiscal_note_september(request: Request, bill_type: Bill_type_options, bill_number: str, year: Year_options = Year_options.YEAR_2025):
    bill_type = bill_type
    bill_number = bill_number
    year = year

    job_id = f"{bill_type.value}_{bill_number}_{year}"
    if get_job_status(job_id):
        return {
            "message": "Fiscal note generation already in progress"
        }

    chronological_path = os.path.join(fiscal_notes_dir_september, f"{bill_type.value}_{bill_number}_{year.value}", f"{bill_type.value}_{bill_number}_{year.value}_chronological.json")
    try:
        fiscal_notes_path = os.path.join(fiscal_notes_dir_september, f"{bill_type.value}_{bill_number}_{year.value}", "fiscal_notes")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fiscal Note Not Found")

    timeline_path = os.path.join(fiscal_notes_dir_september, f"{bill_type.value}_{bill_number}_{year.value}", f"{bill_type.value}_{bill_number}_{year.value}_timeline.json")
    # get jsons in fiscal_notes_path
    fiscal_notes = []

    with open(chronological_path, 'r') as f:
        print(f"Chronological path: {chronological_path}")
        chronological = json.load(f)
        files = os.listdir(fiscal_notes_path)
        
        
        for file in chronological:
            print(f"File: {file['name'] + '.json'}")
            if file['name'] + '.json' in files: 
                print(f"File found: {file['name'] + '.json'}")
                with open(os.path.join(fiscal_notes_path, file['name'] + '.json'), 'r') as f:
                    fiscal_note_data = json.load(f)
                    
                    fiscal_notes.append({
                        'filename': file['name'],
                        'data': fiscal_note_data
                    })

    with open(timeline_path, 'r') as f:
        timeline = json.load(f)


    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "fiscal_notes": fiscal_notes,
            "timeline": timeline,
            "document_mapping": {}
        }
    )

@app.post("/get_fiscal_note")
async def get_fiscal_note(request: Request, bill_type: Bill_type_options, bill_number: str, year: Year_options = Year_options.YEAR_2025):
    bill_type = bill_type
    bill_number = bill_number
    year = year

    job_id = f"{bill_type.value}_{bill_number}_{year}"
    if get_job_status(job_id):
        return {
            "message": "Fiscal note generation already in progress"
        }

    chronological_path = os.path.join(fiscal_notes_dir, f"{bill_type.value}_{bill_number}_{year.value}", f"{bill_type.value}_{bill_number}_{year.value}_chronological.json")
    try:
        # Try to load enhanced fiscal notes with chunks first, fall back to regular fiscal notes
        fiscal_notes_with_chunks_path = os.path.join(fiscal_notes_dir, f"{bill_type.value}_{bill_number}_{year.value}", "fiscal_notes_with_chunks")
        fiscal_notes_path = os.path.join(fiscal_notes_dir, f"{bill_type.value}_{bill_number}_{year.value}", "fiscal_notes")
        
        if os.path.exists(fiscal_notes_with_chunks_path):
            fiscal_notes_path = fiscal_notes_with_chunks_path
            print(f"Using enhanced fiscal notes with chunks: {fiscal_notes_path}")
        else:
            print(f"Using regular fiscal notes: {fiscal_notes_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fiscal Note Not Found")

    timeline_path = os.path.join(fiscal_notes_dir, f"{bill_type.value}_{bill_number}_{year.value}", f"{bill_type.value}_{bill_number}_{year.value}_timeline.json")
    
    # get jsons in fiscal_notes_path
    fiscal_notes = []
    
    # Create or load document mapping: filename -> number
    base_dir = os.path.dirname(chronological_path)
    mapping_file = os.path.join(base_dir, "document_mapping.json")
    
    # Try to load existing mapping
    document_mapping = {}
    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, 'r') as f:
                document_mapping = json.load(f)
            print(f"Loaded existing document mapping with {len(document_mapping)} documents")
        except Exception as e:
            print(f"Error loading document mapping: {e}")

    with open(chronological_path, 'r') as f:
        print(f"Chronological path: {chronological_path}")
        chronological = json.load(f)
        files = os.listdir(fiscal_notes_path)
        
        # Create mapping of document names to numbers (if not already loaded)
        if not document_mapping:
            for index, file in enumerate(chronological, 1):
                document_mapping[file['name']] = index
            
            # Save the mapping for future use
            try:
                with open(mapping_file, 'w') as f:
                    json.dump(document_mapping, f, indent=2)
                print(f"Saved document mapping to {mapping_file}")
            except Exception as e:
                print(f"Error saving document mapping: {e}")
        
        for file in chronological:
            print(f"File: {file['name'] + '.json'}")
            if file['name'] + '.json' in files: 
                print(f"File found: {file['name'] + '.json'}")
                with open(os.path.join(fiscal_notes_path, file['name'] + '.json'), 'r') as f:
                    fiscal_note_data = json.load(f)
                    
                    # Process fiscal note data to replace filenames with numbered references
                    processed_data = process_fiscal_note_references(fiscal_note_data, document_mapping)
                    
                    fiscal_notes.append({
                        'filename': file['name'],
                        'data': processed_data
                    })

    with open(timeline_path, 'r') as f:
        timeline = json.load(f)


    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "fiscal_notes": fiscal_notes,
            "timeline": timeline,
            "document_mapping": document_mapping
        }
    )

@app.post("/get_fiscal_note_data")
async def get_fiscal_note_data(bill_type: Bill_type_options, bill_number: str, year: Year_options = Year_options.YEAR_2025):
    """
    New endpoint that returns structured JSON data for React frontend
    """
    bill_type = bill_type
    bill_number = bill_number
    year = year

    job_id = f"{bill_type.value}_{bill_number}_{year.value}"
    if get_job_status(job_id):
        return {
            "message": "Fiscal note generation already in progress",
            "status": "generating"
        }

    chronological_path = os.path.join(fiscal_notes_dir, f"{bill_type.value}_{bill_number}_{year.value}", f"{bill_type.value}_{bill_number}_{year.value}_chronological.json")
    try:
        # Try to load enhanced fiscal notes with chunks first, fall back to regular fiscal notes
        fiscal_notes_with_chunks_path = os.path.join(fiscal_notes_dir, f"{bill_type.value}_{bill_number}_{year.value}", "fiscal_notes_with_chunks")
        fiscal_notes_path = os.path.join(fiscal_notes_dir, f"{bill_type.value}_{bill_number}_{year.value}", "fiscal_notes")
        
        if os.path.exists(fiscal_notes_with_chunks_path):
            fiscal_notes_path = fiscal_notes_with_chunks_path
            print(f"Using enhanced fiscal notes with chunks: {fiscal_notes_path}")
        else:
            print(f"Using regular fiscal notes: {fiscal_notes_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fiscal Note Not Found")

    timeline_path = os.path.join(fiscal_notes_dir, f"{bill_type.value}_{bill_number}_{year.value}", f"{bill_type.value}_{bill_number}_{year.value}_timeline.json")
    
    # get jsons in fiscal_notes_path
    fiscal_notes = []
    
    # Create or load document mapping: filename -> number
    base_dir = os.path.dirname(chronological_path)
    mapping_file = os.path.join(base_dir, "document_mapping.json")
    
    # Try to load existing mapping
    document_mapping = {}
    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, 'r') as f:
                document_mapping = json.load(f)
            print(f"Loaded existing document mapping with {len(document_mapping)} documents")
        except Exception as e:
            print(f"Error loading document mapping: {e}")

    with open(chronological_path, 'r') as f:
        print(f"Chronological path: {chronological_path}")
        chronological = json.load(f)
        files = os.listdir(fiscal_notes_path)
        
        # Create mapping of document names to numbers (if not already loaded)
        if not document_mapping:
            for index, file in enumerate(chronological, 1):
                document_mapping[file['name']] = index
            
            # Save the mapping for future use
            try:
                with open(mapping_file, 'w') as f:
                    json.dump(document_mapping, f, indent=2)
                print(f"Saved document mapping to {mapping_file}")
            except Exception as e:
                print(f"Error saving document mapping: {e}")
        
        # Create enhanced document mapping with type information
        enhanced_document_mapping = {}
        for doc_name, doc_number in document_mapping.items():
            doc_type = classify_document_type(doc_name)
            enhanced_document_mapping[doc_number] = {
                "name": doc_name,
                "type": doc_type,
                "description": get_document_type_description(doc_type),
                "icon": get_document_type_icon(doc_type)
            }
        
        # Collect all numbers_data from metadata files
        all_numbers_data = []
        all_number_citation_maps = {}
        all_chunk_text_maps = {}
        all_sentence_chunk_mappings = []  # NEW: Collect sentence-to-chunk mappings
        
        # Create a global citation map to ensure consistent numbering across fiscal notes
        global_amount_to_citation = {}  # Maps (amount, document_name) -> citation_number
        global_next_citation_number = max(document_mapping.values()) + 1 if document_mapping else 1
        
        for file in chronological:
            print(f"File: {file['name'] + '.json'}")
            if file['name'] + '.json' in files: 
                print(f"File found: {file['name'] + '.json'}")
                with open(os.path.join(fiscal_notes_path, file['name'] + '.json'), 'r') as f:
                    fiscal_note_data = json.load(f)
                    
                    # Try to load corresponding metadata file for numbers_data and chunks
                    metadata_file = os.path.join(fiscal_notes_path, file['name'] + '_metadata.json')
                    numbers_data = []
                    chunks_data = []
                    sentence_attributions = []
                    sentence_chunk_mapping = []  # NEW: Load sentence-chunk mappings
                    new_documents_processed = []  # NEW: Documents used for this fiscal note
                    strikethroughs = []  # Legacy: Load strikethroughs
                    annotations = []  # NEW: Load annotations
                    enhanced_numbers = None  # NEW: Load enhanced numbers
                    if os.path.exists(metadata_file):
                        try:
                            with open(metadata_file, 'r') as meta_f:
                                metadata = json.load(meta_f)
                                numbers_data = metadata.get('response_metadata', {}).get('numbers_data', [])
                                chunks_metadata = metadata.get('response_metadata', {}).get('chunks_metadata', {})
                                chunks_data = chunks_metadata.get('chunk_details', [])
                                sentence_attribution_analysis = metadata.get('response_metadata', {}).get('sentence_attribution_analysis', {})
                                sentence_attributions = sentence_attribution_analysis.get('sentence_attributions', [])
                                # NEW: Load sentence-to-chunk mapping
                                sentence_chunk_mapping = metadata.get('response_metadata', {}).get('sentence_chunk_mapping', [])
                                # NEW: Load list of documents used for this fiscal note
                                new_documents_processed = metadata.get('new_documents_processed', [])
                                # NEW: Load annotations (preferred) or migrate from strikethroughs (legacy)
                                annotations = metadata.get('annotations', [])
                                strikethroughs = metadata.get('strikethroughs', [])
                                # NEW: Load enhanced numbers
                                enhanced_numbers = metadata.get('enhanced_numbers')
                                
                                # Migration: If no annotations but strikethroughs exist, convert them
                                if not annotations and strikethroughs:
                                    annotations = []
                                    for st in strikethroughs:
                                        ann = st.copy() if isinstance(st, dict) else st
                                        # Add type field if not present (default to strikethrough)
                                        if isinstance(ann, dict) and 'type' not in ann:
                                            ann['type'] = 'strikethrough'
                                        annotations.append(ann)
                                    print(f"Migrated {len(strikethroughs)} legacy strikethroughs to annotations for {file['name']}")
                                
                                print(f"Loaded {len(numbers_data)} numbers, {len(chunks_data)} chunks, {len(sentence_attributions)} sentence attributions, {len(sentence_chunk_mapping)} sentence-chunk mappings, {len(new_documents_processed)} documents, {len(annotations)} annotations from metadata for {file['name']}")
                        except Exception as e:
                            print(f"Error loading metadata for {file['name']}: {e}")
                    
                    # Add numbers_data and sentence mappings to the global collection
                    all_numbers_data.extend(numbers_data)
                    
                    # NEW: Add sentence-chunk mappings with fiscal note context
                    for mapping in sentence_chunk_mapping:
                        all_sentence_chunk_mappings.append({
                            'fiscal_note': file['name'],
                            'section': mapping.get('section'),
                            'sentence': mapping.get('sentence'),
                            'chunks': mapping.get('chunks', [])
                        })
                    
                    # Process fiscal note data with structured references, numbers, and chunks
                    # Pass new_documents_processed as parameter for filtering
                    processed_data = process_fiscal_note_references_structured(
                        fiscal_note_data, document_mapping, numbers_data, chunks_data, sentence_attributions,
                        global_amount_to_citation, global_next_citation_number, new_documents_processed
                    )
                    
                    # Extract and store number citation map and chunk text map
                    number_citation_map = processed_data.pop('_number_citation_map', {})
                    chunk_text_map = processed_data.pop('_chunk_text_map', {})
                    updated_next_citation_number = processed_data.pop('_updated_next_citation_number', global_next_citation_number)
                    
                    # Update global citation number for next iteration
                    global_next_citation_number = updated_next_citation_number
                    
                    all_number_citation_maps.update(number_citation_map)
                    
                    # NEW: Use sentence-chunk mappings to build chunk_text_map
                    # This provides the most accurate sentence-to-chunk association
                    for mapping in sentence_chunk_mapping:
                        sentence = mapping.get('sentence', '')
                        chunks = mapping.get('chunks', [])
                        
                        for chunk_info in chunks:
                            citation_num = chunk_info.get('citation_number')
                            chunk_text = chunk_info.get('chunk_text', '')
                            chunk_id = chunk_info.get('chunk_id')
                            doc_name = chunk_info.get('document_name', '')
                            
                            if citation_num:
                                if citation_num not in all_chunk_text_maps:
                                    all_chunk_text_maps[citation_num] = []
                                
                                # Add chunk with sentence context
                                all_chunk_text_maps[citation_num].append({
                                    'chunk_text': chunk_text,
                                    'attribution_score': 1.0,
                                    'attribution_method': 'sentence_chunk_mapping',
                                    'sentence': sentence,  # Include the sentence that uses this chunk
                                    'chunk_id': chunk_id,
                                    'document_name': doc_name
                                })
                    
                    # Fallback: Use chunk mapping from metadata if no sentence mappings
                    if not sentence_chunk_mapping:
                        chunk_mapping = metadata.get('chunk_mapping', {})
                        if not chunk_mapping or file['name'] not in chunk_mapping:
                            # Try to load chunk mapping from file
                            chunk_mapping_file = os.path.join(fiscal_notes_path, f"{file['name']}_chunk_mapping.json")
                            if os.path.exists(chunk_mapping_file):
                                try:
                                    with open(chunk_mapping_file, 'r') as f:
                                        chunk_file_data = json.load(f)
                                        chunk_mapping = {chunk_file_data['fiscal_note_name']: chunk_file_data['chunks']}
                                except Exception as e:
                                    print(f"Error loading chunk mapping file {chunk_mapping_file}: {e}")
                        
                        if chunk_mapping and file['name'] in chunk_mapping:
                            fiscal_note_chunks = chunk_mapping[file['name']]
                            for chunk in fiscal_note_chunks:
                                chunk_num = chunk['chunk_number']
                                chunk_text = chunk['chunk_text']
                                
                                # Add to all_chunk_text_maps
                                if chunk_num not in all_chunk_text_maps:
                                    all_chunk_text_maps[chunk_num] = []
                                
                                all_chunk_text_maps[chunk_num].append({
                                    'chunk_text': chunk_text,
                                    'attribution_score': 1.0,
                                    'attribution_method': 'chunk_mapping',
                                    'sentence': '',
                                    'chunk_id': chunk_num
                                })
                        else:
                            # Final fallback to chunk_text_map from processing
                            for citation_num, chunks in chunk_text_map.items():
                                if citation_num in all_chunk_text_maps:
                                    # Add new chunks to existing ones (avoid duplicates)
                                    existing_chunks = all_chunk_text_maps[citation_num]
                                    for chunk in chunks:
                                        # Check if this chunk already exists (by text content)
                                        chunk_text = chunk.get('chunk_text', '')
                                        if not any(existing.get('chunk_text', '') == chunk_text for existing in existing_chunks):
                                            existing_chunks.append(chunk)
                                else:
                                    # New citation number, add all chunks
                                    all_chunk_text_maps[citation_num] = chunks
                    
                    # Filter out chunk reference properties for frontend display
                    filtered_data = {k: v for k, v in processed_data.items() if not k.endswith('_chunk_references')}
                    
                    fiscal_note_item = {
                        'filename': file['name'],
                        'data': processed_data,
                        'new_documents_processed': new_documents_processed,  # NEW: Include documents used
                        'strikethroughs': strikethroughs,  # Legacy: Include strikethroughs for backward compatibility
                        'annotations': annotations  # NEW: Include annotations (strikethrough + underline)
                    }
                    
                    # Add enhanced_numbers if available
                    if enhanced_numbers:
                        fiscal_note_item['enhanced_numbers'] = enhanced_numbers
                    
                    fiscal_notes.append(fiscal_note_item)

    # Load chronological tracking data if available
    tracking_summary_file = os.path.join(base_dir, f"{job_id}_number_changes_summary.json")
    tracking_file = os.path.join(base_dir, f"{job_id}_chronological_tracking.json")
    
    print(f"🔍 Looking for tracking files:")
    print(f"   base_dir: {base_dir}")
    print(f"   job_id: {job_id}")
    print(f"   Summary file: {tracking_summary_file}")
    print(f"   Summary exists: {os.path.exists(tracking_summary_file)}")
    print(f"   Tracking file: {tracking_file}")
    print(f"   Tracking exists: {os.path.exists(tracking_file)}")
    
    chronological_tracking = None
    has_tracking = False
    
    # Prefer summary file (frontend-optimized), fall back to full tracking
    if os.path.exists(tracking_summary_file):
        try:
            with open(tracking_summary_file, 'r') as f:
                chronological_tracking = json.load(f)
            has_tracking = True
            print(f"✅ Loaded chronological tracking summary: {tracking_summary_file}")
        except Exception as e:
            print(f"⚠️  Error loading tracking summary: {e}")
    elif os.path.exists(tracking_file):
        try:
            with open(tracking_file, 'r') as f:
                chronological_tracking = json.load(f)
            has_tracking = True
            print(f"✅ Loaded chronological tracking: {tracking_file}")
        except Exception as e:
            print(f"⚠️  Error loading tracking file: {e}")
    else:
        print(f"ℹ️  No chronological tracking data found for {job_id}")
        print(f"   Checked: {tracking_summary_file}")
        print(f"   Checked: {tracking_file}")
    
    # Map tracking segments to fiscal notes by matching document names
    if has_tracking and chronological_tracking:
        tracking_segments = chronological_tracking.get('segments', [])
        
        print(f"📊 Tracking segments: {len(tracking_segments)} total")
        print(f"📋 Fiscal notes: {len(fiscal_notes)}")
        
        # Helper function to find matching segment for a fiscal note
        def find_matching_segment(fiscal_note_filename, segments):
            """Find segment that contains a document matching the fiscal note filename."""
            # Try to match by checking if any segment document is a prefix of the fiscal note
            # Use longest match to avoid matching "HB1483" when "HB1483_HD1" is available
            best_match = None
            best_match_length = 0
            
            for segment in segments:
                for doc in segment.get('documents', []):
                    # Check if document name is a prefix of fiscal note filename
                    # e.g., "HB1483_HD1" matches "HB1483_HD1_HSCR983_"
                    if fiscal_note_filename.startswith(doc):
                        # Use longest matching document to avoid false positives
                        if len(doc) > best_match_length:
                            best_match = segment
                            best_match_length = len(doc)
            
            return best_match
        
        last_segment = None  # Track the most recent segment for carry-forward
        
        for idx, fiscal_note in enumerate(fiscal_notes):
            fiscal_note_name = fiscal_note['filename']
            
            # Try to find exact match by document name
            matching_segment = find_matching_segment(fiscal_note_name, tracking_segments)
            
            if matching_segment:
                # Direct match found
                fiscal_note['number_tracking'] = {
                    'segment_id': matching_segment.get('segment_id'),
                    'segment_name': matching_segment.get('segment_name'),
                    'documents': matching_segment.get('documents', []),
                    'ends_with_committee_report': matching_segment.get('ends_with_committee_report', False),
                    'counts': matching_segment.get('counts', {}),
                    'numbers': matching_segment.get('numbers', []),
                    'is_carried_forward': False
                }
                last_segment = matching_segment
                print(f"✅ Matched segment {matching_segment.get('segment_id')} to fiscal note {idx}: {fiscal_note_name}")
                print(f"   Segment documents: {matching_segment.get('documents', [])}")
                print(f"   Numbers count: {len(matching_segment.get('numbers', []))}")
            elif last_segment:
                # No match - carry forward from most recent segment
                fiscal_note['number_tracking'] = {
                    'segment_id': last_segment.get('segment_id'),
                    'segment_name': last_segment.get('segment_name'),
                    'documents': last_segment.get('documents', []),
                    'ends_with_committee_report': last_segment.get('ends_with_committee_report', False),
                    'counts': last_segment.get('counts', {}),
                    'numbers': last_segment.get('numbers', []),
                    'is_carried_forward': True,
                    'carried_forward_from': last_segment.get('segment_id')
                }
                print(f"🔄 Carried forward segment {last_segment.get('segment_id')} to fiscal note {idx}: {fiscal_note_name}")
                print(f"   (No matching segment found, using previous segment's data)")
            else:
                # No match and no previous segment
                print(f"⚠️  No tracking segment found for fiscal note {idx}: {fiscal_note_name}")
                print(f"   (This is the first fiscal note with no matching segment)")

    with open(timeline_path, 'r') as f:
        timeline = json.load(f)

        return {
            "status": "ready",
            "fiscal_notes": fiscal_notes,
            "timeline": timeline,
            "document_mapping": document_mapping,
            "enhanced_document_mapping": enhanced_document_mapping,
            "numbers_data": all_numbers_data,
            "number_citation_map": all_number_citation_maps,
            "chunk_text_map": all_chunk_text_maps,
            "sentence_chunk_mappings": all_sentence_chunk_mappings,
            "chronological_tracking": chronological_tracking,  # NEW: Full tracking data
            "has_tracking": has_tracking  # NEW: Flag indicating if tracking is available
        }

async def create_fiscal_note_job(bill_type: Bill_type_options, bill_number: str, year: str):
    job_id = f"{bill_type.value}_{bill_number}_{year}"
    try:
        print(f"Starting fiscal note generation for {job_id}")
        
        base_url = "https://www.capitol.hawaii.gov/session/measure_indiv.aspx"
        measure_url = f"{base_url}?billtype={bill_type.value}&billnumber={bill_number}&year={year}"
        
        # Send progress update
        await manager.broadcast(json.dumps({
            "type": "job_progress",
            "job_id": job_id,
            "status": "fetching_documents",
            "message": "Fetching documents from Hawaii Capitol website..."
        }))
        print("Entering fetch_documents")
        
        saved_path = fetch_documents(measure_url)

        print("Exiting fetch_documents")

        await manager.broadcast(json.dumps({
            "type": "job_progress",
            "job_id": job_id,
            "status": "reordering_documents",
            "message": "Reordering documents chronologically..."
        }))
        
        chronological_path = reorder_documents(saved_path)
        documents_path = retrieve_documents(chronological_path)
        
        await manager.broadcast(json.dumps({
            "type": "job_progress",
            "job_id": job_id,
            "status": "extracting_numbers",
            "message": "Extracting financial numbers and context..."
        }))
        
        base_dir = os.path.dirname(documents_path)
        numbers_file_path = os.path.join(base_dir, f"{bill_type.value}_{bill_number}_{year}_numbers.json")
        extract_number_context(documents_path, numbers_file_path)
        
        await manager.broadcast(json.dumps({
            "type": "job_progress",
            "job_id": job_id,
            "status": "generating_fiscal_notes",
            "message": "Generating fiscal note content..."
        }))
        
        fiscal_notes_path = generate_fiscal_notes(documents_path, numbers_file_path)
        
        # Step 6: Enhance numbers with RAG agent (optional, non-blocking)
        if ENABLE_STEP6_ENHANCE_NUMBERS:
            await manager.broadcast(json.dumps({
                "type": "job_progress",
                "job_id": job_id,
                "status": "enhancing_numbers",
                "message": "Enhancing numbers with RAG agent..."
            }))
            
            try:
                enhanced_numbers_path = enhance_numbers_for_bill(base_dir)
                if enhanced_numbers_path:
                    print(f"✅ Step 6 completed: {enhanced_numbers_path}")
                else:
                    print(f"⚠️  Step 6 skipped or failed (non-critical)")
            except Exception as e:
                print(f"⚠️  Step 6 error (non-critical): {e}")
        else:
            print(f"⏭️  Step 6 (Enhance Numbers) is disabled - skipping")
        
        # Step 7: Track chronological changes (optional, non-blocking)
        if ENABLE_STEP7_TRACK_CHRONOLOGICAL:
            await manager.broadcast(json.dumps({
                "type": "job_progress",
                "job_id": job_id,
                "status": "tracking_changes",
                "message": "Tracking chronological number changes..."
            }))
            
            try:
                tracking_result = track_chronological_changes(base_dir)
                if tracking_result:
                    print(f"✅ Step 7 completed:")
                    print(f"   - {tracking_result.get('tracking_file')}")
                    print(f"   - {tracking_result.get('summary_file')}")
                else:
                    print(f"⚠️  Step 7 skipped or failed (non-critical)")
            except Exception as e:
                print(f"⚠️  Step 7 error (non-critical): {e}")
        else:
            print(f"⏭️  Step 7 (Track Chronological Changes) is disabled - skipping")
        
        # Send completion notification
        await manager.broadcast(json.dumps({
            "type": "job_completed",
            "job_id": job_id,
            "status": "ready",
            "message": f"Fiscal note for {job_id} has been generated successfully!"
        }))
        
        print(f"Fiscal note generation completed for {job_id}")
        send_success_msg_to_slack(f"Fiscal note for {job_id} has been generated successfully!")
        
        # Clean up Selenium temp files to prevent disk space issues
        cleanup_selenium_temp_files()
        
    except Exception as e:
        error_msg = f"Error in fiscal note generation job {job_id}: {str(e)}"
        print(f"❌ {error_msg}")
        
        # Clean up job immediately on error
        cleanup_job(job_id)
        print(f"🧹 Cleaned up failed job: {job_id}")
        
        send_error_to_slack(error_msg)

        # Send error notification
        await manager.broadcast(json.dumps({
            "type": "job_error",
            "job_id": job_id,
            "status": "error",
            "message": f"Failed to generate fiscal note for {job_id}: {str(e)}"
        }))
        
        # Re-raise the exception to ensure it's properly logged
        raise
    finally:
        # Ensure cleanup happens regardless (defensive programming)
        cleanup_job(job_id)
        print(f"🧹 Final cleanup for job: {job_id}")

@app.post("/generate-fiscal-note")
async def generate_fiscal_note(request: Request, bill_type: Bill_type_options, bill_number: str, year: str = "2025"):
    bill_type = bill_type
    bill_number = bill_number
    year = year

    job_id = f"{bill_type.value}_{bill_number}_{year}"
    if get_job_status(job_id):
        return {
            "message": "Fiscal note generation already in progress",
            "success": False
        }
    
    # Check concurrent job limit
    if USE_REDIS:
        # Count active jobs in Redis
        active_jobs = len([key for key in redis_client.scan_iter(match="job:*")])
    else:
        # Count active jobs in memory
        active_jobs = len(jobs)
    
    MAX_CONCURRENT_FISCAL_NOTES = 10  # Allow 4 concurrent jobs across workers
    if active_jobs >= MAX_CONCURRENT_FISCAL_NOTES:
        return {
            "message": f"Only {MAX_CONCURRENT_FISCAL_NOTES} fiscal notes can be generated at the same time. Currently {active_jobs} jobs are running. Please try again later.",
            "success": False
        }
    
    set_job_status(job_id, True)
    
    try:
        # Create independent background task with error handling
        task = asyncio.create_task(create_fiscal_note_job(bill_type, bill_number, year))
        # Add done callback to handle any unhandled exceptions and ensure cleanup
        def handle_task_completion(task):
            if task.exception():
                print(f"❌ Unhandled exception in fiscal note job {job_id}: {task.exception()}")
                cleanup_job(job_id)
                print(f"🧹 Emergency cleanup for job: {job_id}")
        
        task.add_done_callback(handle_task_completion)

        return {
            "message": "Fiscal note queued for generation",
            "job_id": job_id,
            "success": True
        }
    except Exception as e:
        # If task creation fails, clean up immediately
        cleanup_job(job_id)
        print(f"❌ Failed to create fiscal note task for {job_id}: {e}")
        return {
            "message": f"Failed to queue fiscal note generation: {str(e)}",
            "job_id": job_id,
            "success": False
        }

@app.post("/bill_search_query")
async def bill_search_query(request: Request, bill_type: Bill_type_options, bill_number: str, year: str = "2025"):
    bill_type = bill_type
    bill_number = bill_number
    year = year
    bill_name = f"{bill_type.value}{bill_number}_"

    tfidf_results, vector_results = bill_similarity_searcher.search_similar_bills(bill_name)
    print(tfidf_results)
    print(vector_results)
    return {
        "tfidf_results": tfidf_results,
        "vector_results": vector_results
    }


@app.post("/get_similar_bills")
async def get_bill_summary(request: Request, bill_type: Bill_type_options, bill_number: str, year: str = "2025"):
    bill_type = bill_type
    bill_number = bill_number
    year = year
    bill_name = f"{bill_type.value}{bill_number}_"

    tfidf_results, vector_results, search_bill = bill_similarity_searcher.search_similar_bills(bill_name)
    print(tfidf_results)
    print(vector_results)
    print(search_bill)
    return {
        "tfidf_results": tfidf_results,
        "vector_results": vector_results,
        "search_bill": search_bill
    }


@app.post("/ask_llm")
async def ask_llm(request: LLMRequest):
    try:
        print(f"Received question: {request.question[:100]}...")
        response = model.generate_content(request.question)
        print(f"Generated response: {response}")
        with open("log.txt", "a") as f:
            f.write(f"Question: {request.question}\n")
            f.write(f"Response: {response.text}\n")
        return {
            "question": request.question,
            "response": response.text
        }
    except Exception as e:
        print(f"Error generating LLM response: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate LLM response: {str(e)}")

@app.post("/api/fiscal-notes/save-strikethroughs")
async def save_strikethroughs(request: Request):
    """
    Save annotations (strikethroughs and underlines) for a specific fiscal note to its metadata file.
    Supports both legacy 'strikethroughs' and new 'annotations' format.
    """
    try:
        data = await request.json()
        filename = data.get('filename')
        # Support both legacy 'strikethroughs' and new 'annotations' format
        strikethroughs = data.get('strikethroughs', [])
        annotations = data.get('annotations', [])
        bill_type = data.get('bill_type')
        bill_number = data.get('bill_number')
        year = data.get('year', '2025')
        
        if not filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        
        # Use annotations if provided, otherwise use strikethroughs (backward compatibility)
        if annotations:
            print(f"💾 Saving {len(annotations)} annotations for {filename}")
        else:
            print(f"💾 Saving {len(strikethroughs)} strikethroughs (legacy) for {filename}")
            # Convert legacy strikethroughs to annotations format
            annotations = []
            for st in strikethroughs:
                ann = st.copy()
                # Add type field if not present (default to strikethrough)
                if 'type' not in ann:
                    ann['type'] = 'strikethrough'
                annotations.append(ann)
        
        # If bill info not provided, try to extract from URL context or use defaults
        if not bill_type or not bill_number:
            # Try to parse from filename if it contains underscores
            parts = filename.split('_')
            if len(parts) >= 3:
                bill_type = parts[0]
                bill_number = parts[1]
                year = parts[2]
                print(f"   Parsed from filename: bill_type={bill_type}, bill_number={bill_number}, year={year}")
            else:
                raise HTTPException(status_code=400, detail=f"Bill information required. Please provide bill_type, bill_number, and year")
        
        print(f"   Using: bill_type={bill_type}, bill_number={bill_number}, year={year}")
        
        # Construct path to fiscal notes directory
        bill_dir = f"{bill_type}_{bill_number}_{year}"
        
        # Try enhanced fiscal notes first, fall back to regular
        fiscal_notes_with_chunks_path = os.path.join(fiscal_notes_dir, bill_dir, "fiscal_notes_with_chunks")
        fiscal_notes_path = os.path.join(fiscal_notes_dir, bill_dir, "fiscal_notes")
        
        if os.path.exists(fiscal_notes_with_chunks_path):
            target_dir = fiscal_notes_with_chunks_path
        elif os.path.exists(fiscal_notes_path):
            target_dir = fiscal_notes_path
        else:
            raise HTTPException(status_code=404, detail=f"Fiscal notes directory not found for {bill_dir}")
        
        # Path to metadata file
        metadata_file = os.path.join(target_dir, f"{filename}_metadata.json")
        
        # Load existing metadata or create new
        metadata = {}
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                print(f"📂 Loaded existing metadata from {metadata_file}")
            except Exception as e:
                print(f"⚠️ Error loading metadata, creating new: {e}")
        
        # Update both annotations (new) and strikethroughs (legacy) in metadata
        metadata['annotations'] = annotations
        metadata['annotations_updated_at'] = datetime.now().isoformat()
        # Keep strikethroughs for backward compatibility
        metadata['strikethroughs'] = strikethroughs if strikethroughs else annotations
        metadata['strikethroughs_updated_at'] = datetime.now().isoformat()
        
        # Save metadata
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✅ Saved annotations to {metadata_file}")
        
        return {
            "success": True,
            "message": f"Saved {len(annotations)} annotations",
            "filename": filename,
            "metadata_file": metadata_file,
            "annotation_count": len(annotations)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error saving strikethroughs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save strikethroughs: {str(e)}")

# Property Prompts Management - Helper Functions
def get_prompts_config_file():
    """Get path to property prompts config file"""
    return Path(__file__).parent / "fiscal_notes" / "property_prompts_config.json"

def migrate_old_config_to_templates():
    """Migrate old single-prompt config to new template structure"""
    from fiscal_notes.generation.step5_fiscal_note_gen import PROPERTY_PROMPTS
    from datetime import datetime
    
    config_file = get_prompts_config_file()
    
    if not config_file.exists():
        # No config exists, create default
        return {
            "templates": [
                {
                    "id": "default",
                    "name": "Default",
                    "is_default": True,
                    "created_at": datetime.now().isoformat(),
                    "prompts": PROPERTY_PROMPTS
                }
            ],
            "active_template_id": "default"
        }
    
    with open(config_file, 'r') as f:
        old_config = json.load(f)
    
    # Check if already migrated
    if "templates" in old_config:
        return old_config
    
    # Old format - migrate
    print("🔄 Migrating old property prompts config to template format...")
    
    new_config = {
        "templates": [
            {
                "id": "default",
                "name": "Default",
                "is_default": True,
                "created_at": datetime.now().isoformat(),
                "prompts": PROPERTY_PROMPTS
            }
        ],
        "active_template_id": "default"
    }
    
    # If old config was custom (different from default), preserve it
    if old_config != PROPERTY_PROMPTS:
        new_config["templates"].append({
            "id": "custom_migrated",
            "name": "Custom Template",
            "is_default": False,
            "created_at": datetime.now().isoformat(),
            "prompts": old_config
        })
        new_config["active_template_id"] = "custom_migrated"
        print("✅ Migrated custom prompts to 'Custom Template'")
    
    # Save migrated config
    with open(config_file, 'w') as f:
        json.dump(new_config, f, indent=2, ensure_ascii=False)
    
    print("✅ Migration complete")
    return new_config

def load_templates_config():
    """Load templates config, migrating if necessary"""
    config = migrate_old_config_to_templates()
    return config

def save_templates_config(config):
    """Save templates config to file"""
    config_file = get_prompts_config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

# Property Prompts Management Endpoints
@app.get("/api/property-prompts")
async def get_property_prompts():
    """
    Get all property prompt templates and active template ID.
    Automatically migrates old config format if needed.
    """
    try:
        config = load_templates_config()
        return {
            "templates": config.get("templates", []),
            "active_template_id": config.get("active_template_id", "default")
        }
    except Exception as e:
        print(f"❌ Error loading property prompts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load property prompts: {str(e)}")

@app.post("/api/property-prompts/template")
async def create_template(request: Request):
    """
    Create a new template by copying an existing one.
    """
    try:
        from datetime import datetime
        import time
        
        data = await request.json()
        source_template_id = data.get('source_template_id')
        name = data.get('name', 'New Template')
        
        if not source_template_id:
            raise HTTPException(status_code=400, detail="source_template_id is required")
        
        config = load_templates_config()
        
        # Find source template
        source_template = None
        for template in config['templates']:
            if template['id'] == source_template_id:
                source_template = template
                break
        
        if not source_template:
            raise HTTPException(status_code=404, detail=f"Source template '{source_template_id}' not found")
        
        # Create new template
        new_template = {
            "id": f"custom_{int(time.time())}",
            "name": name,
            "is_default": False,
            "created_at": datetime.now().isoformat(),
            "prompts": source_template['prompts'].copy()
        }
        
        config['templates'].append(new_template)
        save_templates_config(config)
        
        print(f"✅ Created new template: {new_template['name']} (ID: {new_template['id']})")
        
        return {
            "success": True,
            "template": new_template,
            "message": f"Created template '{name}'"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating template: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")

@app.put("/api/property-prompts/template/{template_id}")
async def update_template(template_id: str, request: Request):
    """
    Update an existing template's name and/or prompts.
    """
    try:
        data = await request.json()
        name = data.get('name')
        prompts = data.get('prompts')
        
        config = load_templates_config()
        
        # Find template
        template = None
        for t in config['templates']:
            if t['id'] == template_id:
                template = t
                break
        
        if not template:
            raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
        
        # Cannot modify default template name
        if template['is_default'] and name and name != "Default":
            raise HTTPException(status_code=400, detail="Cannot rename default template")
        
        # Update fields
        if name:
            template['name'] = name
        
        if prompts:
            # Validate prompts structure
            if not isinstance(prompts, dict):
                raise HTTPException(status_code=400, detail="Invalid prompts structure")
            
            for section_key, section_data in prompts.items():
                if not isinstance(section_data, dict):
                    raise HTTPException(status_code=400, detail=f"Section '{section_key}' must be an object")
                if 'prompt' not in section_data or 'description' not in section_data:
                    raise HTTPException(status_code=400, detail=f"Section '{section_key}' missing required fields")
            
            template['prompts'] = prompts
        
        save_templates_config(config)
        
        print(f"✅ Updated template: {template['name']} (ID: {template_id})")
        
        return {
            "success": True,
            "template": template,
            "message": f"Updated template '{template['name']}'"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating template: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update template: {str(e)}")

@app.delete("/api/property-prompts/template/{template_id}")
async def delete_template(template_id: str):
    """
    Delete a template. Cannot delete default or active template.
    """
    try:
        config = load_templates_config()
        
        # Find template
        template = None
        template_index = None
        for i, t in enumerate(config['templates']):
            if t['id'] == template_id:
                template = t
                template_index = i
                break
        
        if not template:
            raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
        
        # Cannot delete default template
        if template['is_default']:
            raise HTTPException(status_code=400, detail="Cannot delete default template")
        
        # Cannot delete active template
        if config['active_template_id'] == template_id:
            raise HTTPException(status_code=400, detail="Cannot delete active template. Switch to another template first.")
        
        # Delete template
        config['templates'].pop(template_index)
        save_templates_config(config)
        
        print(f"✅ Deleted template: {template['name']} (ID: {template_id})")
        
        return {
            "success": True,
            "message": f"Deleted template '{template['name']}'"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting template: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")

@app.put("/api/property-prompts/active")
async def set_active_template(request: Request):
    """
    Set the active template for fiscal note generation.
    """
    try:
        data = await request.json()
        template_id = data.get('template_id')
        
        if not template_id:
            raise HTTPException(status_code=400, detail="template_id is required")
        
        config = load_templates_config()
        
        # Verify template exists
        template_exists = any(t['id'] == template_id for t in config['templates'])
        if not template_exists:
            raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
        
        config['active_template_id'] = template_id
        save_templates_config(config)
        
        print(f"✅ Set active template to: {template_id}")
        
        return {
            "success": True,
            "active_template_id": template_id,
            "message": f"Active template set to '{template_id}'"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error setting active template: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set active template: {str(e)}")

@app.post("/api/property-prompts/reset")
async def reset_property_prompts():
    """
    Reset property prompts to defaults by removing custom config file.
    """
    try:
        from fiscal_notes.generation.step5_fiscal_note_gen import PROPERTY_PROMPTS
        
        custom_prompts_file = Path(__file__).parent / "fiscal_notes" / "property_prompts_config.json"
        
        if custom_prompts_file.exists():
            custom_prompts_file.unlink()
            print(f"✅ Deleted custom property prompts file")
        
        return {
            "success": True,
            "message": "Reset to default property prompts",
            "prompts": PROPERTY_PROMPTS,
            "is_custom": False
        }
    except Exception as e:
        print(f"❌ Error resetting property prompts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset property prompts: {str(e)}")

@app.get("/api/fiscal-note-property-prompts")
async def get_fiscal_note_property_prompts(
    bill_type: Bill_type_options,
    bill_number: str,
    fiscal_note_name: str,
    year: Year_options = Year_options.YEAR_2025
):
    """
    Get the property prompts that were used to generate a specific fiscal note.
    Returns the prompts from the fiscal note's metadata.
    """
    try:
        bill_dir = f"{bill_type.value}_{bill_number}_{year.value}"
        
        # Try both fiscal_notes_with_chunks and fiscal_notes directories
        fiscal_notes_with_chunks_path = os.path.join(fiscal_notes_dir, bill_dir, "fiscal_notes_with_chunks")
        fiscal_notes_path = os.path.join(fiscal_notes_dir, bill_dir, "fiscal_notes")
        
        target_dir = None
        if os.path.exists(fiscal_notes_with_chunks_path):
            target_dir = fiscal_notes_with_chunks_path
        elif os.path.exists(fiscal_notes_path):
            target_dir = fiscal_notes_path
        else:
            raise HTTPException(status_code=404, detail=f"Fiscal notes directory not found for {bill_dir}")
        print(fiscal_note_name)
        # Path to metadata file
        metadata_file = os.path.join(target_dir, f"{fiscal_note_name.split('_')[0] + fiscal_note_name.split('_')[1]}_metadata.json")
        
        if not os.path.exists(metadata_file):
            raise HTTPException(status_code=404, detail=f"Metadata file not found for {fiscal_note_name}")
        
        # Load metadata
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        # Get property prompts from metadata
        property_prompts = metadata.get('response_metadata', None).get('property_prompts_used', None)
        
        # Load default prompts for comparison
        from fiscal_notes.generation.step5_fiscal_note_gen import PROPERTY_PROMPTS
        
        if property_prompts is None:
            # If not stored in metadata, return default prompts
            return {
                "prompts": PROPERTY_PROMPTS,
                "is_stored": False,
                "custom_prompts_used": False,
                "message": "Property prompts not stored in metadata, returning defaults"
            }
        
        # Check if the stored prompts are different from defaults
        custom_prompts_used = property_prompts != PROPERTY_PROMPTS
        
        return {
            "prompts": property_prompts,
            "is_stored": True,
            "custom_prompts_used": custom_prompts_used
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error loading fiscal note property prompts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load fiscal note property prompts: {str(e)}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print(f"🔌 WebSocket connection attempt from {websocket.client}")
    await manager.connect(websocket)
    print(f"✅ WebSocket connected. Total connections: {len(manager.active_connections)}")
    try:
        while True:
            # Keep the connection alive and handle any incoming messages
            data = await websocket.receive_text()
            print(f"📨 Received WebSocket message: {data}")
            # You can handle client messages here if needed
    except WebSocketDisconnect:
        print(f"🔌 WebSocket disconnected from {websocket.client}")
        manager.disconnect(websocket)
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        manager.disconnect(websocket)

