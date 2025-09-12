"""
Test Script for NLP Backend
Demonstrates the 6-step pipeline with various query types
"""

import json
import time
import logging
from pathlib import Path
import sys
import os

# Add src to path for imports
sys.path.append(str(Path(__file__).parent))

try:
    from .nlp_backend import NLPBackend, RetrievalMethod, QueryType
    from ..settings import settings
    import google.generativeai as genai
except ImportError:
    try:
        from nlp_backend import NLPBackend, RetrievalMethod, QueryType
        sys.path.append(str(Path(__file__).parent.parent))
        from settings import settings
        import google.generativeai as genai
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure you have all required dependencies installed")
        sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MockCollectionManager:
    """Mock collection manager for testing"""
    
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self.mock_documents = self._create_mock_documents()
    
    def _create_mock_documents(self):
        """Create mock financial documents for testing"""
        if self.collection_name == "bills":
            return [
                {
                    'content': 'House Bill 1234 appropriates $50 million for education programs in fiscal year 2025-26. The bill includes funding for teacher salaries, classroom supplies, and technology upgrades.',
                    'metadata': {'id': 'HB1234', 'document_id': 'HB1234', 'bill_number': 'HB1234', 'amount': 50000000, 'fiscal_year': '2025-26'},
                    'score': 0.95
                },
                {
                    'content': 'Senate Bill 5678 establishes a new healthcare program with $25 million in appropriations. The program will provide medical services to underserved communities.',
                    'metadata': {'id': 'SB5678', 'document_id': 'SB5678', 'bill_number': 'SB5678', 'amount': 25000000, 'program': 'healthcare'},
                    'score': 0.88
                },
                {
                    'content': 'Budget Resolution 2024-1 outlines total state spending of $2.5 billion for the upcoming biennium. Major allocations include education ($800M), healthcare ($600M), and infrastructure ($400M).',
                    'metadata': {'id': 'BR2024-1', 'document_id': 'BR2024-1', 'resolution': 'BR2024-1', 'total_budget': 2500000000},
                    'score': 0.92
                },
                {
                    'content': 'House Bill 9999 creates a renewable energy fund with $100 million in initial funding. The fund will support solar and wind energy projects across the state.',
                    'metadata': {'id': 'HB9999', 'document_id': 'HB9999', 'bill_number': 'HB9999', 'amount': 100000000, 'sector': 'energy'},
                    'score': 0.85
                },
                {
                    'content': 'Transportation Bill TB-2025 allocates $300 million for highway maintenance and new road construction. The bill prioritizes rural area connectivity.',
                    'metadata': {'id': 'TB2025', 'document_id': 'TB2025', 'bill_number': 'TB2025', 'amount': 300000000, 'sector': 'transportation'},
                    'score': 0.80
                }
            ]
        return []
    
    def search_similar_chunks(self, query: str, limit: int = 10):
        """Mock search functionality"""
        query_lower = query.lower()
        results = []
        
        for doc in self.mock_documents:
            content_lower = doc['content'].lower()
            
            # Simple relevance scoring based on keyword matches
            score = 0
            query_words = query_lower.split()
            for word in query_words:
                if word in content_lower:
                    score += content_lower.count(word) * 0.1
            
            if score > 0:
                result = doc.copy()
                result['score'] = min(score, 1.0)  # Cap at 1.0
                results.append(result)
        
        # Sort by score and return top results
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

def setup_test_environment():
    """Setup test environment with mock data"""
    
    # Mock configuration
    config = {
        "collections": ["bills"],
        "system": {
            "chroma_db_path": "./chroma_db/data",
            "embedding_model": "text-embedding-004",
            "llm_model": "gemini-1.5-flash"
        }
    }
    
    # Create mock collection managers
    collection_managers = {
        "bills": MockCollectionManager("bills")
    }
    
    return config, collection_managers

def test_query_scenarios():
    """Define various test query scenarios"""
    return [
        {
            "name": "Simple Factual Query",
            "query": "How much funding does House Bill 1234 provide for education?",
            "expected_type": "new_document",
            "expected_method": "keyword_matching"
        },
        {
            "name": "Complex Analysis Query", 
            "query": "Compare the budget allocations across different sectors in the state budget",
            "expected_type": "new_document",
            "expected_method": "dense_encoder"
        },
        {
            "name": "Follow-up Query",
            "query": "What are the specific programs included in that education funding?",
            "expected_type": "follow_up",
            "expected_method": None
        },
        {
            "name": "Multi-document Research",
            "query": "Analyze all healthcare-related appropriations and their total impact on the state budget",
            "expected_type": "new_document", 
            "expected_method": "multi_hop_reasoning"
        },
        {
            "name": "Specific Bill Lookup",
            "query": "Show me the details of Senate Bill 5678",
            "expected_type": "new_document",
            "expected_method": "keyword_matching"
        },
        {
            "name": "Conceptual Query",
            "query": "What renewable energy initiatives are funded in the current budget?",
            "expected_type": "new_document",
            "expected_method": "dense_encoder"
        }
    ]

