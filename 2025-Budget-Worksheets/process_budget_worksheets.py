import json
import re
import os
import google.generativeai as genai
from typing import Dict, List, Union, Any, Optional, Tuple
import time
import sys
from multiprocessing import Pool, cpu_count

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

def process_budget_worksheet_document(document_name: str, pages_data: List[Dict], model) -> Dict[str, Any]:
    """
    Process budget worksheet document using Gemini AI to extract budget items and text items.
    """
    
    result = {
        'budget_items': [],
        'text_items': [],
        'metadata': {
            'document_name': document_name,
            'total_pages': len(pages_data),
            'processed_pages': 0,
            'extraction_method': 'gemini_dual_budget_worksheet',
            'budget_items_with_unknowns': 0,
            'total_unknown_fields': 0,
            'unknown_field_breakdown': {
                'program_id': 0,
                'program_name': 0,
                'structure_number': 0,
                'subject_committee': 0,
                'sequence_number': 0,
                'explanation': 0,
                'fy26_amount': 0,
                'fy26_mof': 0,
                'fy27_amount': 0,
                'fy27_mof': 0,
                'date': 0,
                'worksheet_title': 0
            }
        }
    }
    
    # Process all pages
    for i, page_data in enumerate(pages_data):
        page_num = page_data['page_number']
        
        # Classify document type based on text content
        sample_text = (page_data.get('pdfplumber_text', '') + ' ' + page_data.get('pymupdf_text', ''))[:1000]
        document_type = classify_document_type(document_name, sample_text)
        
        print(f"Processing {document_name} page {page_num} (type: {document_type})...")
        
        try:
            # Get previous page context
            previous_page_data = pages_data[i-1] if i > 0 else None
            
            # Get last 3 budget items as context for budget worksheets
            recent_budget_items = result['budget_items'][-3:] if len(result['budget_items']) >= 3 else result['budget_items']
            
            # Extract budget items based on document type with context
            if document_type == "budget_worksheet":
                budget_items = extract_budget_worksheet_items(
                    page_data, document_name, model, document_type,
                    previous_page_data=previous_page_data,
                    recent_items=recent_budget_items
                )
            elif document_type == "cip":
                budget_items = extract_cip_items(
                    page_data, document_name, model, document_type,
                    previous_page_data=previous_page_data,
                    recent_items=recent_budget_items
                )
            else:
                budget_items = []
            
            if budget_items:
                result['budget_items'].extend(budget_items)
                
                # Track unknown statistics
                for item in budget_items:
                    if item.get('has_unknown_values', False):
                        result['metadata']['budget_items_with_unknowns'] += 1
                    
                    # Count specific unknown fields based on document type
                    if document_type == "budget_worksheet":
                        fields_to_check = ['program_id', 'program_name', 'structure_number', 
                                         'subject_committee', 'sequence_number', 'explanation',
                                         'fy26_amount', 'fy26_mof', 'fy27_amount', 'fy27_mof',
                                         'date', 'worksheet_title']
                    else:  # CIP
                        fields_to_check = ['project_name', 'agency', 'project_id', 'explanation',
                                         'fy26_amount', 'fy26_mof', 'fy27_amount', 'fy27_mof',
                                         'date', 'worksheet_title']
                    
                    for field in fields_to_check:
                        if str(item.get(field, '')).lower() == 'unknown':
                            result['metadata']['total_unknown_fields'] += 1
                            # Map CIP fields to budget worksheet field names for tracking
                            if field in ['project_name']:
                                result['metadata']['unknown_field_breakdown']['program_name'] += 1
                            elif field in ['agency']:
                                result['metadata']['unknown_field_breakdown']['program_id'] += 1
                            elif field in ['project_id']:
                                result['metadata']['unknown_field_breakdown']['structure_number'] += 1
                            elif field in result['metadata']['unknown_field_breakdown']:
                                result['metadata']['unknown_field_breakdown'][field] += 1
            
            # Extract text item for every page
            text_item = extract_text_item_with_dual_text(page_data, document_name, model, document_type)
            if text_item:
                result['text_items'].append(text_item)
            
            result['metadata']['processed_pages'] += 1
            
            # Small delay to avoid rate limiting
            time.sleep(0.15)
            
        except Exception as e:
            print(f"Error processing {document_name} page {page_num}: {e}")
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
{pdfplumber_text if pdfplumber_text else "No PDFPlumber text available"}

