import json
import os
from typing import Dict, List, Any, Optional

def load_gemini_processed_files(processed_dir: str = "../improve_rag/documents/model_ouputs/processed_documents/") -> Dict[str, Dict[str, Any]]:
    """
    Load all the gemini-processed HB300 files.
    
    Args:
        processed_dir: Directory containing the processed gemini files
        
    Returns:
        Dictionary mapping document names to their processed data
    """
    gemini_files = {
        "HB300-HD1-(Exec).pdf": "processed_HB300_HD1_geminiV4.json",
        "HB300-SD1-(EXEC).pdf": "processed_HB300_SD1_geminiV4.json", 
        "HB300_CD1_WORKSHEETS_FINAL.pdf": "processed_HB300_CD1_geminiV4.json",
        "HB300 SD-HD_AGREE_FINAL.pdf": "processed_HB300_geminiV4.json",  # Base version
        "HB300 SD-HD_DISAGREE_FINAL.pdf": "processed_HB300_geminiV4.json",  # Base version
        "HB300 SD-HD DISAGREE_MARKED-UP_FINAL.pdf": "processed_HB300_geminiV4.json"  # Base version
    }
    
    loaded_data = {}
    
    for pdf_name, json_file in gemini_files.items():
        json_path = os.path.join(processed_dir, json_file)
        
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    loaded_data[pdf_name] = data
                    print(f"✓ Loaded {json_file} for {pdf_name}")
                    print(f"  - Budget items: {len(data.get('budget_items', []))}")
                    print(f"  - Text items: {len(data.get('text_items', []))}")
            except Exception as e:
                print(f"❌ Error loading {json_file}: {e}")
        else:
            print(f"⚠️  File not found: {json_path}")
    
    return loaded_data

