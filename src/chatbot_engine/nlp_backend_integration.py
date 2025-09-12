"""
Integration Example for NLP Backend with Existing ChromaDB System
Shows how to connect the new NLP backend with your existing infrastructure
"""

import json
import logging
from pathlib import Path
import sys
import os

# Add src to path for imports
sys.path.append(str(Path(__file__).parent))

try:
    from .nlp_backend import NLPBackend
    from ..query_processor import QueryProcessor
    import google.generativeai as genai
except ImportError:
    try:
        from nlp_backend import NLPBackend
        sys.path.append(str(Path(__file__).parent.parent))
        from query_processor import QueryProcessor
        import google.generativeai as genai
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure you have all required dependencies installed")
        sys.exit(1)

logger = logging.getLogger(__name__)

class IntegratedNLPSystem:
    """
    Integration wrapper that combines the new NLP Backend with existing systems
    """
    
    def __init__(self, collection_managers: dict, config: dict):
        self.collection_managers = collection_managers
        self.config = config
        
        # Initialize both systems
        self.nlp_backend = NLPBackend(collection_managers, config)
        self.legacy_processor = QueryProcessor(collection_managers, config)
        
        # Configuration for when to use which system
        self.use_nlp_backend = True  # Set to False to use legacy system
        
    def process_query(self, user_query: str, conversation_id: str = "default", use_advanced_pipeline: bool = True):
        """
        Process query using either the new NLP backend or legacy processor
        """
        if use_advanced_pipeline and self.use_nlp_backend:
            logger.info("Using advanced NLP backend pipeline")
            return self.nlp_backend.process_query(user_query, conversation_id)
        else:
            logger.info("Using legacy query processor")
            # Convert legacy result to match new format
            legacy_result = self.legacy_processor.process_query(user_query, threshold=0.7)
            return self._convert_legacy_result(legacy_result, conversation_id)
    
    def _convert_legacy_result(self, legacy_result: dict, conversation_id: str) -> dict:
        """Convert legacy result format to new format"""
        return {
            "answer": legacy_result.get("response", ""),
            "sources": legacy_result.get("sources", []),
            "context_used": legacy_result.get("total_documents_found", 0),
            "conversation_id": conversation_id,
            "processing_steps": 3,  # Legacy system has 3 steps
            "pipeline_steps": {
                "legacy_system": True,
                "reasoning": legacy_result.get("reasoning", {}),
                "total_documents": legacy_result.get("total_documents_found", 0)
            }
        }
    
    def compare_systems(self, user_query: str, conversation_id: str = "comparison"):
        """
        Compare results from both systems side by side
        """
        print(f"\n{'='*80}")
        print(f"SYSTEM COMPARISON FOR QUERY: {user_query}")
        print(f"{'='*80}")
        
        # Test with new NLP backend
        print("\n🤖 NEW NLP BACKEND RESULTS:")
        print("-" * 40)
        try:
            nlp_result = self.nlp_backend.process_query(user_query, f"{conversation_id}_nlp")
            print(f"Answer: {nlp_result.get('answer', '')[:200]}...")
            print(f"Sources: {nlp_result.get('context_used', 0)}")
            print(f"Processing Time: {nlp_result.get('processing_time', 0):.2f}s")
            if 'pipeline_steps' in nlp_result:
                steps = nlp_result['pipeline_steps']
                print(f"Query Type: {steps.get('step1_decision', {}).get('query_type', 'unknown')}")
                print(f"Retrieval Method: {steps.get('step3_retrieval_method', 'unknown')}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test with legacy system
        print("\n🏛️ LEGACY SYSTEM RESULTS:")
        print("-" * 40)
        try:
            legacy_result = self.legacy_processor.process_query(user_query, threshold=0.7)
            print(f"Answer: {legacy_result.get('response', '')[:200]}...")
            print(f"Sources: {legacy_result.get('total_documents_found', 0)}")
            print(f"Reasoning: {legacy_result.get('reasoning', {}).get('intent', 'unknown')}")
        except Exception as e:
            print(f"Error: {e}")

def load_real_collection_managers():
    """
    Load real collection managers from your existing system
    This function should be adapted to your actual ChromaDB setup
    """
    try:
        # This is a placeholder - adapt to your actual collection loading logic
        from documents.embeddings import CollectionManager  # Adjust import as needed
        
        config_path = Path(__file__).parent / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        collection_managers = {}
        for collection_name in config["collections"]:
            # Initialize your actual collection managers here
            # collection_managers[collection_name] = CollectionManager(collection_name, config)
            pass
        
        return collection_managers, config
        
    except Exception as e:
        logger.warning(f"Could not load real collection managers: {e}")
        logger.info("Using mock collection managers for demonstration")
        return None, None

def demo_advanced_features():
    """Demonstrate advanced features of the NLP backend"""
    
    print("\n🎯 ADVANCED FEATURES DEMONSTRATION")
    print("=" * 60)
    
    # Load configuration
    config_path = Path(__file__).parent / "config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    # Try to load real collection managers, fall back to mock
    real_managers, real_config = load_real_collection_managers()
    
    if real_managers:
        print("✅ Using real ChromaDB collections")
        integrated_system = IntegratedNLPSystem(real_managers, real_config)
    else:
        print("⚠️  Using mock collections for demonstration")
        # Use mock system from test file
        from test_nlp_backend import setup_test_environment
        config, collection_managers = setup_test_environment()
        integrated_system = IntegratedNLPSystem(collection_managers, config)
    
    # Demonstrate conversation continuity
    conversation_id = "demo_conversation"
    
    queries = [
        "What is the total budget allocation for education programs?",
        "Which specific bills contribute to that education funding?",  # Follow-up
        "How does the education budget compare to healthcare spending?",  # New analysis
        "What are the details of the renewable energy initiatives?"  # New topic
    ]
    
    print(f"\n💬 CONVERSATION FLOW DEMONSTRATION")
    print("-" * 40)
    
    for i, query in enumerate(queries, 1):
        print(f"\n[Query {i}] {query}")
        
        try:
            result = integrated_system.process_query(query, conversation_id)
            
            # Show key insights
            if 'pipeline_steps' in result:
                steps = result['pipeline_steps']
                query_type = steps.get('step1_decision', {}).get('query_type', 'unknown')
                method = steps.get('step3_retrieval_method', 'unknown')
                print(f"  → Classified as: {query_type}")
                print(f"  → Used method: {method}")
                print(f"  → Sources: {result.get('context_used', 0)}")
            
            # Show brief answer
            answer = result.get('answer', '')
            if len(answer) > 150:
                print(f"  → Answer: {answer[:150]}...")
            else:
                print(f"  → Answer: {answer}")
                
        except Exception as e:
            print(f"  → Error: {e}")
    
    # Show conversation state
    print(f"\n📊 FINAL CONVERSATION STATE:")
    state = integrated_system.nlp_backend.get_conversation_state(conversation_id)
    print(f"  Documents tracked: {len(state.get('current_documents', []))}")
    print(f"  Decision history: {state.get('decision_count', 0)} decisions")
    print(f"  Context length: {state.get('context_length', 0)} exchanges")

def main():
    """Main demonstration function"""
    
    print("🚀 NLP Backend Integration Demo")
    print("=" * 60)
    
    # Check API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY environment variable not set")
        print("Please set your Gemini API key to run the demo")
        return
    
    genai.configure(api_key=api_key)
    
    # Run advanced features demo
    demo_advanced_features()
    
    print(f"\n✅ Integration demo completed!")
    print("\nTo integrate with your existing system:")
    print("1. Replace mock collection managers with your real ChromaDB managers")
    print("2. Update the import statements to match your project structure")
    print("3. Configure the system to use either NLP backend or legacy processor")
    print("4. Test with your actual document collections")

if __name__ == "__main__":
    main()