EXTRACTION 2 - PyMuPDF:
{pymupdf_text if pymupdf_text else "No PyMuPDF text available"}

TASK: Extract budget worksheet items from this page. These are G-type budget worksheets with the following structure:

BUDGET WORKSHEET SCHEMA:
{{
  "program_id": "Program identifier (e.g., AGR101, BED144)",
  "program_name": "Full program name",
  "structure_number": "Structure number (e.g., 010301000000)",
  "subject_committee": "Subject committee code and name (e.g., AEN AGRICULTURE AND ENVIRONMENT)",
  "sequence_number": "Sequence number from line items (e.g., 4-001, 60-001, 100-001)",
  "explanation": "Budget line explanation/description - look for text starting with OBJECTIVE:, JUDICIARY REQUEST:, DETAIL OF JUDICIARY REQUEST:, EXECUTIVE BUDGET SUPPORT, etc.",
  "position_change_perm": "Permanent position change (number with decimal)",
  "position_change_temp": "Temporary position change (number with decimal)",
  "fy26_amount": "FY26 dollar amount (number without commas)",
  "fy26_mof": "FY26 method of financing code (A, B, C, P, T, U, W)",
  "fy27_amount": "FY27 dollar amount (number without commas)",
  "fy27_mof": "FY27 method of financing code (A, B, C, P, T, U, W)",
  "request_type": "Type of request (EXECUTIVE BUDGET PREP, EXECUTIVE REQUEST, etc.)",
  "date": "Document date (e.g., Tuesday, February 25, 2025 1:43 pm)",
  "worksheet_title": "Worksheet title (e.g., BUDGET WORKSHEET)"
}}

IMPORTANT EXTRACTION RULES:
1. Look for Program ID patterns like AGR101, BED144, etc.
2. Structure numbers are long numeric codes like 010301000000
3. Sequence numbers follow patterns like 4-001, 60-001, 100-001
4. MOF codes: A=General Funds, B=Special Funds, C=Capital Projects, P=Position costs, T=Trust, U=Federal, W=Working capital
5. Amounts can be positive or negative (in parentheses)
6. Use context from previous pages and recent items to understand continuation patterns
7. Base appropriations are different from budget changes - focus on line items with sequence numbers
8. For explanations, look for text that starts with keywords like:
   - "OBJECTIVE:"
   - "JUDICIARY REQUEST:"
   - "DETAIL OF JUDICIARY REQUEST:"
   - "EXECUTIVE BUDGET SUPPORT"
   - "SENATE REQUEST:"
   - "HOUSE REQUEST:"
   - Do NOT use "BASE APPROPRIATIONS" as an explanation
9. Use "unknown" only if information is truly not present
10. Each page may contain multiple line items or continue from previous pages
11. For date and worksheet_title, extract from document header (usually at top of page)

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
{pdfplumber_text if pdfplumber_text else "No PDFPlumber text available"}

EXTRACTION 2 - PyMuPDF:
{pymupdf_text if pymupdf_text else "No PyMuPDF text available"}

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
- For position changes: Look for decimal numbers indicating staff changes
- For request_type: Look for text like "EXECUTIVE BUDGET PREP", "EXECUTIVE REQUEST"

TASK: Return the IMPROVED extraction with the same items but filled-in unknown values where possible.

BUDGET WORKSHEET SCHEMA:
{{
  "program_id": "Program identifier (e.g., AGR101, BED144)",
  "program_name": "Full program name",
  "structure_number": "Structure number (e.g., 010301000000)",
  "subject_committee": "Subject committee code and name",
  "sequence_number": "Sequence number from line items",
  "explanation": "Budget line explanation/description starting with OBJECTIVE:, JUDICIARY REQUEST:, etc.",
  "position_change_perm": "Permanent position change",
  "position_change_temp": "Temporary position change",
  "fy26_amount": "FY26 dollar amount",
  "fy26_mof": "FY26 method of financing code",
  "fy27_amount": "FY27 dollar amount",
  "fy27_mof": "FY27 method of financing code",
  "request_type": "Type of request",
  "date": "Document date",
  "worksheet_title": "Worksheet title"
}}

