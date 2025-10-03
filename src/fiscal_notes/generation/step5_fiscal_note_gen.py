import json
import os
import glob
from pydantic import BaseModel, create_model
from tenacity import retry, stop_after_attempt, wait_exponential
import time
from google import genai

from dotenv import load_dotenv
load_dotenv()

class FiscalNoteModel(BaseModel):
    overview: str
    appropriations:str
    assumptions_and_methodology:str
    agency_impact:str
    economic_impact:str 
    policy_impact: str
    revenue_sources: str 
    six_year_fiscal_implications: str
    operating_revenue_impact: str
    capital_expenditure_impact: str
    fiscal_implications_after_6_years: str
    updates_from_previous_fiscal_note: str


# Example LLM query function (replace with your actual model)
def query_gemini(prompt: str):
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": FiscalNoteModel}
    )
    return response.text, response.parsed

# Property prompts (from your input)
PROPERTY_PROMPTS = { 
    "overview": { "prompt": "Using the provided legislative documents, statutes, and testimonies, write a clear summary describing the purpose, scope, and key components of the proposed measure or bill, including any pilot or permanent programs, reporting requirements, and sunset clauses. This should be around 3 sentences.", "description": "General overview and summary of the measure" }, 
    "appropriations": { "prompt": "Based on budgetary data and legislative appropriations, detail the funding allocated for the program or measure, including fiscal years, amounts, intended uses such as staffing, training, contracts, technology, etc... This should be around 3 sentences.", "description": "Funding allocation and appropriations details" }, 
    "assumptions_and_methodology": { "prompt": "Explain the assumptions, cost estimation methods, and data sources used to calculate the financial projections for this program or measure, referencing comparable programs or historical budgets where applicable. This should be around 3 sentences.", "description": "Cost estimation methodology and assumptions" }, 
    "agency_impact": { "prompt": "Describe the anticipated operational, administrative, and budgetary impact of the program or measure on the relevant government agency or department, including supervision, staffing, and resource allocation. This should be around 3 sentences.", "description": "Impact on government agencies and departments" }, 
    "economic_impact": { "prompt": "Summarize the expected economic effects of the program or measure, such as cost savings, potential reductions in related expenditures, benefits to the community, and any relevant performance or participation statistics. This should be around 3 sentences.", "description": "Economic effects and community benefits" }, 
    "policy_impact": { "prompt": "Analyze the policy implications of the measure, including how it modifies existing laws or programs, its role within broader legislative strategies, and its potential effects on state or local governance. This should be around 3 sentences.", "description": "Policy implications and legislative analysis" }, 
    "revenue_sources": { "prompt": "Identify and describe the funding sources that will support the program or measure, such as general funds, grants, fees, or other revenue streams, based on the provided fiscal documents. This should be around 3 sentences.", "description": "Funding sources and revenue streams" }, 
    "six_year_fiscal_implications": { "prompt": "Provide a multi-year fiscal outlook (e.g., six years) for the program or measure, projecting costs, staffing changes, recurring expenses, and assumptions about program expansion or permanence using available budget and workload data. This should be around 10 sentences.", "description": "Six-year fiscal projections and outlook" }, 
    "operating_revenue_impact": { "prompt": "Describe any anticipated impacts on operating revenues resulting from the program or measure, including increases, decreases, or changes in revenue streams. This should be around 3 sentences.", "description": "Operating revenue impacts" }, 
    "capital_expenditure_impact": { "prompt": "Outline any expected capital expenditures related to the program or measure, such as investments in facilities, equipment, or technology infrastructure, based on capital budgets or agency plans. This should be around 3 sentences.", "description": "Capital expenditure requirements" }, 
    "fiscal_implications_after_6_years": { "prompt": "Summarize the ongoing fiscal obligations after the initial multi-year period for the program or measure, including annual operating costs, expected number of program sites or units, and the sustainability of funding. This should be around 3 sentences.", "description": "Long-term fiscal obligations beyond six years" },
    "updates_from_previous_fiscal_note" : {"prompt": "If you are given a previous fisacl not. Please summarize the MAIN POINTS that are different from the previous fiscal note and the new fisacl note."}
    }