def replace_budget_items_with_gemini(all_pdfs_data: Dict[str, List[Dict[str, Any]]], 
                                   gemini_data: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Replace budget items in all_pdfs_data with gemini-processed versions.
    
    Args:
        all_pdfs_data: Data from all_pdfs_extracted.json
        gemini_data: Loaded gemini-processed data
        
    Returns:
        Modified all_pdfs_data with budget items replaced
    """
    modified_data = {}
    
    for pdf_name, pages in all_pdfs_data.items():
        print(f"\n📄 Processing: {pdf_name}")
        
        if pdf_name in gemini_data:
            print(f"  🔄 Replacing with gemini-processed data...")
            
            # Get the gemini processed data for this PDF
            gemini_pdf_data = gemini_data[pdf_name]
            budget_items = gemini_pdf_data.get('budget_items', [])
            text_items = gemini_pdf_data.get('text_items', [])
            
            # Create a mapping of page numbers to budget items
            budget_items_by_page = {}
            for item in budget_items:
                page_num = item.get('page_number', 0)
                if page_num not in budget_items_by_page:
                    budget_items_by_page[page_num] = []
                budget_items_by_page[page_num].append(item)
            
            # Create a mapping of page numbers to text items
            text_items_by_page = {}
            for item in text_items:
                page_num = item.get('page_number', 0)
                if page_num not in text_items_by_page:
                    text_items_by_page[page_num] = []
                text_items_by_page[page_num].append(item)
            
            # Process each page
            modified_pages = []
            for page in pages:
                page_num = page.get('page_number', 0)
                
                # Start with the original page data
                modified_page = page.copy()
                
                # Add budget items if they exist for this page
                if page_num in budget_items_by_page:
                    modified_page['budget_items'] = budget_items_by_page[page_num]
                    print(f"    Page {page_num}: Added {len(budget_items_by_page[page_num])} budget items")
                else:
                    modified_page['budget_items'] = []
                
                # Add text items if they exist for this page
                if page_num in text_items_by_page:
                    modified_page['text_items'] = text_items_by_page[page_num]
                    print(f"    Page {page_num}: Added {len(text_items_by_page[page_num])} text items")
                else:
                    modified_page['text_items'] = []
                
                modified_pages.append(modified_page)
            
            modified_data[pdf_name] = modified_pages
            
            # Summary
            total_budget_items = sum(len(page.get('budget_items', [])) for page in modified_pages)
            total_text_items = sum(len(page.get('text_items', [])) for page in modified_pages)
            print(f"  ✓ Total budget items added: {total_budget_items}")
            print(f"  ✓ Total text items added: {total_text_items}")
            
        else:
            print(f"  ⚠️  No gemini data found, keeping original")
            # Keep original pages but add empty budget_items and text_items arrays
            modified_pages = []
            for page in pages:
                modified_page = page.copy()
                modified_page['budget_items'] = []
                modified_page['text_items'] = []
                modified_pages.append(modified_page)
            modified_data[pdf_name] = modified_pages
    
    return modified_data

def save_modified_data(modified_data: Dict[str, List[Dict[str, Any]]], 
                      output_path: str = "all_pdfs_with_budget_items.json"):
    """
    Save the modified data to a JSON file.
    
    Args:
        modified_data: The modified data with budget items
        output_path: Path to save the output file
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(modified_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Modified data saved to: {output_path}")
        
        # Print summary statistics
        total_pdfs = len(modified_data)
        total_pages = sum(len(pages) for pages in modified_data.values())
        total_budget_items = sum(
            sum(len(page.get('budget_items', [])) for page in pages)
            for pages in modified_data.values()
        )
        total_text_items = sum(
            sum(len(page.get('text_items', [])) for page in pages)
            for pages in modified_data.values()
        )
        
        print(f"\n📊 MODIFIED DATA SUMMARY:")
        print(f"  Total PDFs: {total_pdfs}")
        print(f"  Total pages: {total_pages}")
        print(f"  Total budget items: {total_budget_items}")
        print(f"  Total text items: {total_text_items}")
        
        # Show per-PDF breakdown for HB300 files
        print(f"\n📋 HB300 FILES BREAKDOWN:")
        for pdf_name, pages in modified_data.items():
            if "HB300" in pdf_name:
                budget_items = sum(len(page.get('budget_items', [])) for page in pages)
                text_items = sum(len(page.get('text_items', [])) for page in pages)
                if budget_items > 0 or text_items > 0:
                    print(f"  {pdf_name}:")
                    print(f"    Budget items: {budget_items}")
                    print(f"    Text items: {text_items}")
        
    except Exception as e:
        print(f"❌ Error saving modified data: {e}")

def process_all_pdfs_with_budget_items(all_pdfs_path: str = "all_pdfs_extracted.json",
                                     processed_dir: str = "../improve_rag/documents/model_ouputs/processed_documents/",
                                     output_path: str = "all_pdfs_with_budget_items.json"):
    """
    Main function to process all PDFs and replace budget items with gemini versions.
    
    Args:
        all_pdfs_path: Path to the all_pdfs_extracted.json file
        processed_dir: Directory containing gemini-processed files
        output_path: Path to save the output
    """
    print("🚀 PDF Budget Item Replacement Tool")
    print("=" * 60)
    
    # Load the all_pdfs_extracted.json file
    print(f"📁 Loading: {all_pdfs_path}")
    try:
        with open(all_pdfs_path, 'r', encoding='utf-8') as f:
            all_pdfs_data = json.load(f)
        print(f"✓ Loaded {len(all_pdfs_data)} PDF files")
    except Exception as e:
        print(f"❌ Error loading {all_pdfs_path}: {e}")
        return
    
    # Load gemini-processed files
    print(f"\n📁 Loading gemini-processed files from: {processed_dir}")
    gemini_data = load_gemini_processed_files(processed_dir)
    
    if not gemini_data:
        print("❌ No gemini-processed files loaded")
        return
    
    # Replace budget items
    print(f"\n🔄 Replacing budget items...")
    modified_data = replace_budget_items_with_gemini(all_pdfs_data, gemini_data)
    
    # Save the result
    save_modified_data(modified_data, output_path)
    
    print(f"\n🎉 Processing completed successfully!")

def main():
    """Main function to run the replacement process."""
    import sys
    
    # Get paths from command line arguments or use defaults
    all_pdfs_path = sys.argv[1] if len(sys.argv) > 1 else "all_pdfs_extracted.json"
    processed_dir = sys.argv[2] if len(sys.argv) > 2 else "../improve_rag/documents/model_ouputs/processed_documents/"
    output_path = sys.argv[3] if len(sys.argv) > 3 else "all_pdfs_with_budget_items.json"
    
    process_all_pdfs_with_budget_items(all_pdfs_path, processed_dir, output_path)

if __name__ == "__main__":
    main() 