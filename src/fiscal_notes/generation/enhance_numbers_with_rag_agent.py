"""
Enhanced number analysis using LangGraph RAG agent.

This script implements a LangGraph StateGraph agent following best practices:

Architecture:
- Uses TypedDict with Annotated types and reducers for proper state management
- Implements a cyclic graph with conditional routing for iterative refinement
- Separates concerns: search generation, execution, analysis, and routing

The agent workflow:
1. Receive numbers with their immediate context
2. Use RAG (Retrieval-Augmented Generation) to search the full document
3. Iteratively refine understanding through multiple search cycles (max 10 iterations)
4. Generate comprehensive properties and summaries for each number

Key LangGraph features used:
- StateGraph with proper state reducers (operator.add for lists)
- Conditional edges for dynamic routing
- START/END constants for graph boundaries
- Standalone routing functions for clean separation of concerns
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, TypedDict, Annotated
from collections import defaultdict
import time
import operator
from datetime import datetime

import google.generativeai as genai
from dotenv import load_dotenv

# LangGraph imports
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import numpy as np

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Global logger for decision tracking
class DecisionLogger:
    """Logs all agent decisions, reasoning, and queries to a file."""
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.current_number = None
        
    def start_number(self, number_info: Dict[str, Any], index: int, total: int):
        """Start logging for a new number."""
        self.current_number = number_info
        self.log(f"\n{'='*80}")
        self.log(f"NUMBER {index+1}/{total}: {number_info['number']}")
        self.log(f"Source: {number_info.get('filename', 'unknown')}")
        self.log(f"Context: {number_info['text'][:200]}...")
        self.log(f"{'='*80}\n")
    
    def log_iteration(self, iteration: int, reasoning: str, query: str):
        """Log a search iteration."""
        self.log(f"\n--- ITERATION {iteration} ---")
        self.log(f"REASONING: {reasoning}")
        self.log(f"QUERY: {query}")
    
    def log_search_results(self, num_chunks: int, chunks_retrieved: int):
        """Log search results."""
        self.log(f"SEARCH: Requested {num_chunks} chunks, retrieved {chunks_retrieved} new chunks")
    
    def log_decision(self, decision: str, reason: str):
        """Log a routing decision."""
        self.log(f"DECISION: {decision} - {reason}")
    
    def log_analysis(self, properties: Dict[str, Any]):
        """Log final analysis."""
        self.log(f"\nFINAL ANALYSIS:")
        for key, value in properties.items():
            if key not in ['text', 'number', 'filename', 'document_type']:
                self.log(f"  {key}: {value}")
    
    def log(self, message: str):
        """Write to log file."""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime("%H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")

# Global logger instance
logger = None


# Define the agent state with proper reducers
class AgentState(TypedDict):
    """State for the RAG agent.
    
    Uses Annotated types with reducers for lists that accumulate across the entire workflow.
    Lists that need to be reset per-number do NOT use reducers (default replacement behavior).
    
    State management strategy:
    - enhanced_results: Accumulates across all numbers (uses operator.add)
    - search_queries, gathered_context, reasoning_chain: Reset per number (no reducer, uses replacement)
    - current_index, iteration_count: Simple counters (no reducer)
    - current_filename: Tracks which document the current number came from
    """
    numbers: List[Dict[str, Any]]  # Numbers to analyze (immutable input)
    document_name: str  # Name of the bill (e.g., HB_1483_2025)
    vectorstore: Any  # Vectorstore for RAG retrieval (per source document)
    current_index: int  # Current number being processed
    current_filename: str  # Filename of current number's source document
    iteration_count: int  # Number of iterations for current number
    max_iterations: int  # Maximum iterations allowed
    # Per-number state (no reducer - allows replacement for reset)
    search_queries: List[str]  # Queries made for current number
    gathered_context: List[str]  # Context gathered for current number
    reasoning_chain: List[str]  # Chain of reasoning for why each query was made
    # Global accumulator (uses reducer to append across all numbers)
    enhanced_results: Annotated[List[Dict[str, Any]], operator.add]  # Final enhanced numbers
    messages: List[Any]  # Conversation history (currently unused)


# Simple vectorstore using Gemini embeddings
class GeminiVectorStore:
    """Vectorstore using Gemini embeddings API."""
    
    def __init__(self, documents: List[str]):
        self.documents = documents
        self.embeddings = self._create_embeddings(documents)
    
    def _create_embeddings(self, texts: List[str]) -> np.ndarray:
        """Create embeddings using Gemini API."""
        embeddings = []
        for text in texts:
            try:
                result = genai.embed_content(
                    model="models/embedding-001",
                    content=text,
                    task_type="retrieval_document"
                )
                embeddings.append(result['embedding'])
            except Exception as e:
                print(f"  ⚠️  Embedding error: {e}")
                # Use zero vector as fallback
                embeddings.append([0.0] * 768)
        return np.array(embeddings)
    
    def similarity_search(self, query: str, k: int = 3) -> List[Document]:
        """Search for similar documents using cosine similarity."""
        try:
            # Get query embedding
            result = genai.embed_content(
                model="models/embedding-001",
                content=query,
                task_type="retrieval_query"
            )
            query_embedding = np.array(result['embedding'])
            
            # Calculate cosine similarities
            similarities = np.dot(self.embeddings, query_embedding) / (
                np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
            )
            
            # Get top k results
            top_indices = np.argsort(similarities)[-k:][::-1]
            
            results = []
            for idx in top_indices:
                if similarities[idx] > 0.25:  # Lower threshold for better recall
                    results.append(Document(page_content=self.documents[idx]))
            
            return results
        except Exception as e:
            print(f"  ⚠️  Search error: {e}")
            return []


def create_vectorstore(document_path: Path) -> GeminiVectorStore:
    """Create a vectorstore from a document using Gemini embeddings."""
    
    # Read document
    with open(document_path, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
    
    # Split into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    
    chunks = text_splitter.split_text(text)
    
    # Create vectorstore with Gemini embeddings
    vectorstore = GeminiVectorStore(chunks)
    
    return vectorstore


def should_continue(state: AgentState) -> str:
    """Decide whether to continue searching or finalize the analysis.
    
    Uses dynamic thresholds that increase with iterations to gather more context.
    """
    # Check if we've processed all numbers
    if state['current_index'] >= len(state['numbers']):
        return "finalize"
    
    # Check if we've hit max iterations for current number
    if state['iteration_count'] >= state['max_iterations']:
        print(f"    ⏹️  Max iterations reached ({state['max_iterations']})")
        return "analyze"
    
    # SPEED OPTIMIZATION: Reduced thresholds for faster processing
    # Iteration 1: need 4 chunks, 2-3: need 6 chunks, 4+: need 8 chunks
    chunks_needed = 4 + (min(state['iteration_count'] // 2, 2) * 2)
    
    decision = ""
    reason = ""
    
    if len(state['gathered_context']) >= chunks_needed:
        decision = "analyze"
        reason = f"Gathered {len(state['gathered_context'])} chunks (needed {chunks_needed})"
        print(f"    ✓ {reason}, analyzing...")
    elif state['iteration_count'] >= 3 and len(state['gathered_context']) <= 2:
        decision = "analyze"
        reason = f"Limited context after {state['iteration_count']} searches"
        print(f"    ⚠️  {reason}, analyzing with what we have...")
    else:
        decision = "search"
        reason = f"Need more context ({len(state['gathered_context'])}/{chunks_needed} chunks)"
    
    # Log decision
    if logger:
        logger.log_decision(decision, reason)
    
    return decision


def generate_search_query(state: AgentState) -> Dict[str, Any]:
    """Generate a search query to find more context about the current number.
    
    Builds a reasoning chain to track why each query was made.
    Returns state updates that will be merged using the defined reducers.
    
    Raises:
        IndexError: If current_index is out of bounds
    """
    # Validate state
    if state['current_index'] >= len(state['numbers']):
        raise IndexError(f"current_index {state['current_index']} out of bounds for {len(state['numbers'])} numbers")
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    current_number = state['numbers'][state['current_index']]
    
    # Build reasoning context from previous iterations
    reasoning_context = ""
    if state['reasoning_chain']:
        reasoning_context = "\n\nPrevious reasoning and searches:\n" + "\n".join(
            f"{i+1}. {reason}" for i, reason in enumerate(state['reasoning_chain'])
        )
    
    # Build FULL context - NO TRUNCATION
    full_context = ""
    if state['gathered_context']:
        full_context = "\n\nContext gathered so far (" + str(len(state['gathered_context'])) + " chunks):\n"
        for i, ctx in enumerate(state['gathered_context'], 1):
            full_context += f"\nChunk {i}:\n{ctx}\n"
    else:
        full_context = "\n\nContext gathered so far: None yet"
    
    # Create prompt to generate search query with reasoning
    prompt = f"""You are analyzing a number from legislative document: {state['document_name']}
