import os
import time
import shutil
import zipfile
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any
import google.generativeai as genai
from settings import settings
from documents.step1_text_extraction.pdf_text_extractor import PDFTextExtractor

# Setup Paths
# Assuming this file is in src/refbot/
DATA_DIR = Path("refbot_data")
CONTEXT_DIR = Path(__file__).parent / "context"
RESULTS_DIR = Path(__file__).parent / "results"

# Configure GenAI
if settings.google_api_key:
    genai.configure(api_key=settings.google_api_key)

def load_context_content(filename: str) -> str:
    path = CONTEXT_DIR / filename
    if not path.exists():
        logging.warning(f"Context file not found: {path}")
        return ""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def clean_json_response(text: str) -> str:
    """Removes markdown formatting from JSON response."""
    cleaned = re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", text, flags=re.DOTALL)
    return cleaned.strip()

def process_refbot_upload_task(name: str, zip_file_path_str: str, target_dir_str: str):
    """
    Background task to process the uploaded RefBot data.
    """
    start_time = time.time()
    zip_file_path = Path(zip_file_path_str)
    target_dir = Path(target_dir_str)

    try:
        # 5. Unzip the file
        extract_dir = target_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            
        # 6. Find all PDF files
        pdf_files = []
        for root, dirs, files in os.walk(extract_dir):
            for filename in files:
                if filename.lower().endswith('.pdf') and not filename.startswith('._'):
                    pdf_files.append(Path(root) / filename)
                    
        if not pdf_files:
            return {
                "status": "warning",
                "message": "Zip uploaded and extracted, but no PDF files found.",
                "directory": str(target_dir)
            }

        # 7. Load Context Dataa
        try:
            committees_data = load_context_content("extracted_committees.json")
            fsr_content = load_context_content("FinanceSpecialResponsibility.txt")
            gr_content = load_context_content("GeneralResponsibility.txt")
            hre_content = load_context_content("HouseRules_extracted.txt")
            lsr_content = load_context_content("LegislativeSpecialResponsibility.txt")
            examples_3_shot = load_context_content("examples_3_shot.json")
        except Exception as e:
            logging.error(f"Error loading context files: {e}")
            raise Exception(f"Error loading context files: {str(e)}")

        # 8. Process each PDF
        results = []
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        for pdf_path in pdf_files:
            try:
                # Extract text
                extractor = PDFTextExtractor(
                    pdf_path=str(pdf_path),
                    contains_tables=False,
                    contains_images_of_text=False, 
                    contains_images_of_nontext=False
                )
                extraction_results = extractor.extract_all_pages()
                
                full_text = ""
                for page in extraction_results:
                    text = page.get("pymupdf_extraction_text", "")
                    if not text.strip():
                        text = page.get("pdfplumber_extraction_text", "")
                    full_text += text + "\n"
                
                chosen_bill_text = full_text.strip()

                # Fallback to OCR if no text was found
                if not chosen_bill_text:
                    logging.info(f"No text found in {pdf_path.name}, attempting OCR...")
                    try:
                        extractor = PDFTextExtractor(
                            pdf_path=str(pdf_path),
                            contains_tables=False,
                            contains_images_of_text=True, 
                            contains_images_of_nontext=False
                        )
                        extraction_results = extractor.extract_all_pages()
                        
                        full_text = ""
                        for page in extraction_results:
                            text = page.get("ocr_extraction_text", "")
                            if not text.strip():
                                text = page.get("pymupdf_extraction_text", "")
                            if not text.strip():
                                text = page.get("pdfplumber_extraction_text", "")
                            full_text += text + "\n"
                        chosen_bill_text = full_text.strip()

                        # Save OCR text for inspection
                        if chosen_bill_text:
                            debug_dir = target_dir / "debug_ocr"
                            debug_dir.mkdir(exist_ok=True)
                            debug_file = debug_dir / f"{pdf_path.name}.txt"
                            with open(debug_file, "w", encoding="utf-8") as df:
                                df.write(chosen_bill_text)
                                
                    except Exception as ocr_e:
                        logging.error(f"OCR attempt failed for {pdf_path.name}: {ocr_e}")

                if not chosen_bill_text:
                    logging.warning(f"No text extracted from {pdf_path.name} even after OCR attempt.")
                    results.append({
                        "bill_name": pdf_path.name,
                        "error": "No text content found (possibly scanned PDF and OCR failed)",
                        "committees": []
                    })
                    continue

                # Construct Prompt
                prompt = f"""
You are given a definition log of all potential committees and their descriptions
{committees_data}

While making your decision use the following 4 files as rules to base your decisions on which bills should get which committees.

{fsr_content}
{gr_content}
{hre_content}
{lsr_content}

Follow these rules strictly for all future decisions.

using the bill name and introduction assign it committees

{chosen_bill_text}

The following is an example of the correct results, it has the bill name, introduction, and the correct committees. This should be used as an example for when you are assigning committees to bills. 

{examples_3_shot}
   
Please give me a json where each entry has the bill name and your decision of which committees should be applied to that bill.

A single bill is allowed to have between 1 to 4 committees, it is not limited to or restricted to having more or less,
only apply those that make sense using the rules.

Also note that a bill discussing a constitutional amendment should be assigned to both the JHA and FIN committees, along with any other committees that make sense.

Please use this as the layout for the produced output (use the prompt style given here):
[  
      {{
          "prompt_style" : "This is the combination of one bill and three shot",
         "bill_name": "Name of bill ",
         "committees": ["committee_id 1", "committee_id 2", "committee_id 3", "committee_id 4"],
          "reasoning": "only when prompted add in text here other wise leave blank"
       }},
       {{
           "prompt_style" : "This is the combination of one bill and three shot",
           "bill_name": "Name of bill ",
           "committees": ["committee_id 1", "committee_id 2", "committee_id 3", "committee_id 4"],
           "reasoning": ""
       }}
    ]
"""
                # Call Gemini with retry logic
                max_retries = 5
                retry_delay = 10
                
                for attempt in range(max_retries):
                    try:
                        response = model.generate_content(prompt)
                        response_text = response.text
                        break
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str:
                            logging.warning(f"Rate limit hit for {pdf_path.name}. Attempt {attempt + 1}/{max_retries}. Error: {error_str[:100]}...")
                            
                            # Try to extract wait time from error message
                            import re
                            wait_match = re.search(r"retry in (\d+(\.\d+)?)s", error_str)
                            if wait_match:
                                wait_time = float(wait_match.group(1)) + 1  # Add 1s buffer
                                logging.info(f"Waiting {wait_time:.2f}s as requested by API...")
                                time.sleep(wait_time)
                            else:
                                # Exponential backoff
                                sleep_time = retry_delay * (2 ** attempt)
                                logging.info(f"Waiting {sleep_time}s before retry...")
                                time.sleep(sleep_time)
                        else:
                            raise e
                else:
                    raise Exception(f"Failed to process {pdf_path.name} after {max_retries} attempts due to rate limiting.")

                # Parse JSON
                cleaned_json = clean_json_response(response_text)
                bill_data = json.loads(cleaned_json)

                # Add bill name to the parsed object(s)
                if isinstance(bill_data, list):
                    for item in bill_data:
                        item['bill_name'] = pdf_path.name
                elif isinstance(bill_data, dict):
                    bill_data['bill_name'] = pdf_path.name
                
                # If it returns a list, extend our results, otherwise append
                if isinstance(bill_data, list):
                    results.extend(bill_data)
                else:
                    results.append(bill_data)
                    
                # Add a small delay between successful requests to be nice to the API
                time.sleep(1)
                    
            except Exception as e:
                logging.error(f"Error processing PDF {pdf_path.name}: {e}")
                results.append({
                    "bill_name": pdf_path.name,
                    "error": str(e)
                })
            
            # Save incremental results after each bill
            try:
                RESULTS_DIR.mkdir(exist_ok=True)
                results_file = RESULTS_DIR / f"{name}.json"
                with open(results_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
            except Exception as save_e:
                logging.error(f"Failed to save incremental results: {save_e}")

        # Final save (redundant but safe)
        RESULTS_DIR.mkdir(exist_ok=True)
        results_file = RESULTS_DIR / f"{name}.json"
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        execution_time = time.time() - start_time
        return {
            "status": "success",
            "message": f"Processed {len(pdf_files)} files.",
            "directory": str(target_dir),
            "execution_time_seconds": execution_time,
            "results": results
        }

    except Exception as e:
        print(f"❌ Error during refbot processing task: {str(e)}")
        # Raise so RQ marks it as failed
        raise e
