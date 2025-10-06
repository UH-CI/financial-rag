from fastapi import FastAPI, HTTPException, Query, Form, File, UploadFile, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List, Dict, Any, Optional, Union
import os
from pathlib import Path
import json
import google.generativeai as genai
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

import shutil
from enum import Enum
import requests


from app_types.requests import (
    CollectionRequest, SearchRequest, QueryRequest,
    ChunkingRequest, DocumentResponse, CrawlRequest,
    UploadPDFRequest, ChatWithPDFRequest, DriveUploadRequest,
    CollectionStatistics, CollectionsStatsResponse, LLMRequest
)

from documents.step0_document_upload.google_upload import download_pdfs_from_drive
from documents.step1_text_extraction.pdf_text_extractor import extract_pdf_text
from documents.step2_chunking.chunker import chunk_document
from documents.step0_document_upload.web_scraper import scrape_bill_page_links


from settings import Settings
from documents.embeddings import DynamicChromeManager
from query_processor import QueryProcessor
from langgraph_agent import LangGraphRAGAgent
from chatbot_engine.nlp_backend import NLPBackend

from bill_data.bill_similarity_search import BillSimilaritySearcher

# Load configuration
def load_config() -> Dict[str, Any]:
    """Load configuration from config.json"""
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, 'r') as f:
        return json.load(f)

config = load_config()

# Initialize FastAPI app with config
app = FastAPI(
    title=config["api"]["title"],
    description=config["api"]["description"],
    version=config["api"]["version"]
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


@app.get("/collections/stats", response_model=CollectionsStatsResponse)
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

@app.post("/search", response_model=List[DocumentResponse])
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
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    # Test connection
    redis_client.ping()
    USE_REDIS = True
    print("✅ Redis connected for multi-worker job tracking")
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

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        if USE_REDIS:
            # Subscribe to Redis for cross-worker broadcasts
            self.pubsub = redis_client.pubsub()
            self.pubsub.subscribe('fiscal_note_updates')
            # Start Redis listener in background
            asyncio.create_task(self._redis_listener())

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

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
        fiscal_notes_path = os.path.join(fiscal_notes_dir, f"{bill_type.value}_{bill_number}_{year.value}", "fiscal_notes")
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
        
        # Send completion notification
        await manager.broadcast(json.dumps({
            "type": "job_completed",
            "job_id": job_id,
            "status": "ready",
            "message": f"Fiscal note for {job_id} has been generated successfully!"
        }))
        
        print(f"Fiscal note generation completed for {job_id}")
        send_success_msg_to_slack(f"Fiscal note for {job_id} has been generated successfully!")
        
    except Exception as e:
        error_msg = f"Error in fiscal note generation job {job_id}: {str(e)}"
        
        send_error_to_slack(error_msg)

        # Send error notification
        await manager.broadcast(json.dumps({
            "type": "job_error",
            "job_id": job_id,
            "status": "error",
            "message": f"Failed to generate fiscal note for {job_id}: {str(e)}"
        }))
    finally:
        cleanup_job(job_id)

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
    
    # Create independent background task with error handling
    task = asyncio.create_task(create_fiscal_note_job(bill_type, bill_number, year))
    # Add done callback to handle any unhandled exceptions
    task.add_done_callback(lambda t: t.exception() if t.exception() else None)

    return {
        "message": "Fiscal note queued for generation",
        "job_id": job_id,
        "success": True
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
        return {
            "question": request.question,
            "response": response.text
        }
    except Exception as e:
        print(f"Error generating LLM response: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate LLM response: {str(e)}")

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

