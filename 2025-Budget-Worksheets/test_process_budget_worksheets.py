import json
import re
import os
import google.generativeai as genai
from typing import Dict, List, Union, Any
import time
import sys

# Configure Gemini API
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

def load_extracted_data(file_path: str = 'all_pdfs_extracted.json') -> Dict[str, List[Dict]]:
    """
    Load the extracted PDF data from JSON file.
    """
    with open(file_path, 'r') as f:
        return json.load(f)

def classify_document_type(document_name: str, sample_text: str) -> str:
    """
    Classify the document type based on name and content.
    """
    document_name_lower = document_name.lower()
    sample_text_lower = sample_text.lower()
    
    if 'cip' in document_name_lower or 'capital improvement' in sample_text_lower:
        return 'cip'  # Capital Improvement Projects
    elif 'worksheet' in document_name_lower or 'budget worksheet' in sample_text_lower:
        return 'budget_worksheet'  # Budget Worksheets
    elif any(term in sample_text_lower for term in ['program id:', 'structure #:', 'base appropriations']):
        return 'budget_worksheet'
    elif any(term in sample_text_lower for term in ['progid', 'construction', 'plans, design']):
        return 'cip'
    else:
        return 'unknown'

def process_budget_worksheet_document_limited(document_name: str, pages_data: List[Dict], model, max_pages: int = 5) -> Dict[str, Any]:
    """
    Process a budget worksheet document using Gemini AI to extract budget items and text items.
    Limited to first max_pages for testing.
    """
    
    # Limit to first max_pages
    pages_data = pages_data[:max_pages]
    
    # Classify document type
    sample_text = pages_data[0].get('pdfplumber_text', '') if pages_data else ''
    document_type = classify_document_type(document_name, sample_text)
    
    result = {
        'budget_worksheet_items': [],
        'text_items': [],
        'metadata': {
            'document_name': document_name,
            'document_type': document_type,
            'total_pages': len(pages_data),
            'processed_pages': 0,
            'extraction_method': 'gemini_dual_worksheet',
            'items_with_unknowns': 0,
            'total_unknown_fields': 0,
            'limited_test': True,
            'max_pages_processed': max_pages
        }
    }
    
    print(f"Processing {document_name} (Type: {document_type}) - {len(pages_data)} pages (LIMITED TEST)...")
    
    # Process all pages
    for i, page_data in enumerate(pages_data):
        page_num = page_data['page_number']
        
        print(f"  Processing page {page_num}...")
        
        try:
            # Get previous page context
            previous_page_data = pages_data[i-1] if i > 0 else None
            
            # Get last 3 items as context
            recent_items = result['budget_worksheet_items'][-3:] if len(result['budget_worksheet_items']) >= 3 else result['budget_worksheet_items']
            
            # Extract budget worksheet items based on document type
            if document_type == 'budget_worksheet':
                worksheet_items = extract_budget_worksheet_items(
                    page_data, document_name, model, document_type,
                    previous_page_data=previous_page_data,
                    recent_items=recent_items
                )
            elif document_type == 'cip':
                worksheet_items = extract_cip_items(
                    page_data, document_name, model, document_type,
                    previous_page_data=previous_page_data,
                    recent_items=recent_items
                )
            else:
                worksheet_items = []
            
            if worksheet_items:
                result['budget_worksheet_items'].extend(worksheet_items)
                
                # Track unknown statistics
                for item in worksheet_items:
                    if item.get('has_unknown_values', False):
                        result['metadata']['items_with_unknowns'] += 1
            
            # Extract text item for every page
            text_item = extract_text_item_with_dual_text(page_data, document_name, model, document_type)
            if text_item:
                result['text_items'].append(text_item)
            
            result['metadata']['processed_pages'] += 1
            
            # Small delay to avoid rate limiting
            time.sleep(0.15)
            
        except Exception as e:
            print(f"    Error processing {document_name} page {page_num}: {e}")
            continue
    
    return result

