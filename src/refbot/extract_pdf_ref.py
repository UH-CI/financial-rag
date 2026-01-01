
import fitz
import sys

def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

if __name__ == "__main__":
    # Use absolute path to ensure the file is found regardless of where the script is run from
    pdf_path = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/refbot/results_tmp/RefKey.pdf"
    try:
        content = extract_text(pdf_path)
        print(content)
    except Exception as e:
        print(f"Error extracting text: {e}")
