from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, TypedDict
import os
import tempfile
import shutil
from pathlib import Path
import json
import google.generativeai as genai
from tqdm import tqdm

# Handle both relative and absolute imports
try:
    from .settings import Settings
    from .documents.embeddings import ChromaDBManager
except ImportError:
    from settings import Settings
    from documents.embeddings import ChromaDBManager

# Initialize FastAPI app
app = FastAPI(
    title="House Finance Document API",
    description="API for managing and searching financial documents using ChromaDB",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
config = Settings()

# Initialize two separate ChromaDB managers for budget and text collections
class BudgetChromeManager(ChromaDBManager):
    def __init__(self):
        # Initialize the parent class first
        super().__init__()
        
        # Now override with our specific collection
        self.collection_name = "budget_items"
        try:
            self.collection = self.client.get_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function
            )
        except Exception:
            # Create new collection if it doesn't exist
            self.collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"}
            )

class TextChromeManager(ChromaDBManager):
    def __init__(self):
        # Initialize the parent class first
        super().__init__()
        
        # Now override with our specific collection
        self.collection_name = "text_items"
        try:
            self.collection = self.client.get_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function
            )
        except Exception:
            # Create new collection if it doesn't exist
            self.collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"}
            )

budget_manager = BudgetChromeManager()
text_manager = TextChromeManager()

# Initialize Gemini for LangGraph
genai.configure(api_key=config.google_api_key)

# Department and funding mappings
DEPARTMENT_MAPPINGS = {
    "ATG": "Department of the Attorney General",
    "BED": "Department of Business, Economic Development and Tourism", 
    "BUF": "Department of Budget and Finance",
    "CCA": "Department of Commerce and Consumer Affairs",
    "DEF": "Department of Defense",
    "EDN": "Department of Education",
    "GOV": "Office of the Governor",
    "HHL": "Department of Hawaiian Home Lands",
    "HMS": "Department of Human Services",
    "HRD": "Department of Human Resources Development",
    "HTH": "Department of Health",
    "LAW": "Department of Law Enforcement",
    "LBR": "Department of Labor and Industrial Relations",
    "LNR": "Department of Land and Natural Resources",
    "LTG": "Office of the Lieutenant Governor",
    "PSD": "Department of Corrections and Rehabilitation",
    "SUB": "Subsidies",
    "TAX": "Department of Taxation",
    "TRN": "Department of Transportation",
    "UOH": "University of Hawaii",
    "CCH": "City and County of Honolulu",
    "COH": "County of Hawaii",
    "00K": "County of Kauai",
    "COM": "County of Maui"
}

FUNDING_SOURCES = {
    "A": "general funds",
    "B": "special funds", 
    "C": "general obligation bond fund",
    "D": "general obligation bond fund with debt service cost to be paid from special funds",
    "E": "revenue bond funds",
    "J": "federal aid interstate funds",
    "K": "federal aid primary funds",
    "L": "federal aid secondary funds",
    "M": "federal aid urban funds",
    "N": "federal funds",
    "P": "other federal funds",
    "R": "private contributions",
    "S": "county funds",
    "T": "trust funds",
    "U": "interdepartmental transfers",
    "V": "American Rescue Plan funds",
    "W": "revolving funds",
    "X": "other funds"
}

# Pydantic models for API
class SearchQuery(BaseModel):
    query: str = Field(..., description="Search query text")
    n_results: int = Field(default=5, ge=1, le=1000, description="Number of results to return")
    include_metadata: bool = Field(default=True, description="Include document metadata in results")
    collection_type: str = Field(default="both", description="Which collection to search: 'budget', 'text', or 'both'")

class IntelligentQuery(BaseModel):
    query: str = Field(..., description="User's question about the budget")
    max_results: int = Field(default=1000, ge=1, le=10000, description="Maximum number of documents to retrieve")
    use_top_n_results: Optional[int] = Field(default=None, ge=1, le=1000, description="Number of top documents to use for answer generation (None = use all)")

class ReasoningStep(BaseModel):
    step: str
    departments: List[str]
    funding_sources: List[str]
    search_terms: List[str]
    reasoning: str

class IntelligentResponse(BaseModel):
    query: str
    reasoning: ReasoningStep
    retrieved_documents: List[Dict[str, Any]]
    answer: str
    total_documents_found: int
    budget_documents_found: int
    text_documents_found: int

class SearchResult(BaseModel):
    id: str
    content: str
    score: float
    collection_type: str
    metadata: Optional[Dict[str, Any]] = None

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_results: int
    budget_results: int
    text_results: int

class MetadataSearchQuery(BaseModel):
    where: Dict[str, Any] = Field(..., description="Metadata filter conditions")
    n_results: int = Field(default=50, ge=1, le=1000, description="Number of results to return")
    collection_type: str = Field(default="both", description="Which collection to search: 'budget', 'text', or 'both'")

