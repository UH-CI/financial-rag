import json
import re
import os
import google.generativeai as genai
from typing import Dict, List, Union, Any
import time

# Configure Gemini API
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

def process_hb300_hd1_pdfplumber() -> Dict[str, Any]:
    """
    Process HB300_HD1 document using only pdfplumber extraction with Gemini AI.
    """
    
    # File paths for HB300_HD1
    dual_extraction_path = './model_ouputs/text_extractions/HB300_HD1__dual_extraction.json'
    classification_path = './model_ouputs/page_classifications/HB300_HD1_page_classifications.json'
    
    # Check if files exist
    if not os.path.exists(dual_extraction_path):
        print(f"Error: Dual extraction file not found: {dual_extraction_path}")
        return {}
    
    if not os.path.exists(classification_path):
        print(f"Error: Classification file not found: {classification_path}")
        return {}
    
    document_name = "HB300_HD1"
    
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
            'extraction_method': 'gemini_pdfplumber_only',
            'budget_items_with_unknowns': 0,
            'total_unknown_fields': 0,
            'unknown_field_breakdown': {
                'program': 0,
                'program_id': 0,
                'expending_agency': 0,
                'fiscal_year_2025_2026_amount': 0,
                'appropriations_mof_2025_2026': 0,
                'fiscal_year_2026_2027_amount': 0,
                'appropriations_mof_2026_2027': 0
            }
        }
    }
    
    # Initialize Gemini model
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Process all pages
    for i, page_data in enumerate(extraction_data):
        page_num = page_data['page_number']
        classification = classifications.get(page_num, {})
        
        print(f"Processing {document_name} page {page_num}...")
        
        try:
            # Get previous page context
            previous_page_data = extraction_data[i-1] if i > 0 else None
            
            # Get last 3 budget items as context
            recent_budget_items = result['budget_items'][-3:] if len(result['budget_items']) >= 3 else result['budget_items']
            
            # Extract budget items using only pdfplumber with context
            budget_items = extract_budget_items_pdfplumber_only(
                page_data, classification, document_name, model, 
                previous_page_data=previous_page_data, 
                recent_budget_items=recent_budget_items
            )
            if budget_items:
                result['budget_items'].extend(budget_items)
                
                # Track unknown statistics
                for item in budget_items:
                    if item.get('has_unknown_values', False):
                        result['metadata']['budget_items_with_unknowns'] += 1
                    
                    # Count specific unknown fields
                    for field in ['program', 'program_id', 'expending_agency', 
                                'fiscal_year_2025_2026_amount', 'appropriations_mof_2025_2026',
                                'fiscal_year_2026_2027_amount', 'appropriations_mof_2026_2027']:
                        if str(item.get(field, '')).lower() == 'unknown':
                            result['metadata']['total_unknown_fields'] += 1
                            result['metadata']['unknown_field_breakdown'][field] += 1
            
            # Extract text item for every page using only pdfplumber
            text_item = extract_text_item_pdfplumber_only(page_data, classification, document_name, model)
            if text_item:
                result['text_items'].append(text_item)
            
            result['metadata']['processed_pages'] += 1
            
            # Small delay to avoid rate limiting
            time.sleep(0.15)
            
        except Exception as e:
            print(f"Error processing {document_name} page {page_num}: {e}")
            continue
    
    return result

