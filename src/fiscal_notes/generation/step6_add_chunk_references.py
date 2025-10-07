import json
import os
import glob
import re
from typing import List, Dict, Tuple, Any
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

# Initialize the sentence transformer model globally
print("Loading AllMiniLM model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded successfully!")

def chunk_text_by_sentences(text: str) -> List[Dict[str, Any]]:
    """
    Split text into individual sentences for precise similarity matching.
    
    Args:
        text: Input text to split into sentences
    
    Returns:
        List of dictionaries with sentence info
    """
    # Split text into sentences
    sentences = sent_tokenize(text)
    
    chunks = []
    
    for i, sentence in enumerate(sentences):
        # Skip very short sentences (likely artifacts)
        sentence = sentence.strip()
        if len(sentence) < 10:
            continue
            
        sentence_tokens = word_tokenize(sentence.lower())
        token_count = len(sentence_tokens)
        
        chunks.append({
            'id': i,
            'text': sentence,
            'sentence_index': i,
            'token_count': token_count,
            'word_count': len(sentence.split())
        })
    
    return chunks

def extract_sentences_with_references(fiscal_note_text: str) -> List[Dict[str, Any]]:
    """
    Extract sentences from fiscal note that contain document references.
    
    Args:
        fiscal_note_text: The fiscal note content
    
    Returns:
        List of sentences with their reference information
    """
    # Pattern to match document references in parentheses
    reference_pattern = r'\(([^)]+)\)'
    
    # Split into sentences
    sentences = sent_tokenize(fiscal_note_text)
    
    referenced_sentences = []
    
    for i, sentence in enumerate(sentences):
        # Find all references in this sentence
        references = re.findall(reference_pattern, sentence)
        
        if references:
            referenced_sentences.append({
                'sentence_id': i,
                'text': sentence,
                'references': references,
                'clean_text': re.sub(reference_pattern, '', sentence).strip()
            })
    
    return referenced_sentences