class FieldSearchQuery(BaseModel):
    field_name: str = Field(..., description="Name of the metadata field to search")
    search_value: str = Field(..., description="Value to search for")
    exact_match: bool = Field(default=True, description="If True, exact match; if False, contains match")
    n_results: int = Field(default=50, ge=1, le=1000, description="Number of results to return")
    collection_type: str = Field(default="both", description="Which collection to search: 'budget', 'text', or 'both'")

class DocumentInfo(BaseModel):
    filename: str
    size: int
    chunks_created: int
    metadata: Dict[str, Any]

class IngestionResponse(BaseModel):
    success: bool
    message: str
    documents: List[DocumentInfo]

class CollectionStats(BaseModel):
    budget_collection: Dict[str, Any]
    text_collection: Dict[str, Any]
    total_documents: int

# State class for LangGraph  
class QueryState(TypedDict):
    query: str
    max_results: int
    reasoning: Optional[ReasoningStep]
    retrieved_documents: Optional[List[Dict[str, Any]]]
    answer: Optional[str]

# Helper functions for intelligent querying
def analyze_user_query(query: str) -> ReasoningStep:
    """Analyze the query and determine which departments and funding sources to search"""
    print(f"DEBUG: Starting reasoning analysis for query: {query}")
    
    # Create reasoning prompt
    prompt = f"""
    Analyze this budget-related query: "{query}"
    
    Based on the query, identify:
    1. Which government departments might be relevant (use department codes/names)
    2. Which funding sources might be relevant (use funding codes/types)  
    3. Key search terms to use for document retrieval
    
    Available departments: {json.dumps(DEPARTMENT_MAPPINGS, indent=2)}
    Available funding sources: {json.dumps(FUNDING_SOURCES, indent=2)}
    
    Provide your analysis in this JSON format:
    {{
        "departments": ["list of relevant department codes or names"],
        "funding_sources": ["list of relevant funding source codes or types"],
        "search_terms": ["list of key terms to search for"],
        "reasoning": "explanation of your analysis"
    }}
    
    Return only the JSON, no other text.
    """
    
    try:
        print("DEBUG: Calling Gemini for reasoning analysis...")
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(prompt)
        print(f"DEBUG: Gemini response received: {response.text[:200]}...")
        
        analysis = json.loads(response.text.strip())
        print(f"DEBUG: Parsed analysis - departments: {analysis.get('departments', [])}")
        print(f"DEBUG: Parsed analysis - funding_sources: {analysis.get('funding_sources', [])}")
        print(f"DEBUG: Parsed analysis - search_terms: {analysis.get('search_terms', [])}")
        
        reasoning = ReasoningStep(
            step="analysis",
            departments=analysis.get("departments", []),
            funding_sources=analysis.get("funding_sources", []),
            search_terms=analysis.get("search_terms", []),
            reasoning=analysis.get("reasoning", "")
        )
        
        print("DEBUG: Reasoning analysis completed successfully")
        return reasoning
        
    except Exception as e:
        print(f"DEBUG: Error in reasoning analysis: {str(e)}")
        # Fallback reasoning
        reasoning = ReasoningStep(
            step="analysis",
            departments=["EDN", "HTH", "TRN"],  # Common departments
            funding_sources=["A", "B", "C"],    # Common funding types
            search_terms=[query],
            reasoning=f"Using fallback analysis due to error: {str(e)}"
        )
        print("DEBUG: Using fallback reasoning")
        return reasoning