def run_test_query(nlp_backend: NLPBackend, test_case: dict, conversation_id: str):
    """Run a single test query and analyze results"""
    
    print(f"\n{'='*60}")
    print(f"TEST: {test_case['name']}")
    print(f"QUERY: {test_case['query']}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        # Process the query
        result = nlp_backend.process_query(test_case['query'], conversation_id)
        
        processing_time = time.time() - start_time
        
        # Display results
        print(f"\n📊 RESULTS:")
        print(f"   Processing Time: {processing_time:.2f}s")
        print(f"   Sources Used: {result.get('context_used', 0)}")
        print(f"   Pipeline Steps: {result.get('processing_steps', 0)}")
        
        if 'pipeline_steps' in result:
            steps = result['pipeline_steps']
            print(f"\n🔍 PIPELINE ANALYSIS:")
            print(f"   Step 1 - Query Type: {steps.get('step1_decision', {}).get('query_type', 'unknown')}")
            print(f"   Step 1 - Num Documents: {steps.get('step1_decision', {}).get('num_documents', 'unknown')}")
            print(f"   Step 1 - Full Document: {steps.get('step1_decision', {}).get('retrieve_full_document', 'unknown')}")
            print(f"   Step 2 - Search Terms: {len(steps.get('step2_query_generation', {}).get('search_terms', []))} terms")
            print(f"   Step 3 - Retrieval Method: {steps.get('step3_retrieval_method', 'unknown')}")
            print(f"   Step 4 - Content Selected: {steps.get('step4_content_selected', 0)} items")
            print(f"   Step 5 - Reranked: {steps.get('step5_reranked', 0)} items")
        
        print(f"\n💬 ANSWER:")
        answer = result.get('answer', 'No answer generated')
        # Truncate long answers for display
        if len(answer) > 500:
            print(f"   {answer[:500]}...")
        else:
            print(f"   {answer}")
        
        if result.get('sources'):
            print(f"\n📚 SOURCES ({len(result['sources'])}):")
            for i, source in enumerate(result['sources'][:3]):  # Show first 3 sources
                content = source.get('content', '')[:150]
                print(f"   {i+1}. {content}...")
        
        # Validation against expectations
        if 'pipeline_steps' in result:
            actual_type = steps.get('step1_decision', {}).get('query_type')
            actual_method = steps.get('step3_retrieval_method')
            
            print(f"\n✅ VALIDATION:")
            type_match = actual_type == test_case['expected_type']
            print(f"   Query Type: Expected '{test_case['expected_type']}', Got '{actual_type}' {'✓' if type_match else '✗'}")
            
            if test_case['expected_method']:
                method_match = actual_method == test_case['expected_method']
                print(f"   Retrieval Method: Expected '{test_case['expected_method']}', Got '{actual_method}' {'✓' if method_match else '✗'}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_conversation_state(nlp_backend: NLPBackend, conversation_id: str):
    """Test conversation state management"""
    
    print(f"\n{'='*60}")
    print(f"CONVERSATION STATE TEST")
    print(f"{'='*60}")
    
    # Get conversation state
    state = nlp_backend.get_conversation_state(conversation_id)
    print(f"📊 Conversation State:")
    print(f"   ID: {state.get('conversation_id')}")
    print(f"   Documents: {len(state.get('current_documents', []))}")
    print(f"   Decisions: {state.get('decision_count', 0)}")
    print(f"   Context Length: {state.get('context_length', 0)}")
    print(f"   Last Method: {state.get('last_retrieval_method', 'None')}")
    print(f"   Last Type: {state.get('last_query_type', 'None')}")

def main():
    """Main test function"""
    
    print("🚀 NLP Backend Test Suite")
    print("=" * 60)
    
    # Check if Gemini API key is available
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY environment variable not set")
        print("Please set your Gemini API key to run tests")
        return
    
    # Configure Gemini
    genai.configure(api_key=api_key)
    
    # Setup test environment
    print("🔧 Setting up test environment...")
    config, collection_managers = setup_test_environment()
    
    # Initialize NLP Backend
    print("🤖 Initializing NLP Backend...")
    nlp_backend = NLPBackend(collection_managers, config)
    
    # Run test scenarios
    test_cases = test_query_scenarios()
    conversation_id = f"test_conversation_{int(time.time())}"
    
    print(f"🧪 Running {len(test_cases)} test scenarios...")
    
    successful_tests = 0
    total_tests = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[{i}/{total_tests}] Running test: {test_case['name']}")
        
        success = run_test_query(nlp_backend, test_case, conversation_id)
        if success:
            successful_tests += 1
        
        # Small delay between tests
        time.sleep(1)
    
    # Test conversation state
    test_conversation_state(nlp_backend, conversation_id)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Successful Tests: {successful_tests}/{total_tests}")
    print(f"📊 Success Rate: {(successful_tests/total_tests)*100:.1f}%")
    
    if successful_tests == total_tests:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️  {total_tests - successful_tests} tests failed")
    
    # Test conversation reset
    print(f"\n🔄 Testing conversation reset...")
    reset_success = nlp_backend.reset_conversation(conversation_id)
    print(f"   Reset successful: {'✓' if reset_success else '✗'}")

if __name__ == "__main__":
    main()
