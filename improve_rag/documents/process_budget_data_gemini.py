import json
import re
import os
import google.generativeai as genai
from typing import Dict, List, Union, Any
import time

# Configure Gemini API
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

def process_budget_document_with_gemini(dual_extraction_path: str, classification_path: str) -> Dict[str, Any]:
    """
    Process budget document using Gemini AI to extract budget items and text items using both extraction methods.
    
    Args:
        dual_extraction_path: Path to JSON file containing camelot and pdfplumber extractions
        classification_path: Path to JSON file containing AI classification predictions
        
    Returns:
        Dictionary containing processed budget_items and text_items arrays
    """
    
    # Extract filename from the dual extraction path
    filename = os.path.basename(dual_extraction_path)
    document_name = filename.replace('__dual_extraction.json', '')
    
    # Load the data
    with open(dual_extraction_path, 'r') as f:
        extraction_data = json.load(f)
    
    with open(classification_path, 'r') as f:
        classification_data = json.load(f)
    
    # Create lookup for classifications by page number
    classifications = {item['page_number']: item for item in classification_data}
    
    result = {
        'budget_items': [],
        'text_items': [],
        'metadata': {
            'document_name': document_name,
            'total_pages': len(extraction_data),
            'processed_pages': 0,
            'extraction_method': 'gemini_dual'
        }
    }
    
    # Initialize Gemini model
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Process only first 10 pages for testing
    pages_to_process = extraction_data[:10]
    
    for page_data in pages_to_process:
        page_num = page_data['page_number']
        classification = classifications.get(page_num, {})
        
        print(f"Processing page {page_num}...")
        
        try:
            # Extract budget items
            budget_items = extract_budget_items_with_dual_text(page_data, classification, document_name, model)
            if budget_items:
                result['budget_items'].extend(budget_items)
            
            # Extract text item for every page
            text_item = extract_text_item_with_dual_text(page_data, classification, document_name, model)
            if text_item:
                result['text_items'].append(text_item)
            
            result['metadata']['processed_pages'] += 1
            
            # Small delay to avoid rate limiting
            time.sleep(0.2)
            
        except Exception as e:
            print(f"Error processing page {page_num}: {e}")
            continue
    
    return result


def extract_budget_items_with_dual_text(page_data: Dict, classification: Dict, document_name: str, model) -> List[Dict]:
    """
    Use Gemini AI to extract structured budget items using both pdfplumber and camelot text.
    """
    page_num = page_data['page_number']
    
    # Get both extraction texts
    camelot_text = page_data.get('camelot_text', '').strip()
    pdfplumber_text = page_data.get('pdfplumber_text', '').strip()
    
    if not camelot_text and not pdfplumber_text:
        return []
    
    # Prepare classification context
    classification_info = f"""
Classification Prediction: {classification.get('classification', 'unknown')}
Confidence: {classification.get('confidence', 'unknown')}
Reason: {classification.get('reason', 'unknown')}
"""
    
    # Create prompt for Gemini
    prompt = f"""
You are analyzing a budget document page to extract budget line items. You have two different text extractions from the same page and a classification prediction.

CLASSIFICATION CONTEXT:
{classification_info}

EXTRACTION 1 - Camelot (table-focused):
{camelot_text if camelot_text else "No camelot text available"}

EXTRACTION 2 - PDFPlumber (text-focused):
{pdfplumber_text if pdfplumber_text else "No pdfplumber text available"}

TASK: Extract budget items with the following EXACT structure. Use ONLY information explicitly present in the text - do NOT extrapolate meanings of letters, symbols, or abbreviations.

For each budget item found, extract these REQUIRED fields:
- item_number: The line item number (if present, otherwise "unknown")
- program: The full program name as written in the document
- program_id: The program identifier (usually letters + numbers like BED116)
- expending_agency: The agency/department name or code as written
- fiscal_year_2025_2026_amount: Dollar amount for fiscal year 2025-2026 (if present, otherwise "unknown")
- appropriations_mof_2025_2026: MOF code for 2025-2026 appropriation (if present, otherwise "unknown")
- fiscal_year_2026_2027_amount: Dollar amount for fiscal year 2026-2027 (if present, otherwise "unknown")
- appropriations_mof_2026_2027: MOF code for 2026-2027 appropriation (if present, otherwise "unknown")

STRICT RULES:
1. Use "unknown" for any field not explicitly found in the text
2. Do NOT interpret abbreviations or symbols - use exactly as written
3. Keep dollar amounts as numbers without commas (e.g., "1234567" not "1,234,567")
4. Return ONLY a valid JSON array
5. If no budget items are found, return empty array []

Example format:
[
  {{
    "item_number": "1",
    "program": "General Support for Economic Development",
    "program_id": "BED116",
    "expending_agency": "Department of Business and Economic Development",
    "fiscal_year_2025_2026_amount": "1234567",
    "appropriations_mof_2025_2026": "A",
    "fiscal_year_2026_2027_amount": "1456789",
    "appropriations_mof_2026_2027": "A"
  }}
]

Return the JSON array:
"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean up response to get just the JSON
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        
        response_text = response_text.strip()
        
        # Parse JSON response
        budget_items = json.loads(response_text)
        
        # Add metadata to each item
        for item in budget_items:
            item['document_name'] = document_name
            item['page_number'] = page_num
            item['extraction_method'] = 'gemini_dual'
            item['classification_prediction'] = classification.get('classification', 'unknown')
            item['classification_confidence'] = classification.get('confidence', 'unknown')
            
        return budget_items
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error on page {page_num}: {e}")
        print(f"Response was: {response_text[:200]}...")
        return []
    except Exception as e:
        print(f"Error extracting budget items from page {page_num}: {e}")
        return []


def extract_text_item_with_dual_text(page_data: Dict, classification: Dict, document_name: str, model) -> Dict:
    """
    Use Gemini AI to extract text item for every page using both pdfplumber and camelot text.
    """
    page_num = page_data['page_number']
    
    # Get both extraction texts
    camelot_text = page_data.get('camelot_text', '').strip()
    pdfplumber_text = page_data.get('pdfplumber_text', '').strip()
    
    if not camelot_text and not pdfplumber_text:
        return {}
    
    # Prepare classification context
    classification_info = f"""
