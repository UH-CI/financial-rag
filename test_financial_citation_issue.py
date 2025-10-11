#!/usr/bin/env python3

import json
import requests

def test_financial_citation_issue():
    """Test the financial citation issue with $50,000 in HB1483_SD1_SSCR1831_"""
    
    print('🔍 TESTING FINANCIAL CITATION ISSUE')
    print('=' * 50)
    
    # Test the API endpoint to see what data is being returned
    try:
        response = requests.get('http://localhost:8200/get_fiscal_note_data/HB_1483_2025')
        if response.status_code == 200:
            data = response.json()
            
            print(f'✅ API Response received')
            print(f'📊 Number of fiscal notes: {len(data.get("fiscal_notes", []))}')
            
            # Find the HB1483_SD1_SSCR1831_ fiscal note
            target_fiscal_note = None
            for note in data.get("fiscal_notes", []):
                if "HB1483_SD1_SSCR1831_" in note.get("filename", ""):
                    target_fiscal_note = note
                    break
            
            if target_fiscal_note:
                print(f'✅ Found target fiscal note: {target_fiscal_note["filename"]}')
                
                # Check the economic_impact section for $50,000 citation
                economic_impact = target_fiscal_note["data"].get("economic_impact", "")
                print(f'\n📄 Economic Impact section:')
                print(f'   {economic_impact[:200]}...')
                
                # Look for financial citations in the processed text
                import re
                financial_citations = re.findall(r'\$([0-9,]+)\s*\[(\d+)\]', economic_impact)
                print(f'\n💰 Financial citations found: {len(financial_citations)}')
                for amount, citation_num in financial_citations:
                    print(f'   ${amount} -> [{citation_num}]')
                
                # Check if there's number_citation_map data for citation 21
                number_citation_map = data.get("number_citation_map", {})
                citation_21_data = number_citation_map.get("21")
                
                print(f'\n🔍 Citation [21] data:')
                if citation_21_data:
                    print(f'   Amount: ${citation_21_data.get("amount", "N/A")}')
                    print(f'   Filename: {citation_21_data.get("filename", "N/A")}')
                    print(f'   Document name: {citation_21_data.get("document_name", "N/A")}')
                    
                    # Check if there's chunk text data
                    chunk_data = citation_21_data.get("data")
                    if chunk_data:
                        chunk_text = chunk_data.get("text", "")
                        print(f'   Chunk text length: {len(chunk_text)} characters')
                        if len(chunk_text) > 0:
                            print(f'   Chunk text preview: {chunk_text[:100]}...')
                        else:
                            print(f'   ❌ Chunk text is empty!')
                    else:
                        print(f'   ❌ No chunk data available!')
                else:
                    print(f'   ❌ No data found for citation [21]')
                
                # Check numbers_data for $50,000
                numbers_data = data.get("numbers_data", [])
                print(f'\n📊 Numbers data: {len(numbers_data)} entries')
                
                # Look for 50000 in numbers_data
                found_50000 = False
                for number_item in numbers_data:
                    if abs(number_item.get("number", 0) - 50000) < 0.01:
                        found_50000 = True
                        print(f'   ✅ Found $50,000 entry:')
                        print(f'      Filename: {number_item.get("filename", "N/A")}')
                        print(f'      Text length: {len(number_item.get("text", ""))} characters')
                        if len(number_item.get("text", "")) > 0:
                            print(f'      Text preview: {number_item.get("text", "")[:100]}...')
                        break
                
                if not found_50000:
                    print(f'   ❌ No $50,000 entry found in numbers_data')
                    print(f'   🔍 This explains why the tooltip has no content!')
                
            else:
                print(f'❌ Could not find HB1483_SD1_SSCR1831_ fiscal note')
                
        else:
            print(f'❌ API request failed: {response.status_code}')
            
    except Exception as e:
        print(f'❌ Error testing API: {e}')
        
    print(f'\n🎯 CONCLUSION:')
    print(f'   The issue is likely that the $50,000 amount is not in numbers_data,')
    print(f'   so the financial citation [21] has no chunk text to display in the tooltip.')

if __name__ == "__main__":
    test_financial_citation_issue()