Return a JSON array with the SAME NUMBER OF ITEMS but with improved completeness:
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
            worksheet_items = json.loads(response_text)
            
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
                
                structured_item = {
                    "program_id": item.get('program_id', 'unknown'),
                    "program_name": program_name,
                    "structure_number": item.get('structure_number', 'unknown'),
                    "subject_committee": item.get('subject_committee', 'unknown'),
                    "sequence_number": item.get('sequence_number', 'unknown'),
                    "explanation": item.get('explanation', 'unknown'),
                    "position_change_perm": item.get('position_change_perm', 'unknown'),
                    "position_change_temp": item.get('position_change_temp', 'unknown'),
                    "fy26_amount": item.get('fy26_amount', 'unknown'),
                    "fy26_mof": item.get('fy26_mof', 'unknown'),
                    "fy27_amount": item.get('fy27_amount', 'unknown'),
                    "fy27_mof": item.get('fy27_mof', 'unknown'),
                    "request_type": item.get('request_type', 'unknown'),
                    "date": item.get('date', document_date),  # Use extracted date as fallback
                    "worksheet_title": item.get('worksheet_title', worksheet_title),  # Use extracted title as fallback
                    
                    # Metadata
                    "item_number": i + 1,
                    "document_name": document_name,
                    "document_type": document_type,
                    "detail_type": detail_type,  # Add detail type (G, S, etc.)
                    "page_number": page_num,
                    "extraction_method": "gemini_dual_worksheet",
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
    Extract Capital Improvement Project items from CIP pages.
    """
    page_num = page_data['page_number']
    
    # Get both extraction texts
    pdfplumber_text = page_data.get('pdfplumber_text', '').strip()
    pymupdf_text = page_data.get('pymupdf_text', '').strip()
    
    if not pdfplumber_text and not pymupdf_text:
        return []
    
    # Extract document-level metadata (date and title) from the first few lines
    document_date = "unknown"
    worksheet_title = "CAPITAL IMPROVEMENT PROJECT"  # Default for CIP
    
    # Try to extract date from both text sources
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
            
            # Look for CIP-specific title
            text_upper = text_source.upper()
            if 'CAPITAL IMPROVEMENT PROJECT' in text_upper:
                worksheet_title = "CAPITAL IMPROVEMENT PROJECT"
            elif 'CIP' in text_upper:
                worksheet_title = "CIP"
    
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
        recent_items_context = "RECENT CIP ITEMS FOR CONTEXT (showing patterns and continuation):\n"
        for i, item in enumerate(recent_items):
            recent_items_context += f"""
Item {i+1} (Page {item.get('page_number', 'unknown')}):
- Project Name: {item.get('project_name', 'unknown')}
- Agency: {item.get('agency', 'unknown')}
- Project ID: {item.get('project_id', 'unknown')}
- Project Description: {str(item.get('project_description', 'unknown'))[:150]}{'...' if len(str(item.get('project_description', ''))) > 150 else ''}
- Explanation: {str(item.get('explanation', 'unknown'))[:200]}{'...' if len(str(item.get('explanation', ''))) > 200 else ''}
- FY26 Amount: {item.get('fy26_amount', 'unknown')} (MOF: {item.get('fy26_mof', 'unknown')})
- FY27 Amount: {item.get('fy27_amount', 'unknown')} (MOF: {item.get('fy27_mof', 'unknown')})
- Total Project Cost: {item.get('total_project_cost', 'unknown')}
- Funding Source: {item.get('funding_source', 'unknown')}
- Request Type: {item.get('request_type', 'unknown')}
- Date: {item.get('date', 'unknown')}
- Worksheet Title: {item.get('worksheet_title', 'unknown')}
"""
    
    # Try up to 3 times to get complete CIP items
    max_retries = 3
    previous_attempt_results = None
    
    for attempt in range(max_retries):
        print(f"    Attempt {attempt + 1}/{max_retries} for {document_name} page {page_num}")
        
        # Create prompt for different attempt levels
        if attempt == 0:
            # First attempt - standard prompt with context
            prompt = f"""
You are analyzing a CAPITAL IMPROVEMENT PROJECT (CIP) document page to extract project items. You have two different text extractions from the same page and context from previous pages.

{previous_page_context}

{recent_items_context}

CURRENT PAGE EXTRACTIONS (Page {page_num}):
EXTRACTION 1 - PDFPlumber:
{pdfplumber_text if pdfplumber_text else "No PDFPlumber text available"}

EXTRACTION 2 - PyMuPDF:
{pymupdf_text if pymupdf_text else "No PyMuPDF text available"}

TASK: Extract Capital Improvement Project items from this page. These are CIP documents with the following structure:

CIP SCHEMA:
{{
  "project_name": "Name of the capital improvement project",
  "agency": "Agency or department responsible",
  "project_id": "Project identifier/code",
  "project_description": "Description of the project",
  "explanation": "Project explanation/justification - look for OBJECTIVE:, JUDICIARY REQUEST:, DETAIL OF JUDICIARY REQUEST:, EXECUTIVE BUDGET SUPPORT, etc.",
  "fy26_amount": "FY26 dollar amount (number without commas)",
  "fy26_mof": "FY26 method of financing code (A, B, C, P, T, U, W)",
  "fy27_amount": "FY27 dollar amount (number without commas)",
  "fy27_mof": "FY27 method of financing code (A, B, C, P, T, U, W)",
  "total_project_cost": "Total project cost if specified",
  "funding_source": "Source of funding information",
  "request_type": "Type of request (EXECUTIVE REQUEST, etc.)",
  "date": "Document date",
  "worksheet_title": "Document title (CAPITAL IMPROVEMENT PROJECT)"
}}

IMPORTANT EXTRACTION RULES:
1. Look for project names and descriptions
2. Agency codes are usually 3-letter codes (DOT, DAGS, UH, etc.)
3. Project IDs may vary in format
4. MOF codes: A=General Funds, B=Special Funds, C=Capital Projects, P=Position costs, T=Trust, U=Federal, W=Working capital
5. Amounts can be positive or negative (in parentheses)
6. Use context from previous pages and recent items to understand continuation patterns
7. For explanations, look for text that starts with keywords like:
   - "OBJECTIVE:"
   - "JUDICIARY REQUEST:"
   - "DETAIL OF JUDICIARY REQUEST:"
   - "EXECUTIVE BUDGET SUPPORT"
   - "SENATE REQUEST:"
   - "HOUSE REQUEST:"
   - Do NOT use "BASE APPROPRIATIONS" as an explanation
8. Use "unknown" only if information is truly not present
9. Each page may contain multiple project items or continue from previous pages
10. For date and worksheet_title, extract from document header

Return a JSON array of CIP items. If no items found, return empty array [].

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
                        unknown_fields_summary += f"  Known data: {item.get('project_name', 'unknown')}, {item.get('agency', 'unknown')}, {item.get('project_id', 'unknown')}\n"
                
                unknown_fields_summary += f"\nPREVIOUS ATTEMPT EXTRACTED {len(previous_attempt_results)} ITEMS:\n"
                for i, item in enumerate(previous_attempt_results):
                    unknown_fields_summary += f"Item {i+1}: {json.dumps(item, indent=2)}\n"
            
            prompt = f"""
You are analyzing a CAPITAL IMPROVEMENT PROJECT (CIP) document page to extract project items. This is RETRY ATTEMPT {attempt + 1} - you need to improve upon the previous extraction results.

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
{pdfplumber_text if pdfplumber_text else "No PDFPlumber text available"}

EXTRACTION 2 - PyMuPDF:
{pymupdf_text if pymupdf_text else "No PyMuPDF text available"}

FOCUSED GUIDANCE FOR MISSING FIELDS:
- For project_name: Look for descriptive project titles or names
- For agency: Look for 3-letter agency codes (DOT, DAGS, UH, EDN, HTH)
- For project_id: Look for alphanumeric project identifiers, often with agency prefixes
- For project_description: Look for detailed descriptions of what the project entails
- For explanations: Search carefully for descriptive text that starts with:
  * "OBJECTIVE:" followed by project justification
  * "JUDICIARY REQUEST:" or "DETAIL OF JUDICIARY REQUEST:" 
  * "EXECUTIVE BUDGET SUPPORT" or similar executive language
  * "SENATE REQUEST:" or "HOUSE REQUEST:"
- For MOF codes: Look for single letters (A, B, C, P, T, U, W) near dollar amounts
- For amounts: Look for dollar values, may be formatted with commas or in parentheses for negatives
- For total_project_cost: Look for overall project cost figures
- For funding_source: Look for information about where funding comes from
- For request_type: Look for text like "EXECUTIVE REQUEST", "LEGISLATIVE REQUEST"

TASK: Return the IMPROVED extraction with the same items but filled-in unknown values where possible.

CIP SCHEMA:
{{
  "project_name": "Name of the capital improvement project",
  "agency": "Agency or department responsible",
  "project_id": "Project identifier/code",
  "project_description": "Description of the project",
  "explanation": "Project explanation starting with OBJECTIVE:, JUDICIARY REQUEST:, etc.",
  "fy26_amount": "FY26 dollar amount",
  "fy26_mof": "FY26 method of financing code",
  "fy27_amount": "FY27 dollar amount",
  "fy27_mof": "FY27 method of financing code",
  "total_project_cost": "Total project cost if specified",
  "funding_source": "Source of funding information",
  "request_type": "Type of request",
  "date": "Document date",
  "worksheet_title": "Document title"
}}

Return a JSON array with the SAME NUMBER OF ITEMS but with improved completeness:
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
            cip_items = json.loads(response_text)
            
            if not cip_items:
                if attempt == max_retries - 1:
                    print(f"      No CIP items found after {max_retries} attempts")
                    return []
                continue
            
            # Count unknowns in this attempt
            total_unknowns = 0
            unknown_fields = []
            for item in cip_items:
                for key, value in item.items():
                    if str(value).lower() == 'unknown':
                        total_unknowns += 1
                        unknown_fields.append(f"{key}")
            
            print(f"      Found {len(cip_items)} CIP items with {total_unknowns} unknown values")
            if total_unknowns > 0:
                print(f"      Unknown fields: {', '.join(set(unknown_fields))}")
            
            # Store this attempt's results for potential next retry
            previous_attempt_results = cip_items.copy()
            
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
            for i, item in enumerate(cip_items):
                # Auto-derive agency from project_id if agency is unknown
                project_id = item.get('project_id', 'unknown')
                agency = item.get('agency', 'unknown')
                
                # If project_id is found but agency is unknown, try to derive it
                if (project_id != 'unknown' and str(project_id).strip() and 
                    (agency == 'unknown' or not str(agency).strip())):
                    # Extract agency code from project_id (first few letters)
                    agency_match = re.match(r'^([A-Z]{2,4})', str(project_id))
                    if agency_match:
                        derived_agency = agency_match.group(1)
                        agency = derived_agency
                        print(f"      Derived agency '{derived_agency}' from project_id '{project_id}'")
                
                structured_item = {
                    "project_name": item.get('project_name', 'unknown'),
                    "agency": agency,
                    "project_id": item.get('project_id', 'unknown'),
                    "project_description": item.get('project_description', 'unknown'),
                    "explanation": item.get('explanation', 'unknown'),
                    "fy26_amount": item.get('fy26_amount', 'unknown'),
                    "fy26_mof": item.get('fy26_mof', 'unknown'),
                    "fy27_amount": item.get('fy27_amount', 'unknown'),
                    "fy27_mof": item.get('fy27_mof', 'unknown'),
                    "total_project_cost": item.get('total_project_cost', 'unknown'),
                    "funding_source": item.get('funding_source', 'unknown'),
                    "request_type": item.get('request_type', 'unknown'),
                    "date": item.get('date', document_date),  # Use extracted date as fallback
                    "worksheet_title": item.get('worksheet_title', worksheet_title),  # Use extracted title as fallback
                    
                    # Metadata
                    "item_number": i + 1,
                    "document_name": document_name,
                    "document_type": document_type,
                    "page_number": page_num,
                    "extraction_method": "gemini_dual_cip",
                    "extraction_attempts": attempt + 1,
                    "has_unknown_values": any(str(v).lower() == 'unknown' for v in item.values())
                }
                
                cip_items[i] = structured_item
            
            return cip_items
            
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

def extract_text_item_with_dual_text(page_data: Dict, document_name: str, model, document_type: str) -> Dict:
    """
    Use Gemini AI to extract text item for every page using both pdfplumber and pymupdf text.
    """
    page_num = page_data['page_number']
    
    # Get both extraction texts
    pdfplumber_text = page_data.get('pdfplumber_text', '').strip()
    pymupdf_text = page_data.get('pymupdf_text', '').strip()
    
    if not pdfplumber_text and not pymupdf_text:
        return {}
    
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
            elif 'CAPITAL IMPROVEMENT PROJECT' in text_upper:
                worksheet_title = "CAPITAL IMPROVEMENT PROJECT"
            elif 'CIP' in text_upper:
                worksheet_title = "CIP"
            
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
    
    # Create prompt for Gemini
    prompt = f"""
You are analyzing a budget document page to create a clean text representation. You have two different text extractions from the same page.

EXTRACTION 1 - PDFPlumber:
{pdfplumber_text if pdfplumber_text else "No PDFPlumber text available"}

EXTRACTION 2 - PyMuPDF:
{pymupdf_text if pymupdf_text else "No PyMuPDF text available"}

TASK: Create a JSON object with clean text representation.

Based on the document type ({document_type}) and quality of extractions, choose the best extraction method and create a clean text representation:
- If this appears to be a budget worksheet with tables, prefer the extraction that best preserves table structure
- If this appears to be descriptive text, prefer the extraction that best preserves readability
- Remove excessive whitespace, fix formatting issues
- Keep the content readable and well-structured

Return a JSON object with:
- text: The cleaned text content (choose the better extraction and clean it)
- date: Document date if found (e.g., "Tuesday, February 25, 2025 1:43 pm")
- worksheet_title: Document title if found (e.g., "BUDGET WORKSHEET" or "CAPITAL IMPROVEMENT PROJECT")

STRICT RULES:
1. Choose the extraction that best matches the document type and content
2. Clean up formatting but keep original content intact
3. Do NOT add information not in the original text
4. Return ONLY a valid JSON object
5. If both extractions are poor quality, return {{"text": "unknown", "date": "unknown", "worksheet_title": "unknown"}}

Example format:
{{
  "text": "This is the cleaned and formatted text content from the page...",
  "date": "Tuesday, February 25, 2025 1:43 pm",
  "worksheet_title": "BUDGET WORKSHEET"
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
        
        # Add metadata to the text item with fallbacks
        text_item['document_name'] = document_name
        text_item['document_type'] = document_type
        text_item['detail_type'] = detail_type
        text_item['page_number'] = page_num
        text_item['extraction_method'] = 'gemini_dual_text'
        
        # Use extracted metadata as fallbacks if not found by AI
        if not text_item.get('date') or text_item.get('date') == 'unknown':
            text_item['date'] = document_date
        if not text_item.get('worksheet_title') or text_item.get('worksheet_title') == 'unknown':
            text_item['worksheet_title'] = worksheet_title
        
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

def process_single_document(doc_name: str) -> Tuple[str, Dict]:
    """
    Process a single document - designed to be used by multiprocessing workers.
    Returns a tuple of (document_name, results_dict).
    """
    try:
        # Initialize Gemini model for this worker process
        if not os.environ.get('GEMINI_API_KEY'):
            return doc_name, {"error": "GEMINI_API_KEY not set"}
        
        genai.configure(api_key=os.environ['GEMINI_API_KEY'])
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Load data
        data = load_extracted_data()
        
        if doc_name not in data:
            return doc_name, {"error": f"Document {doc_name} not found"}
        
        print(f"Worker processing: {doc_name}")
        
        # Process the document
        results = process_budget_worksheet_document(doc_name, data[doc_name], model)
        
        print(f"Worker completed: {doc_name} - {len(results.get('worksheet_items', []))} worksheet items, {len(results.get('text_items', []))} text items")
        
        return doc_name, results
        
    except Exception as e:
        print(f"Worker error processing {doc_name}: {str(e)}")
        return doc_name, {"error": str(e)}

# Main processing script
if __name__ == "__main__":
    # Check for API key
    if not os.environ.get('GEMINI_API_KEY'):
        print("Please set the GEMINI_API_KEY environment variable")
        exit(1)
    
    # Get target document(s) from command line argument
    if len(sys.argv) < 2:
        # Show available documents
        try:
            data = load_extracted_data()
            print("Usage: python process_budget_worksheets.py <document_name_or_'all'>")
            print("Available documents:")
            for doc_name in sorted(data.keys()):
                doc_type = classify_document_type(doc_name, data[doc_name][0].get('pdfplumber_text', '') if data[doc_name] else '')
                print(f"  - {doc_name} ({doc_type})")
        except Exception as e:
            print(f"Error loading data: {e}")
        exit(1)
    
    target_document = sys.argv[1]
    
    try:
        if target_document.lower() == 'all':
            # Process all documents in parallel
            print("Processing ALL documents with parallel processing (6 workers)...")
            start_time = time.time()
            
            data = load_extracted_data()
            all_doc_names = list(data.keys())
            
            print(f"Found {len(all_doc_names)} documents to process")
            print("Starting parallel processing...")
            
            # Use multiprocessing with 6 workers
            with Pool(processes=6) as pool:
                # Process documents in parallel
                results = pool.map(process_single_document, all_doc_names)
            
            # Combine results
            all_processed_data = {}
            successful_docs = 0
            failed_docs = 0
            
            for doc_name, doc_results in results:
                if "error" in doc_results:
                    print(f"Failed to process {doc_name}: {doc_results['error']}")
                    failed_docs += 1
                    all_processed_data[doc_name] = {"error": doc_results["error"]}
                else:
                    all_processed_data[doc_name] = doc_results
                    successful_docs += 1
            
            # Save consolidated results
            output_file = 'all_budget_worksheets_processed.json'
            with open(output_file, 'w') as f:
                json.dump(all_processed_data, f, indent=2)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            print(f"\n=== PARALLEL PROCESSING COMPLETE ===")
            print(f"Total time: {processing_time:.2f} seconds")
            print(f"Successfully processed: {successful_docs} documents")
            print(f"Failed: {failed_docs} documents")
            print(f"Results saved to: {output_file}")
            
            # Show summary
            total_worksheet_items = 0
            total_text_items = 0
            for doc_name, doc_data in all_processed_data.items():
                if "error" not in doc_data:
                    total_worksheet_items += len(doc_data.get('worksheet_items', []))
                    total_text_items += len(doc_data.get('text_items', []))
            
            print(f"Total worksheet items extracted: {total_worksheet_items}")
            print(f"Total text items extracted: {total_text_items}")
            
        else:
            # Process single document (sequential for debugging)
            print(f"Processing single document: {target_document}")
            start_time = time.time()
            
            # Initialize model
            genai.configure(api_key=os.environ['GEMINI_API_KEY'])
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Load and process data
            data = load_extracted_data()
            
            if target_document not in data:
                print(f"Document '{target_document}' not found in extracted data")
                print("Available documents:")
                for doc_name in sorted(data.keys()):
                    print(f"  - {doc_name}")
                exit(1)
            
            # Process the document
            results = process_budget_worksheet_document(target_document, data[target_document], model)
            
            # Save single document results
            processed_data = {target_document: results}
            output_file = 'budget_worksheets_processed.json'
            with open(output_file, 'w') as f:
                json.dump(processed_data, f, indent=2)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            print(f"\n=== PROCESSING COMPLETE ===")
            print(f"Time: {processing_time:.2f} seconds")
            print(f"Worksheet items: {len(results.get('worksheet_items', []))}")
            print(f"Text items: {len(results.get('text_items', []))}")
            print(f"Results saved to: {output_file}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1) 