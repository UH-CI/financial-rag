#!/usr/bin/env python3
"""
Test script to verify document mapping and reference replacement functionality.
"""

import re

def process_fiscal_note_references(fiscal_note_data, document_mapping):
    """
    Process fiscal note data to replace filename references with numbered references.
    """
    
    def replace_filename_with_number(text):
        if not isinstance(text, str):
            return text
        
        # Pattern to match any content in parentheses that looks like a document reference
        pattern = r'\(([^)]+)\)'
        
        def replacement(match):
            content = match.group(1)
            
            # Look for the content in the document mapping (exact match first)
            for doc_name, doc_number in document_mapping.items():
                if doc_name == content:
                    return f'<span class="doc-reference" data-tooltip="{content}" title="{content}">[{doc_number}]</span>'
            
            # Try partial matches - check if content contains any document name
            for doc_name, doc_number in document_mapping.items():
                if doc_name in content or content in doc_name:
                    return f'<span class="doc-reference" data-tooltip="{content}" title="{content}">[{doc_number}]</span>'
            
            # If not found, return original
            return match.group(0)
        
        return re.sub(pattern, replacement, text)
    
    # Process all string values in the fiscal note data
    processed_data = {}
    for key, value in fiscal_note_data.items():
        if isinstance(value, str):
            processed_data[key] = replace_filename_with_number(value)
        elif isinstance(value, dict):
            processed_data[key] = process_fiscal_note_references(value, document_mapping)
        elif isinstance(value, list):
            processed_data[key] = [
                process_fiscal_note_references(item, document_mapping) if isinstance(item, dict)
                else replace_filename_with_number(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            processed_data[key] = value
    
    return processed_data

def test_document_mapping():
    """Test the document mapping and reference replacement"""
    
    print("🧪 Testing Document Mapping & Reference Replacement")
    print("=" * 60)
    
    # Sample document mapping based on the actual output you showed
    document_mapping = {
        "HB441": 1,
        "HB441_SD2_": 2,
        "HB441_HD1_": 3,
        "HB441_HSCR53_": 4,
        "HB441_SSCR45_": 5
    }
    
    # Sample fiscal note data matching your actual output
    sample_fiscal_note = {
        "overview": "This bill proposes to increase the excise tax on cigarettes and little cigars from 16 cents (HB441) to 18 cents (HB441) per item, effective January 1, 2026.",
        "appropriations": "This bill does not make a direct appropriation of a specific dollar amount. Instead, it amends the disposition of tax revenues by increasing the allocation to the Hawaii Cancer Research Special Fund. Effective January 1, 2026, the allocation to the fund will increase from 2.0 cents (HB441) per cigarette to 4.0 cents (HB441) per cigarette, with the additional revenue designated for debt service and building maintenance until June 30, 2041 (HB441)."
    }
    
    print("📋 Original fiscal note:")
    for key, value in sample_fiscal_note.items():
        print(f"  {key}: {value[:100]}...")
    
    print(f"\n🗂️  Document mapping:")
    for doc_name, doc_number in document_mapping.items():
        print(f"  [{doc_number}] {doc_name}")
    
    # Process the fiscal note
    processed_note = process_fiscal_note_references(sample_fiscal_note, document_mapping)
    
    print(f"\n✨ Processed fiscal note:")
    for key, value in processed_note.items():
        print(f"  {key}: {value}")
    
    print(f"\n🎯 Expected behavior:")
    print("  - Filenames in parentheses should be replaced with numbered references")
    print("  - References should have tooltip data and styling classes")
    print("  - Numbers should be clickable with hover tooltips")
    
    return processed_note

def test_reference_patterns():
    """Test different filename patterns"""
    
    print(f"\n🧪 Testing Reference Patterns")
    print("=" * 40)
    
    document_mapping = {"TEST_DOC": 1, "ANOTHER_FILE": 2}
    
    test_cases = [
        "Amount is $50,000 (TEST_DOC.txt) for training",
        "Budget shows $25,000 (ANOTHER_FILE.PDF.txt) allocation", 
        "The bill specifies $100,000 (TEST_DOC.HTM.txt) for operations",
        "No reference here should remain unchanged"
    ]
    
    for test_case in test_cases:
        result = process_fiscal_note_references({"test": test_case}, document_mapping)
        print(f"  Input:  {test_case}")
        print(f"  Output: {result['test']}")
        print()

if __name__ == "__main__":
    processed = test_document_mapping()
    test_reference_patterns()
    
    print("🎉 Document mapping test completed!")
    print("💡 References should now show as numbered links with tooltips")
