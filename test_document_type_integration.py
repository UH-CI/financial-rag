#!/usr/bin/env python3

import requests
import json

def test_document_type_integration():
    """Test the document type classification integration with the API"""
    
    print('🔍 TESTING DOCUMENT TYPE INTEGRATION')
    print('=' * 50)
    
    # Test the API endpoint
    try:
        url = "http://localhost:8200/get_fiscal_note_data/HB_1483_2025"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            
            print(f'✅ API Response received')
            print(f'📊 Status: {data.get("status")}')
            
            # Check if enhanced_document_mapping is present
            enhanced_mapping = data.get("enhanced_document_mapping", {})
            print(f'📋 Enhanced document mapping entries: {len(enhanced_mapping)}')
            
            if enhanced_mapping:
                print(f'\n📄 Document Type Classification Results:')
                
                # Sort by citation number for better display
                for citation_num in sorted(enhanced_mapping.keys(), key=int):
                    doc_info = enhanced_mapping[citation_num]
                    print(f'   [{citation_num}] {doc_info["icon"]} {doc_info["name"]}')
                    print(f'       Type: {doc_info["type"]}')
                    print(f'       Description: {doc_info["description"]}')
                    print()
                
                # Test specific document types
                print(f'🔍 Document Type Distribution:')
                type_counts = {}
                for doc_info in enhanced_mapping.values():
                    doc_type = doc_info["type"]
                    type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
                
                for doc_type, count in sorted(type_counts.items()):
                    print(f'   {doc_type}: {count} documents')
                
                # Verify expected types are present
                expected_types = ["Bill Introduction", "Bill Amendment", "Committee Report", "Testimony"]
                found_types = set(type_counts.keys())
                
                print(f'\n✅ Expected document types found:')
                for expected_type in expected_types:
                    if expected_type in found_types:
                        print(f'   ✅ {expected_type}')
                    else:
                        print(f'   ❌ {expected_type} (missing)')
                
            else:
                print(f'❌ No enhanced document mapping found in API response')
                
        else:
            print(f'❌ API request failed: {response.status_code}')
            print(f'   Response: {response.text}')
            
    except Exception as e:
        print(f'❌ Error testing API: {e}')
        print(f'   Make sure the backend is running on port 8200')

if __name__ == "__main__":
    test_document_type_integration()
