#!/usr/bin/env python3
"""
Gemini Text Cleaner - Clean up and parse already extracted budget text files
"""

import os
import json
import time
import re
from typing import List, Dict, Optional
from dotenv import load_dotenv
import google.generativeai as genai

class GeminiTextCleaner:
    def __init__(self, api_key: str):
        """Initialize the Gemini text cleaner with Google AI API key."""
        self.api_key = api_key
        self.model = None
        self.initialize_gemini()
    
    def initialize_gemini(self) -> None:
        """Initialize the Gemini model using Google AI API."""
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            print("✅ Successfully initialized Gemini API")
        except Exception as e:
            print(f"❌ Error initializing Gemini: {e}")
            raise

    def extract_budget_sections(self, text: str) -> List[str]:
        """Extract individual budget sections from the text."""
        sections = []
        
        # Split by page markers
        page_pattern = r'============================================================\nPAGE \d+ - (PDFPLUMBER|CAMELOT) EXTRACTION'
        pages = re.split(page_pattern, text)
        
        current_section = ""
        for i, page in enumerate(pages):
            if i == 0:  # Skip the header
                continue
            
            # Clean up the page content
            page_content = page.strip()
            if page_content and len(page_content) > 100:  # Only include substantial content
                current_section += page_content + "\n\n"
                
                # If we have enough content, add it as a section
                if len(current_section) > 5000:  # ~5KB chunks
                    sections.append(current_section.strip())
                    current_section = ""
        
        # Add any remaining content
        if current_section.strip():
            sections.append(current_section.strip())
            
        return sections

    def clean_and_structure_text(self, text_chunk: str) -> Dict:
        """Use Gemini to clean and structure a chunk of budget text."""
        
        prompt = """You are analyzing a section of a legislative budget document (HB300) that contains both regular text and financial tables. 

Your task is to:
1. Clean up the formatting and remove extraction artifacts
2. Extract structured budget information
3. Identify departments, programs, and financial details
4. Return clean, organized data

For each budget item you find, extract:
- Department/Agency name
- Program name and ID
- Dollar amounts (with proper formatting)
- Position counts (FTE)
- Fund types (A=General Fund, B=Special Fund, etc.)
- Appropriation type (Operating, Capital, etc.)

Return a JSON object with this structure:
{
  "cleaned_text": "Clean, readable version of the text content",
  "budget_items": [
    {
      "department": "Department name",
      "program": "Program name",
      "program_id": "Program ID (e.g., BED100)",
      "amount": 1234567,
      "amount_formatted": "$1,234,567",
      "fund_type": "General Fund",
      "fund_code": "A",
      "positions": 25.5,
      "appropriation_type": "Operating",
      "fiscal_year": "2025-2026"
    }
  ],
  "summary": {
    "total_items": 5,
    "total_amount": 12345678,
    "departments": ["Dept 1", "Dept 2"]
  }
}

Important:
- Fix formatting issues like missing spaces, broken words
- Convert fund codes to readable names (A=General Fund, B=Special Fund, etc.)
- Preserve exact dollar amounts and position counts
- Clean up table formatting but keep the financial data accurate
- If text is mostly legislative language without budget data, focus on cleaning the text

Here's the text to process:

""" + text_chunk

        try:
            response = self.model.generate_content(prompt)
            
            if response and hasattr(response, 'text'):
                response_text = response.text.strip()
                
                # Clean JSON from markdown formatting
                if '```json' in response_text:
                    response_text = response_text.split('```json')[1].split('```')[0]
                elif '```' in response_text:
                    response_text = response_text.split('```')[1].split('```')[0]
                
                try:
                    result = json.loads(response_text)
                    return result
                except json.JSONDecodeError as e:
                    print(f"⚠️  JSON decode error: {e}")
                    print(f"Raw response (first 500 chars): {response_text[:500]}...")
                    
                    # Try to extract JSON manually if it's malformed or truncated
                    try:
                        # Look for the actual JSON structure in the response
                        if response_text.startswith('{') and '"budget_items"' in response_text:
                            # Try to find the end of the JSON
                            brace_count = 0
                            json_end = 0
                            for i, char in enumerate(response_text):
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        json_end = i + 1
                                        break
                            
                            if json_end > 0:
                                clean_json = response_text[:json_end]
                                result = json.loads(clean_json)
                                return result
                    except:
                        pass
                    
                    # Return a basic structure with just cleaned text
                    return {
                        "cleaned_text": response_text,
                        "budget_items": [],
                        "summary": {"total_items": 0, "total_amount": 0, "departments": []}
                    }
            else:
                print("⚠️  No response from Gemini")
                return None
                
        except Exception as e:
            print(f"❌ Error processing with Gemini: {e}")
            return None

    def process_file(self, input_file: str, output_dir: str) -> Dict:
        """Process a single text file and return cleaned results."""
        
        print(f"\n🔄 Processing: {os.path.basename(input_file)}")
        
        # Read the input file
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            return {}
        
        print(f"📄 File size: {len(content):,} characters")
        
        # Extract sections from the text
        try:
            sections = self.extract_budget_sections(content)
            print(f"📑 Split into {len(sections)} sections")
        except Exception as e:
            print(f"❌ Error splitting into sections: {e}")
            return {}
        
        # Process each section
        all_budget_items = []
        all_cleaned_text = []
        all_departments = set()
        total_amount = 0
        successful_sections = 0
        failed_sections = 0
        
        for i, section in enumerate(sections, 1):
            print(f"   Processing section {i}/{len(sections)}...")
            
            try:
                result = self.clean_and_structure_text(section)
                if result:
                    # Collect cleaned text
                    cleaned_text = result.get('cleaned_text', '')
                    if cleaned_text and isinstance(cleaned_text, str):
                        all_cleaned_text.append(f"=== SECTION {i} ===\n{cleaned_text}")
                    
                    # Collect budget items
                    budget_items = result.get('budget_items', [])
                    if budget_items and isinstance(budget_items, list):
                        all_budget_items.extend(budget_items)
                        
                    # Collect summary info with robust error handling
                    summary = result.get('summary', {})
                    if summary and isinstance(summary, dict):
                        # Handle total_amount safely
                        summary_amount = summary.get('total_amount', 0)
                        if summary_amount is not None and isinstance(summary_amount, (int, float)):
                            total_amount += summary_amount
                        
                        # Handle departments safely
                        summary_depts = summary.get('departments', [])
                        if summary_depts and isinstance(summary_depts, list):
                            # Filter out None, empty strings, and non-string values
                            valid_depts = [dept for dept in summary_depts 
                                         if dept is not None and isinstance(dept, str) and dept.strip()]
                            all_departments.update(valid_depts)
                    
                    successful_sections += 1
                else:
                    failed_sections += 1
                    print(f"   ⚠️  Section {i} returned no result")
                    
            except Exception as e:
                failed_sections += 1
                print(f"   ❌ Error processing section {i}: {e}")
                continue
            
            # Rate limiting
            time.sleep(1)
        
        print(f"📊 Processing complete: {successful_sections} successful, {failed_sections} failed sections")
        
        # Compile final results with safe handling
        try:
            # Ensure all_departments contains only valid strings
            valid_departments = [dept for dept in all_departments 
                               if dept is not None and isinstance(dept, str) and dept.strip()]
            
            final_result = {
                "source_file": os.path.basename(input_file),
                "processed_sections": len(sections),
                "successful_sections": successful_sections,
                "failed_sections": failed_sections,
                "cleaned_text": "\n\n".join(all_cleaned_text) if all_cleaned_text else "",
                "budget_items": all_budget_items,
                "summary": {
                    "total_items": len(all_budget_items),
                    "total_amount": total_amount if isinstance(total_amount, (int, float)) else 0,
                    "departments": sorted(valid_departments)
                }
            }
            
            # Save results with error handling
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            
            try:
                # Save cleaned text
                cleaned_text_file = os.path.join(output_dir, f"{base_name}_cleaned.txt")
                with open(cleaned_text_file, 'w', encoding='utf-8') as f:
                    f.write(final_result['cleaned_text'])
                print(f"   📄 Cleaned text saved: {cleaned_text_file}")
            except Exception as e:
                print(f"   ⚠️  Could not save cleaned text: {e}")
            
            try:
                # Save structured data
                json_file = os.path.join(output_dir, f"{base_name}_structured.json")
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(final_result, f, indent=2, ensure_ascii=False)
                print(f"   📁 JSON data saved: {json_file}")
            except Exception as e:
                print(f"   ⚠️  Could not save JSON data: {e}")
            
            print(f"✅ Completed processing")
            print(f"   📊 Extracted {len(all_budget_items)} budget items")
            print(f"   🏛️  Found {len(valid_departments)} departments")
            print(f"   💰 Total amount: ${total_amount:,.2f}")
            
            return final_result
            
        except Exception as e:
            print(f"❌ Error compiling final results: {e}")
            return {}

