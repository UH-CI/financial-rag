#!/usr/bin/env python3

import json
import re

def debug_document_citations_first_note():
    """Debug why the first fiscal note has no document citations to HB1483"""
    
    print('🔍 DEBUGGING DOCUMENT CITATIONS IN FIRST FISCAL NOTE')
    print('=' * 60)
    
    # Load the first fiscal note (raw JSON)
    fiscal_note_file = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation/HB_1483_2025/fiscal_notes/HB1483.json"
    with open(fiscal_note_file, 'r') as f:
        fiscal_note = json.load(f)
    
    # Load the metadata to see the raw LLM response
    metadata_file = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation/HB_1483_2025/fiscal_notes/HB1483_metadata.json"
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    # Get the raw LLM response text
    raw_response = metadata.get('response_metadata', {}).get('response_text', '')
    
    print('📄 Documents processed: HB1483 only')
    print('💭 Expected citations: (HB1483) should become [1]')
    
    # Check what's in the raw LLM response vs processed JSON
    print(f'\n🔍 Checking raw LLM response for HB1483 citations:')
    
    # Look for HB1483 citations in raw response
    hb1483_citations = re.findall(r'\(HB1483[^)]*\)', raw_response)
    print(f'   Raw LLM response HB1483 citations: {len(hb1483_citations)}')
    for citation in set(hb1483_citations):
        print(f'      {citation}')
    
    # Look for any parenthetical citations in raw response
    all_citations_raw = re.findall(r'\(([^)]+)\)', raw_response)
    document_citations_raw = [c for c in all_citations_raw if not (c.isdigit() and len(c) <= 2) and not c.isalpha()]
    
    print(f'\n📋 All document citations in raw LLM response:')
    print(f'   Total: {len(set(document_citations_raw))}')
    for citation in sorted(set(document_citations_raw)):
        print(f'      ({citation})')
    
    # Check what's in the processed JSON
    print(f'\n📄 Checking processed fiscal note JSON:')
    
    all_citations_processed = set()
    for field_name, content in fiscal_note.items():
        if isinstance(content, str):
            citations = re.findall(r'\(([^)]+)\)', content)
            for citation in citations:
                if not (citation.isdigit() and len(citation) <= 2) and not citation.isalpha():
                    all_citations_processed.add(citation)
    
    print(f'   Total document citations in processed JSON: {len(all_citations_processed)}')
    for citation in sorted(all_citations_processed):
        print(f'      ({citation})')
    
    # Check if the issue is in LLM generation or API processing
    if not document_citations_raw:
        print(f'\n🚨 ISSUE IDENTIFIED: LLM Generation Problem')
        print(f'   The LLM is not generating ANY document citations in the raw response!')
        print(f'   This means the LLM is not citing the HB1483 document at all.')
        print(f'   Expected: The LLM should generate citations like (HB1483) in its response.')
        
        # Check if HB1483 content is actually in the context
        print(f'\n🔍 Checking if HB1483 content was in the LLM context:')
        
        # Look for HB1483 document markers in the raw response
        if '=== Document: HB1483 ===' in raw_response:
            print(f'   ✅ HB1483 document was in the context')
        else:
            print(f'   ❌ HB1483 document marker not found in context')
        
        # Check the prompt structure
        if 'Context:' in raw_response:
            context_start = raw_response.find('Context:')
            context_section = raw_response[context_start:context_start+500]
            print(f'\n📝 Context section (first 500 chars):')
            print(context_section)
        
    elif document_citations_raw and not all_citations_processed:
        print(f'\n🚨 ISSUE IDENTIFIED: API Processing Problem')
        print(f'   The LLM generated document citations, but they were lost during API processing!')
        print(f'   Raw citations: {document_citations_raw}')
        print(f'   Processed citations: {list(all_citations_processed)}')
        
    else:
        print(f'\n✅ Citations are being generated and processed')
        print(f'   But they might not be the RIGHT citations (should be HB1483)')
    
    # Check document mapping
    base_dir = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation/HB_1483_2025"
    mapping_file = f"{base_dir}/document_mapping.json"
    
    with open(mapping_file, 'r') as f:
        document_mapping = json.load(f)
    
    print(f'\n📋 Document Mapping for HB1483:')
    for doc_name, doc_num in document_mapping.items():
        if 'HB1483' in doc_name and not any(x in doc_name for x in ['CD1', 'HD1', 'SD1', 'TESTIMONY', 'HSCR', 'SSCR']):
            print(f'   {doc_name} -> [{doc_num}]')

if __name__ == "__main__":
    debug_document_citations_first_note()
