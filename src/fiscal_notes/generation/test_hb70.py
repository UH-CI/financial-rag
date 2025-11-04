#!/usr/bin/env python3
"""
Test fiscal note generation for HB 70
"""
import os
import sys
from step1_get_context import fetch_documents
from step2_reorder_context import reorder_documents
from step3_retrieve_docs import retrieve_documents
from step4_get_numbers import extract_number_context
from step5_fiscal_note_gen import generate_fiscal_notes

def test_hb70_fiscal_note_generation():
    """Run the complete fiscal note generation pipeline for HB 70"""
    
    # HB 70 URL for 2025 session
    hb70_url = "https://www.capitol.hawaii.gov/session/measure_indiv.aspx?billtype=HB&billnumber=70&year=2025"
    
    print("🏛️  Testing Fiscal Note Generation for HB 70")
    print("=" * 50)
    
    # Step 1: Fetch documents
    print("\n📥 Step 1: Fetching documents from legislature website...")
    try:
        saved_path = fetch_documents(hb70_url)
        print(f"✅ Documents fetched successfully: {saved_path}")
    except Exception as e:
        print(f"❌ Error fetching documents: {e}")
        return False
    
    if not saved_path:
        print("❌ No documents path returned")
        return False
    
    # Step 2: Reorder documents chronologically
    print("\n📋 Step 2: Reordering documents chronologically...")
    try:
        chronological_path = reorder_documents(saved_path)
        print(f"✅ Documents reordered successfully: {chronological_path}")
    except Exception as e:
        print(f"❌ Error reordering documents: {e}")
        return False
    
    if not chronological_path:
        print("❌ No chronological path returned")
        return False
    
    # Step 3: Retrieve and process documents
    print("\n📄 Step 3: Retrieving and processing documents...")
    try:
        documents_path = retrieve_documents(chronological_path)
        print(f"✅ Documents retrieved successfully: {documents_path}")
    except Exception as e:
        print(f"❌ Error retrieving documents: {e}")
        return False
    
    if not documents_path:
        print("❌ No documents path returned")
        return False
    
    # Step 4: Extract number context
    print("\n🔢 Step 4: Extracting numerical context...")
    try:
        numbers_file = os.path.join(os.path.dirname(documents_path), "HB_70_2025_numbers.json")
        extract_number_context(documents_path, numbers_file)
        print(f"✅ Number context extracted: {numbers_file}")
    except Exception as e:
        print(f"❌ Error extracting numbers: {e}")
        return False
    
    # Step 5: Generate fiscal notes
    print("\n💰 Step 5: Generating fiscal notes...")
    try:
        fiscal_notes_path = generate_fiscal_notes(documents_path)
        print(f"✅ Fiscal notes generated successfully: {fiscal_notes_path}")
    except Exception as e:
        print(f"❌ Error generating fiscal notes: {e}")
        return False
    
    print("\n🎉 HB 70 Fiscal Note Generation Complete!")
    print(f"📁 Output directory: {os.path.dirname(documents_path)}")
    
    return True

if __name__ == "__main__":
    success = test_hb70_fiscal_note_generation()
    sys.exit(0 if success else 1)
