#!/usr/bin/env python3

import json
import os
import sys

# Add the path to import step5_fiscal_note_gen
sys.path.append('/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation')

def debug_step5_filtering():
    """Debug the filtering logic in step5_fiscal_note_gen.py"""
    
    print('🔍 DEBUGGING STEP5 FILTERING LOGIC')
    print('=' * 50)
    
    # Simulate the exact scenario from step5
    bill_name = "HB_1483_2025"
    base_dir = f"/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation/{bill_name}"
    numbers_file_path = f"{base_dir}/{bill_name}_numbers.json"
    
    # Load all numbers data
    with open(numbers_file_path, "r") as f:
        all_numbers = json.load(f)
    
    print(f'📊 Total numbers available: {len(all_numbers)}')
    
    # Simulate first fiscal note scenario
    new_document_names = ["HB1483"]  # Only the first document
    
    print(f'📄 NEW documents for first fiscal note: {new_document_names}')
    
    # Apply the filtering logic from step5_fiscal_note_gen.py
    numbers_data = []
    for number_item in all_numbers:
        # Check if this number's document is in the NEW documents
        number_doc_name = number_item['filename']
        # Remove .txt extension for comparison
        if number_doc_name.endswith('.txt'):
            number_doc_base = number_doc_name[:-4]
        else:
            number_doc_base = number_doc_name
        
        # Match against NEW document names only
        for new_doc_name in new_document_names:
            matched = False
            
            # Exact matches
            if (number_doc_name == new_doc_name or 
                number_doc_base == new_doc_name or
                number_doc_name == new_doc_name + '.txt' or
                number_doc_base == new_doc_name + '_.HTM'):
                matched = True
                match_reason = "Exact match"
            
            # Prefix matches - but be more careful for base documents
            elif (number_doc_name.startswith(new_doc_name + '_') or
                  number_doc_base.startswith(new_doc_name + '_')):
                # For base documents like "HB1483", only match if the next character after _ 
                # indicates it's the same document version (like HB1483_.HTM.txt)
                # NOT later versions (like HB1483_CD1_.HTM.txt)
                
                # Extract what comes after the base name + underscore
                if number_doc_name.startswith(new_doc_name + '_'):
                    suffix = number_doc_name[len(new_doc_name + '_'):]
                else:
                    suffix = number_doc_base[len(new_doc_name + '_'):]
                
                # Only match if suffix is just file extension (HTM.txt) or empty
                # Don't match if suffix contains version indicators (CD1, HD1, SD1, TESTIMONY, etc.)
                version_indicators = ['CD1', 'CD2', 'CD3', 'HD1', 'HD2', 'HD3', 'SD1', 'SD2', 'SD3', 'TESTIMONY', 'HSCR', 'SSCR', 'CCR']
                if not any(indicator in suffix for indicator in version_indicators):
                    matched = True
                    match_reason = f"Prefix match (suffix: '{suffix}')"
            
            if matched:
                numbers_data.append(number_item)
                print(f"✅ Matched: {number_doc_name} -> {new_doc_name} ({match_reason})")
                break
    
    print(f'\n📊 FILTERING RESULTS:')
    print(f'   Numbers before filtering: {len(all_numbers)}')
    print(f'   Numbers after filtering: {len(numbers_data)}')
    
    # This should match what we expect
    expected_count = 11  # Only HB1483_.HTM.txt numbers
    if len(numbers_data) == expected_count:
        print(f'   ✅ SUCCESS: Got expected {expected_count} numbers')
    else:
        print(f'   ❌ ISSUE: Expected {expected_count} numbers, got {len(numbers_data)}')
    
    # Check what documents are included
    included_docs = {}
    for number_item in numbers_data:
        filename = number_item['filename']
        if filename not in included_docs:
            included_docs[filename] = 0
        included_docs[filename] += 1
    
    print(f'\n✅ INCLUDED documents:')
    for filename, count in included_docs.items():
        print(f'   {filename}: {count} numbers')
    
    # The key insight: if this filtering works correctly but step5 still uses 61 numbers,
    # then there's a bug in step5 where it's not actually using this filtering logic
    
    print(f'\n🔍 CONCLUSION:')
    if len(numbers_data) == 11 and 'HB1483_.HTM.txt' in included_docs:
        print(f'   ✅ Filtering logic is CORRECT')
        print(f'   ❌ But step5 regeneration still used 61 numbers')
        print(f'   🐛 This suggests step5 is NOT using the updated filtering code')
        print(f'   💡 Possible causes:')
        print(f'      - Code wasn\'t saved properly')
        print(f'      - Python import cache issue')
        print(f'      - Different code path being used')
    else:
        print(f'   ❌ Filtering logic has a bug')

if __name__ == "__main__":
    debug_step5_filtering()