def generate_fiscal_note_for_context(context_text, numbers_data=None, previous_note=None):
    """
    Generate a full fiscal note (all properties at once) using PROPERTY_PROMPTS.
    If previous_note is provided, instruct the LLM to avoid repeating information.
    """
    # Build a combined instruction
    combined_prompt = "You are tasked with generating a fiscal note based on the context that you are given on a set of documents.\n"
    combined_prompt += "Extract the following information:\n\n"
    for key, prop in PROPERTY_PROMPTS.items():
        combined_prompt += f"- {key}: {prop['prompt']}\n"

    # Add specific instructions about using numbers
    combined_prompt += "\n**CRITICAL INSTRUCTIONS FOR FINANCIAL NUMBERS:**\n"
    combined_prompt += "1. EVERY financial number MUST be immediately followed by its source in parentheses\n"
    combined_prompt += "2. Use document-type-specific language when citing numbers:\n"
    combined_prompt += "   - For 'introduction' documents: 'The introduction allocates $X (filename)' or 'The bill appropriates $X (filename)'\n"
    combined_prompt += "   - For 'testimony' documents: 'The testimony requests $X (filename)' or 'Testimony indicates $X (filename)'\n"
    combined_prompt += "   - For 'committee_hearing' documents: 'The committee hearing determines $X (filename)' or 'It is decided in the committee hearing that $X (filename)'\n"
    combined_prompt += "   - For 'document' documents: 'The legislative document specifies $X (filename)'\n"
    combined_prompt += "3. Do NOT put citations at the end of sentences - put them immediately after each number\n"
    combined_prompt += "4. Do NOT make up or estimate numbers - only use numbers from the provided financial data\n"
    combined_prompt += "5. Be VERY SPECIFIC about what each dollar amount is for\n"
    combined_prompt += "6. Example: 'The introduction allocates $50,000 (HB123.HTM.txt) for staff training and testimony requests $25,000 (HB123_TESTIMONY_EDU.PDF.txt) for equipment.'\n\n"

    # Add numbers data if available
    if numbers_data:
        combined_prompt += "**FINANCIAL NUMBERS FOUND IN DOCUMENTS:**\n"
        for number_item in numbers_data:
            doc_type_desc = {
                'introduction': 'Bill introduction',
                'committee_hearing': 'Committee hearing',
                'testimony': 'Public testimony',
                'document': 'Legislative document'
            }.get(number_item.get('document_type', 'document'), 'Document')
            
            combined_prompt += f"- ${number_item['number']:,.2f} from {doc_type_desc} ({number_item['filename']})\n"
            combined_prompt += f"  Context: {number_item['text'][:200]}...\n\n"

    combined_prompt += f"\nContext:\n{context_text}\n"

    if previous_note:
        combined_prompt += (
            f"""
            You are generating a **new fiscal note** based on updated documents. 
Compare it to the previous fiscal note (shown below). Only include information that is **new or has changed**. 
If a section has no changes, leave it **blank**. 
Do **not repeat content** from the previous fiscal note.
Ensure that you use numbers according to the numbers.json file. Do not make up numbers.
Previous fiscal note:
            """
            f"{json.dumps(previous_note, ensure_ascii=False, indent=2)}"
            f"\nAccording to the previous fiscal note, focus on what has been discussed and the main points that have changed. Do not repeat the same content. The previous fiscal note should be very different in the new fiscal note. If no new information is needed, leave the section blank\n"
            
        )
    
    text, parsed = query_gemini(combined_prompt)

    # Convert to dict
    fiscal_note = {}
    if parsed:
        try:
            fiscal_note = parsed.dict()  # Pydantic v1
        except AttributeError:
            fiscal_note = parsed.model_dump()  # Pydantic v2

    return fiscal_note, combined_prompt

