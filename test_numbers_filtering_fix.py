#!/usr/bin/env python3

import json

def test_numbers_filtering_fix():
    """Test the improved numbers filtering logic for the first fiscal note"""
    
    print('🧪 TESTING NUMBERS FILTERING FIX')
    print('=' * 50)
    
    # Load all numbers data
    numbers_file = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation/HB_1483_2025/HB_1483_2025_numbers.json"
    with open(numbers_file, 'r') as f:
        all_numbers = json.load(f)
    
    # Simulate the first fiscal note scenario
    new_document_names = ["HB1483"]  # Only the first document
    
    print(f'📄 NEW documents for first fiscal note: {new_document_names}')
    print(f'📊 Total numbers available: {len(all_numbers)}')
    
    # Apply the FIXED filtering logic
    numbers_data = []
    
    for number_item in all_numbers:
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
    
    # Group by document to see what was included/excluded
    included_docs = {}
    excluded_docs = {}
    
    for number_item in all_numbers:
        filename = number_item['filename']
        if number_item in numbers_data:
            if filename not in included_docs:
                included_docs[filename] = 0
            included_docs[filename] += 1
        else:
            if filename not in excluded_docs:
                excluded_docs[filename] = 0
            excluded_docs[filename] += 1
    
    print(f'\n✅ INCLUDED documents:')
    for filename, count in included_docs.items():
        print(f'   {filename}: {count} numbers')
    
    print(f'\n❌ EXCLUDED documents:')
    for filename, count in excluded_docs.items():
        print(f'   {filename}: {count} numbers')
    
    # Check if the fix worked
    print(f'\n🎯 FIX VERIFICATION:')
    
    # Should include only HB1483 base document numbers
    expected_includes = ['HB1483_.HTM.txt', 'HB1483.HTM.txt']
    expected_excludes = ['HB1483_CD1_.HTM.txt', 'HB1483_HD1_.HTM.txt', 'HB1483_SD1_TESTIMONY_WAM_04-04-25_.PDF.txt']
    
    for expected in expected_includes:
        if expected in included_docs:
            print(f'   ✅ Correctly included: {expected}')
        else:
            print(f'   ❌ Should have included: {expected}')
    
    for expected in expected_excludes:
        if expected in excluded_docs:
            print(f'   ✅ Correctly excluded: {expected}')
        else:
            print(f'   ❌ Should have excluded: {expected}')
    
    # Expected outcome
    if len(excluded_docs) > 0 and any('CD1' in doc or 'HD1' in doc or 'SD1' in doc for doc in excluded_docs):
        print(f'\n🎉 SUCCESS: Later document versions are now excluded!')
        print(f'   The LLM should no longer have access to numbers from later documents.')
        print(f'   This should prevent hallucinated citations to HB1483_CD1_, HB1483_HD1_, etc.')
    else:
        print(f'\n⚠️  Issue: Later document versions may still be included.')

if __name__ == "__main__":
    test_numbers_filtering_fix()