def main():
    """Main function to process text files."""
    
    # Load environment variables
    load_dotenv()
    
    # Get API key
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("❌ GOOGLE_API_KEY not found in environment variables")
        print("💡 Add it to your .env file: GOOGLE_API_KEY=your_api_key_here")
        return
    
    # Set up directories
    input_dir = "output"
    output_dir = "cleaned_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize cleaner
    cleaner = GeminiTextCleaner(api_key)
    
    # Process files
    import sys
    if len(sys.argv) > 1:
        # Process specific file
        input_file = sys.argv[1]
        if not os.path.exists(input_file):
            print(f"❌ File not found: {input_file}")
            return
        
        cleaner.process_file(input_file, output_dir)
    else:
        # Process all .txt files in output directory
        txt_files = [f for f in os.listdir(input_dir) if f.endswith('.txt')]
        
        if not txt_files:
            print(f"❌ No .txt files found in {input_dir}")
            return
        
        print(f"🔍 Found {len(txt_files)} text files to process")
        
        for txt_file in txt_files:
            input_path = os.path.join(input_dir, txt_file)
            cleaner.process_file(input_path, output_dir)

if __name__ == "__main__":
    print("🧹 Gemini Text Cleaner - Budget Document Processor")
    print("=" * 60)
    main() 