Source file: {state['current_filename']}

Number: {current_number['number']}
Immediate context: {current_number['text']}
{full_context}
{reasoning_context}

Based on what we know so far, generate:
1. A brief reasoning (1 sentence) explaining what information is still needed
2. A specific search query to find that information

Focus on finding:
- What this number represents (appropriation, fine, fee, penalty, etc.)
- Which agency, entity, or program is involved
- What fiscal year or time period applies
- What service, purpose, or violation it relates to

Format your response as:
REASONING: [your reasoning]
QUERY: [your search query]"""

    response = llm.invoke([HumanMessage(content=prompt)])
    response_text = response.content.strip()
    
    # Parse reasoning and query
    reasoning = ""
    search_query = response_text
    
    if "REASONING:" in response_text and "QUERY:" in response_text:
        parts = response_text.split("QUERY:")
        reasoning = parts[0].replace("REASONING:", "").strip()
        search_query = parts[1].strip()
    
    # Build reasoning entry
    reasoning_entry = f"Iteration {state['iteration_count'] + 1}: {reasoning} → Query: '{search_query}'"
    
    # Log to decision log
    if logger:
        logger.log_iteration(state['iteration_count'] + 1, reasoning, search_query)
    
    # Append to state (no reducer, so we manually append)
    return {
        'search_queries': state['search_queries'] + [search_query],
        'reasoning_chain': state['reasoning_chain'] + [reasoning_entry],
        'iteration_count': state['iteration_count'] + 1
    }


def search_document(state: AgentState) -> Dict[str, Any]:
    """Search the document using the latest query.
    
    Dynamically increases chunk retrieval as iterations progress.
    Returns state updates that will be merged using the defined reducers.
    Handles errors gracefully by returning empty results.
    """
    if not state['search_queries']:
        print("    ⚠️  No search queries available")
        return {}
    
    latest_query = state['search_queries'][-1]
    
    # Dynamic k: start with 3, increase by 2 each iteration (3, 5, 7, 9...)
    k = 3 + (state['iteration_count'] * 2)
    k = min(k, 15)  # Cap at 15 chunks per search
    
    try:
        # Search vectorstore with dynamic k
        results = state['vectorstore'].similarity_search(latest_query, k=k)
        
        # Collect new context (avoid duplicates)
        new_context = []
        for doc in results:
            if doc.page_content not in state['gathered_context']:
                new_context.append(doc.page_content)
        
        # Log search results
        if logger:
            logger.log_search_results(k, len(new_context))
        
        # Append to gathered_context (no reducer, so we manually append)
        if new_context:
            return {'gathered_context': state['gathered_context'] + new_context}
        return {}
    except Exception as e:
        print(f"    ⚠️  Search error: {e}")
        return {}


def analyze_number(state: AgentState) -> Dict[str, Any]:
    """Analyze the current number with all gathered context.
    
    Returns state updates that will be merged using the defined reducers.
    """
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    current_number = state['numbers'][state['current_index']]
    print(f"    🔍 Analyzing number {state['current_index']+1}/{len(state['numbers'])}: {current_number['number']}")
    
    # Create comprehensive analysis prompt with reasoning chain
    reasoning_summary = ""
    if state['reasoning_chain']:
        reasoning_summary = f"\n\nSearch reasoning chain:\n{chr(10).join(state['reasoning_chain'])}\n"
    
    # Build FULL context - NO TRUNCATION - Give model EVERYTHING
    full_context = ""
    if state['gathered_context']:
        full_context = f"\n\nAdditional context gathered ({len(state['gathered_context'])} chunks):\n"
        for i, ctx in enumerate(state['gathered_context'], 1):
            full_context += f"\n--- Chunk {i} ---\n{ctx}\n"
    else:
        full_context = "\n\nNo additional context gathered."
    
    prompt = f"""You are analyzing a number from legislative document: {state['document_name']}
