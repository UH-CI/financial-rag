#!/usr/bin/env python3

import requests
import json
import re

def debug_citation_issues():
    """Debug the citation highlighting and tooltip issues"""
    
    print('🔍 DEBUGGING CITATION ISSUES')
    print('=' * 60)
    
    # Test cases from user report
    test_cases = [
        {
            "bill": "HB_727_2025",
            "fiscal_note": "HB727_SD1_SSCR1240_",
            "issue": "Financial citation highlighting not working",
            "sample_text": "Year 1 costs total $514,900 [15], which includes $175,000 [22]"
        },
        {
            "bill": "HB_300_2025", 
            "fiscal_note": "HB300_CD1_CCR45_",
            "issue": "Missing chunk text in tooltips",
            "sample_text": "appropriates $10,000,000 [55] from general revenues"
        }
    ]
    
    for test_case in test_cases:
        print(f'\n🔍 Testing {test_case["bill"]} - {test_case["fiscal_note"]}')
        print(f'   Issue: {test_case["issue"]}')
        print(f'   Sample: {test_case["sample_text"]}')
        
        try:
            # Get API data
            url = f"http://localhost:8200/get_fiscal_note_data/{test_case['bill']}"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                # Find the specific fiscal note
                target_note = None
                for note in data.get("fiscal_notes", []):
                    if test_case["fiscal_note"] in note.get("filename", ""):
                        target_note = note
                        break
                
                if target_note:
                    print(f'   ✅ Found fiscal note: {target_note["filename"]}')
                    
                    # Check number_citation_map for the citations mentioned
                    number_citation_map = data.get("number_citation_map", {})
                    
                    # Extract citation numbers from sample text
                    citations = re.findall(r'\[(\d+)\]', test_case["sample_text"])
                    print(f'   📋 Citations to check: {citations}')
                    
                    for citation_num in citations:
                        citation_data = number_citation_map.get(citation_num)
                        if citation_data:
                            print(f'   ✅ Citation [{citation_num}]:')
                            print(f'      Amount: ${citation_data.get("amount", "N/A")}')
                            print(f'      Document: {citation_data.get("document_name", "N/A")}')
                            
                            # Check if chunk text is available
                            chunk_data = citation_data.get("data")
                            if chunk_data and chunk_data.get("text"):
                                chunk_text = chunk_data.get("text", "")
                                print(f'      ✅ Chunk text available: {len(chunk_text)} chars')
                                print(f'      Preview: {chunk_text[:100]}...')
                                
                                # Check if the amount appears in the chunk text
                                amount = citation_data.get("amount", 0)
                                amount_patterns = [
                                    f"${amount:,.0f}",
                                    f"${amount:,}",
                                    f"${int(amount)}",
                                    f"{amount:,.0f}",
                                    f"{int(amount)}"
                                ]
                                
                                found_in_chunk = False
                                for pattern in amount_patterns:
                                    if pattern in chunk_text:
                                        print(f'      ✅ Amount found in chunk as: {pattern}')
                                        found_in_chunk = True
                                        break
                                
                                if not found_in_chunk:
                                    print(f'      ❌ Amount ${amount} not found in chunk text')
                                    print(f'      🔍 Chunk preview: {chunk_text[:200]}...')
                                
                            else:
                                print(f'      ❌ No chunk text available')
                                print(f'      🔍 Citation data: {citation_data}')
                        else:
                            print(f'   ❌ Citation [{citation_num}] not found in number_citation_map')
                    
                    # Check if the fiscal note text contains the expected financial citations
                    note_data = target_note.get("data", {})
                    
                    # Look through all fields for the sample text
                    found_sample = False
                    for field_name, field_value in note_data.items():
                        if isinstance(field_value, str) and test_case["sample_text"][:20] in field_value:
                            print(f'   ✅ Found sample text in field: {field_name}')
                            print(f'   📄 Full field content:')
                            print(f'      {field_value[:500]}...')
                            found_sample = True
                            break
                    
                    if not found_sample:
                        print(f'   ❌ Sample text not found in fiscal note')
                
                else:
                    print(f'   ❌ Fiscal note {test_case["fiscal_note"]} not found')
                    available_notes = [note.get("filename", "") for note in data.get("fiscal_notes", [])]
                    print(f'   Available notes: {available_notes}')
                    
            else:
                print(f'   ❌ API request failed: {response.status_code}')
                
        except Exception as e:
            print(f'   ❌ Error: {e}')
    
    print(f'\n🎯 SUMMARY:')
    print(f'   Issue 1: Financial highlighting - Check if amounts exist in chunk text')
    print(f'   Issue 2: Missing tooltips - Check if number_citation_map has data')
    print(f'   Both issues may be related to the numbers filtering fix')

if __name__ == "__main__":
    debug_citation_issues()