def search_relevant_documents(reasoning: ReasoningStep, max_results: int = 1000) -> Dict[str, Any]:
    """Search for relevant documents in both collections based on the reasoning using flexible metadata search"""
    print("DEBUG: Starting document search in both collections using flexible metadata search")
    
    budget_documents = []
    text_documents = []
    search_queries = []
    
    # Build search queries from reasoning
    for term in reasoning.search_terms:
        search_queries.append(term)
    
    for dept in reasoning.departments:
        if dept in DEPARTMENT_MAPPINGS:
            search_queries.append(DEPARTMENT_MAPPINGS[dept])
        else:
            search_queries.append(dept)
    
    for funding in reasoning.funding_sources:
        if funding in FUNDING_SOURCES:
            search_queries.append(FUNDING_SOURCES[funding])
        else:
            search_queries.append(funding)
    
    print(f"DEBUG: Built {len(search_queries)} search queries: {search_queries}")
    
    # Search both collections using flexible metadata search
    half_results = max_results // 2
    
    # Search budget collection with flexible metadata search
    budget_seen_ids = set()
    
    # First pass: search with specific queries
    for i, search_query in enumerate(search_queries):
        print(f"DEBUG: Searching budget collection with flexible metadata search {i+1}/{len(search_queries)}: '{search_query}'")
        try:
            # Request more results per query to increase chances of finding documents
            results_per_query = min(200, half_results // max(1, len(search_queries) // 2))
            results = budget_manager.flexible_metadata_search(
                query=search_query,
                n_results=results_per_query
            )
            
            results_count = len(results["documents"][0]) if results["documents"] else 0
            print(f"DEBUG: Found {results_count} budget results for query '{search_query}'")
            
            # Process results and avoid duplicates
            for doc_id, content, metadata in zip(
                results["ids"][0],
                results["documents"][0], 
                results["metadatas"][0]
            ):
                if doc_id not in budget_seen_ids:
                    budget_documents.append({
                        "id": doc_id,
                        "content": content,
                        "score": 1.0,  # Metadata matches are binary (match or no match)
                        "metadata": metadata,
                        "search_query": search_query,
                        "collection_type": "budget_item"
                    })
                    budget_seen_ids.add(doc_id)
                        
        except Exception as e:
            print(f"DEBUG: Error searching budget collection for '{search_query}': {e}")
            continue
    
    # Second pass: if we don't have enough results, try broader searches
    if len(budget_documents) < half_results:
        print(f"DEBUG: Only found {len(budget_documents)} budget documents, trying broader searches...")
        
        # Try searching for just department codes
        for dept in reasoning.departments:
            if dept in DEPARTMENT_MAPPINGS and len(budget_documents) < half_results:
                try:
                    results = budget_manager.flexible_metadata_search(
                        query=dept,  # Just the department code
                        n_results=100
                    )
                    
                    results_count = len(results["documents"][0]) if results["documents"] else 0
                    print(f"DEBUG: Broader search for '{dept}' found {results_count} budget results")
                    
                    for doc_id, content, metadata in zip(
                        results["ids"][0],
                        results["documents"][0], 
                        results["metadatas"][0]
                    ):
                        if doc_id not in budget_seen_ids:
                            budget_documents.append({
                                "id": doc_id,
                                "content": content,
                                "score": 0.8,  # Slightly lower score for broader matches
                                "metadata": metadata,
                                "search_query": f"broad_{dept}",
                                "collection_type": "budget_item"
                            })
                            budget_seen_ids.add(doc_id)
                            
                except Exception as e:
                    print(f"DEBUG: Error in broader search for '{dept}': {e}")
                    continue
    
    # Search text collection with flexible metadata search
    text_seen_ids = set()
    
    # First pass: search with specific queries
    for i, search_query in enumerate(search_queries):
        print(f"DEBUG: Searching text collection with flexible metadata search {i+1}/{len(search_queries)}: '{search_query}'")
        try:
            # Request more results per query to increase chances of finding documents
            results_per_query = min(200, half_results // max(1, len(search_queries) // 2))
            results = text_manager.flexible_metadata_search(
                query=search_query,
                n_results=results_per_query
            )
            
            results_count = len(results["documents"][0]) if results["documents"] else 0
            print(f"DEBUG: Found {results_count} text results for query '{search_query}'")
            
            # Process results and avoid duplicates
            for doc_id, content, metadata in zip(
                results["ids"][0],
                results["documents"][0], 
                results["metadatas"][0]
            ):
                if doc_id not in text_seen_ids:
                    text_documents.append({
                        "id": doc_id,
                        "content": content,
                        "score": 1.0,  # Metadata matches are binary (match or no match)
                        "metadata": metadata,
                        "search_query": search_query,
                        "collection_type": "text_item"
                    })
                    text_seen_ids.add(doc_id)
                        
        except Exception as e:
            print(f"DEBUG: Error searching text collection for '{search_query}': {e}")
            continue
    
    # Second pass for text collection: if we don't have enough results, try broader searches
    if len(text_documents) < half_results:
        print(f"DEBUG: Only found {len(text_documents)} text documents, trying broader searches...")
        
        # Try searching for just department codes
        for dept in reasoning.departments:
            if dept in DEPARTMENT_MAPPINGS and len(text_documents) < half_results:
                try:
                    results = text_manager.flexible_metadata_search(
                        query=dept,  # Just the department code
                        n_results=100
                    )
                    
                    results_count = len(results["documents"][0]) if results["documents"] else 0
                    print(f"DEBUG: Broader search for '{dept}' found {results_count} text results")
                    
                    for doc_id, content, metadata in zip(
                        results["ids"][0],
                        results["documents"][0], 
                        results["metadatas"][0]
                    ):
                        if doc_id not in text_seen_ids:
                            text_documents.append({
                                "id": doc_id,
                                "content": content,
                                "score": 0.8,  # Slightly lower score for broader matches
                                "metadata": metadata,
                                "search_query": f"broad_{dept}",
                                "collection_type": "text_item"
                            })
                            text_seen_ids.add(doc_id)
                            
                except Exception as e:
                    print(f"DEBUG: Error in broader search for '{dept}': {e}")
                    continue
    
    # Third pass: if we still don't have enough results, try semantic search as fallback
    total_found = len(budget_documents) + len(text_documents)
    if total_found < max_results // 2:  # If we have less than 50% of desired results
        print(f"DEBUG: Only found {total_found} total documents, trying semantic search fallback...")
        
        # Try semantic search on budget collection
        if len(budget_documents) < half_results:
            try:
                # Use the main search terms for semantic search
                main_query = " ".join(reasoning.search_terms[:3])  # Use first 3 search terms
                semantic_results = budget_manager.query_documents(
                    query_text=main_query,
                    n_results=min(100, half_results - len(budget_documents))
                )
                
                results_count = len(semantic_results["documents"][0]) if semantic_results["documents"] else 0
                print(f"DEBUG: Semantic search for '{main_query}' found {results_count} budget results")
                
                for i, doc in enumerate(semantic_results["documents"][0]):
                    doc_id = f"semantic_budget_{i}_{len(budget_documents)}"
                    if doc_id not in budget_seen_ids:
                        budget_documents.append({
                            "id": doc_id,
                            "content": doc,
                            "score": 0.6,  # Lower score for semantic matches
                            "metadata": semantic_results["metadatas"][0][i],
                            "search_query": f"semantic_{main_query}",
                            "collection_type": "budget_item"
                        })
                        budget_seen_ids.add(doc_id)
                        
            except Exception as e:
                print(f"DEBUG: Error in semantic search for budget collection: {e}")
        
        # Try semantic search on text collection
        if len(text_documents) < half_results:
            try:
                # Use the main search terms for semantic search
                main_query = " ".join(reasoning.search_terms[:3])  # Use first 3 search terms
                semantic_results = text_manager.query_documents(
                    query_text=main_query,
                    n_results=min(100, half_results - len(text_documents))
                )
                
                results_count = len(semantic_results["documents"][0]) if semantic_results["documents"] else 0
                print(f"DEBUG: Semantic search for '{main_query}' found {results_count} text results")
                
                for i, doc in enumerate(semantic_results["documents"][0]):
                    doc_id = f"semantic_text_{i}_{len(text_documents)}"
                    if doc_id not in text_seen_ids:
                        text_documents.append({
                            "id": doc_id,
                            "content": doc,
                            "score": 0.6,  # Lower score for semantic matches
                            "metadata": semantic_results["metadatas"][0][i],
                            "search_query": f"semantic_{main_query}",
                            "collection_type": "text_item"
                        })
                        text_seen_ids.add(doc_id)
                        
            except Exception as e:
                print(f"DEBUG: Error in semantic search for text collection: {e}")
    
    # Combine all documents and ensure no cross-collection duplicates
    all_documents = budget_documents + text_documents
    
    # Additional deduplication check across collections (in case same ID exists in both)
    seen_all_ids = set()
    deduplicated_documents = []
    for doc in all_documents:
        if doc["id"] not in seen_all_ids:
            deduplicated_documents.append(doc)
            seen_all_ids.add(doc["id"])
    
    # Sort by score (prioritize exact matches over broader matches)
    deduplicated_documents.sort(key=lambda x: x["score"], reverse=True)
    result_documents = deduplicated_documents[:max_results]
    
    print(f"DEBUG: Document search completed - found {len(budget_documents)} budget docs, {len(text_documents)} text docs")
    print(f"DEBUG: After deduplication: {len(deduplicated_documents)} unique docs, returning top {len(result_documents)}")
    
    return {
        "documents": result_documents,
        "budget_count": len(budget_documents),
        "text_count": len(text_documents)
    }

def generate_comprehensive_answer(query: str, reasoning: ReasoningStep, search_results: Dict[str, Any], use_top_n_results: int = None) -> str:
    """Generate a comprehensive answer based on retrieved documents from both collections"""
    documents = search_results["documents"]
    budget_count = search_results["budget_count"]
    text_count = search_results["text_count"]
    
    # Use all documents by default, or limit to specified number
    if use_top_n_results is None:
        docs_to_use = documents
    else:
        docs_to_use = documents[:use_top_n_results]
    
    print("DEBUG: Starting answer generation")
    print(f"DEBUG: Generating answer from {len(docs_to_use)} documents (out of {len(documents)} total) ({budget_count} budget, {text_count} text)")
    
    # Prepare context from documents
    context_parts = []
    for i, doc in enumerate(docs_to_use):
        metadata = doc["metadata"]
        collection_type = doc["collection_type"]
        
        if collection_type == "budget_item":
            dept = metadata.get("expending_agency", "Unknown")
            amount_2025 = metadata.get("fiscal_year_2025_2026_amount", "unknown")
            amount_2026 = metadata.get("fiscal_year_2026_2027_amount", "unknown")
            
            context_parts.append(f"""
Budget Document {i+1}:
Department: {dept}
FY 2025-2026 Amount: ${amount_2025}
FY 2026-2027 Amount: ${amount_2026}
Content: {doc["content"][:300]}...
""")
        else:  # text_item
            doc_name = metadata.get("document_name", "Unknown")
            page_num = metadata.get("page_number", "Unknown")
            
            context_parts.append(f"""
Text Document {i+1}:
Source: {doc_name} (Page {page_num})
Content: {doc["content"][:300]}...
""")
    
    context = "\n".join(context_parts)
    print(f"DEBUG: Prepared context from {len(docs_to_use)} documents")
    
    # Generate answer
    prompt = f"""
Based on the following budget documents from both structured budget data and text content, provide a comprehensive answer to this question: "{query}"

Context from budget documents:
{context}

Analysis performed:
- Searched departments: {reasoning.departments}
- Searched funding sources: {reasoning.funding_sources}
- Search terms used: {reasoning.search_terms}
- Reasoning: {reasoning.reasoning}
- Documents found: {budget_count} structured budget items, {text_count} text documents
- Documents used for analysis: {len(docs_to_use)} out of {len(documents)} total documents

Provide a detailed answer that:
1. Directly answers the user's question
2. Includes specific budget amounts and departments when relevant
3. Explains any patterns or insights from the data
4. Mentions data sources and limitations if applicable
5. Distinguishes between structured budget data and supporting text when relevant

Answer:
"""
    
    try:
        print("DEBUG: Calling Gemini for answer generation...")
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(prompt)
        answer = response.text.strip()
        print(f"DEBUG: Answer generated successfully - length: {len(answer)} characters")
        return answer
    except Exception as e:
        print(f"DEBUG: Error generating answer: {str(e)}")
        return f"I found {len(documents)} relevant budget documents ({budget_count} structured budget items, {text_count} text documents), but encountered an error generating the full analysis: {str(e)}"

# API Endpoints

def ingest_processed_documents(file_path: str = "documents/processed_all_documents_geminiV4_expanded.json") -> Dict[str, Any]:
    """
    Ingest processed budget documents into both budget and text collections
    
    Args:
        file_path: Path to the processed JSON file (relative to src directory)
    
    Returns:
        Dictionary with ingestion statistics
    """
    import time
    start_time = time.time()
    
    print(f"📥 Starting document ingestion from {file_path}")
    
    # Make sure file path is relative to src directory
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.path.dirname(__file__), file_path)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Processed documents file not found: {file_path}")
    
    def clean_metadata_value(value):
        """Convert None values to 'unknown' string for ChromaDB compatibility"""
        if value is None:
            return 'unknown'
        if isinstance(value, (int, float)):
            return str(value)
        return str(value)
    
    def clean_metadata_dict(metadata):
        """Clean all values in metadata dictionary for ChromaDB compatibility"""
        cleaned = {}
        for key, value in metadata.items():
            cleaned[key] = clean_metadata_value(value)
        return cleaned
    
    try:
        # Load the processed JSON data
        print("📖 Loading processed document data...")
        with open(file_path, 'r', encoding='utf-8') as f:
            all_documents = json.load(f)
        
        print(f"✅ Loaded data for {len(all_documents)} documents")
        
        budget_count = 0
        text_count = 0
        errors = []
        unknown_items_count = 0
        
        # Count total items for overall progress
        total_budget_items = sum(len(doc_data.get('budget_items', [])) for doc_data in all_documents.values())
        total_text_items = sum(len(doc_data.get('text_items', [])) for doc_data in all_documents.values())
        
        print(f"📊 Total items to process: {total_budget_items} budget items, {total_text_items} text items")
        
        # Create overall progress bars
        overall_budget_progress = tqdm(total=total_budget_items, desc="Overall Budget Items", position=0)
        overall_text_progress = tqdm(total=total_text_items, desc="Overall Text Items", position=1)
        
        # Process each document
        for doc_name, doc_data in tqdm(all_documents.items(), desc="Processing documents", position=2, leave=False):
            doc_start_time = time.time()
            print(f"\n🔄 Processing document: {doc_name}")
            
            try:
                # Process budget items
                if 'budget_items' in doc_data:
                    budget_items = doc_data['budget_items']
                    print(f"   📊 Found {len(budget_items)} budget items")
                    
                    for item in tqdm(budget_items, desc=f"Budget items in {doc_name}", position=3, leave=False):
                        try:
                            # Create document text with key budget information
                            doc_parts = []
                            
                            # Add program if available
                            if item.get('program') and item.get('program') != 'unknown':
                                doc_parts.append(f"Program: {item.get('program')}")
                            
                            # Add program_id if available
                            if item.get('program_id') and item.get('program_id') != 'unknown':
                                doc_parts.append(f"Program ID: {item.get('program_id')}")
                            
                            # Add expending_agency if available
                            if item.get('expending_agency') and item.get('expending_agency') != 'unknown':
                                doc_parts.append(f"Expending Agency: {item.get('expending_agency')}")
                            
                            # Add expanded expending_agency if available
                            if item.get('expending_agency_expanded') and item.get('expending_agency_expanded') != 'unknown':
                                doc_parts.append(f"Department: {item.get('expending_agency_expanded')}")
                            
                            # Add fiscal year amounts if available
                            if item.get('fiscal_year_2025_2026_amount') and item.get('fiscal_year_2025_2026_amount') != 'unknown':
                                doc_parts.append(f"FY 2025-2026 Amount: ${item.get('fiscal_year_2025_2026_amount')}")
                            
                            if item.get('fiscal_year_2026_2027_amount') and item.get('fiscal_year_2026_2027_amount') != 'unknown':
                                doc_parts.append(f"FY 2026-2027 Amount: ${item.get('fiscal_year_2026_2027_amount')}")
                            
                            # Add appropriations MOF if available
                            if item.get('appropriations_mof_2025_2026') and item.get('appropriations_mof_2025_2026') != 'unknown':
                                doc_parts.append(f"FY 2025-2026 Funding Type: {item.get('appropriations_mof_2025_2026')}")
                            
                            if item.get('appropriations_mof_2026_2027') and item.get('appropriations_mof_2026_2027') != 'unknown':
                                doc_parts.append(f"FY 2026-2027 Funding Type: {item.get('appropriations_mof_2026_2027')}")
                            
                            # Add expanded appropriations MOF if available
                            if item.get('appropriations_mof_2025_2026_expanded') and item.get('appropriations_mof_2025_2026_expanded') != 'unknown':
                                doc_parts.append(f"FY 2025-2026 Funding: {item.get('appropriations_mof_2025_2026_expanded')}")
                            
                            if item.get('appropriations_mof_2026_2027_expanded') and item.get('appropriations_mof_2026_2027_expanded') != 'unknown':
                                doc_parts.append(f"FY 2026-2027 Funding: {item.get('appropriations_mof_2026_2027_expanded')}")
                            
                            # Check if we have any meaningful content
                            if not doc_parts:
                                print(f"   ⚠️  Unknown budget item found: {item}")
                                unknown_items_count += 1
                                overall_budget_progress.update(1)
                                continue
                            
                            # Create comprehensive searchable text
                            searchable_content = "\n".join(doc_parts)
                            searchable_content += f"\nDocument: {doc_name}"
                            
                            # Generate unique ID
                            item_id = f"{doc_name}_budget_{item.get('page_number', 'unknown')}_{budget_count}"
                            
                            # Clean metadata for ChromaDB compatibility
                            cleaned_metadata = clean_metadata_dict(item)
                            
                            # Add to budget collection
                            budget_manager.collection.add(
                                documents=[searchable_content],
                                metadatas=[cleaned_metadata],
                                ids=[item_id]
                            )
                            
                            budget_count += 1
                            overall_budget_progress.update(1)
                            
                        except Exception as e:
                            error_msg = f"Error processing budget item in {doc_name}: {str(e)}"
                            print(f"   ⚠️  {error_msg}")
                            errors.append(error_msg)
                            overall_budget_progress.update(1)  # Still update progress even on error
                
                # Process text items
                if 'text_items' in doc_data:
                    text_items = doc_data['text_items']
                    print(f"   📄 Found {len(text_items)} text items")
                    
                    for item in tqdm(text_items, desc=f"Text items in {doc_name}", position=3, leave=False):
                        try:
                            # Use the text content directly for embedding
                            text_content = item.get('text_content', '')
                            
                            if text_content.strip():  # Only add non-empty text
                                # Generate unique ID
                                item_id = f"{doc_name}_text_{item.get('page_number', 'unknown')}_{text_count}"
                                
                                # Clean metadata for ChromaDB compatibility
                                cleaned_metadata = clean_metadata_dict(item)
                                
                                # Add to text collection
                                text_manager.collection.add(
                                    documents=[text_content],
                                    metadatas=[cleaned_metadata],
                                    ids=[item_id]
                                )
                                
                                text_count += 1
                            
                            overall_text_progress.update(1)
                            
                        except Exception as e:
                            error_msg = f"Error processing text item in {doc_name}: {str(e)}"
                            print(f"   ⚠️  {error_msg}")
                            errors.append(error_msg)
                            overall_text_progress.update(1)  # Still update progress even on error
                
                # Show timing for this document
                doc_time = time.time() - doc_start_time
                print(f"   ✅ Completed {doc_name} in {doc_time:.2f} seconds")
                
            except Exception as e:
                error_msg = f"Error processing document {doc_name}: {str(e)}"
                print(f"❌ {error_msg}")
                errors.append(error_msg)
        
        # Close progress bars
        overall_budget_progress.close()
        overall_text_progress.close()
        
        # Summary
        total_time = time.time() - start_time
        print(f"\n✅ Ingestion completed in {total_time:.2f} seconds!")
        print(f"   📊 Budget items ingested: {budget_count}")
        print(f"   📄 Text items ingested: {text_count}")
        print(f"   ⚠️  Unknown budget items skipped: {unknown_items_count}")
        print(f"   ⏱️  Average rate: {(budget_count + text_count) / total_time:.1f} items/second")
        if errors:
            print(f"   ⚠️  Errors encountered: {len(errors)}")
            for error in errors[:5]:  # Show first 5 errors
                print(f"      - {error}")
            if len(errors) > 5:
                print(f"      ... and {len(errors) - 5} more errors")
        
        return {
            "success": True,
            "budget_items_ingested": budget_count,
            "text_items_ingested": text_count,
            "unknown_items_skipped": unknown_items_count,
            "total_documents_processed": len(all_documents),
            "processing_time_seconds": total_time,
            "items_per_second": (budget_count + text_count) / total_time if total_time > 0 else 0,
            "errors": errors,
            "file_path": file_path
        }
        
    except Exception as e:
        error_msg = f"Fatal error during ingestion: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "budget_items_ingested": 0,
            "text_items_ingested": 0,
            "unknown_items_skipped": 0,
            "total_documents_processed": 0,
            "processing_time_seconds": 0,
            "items_per_second": 0,
            "errors": [error_msg],
            "file_path": file_path
        }