Source file: {state['current_filename']}

Number: {current_number['number']}
Immediate context: {current_number['text']}
{reasoning_summary}
{full_context}

Based on ALL the context above AND the reasoning chain that guided our search, determine properties for this number.

IMPORTANT CONTEXT - Expending Agency Abbreviations:
- AGR: Department of Agriculture
- AGS: Department of Accounting and General Services
- ATG: Department of the Attorney General
- BED: Department of Business, Economic Development and Tourism
- BUF: Department of Budget and Finance
- CCA: Department of Commerce and Consumer Affairs
- DEF: Department of Defense
- EDN: Department of Education
- GOV: Office of the Governor
- HHL: Department of Hawaiian Home Lands
- HMS: Department of Human Services
- HRD: Department of Human Resources Development
- HTH: Department of Health
- LAW: Department of Law Enforcement
- LBR: Department of Labor and Industrial Relations
- LNR: Department of Land and Natural Resources
- LTG: Office of the Lieutenant Governor
- PSD: Department of Corrections and Rehabilitation
- SUB: Subsidies
- TAX: Department of Taxation
- TRN: Department of Transportation
- UOH: University of Hawaii
- CCH: City and County of Honolulu
- COH: County of Hawaii
- COK: County of Kauai
- COM: County of Maui

IMPORTANT CONTEXT - Means of Financing (Fund Types):
- A: general funds
- B: special funds
- C: general obligation bond fund
- D: general obligation bond fund with debt service cost to be paid from special funds
- E: revenue bond funds
- J: federal aid interstate funds
- K: federal aid primary funds
- L: federal aid secondary funds
- M: federal aid urban funds
- N: federal funds
- P: other federal funds
- R: private contributions
- S: county funds
- T: trust funds
- U: interdepartmental transfers
- V: American Rescue Plan funds
- W: revolving funds
- X: other funds

