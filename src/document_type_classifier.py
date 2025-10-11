#!/usr/bin/env python3

def classify_document_type(document_name: str) -> str:
    """
    Classify document type based on naming patterns
    
    Args:
        document_name: Document name like "HB1483_HD1_TESTIMONY_FIN_02-25-25_"
    
    Returns:
        Document type: "Bill Introduction", "Bill Amendment", "Committee Report", "Testimony"
    """
    
    # Remove common suffixes for analysis
    name = document_name.replace('_.HTM', '').replace('.txt', '').replace('.PDF', '')
    
    # Bill Introduction (base bill)
    # Pattern: HB1483, SB123, etc.
    if name.count('_') == 0 or (name.count('_') == 1 and name.endswith('_')):
        return "Bill Introduction"
    
    # Testimony documents
    # Pattern: HB1483_TESTIMONY_*, HB1483_HD1_TESTIMONY_*, etc.
    if 'TESTIMONY' in name:
        return "Testimony"
    
    # Committee Reports
    # Pattern: HB1483_HD1_HSCR629_, HB1483_SD1_SSCR1268_, HB1483_CD1_CCR233_
    committee_report_indicators = ['HSCR', 'SSCR', 'CCR', 'SCR', 'HCR']
    if any(indicator in name for indicator in committee_report_indicators):
        return "Committee Report"
    
    # Bill Amendments (House/Senate/Conference drafts)
    # Pattern: HB1483_HD1, HB1483_SD1, HB1483_CD1, HB1483_HFA7, HB1483_SFA12
    amendment_indicators = ['HD', 'SD', 'CD', 'HFA', 'SFA']
    if any(f'_{indicator}' in name for indicator in amendment_indicators):
        return "Bill Amendment"
    
    # Default fallback
    return "Document"

def get_document_type_description(doc_type: str) -> str:
    """Get a user-friendly description of the document type"""
    descriptions = {
        "Bill Introduction": "Original bill as introduced",
        "Bill Amendment": "Amended version of the bill", 
        "Committee Report": "Committee analysis and recommendations",
        "Testimony": "Public testimony on the bill",
        "Document": "Legislative document"
    }
    return descriptions.get(doc_type, doc_type)

def get_document_type_icon(doc_type: str) -> str:
    """Get an icon for the document type"""
    icons = {
        "Bill Introduction": "📄",
        "Bill Amendment": "📝", 
        "Committee Report": "📋",
        "Testimony": "🗣️",
        "Document": "📄"
    }
    return icons.get(doc_type, "📄")

def test_document_classification():
    """Test the document classification with sample names"""
    test_cases = [
        "HB1483",
        "HB1483_TESTIMONY_JHA_02-06-25_",
        "HB1483_HD1",
        "HB1483_HD1_HSCR629_",
        "HB1483_HD1_TESTIMONY_FIN_02-25-25_",
        "HB1483_SD1_SSCR1268_",
        "HB1483_CD1_CCR233_",
        "HB1483_CD1_HFA7",
        "HB1483_CD1_SFA12",
        "HB1483_CD2"
    ]
    
    print("🔍 DOCUMENT TYPE CLASSIFICATION TEST")
    print("=" * 50)
    
    for doc_name in test_cases:
        doc_type = classify_document_type(doc_name)
        description = get_document_type_description(doc_type)
        icon = get_document_type_icon(doc_type)
        
        print(f"{icon} {doc_name}")
        print(f"   Type: {doc_type}")
        print(f"   Description: {description}")
        print()

if __name__ == "__main__":
    test_document_classification()
