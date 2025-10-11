#!/usr/bin/env python3

import json
import re

def test_financial_citation_fix():
    """Test if the financial citation fix is working for $50,000 [21]"""
    
    print('🔍 TESTING FINANCIAL CITATION FIX VERIFICATION')
    print('=' * 60)
    
    # Check the current fiscal note before regeneration
    fiscal_note_file = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation/HB_1483_2025/fiscal_notes/HB1483_SD1_SSCR1831_.json"
    metadata_file = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation/HB_1483_2025/fiscal_notes/HB1483_SD1_SSCR1831__metadata.json"
    
    try:
        # Load the fiscal note
        with open(fiscal_note_file, 'r') as f:
            fiscal_note = json.load(f)
        
        # Load the metadata
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        print(f'📄 Analyzing fiscal note: HB1483_SD1_SSCR1831_')
        
        # Check the economic_impact section for $50,000 citations
        economic_impact = fiscal_note.get("economic_impact", "")
        print(f'\n💰 Economic Impact section:')
        print(f'   {economic_impact}')
        
        # Find all financial amounts mentioned
        financial_amounts = re.findall(r'\$([0-9,]+)', economic_impact)
        print(f'\n💵 Financial amounts found: {financial_amounts}')
        
        # Check if $50,000 is cited with parenthetical reference
        if '$50,000' in economic_impact:
            print(f'   ✅ $50,000 amount found in text')
            
            # Check if it has a parenthetical citation
            citation_pattern = r'\$50,000[^(]*\(([^)]+)\)'
            citation_match = re.search(citation_pattern, economic_impact)
            if citation_match:
                citation_ref = citation_match.group(1)
                print(f'   ✅ $50,000 has citation: ({citation_ref})')
            else:
                print(f'   ❌ $50,000 has no parenthetical citation')
        else:
            print(f'   ❌ $50,000 amount not found in text')
        
        # Check the metadata for numbers_data
        numbers_used = metadata.get('numbers_used', 0)
        numbers_data = metadata.get('response_metadata', {}).get('numbers_data', [])
        
        print(f'\n📊 Metadata Analysis:')
        print(f'   Numbers used: {numbers_used}')
        print(f'   Numbers data entries: {len(numbers_data)}')
        
        # Look for $50,000 in numbers_data
        found_50000_in_metadata = False
        for number_item in numbers_data:
            if abs(number_item.get('number', 0) - 50000) < 0.01:
                found_50000_in_metadata = True
                print(f'   ✅ Found $50,000 in numbers_data:')
                print(f'      Filename: {number_item.get("filename", "N/A")}')
                print(f'      Text length: {len(number_item.get("text", ""))} chars')
                print(f'      Text preview: {number_item.get("text", "")[:150]}...')
                break
        
        if not found_50000_in_metadata:
            print(f'   ❌ $50,000 NOT found in numbers_data')
            print(f'   🔍 This means the fix hasn\'t been applied yet or needs regeneration')
        
        # Check what documents were processed
        new_docs = metadata.get('new_documents_processed', [])
        print(f'\n📄 Documents processed: {new_docs}')
        
        # Expected result after fix
        print(f'\n🎯 EXPECTED AFTER FIX:')
        print(f'   - numbers_used should be > 0 (currently: {numbers_used})')
        print(f'   - numbers_data should contain $50,000 entry (currently: {"✅" if found_50000_in_metadata else "❌"})')
        print(f'   - Frontend should show chunk text for [21] citation')
        
        if numbers_used == 0 and not found_50000_in_metadata:
            print(f'\n⚠️  REGENERATION NEEDED:')
            print(f'   The fiscal notes need to be regenerated with the updated logic.')
            print(f'   Current state shows the fix hasn\'t been applied yet.')
        elif found_50000_in_metadata:
            print(f'\n🎉 FIX APPEARS TO BE WORKING:')
            print(f'   The $50,000 entry is now in the metadata.')
            print(f'   The frontend should display proper chunk text for financial citations.')
        
    except FileNotFoundError as e:
        print(f'❌ File not found: {e}')
        print(f'   The fiscal notes may need to be regenerated first.')
    except Exception as e:
        print(f'❌ Error: {e}')

if __name__ == "__main__":
    test_financial_citation_fix()