Possible properties (only provide when clearly applicable):
- description: Description of how the amount is used
- entity_name: Entity name (e.g., "DOE", "Hawaii Health", "University of Hawaii", "Department of Education")
- type: Type of amount (e.g., "appropriation", "penalty", "fee", "violation", "cost", "operating cost", "grant", "loan")
- fund_type: Fund type using abbreviations above (e.g., "A", "B", "N", "C")
- fiscal_year: Fiscal year(s) as array (e.g., ["2025", "2026"] or ["2025"])
- purpose: Brief description of what it is used for
- organization: Specific organization name (e.g., "Best Buddies Hawaii LLC", "Hua O Lahui")
- sunset_date: Sunset date if mentioned
- begin_date: Begin date if mentioned
- service_description: Brief description of service/project
- requesting_agency: Agency requesting funds (use abbreviations above)
- expending_agency: Agency expending funds (use abbreviations above)
- category: Category (e.g., "insurance", "enforcement", "budget", "infrastructure", "education", "health")
- unit: Unit type (e.g., "per_unit", "total", "minimum", "maximum", "per_violation")
- summary: A concise 1-2 sentence description (REQUIRED)

Return a JSON object with the number and its properties:
{{
  "number": {current_number['number']},
  "description": "...",
  "entity_name": "...",
  "type": "...",
  "fund_type": "...",
  "fiscal_year": "...",
  "purpose": "...",
  "organization": "...",
  "sunset_date": "...",
  "begin_date": "...",
  "service_description": "...",
  "requesting_agency": "...",
  "expending_agency": "...",
  "category": "...",
  "unit": "...",
  "summary": "...",
  "other_properties": "..."
}}