def find_best_matching_sentence(query_sentence: str, document_sentences: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Find the document sentence with highest cosine similarity to the given sentence using AllMiniLM embeddings.
    
    Args:
        query_sentence: The sentence to match
        document_sentences: List of document sentences
    
    Returns:
        Best matching sentence with similarity score
    """
    if not document_sentences:
        return None
    
    try:
        # Prepare texts for embedding
        sentence_texts = [sent['text'] for sent in document_sentences]
        
        # Generate embeddings using AllMiniLM
        print(f"Generating embeddings for query and {len(sentence_texts)} document sentences...")
        query_embedding = model.encode([query_sentence])
        sentence_embeddings = model.encode(sentence_texts)
        
        # Calculate cosine similarity between query sentence and all document sentences
        similarities = cosine_similarity(query_embedding, sentence_embeddings)[0]
        
        # Find best match
        best_idx = np.argmax(similarities)
        best_score = similarities[best_idx]
        
        print(f"Best match: sentence {best_idx} with similarity {best_score:.3f}")
        
        best_sentence = document_sentences[best_idx].copy()
        best_sentence['similarity_score'] = float(best_score)
        
        return best_sentence
        
    except Exception as e:
        print(f"Error in embedding similarity calculation: {e}")
        # Return first sentence as fallback
        fallback_sentence = document_sentences[0].copy()
        fallback_sentence['similarity_score'] = 0.0
        return fallback_sentence

def process_fiscal_note_with_chunks(fiscal_note_path: str, documents_dir: str) -> Dict[str, Any]:
    """
    Process a single fiscal note to add chunk references.
    
    Args:
        fiscal_note_path: Path to the fiscal note JSON file
        documents_dir: Directory containing document text files
    
    Returns:
        Enhanced fiscal note with chunk references
    """
    # Load fiscal note
    with open(fiscal_note_path, 'r', encoding='utf-8') as f:
        fiscal_note = json.load(f)
    
    # Load and chunk all documents
    document_chunks = {}
    
    # Get all text files in documents directory
    txt_files = glob.glob(os.path.join(documents_dir, "*.txt"))
    
    for txt_file in txt_files:
        doc_name = os.path.splitext(os.path.basename(txt_file))[0]
        
        with open(txt_file, 'r', encoding='utf-8') as f:
            doc_text = f.read()
        
        # Split document into individual sentences for precise matching
        chunks = chunk_text_by_sentences(doc_text)
        document_chunks[doc_name] = chunks
    
    # Process each field in the fiscal note
    enhanced_fiscal_note = fiscal_note.copy()
    
    for field_name, field_value in fiscal_note.items():
        if isinstance(field_value, str) and field_value.strip():
            # Extract sentences with references
            referenced_sentences = extract_sentences_with_references(field_value)
            
            # For each referenced sentence, find best matching chunks
            sentence_chunk_mappings = []
            
            for ref_sentence in referenced_sentences:
                sentence_mappings = {
                    'sentence': ref_sentence,
                    'chunk_matches': {}
                }
                
                # For each reference in the sentence, find best chunk
                for reference in ref_sentence['references']:
                    # Try to find matching document
                    matching_docs = []
                    
                    for doc_name, chunks in document_chunks.items():
                        if reference in doc_name or doc_name in reference:
                            matching_docs.append((doc_name, chunks))
                    
                    # If no exact match, try partial matching
                    if not matching_docs:
                        for doc_name, chunks in document_chunks.items():
                            # Check if any part of the reference matches the document name
                            ref_parts = reference.replace('_', ' ').split()
                            doc_parts = doc_name.replace('_', ' ').split()
                            
                            if any(part in doc_name.upper() for part in ref_parts if len(part) > 2):
                                matching_docs.append((doc_name, chunks))
                    
                    # Find best chunk for this reference
                    if matching_docs:
                        best_overall_chunk = None
                        best_overall_score = -1
                        best_doc_name = None
                        
                        # Find best matching sentence for this reference
                        best_sentence = find_best_matching_sentence(sentence_info['clean_text'], matching_docs[0][1])
                        if best_sentence and best_sentence['similarity_score'] > best_overall_score:
                            best_overall_chunk = best_sentence
                            best_overall_score = best_sentence['similarity_score']
                            best_doc_name = matching_docs[0][0]
                        
                        if best_overall_chunk:
                            sentence_mappings['chunk_matches'][reference] = {
                                'document_name': best_doc_name,
                                'chunk': best_overall_chunk
                            }
                
                if sentence_mappings['chunk_matches']:
                    sentence_chunk_mappings.append(sentence_mappings)
            
            # Add chunk mappings to the enhanced fiscal note
            if sentence_chunk_mappings:
                enhanced_fiscal_note[f"{field_name}_chunk_references"] = sentence_chunk_mappings
    
    return enhanced_fiscal_note

def add_chunk_references_to_fiscal_notes(fiscal_notes_dir: str, documents_dir: str) -> str:
    """
    Process all fiscal notes in a directory to add chunk references.
    
    Args:
        fiscal_notes_dir: Directory containing fiscal note JSON files
        documents_dir: Directory containing document text files
    
    Returns:
        Path to the enhanced fiscal notes directory
    """
    # Create output directory for enhanced fiscal notes
    base_dir = os.path.dirname(fiscal_notes_dir)
    enhanced_dir = os.path.join(base_dir, "fiscal_notes_with_chunks")
    os.makedirs(enhanced_dir, exist_ok=True)
    
    # Get all fiscal note JSON files
    fiscal_note_files = glob.glob(os.path.join(fiscal_notes_dir, "*.json"))
    
    if not fiscal_note_files:
        raise FileNotFoundError(f"No fiscal note JSON files found in {fiscal_notes_dir}")
    
    print(f"🔄 Processing {len(fiscal_note_files)} fiscal notes...")
    
    for i, fiscal_note_file in enumerate(fiscal_note_files):
        print(f"📝 Processing fiscal note {i+1}/{len(fiscal_note_files)}: {os.path.basename(fiscal_note_file)}")
        
        try:
            # Process the fiscal note
            enhanced_fiscal_note = process_fiscal_note_with_chunks(fiscal_note_file, documents_dir)
            
            # Save enhanced fiscal note
            output_file = os.path.join(enhanced_dir, os.path.basename(fiscal_note_file))
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(enhanced_fiscal_note, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Enhanced fiscal note saved: {os.path.basename(output_file)}")
            
        except Exception as e:
            print(f"❌ Error processing {os.path.basename(fiscal_note_file)}: {e}")
            continue
    
    print(f"✅ All fiscal notes processed and saved to: {enhanced_dir}")
    return enhanced_dir

def main():
    """
    Main function to process fiscal notes with chunk references.
    """
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python step6_add_chunk_references.py <fiscal_notes_dir> <documents_dir>")
        print("Example: python step6_add_chunk_references.py ./fiscal_notes ./documents")
        sys.exit(1)
    
    fiscal_notes_dir = sys.argv[1]
    documents_dir = sys.argv[2]
    
    if not os.path.exists(fiscal_notes_dir):
        print(f"❌ Fiscal notes directory not found: {fiscal_notes_dir}")
        sys.exit(1)
    
    if not os.path.exists(documents_dir):
        print(f"❌ Documents directory not found: {documents_dir}")
        sys.exit(1)
    
    try:
        enhanced_dir = add_chunk_references_to_fiscal_notes(fiscal_notes_dir, documents_dir)
        print(f"🎉 Successfully enhanced fiscal notes with chunk references!")
        print(f"📁 Output directory: {enhanced_dir}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

__all__ = ["add_chunk_references_to_fiscal_notes", "process_fiscal_note_with_chunks", "chunk_text_by_tokens"]
