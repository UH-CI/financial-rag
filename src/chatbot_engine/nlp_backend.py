"""
Advanced NLP Backend for Financial RAG System
Implements a multi-step pipeline with LLM-guided decision making
"""

import json
import logging
from enum import Enum
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from dataclasses import dataclass
import time
import google.generativeai as genai
from pathlib import Path
import re

# Handle both relative and absolute imports
try:
    from .retrieval import OnlineRetriever
    from .schemas import KG2RAGConfig, Document, Chunk
except ImportError:
    try:
        from retrieval import OnlineRetriever
        from schemas import KG2RAGConfig, Document, Chunk
    except ImportError:
        # Fallback - create minimal classes if imports fail
        OnlineRetriever = None
        class KG2RAGConfig:
            def __init__(self):
                pass
        class Document:
            def __init__(self, id, content):
                self.id = id
                self.content = content
        class Chunk:
            def __init__(self, id, content):
                self.id = id
                self.content = content

# Import settings separately to avoid directory creation issues
try:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from settings import settings
except ImportError:
    settings = None

logger = logging.getLogger(__name__)

class RetrievalMethod(Enum):
    """Available retrieval methods"""
    KEYWORD_MATCHING = "keyword_matching"
    DENSE_ENCODER = "dense_encoder"  
    SPARSE_ENCODER = "sparse_encoder"  # BM25
    MULTI_HOP_REASONING = "multi_hop_reasoning"

class QueryType(Enum):
    """Query classification types"""
    NEW_DOCUMENT = "new_document"
    FOLLOW_UP = "follow_up"

@dataclass
class GlobalState:
    """Maintains conversation state across queries"""
    conversation_id: str
    context_history: List[str]
    current_documents: List[str]  # Document IDs currently in context
    decision_history: List[Dict[str, Any]]
    source_references: List[Dict[str, Any]] = None  # Track sources for follow-up queries
    last_retrieval_method: Optional[RetrievalMethod] = None
    last_query_type: Optional[QueryType] = None
    
    def __post_init__(self):
        if self.source_references is None:
            self.source_references = []

@dataclass
class Step1Decision:
    """Decision from Step 1: Document Retrieval Planning"""
    query_type: QueryType
    num_documents: int
    retrieve_full_document: bool
    reasoning: str
    immediate_answer: Optional[str] = None
    can_answer_immediately: bool = False

@dataclass
class Step2QueryGeneration:
    """Output from Step 2: Query Generation"""
    search_terms: List[str]
    retrieval_method: RetrievalMethod
    reasoning: str

@dataclass
class RetrievalResult:
    """Result from retrieval step"""
    documents: List[Dict[str, Any]]
    chunks: List[Dict[str, Any]]
    method_used: RetrievalMethod
    scores: List[float]