Return ONLY the JSON object, no other text."""

    response = llm.invoke([HumanMessage(content=prompt)])
    
    enhanced_item = None
    try:
        # Parse response
        response_text = response.content.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            # Remove first and last lines (``` markers)
            response_text = '\n'.join(lines[1:-1])
            # Remove language identifier if present
            if response_text.startswith('json'):
                response_text = response_text[4:].strip()
        
        result = json.loads(response_text)
        
        # Merge with original data
        enhanced_item = current_number.copy()
        for key, value in result.items():
            if key != 'number':
                enhanced_item[key] = value
        
        print(f"    ✅ Analyzed number {current_number['number']} - added {len(result)-1} properties")
        
        # Log analysis
        if logger:
            logger.log_analysis(enhanced_item)
        
    except json.JSONDecodeError as e:
        print(f"    ❌ JSON parse error for {current_number['number']}: {e}")
        print(f"    Response was: {response_text[:200]}...")
        # Keep original if analysis fails
        enhanced_item = current_number
    except Exception as e:
        print(f"    ⚠️  Error analyzing number {current_number['number']}: {e}")
        # Keep original if analysis fails
        enhanced_item = current_number
    
    # Return state updates for next number
    # The reset_for_next_number node will handle resetting search state
    return {
        'enhanced_results': [enhanced_item],
        'current_index': state['current_index'] + 1
    }


def finalize_results(state: AgentState) -> Dict[str, Any]:
    """Finalize and return results.
    
    This is the terminal node that doesn't modify state.
    """
    return {}


def check_next_number(state: AgentState) -> str:
    """Routing function to check if there are more numbers to process.
    
    This is a proper standalone routing function as per LangGraph best practices.
    """
    if state['current_index'] >= len(state['numbers']):
        return "finalize"
    return "continue"


def reset_for_next_number(state: AgentState) -> Dict[str, Any]:
    """Reset search state for the next number.
    
    This node resets the per-number state before starting a new search cycle.
    Also sets the current_filename from the number being processed.
    Since search_queries, gathered_context, and reasoning_chain don't use reducers,
    returning an empty list will REPLACE the existing list (not append to it).
    """
    # Get filename from current number
    current_filename = ""
    if state['current_index'] < len(state['numbers']):
        current_number = state['numbers'][state['current_index']]
        current_filename = current_number.get('filename', '')
        
        # Log start of new number
        if logger:
            logger.start_number(current_number, state['current_index'], len(state['numbers']))
    
    return {
        'iteration_count': 0,
        'current_filename': current_filename,
        'search_queries': [],
        'gathered_context': [],
        'reasoning_chain': []
    }


def create_rag_agent() -> StateGraph:
    """Create the LangGraph RAG agent.
    
    Graph structure:
    1. START -> reset_state (prepare for first/next number)
    2. reset_state -> generate_query (create search query)
    3. generate_query -> search (execute search)
    4. search -> should_continue (decide: more searches, analyze, or done)
    5. should_continue -> generate_query (more searches) OR analyze (enough context)
    6. analyze -> check_next_number (decide: more numbers or finalize)
    7. check_next_number -> reset_state (next number) OR finalize (done)
    8. finalize -> END
    """
    # Create the graph with proper state management
    workflow = StateGraph(AgentState)
    
    # Add all nodes
    workflow.add_node("reset_state", reset_for_next_number)
    workflow.add_node("generate_query", generate_search_query)
    workflow.add_node("search", search_document)
    workflow.add_node("analyze", analyze_number)
    workflow.add_node("finalize", finalize_results)
    
    # Set entry point using START constant
    workflow.add_edge(START, "reset_state")
    
    # Build the graph flow
    workflow.add_edge("reset_state", "generate_query")
    workflow.add_edge("generate_query", "search")
    
    # Conditional edge after search: continue searching, analyze, or finalize
    workflow.add_conditional_edges(
        "search",
        should_continue,
        {
            "search": "generate_query",  # Continue searching
            "analyze": "analyze",         # Enough context, analyze now
            "finalize": "finalize"        # No more numbers
        }
    )
    
    # After analyze, check if there are more numbers to process
    workflow.add_conditional_edges(
        "analyze",
        check_next_number,
        {
            "continue": "reset_state",  # More numbers, reset and continue
            "finalize": "finalize"       # All done
        }
    )
    
    # Terminal edge
    workflow.add_edge("finalize", END)
    
    return workflow.compile()


def group_by_filename(numbers: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group numbers by their filename."""
    grouped = defaultdict(list)
    for item in numbers:
        filename = item.get('filename', 'unknown')
        grouped[filename].append(item)
    return dict(grouped)