def extract_budget_worksheet_items(page_data: Dict, document_name: str, model, document_type: str, 
                                 previous_page_data: Dict = None, recent_items: List[Dict] = []) -> List[Dict]:
    """
    Extract budget worksheet items from G-type budget worksheet pages.
    """
    page_num = page_data['page_number']
    
    # Get both extraction texts
    pdfplumber_text = page_data.get('pdfplumber_text', '').strip()
    pymupdf_text = page_data.get('pymupdf_text', '').strip()
    
    if not pdfplumber_text and not pymupdf_text:
        return []
    
    # Extract document-level metadata (date and title) from the first few lines
    document_date = "unknown"
    worksheet_title = "unknown"
    detail_type = "unknown"
    
    # Try to extract date and title from both text sources
    for text_source in [pdfplumber_text, pymupdf_text]:
        if text_source:
            lines = text_source.split('\n')[:10]  # Look at first 10 lines
            for line in lines:
                line = line.strip()
                # Look for date pattern like "Tuesday, February 25, 2025 1:43 pm"
                if any(day in line for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']):
                    if '2025' in line or '2024' in line or '2026' in line:
                        document_date = line
                        break
            
            # Look for worksheet title and detail type
            text_upper = text_source.upper()
            if 'BUDGET WORKSHEET' in text_upper:
                worksheet_title = "BUDGET WORKSHEET"
            if 'DETAIL TYPE:' in text_upper:
                # Extract detail type (G, S, etc.)
                lines = text_source.split('\n')
                for i, line in enumerate(lines):
                    if 'Detail Type:' in line or 'DETAIL TYPE:' in line:
                        # Look for single letter after colon
                        parts = line.split(':')
                        if len(parts) > 1:
                            detail_type_candidate = parts[1].strip().split()[0] if parts[1].strip() else ""
                            if detail_type_candidate and len(detail_type_candidate) == 1:
                                detail_type = detail_type_candidate
                                break

    # Prepare previous page context
    previous_page_context = ""
    if previous_page_data:
        prev_pdfplumber = previous_page_data.get('pdfplumber_text', '').strip()
        prev_pymupdf = previous_page_data.get('pymupdf_text', '').strip()
        
        if prev_pdfplumber or prev_pymupdf:
            # Use entire previous page content - no limits
            previous_page_context = f"""
PREVIOUS PAGE CONTEXT (Page {previous_page_data.get('page_number', 'unknown')}):
PDFPlumber: {prev_pdfplumber if prev_pdfplumber else "No text"}
PyMuPDF: {prev_pymupdf if prev_pymupdf else "No text"}
"""

    # Prepare recent items context with more detailed information
    recent_items_context = ""
    if recent_items:
        recent_items_context = "RECENT BUDGET WORKSHEET ITEMS FOR CONTEXT (showing patterns and continuation):\n"
        for i, item in enumerate(recent_items):
            recent_items_context += f"""
Item {i+1} (Page {item.get('page_number', 'unknown')}):
- Program ID: {item.get('program_id', 'unknown')}
- Program Name: {item.get('program_name', 'unknown')}
- Structure #: {item.get('structure_number', 'unknown')}
- Committee: {item.get('subject_committee', 'unknown')}
- Sequence: {item.get('sequence_number', 'unknown')}
- Explanation: {str(item.get('explanation', 'unknown'))[:200]}{'...' if len(str(item.get('explanation', ''))) > 200 else ''}
- FY26 Amount: {item.get('fy26_amount', 'unknown')} (MOF: {item.get('fy26_mof', 'unknown')})
- FY27 Amount: {item.get('fy27_amount', 'unknown')} (MOF: {item.get('fy27_mof', 'unknown')})
- Request Type: {item.get('request_type', 'unknown')}
- Date: {item.get('date', 'unknown')}
- Worksheet Title: {item.get('worksheet_title', 'unknown')}
- Detail Type: {item.get('detail_type', 'unknown')}
"""

    # Try up to 3 times to get complete budget items
    max_retries = 3
    previous_attempt_results = None
    
    for attempt in range(max_retries):
        print(f"    Attempt {attempt + 1}/{max_retries} for {document_name} page {page_num}")
        
        # Create prompt for different attempt levels
        if attempt == 0:
            # First attempt - standard prompt with context
            prompt = f"""
You are analyzing a BUDGET WORKSHEET document page to extract budget line items. You have two different text extractions from the same page and context from previous pages.

{previous_page_context}

{recent_items_context}

CURRENT PAGE EXTRACTIONS (Page {page_num}):
EXTRACTION 1 - PDFPlumber:
{pdfplumber_text[:2000] if pdfplumber_text else "No PDFPlumber text available"}

EXTRACTION 2 - PyMuPDF:
{pymupdf_text[:2000] if pymupdf_text else "No PyMuPDF text available"}

TASK: Extract budget worksheet items from this page with the following structure:

BUDGET WORKSHEET SCHEMA:
{{
  "program_id": "Program identifier (e.g., AGR101, BED144)",
  "program_name": "Full program name",
  "structure_number": "Structure number (e.g., 010301000000)",
  "subject_committee": "Subject committee code and name",
  "sequence_number": "Sequence number from line items",
  "explanation": "Budget line explanation/description - look for OBJECTIVE:, JUDICIARY REQUEST:, etc.",
  "fy26_amount": "FY26 dollar amount",
  "fy26_mof": "FY26 method of financing code",
  "fy27_amount": "FY27 dollar amount", 
  "fy27_mof": "FY27 method of financing code",
  "request_type": "Type of request",
  "date": "Document date from header",
  "worksheet_title": "Worksheet title from header"
}}

IMPORTANT EXTRACTION RULES:
1. Look for Program ID patterns like AGR101, BED144, etc.
2. Structure numbers are long numeric codes like 010301000000
3. Sequence numbers follow patterns like 4-001, 60-001, 100-001
4. MOF codes: A=General Funds, B=Special Funds, C=Capital Projects, P=Position costs, T=Trust, U=Federal, W=Working capital
5. For explanations, look for text that starts with keywords like:
   - "OBJECTIVE:"
   - "JUDICIARY REQUEST:"
   - "DETAIL OF JUDICIARY REQUEST:"
   - "EXECUTIVE BUDGET SUPPORT"
   - Do NOT use "BASE APPROPRIATIONS" as an explanation
6. Use "unknown" only if information is truly not present
7. For date and worksheet_title, extract from document header

Return a JSON array of budget worksheet items. If no items found, return empty array [].

JSON Array:
"""
        else:
            # Retry attempts - provide context about previous attempt and what needs fixing
            unknown_fields_summary = ""
            missing_fields_by_item = []
            
            if previous_attempt_results:
                unknown_fields_summary = "PREVIOUS ATTEMPT RESULTS ANALYSIS:\n"
                for i, item in enumerate(previous_attempt_results):
                    missing_fields = []
                    for key, value in item.items():
                        if str(value).lower() == 'unknown':
                            missing_fields.append(key)
                    
                    if missing_fields:
                        missing_fields_by_item.append({
                            'item_index': i,
                            'missing_fields': missing_fields,
                            'partial_data': {k: v for k, v in item.items() if str(v).lower() != 'unknown'}
                        })
                        unknown_fields_summary += f"Item {i+1}: Missing {', '.join(missing_fields)}\n"
                        unknown_fields_summary += f"  Known data: {item.get('program_id', 'unknown')}, {item.get('program_name', 'unknown')}, {item.get('sequence_number', 'unknown')}\n"
                
                unknown_fields_summary += f"\nPREVIOUS ATTEMPT EXTRACTED {len(previous_attempt_results)} ITEMS:\n"
                for i, item in enumerate(previous_attempt_results):
                    unknown_fields_summary += f"Item {i+1}: {json.dumps(item, indent=2)}\n"
            
            prompt = f"""
You are analyzing a BUDGET WORKSHEET document page to extract budget line items. This is RETRY ATTEMPT {attempt + 1} - you need to improve upon the previous extraction results.

{unknown_fields_summary}

SPECIFIC TASK FOR THIS RETRY:
Based on the previous attempt, you need to:
1. KEEP all the correct data that was already extracted
2. FILL IN the missing "unknown" values by looking more carefully at the text
3. Look specifically for the missing fields identified above
4. Use the exact same item structure but with better completeness

{previous_page_context}

{recent_items_context}

CURRENT PAGE EXTRACTIONS (Page {page_num}):
EXTRACTION 1 - PDFPlumber:
{pdfplumber_text[:2000] if pdfplumber_text else "No PDFPlumber text available"}

EXTRACTION 2 - PyMuPDF:
{pymupdf_text[:2000] if pymupdf_text else "No PyMuPDF text available"}

FOCUSED GUIDANCE FOR MISSING FIELDS:
- For program_name: Look for descriptive text near the program_id
- For structure_number: Look for long numeric sequences like 010301000000
- For subject_committee: Look for committee codes like "AEN AGRICULTURE AND ENVIRONMENT", "WAM WAYS AND MEANS"
- For sequence_number: Look for patterns like 4-001, 60-001, 100-001, 102-001
- For explanations: Search carefully for descriptive text that starts with:
  * "OBJECTIVE:" followed by program description
  * "JUDICIARY REQUEST:" or "DETAIL OF JUDICIARY REQUEST:" 
  * "EXECUTIVE BUDGET SUPPORT" or similar executive language
  * "SENATE REQUEST:" or "HOUSE REQUEST:"
- For MOF codes: Look for single letters (A, B, C, P, T, U, W) near dollar amounts
- For amounts: Look for dollar values, may be formatted with commas or in parentheses for negatives
- For request_type: Look for text like "EXECUTIVE BUDGET PREP", "EXECUTIVE REQUEST"

BUDGET WORKSHEET SCHEMA:
{{
  "program_id": "Program identifier (e.g., AGR101, BED144)",
  "program_name": "Full program name",
  "structure_number": "Structure number (e.g., 010301000000)",
  "subject_committee": "Subject committee code and name",
  "sequence_number": "Sequence number from line items",
  "explanation": "Budget line explanation/description",
  "fy26_amount": "FY26 dollar amount",
  "fy26_mof": "FY26 method of financing code",
  "fy27_amount": "FY27 dollar amount", 
  "fy27_mof": "FY27 method of financing code",
  "request_type": "Type of request",
  "date": "Document date from header",
  "worksheet_title": "Worksheet title from header"
}}

Return a JSON array with the SAME NUMBER OF ITEMS but with improved completeness:
"""

        try:
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean up response
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            # Parse JSON response
            worksheet_items = json.loads(response_text.strip())
            
            if not worksheet_items:
                if attempt == max_retries - 1:
                    print(f"      No worksheet items found after {max_retries} attempts")
                    return []
                continue
            
            # Count unknowns in this attempt
            total_unknowns = 0
            unknown_fields = []
            for item in worksheet_items:
                for key, value in item.items():
                    if str(value).lower() == 'unknown':
                        total_unknowns += 1
                        unknown_fields.append(f"{key}")
            
            print(f"      Found {len(worksheet_items)} worksheet items with {total_unknowns} unknown values")
            if total_unknowns > 0:
                print(f"      Unknown fields: {', '.join(set(unknown_fields))}")
            
            # Store this attempt's results for potential next retry
            previous_attempt_results = worksheet_items.copy()
            
            # If we have items with few/no unknowns, we can stop early
            if total_unknowns == 0:
                print(f"      Perfect extraction - no unknown values, stopping early")
            elif total_unknowns <= 3 and attempt >= 1:  # Allow some unknowns after first retry
                print(f"      Good extraction with minimal unknowns, stopping early")
            elif total_unknowns > 0 and attempt < max_retries - 1:
                # Show improvement from previous attempt
                if attempt > 0 and len(previous_attempt_results) > 0:
                    prev_unknowns = sum(1 for item in previous_attempt_results for v in item.values() if str(v).lower() == 'unknown')
                    if total_unknowns < prev_unknowns:
                        print(f"      Improved from {prev_unknowns} to {total_unknowns} unknowns, retrying for more...")
                    else:
                        print(f"      No improvement in unknowns, retrying with different approach...")
                else:
                    print(f"      Retrying to reduce unknown values...")
                continue
            
            # Add metadata to each item
            for i, item in enumerate(worksheet_items):
                # Auto-derive program_name from program_id if program_name is unknown
                program_id = item.get('program_id', 'unknown')
                program_name = item.get('program_name', 'unknown')
                
                # If program_id is found but program_name is unknown, try to derive it
                if (program_id != 'unknown' and str(program_id).strip() and 
                    (program_name == 'unknown' or not str(program_name).strip())):
                    # Look for program name in the text extractions near the program_id
                    for text_source in [pdfplumber_text, pymupdf_text]:
                        if text_source and program_id in text_source:
                            # Try to find text after program_id that looks like a program name
                            lines = text_source.split('\n')
                            for line in lines:
                                if program_id in line:
                                    # Extract text after program_id
                                    parts = line.split(program_id)
                                    if len(parts) > 1:
                                        potential_name = parts[1].strip().split('\t')[0].split('  ')[0]
                                        if potential_name and len(potential_name) > 3:
                                            program_name = potential_name
                                            print(f"      Derived program_name '{potential_name}' from program_id '{program_id}'")
                                            break
                                    if program_name != 'unknown':
                                        break
                            if program_name != 'unknown':
                                break
                
                structured_item = {
                    "program_id": item.get('program_id', 'unknown'),
                    "program_name": program_name,
                    "structure_number": item.get('structure_number', 'unknown'),
                    "subject_committee": item.get('subject_committee', 'unknown'),
                    "sequence_number": item.get('sequence_number', 'unknown'),
                    "explanation": item.get('explanation', 'unknown'),
                    "fy26_amount": item.get('fy26_amount', 'unknown'),
                    "fy26_mof": item.get('fy26_mof', 'unknown'),
                    "fy27_amount": item.get('fy27_amount', 'unknown'),
                    "fy27_mof": item.get('fy27_mof', 'unknown'),
                    "request_type": item.get('request_type', 'unknown'),
                    "date": item.get('date', document_date),
                    "worksheet_title": item.get('worksheet_title', worksheet_title),
                    
                    # Metadata
                    "item_number": i + 1,
                    "document_name": document_name,
                    "document_type": document_type,
                    "detail_type": detail_type,
                    "page_number": page_num,
                    "extraction_method": "gemini_dual_worksheet_test",
                    "extraction_attempts": attempt + 1,
                    "has_unknown_values": any(str(v).lower() == 'unknown' for v in item.values())
                }
                
                worksheet_items[i] = structured_item
            
            return worksheet_items
            
        except json.JSONDecodeError as e:
            print(f"      JSON decode error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                return []
            continue
        except Exception as e:
            print(f"      Error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                return []
            continue
    
    return []

def extract_cip_items(page_data: Dict, document_name: str, model, document_type: str,
                     previous_page_data: Dict = None, recent_items: List[Dict] = []) -> List[Dict]:
    """
    Extract Capital Improvement Project (CIP) items.
    """
    page_num = page_data['page_number']
    
    # Get both extraction texts
    pdfplumber_text = page_data.get('pdfplumber_text', '').strip()
    pymupdf_text = page_data.get('pymupdf_text', '').strip()
    
    if not pdfplumber_text and not pymupdf_text:
        return []
    
    # Extract document-level metadata
    document_date = "unknown"
    worksheet_title = "unknown"
    detail_type = "unknown"
    
    for text_source in [pdfplumber_text, pymupdf_text]:
        if text_source:
            lines = text_source.split('\n')[:10]
            for line in lines:
                line = line.strip()
                if any(day in line for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']):
                    if '2025' in line or '2024' in line or '2026' in line:
                        document_date = line
                        break
            
            text_upper = text_source.upper()
            if 'CAPITAL IMPROVEMENT' in text_upper or 'CIP' in text_upper:
                worksheet_title = "CAPITAL IMPROVEMENT PROJECT"
            elif 'BUDGET WORKSHEET' in text_upper:
                worksheet_title = "BUDGET WORKSHEET"

    # Simplified CIP extraction for testing
    prompt = f"""
Extract CIP items from this page:

{pdfplumber_text[:2000] if pdfplumber_text else pymupdf_text[:2000]}

Return JSON array with schema:
{{
  "program_id": "Program ID",
  "title": "Project title", 
  "agency": "Agency code",
  "fy26_amount": "FY26 amount",
  "fy27_amount": "FY27 amount",
  "mof": "MOF code",
  "date": "Document date",
  "worksheet_title": "Worksheet title"
}}

JSON Array:
"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        
        cip_items = json.loads(response_text.strip())
        
        if not cip_items:
            return []
        
        for i, item in enumerate(cip_items):
            structured_item = {
                "program_id": item.get('program_id', 'unknown'),
                "title": item.get('title', 'unknown'),
                "agency": item.get('agency', 'unknown'),
                "fy26_amount": item.get('fy26_amount', 'unknown'),
                "fy27_amount": item.get('fy27_amount', 'unknown'),
                "mof": item.get('mof', 'unknown'),
                "date": item.get('date', document_date),
                "worksheet_title": item.get('worksheet_title', worksheet_title),
                
                "item_number": i + 1,
                "document_name": document_name,
                "document_type": document_type,
                "detail_type": detail_type,
                "page_number": page_num,
                "extraction_method": "gemini_dual_worksheet_test",
                "has_unknown_values": any(str(v).lower() == 'unknown' for v in item.values())
            }
            
            cip_items[i] = structured_item
        
        print(f"      Found {len(cip_items)} CIP items")
        return cip_items
        
    except Exception as e:
        print(f"      Error: {e}")
        return []

def extract_text_item_with_dual_text(page_data: Dict, document_name: str, model, document_type: str) -> Dict:
    """
    Extract text item for every page.
    """
    page_num = page_data['page_number']
    
    pdfplumber_text = page_data.get('pdfplumber_text', '').strip()
    pymupdf_text = page_data.get('pymupdf_text', '').strip()
    
    if not pdfplumber_text and not pymupdf_text:
        return {}
    
    # Simple text extraction for testing
    better_text = pdfplumber_text if len(pdfplumber_text) > len(pymupdf_text) else pymupdf_text
    
    return {
        'text': better_text[:1000] + "..." if len(better_text) > 1000 else better_text,
        'document_name': document_name,
        'document_type': document_type,
        'page_number': page_num,
        'extraction_method': 'simple_test'
    }

def save_processed_data(processed_data: Dict, output_path: str):
    """
    Save the processed data to a JSON file.
    """
    with open(output_path, 'w') as f:
        json.dump(processed_data, f, indent=2)

# Main testing script
if __name__ == "__main__":
    # Check for API key
    if not os.environ.get('GEMINI_API_KEY'):
        print("Please set the GEMINI_API_KEY environment variable")
        exit(1)
    
    # Load data
    try:
        all_data = load_extracted_data()
    except Exception as e:
        print(f"Error loading extracted data: {e}")
        exit(1)
    
    # Select 4 documents for testing
    document_names = list(all_data.keys())
    selected_docs = document_names[:4]  # First 4 documents
    
    print("Testing with 4 documents, 5 pages each:")
    for doc in selected_docs:
        print(f"  - {doc}")
    print("="*80)
    
    # Initialize Gemini model
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    all_results = {}
    
    for doc_name in selected_docs:
        try:
            result = process_budget_worksheet_document_limited(doc_name, all_data[doc_name], model, max_pages=5)
            all_results[doc_name] = result
            
            # Print summary for this document
            print(f"\nSUMMARY for {doc_name}:")
            print(f"  Document type: {result['metadata']['document_type']}")
            print(f"  Pages processed: {result['metadata']['processed_pages']}")
            print(f"  Budget worksheet items: {len(result['budget_worksheet_items'])}")
            print(f"  Text items: {len(result['text_items'])}")
            
            # Show sample items with new fields
            if result['budget_worksheet_items']:
                print(f"\n--- Sample Items (first 2) ---")
                for i, item in enumerate(result['budget_worksheet_items'][:2]):
                    print(f"\nItem {i+1}:")
                    print(f"  Date: {item.get('date', 'N/A')}")
                    print(f"  Worksheet Title: {item.get('worksheet_title', 'N/A')}")
                    print(f"  Detail Type: {item.get('detail_type', 'N/A')}")
                    print(f"  Program ID: {item.get('program_id', 'N/A')}")
                    print(f"  Program Name: {item.get('program_name', 'N/A')[:50]}...")
                    print(f"  FY26 Amount: {item.get('fy26_amount', 'N/A')} (MOF: {item.get('fy26_mof', 'N/A')})")
            
            print(f"\n{'-'*40}")
            
        except Exception as e:
            print(f"Error processing {doc_name}: {e}")
            continue
    
    # Save combined results
    output_path = 'test_results_4_docs_5_pages.json'
    save_processed_data(all_results, output_path)
    print(f"\nTest results saved to: {output_path}")
    print(f"Processed {len(selected_docs)} documents with 5 pages each") 