class NLPBackend:
    """Main NLP Backend orchestrator"""
    
    def __init__(self, collection_managers: Dict[str, Any], config: Dict[str, Any]):
        self.collection_managers = collection_managers
        self.config = config
        self.collection_names = config["collections"]
        
        # Load real data files
        self.chunked_data_path = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/documents/chunked_text/bills/bills_chunked_no_sentence.json"
        self.extracted_data_path = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/documents/extracted_text/bills/filtered_documents.json"
        
        # Load chunked data for retrieval
        try:
            import json
            with open(self.chunked_data_path, 'r') as f:
                self.chunked_data = json.load(f)
            logger.info(f"Loaded {len(self.chunked_data)} chunks from real data")
        except Exception as e:
            logger.error(f"Failed to load chunked data: {e}")
            self.chunked_data = []
        
        # Load extracted data for full documents
        try:
            with open(self.extracted_data_path, 'r') as f:
                self.extracted_data = json.load(f)
            logger.info(f"Loaded {len(self.extracted_data)} full documents from real data")
        except Exception as e:
            logger.error(f"Failed to load extracted data: {e}")
            self.extracted_data = []
        
        # Initialize Gemini model
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Initialize retrieval components
        self.kg2rag_config = KG2RAGConfig()
        self.online_retriever = None  # Will be initialized when needed
        
        # Global state management
        self.states: Dict[str, GlobalState] = {}
        
        logger.info("NLP Backend initialized")

    def get_or_create_state(self, conversation_id: str) -> GlobalState:
        """Get or create global state for a conversation"""
        if conversation_id not in self.states:
            self.states[conversation_id] = GlobalState(
                conversation_id=conversation_id,
                context_history=[],
                current_documents=[],
                decision_history=[]
            )
        return self.states[conversation_id]

    def step1_document_retrieval_decision(self, user_query: str, state: GlobalState) -> Step1Decision:
        """
        Step 1: LLM decides number of documents, full/chunks, and follow-up classification
        """
        logger.info("Step 1: Document Retrieval Decision")
        
        # Build context from conversation history
        context_info = "None (new conversation)"
        if state.current_documents:
            context_info = f"Current documents in context: {', '.join(state.current_documents)}"
        
        if state.context_history:
            recent_context = state.context_history[-3:]  # Last 3 exchanges
            context_info = f"Recent conversation:\n" + "\n".join(recent_context)
            if state.current_documents:
                context_info += f"\nCurrent documents: {', '.join(state.current_documents)}"

        prompt = f"""You are an intelligent document retrieval planner for a financial RAG system.

SYSTEM CONTEXT:
- The backend has references to bills that will either be in chunks or full documents
- Available collections: {', '.join(self.collection_names)}
- Current conversation context: {context_info}

USER QUERY: "{user_query}"

TASK: Analyze the user's query and make decisions in this order:

1. IMMEDIATE ANSWER CHECK:
   - Can you provide a complete, accurate answer to this query using your general knowledge about legislative processes, common bill structures, or standard government procedures?
   - Only answer immediately if you're confident the answer is accurate and complete
   - Do NOT guess about specific bill contents, numbers, or details
   - If you can answer immediately, provide the answer and set "can_answer_immediately": true

2. QUERY TYPE CLASSIFICATION (if cannot answer immediately):
   - "new_document": User is asking for new information requiring document retrieval
   - "follow_up": User is asking follow-up questions about previously retrieved documents (skip retrieval steps)

3. DOCUMENT RETRIEVAL PLANNING (if new_document):
   - How many documents to retrieve (1-10)?
   - Choose a single number (1-10) based on query complexity
   - Simple factual questions: 1-3 documents
   - Complex analysis questions: 4-7 documents
   - Comprehensive research questions: 8-10 documents

4. RETRIEVAL SCOPE (if new_document):
   - "retrieve_full_document": true/false
   - Use full documents for: comprehensive analysis, document structure matters, need complete context
   - Use chunks for: specific facts, targeted information, efficiency

RESPOND IN PLAIN JSON FORMAT (no markdown, no code blocks):
{{
    "can_answer_immediately": <true/false>,
    "immediate_answer": "<answer if can_answer_immediately is true, otherwise null>",
    "query_type": "new_document" or "follow_up" or null,
    "num_documents": <number 1-10 or null>,
    "retrieve_full_document": <true/false or null>,
    "reasoning": "Explain your decisions clearly"
}}"""

        try:
            logger.debug(f"\n=== STEP 1 LLM PROMPT ===\n{prompt}\n=== END PROMPT ===")
            response = self.model.generate_content(prompt)
            logger.debug(f"\n=== STEP 1 LLM RESPONSE ===\n{response.text}\n=== END RESPONSE ===")
            
            # Clean the response text to handle markdown formatting
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]  # Remove ```json
            if response_text.endswith('```'):
                response_text = response_text[:-3]  # Remove ```
            response_text = response_text.strip()
            
            decision_data = json.loads(response_text)
            
            # Check if LLM can answer immediately
            if decision_data.get("can_answer_immediately", False):
                decision = Step1Decision(
                    query_type=QueryType.FOLLOW_UP,  # Skip retrieval
                    num_documents=0,
                    retrieve_full_document=False,
                    reasoning=decision_data["reasoning"],
                    immediate_answer=decision_data.get("immediate_answer"),
                    can_answer_immediately=True
                )
            else:
                decision = Step1Decision(
                    query_type=QueryType(decision_data["query_type"]),
                    num_documents=decision_data["num_documents"],
                    retrieve_full_document=decision_data["retrieve_full_document"],
                    reasoning=decision_data["reasoning"],
                    immediate_answer=None,
                    can_answer_immediately=False
                )
            
            # Update state
            state.decision_history.append({
                "step": "document_retrieval_decision",
                "decision": decision_data,
                "timestamp": time.time()
            })
            state.last_query_type = decision.query_type
            
            if decision.can_answer_immediately:
                logger.info(f"Step 1 Decision: Can answer immediately - {decision.immediate_answer[:50]}...")
            else:
                logger.info(f"Step 1 Decision: {decision.query_type.value}, {decision.num_documents} docs, full_doc: {decision.retrieve_full_document}")
            return decision
            
        except Exception as e:
            logger.error(f"Error in Step 1: {e}")
            # Fallback decision
            return Step1Decision(
                query_type=QueryType.NEW_DOCUMENT,
                num_documents=3,
                retrieve_full_document=False,
                reasoning=f"Fallback decision due to error: {str(e)}",
                immediate_answer=None,
                can_answer_immediately=False
            )

    def step2_query_generation(self, user_query: str, step1_decision: Step1Decision, state: GlobalState) -> Step2QueryGeneration:
        """
        Step 2: LLM generates search keywords/phrases and picks retrieval method
        """
        logger.info("Step 2: Query Generation")
        
        prompt = f"""You are a query generation expert for financial document retrieval.

USER QUERY: "{user_query}"
RETRIEVAL CONTEXT: Need {step1_decision.num_documents} documents, {'full documents' if step1_decision.retrieve_full_document else 'chunks'}

TASK: Generate optimal search terms and select the best retrieval method.

1. SEARCH TERMS (3-5 terms):
   Extract and generate 3-5 SHORT, SPECIFIC search terms. Focus on:
   - EXACT bill numbers (HB100, SB1367, etc.) - extract these PRECISELY
   - Budget line items, program codes, department names
   - Dollar amounts, fiscal years, appropriations
   - Key topics (healthcare, education, transportation)
   - UNIQUE, DISTINCTIVE keywords that differentiate documents
   - DO NOT use generic terms like "bill", "act", "purpose", "legislation" unless explicitly mentioned by user
   - DO NOT use full sentences or long phrases
   
   Examples:
   - "What does HB100 say?" → ["HB100", "provisions", "requirements"]
   - "SB1367 healthcare funding" → ["SB1367", "healthcare", "funding", "appropriation"]
   - "education budget 2025" → ["education", "budget", "2025", "appropriation"]
   - "HB1462 purpose" → ["HB1462", "objectives", "intent"] (avoid "purpose" unless user specifically asks for it)

2. RETRIEVAL METHOD (pick 1 of 4):
   - "keyword_matching": Use for specific bill numbers, codes, exact terms
   - "dense_encoder": Use for conceptual/semantic queries about topics
   - "sparse_encoder": Use for statistical term frequency analysis
   - "multi_hop_reasoning": Use for complex relationship queries

RESPOND IN PLAIN JSON FORMAT (no markdown, no code blocks):
{{
    "search_terms": ["term1", "term2", "term3", "term4", "term5"],
    "retrieval_method": "one of the 4 methods above",
    "reasoning": "Explain why you chose these terms and this method"
}}"""

        try:
            logger.debug(f"\n=== STEP 2 LLM PROMPT ===\n{prompt}\n=== END PROMPT ===")
            response = self.model.generate_content(prompt)
            logger.debug(f"\n=== STEP 2 LLM RESPONSE ===\n{response.text}\n=== END RESPONSE ===")
            
            # Clean the response text to handle markdown formatting
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]  # Remove ```json
            if response_text.endswith('```'):
                response_text = response_text[:-3]  # Remove ```
            response_text = response_text.strip()
            
            generation_data = json.loads(response_text)
            
            # Extract bill numbers using regex as fallback if LLM didn't extract them properly
            import re
            bill_pattern = r'\b([HS]B\d+)\b'
            extracted_bills = re.findall(bill_pattern, user_query.upper())
            
            search_terms = generation_data["search_terms"]
            
            # If we found bill numbers but they're not in search terms, add them
            for bill in extracted_bills:
                if not any(bill.lower() in term.lower() for term in search_terms):
                    search_terms.insert(0, bill)  # Add at beginning for priority
            
            # If search terms contain full sentences, try to extract key terms
            refined_terms = []
            for term in search_terms:
                if len(term.split()) > 3:  # If term is too long (likely a sentence)
                    # Extract bill numbers, key words
                    bills_in_term = re.findall(bill_pattern, term.upper())
                    refined_terms.extend(bills_in_term)
                    # Extract other key words (simple approach)
                    words = term.lower().split()
                    key_words = [w for w in words if len(w) > 3 and w not in ['what', 'does', 'about', 'tell', 'bring', 'and', 'the', 'is', 'it']]
                    refined_terms.extend(key_words[:2])  # Take first 2 key words
                else:
                    refined_terms.append(term)
            
            # Remove duplicates and limit to 5 terms
            final_terms = list(dict.fromkeys(refined_terms))[:5]
            
            query_gen = Step2QueryGeneration(
                search_terms=final_terms,
                retrieval_method=RetrievalMethod(generation_data["retrieval_method"]),
                reasoning=generation_data["reasoning"] + f" (Enhanced with regex extraction: {extracted_bills})"
            )
            
            # Update state
            state.decision_history.append({
                "step": "query_generation", 
                "decision": generation_data,
                "timestamp": time.time()
            })
            state.last_retrieval_method = query_gen.retrieval_method
            
            logger.info(f"Step 2 Generated: {len(query_gen.search_terms)} terms, method: {query_gen.retrieval_method.value}")
            logger.info(f"Final search terms: {query_gen.search_terms}")
            return query_gen
            
        except Exception as e:
            logger.error(f"Error in Step 2: {e}")
            
            # Enhanced fallback with regex extraction
            import re
            bill_pattern = r'\b([HS]B\d+)\b'
            extracted_bills = re.findall(bill_pattern, user_query.upper())
            
            # Extract key terms from query
            words = user_query.lower().split()
            key_words = [w for w in words if len(w) > 3 and w not in ['what', 'does', 'about', 'tell', 'bring', 'and', 'the', 'is', 'it', 'can', 'you']]
            
            # Combine extracted bills and key words
            fallback_terms = extracted_bills + key_words[:3]  # Bills + up to 3 key words
            
            # If no good terms found, use the full query
            if not fallback_terms:
                fallback_terms = [user_query]
            
            # Choose method based on whether we found bill numbers
            method = RetrievalMethod.KEYWORD_MATCHING if extracted_bills else RetrievalMethod.DENSE_ENCODER
            
            return Step2QueryGeneration(
                search_terms=fallback_terms,
                retrieval_method=method,
                reasoning=f"Fallback generation due to error: {str(e)}. Extracted bills: {extracted_bills}"
            )

    def step3_execute_retrieval(self, query_gen: Step2QueryGeneration, step1_decision: Step1Decision) -> RetrievalResult:
        """
        Step 3: Execute retrieval using the selected method
        """
        logger.info(f"Step 3: Execute Retrieval using {query_gen.retrieval_method.value}")
        
        method = query_gen.retrieval_method
        search_terms = query_gen.search_terms
        num_docs = step1_decision.num_documents
        
        if method == RetrievalMethod.KEYWORD_MATCHING:
            return self._keyword_matching_retrieval(search_terms, num_docs)
        elif method == RetrievalMethod.DENSE_ENCODER:
            return self._dense_encoder_retrieval(search_terms, num_docs)
        elif method == RetrievalMethod.SPARSE_ENCODER:
            return self._sparse_encoder_retrieval(search_terms, num_docs)
        elif method == RetrievalMethod.MULTI_HOP_REASONING:
            return self._multi_hop_reasoning_retrieval(search_terms, num_docs)
        else:
            logger.warning(f"Unknown retrieval method: {method}")
            return self._dense_encoder_retrieval(search_terms, num_docs)

    def _keyword_matching_retrieval(self, search_terms: List[str], num_docs: int) -> RetrievalResult:
        """Keyword matching retrieval using source_identifier and content matching"""
        logger.info("Executing keyword matching retrieval")
        
        all_results = []
        
        # Search through real chunked data
        for chunk in self.chunked_data:
            content_lower = chunk['text'].lower()
            source_id_lower = chunk['source_identifier'].lower()
            
            total_score = 0
            matched_terms = []
            
            for term in search_terms:
                term_lower = term.lower()
                
                # Score based on source_identifier match (much higher weight for exact bill matches)
                source_score = 0
                if term_lower in source_id_lower:
                    # Give extremely high weight to bill number matches
                    if len(term) >= 4 and (term.upper().startswith('HB') or term.upper().startswith('SB')):
                        source_score = 1000  # Very high weight for bill numbers
                    else:
                        source_score = 50  # High weight for other source identifier matches
                    matched_terms.append(f"source:{term}")
                
                # Score based on content match
                content_score = content_lower.count(term_lower)
                if content_score > 0:
                    matched_terms.append(f"content:{term}")
                
                total_score += source_score + content_score
            
            if total_score > 0:
                result = {
                    'content': chunk['text'],
                    'metadata': {
                        'source_identifier': chunk['source_identifier'],
                        'chunk_id': chunk['chunk_id'],
                        'chunking_method': chunk['chunking_method'],
                        'source_page': chunk.get('source_page', 0)
                    },
                    'score': total_score,
                    'keyword_score': total_score,
                    'matched_terms': matched_terms,
                    'chunk_id': f"chunk_{chunk['chunk_id']}"
                }
                all_results.append(result)
        
        # Sort by keyword score and take top results
        all_results.sort(key=lambda x: x.get('keyword_score', 0), reverse=True)
        top_results = all_results[:num_docs]
        
        return RetrievalResult(
            documents=[],
            chunks=top_results,
            method_used=RetrievalMethod.KEYWORD_MATCHING,
            scores=[r.get('keyword_score', 0) for r in top_results]
        )

    def _dense_encoder_retrieval(self, search_terms: List[str], num_docs: int) -> RetrievalResult:
        """Dense encoder retrieval using hypothetical answer approach for better semantic matching"""
        logger.info("Executing dense encoder retrieval with hypothetical answer approach")
        
        # Generate a hypothetical answer based on the search terms
        hypothetical_answer = self._generate_hypothetical_answer(search_terms)
        logger.info(f"Generated hypothetical answer: {hypothetical_answer[:100]}...")
        
        all_results = []
        
        # Use the hypothetical answer for semantic search instead of raw search terms
        search_query = hypothetical_answer
        
        for collection_name in self.collection_names:
            try:
                if collection_name in self.collection_managers:
                    manager = self.collection_managers[collection_name]
                    # Use existing semantic search functionality with hypothetical answer
                    results = manager.search_similar_chunks(search_query, num_docs * 2)
                    
                    for result in results:
                        result['collection'] = collection_name
                        result['search_query'] = search_query
                        result['hypothetical_answer'] = hypothetical_answer
                        
                    all_results.extend(results)
                    
            except Exception as e:
                logger.error(f"Error in dense encoder retrieval for {collection_name}: {e}")
        
        # Sort by similarity score and take top results
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        top_results = all_results[:num_docs]
        
        return RetrievalResult(
            documents=[],
            chunks=top_results,
            method_used=RetrievalMethod.DENSE_ENCODER,
            scores=[r.get('score', 0) for r in top_results]
        )
    
    def _generate_hypothetical_answer(self, search_terms: List[str]) -> str:
        """Generate a hypothetical answer based on search terms for better semantic matching"""
        try:
            # Create a prompt to generate a hypothetical answer
            terms_str = ", ".join(search_terms)
            prompt = f"""Based on these search terms: {terms_str}
            
Generate a brief, realistic hypothetical answer (2-3 sentences) that would likely appear in a legislative document addressing these topics. Focus on the specific information being sought.
            
Example:
            Search terms: ["manufacturers", "exclude information", "repair facilities"]
            Hypothetical answer: "Manufacturers may exclude proprietary diagnostic information and trade secrets from disclosure to independent repair facilities. However, basic repair procedures and safety-related technical data must be provided to authorized repair centers."
            
Generate a hypothetical answer:"""
            
            response = self.model.generate_content(prompt)
            hypothetical_answer = response.text.strip()
            
            # Clean up any quotes or formatting
            if hypothetical_answer.startswith('"') and hypothetical_answer.endswith('"'):
                hypothetical_answer = hypothetical_answer[1:-1]
                
            return hypothetical_answer
            
        except Exception as e:
            logger.error(f"Error generating hypothetical answer: {e}")
            # Enhanced fallback with domain-specific hypothetical answers
            return self._create_fallback_hypothetical_answer(search_terms)
    
    def _create_fallback_hypothetical_answer(self, search_terms: List[str]) -> str:
        """Create a domain-specific hypothetical answer when LLM fails"""
        # Default fallback
        return f"This legislation addresses {', '.join(search_terms[:3])} and establishes relevant requirements, procedures, and standards for implementation."

    def _sparse_encoder_retrieval(self, search_terms: List[str], num_docs: int) -> RetrievalResult:
        """BM25 sparse encoder retrieval"""
        logger.info("Executing BM25 sparse encoder retrieval")
        
        # For now, implement a simple TF-IDF-like approach
        # In a full implementation, you'd use a proper BM25 library like rank_bm25
        
        all_results = []
        
        for term in search_terms:
            for collection_name in self.collection_names:
                try:
                    if collection_name in self.collection_managers:
                        manager = self.collection_managers[collection_name]
                        results = manager.search_similar_chunks(term, num_docs * 3)
                        
                        # Simple BM25-like scoring based on term frequency
                        for result in results:
                            content = result['content'].lower()
                            term_lower = term.lower()
                            
                            # Calculate term frequency
                            tf = content.count(term_lower)
                            doc_length = len(content.split())
                            
                            # Simple BM25 approximation
                            k1, b = 1.5, 0.75
                            avgdl = 100  # Assume average document length
                            
                            bm25_score = tf * (k1 + 1) / (tf + k1 * (1 - b + b * doc_length / avgdl))
                            result['bm25_score'] = bm25_score
                            result['search_term'] = term
                            
                        all_results.extend(results)
                        
                except Exception as e:
                    logger.error(f"Error in BM25 retrieval for {collection_name}: {e}")
        
        # Sort by BM25 score
        all_results.sort(key=lambda x: x.get('bm25_score', 0), reverse=True)
        top_results = all_results[:num_docs]
        
        return RetrievalResult(
            documents=[],
            chunks=top_results,
            method_used=RetrievalMethod.SPARSE_ENCODER,
            scores=[r.get('bm25_score', 0) for r in top_results]
        )

    def _multi_hop_reasoning_retrieval(self, search_terms: List[str], num_docs: int) -> RetrievalResult:
        """Multi-hop reasoning using knowledge graph"""
        logger.info("Executing multi-hop reasoning retrieval")
        
        try:
            # Use the existing KG2RAG system
            if self.online_retriever is None:
                # Initialize if not already done
                # This would require proper setup with chunks and knowledge graph
                logger.warning("Multi-hop reasoning not fully initialized, falling back to dense encoder")
                return self._dense_encoder_retrieval(search_terms, num_docs)
            
            # Combine search terms for KG query
            combined_query = " ".join(search_terms)
            result = self.online_retriever.retrieve(combined_query)
            
            # Convert KG2RAG result to our format
            chunks = []
            for chunk in result.expanded_chunks[:num_docs]:
                chunks.append({
                    'content': chunk.content,
                    'metadata': chunk.metadata,
                    'score': 1.0,  # KG2RAG doesn't provide direct scores
                    'chunk_id': chunk.id
                })
            
            return RetrievalResult(
                documents=[],
                chunks=chunks,
                method_used=RetrievalMethod.MULTI_HOP_REASONING,
                scores=[1.0] * len(chunks)
            )
            
        except Exception as e:
            logger.error(f"Error in multi-hop reasoning: {e}")
            # Fallback to dense encoder
            return self._dense_encoder_retrieval(search_terms, num_docs)

    def step4_document_selection(self, retrieval_result: RetrievalResult, step1_decision: Step1Decision) -> List[Dict[str, Any]]:
        """
        Step 4: Select full documents or chunks based on Step 1 decision
        """
        logger.info("Step 4: Document Selection")
        
        if step1_decision.retrieve_full_document:
            # Get full documents using source_identifier from extracted data
            full_documents = []
            seen_source_ids = set()
            
            for chunk in retrieval_result.chunks:
                source_identifier = chunk.get('metadata', {}).get('source_identifier')
                if source_identifier and source_identifier not in seen_source_ids:
                    seen_source_ids.add(source_identifier)
                    
                    # Find the full document in extracted data
                    full_doc_content = None
                    for doc in self.extracted_data:
                        # Match by extracting filename from URL
                        doc_filename = doc['url'].split('/')[-1] if doc.get('url') else ''
                        if doc_filename == source_identifier:
                            full_doc_content = doc['text']
                            break
                    
                    if full_doc_content:
                        full_documents.append({
                            'document_id': source_identifier,
                            'content': full_doc_content,
                            'metadata': {
                                'source_identifier': source_identifier,
                                'url': next((doc['url'] for doc in self.extracted_data if doc['url'].split('/')[-1] == source_identifier), ''),
                                'text_length': len(full_doc_content)
                            },
                            'source': 'full_document'
                        })
                    else:
                        # Fallback to chunk content if full document not found
                        full_documents.append({
                            'document_id': source_identifier,
                            'content': chunk['content'],
                            'metadata': chunk.get('metadata', {}),
                            'source': 'full_document_fallback'
                        })
            
            logger.info(f"Selected {len(full_documents)} full documents")
            return full_documents
        else:
            # Return the chunks as-is
            for chunk in retrieval_result.chunks:
                chunk['source'] = 'chunk'
            logger.info(f"Selected {len(retrieval_result.chunks)} chunks")
            return retrieval_result.chunks

    def step5_rerank_chunks(self, user_query: str, selected_content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Step 5: Rerank chunks/documents for better relevance using LLM
        """
        logger.info("Step 5: Reranking for Relevance")
        
        if not selected_content or selected_content[0].get('source') == 'full_document':
            # Skip reranking for full documents
            logger.info("Skipping reranking for full documents")
            return selected_content
        
        # Use LLM to rerank chunks based on relevance to user query
        try:
            # Prepare content for reranking
            content_items = []
            for i, item in enumerate(selected_content):
                content_items.append(f"Item {i+1}: {item['content'][:500]}...")  # Truncate for prompt
            
            rerank_prompt = f"""You are a relevance ranking expert. Given a user query and a list of text chunks, rank them by relevance.

USER QUERY: "{user_query}"

CONTENT ITEMS:
{chr(10).join(content_items)}

TASK: Rank the items from most relevant (1) to least relevant ({len(content_items)}) based on how well they answer the user's query.

RESPOND IN PLAIN JSON FORMAT (no markdown, no code blocks):
{{
    "rankings": [item_number_most_relevant, item_number_second_most_relevant, ...],
    "reasoning": "Brief explanation of ranking decisions"
}}"""

            logger.debug(f"\n=== STEP 5 LLM PROMPT ===\n{rerank_prompt}\n=== END PROMPT ===")
            response = self.model.generate_content(rerank_prompt)
            logger.debug(f"\n=== STEP 5 LLM RESPONSE ===\n{response.text}\n=== END RESPONSE ===")
            
            # Clean the response text to handle markdown formatting
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]  # Remove ```json
            if response_text.endswith('```'):
                response_text = response_text[:-3]  # Remove ```
            response_text = response_text.strip()
            
            ranking_data = json.loads(response_text)
            
            # Reorder based on rankings
            rankings = ranking_data["rankings"]
            reranked_content = []
            
            for rank in rankings:
                if 1 <= rank <= len(selected_content):
                    item = selected_content[rank - 1].copy()
                    item['rerank_position'] = len(reranked_content) + 1
                    reranked_content.append(item)
            
            logger.info(f"Reranked {len(reranked_content)} items")
            return reranked_content
            
        except Exception as e:
            logger.error(f"Error in reranking: {e}")
            # Return original order if reranking fails
            return selected_content

    def step6_generate_answer(self, user_query: str, reranked_content: List[Dict[str, Any]], state: GlobalState) -> Dict[str, Any]:
        """
        Step 6: Generate final answer using LLM with context and history
        """
        logger.info("Step 6: Final Answer Generation")
        
        # Prepare context from reranked content
        context_parts = []
        sources = []
        
        for i, item in enumerate(reranked_content):
            context_parts.append(f"Source {i+1}:")
            context_parts.append(f"Content: {item['content']}")
            context_parts.append(f"Type: {item.get('source', 'unknown')}")
            context_parts.append("---")
            
            sources.append({
                'content': item['content'],
                'metadata': item.get('metadata', {}),
                'source_type': item.get('source', 'unknown'),
                'rank': item.get('rerank_position', i+1)
            })
        
        context = "\n".join(context_parts)
        
        # Include conversation history
        history_context = ""
        if state.context_history:
            recent_history = state.context_history[-2:]  # Last 2 exchanges
            history_context = f"\nCONVERSATION HISTORY:\n" + "\n".join(recent_history)
        
        answer_prompt = f"""You are a knowledgeable financial assistant providing comprehensive answers based on retrieved documents.

USER QUERY: "{user_query}"

RETRIEVED CONTEXT:
{context}
{history_context}

INSTRUCTIONS:
1. Provide a direct, comprehensive answer to the user's question
2. Reference specific information from the sources when possible
3. Use clear formatting (bullet points, lists, tables) for readability
4. If the sources don't fully answer the question, explain what information is available
5. Be conversational but authoritative
6. Focus on actionable information
7. Cite sources by number when referencing specific information

Generate a helpful, well-structured response:"""

        try:
            logger.debug(f"\n=== STEP 6 LLM PROMPT ===\n{answer_prompt}\n=== END PROMPT ===")
            response = self.model.generate_content(answer_prompt)
            logger.debug(f"\n=== STEP 6 LLM RESPONSE ===\n{response.text}\n=== END RESPONSE ===")
            
            # Update conversation history
            state.context_history.append(f"Q: {user_query}")
            state.context_history.append(f"A: {response.text[:200]}...")  # Truncated for history
            
            # Keep history manageable
            if len(state.context_history) > 10:
                state.context_history = state.context_history[-10:]
            
            return {
                "answer": response.text,
                "sources": sources,
                "context_used": len(reranked_content),
                "conversation_id": state.conversation_id,
                "processing_steps": len(state.decision_history)
            }
            
        except Exception as e:
            logger.error(f"Error generating final answer: {e}")
            return {
                "answer": f"I found relevant information but encountered an error generating the response: {str(e)}",
                "sources": sources,
                "context_used": len(reranked_content),
                "conversation_id": state.conversation_id,
                "processing_steps": len(state.decision_history)
            }

    def process_query(self, user_query: str, conversation_id: str = "default") -> Dict[str, Any]:
        """
        Main method: Execute the complete NLP backend pipeline
        """
        start_time = time.time()
        logger.info(f"\n{'='*80}")
        logger.info(f"🧠 NLP BACKEND QUERY PROCESSING STARTED")
        logger.info(f"Query: '{user_query}'")
        logger.info(f"Conversation ID: {conversation_id}")
        logger.info(f"{'='*80}")
        
        # Set logging level to DEBUG for this query to capture all LLM interactions
        original_level = logger.level
        logger.setLevel(logging.DEBUG)
        
        try:
            # Get or create conversation state
            state = self.get_or_create_state(conversation_id)
            
            # Step 1: Document Retrieval Decision
            step1_decision = self.step1_document_retrieval_decision(user_query, state)
            
            # Check if LLM can answer immediately
            if step1_decision.can_answer_immediately:
                logger.info("LLM can answer immediately, skipping document retrieval")
                processing_time = time.time() - start_time
                
                # Restore original logging level
                logger.setLevel(original_level)
                
                return {
                    "answer": step1_decision.immediate_answer,
                    "sources": [],
                    "context_used": 0,
                    "conversation_id": conversation_id,
                    "processing_steps": 1,
                    "processing_time": processing_time,
                    "immediate_response": True,
                    "pipeline_steps": {
                        "step1_decision": {
                            "can_answer_immediately": True,
                            "reasoning": step1_decision.reasoning
                        }
                    }
                }
            
            # Check if this is a follow-up query
            if step1_decision.query_type == QueryType.FOLLOW_UP:
                logger.info("Follow-up query detected, generating response from existing context")
                # Generate response using existing context
                existing_context = [{"content": ctx, "source": "history"} for ctx in state.context_history[-4:]]
                return self.step6_generate_answer(user_query, existing_context, state)
            
            # Step 2: Query Generation
            step2_query_gen = self.step2_query_generation(user_query, step1_decision, state)
            
            # Step 3: Execute Retrieval
            retrieval_result = self.step3_execute_retrieval(step2_query_gen, step1_decision)
            
            # Step 4: Document Selection
            selected_content = self.step4_document_selection(retrieval_result, step1_decision)
            
            # Step 5: Reranking
            reranked_content = self.step5_rerank_chunks(user_query, selected_content)
            
            # Step 6: Generate Answer
            final_result = self.step6_generate_answer(user_query, reranked_content, state)
            
            # Add processing metadata
            processing_time = time.time() - start_time
            final_result.update({
                "processing_time": processing_time,
                "pipeline_steps": {
                    "step1_decision": step1_decision.__dict__,
                    "step2_query_generation": step2_query_gen.__dict__,
                    "step3_retrieval_method": retrieval_result.method_used.value,
                    "step4_content_selected": len(selected_content),
                    "step5_reranked": len(reranked_content)
                }
            })
            
            # Update state with new documents and source references
            if selected_content:
                new_doc_ids = [item.get('metadata', {}).get('id', f"doc_{i}") 
                              for i, item in enumerate(selected_content)]
                state.current_documents.extend(new_doc_ids)
                # Keep only recent documents
                state.current_documents = list(set(state.current_documents[-20:]))
                
                # Track source references for follow-up queries
                for item in selected_content:
                    source_ref = {
                        "source_identifier": item.get('metadata', {}).get('source_identifier', 'unknown'),
                        "content_preview": item.get('content', '')[:200],
                        "timestamp": time.time(),
                        "query": user_query
                    }
                    state.source_references.append(source_ref)
                
                # Keep only recent source references
                state.source_references = state.source_references[-10:]
            
            # Restore original logging level
            logger.setLevel(original_level)
            
            logger.info(f"\n{'='*80}")
            logger.info(f"✅ NLP BACKEND QUERY PROCESSING COMPLETED")
            logger.info(f"Processing time: {processing_time:.2f} seconds")
            logger.info(f"LLM calls made: Steps 1, 2, 5, 6 (4 total)")
            logger.info(f"{'='*80}\n")
            
            return final_result
            
        except Exception as e:
            # Restore original logging level on error
            logger.setLevel(original_level)
            
            logger.error(f"\n{'='*80}")
            logger.error(f"❌ NLP BACKEND ERROR")
            logger.error(f"Error: {str(e)}")
            logger.error(f"{'='*80}\n")
            
            return {
                "answer": f"I encountered an error while processing your query: {str(e)}",
                "sources": [],
                "context_used": 0,
                "conversation_id": conversation_id,
                "processing_steps": 0,
                "error": str(e)
            }

    def get_conversation_state(self, conversation_id: str) -> Dict[str, Any]:
        """Get current state of a conversation"""
        if conversation_id in self.states:
            state = self.states[conversation_id]
            return {
                "conversation_id": conversation_id,
                "current_documents": state.current_documents,
                "decision_count": len(state.decision_history),
                "context_length": len(state.context_history),
                "last_retrieval_method": state.last_retrieval_method.value if state.last_retrieval_method else None,
                "last_query_type": state.last_query_type.value if state.last_query_type else None
            }
        return {"conversation_id": conversation_id, "status": "not_found"}

    def reset_conversation(self, conversation_id: str) -> bool:
        """Reset conversation state"""
        if conversation_id in self.states:
            del self.states[conversation_id]
            logger.info(f"Reset conversation: {conversation_id}")
            return True
        return False