def read_numbers_file(bill_dir: Path) -> List[Dict[str, Any]]:
    """Read the numbers file from a bill directory."""
    numbers_file = bill_dir / f"{bill_dir.name}_numbers.json"
    
    if not numbers_file.exists():
        print(f"❌ Numbers file not found: {numbers_file}")
        return []
    
    with open(numbers_file, 'r') as f:
        return json.load(f)


def find_document_path(bill_dir: Path, filename: str) -> Path:
    """Find the full path to a document file."""
    for subdir in ['documents', 'fiscal_notes']:
        doc_path = bill_dir / subdir / filename
        if doc_path.exists():
            return doc_path
    return None


def process_single_number(number: Dict[str, Any], vectorstore: Any, bill_name: str, filename: str, index: int, total: int) -> Dict[str, Any]:
    """Process a single number individually for better accuracy.
    
    Args:
        number: Single number dictionary to enhance
        vectorstore: Vectorstore for this specific document
        bill_name: Name of the bill (e.g., HB_1483_2025)
        filename: Source filename
        index: Current number index (0-based)
        total: Total numbers in this file
    
    Returns:
        Enhanced number with properties
    """
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        
        # Log number start
        if logger:
            logger.log(f"\n{'='*80}")
            logger.log(f"NUMBER {index+1}/{total}: {number['number']}")
            logger.log(f"Source: {filename}")
            logger.log(f"Context: {number['text'][:200]}...")
            logger.log(f"{'='*80}\n")
        
        # Gather context for THIS number only
        query = f"{number['number']} {number['text']}"  # Full text, no truncation
        results = vectorstore.similarity_search(query, k=3)
        
        # Build context
        full_context = ""
        if results:
            full_context = f"\n\nRelevant context from {filename} ({len(results)} chunks):\n"
            for i, doc in enumerate(results, 1):
                full_context += f"\n--- Chunk {i} ---\n{doc.page_content}\n"
        
        # Create focused prompt for single number
        prompt = f"""You are analyzing a number from legislative document: {bill_name}
Source file: {filename}

Number: {number['number']}
Immediate context: {number['text']}
{full_context}

Based on the immediate context and additional context above, determine properties for this number.

IMPORTANT CONTEXT - Expending Agency Abbreviations:
- AGR: Department of Agriculture
- AGS: Department of Accounting and General Services
- ATG: Department of the Attorney General
- BED: Department of Business, Economic Development and Tourism
- BUF: Department of Budget and Finance
- CCA: Department of Commerce and Consumer Affairs
- DEF: Department of Defense
- EDN: Department of Education
- GOV: Office of the Governor
- HHL: Department of Hawaiian Home Lands
- HMS: Department of Human Services
- HRD: Department of Human Resources Development
- HTH: Department of Health
- LAW: Department of Law Enforcement
- LBR: Department of Labor and Industrial Relations
- LNR: Department of Land and Natural Resources
- LTG: Office of the Lieutenant Governor
- PSD: Department of Corrections and Rehabilitation
- SUB: Subsidies
- TAX: Department of Taxation
- TRN: Department of Transportation
- UOH: University of Hawaii
- CCH: City and County of Honolulu
- COH: County of Hawaii
- COK: County of Kauai
- COM: County of Maui

IMPORTANT CONTEXT - Means of Financing (Fund Types):
- A: general funds
- B: special funds
- C: general obligation bond fund
- D: general obligation bond fund with debt service cost to be paid from special funds
- E: revenue bond funds
- J: federal aid interstate funds
- K: federal aid primary funds
- L: federal aid secondary funds
- M: federal aid urban funds
- N: federal funds
- P: other federal funds
- R: private contributions
- S: county funds
- T: trust funds
- U: interdepartmental transfers
- V: American Rescue Plan funds
- W: revolving funds
- X: other funds

Possible properties (only provide when clearly applicable):
- description: Description of how the amount is used
- entity_name: Entity name (e.g., "DOE", "Hawaii Health", "University of Hawaii", "Department of Education")
- type: Type of amount (e.g., "appropriation", "penalty", "fee", "violation", "cost", "operating cost", "grant", "loan")
- fund_type: Fund type using abbreviations above (e.g., "A", "B", "N", "C")
- fiscal_year: Fiscal year(s) as array (e.g., ["2025", "2026"] or ["2025"])
- purpose: Brief description of what it is used for
- organization: Specific organization name (e.g., "Best Buddies Hawaii LLC", "Hua O Lahui")
- sunset_date: Sunset date if mentioned
- begin_date: Begin date if mentioned
- service_description: Brief description of service/project
- requesting_agency: Agency requesting funds (use abbreviations above)
- expending_agency: Agency expending funds (use abbreviations above)
- category: Category (e.g., "insurance", "enforcement", "budget", "infrastructure", "education", "health")
- unit: Unit type (e.g., "per_unit", "total", "minimum", "maximum", "per_violation")
- summary: A concise 1-2 sentence description (REQUIRED)

IMPORTANT: Pay close attention to phrases like:
- "no more than $X" = maximum fine (unit: "maximum")
- "no less than $X" = minimum fine (unit: "minimum")
- "$X fine" = specific fine amount (unit: "per_violation" or "per_offense")
- "up to $X" = maximum (unit: "maximum")

Return a JSON object with the number and its properties:
{{
  "number": {number['number']},
  "description": "...",
  "entity_name": "...",
  "type": "...",
  "fund_type": "...",
  "fiscal_year": ["2025"],
  "purpose": "...",
  "organization": "...",
  "sunset_date": "...",
  "begin_date": "...",
  "service_description": "...",
  "requesting_agency": "...",
  "expending_agency": "...",
  "category": "...",
  "unit": "...",
  "summary": "..."
}}

Return ONLY the JSON object, nothing else."""
        
        # Make LLM call for this number
        response = llm.invoke([HumanMessage(content=prompt)])
        response_text = response.content.strip()
        
        # Parse JSON response
        if response_text.startswith('```json'):
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif response_text.startswith('```'):
            response_text = response_text.split('```')[1].split('```')[0].strip()
        
        result = json.loads(response_text)
        
        # Merge with original data
        enhanced_item = number.copy()
        for key, value in result.items():
            if key != 'number':
                enhanced_item[key] = value
        
        # Log analysis
        if logger:
            logger.log(f"\nANALYSIS:")
            logger.log(f"  summary: {result.get('summary', 'N/A')}")
            for key, value in result.items():
                if key not in ['number', 'summary']:
                    logger.log(f"  {key}: {value}")
        
        return enhanced_item
        
    except Exception as e:
        print(f"  ⚠️  Error processing number {number.get('number', 'unknown')}: {e}")
        import traceback
        traceback.print_exc()
        return number