def generate_fiscal_notes_chronologically(documents, chronological_documents, output_dir, numbers_file_path):
    """
    Generate fiscal notes sequentially for a list of chronologically ordered documents.
    Each document adds to the cumulative context, but previous fiscal note is given to reduce redundancy.
    
    documents: list of dicts with {"name": ..., "text": ...} from retrieved documents
    chronological_documents: list of dicts with {"name": ..., "url": ...} from chronological JSON
    """
    os.makedirs(output_dir, exist_ok=True)
    cumulative_context = ""
    previous_fiscal_note = None
    processed_documents = []  # Track documents processed so far
    
    # Load all numbers data once
    all_numbers = []
    try:
        with open(numbers_file_path, "r") as f:
            all_numbers = json.load(f)
    except Exception as e:
        print(f"Warning: Could not load numbers data: {e}")
    
    # Create a mapping of document names to URLs for committee report detection
    doc_url_map = {doc['name']: doc['url'] for doc in chronological_documents}
    
    for i, doc in enumerate(documents, start=1):
        print(f"Processing document {i}/{len(documents)}: {doc['name']}, text: {doc['text'][:10]}")
        
        # Append the new document to the cumulative context
        cumulative_context += f"\n\n=== Document: {doc['name']} ===\n{doc['text']}"
        processed_documents.append(doc['name'])  # Track this document as processed
        
        # Check if this document should generate a fiscal note:
        # 1. If it's the first document (bill introduction)
        # 2. If the URL contains "CommReports" (committee reports)
        should_generate = False
        if i == 1:  # First document (bill introduction)
            should_generate = True
            print(f"📋 Generating fiscal note for bill introduction: {doc['name']}")
        elif doc['name'] in doc_url_map and "CommReports" in doc_url_map[doc['name']]:
            should_generate = True
            print(f"📋 Generating fiscal note for committee report: {doc['name']}")
        
        if should_generate:
            # Filter numbers data to only include documents processed so far
            numbers_data = []
            for number_item in all_numbers:
                # Check if this number's document has been processed
                number_doc_name = number_item['filename']
                # Match against processed document names (handle .txt extension)
                for processed_doc in processed_documents:
                    if (number_doc_name == processed_doc or 
                        number_doc_name == processed_doc + '.txt' or
                        number_doc_name + '.txt' == processed_doc):
                        numbers_data.append(number_item)
                        break
            
            print(f"📊 Using {len(numbers_data)} numbers from {len(processed_documents)} processed documents")
            
            # Generate fiscal note for the current cumulative context
            fiscal_note, combined_prompt = generate_fiscal_note_for_context(
                cumulative_context, 
                numbers_data=numbers_data, 
                previous_note=previous_fiscal_note
            )
            # Save to a JSON file (filename = new document name)
            out_path = os.path.join(output_dir, f"{doc['name']}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(fiscal_note, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Fiscal note saved: {out_path}")
            # Update previous fiscal note to avoid redundancy in the next iteration
            previous_fiscal_note = fiscal_note
            cumulative_context = ""


def generate_fiscal_notes(documents_dir: str, numbers_file_path: str) -> str:
    """
    Takes a documents directory path and generates fiscal notes in chronological order.
    Reads the chronological JSON and processes the retrieved documents.
    Returns the path to the fiscal notes output directory.
    """
    # Find the chronological JSON file in the parent directory
    base_dir = os.path.dirname(documents_dir)
    chronological_files = glob.glob(os.path.join(base_dir, "*_chronological.json"))
    
    if not chronological_files:
        raise FileNotFoundError(f"No chronological JSON file found in {base_dir}")
    
    chronological_json_path = chronological_files[0]
    
    # Load chronological documents
    with open(chronological_json_path, 'r', encoding='utf-8') as f:
        documents_chronological = json.load(f)
    
    # Create fiscal notes output directory
    fiscal_notes_dir = os.path.join(base_dir, "fiscal_notes")
    os.makedirs(fiscal_notes_dir, exist_ok=True)
    
    # Load documents with text content
    documents_with_text = []
    
    for doc in documents_chronological:
        name = doc['name']
        # Look for any file that starts with the document name in the documents directory
        matches = glob.glob(os.path.join(documents_dir, f"{name}*"))
        if matches:
            # Take the first match
            txt_path = matches[0]
            with open(txt_path, "r", encoding="utf-8") as f:
                text = f.read()
            documents_with_text.append({"name": name, "text": text})
        else:
            print(f"⚠️ File not found for {name}")
    
    # Generate fiscal notes in chronological order
    generate_fiscal_notes_chronologically(documents_with_text, documents_chronological, fiscal_notes_dir, numbers_file_path)
    
    print(f"✅ Fiscal notes generated and saved to: {fiscal_notes_dir}")
    return fiscal_notes_dir


__all__ = ["generate_fiscal_notes"]