Classification Prediction: {classification.get('classification', 'unknown')}
Confidence: {classification.get('confidence', 'unknown')}
Reason: {classification.get('reason', 'unknown')}
"""
    
    # Create prompt for Gemini
    prompt = f"""
You are analyzing a budget document page to create a clean text representation. You have two different text extractions from the same page and a classification prediction.

CLASSIFICATION CONTEXT:
{classification_info}

EXTRACTION 1 - Camelot (table-focused):
{camelot_text if camelot_text else "No camelot text available"}

EXTRACTION 2 - PDFPlumber (text-focused):
{pdfplumber_text if pdfplumber_text else "No pdfplumber text available"}

TASK: Create a JSON object with clean text representation based on the classification and quality of extractions.

Based on the classification prediction and reasoning, choose the best extraction method and create a clean text representation:
- If classified as "budget_table", prefer camelot text but clean it up
- If classified as "text", prefer pdfplumber text but clean it up
- Remove excessive whitespace, fix formatting issues
- Keep the content readable and well-structured

Return a JSON object with:
- text: The cleaned text content (choose the better extraction and clean it)

STRICT RULES:
1. Choose the extraction that best matches the classification
2. Clean up formatting but keep original content intact
3. Do NOT add information not in the original text
4. Return ONLY a valid JSON object
5. If both extractions are poor quality, return {{"text": "unknown"}}

Example format:
{{
  "text": "This is the cleaned and formatted text content from the page..."
}}

Return the JSON object:
"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean up response to get just the JSON
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        
        response_text = response_text.strip()
        
        # Parse JSON response
        text_item = json.loads(response_text)
        
        # Add metadata to the text item
        text_item['document_name'] = document_name
        text_item['page_number'] = page_num
        text_item['extraction_method'] = 'gemini_dual'
        text_item['classification_prediction'] = classification.get('classification', 'unknown')
        text_item['classification_confidence'] = classification.get('confidence', 'unknown')
        
        return text_item
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error on page {page_num}: {e}")
        print(f"Response was: {response_text[:200]}...")
        return {}
    except Exception as e:
        print(f"Error extracting text item from page {page_num}: {e}")
        return {}


def save_processed_data(processed_data: Dict, output_path: str):
    """
    Save the processed data to a JSON file.
    """
    with open(output_path, 'w') as f:
        json.dump(processed_data, f, indent=2)


# Example usage
if __name__ == "__main__":
    # Check for API key
    if not os.environ.get('GEMINI_API_KEY'):
        print("Please set the GEMINI_API_KEY environment variable")
        exit(1)
    
    # Process the data (first 10 pages only for testing)
    print("Processing first 10 pages only for testing...")
    result = process_budget_document_with_gemini(
        './model_ouputs/HB300__dual_extraction.json',
        './model_ouputs/page_classifications.json'
    )
    
    # Print summary
    print(f"\nProcessed document: {result['metadata']['document_name']}")
    print(f"Total pages: {result['metadata']['total_pages']}")
    print(f"Pages processed: {result['metadata']['processed_pages']}")
    print(f"Budget items extracted: {len(result['budget_items'])}")
    print(f"Text items extracted: {len(result['text_items'])}")
    
    # Save results
    save_processed_data(result, './model_ouputs/processed_budget_data_gemini_first10.json')
    print("\nResults saved to './model_ouputs/processed_budget_data_gemini_first10.json'")
    
    # Show budget items
    if result['budget_items']:
        print("\n--- Budget Items Found ---")
        for i, item in enumerate(result['budget_items']):
            print(f"\nBudget Item {i+1}:")
            print(f"  Document: {item['document_name']}")
            print(f"  Page: {item['page_number']}")
            print(f"  Item Number: {item.get('item_number', 'N/A')}")
            print(f"  Program: {item.get('program', 'N/A')}")
            print(f"  Program ID: {item.get('program_id', 'N/A')}")
            print(f"  Expending Agency: {item.get('expending_agency', 'N/A')}")
            print(f"  FY 2025-2026 Amount: {item.get('fiscal_year_2025_2026_amount', 'N/A')}")
            print(f"  MOF 2025-2026: {item.get('appropriations_mof_2025_2026', 'N/A')}")
            print(f"  FY 2026-2027 Amount: {item.get('fiscal_year_2026_2027_amount', 'N/A')}")
            print(f"  MOF 2026-2027: {item.get('appropriations_mof_2026_2027', 'N/A')}")
            print(f"  Classification: {item.get('classification_prediction', 'N/A')} (confidence: {item.get('classification_confidence', 'N/A')})")
    else:
        print("\nNo budget items found.")
    
    # Show text items
    if result['text_items']:
        print("\n--- Text Items Found ---")
        for i, item in enumerate(result['text_items']):
            print(f"\nText Item {i+1}:")
            print(f"  Document: {item['document_name']}")
            print(f"  Page: {item['page_number']}")
            print(f"  Classification: {item.get('classification_prediction', 'N/A')} (confidence: {item.get('classification_confidence', 'N/A')})")
            text_content = item.get('text', 'N/A')
            if len(text_content) > 200:
                print(f"  Text: {text_content[:200]}...")
            else:
                print(f"  Text: {text_content}")
    else:
        print("\nNo text items found.") 