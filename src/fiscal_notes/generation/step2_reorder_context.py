import json
import os
import re
from pydantic import BaseModel
from google import genai
class Document(BaseModel):
    date: str
    text: str
    documents: list[str]


from dotenv import load_dotenv
load_dotenv()




# Updated Gemini query function
def query_gemini(prompt: str):
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": list[Document]}
    )
    return response.text, response.parsed

def generate_order_prompt_json(status_rows, document_names):
    """
    Generates a prompt asking Gemini 2.5 Pro to return a chronological JSON timeline of document creation.
    Each event should be an object with:
      - date: string (single date or date range)
      - text: string (description of the event)
      - documents: array of document names (can be empty)
    Include all documents. Place testimony documents under the relevant hearing event.
    """
    status_text = "\n".join(status_rows)
    documents_text = "\n".join(document_names)
    
    prompt = (
        "You are given legislative status updates of a bill and a list of document names.\n\n"
        "Some documents are testimonies related to hearings. Place testimony documents under the event where the hearing occurred.\n\n"
        "Status updates (chronological):\n"
        f"{status_text}\n\n"
        "Document names:\n"
        f"{documents_text}\n\n"
        "Return a chronological timeline as a JSON array of objects. Each object must have:\n"
        "{\n"
        '  "date": "event date or date range",\n'
        '  "text": "description of the event",\n'
        '  "documents": ["doc1", "doc2"]  # list of documents associated with this event, can be empty\n'
        "}\n\n"
        "Use all documents from the list. Do NOT include explanations, reasoning, or extra text. Just return valid JSON."
    )
    
    return prompt



def reorder_documents(json_file_path: str) -> str:
    """
    Takes a JSON file path containing bill documents and reorders them chronologically.
    Returns the path to the saved reordered documents file.
    """
    # Load the JSON data
    with open(json_file_path, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    # Extract documents and status information
    documents = [document['name'] for document in results[0]['documents']]
    status_rows = results[0]['text']
    
    # Generate the prompt
    query = generate_order_prompt_json(status_rows, documents)
    
    # Send prompt to Gemini
    text, parsed = query_gemini(query)
    timeline = parsed
    
    # Create document mapping
    doc_map = {doc['name']: doc for doc in results[0]['documents']}
    
    # Reorder documents chronologically
    documents_chronological = []
    seen = set()
    for event in timeline:
        for doc_name in event.documents:
            if doc_name in doc_map and doc_name not in seen:
                documents_chronological.append(doc_map[doc_name])
                seen.add(doc_name)
    
    # Create output filename in the same directory
    base_dir = os.path.dirname(json_file_path)
    base_name = os.path.splitext(os.path.basename(json_file_path))[0]
    output_file = os.path.join(base_dir, f"{base_name}_chronological.json")
    
    # Save reordered documents
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(documents_chronological, f, ensure_ascii=False, indent=2)
    
    return output_file


__all__ = ["reorder_documents"]

