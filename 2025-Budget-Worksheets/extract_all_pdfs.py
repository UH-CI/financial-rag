import os
import json
import glob
from typing import Dict, List, Any
import fitz  # PyMuPDF
import pdfplumber
from pathlib import Path

def extract_pdf_text(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extract text from a PDF using both pdfplumber and PyMuPDF.
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        List of dictionaries containing page data
    """
    pages = []
    
    try:
        # Get total pages using PyMuPDF
        with fitz.open(pdf_path) as doc:
            total_pages = len(doc)
        
        print(f"  Processing {total_pages} pages...")
        
        # Process each page
        for page_num in range(total_pages):
            page_data = {
                'page_number': page_num + 1,
                'pdfplumber_text': '',
                'pymupdf_text': ''
            }
            
            # Extract with pdfplumber
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    if page_num < len(pdf.pages):
                        page = pdf.pages[page_num]
                        text = page.extract_text() or ""
                        
                        # Also extract tables and convert to text
                        tables = page.extract_tables()
                        if tables:
                            table_text = "\n\n--- TABLES ---\n"
                            for i, table in enumerate(tables):
                                table_text += f"\nTable {i+1}:\n"
                                for row in table:
                                    if row:  # Skip empty rows
                                        table_text += " | ".join(str(cell) if cell else "" for cell in row) + "\n"
                            text += table_text
                        
                        page_data['pdfplumber_text'] = text.strip()
            except Exception as e:
                print(f"    pdfplumber error on page {page_num + 1}: {e}")
                page_data['pdfplumber_text'] = f"Error: {str(e)}"
            
            # Extract with PyMuPDF
            try:
                with fitz.open(pdf_path) as doc:
                    page = doc[page_num]
                    page_data['pymupdf_text'] = page.get_text().strip()
            except Exception as e:
                print(f"    PyMuPDF error on page {page_num + 1}: {e}")
                page_data['pymupdf_text'] = f"Error: {str(e)}"
            
            pages.append(page_data)
            
            # Progress indicator
            if (page_num + 1) % 10 == 0 or page_num + 1 == total_pages:
                print(f"    Processed {page_num + 1}/{total_pages} pages")
    
    except Exception as e:
        print(f"  Error processing PDF: {e}")
        return []
    
    return pages

def find_pdf_files(directory: str) -> List[str]:
    """
    Find all PDF files in the specified directory.
    
    Args:
        directory (str): Directory to search for PDF files
        
    Returns:
        List of PDF file paths
    """
    pdf_files = []
    
    # Find all PDF files
    for pdf_file in glob.glob(os.path.join(directory, "*.pdf")):
        pdf_files.append(pdf_file)
    
    # Sort for consistent ordering
    pdf_files.sort()
    
    return pdf_files

def process_all_pdfs(directory: str = ".") -> Dict[str, List[Dict[str, Any]]]:
    """
    Process all PDF files in the directory and extract text.
    
    Args:
        directory (str): Directory containing PDF files
        
    Returns:
        Dictionary with PDF names as keys and page data as values
    """
    pdf_files = find_pdf_files(directory)
    
    if not pdf_files:
        print("No PDF files found in the directory")
        return {}
    
    print(f"Found {len(pdf_files)} PDF files to process:")
    for pdf_file in pdf_files:
        print(f"  - {os.path.basename(pdf_file)}")
    
    results = {}
    
    for i, pdf_path in enumerate(pdf_files):
        pdf_name = os.path.basename(pdf_path)
        print(f"\n[{i+1}/{len(pdf_files)}] Processing: {pdf_name}")
        
        # Extract text from the PDF
        pages = extract_pdf_text(pdf_path)
        
        if pages:
            results[pdf_name] = pages
            print(f"  ✓ Successfully processed {len(pages)} pages")
        else:
            print(f"  ❌ Failed to process {pdf_name}")
    
    return results

def save_results(results: Dict[str, List[Dict[str, Any]]], output_path: str = "all_pdfs_extracted.json"):
    """
    Save the extraction results to a JSON file.
    
    Args:
        results: Dictionary containing all PDF extraction results
        output_path: Path to save the JSON file
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Results saved to: {output_path}")
        
        # Print summary statistics
        total_pdfs = len(results)
        total_pages = sum(len(pages) for pages in results.values())
        total_pdfplumber_chars = sum(
            sum(len(page.get('pdfplumber_text', '')) for page in pages)
            for pages in results.values()
        )
        total_pymupdf_chars = sum(
            sum(len(page.get('pymupdf_text', '')) for page in pages)
            for pages in results.values()
        )
        
        print(f"\n📊 EXTRACTION SUMMARY:")
        print(f"  Total PDFs processed: {total_pdfs}")
        print(f"  Total pages extracted: {total_pages}")
        print(f"  Total pdfplumber characters: {total_pdfplumber_chars:,}")
        print(f"  Total PyMuPDF characters: {total_pymupdf_chars:,}")
        
        # Show per-PDF breakdown
        print(f"\n📋 PER-PDF BREAKDOWN:")
        for pdf_name, pages in results.items():
            pdfplumber_chars = sum(len(page.get('pdfplumber_text', '')) for page in pages)
            pymupdf_chars = sum(len(page.get('pymupdf_text', '')) for page in pages)
            print(f"  {pdf_name}:")
            print(f"    Pages: {len(pages)}")
            print(f"    pdfplumber chars: {pdfplumber_chars:,}")
            print(f"    PyMuPDF chars: {pymupdf_chars:,}")
        
    except Exception as e:
        print(f"❌ Error saving results: {e}")

def main():
    """Main function to process all PDFs and save results."""
    import sys
    
    # Get directory from command line argument or use current directory
    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    output_file = sys.argv[2] if len(sys.argv) > 2 else "all_pdfs_extracted.json"
    
    print("🚀 PDF Extraction Tool")
    print("=" * 50)
    print(f"📁 Directory: {os.path.abspath(directory)}")
    print(f"💾 Output file: {output_file}")
    print("=" * 50)
    
    # Process all PDFs
    results = process_all_pdfs(directory)
    
    if results:
        # Save results
        save_results(results, output_file)
        print(f"\n🎉 Processing completed successfully!")
    else:
        print(f"\n❌ No PDFs were successfully processed")

if __name__ == "__main__":
    main() 