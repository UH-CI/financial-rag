import google.generativeai as genai
import json
from pathlib import Path

# Configure Gemini API
# You'll need to set your API key - get it from https://aistudio.google.com/app/apikey
API_KEY = "YOUR_GEMINI_API_KEY_HERE"  # Replace with your actual API key
genai.configure(api_key=API_KEY)

def test_gemini_grounding_with_document():
    """
    Test Gemini-2.5-pro with a large document to see grounding_metadata in action
    """
    
    # Sample large document (you can replace this with your own document)
    large_document = """
    FISCAL IMPACT ANALYSIS
    
    BILL: HB 1483 - Relating to Environmental Protection
    
    EXECUTIVE SUMMARY:
    This bill establishes new environmental protection standards for industrial facilities in Hawaii.
    The legislation requires mandatory environmental impact assessments for all new industrial 
    developments exceeding 50,000 square feet. Additionally, it creates a new Environmental 
    Compliance Division within the Department of Health with an annual budget of $2.5 million.
    
    FISCAL IMPACT:
    The implementation of this bill will require significant state funding across multiple departments:
    
    1. Department of Health - Environmental Compliance Division:
       - Personnel costs: $1,800,000 annually (12 FTE positions)
       - Equipment and technology: $500,000 initial setup
       - Operating expenses: $200,000 annually
    
    2. Department of Land and Natural Resources:
       - Additional environmental review staff: $600,000 annually (4 FTE positions)
       - Enhanced monitoring equipment: $300,000 initial setup
    
    3. Department of Business, Economic Development & Tourism:
       - Impact assessment coordination: $150,000 annually (1 FTE position)
    
    REVENUE IMPLICATIONS:
    The bill establishes new permit fees for industrial facilities:
    - Initial environmental assessment fee: $25,000 per facility
    - Annual compliance monitoring fee: $10,000 per facility
    - Estimated 15 new facilities annually, generating $525,000 in revenue
    
    NET FISCAL IMPACT:
    Total annual costs: $2,750,000
    Total annual revenue: $525,000
    Net annual cost to state: $2,225,000
    
    IMPLEMENTATION TIMELINE:
    Year 1: Setup costs of $800,000 plus annual operating costs
    Years 2+: Annual operating costs of $2,750,000 minus revenue of $525,000
    
    ECONOMIC BENEFITS:
    While the bill requires significant state investment, it is projected to:
    - Reduce environmental cleanup costs by an estimated $5 million annually
    - Attract environmentally conscious businesses, potentially increasing tax revenue
    - Improve public health outcomes, reducing healthcare costs
    
    CONCLUSION:
    The bill represents a substantial investment in environmental protection with long-term 
    economic and health benefits that may offset the initial fiscal impact.
    """
    
    # Initialize the model
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    # Create a comprehensive prompt that should trigger grounding
    prompt = f"""
    Please analyze the following fiscal impact document and provide a comprehensive summary.
    Focus on the key financial figures, implementation costs, revenue projections, and 
    overall fiscal implications. Be specific about dollar amounts and timelines mentioned.
    
    Document to analyze:
    {large_document}
    
    Please provide:
    1. A concise executive summary
    2. Key financial figures and their sources
    3. Implementation timeline with costs
    4. Revenue vs. cost analysis
    5. Long-term fiscal implications
    """
    
    try:
        # Generate response with grounding
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,  # Lower temperature for more factual responses
                top_p=0.8,
                top_k=40,
                max_output_tokens=2048,
            )
        )
        
        print("=== GEMINI RESPONSE ===")
        print(response.text)
        print("\n" + "="*50)
        
        # Check for grounding metadata
        print("\n=== GROUNDING METADATA ANALYSIS ===")
        
        # Access the response object attributes
        print(f"Response type: {type(response)}")
        print(f"Available attributes: {dir(response)}")
        
        # Try to access grounding metadata
        if hasattr(response, 'grounding_metadata'):
            print(f"\nGrounding metadata found: {response.grounding_metadata}")
        else:
            print("\nNo grounding_metadata attribute found in response")
            
        # Check candidates for grounding info
        if hasattr(response, 'candidates') and response.candidates:
            print(f"\nNumber of candidates: {len(response.candidates)}")
            for i, candidate in enumerate(response.candidates):
                print(f"\nCandidate {i} attributes: {dir(candidate)}")
                if hasattr(candidate, 'grounding_metadata'):
                    print(f"Candidate {i} grounding metadata: {candidate.grounding_metadata}")
                if hasattr(candidate, 'grounding_attributions'):
                    print(f"Candidate {i} grounding attributions: {candidate.grounding_attributions}")
        
        # Try to access the raw response data
        print(f"\n=== RAW RESPONSE INSPECTION ===")
        if hasattr(response, '_result'):
            print(f"Raw result type: {type(response._result)}")
            print(f"Raw result: {response._result}")
        
        # Print full response object as JSON if possible
        try:
            response_dict = {}
            for attr in dir(response):
                if not attr.startswith('_') and not callable(getattr(response, attr)):
                    try:
                        value = getattr(response, attr)
                        response_dict[attr] = str(value)  # Convert to string for JSON serialization
                    except:
                        response_dict[attr] = "Could not serialize"
            
            print(f"\n=== FULL RESPONSE OBJECT ===")
            print(json.dumps(response_dict, indent=2))
            
        except Exception as e:
            print(f"Could not serialize response object: {e}")
        
        return response
        
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        print("Make sure you've set your API key correctly!")
        return None

# Run the test
if __name__ == "__main__":
    print("Testing Gemini-2.5-pro with grounding metadata...")
    print("Make sure to replace 'YOUR_GEMINI_API_KEY_HERE' with your actual API key!")
    print("="*60)
    
    response = test_gemini_grounding_with_document()