def extract_budget_items_pdfplumber_only(page_data: Dict, classification: Dict, document_name: str, model, previous_page_data: Dict = None, recent_budget_items: List[Dict] = []) -> List[Dict]:
    """
    Use Gemini AI to extract structured budget items using only pdfplumber text.
    Includes retry logic for unknown values and comprehensive metadata tracking.
    Now includes context from previous page and recent budget items.
    """
    page_num = page_data['page_number']
    
    # Get only pdfplumber text
    pdfplumber_text = page_data.get('pdfplumber_text', '').strip()
    
    if not pdfplumber_text:
        return []
    
    # Prepare classification context
    classification_info = f"""
Classification Prediction: {classification.get('classification', 'unknown')}
Confidence: {classification.get('confidence', 'unknown')}
Reason: {classification.get('reason', 'unknown')}
"""
    
    # Prepare previous page context
    previous_page_context = ""
    if previous_page_data:
        previous_page_text = previous_page_data.get('pdfplumber_text', '').strip()
        if previous_page_text:
            # Limit previous page text to avoid token limits
            if len(previous_page_text) > 1000:
                previous_page_text = previous_page_text[-1000:]  # Take last 1000 chars
            previous_page_context = f"""
PREVIOUS PAGE CONTEXT (Page {previous_page_data.get('page_number', 'unknown')}):
{previous_page_text}
"""
    
    # Prepare recent budget items context
    recent_items_context = ""
    if recent_budget_items:
        recent_items_context = "RECENT BUDGET ITEMS FOR CONTEXT:\n"
        for i, item in enumerate(recent_budget_items):
            recent_items_context += f"""
Item {i+1} (Page {item.get('page_number', 'unknown')}):
- Program: {item.get('program', 'unknown')}
- Program ID: {item.get('program_id', 'unknown')}
- Agency: {item.get('expending_agency', 'unknown')}
- FY 2025-2026: {item.get('fiscal_year_2025_2026_amount', 'unknown')} (MOF: {item.get('appropriations_mof_2025_2026', 'unknown')})
- FY 2026-2027: {item.get('fiscal_year_2026_2027_amount', 'unknown')} (MOF: {item.get('appropriations_mof_2026_2027', 'unknown')})
"""
    
    # Try up to 3 times to get complete budget items
    max_retries = 3
    for attempt in range(max_retries):
        print(f"  Attempt {attempt + 1}/{max_retries} for {document_name} page {page_num}")
        
        # Create prompt for Gemini
        if attempt == 0:
            # First attempt - standard prompt with context
            prompt = f"""
You are analyzing a budget document page to extract budget line items. You have pdfplumber text extraction, a classification prediction, and additional context from previous pages and recent budget items.

CLASSIFICATION CONTEXT:
{classification_info}

{previous_page_context}

{recent_items_context}

CURRENT PAGE TEXT (Page {page_num}):
{pdfplumber_text}

TASK: Extract budget items with the following EXACT structure. Use ONLY information explicitly present in the text - do NOT extrapolate meanings of letters, symbols, or abbreviations.

IMPORTANT: Use the previous page context and recent budget items to understand patterns and help identify budget items that may span multiple pages or follow similar formatting.

For each budget item found, extract these REQUIRED fields with EXACT structure:
{{
  "program": "Full program name as written in the document",
  "program_id": "Program identifier (letters + numbers like LBR111)",
  "expending_agency": "Agency/department code (like LBR, BED, EDN)",
  "fiscal_year_2025_2026_amount": "Dollar amount as number without commas",
  "appropriations_mof_2025_2026": "MOF code (single letter like A, B, C)",
  "fiscal_year_2026_2027_amount": "Dollar amount as number without commas",
  "appropriations_mof_2026_2027": "MOF code (single letter like A, B, C)"
}}

STRICT RULES:
1. Use "unknown" ONLY if information is truly not present in the text
2. Look carefully for program names, IDs, agency codes, amounts, and MOF codes
3. Use context from previous page and recent items to understand patterns
4. Agency codes are usually 3-letter codes (LBR, BED, EDN, HTH, etc.)
5. Program IDs combine agency code + numbers (like LBR111, BED116)
6. MOF codes are single letters (A, B, C, D, E, etc.)
7. Dollar amounts should be numbers without commas or dollar signs
8. Return ONLY a valid JSON array
9. If no budget items are found, return empty array []

Return the JSON array:
"""
        else:
            # Retry attempts - provide more context and guidance
            prompt = f"""
You are analyzing a budget document page to extract budget line items. This is RETRY ATTEMPT {attempt + 1} - please look more carefully for missing information using all available context.

CLASSIFICATION CONTEXT:
{classification_info}

{previous_page_context}

{recent_items_context}

CURRENT PAGE TEXT (Page {page_num}):
{pdfplumber_text}

IMPORTANT GUIDANCE FOR THIS RETRY:
- Look for program names that might be split across lines or continue from previous page
- Agency codes are typically 3-letter abbreviations (LBR, BED, EDN, HTH, TRN, etc.)
- Program IDs often combine agency code + numbers (LBR111, BED116, EDN100)
- MOF codes are single letters found near dollar amounts (A=general funds, B=special funds, etc.)
- Dollar amounts might be formatted with commas or in separate sections
- Use patterns from recent budget items to identify similar structures
- If you see partial information, try to piece it together from context
- Budget items may span multiple pages - check if current page continues from previous page

TASK: Extract budget items with the following EXACT structure:
{{
  "program": "Full program name as written in the document",
  "program_id": "Program identifier (letters + numbers like LBR111)",
  "expending_agency": "Agency/department code (like LBR, BED, EDN)",
  "fiscal_year_2025_2026_amount": "Dollar amount as number without commas",
  "appropriations_mof_2025_2026": "MOF code (single letter like A, B, C)",
  "fiscal_year_2026_2027_amount": "Dollar amount as number without commas",
  "appropriations_mof_2026_2027": "MOF code (single letter like A, B, C)"
}}

MINIMIZE "unknown" values by looking more carefully and using context. Only use "unknown" if truly not present.

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
            
            # Check if we have items and count unknowns
            if not budget_items:
                if attempt == max_retries - 1:
                    print(f"    No budget items found after {max_retries} attempts")
                    return []
                continue
            
            # Count unknowns in this attempt
            total_unknowns = 0
            for item in budget_items:
                for key, value in item.items():
                    if str(value).lower() == 'unknown':
                        total_unknowns += 1
            
            print(f"    Found {len(budget_items)} budget items with {total_unknowns} unknown values")
            
            # If we have items with few/no unknowns, we can stop early
            if total_unknowns == 0:
                print(f"    Perfect extraction - no unknown values, stopping early")
            elif total_unknowns <= 2 and attempt >= 1:  # Allow some unknowns after first retry
                print(f"    Good extraction with minimal unknowns, stopping early")
            elif total_unknowns > 0 and attempt < max_retries - 1:
                print(f"    Retrying to reduce unknown values...")
                continue
            
            # If we reach here, we either have good results or exhausted retries
            
            # Add comprehensive metadata to each item
            for i, item in enumerate(budget_items):
                # Auto-derive expending_agency from program_id if program_id is found
                program_id = item.get('program_id', 'unknown')
                expending_agency = item.get('expending_agency', 'unknown')
                
                # If program_id is found but expending_agency is unknown, derive it
                if (program_id != 'unknown' and str(program_id).strip() and 
                    (expending_agency == 'unknown' or not str(expending_agency).strip())):
                    # Extract first 3 capital letters from program_id
                    capital_letters = re.findall(r'[A-Z]', str(program_id))
                    if len(capital_letters) >= 3:
                        derived_agency = ''.join(capital_letters[:3])
                        expending_agency = derived_agency
                        print(f"    Derived expending_agency '{derived_agency}' from program_id '{program_id}'")
                
                # Ensure required structure
                structured_item = {
                    "program": item.get('program', 'unknown'),
                    "program_id": program_id,
                    "expending_agency": expending_agency,
                    "fiscal_year_2025_2026_amount": item.get('fiscal_year_2025_2026_amount', 'unknown'),
                    "appropriations_mof_2025_2026": item.get('appropriations_mof_2025_2026', 'unknown'),
                    "fiscal_year_2026_2027_amount": item.get('fiscal_year_2026_2027_amount', 'unknown'),
                    "appropriations_mof_2026_2027": item.get('appropriations_mof_2026_2027', 'unknown'),
                    
                    # Metadata
                    "item_number": i + 1,
                    "document_name": document_name,
                    "page_number": page_num,
                    "extraction_method": "gemini_pdfplumber_only",
                    "classification_prediction": classification.get('classification', 'unknown'),
                    "classification_confidence": classification.get('confidence', 'unknown'),
                    "extraction_attempts": attempt + 1,
                    "has_unknown_values": any(str(v).lower() == 'unknown' for v in [
                        item.get('program', ''),
                        program_id,
                        expending_agency,
                        item.get('fiscal_year_2025_2026_amount', ''),
                        item.get('appropriations_mof_2025_2026', ''),
                        item.get('fiscal_year_2026_2027_amount', ''),
                        item.get('appropriations_mof_2026_2027', '')
                    ])
                }
                
                budget_items[i] = structured_item
            
            return budget_items
            
        except json.JSONDecodeError as e:
            print(f"    JSON decode error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                print(f"    Failed to parse JSON after {max_retries} attempts")
                return []
            continue
        except Exception as e:
            print(f"    Error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                print(f"    Failed after {max_retries} attempts")
                return []
            continue
    
    return []

def extract_text_item_pdfplumber_only(page_data: Dict, classification: Dict, document_name: str, model) -> Dict:
    """
    Use Gemini AI to extract text item for every page using only pdfplumber text.
    """
    page_num = page_data['page_number']
    
    # Get only pdfplumber text
    pdfplumber_text = page_data.get('pdfplumber_text', '').strip()
    
    if not pdfplumber_text:
        return {}
    
    # Prepare classification context
    classification_info = f"""