@app.get("/", summary="Health Check")
async def root():
    """Health check endpoint"""
    return {
        "message": "House Finance Document API",
        "status": "healthy",
        "embedding_model": config.embedding_model,
        "embedding_provider": config.embedding_provider,
        "collections": ["budget_items", "text_items"]
    }

@app.get("/stats", response_model=CollectionStats, summary="Get Collection Statistics")
async def get_stats():
    """Get statistics about both document collections"""
    try:
        budget_stats = budget_manager.get_collection_stats()
        text_stats = text_manager.get_collection_stats()
        
        return CollectionStats(
            budget_collection=budget_stats,
            text_collection=text_stats,
            total_documents=budget_stats.get("document_count", 0) + text_stats.get("document_count", 0)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")

@app.post("/search", response_model=SearchResponse, summary="Search Documents")
async def search_documents(search_query: SearchQuery):
    """Search documents using semantic similarity."""
    try:
        all_results = []
        budget_results = []
        text_results = []
        
        if search_query.collection_type in ["budget", "both"]:
            # Search budget collection
            budget_search_results = budget_manager.query_documents(
                query_text=search_query.query,
                n_results=search_query.n_results
            )
            
            # Process budget results
            for i, doc in enumerate(budget_search_results['documents'][0]):
                result = SearchResult(
                    id=f"budget_{i}",
                    content=doc,
                    score=1.0 - budget_search_results['distances'][0][i],  # Convert distance to similarity
                    collection_type="budget",
                    metadata=budget_search_results['metadatas'][0][i] if search_query.include_metadata else None
                )
                all_results.append(result)
                budget_results.append(result)
        
        if search_query.collection_type in ["text", "both"]:
            # Search text collection
            text_search_results = text_manager.query_documents(
                query_text=search_query.query,
                n_results=search_query.n_results
            )
            
            # Process text results
            for i, doc in enumerate(text_search_results['documents'][0]):
                result = SearchResult(
                    id=f"text_{i}",
                    content=doc,
                    score=1.0 - text_search_results['distances'][0][i],  # Convert distance to similarity
                    collection_type="text",
                    metadata=text_search_results['metadatas'][0][i] if search_query.include_metadata else None
                )
                all_results.append(result)
                text_results.append(result)
        
        # Sort all results by score (highest first)
        all_results.sort(key=lambda x: x.score, reverse=True)
        
        # Limit to requested number of results
        all_results = all_results[:search_query.n_results]
        
        return SearchResponse(
            query=search_query.query,
            results=all_results,
            total_results=len(all_results),
            budget_results=len(budget_results),
            text_results=len(text_results)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.post("/search/metadata", response_model=SearchResponse, summary="Search Documents by Metadata")
async def search_by_metadata(search_query: MetadataSearchQuery):
    """Search documents using flexible metadata matching with case-insensitive partial string search."""
    try:
        all_results = []
        budget_results = []
        text_results = []
        
        # Extract search query from the where clause for flexible search
        # Handle both direct field queries and $or queries
        search_terms = []
        
        if "$or" in search_query.where:
            # Extract search terms from $or clauses
            for condition in search_query.where["$or"]:
                for field, value in condition.items():
                    if isinstance(value, dict) and "$contains" in value:
                        search_terms.append(value["$contains"])
                    elif isinstance(value, str):
                        search_terms.append(value)
        else:
            # Handle direct field queries
            for field, value in search_query.where.items():
                if isinstance(value, dict) and "$contains" in value:
                    search_terms.append(value["$contains"])
                elif isinstance(value, str):
                    search_terms.append(value)
        
        # Use the first search term for flexible search (most common case)
        query_term = search_terms[0] if search_terms else ""
        
        if search_query.collection_type in ["budget", "both"]:
            # Use flexible metadata search for budget collection
            budget_search_results = budget_manager.flexible_metadata_search(
                query=query_term,
                n_results=search_query.n_results
            )
            
            # Process budget results
            for i, doc in enumerate(budget_search_results['documents'][0]):
                result = SearchResult(
                    id=budget_search_results['ids'][0][i] if 'ids' in budget_search_results else f"budget_{i}",
                    content=doc,
                    score=1.0,  # Metadata matches are binary (match or no match)
                    collection_type="budget",
                    metadata=budget_search_results['metadatas'][0][i]
                )
                all_results.append(result)
                budget_results.append(result)
        
        if search_query.collection_type in ["text", "both"]:
            # Use flexible metadata search for text collection
            text_search_results = text_manager.flexible_metadata_search(
                query=query_term,
                n_results=search_query.n_results
            )
            
            # Process text results
            for i, doc in enumerate(text_search_results['documents'][0]):
                result = SearchResult(
                    id=text_search_results['ids'][0][i] if 'ids' in text_search_results else f"text_{i}",
                    content=doc,
                    score=1.0,  # Metadata matches are binary (match or no match)
                    collection_type="text",
                    metadata=text_search_results['metadatas'][0][i]
                )
                all_results.append(result)
                text_results.append(result)
        
        # Limit to requested number of results
        all_results = all_results[:search_query.n_results]
        
        return SearchResponse(
            query=f"Flexible metadata search: {query_term}",
            results=all_results,
            total_results=len(all_results),
            budget_results=len(budget_results),
            text_results=len(text_results)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metadata search failed: {str(e)}")

@app.delete("/reset", summary="Reset Collections")
async def reset_collections():
    """Reset both document collections (delete all documents)"""
    try:
        budget_manager.reset_collection()
        text_manager.reset_collection()
        return {"message": "Both collections reset successfully", "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting collections: {str(e)}")

@app.get("/documents/{document_id}", summary="Get Document by ID")
async def get_document(document_id: str, collection: str = Query(default="budget", description="Collection to search: 'budget' or 'text'")):
    """Get a specific document by its ID from specified collection"""
    try:
        manager = budget_manager if collection == "budget" else text_manager
        
        # Query for specific document ID
        results = manager.collection.get(ids=[document_id])
        
        if not results["ids"]:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "id": results["ids"][0],
            "content": results["documents"][0],
            "collection_type": collection,
            "metadata": results["metadatas"][0] if results["metadatas"] else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting document: {str(e)}")

@app.post("/intelligent-query", response_model=IntelligentResponse, summary="Get Comprehensive Answer to Budget-Related Question")
async def intelligent_query(query: IntelligentQuery):
    """Get a comprehensive answer to a budget-related question using both collections"""
    try:
        print(f"DEBUG: Received intelligent query: '{query.query}' with max_results={query.max_results}")
        
        print("DEBUG: Starting intelligent query processing...")
        import time
        start_time = time.time()
        
        # Execute intelligent query processing
        reasoning = analyze_user_query(query.query)
        search_results = search_relevant_documents(reasoning, query.max_results)
        answer = generate_comprehensive_answer(query.query, reasoning, search_results, query.use_top_n_results)
        
        end_time = time.time()
        print(f"DEBUG: Intelligent query processing completed in {end_time - start_time:.2f} seconds")
        
        # Extract results
        documents = search_results["documents"]
        budget_count = search_results["budget_count"]
        text_count = search_results["text_count"]
        total_documents_found = len(documents)
        
        print(f"DEBUG: Final results - {total_documents_found} documents found ({budget_count} budget, {text_count} text), answer length: {len(answer)} characters")
        
        # Format retrieved documents
        formatted_documents = []
        for doc in documents:
            formatted_documents.append({
                "id": doc["id"],
                "content": doc["content"],
                "score": doc["score"],
                "metadata": doc["metadata"],
                "search_query": doc["search_query"],
                "collection_type": doc["collection_type"]
            })
        
        print("DEBUG: Returning intelligent query response")
        return IntelligentResponse(
            query=query.query,
            reasoning=reasoning,
            retrieved_documents=formatted_documents,
            answer=answer,
            total_documents_found=total_documents_found,
            budget_documents_found=budget_count,
            text_documents_found=text_count
        )
    
    except Exception as e:
        print(f"DEBUG: Error in intelligent query endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing intelligent query: {str(e)}")

# Run the server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 