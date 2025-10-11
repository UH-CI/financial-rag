#!/usr/bin/env python3

import json
import re

def debug_first_fiscal_note_citations():
    """Debug why the first fiscal note doesn't cite the first bill introduction document"""
    
    print('🔍 DEBUGGING FIRST FISCAL NOTE CITATIONS')
    print('=' * 60)
    
    # Load the first fiscal note
    fiscal_note_file = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation/HB_1483_2025/fiscal_notes/HB1483.json"
    with open(fiscal_note_file, 'r') as f:
        fiscal_note = json.load(f)
    
    # Load the metadata
    metadata_file = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation/HB_1483_2025/fiscal_notes/HB1483_metadata.json"
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    # Check what documents were processed
    new_docs = metadata.get('new_documents_processed', [])
    numbers_used = metadata.get('numbers_used', 0)
    
    print(f'📄 Documents processed for first fiscal note: {new_docs}')
    print(f'💰 Numbers used: {numbers_used}')
    
    # Extract all citations from the fiscal note
    print(f'\n🔍 Citations found in first fiscal note:')
    
    all_citations = set()
    for field_name, content in fiscal_note.items():
        if isinstance(content, str):
            # Find all parenthetical citations
            citations = re.findall(r'\(([^)]+)\)', content)
            for citation in citations:
                # Skip numbered citations like (1), (2), etc.
                if not (citation.isdigit() and len(citation) <= 2):
                    all_citations.add(citation)
    
    print(f'   Total unique citations: {len(all_citations)}')
    for citation in sorted(all_citations):
        print(f'      ({citation})')
    
    # Check which citations should be valid for the first fiscal note
    print(f'\n✅ Expected citations for first fiscal note:')
    expected_citations = [
        'HB1483',
        'HB1483_.HTM.txt',
        'HB1483.HTM.txt'
    ]
    
    for expected in expected_citations:
        if expected in all_citations:
            print(f'   ✅ ({expected}) - FOUND')
        else:
            print(f'   ❌ ({expected}) - MISSING')
    
    # Check which citations are INVALID (from later documents)
    print(f'\n❌ Invalid citations (from later documents):')
    invalid_citations = []
    
    for citation in all_citations:
        # Check if this citation refers to a later document
        if any(later_doc in citation for later_doc in [
            'CD1', 'HD1', 'SD1', 'TESTIMONY', 'HSCR', 'SSCR', 'CCR'
        ]):
            invalid_citations.append(citation)
            print(f'   ❌ ({citation}) - Should NOT be in first fiscal note!')
    
    print(f'\n📊 Citation Analysis Summary:')
    print(f'   Total citations: {len(all_citations)}')
    print(f'   Invalid citations: {len(invalid_citations)}')
    print(f'   Valid citations: {len(all_citations) - len(invalid_citations)}')
    
    if invalid_citations:
        print(f'\n🚨 PROBLEM IDENTIFIED:')
        print(f'   The LLM is hallucinating citations to documents that were NOT in the context!')
        print(f'   The first fiscal note should only cite HB1483 documents.')
        
        # Check the numbers data to see if this explains the wrong citations
        response_metadata = metadata.get('response_metadata', {})
        numbers_data = response_metadata.get('numbers_data', [])
        
        print(f'\n💰 Numbers data analysis:')
        print(f'   Total numbers available: {len(numbers_data)}')
        
        # Group numbers by document
        numbers_by_doc = {}
        for number_item in numbers_data:
            filename = number_item.get('filename', 'Unknown')
            if filename not in numbers_by_doc:
                numbers_by_doc[filename] = []
            numbers_by_doc[filename].append(number_item['number'])
        
        print(f'   Numbers grouped by document:')
        for filename, numbers in numbers_by_doc.items():
            print(f'      {filename}: {len(numbers)} numbers')
            if len(numbers) <= 5:
                print(f'         Values: {numbers}')
        
        # Check if the wrong citations come from the numbers data
        print(f'\n🔍 Checking if wrong citations come from numbers data:')
        for invalid_citation in invalid_citations[:5]:  # Check first 5
            # Remove file extensions for comparison
            base_citation = invalid_citation.replace('.HTM.txt', '').replace('.PDF.txt', '')
            
            matching_numbers = []
            for filename, numbers in numbers_by_doc.items():
                if base_citation in filename:
                    matching_numbers.extend(numbers)
            
            if matching_numbers:
                print(f'   ({invalid_citation}) -> {len(matching_numbers)} numbers found')
                print(f'      This explains why the LLM cited this document!')
            else:
                print(f'   ({invalid_citation}) -> No numbers found (pure hallucination)')

if __name__ == "__main__":
    debug_first_fiscal_note_citations()