Classification Prediction: {classification.get('classification', 'unknown')}
Confidence: {classification.get('confidence', 'unknown')}
Reason: {classification.get('reason', 'unknown')}
"""
    
    # Create prompt for Gemini
    prompt = f"""
You are analyzing a budget document page to create a clean text representation using pdfplumber extraction.

CLASSIFICATION CONTEXT:
{classification_info}

PDFPLUMBER TEXT:
{pdfplumber_text}

TASK: Create a JSON object with clean text representation.

Clean up the pdfplumber text:
- Remove excessive whitespace and fix formatting issues
- Keep the content readable and well-structured
- Preserve all original content and meaning

Return a JSON object with:
- text: The cleaned text content

STRICT RULES:
1. Clean up formatting but keep original content intact
2. Do NOT add information not in the original text
3. Return ONLY a valid JSON object
4. If text is poor quality, return {{"text": "unknown"}}

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
        text_item['extraction_method'] = 'gemini_pdfplumber_only'
        text_item['classification_prediction'] = classification.get('classification', 'unknown')
        text_item['classification_confidence'] = classification.get('confidence', 'unknown')
        
        return text_item
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error on {document_name} page {page_num}: {e}")
        return {}
    except Exception as e:
        print(f"Error extracting text item from {document_name} page {page_num}: {e}")
        return {}