def enhance_numbers_with_rag(numbers: List[Dict[str, Any]], bill_dir: Path) -> List[Dict[str, Any]]:
    """Enhance numbers using RAG with per-document vectorstores and individual processing.
    
    Key improvements:
    1. Creates a separate vectorstore for each source document
    2. Numbers only search within their originating document
    3. Processes each number individually for better accuracy
    
    Args:
        numbers: List of number dictionaries to enhance
        bill_dir: Path to the bill directory
    """
    # Group by filename (each filename gets its own vectorstore)
    grouped = group_by_filename(numbers)
    
    print(f"📊 Found {len(grouped)} unique source documents to process")
    
    # Pre-create vectorstores for all documents
    print(f"\n📚 Creating vectorstores for each document...")
    vectorstores = {}
    for filename in grouped.keys():
        doc_path = find_document_path(bill_dir, filename)
        if doc_path:
            try:
                print(f"  - {filename}...")
                vectorstores[filename] = create_vectorstore(doc_path)
            except Exception as e:
                print(f"  ⚠️  Error creating vectorstore for {filename}: {e}")
        else:
            print(f"  ⚠️  Document not found: {filename}")
    
    print(f"\n✅ Created {len(vectorstores)} vectorstores")
    
    all_enhanced = []
    
    # Process each file group with its dedicated vectorstore
    for idx, (filename, numbers_group) in enumerate(grouped.items(), 1):
        print(f"\n[{idx}/{len(grouped)}] Processing {filename} ({len(numbers_group)} numbers)...")
        
        # Check if we have a vectorstore for this document
        if filename not in vectorstores:
            print(f"  ⚠️  No vectorstore available, keeping original data")
            all_enhanced.extend(numbers_group)
            continue
        
        try:
            # INDIVIDUAL PROCESSING: Process each number separately for better accuracy
            vectorstore = vectorstores[filename]
            enhanced_group = []
            
            print(f"  🔍 Processing {len(numbers_group)} numbers individually...")
            for i, number in enumerate(numbers_group):
                enhanced_number = process_single_number(
                    number,
                    vectorstore,
                    bill_dir.name,
                    filename,
                    i,
                    len(numbers_group)
                )
                enhanced_group.append(enhanced_number)
                print(f"    ✓ Completed {i+1}/{len(numbers_group)}")
            
            all_enhanced.extend(enhanced_group)
            print(f"  ✅ Processed {len(enhanced_group)} numbers from {filename}")
            
        except Exception as e:
            print(f"  ❌ Error processing {filename}: {e}")
            import traceback
            traceback.print_exc()
            all_enhanced.extend(numbers_group)
    
    return all_enhanced


