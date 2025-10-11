#!/usr/bin/env python3

import json
import sys
import os

# Add the src directory to the path to import the API functions
sys.path.append('/Users/rodericktabalba/Documents/GitHub/financial-rag/src')

def debug_missing_tooltips():
    """Debug why some financial citation tooltips are missing chunk text"""
    
    print('🔍 DEBUGGING MISSING FINANCIAL TOOLTIPS')
    print('=' * 60)
    
    # Test the specific cases mentioned by the user
    test_cases = [
        {
            "bill": "HB_727_2025",
            "fiscal_note": "HB727_SD1_SSCR1240_",
            "amount": 514900,
            "expected_citation": 15
        },
        {
            "bill": "HB_300_2025", 
            "fiscal_note": "HB300_CD1_CCR45_",
            "amount": 10000000,
            "expected_citation": 55
        }
    ]
    
    for test_case in test_cases:
        print(f'\n🔍 Testing {test_case["bill"]} - {test_case["fiscal_note"]}')
        print(f'   Amount: ${test_case["amount"]:,}')
        print(f'   Expected Citation: [{test_case["expected_citation"]}]')
        
        try:
            # Load the fiscal note and metadata directly
            base_dir = f"/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation/{test_case['bill']}"
            fiscal_note_file = f"{base_dir}/fiscal_notes/{test_case['fiscal_note']}.json"
            metadata_file = f"{base_dir}/fiscal_notes/{test_case['fiscal_note']}_metadata.json"
            
            # Load fiscal note
            with open(fiscal_note_file, 'r') as f:
                fiscal_note = json.load(f)
            
            # Load metadata
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            print(f'   ✅ Loaded fiscal note and metadata')
            
            # Check numbers_data in metadata
            numbers_data = metadata.get('response_metadata', {}).get('numbers_data', [])
            print(f'   📊 Numbers data entries: {len(numbers_data)}')
            
            # Find the specific amount in numbers_data
            target_number_data = None
            for number_item in numbers_data:
                if abs(number_item.get('number', 0) - test_case['amount']) < 0.01:
                    target_number_data = number_item
                    break
            
            if target_number_data:
                print(f'   ✅ Found target amount in numbers_data:')
                print(f'      Filename: {target_number_data.get("filename")}')
                print(f'      Document type: {target_number_data.get("document_type")}')
                print(f'      Text length: {len(target_number_data.get("text", ""))} chars')
                
                chunk_text = target_number_data.get("text", "")
                if chunk_text:
                    print(f'      ✅ Chunk text available')
                    print(f'      Preview: {chunk_text[:150]}...')
                    
                    # Check if the amount appears in the chunk text
                    amount_patterns = [
                        f"${test_case['amount']:,}",
                        f"${test_case['amount']:,.0f}",
                        f"${test_case['amount']:,}.00",
                        f"{test_case['amount']:,}",
                        f"{test_case['amount']:,.0f}"
                    ]
                    
                    found_patterns = []
                    for pattern in amount_patterns:
                        if pattern in chunk_text:
                            found_patterns.append(pattern)
                    
                    if found_patterns:
                        print(f'      ✅ Amount found in chunk as: {found_patterns}')
                    else:
                        print(f'      ❌ Amount not found in chunk text')
                        print(f'      🔍 Searched for: {amount_patterns}')
                else:
                    print(f'      ❌ No chunk text in numbers_data')
            else:
                print(f'   ❌ Target amount ${test_case["amount"]:,} not found in numbers_data')
                
                # Show what amounts are available
                available_amounts = [item.get('number', 0) for item in numbers_data[:10]]
                print(f'   🔍 First 10 available amounts: {available_amounts}')
            
            # Now simulate the API processing to see what would be returned
            print(f'\n🔧 Simulating API processing...')
            
            # Import the API processing function
            try:
                from api import process_fiscal_note_references_structured
                
                # Load document mapping
                mapping_file = f"{base_dir}/document_mapping.json"
                with open(mapping_file, 'r') as f:
                    document_mapping = json.load(f)
                
                # Get chunks data and sentence attributions
                chunks_data = metadata.get('response_metadata', {}).get('chunks_metadata', {}).get('chunk_details', [])
                sentence_attributions = metadata.get('response_metadata', {}).get('sentence_attribution_analysis', {}).get('sentence_attributions', [])
                
                print(f'   📋 Document mapping entries: {len(document_mapping)}')
                print(f'   📊 Chunks data entries: {len(chunks_data)}')
                print(f'   📝 Sentence attributions: {len(sentence_attributions)}')
                
                # Process the fiscal note
                processed_data = process_fiscal_note_references_structured(
                    fiscal_note, 
                    document_mapping, 
                    numbers_data, 
                    chunks_data, 
                    sentence_attributions
                )
                
                # Check if the number citation map was created
                number_citation_map = processed_data.get('_number_citation_map', {})
                print(f'   💰 Number citation map entries: {len(number_citation_map)}')
                
                # Look for the expected citation
                expected_citation_str = str(test_case['expected_citation'])
                if expected_citation_str in number_citation_map:
                    citation_data = number_citation_map[expected_citation_str]
                    print(f'   ✅ Found expected citation [{test_case["expected_citation"]}]:')
                    print(f'      Amount: ${citation_data.get("amount", "N/A")}')
                    print(f'      Document: {citation_data.get("document_name", "N/A")}')
                    
                    chunk_data = citation_data.get("data")
                    if chunk_data and chunk_data.get("text"):
                        print(f'      ✅ Chunk text available in citation data')
                        print(f'      Length: {len(chunk_data.get("text", ""))} chars')
                    else:
                        print(f'      ❌ No chunk text in citation data')
                        print(f'      🔍 Citation data structure: {citation_data}')
                else:
                    print(f'   ❌ Expected citation [{test_case["expected_citation"]}] not found')
                    available_citations = list(number_citation_map.keys())[:10]
                    print(f'   🔍 Available citations: {available_citations}')
                
            except Exception as e:
                print(f'   ❌ Error during API processing simulation: {e}')
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            print(f'   ❌ Error loading files: {e}')
    
    print(f'\n🎯 CONCLUSION:')
    print(f'   The issue might be in:')
    print(f'   1. Numbers data not containing the expected amounts')
    print(f'   2. API processing not correctly mapping amounts to citations')
    print(f'   3. Frontend not receiving the chunk text data')

if __name__ == "__main__":
    debug_missing_tooltips()