def save_processed_data(processed_data: Dict, output_path: str):
    """
    Save the processed data to a JSON file.
    """
    with open(output_path, 'w') as f:
        json.dump(processed_data, f, indent=2)

# Main processing script
if __name__ == "__main__":
    # Check for API key
    if not os.environ.get('GEMINI_API_KEY'):
        print("Please set the GEMINI_API_KEY environment variable")
        exit(1)
    
    print("Processing HB300_HD1 using pdfplumber extraction only...")
    print("="*60)
    
    try:
        result = process_hb300_hd1_pdfplumber()
        
        if not result:
            print("Failed to process HB300_HD1")
            exit(1)
        
        # Print summary
        print(f"\nSUMMARY for {result['metadata']['document_name']}:")
        print(f"  Total pages: {result['metadata']['total_pages']}")
        print(f"  Pages processed: {result['metadata']['processed_pages']}")
        print(f"  Budget items extracted: {len(result['budget_items'])}")
        print(f"  Text items extracted: {len(result['text_items'])}")
        print(f"  Budget items with unknowns: {result['metadata']['budget_items_with_unknowns']}")
        print(f"  Total unknown fields: {result['metadata']['total_unknown_fields']}")
        
        if result['metadata']['total_unknown_fields'] > 0:
            print(f"  Unknown field breakdown:")
            for field, count in result['metadata']['unknown_field_breakdown'].items():
                if count > 0:
                    print(f"    {field}: {count}")
        
        # Calculate percentage of items with unknowns
        total_budget_items = len(result['budget_items'])
        if total_budget_items > 0:
            unknown_percentage = (result['metadata']['budget_items_with_unknowns'] / total_budget_items) * 100
            print(f"  Percentage with unknowns: {unknown_percentage:.1f}%")
        
        # Save results
        output_path = './model_ouputs/processed_documents/processed_HB300_HD1_geminiV3.json'
        save_processed_data(result, output_path)
        print(f"  Saved to: {output_path}")
        
        # Show sample budget items
        if result['budget_items']:
            print(f"\n--- Sample Budget Items (showing first 3) ---")
            for i, item in enumerate(result['budget_items'][:3]):
                print(f"\nBudget Item {i+1}:")
                print(f"  Page: {item['page_number']}")
                print(f"  Program: {item.get('program', 'N/A')}")
                print(f"  Program ID: {item.get('program_id', 'N/A')}")
                print(f"  Expending Agency: {item.get('expending_agency', 'N/A')}")
                print(f"  FY 2025-2026 Amount: {item.get('fiscal_year_2025_2026_amount', 'N/A')}")
                print(f"  MOF 2025-2026: {item.get('appropriations_mof_2025_2026', 'N/A')}")
                print(f"  Extraction Attempts: {item.get('extraction_attempts', 'N/A')}")
                print(f"  Has Unknowns: {item.get('has_unknown_values', 'N/A')}")
        
        print(f"\n{'='*60}")
        print("Processing completed successfully!")
        
    except Exception as e:
        print(f"Error processing HB300_HD1: {e}")
        exit(1) 