def check_if_already_enhanced(bill_dir: Path) -> bool:
    """Check if a bill has already been enhanced."""
    enhanced_file = bill_dir / f"{bill_dir.name}_numbers_enhanced.json"
    return enhanced_file.exists()


def process_bill_directory(bill_dir: Path, force: bool = False) -> bool:
    """Process a single bill directory."""
    global logger
    
    print(f"\n{'='*60}")
    print(f"Processing: {bill_dir.name}")
    print(f"{'='*60}")
    
    # Initialize logger for this bill
    log_file = bill_dir / f"{bill_dir.name}_decision_log.txt"
    logger = DecisionLogger(log_file)
    logger.log(f"\n{'='*80}")
    logger.log(f"STARTING PROCESSING: {bill_dir.name}")
    logger.log(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.log(f"{'='*80}\n")
    
    # Check if already enhanced
    if not force and check_if_already_enhanced(bill_dir):
        print(f"⏭️  Already enhanced, skipping...")
        logger.log("Already enhanced, skipping...")
        return True
    
    # Read original numbers
    numbers = read_numbers_file(bill_dir)
    
    if not numbers:
        return False
    
    print(f"📄 Loaded {len(numbers)} number entries")
    
    # Enhance with RAG agent
    enhanced_numbers = enhance_numbers_with_rag(numbers, bill_dir)
    
    # Verify same length
    if len(enhanced_numbers) != len(numbers):
        print(f"❌ Error: Enhanced file has {len(enhanced_numbers)} entries but original has {len(numbers)}")
        return False
    
    # Write enhanced file
    output_file = bill_dir / f"{bill_dir.name}_numbers_enhanced.json"
    with open(output_file, 'w') as f:
        json.dump(enhanced_numbers, f, indent=2)
    
    print(f"✅ Created enhanced file: {output_file.name}")
    print(f"   Original entries: {len(numbers)}")
    print(f"   Enhanced entries: {len(enhanced_numbers)}")
    
    # Log completion
    logger.log(f"\n{'='*80}")
    logger.log(f"COMPLETED PROCESSING: {bill_dir.name}")
    logger.log(f"Original entries: {len(numbers)}")
    logger.log(f"Enhanced entries: {len(enhanced_numbers)}")
    logger.log(f"Decision log saved to: {log_file.name}")
    logger.log(f"{'='*80}\n")
    
    print(f"📝 Decision log saved to: {log_file.name}")
    
    return True


def main():
    """Main function to process all bills."""
    
    # Get the visuals/data directory
    data_dir = Path(__file__).parent / 'data'
    
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        return
    
    # Get all bill directories
    bill_dirs = [d for d in data_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
    bill_dirs.sort()
    
    print(f"🔍 Found {len(bill_dirs)} bill directories")
    
    # Process each bill
    success_count = 0
    for bill_dir in bill_dirs:
        if process_bill_directory(bill_dir):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"✨ Processing complete!")
    print(f"   Successfully processed: {success_count}/{len(bill_dirs)} bills")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
