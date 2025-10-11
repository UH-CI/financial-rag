#!/usr/bin/env python3

import json

def test_document_name_matching_fix():
    """Test the document name matching fix for .PDF.txt extensions"""
    
    print('🔍 TESTING DOCUMENT NAME MATCHING FIX')
    print('=' * 50)
    
    # Load numbers data
    numbers_file = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation/HB_1483_2025/HB_1483_2025_numbers.json"
    with open(numbers_file, 'r') as f:
        all_numbers = json.load(f)
    
    # Simulate the HB1483_SD1_SSCR1831_ fiscal note scenario
    new_document_names = ["HB1483_SD1_TESTIMONY_WAM_04-04-25_", "HB1483_SD1_SSCR1831_"]
    
    print(f'📄 NEW documents: {new_document_names}')
    print(f'📊 Total numbers available: {len(all_numbers)}')
    
    # Apply the FIXED filtering logic
    numbers_data = []
    
    for number_item in all_numbers:
        # Check if this number's document is in the NEW documents
        number_doc_name = number_item['filename']
        # Remove various extensions for comparison
        number_doc_base = number_doc_name
        if number_doc_name.endswith('.PDF.txt'):
            number_doc_base = number_doc_name[:-8]  # Remove .PDF.txt
        elif number_doc_name.endswith('.txt'):
            number_doc_base = number_doc_name[:-4]  # Remove .txt
        
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
    
    # Check specifically for the $50,000 amount
    found_50000 = False
    for number_item in numbers_data:
        if abs(number_item.get("number", 0) - 50000) < 0.01:
            found_50000 = True
            print(f'\n🎯 FOUND $50,000 ENTRY:')
            print(f'   Filename: {number_item.get("filename")}')
            print(f'   Text preview: {number_item.get("text", "")[:100]}...')
            break
    
    if not found_50000:
        print(f'\n❌ $50,000 entry NOT found in filtered results')
        
        # Check if it exists in the original data
        for number_item in all_numbers:
            if abs(number_item.get("number", 0) - 50000) < 0.01:
                print(f'   But it exists in original data: {number_item.get("filename")}')
                
                # Test the matching logic specifically for this entry
                number_doc_name = number_item['filename']
                number_doc_base = number_doc_name
                if number_doc_name.endswith('.PDF.txt'):
                    number_doc_base = number_doc_name[:-8]
                elif number_doc_name.endswith('.txt'):
                    number_doc_base = number_doc_name[:-4]
                
                print(f'   Original filename: {number_doc_name}')
                print(f'   Base filename: {number_doc_base}')
                
                for new_doc_name in new_document_names:
                    if (number_doc_name == new_doc_name or 
                        number_doc_base == new_doc_name):
                        print(f'   ✅ Should match with: {new_doc_name}')
                    else:
                        print(f'   ❌ Does not match: {new_doc_name}')
                break
    else:
        print(f'\n🎉 SUCCESS: $50,000 entry found in filtered results!')
        print(f'   This should fix the financial citation tooltip issue.')

if __name__ == "__main__":
    test_document_name_matching_fix()
