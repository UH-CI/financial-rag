import json
import os
import glob
from pydantic import BaseModel, create_model
from tenacity import retry, stop_after_attempt, wait_exponential
import time
from datetime import datetime
from google import genai
from google.genai import types

from dotenv import load_dotenv
load_dotenv()

class FiscalNoteModel(BaseModel):
    overview: str
    appropriations:str
    assumptions_and_methodology:str
    agency_impact:str
    economic_impact:str 
    policy_impact: str
    revenue_sources: str 
    six_year_fiscal_implications: str
    operating_revenue_impact: str
    capital_expenditure_impact: str
    fiscal_implications_after_6_years: str
    updates_from_previous_fiscal_note: str


# Example LLM query function (replace with your actual model)
def query_gemini(prompt: str, chunks=None, numbers_data=None):
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    
    # Configure generation with JSON schema and grounding enabled
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=FiscalNoteModel,
        # Enable grounding and citation features
        system_instruction="You are a fiscal note analyst. Use EXACT WORDING from the provided document chunks whenever possible. Quote directly from the source material. When writing fiscal notes, preserve the original language and phrasing from the documents to maintain accuracy and authenticity."
    )
    
    # Create chunked prompt if we have chunks
    if chunks:
        final_prompt = create_chunked_prompt(prompt, chunks, numbers_data)
    else:
        final_prompt = prompt
    
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=final_prompt,
        config=config
    )
    
    # Parse the JSON response
    parsed = None
    if response.text:
        try:
            parsed_dict = json.loads(response.text)
            parsed = FiscalNoteModel(**parsed_dict)
        except Exception as e:
            print(f"Warning: Could not parse response as FiscalNoteModel: {e}")
    
    return response.text, parsed, response, chunks

def chunk_documents(document_sources, chunk_size=250, overlap=20):
    """
    Chunk documents into smaller pieces with overlap for better attribution.
    Each chunk gets a unique index and tracks its source document.
    """
    chunks = []
    chunk_index = 0
    
    for doc_source in document_sources:
        doc_name = doc_source['name']
        doc_text = doc_source['text']
        
        # Simple word-based chunking (approximating tokens)
        words = doc_text.split()
        
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_text = ' '.join(chunk_words)
            
            chunks.append({
                "chunk_id": chunk_index,
                "document_name": doc_name,
                "chunk_text": chunk_text,
                "start_word": start,
                "end_word": end,
                "word_count": len(chunk_words)
            })
            
            chunk_index += 1
            
            # Move start position with overlap
            if end >= len(words):
                break
            start = end - overlap
    
    return chunks

def create_chunked_prompt(base_prompt, chunks, numbers_data):
    """
    Create a prompt that includes chunked documents and emphasizes exact wording.
    """
    prompt = base_prompt + "\n\n"
    prompt += "CRITICAL WRITING REQUIREMENTS:\n"
    prompt += "1. Use EXACT WORDING and PHRASES from the document chunks whenever possible\n"
    prompt += "2. Quote directly from the source material to maintain accuracy\n"
    prompt += "3. Preserve the original language and terminology from the documents\n"
    prompt += "4. When mentioning dollar amounts, use the exact figures as they appear in the source\n"
    prompt += "5. Maintain the authentic voice and style of the original documents\n\n"
    
    # Add chunk information
    prompt += "=== DOCUMENT CHUNKS FOR REFERENCE ===\n"
    for chunk in chunks:
        prompt += f"CHUNK {chunk['chunk_id']} (from {chunk['document_name']}):\n"
        prompt += f"{chunk['chunk_text']}\n\n"
    
    # Add numbers information
    if numbers_data:
        prompt += "=== FINANCIAL NUMBERS AVAILABLE ===\n"
        for i, number_item in enumerate(numbers_data):
            prompt += f"NUMBER {i}: ${number_item['number']:,.2f} from {number_item['filename']}\n"
            prompt += f"Context: {number_item['text'][:200]}...\n\n"
    
    prompt += "WRITING STRATEGY:\n"
    prompt += "- Quote exact phrases and sentences from the chunks when applicable\n"
    prompt += "- Use the precise dollar amounts as they appear in the source documents\n"
    prompt += "- Maintain consistency with the original document language\n"
    prompt += "- Focus on accuracy and authenticity over paraphrasing\n\n"
    
    return prompt

def analyze_sentence_chunk_attribution(response_text, chunks, numbers_data=None):
    """
    Post-process attribution by analyzing document citations, numbers, and semantic similarity.
    """
    import re
    import string
    from collections import Counter
    
    # Split response into sentences and merge short fragments
    raw_sentences = re.split(r'[.!?]+', response_text)
    raw_sentences = [s.strip() for s in raw_sentences if s.strip()]
    
    # Merge sentences that are too short (likely fragments)
    sentences = []
    current_sentence = ""
    
    for sentence in raw_sentences:
        if len(sentence) < 7:  # Too short to be a complete sentence
            current_sentence += sentence + ". "
        else:
            if current_sentence:
                sentences.append((current_sentence + sentence).strip())
                current_sentence = ""
            else:
                sentences.append(sentence)
    
    # Add any remaining current_sentence
    if current_sentence:
        sentences.append(current_sentence.strip())
    
    attribution_metadata = {
        "sentence_attributions": [],
        "chunk_usage_stats": {},
        "attribution_method_stats": {
            "document_citation_based": 0,
            "number_based": 0,
            "word_frequency_based": 0,
            "semantic_similarity": 0,
            "fallback": 0,
            "no_attribution": 0
        }
    }
    
    # Initialize chunk usage stats
    for chunk in chunks:
        attribution_metadata["chunk_usage_stats"][chunk['chunk_id']] = {
            "usage_count": 0,
            "document_name": chunk['document_name'],
            "attribution_reasons": []
        }
    
    # Also initialize stats for number-based attributions
    if numbers_data:
        for number_item in numbers_data:
            number_id = f"NUMBER_{number_item['number']}"
            if number_id not in attribution_metadata["chunk_usage_stats"]:
                attribution_metadata["chunk_usage_stats"][number_id] = {
                    "usage_count": 0,
                    "document_name": number_item['filename'],
                    "attribution_reasons": []
                }
    
    for sentence in sentences:
        if not sentence:
            continue
        
        # Extract document citation from parentheses at end of sentence
        cited_document = extract_document_citation(sentence)
        sentence_without_citation = remove_document_citation(sentence) if cited_document else sentence
        
        # Extract numbers from sentence
        numbers_in_sentence = extract_numbers_from_text(sentence_without_citation, numbers_data)
        
        best_chunk_id = None
        attribution_method = "no_attribution"
        attribution_score = 0
        attribution_reason = ""
        
        # Priority 1: Document citation-based attribution
        if cited_document:
            best_chunk_id, attribution_score, attribution_reason = find_best_chunk_by_document_citation(
                sentence_without_citation, cited_document, chunks, numbers_data, numbers_in_sentence
            )
            if best_chunk_id:
                attribution_method = "document_citation_based"
        
        # Priority 2: Number-based attribution (if no document citation)
        elif numbers_in_sentence:
            best_chunk_id, attribution_score, attribution_reason = find_best_chunk_by_numbers(
                sentence_without_citation, numbers_in_sentence, numbers_data
            )
            if best_chunk_id:
                attribution_method = "number_based"
        
        # Priority 3: General chunk matching
        if not best_chunk_id:
            best_chunk_id, word_score = find_best_chunk_by_word_frequency(sentence_without_citation, chunks)
            if best_chunk_id is not None and word_score > 0:
                attribution_method = "word_frequency_based"
                attribution_score = word_score
                attribution_reason = f"Word frequency match score: {word_score:.3f}"
            elif best_chunk_id is not None:
                # Semantic similarity fallback
                best_chunk_id, semantic_score = find_best_chunk_by_semantic_similarity(sentence_without_citation, chunks)
                if best_chunk_id and semantic_score > 0:
                    attribution_method = "semantic_similarity"
                    attribution_score = semantic_score
                    attribution_reason = f"Semantic similarity score: {semantic_score:.3f}"
        
        # Final fallback for substantial sentences
        if not best_chunk_id and len(sentence_without_citation.split()) >= 3 and chunks:
            best_chunk_id = chunks[0]['chunk_id']
            attribution_method = "fallback"
            attribution_score = 0.1
            attribution_reason = "Fallback attribution (no clear match found)"
        
        # Record attribution
        sentence_attribution = {
            "sentence": sentence,
            "attributed_chunk_id": best_chunk_id,
            "attribution_method": attribution_method,
            "attribution_score": attribution_score,
            "attribution_reason": attribution_reason,
            "numbers_found": numbers_in_sentence
        }
        
        attribution_metadata["sentence_attributions"].append(sentence_attribution)
        attribution_metadata["attribution_method_stats"][attribution_method] += 1
        
        # Update chunk usage stats
        if best_chunk_id is not None:
            # Ensure the chunk_id exists in stats (for NUMBER_ IDs)
            if best_chunk_id not in attribution_metadata["chunk_usage_stats"]:
                if best_chunk_id.startswith("NUMBER_"):
                    # Extract number from ID and find corresponding entry
                    number_str = best_chunk_id.replace("NUMBER_", "")
                    try:
                        number = float(number_str)
                        # Find the document name for this number
                        doc_name = "Unknown"
                        for number_item in numbers_data or []:
                            if abs(number_item['number'] - number) < 0.01:
                                doc_name = number_item['filename']
                                break
                        
                        attribution_metadata["chunk_usage_stats"][best_chunk_id] = {
                            "usage_count": 0,
                            "document_name": doc_name,
                            "attribution_reasons": []
                        }
                    except ValueError:
                        pass
            
            if best_chunk_id in attribution_metadata["chunk_usage_stats"]:
                attribution_metadata["chunk_usage_stats"][best_chunk_id]["usage_count"] += 1
                attribution_metadata["chunk_usage_stats"][best_chunk_id]["attribution_reasons"].append(attribution_reason)
    
    return attribution_metadata

def extract_numbers_from_text(text, numbers_data=None, processed_documents=None):
    """Extract dollar amounts and numbers from text."""
    import re
    
    numbers = []
    
    # Find dollar amounts like $1,000, $1000, $20, etc.
    dollar_matches = re.findall(r'\$[\d,]+(?:\.\d+)?', text)
    for match in dollar_matches:
        # Convert to float
        number_str = match.replace('$', '').replace(',', '')
        try:
            numbers.append(float(number_str))
        except ValueError:
            pass
    
    # Find standalone numbers (removed the >= 10 filter)
    number_matches = re.findall(r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b', text)
    for match in number_matches:
        number_str = match.replace(',', '')
        try:
            number = float(number_str)
            numbers.append(number)
        except ValueError:
            pass
    
    return list(set(numbers))  # Remove duplicates

def calculate_word_frequency_match(sentence, reference_text):
    """Calculate word frequency match between sentence and reference text."""
    from collections import Counter
    
    sentence_words = preprocess_text_for_matching(sentence)
    reference_words = preprocess_text_for_matching(reference_text)
    
    sentence_counter = Counter(sentence_words)
    reference_counter = Counter(reference_words)
    
    # Calculate overlap score
    common_words = sentence_counter & reference_counter
    if not common_words:
        return 0
    
    # Score based on number of matching words weighted by frequency
    score = sum(min(sentence_counter[word], reference_counter[word]) for word in common_words)
    
    # Normalize by sentence length
    normalized_score = score / len(sentence_words) if sentence_words else 0
    
    return normalized_score

def extract_document_citation(sentence):
    """Extract document name from parentheses anywhere in sentence."""
    import re
    # Look for pattern like (HB727_HD1_TESTIMONY_JDC_03-19-25_) anywhere in sentence
    # Find all citations and return the most common one
    citations = re.findall(r'\(([^)]+)\)', sentence)
    
    if not citations:
        return None
    
    # Filter to only document-like citations (contain letters, numbers, underscores)
    doc_citations = []
    for citation in citations:
        if re.match(r'^[A-Za-z0-9_.-]+$', citation.strip()):
            doc_citations.append(citation.strip())
    
    if doc_citations:
        # Return the most frequent citation (in case of multiple)
        from collections import Counter
        most_common = Counter(doc_citations).most_common(1)
        return most_common[0][0]
    
    return None

def remove_document_citation(sentence):
    """Remove all document citations from sentence."""
    import re
    # Remove all patterns like (HB727_HD1_TESTIMONY_JDC_03-19-25_) from anywhere in sentence
    # Only remove document-like citations (letters, numbers, underscores)
    def is_doc_citation(match):
        citation = match.group(1)
        return re.match(r'^[A-Za-z0-9_.-]+$', citation.strip()) is not None
    
    # Find all parenthetical expressions
    result = sentence
    while True:
        match = re.search(r'\s*\(([^)]+)\)\s*', result)
        if not match:
            break
        if is_doc_citation(match):
            # Remove this citation
            result = result[:match.start()] + ' ' + result[match.end():]
            result = re.sub(r'\s+', ' ', result).strip()  # Clean up extra spaces
        else:
            # Skip non-document citations, move past this match
            result = result[:match.start()] + '___SKIP___' + result[match.start():]
            break
    
    # Restore any non-document citations we skipped
    result = result.replace('___SKIP___', '')
    return result.strip()

def find_best_chunk_by_document_citation(sentence, cited_document, chunks, numbers_data, numbers_in_sentence):
    """Find best chunk using document citation, numbers, and similarity."""
    
    # First, try number-based attribution within the cited document
    if numbers_in_sentence and numbers_data:
        best_chunk_id, score, reason = find_best_chunk_by_numbers_in_document(
            sentence, numbers_in_sentence, numbers_data, cited_document
        )
        if best_chunk_id:
            return best_chunk_id, score, reason
    
    # Filter chunks to only those from the cited document
    document_chunks = []
    for chunk in chunks:
        # Check if chunk is from the cited document (flexible matching)
        if is_chunk_from_document(chunk, cited_document):
            document_chunks.append(chunk)
    
    if not document_chunks:
        return None, 0, f"No chunks found for document: {cited_document}"
    
    # Try word frequency matching within document chunks
    best_chunk_id, word_score = find_best_chunk_by_word_frequency(sentence, document_chunks)
    if best_chunk_id and word_score > 0:
        chunk_info = next(c for c in document_chunks if c['chunk_id'] == best_chunk_id)
        return best_chunk_id, word_score, f"Document citation + word frequency: {cited_document} (score: {word_score:.3f})"
    
    # Fallback to semantic similarity within document chunks
    best_chunk_id, semantic_score = find_best_chunk_by_semantic_similarity(sentence, document_chunks)
    if best_chunk_id and semantic_score > 0:
        return best_chunk_id, semantic_score, f"Document citation + semantic similarity: {cited_document} (score: {semantic_score:.3f})"
    
    # Final fallback: use first chunk from document
    if document_chunks:
        return document_chunks[0]['chunk_id'], 0.1, f"Document citation fallback: {cited_document}"
    
    return None, 0, f"No attribution found for document: {cited_document}"

def find_best_chunk_by_numbers_in_document(sentence, numbers_in_sentence, numbers_data, cited_document):
    """Find best number attribution within a specific document."""
    
    number_attributions = []
    
    for number in numbers_in_sentence:
        # Find entries with this number from the cited document
        matching_entries = []
        for number_item in numbers_data:
            if (abs(number_item['number'] - number) < 0.01 and 
                is_filename_match(number_item['filename'], cited_document)):
                matching_entries.append(number_item)
        
        if matching_entries:
            # Find best word frequency match
            best_entry = None
            best_score = 0
            
            for entry in matching_entries:
                word_score = calculate_word_frequency_match(sentence, entry['text'])
                if word_score > best_score:
                    best_score = word_score
                    best_entry = entry
            
            # If no word matches, try semantic similarity
            if best_score == 0 and matching_entries:
                for entry in matching_entries:
                    semantic_score = calculate_semantic_similarity(sentence, entry['text'])
                    if semantic_score > best_score:
                        best_score = semantic_score
                        best_entry = entry
            
            if best_entry:
                number_attributions.append({
                    'number': number,
                    'entry': best_entry,
                    'score': best_score
                })
    
    if number_attributions:
        best_attribution = max(number_attributions, key=lambda x: x['score'])
        chunk_id = f"NUMBER_{best_attribution['number']}"
        reason = f"Number ${best_attribution['number']:,.0f} in {cited_document} (score: {best_attribution['score']:.3f})"
        return chunk_id, best_attribution['score'], reason
    
    return None, 0, ""

def find_best_chunk_by_numbers(sentence, numbers_in_sentence, numbers_data):
    """Find best chunk using numbers (without document constraint)."""
    
    number_attributions = []
    
    for number in numbers_in_sentence:
        matching_entries = []
        for number_item in numbers_data:
            if abs(number_item['number'] - number) < 0.01:
                matching_entries.append(number_item)
        
        if matching_entries:
            best_entry = None
            best_score = 0
            
            # Try word frequency first
            for entry in matching_entries:
                word_score = calculate_word_frequency_match(sentence, entry['text'])
                if word_score > best_score:
                    best_score = word_score
                    best_entry = entry
            
            # Fallback to semantic similarity
            if best_score == 0:
                for entry in matching_entries:
                    semantic_score = calculate_semantic_similarity(sentence, entry['text'])
                    if semantic_score > best_score:
                        best_score = semantic_score
                        best_entry = entry
            
            if best_entry:
                number_attributions.append({
                    'number': number,
                    'entry': best_entry,
                    'score': best_score
                })
    
    if number_attributions:
        best_attribution = max(number_attributions, key=lambda x: x['score'])
        # Use integer format for chunk_id to match viewer expectations
        number_value = best_attribution['number']
        if number_value == int(number_value):
            chunk_id = f"NUMBER_{int(number_value)}"
        else:
            chunk_id = f"NUMBER_{number_value}"
        reason = f"Number ${best_attribution['number']:,.0f} from {best_attribution['entry']['filename']} (score: {best_attribution['score']:.3f})"
        return chunk_id, best_attribution['score'], reason
    
    return None, 0, ""

def find_best_chunk_by_semantic_similarity(sentence, chunks):
    """Find chunk with best semantic similarity to sentence."""
    # Simple semantic similarity using word overlap and position
    best_chunk_id = None
    best_score = 0
    
    sentence_words = set(preprocess_text_for_matching(sentence))
    
    for chunk in chunks:
        chunk_words = set(preprocess_text_for_matching(chunk['chunk_text']))
        
        # Calculate Jaccard similarity
        intersection = sentence_words & chunk_words
        union = sentence_words | chunk_words
        
        if union:
            similarity = len(intersection) / len(union)
            if similarity > best_score:
                best_score = similarity
                best_chunk_id = chunk['chunk_id']
    
    return best_chunk_id, best_score

def calculate_semantic_similarity(text1, text2):
    """Calculate semantic similarity between two texts."""
    # Simple implementation using word overlap
    words1 = set(preprocess_text_for_matching(text1))
    words2 = set(preprocess_text_for_matching(text2))
    
    intersection = words1 & words2
    union = words1 | words2
    
    if union:
        return len(intersection) / len(union)
    return 0

def is_chunk_from_document(chunk, cited_document):
    """Check if chunk is from the cited document."""
    chunk_doc = chunk.get('document_name', '')
    return is_filename_match(chunk_doc, cited_document)

def is_filename_match(filename, cited_document):
    """Check if filename matches cited document (flexible matching)."""
    # Remove extensions and normalize
    filename_clean = filename.replace('.PDF.txt', '').replace('.HTM.txt', '').replace('.htm.txt', '')
    cited_clean = cited_document.replace('.PDF.txt', '').replace('.HTM.txt', '').replace('.htm.txt', '')
    
    # Check for exact match or if one contains the other
    return (filename_clean == cited_clean or 
            cited_clean in filename_clean or 
            filename_clean in cited_clean)

def calculate_number_context_match(sentence, number, numbers_data, chunk):
    """Calculate word frequency match between sentence and number context from numbers_data."""
    if not numbers_data:
        return 0.5  # Default score if no numbers_data
    
    from collections import Counter
    
    # Find the number context from numbers_data
    number_context = ""
    for number_item in numbers_data:
        if abs(number_item['number'] - number) < 0.01:  # Match the number
            number_context = number_item['text']
            break
    
    if not number_context:
        return 0.5  # Default score if no context found
    
    # Calculate word frequency match between sentence and number context
    sentence_words = preprocess_text_for_matching(sentence)
    context_words = preprocess_text_for_matching(number_context)
    chunk_words = preprocess_text_for_matching(chunk['chunk_text'])
    
    sentence_counter = Counter(sentence_words)
    context_counter = Counter(context_words)
    chunk_counter = Counter(chunk_words)
    
    # Score based on overlap between sentence and both context and chunk
    context_overlap = sentence_counter & context_counter
    chunk_overlap = sentence_counter & chunk_counter
    
    context_score = sum(min(sentence_counter[word], context_counter[word]) for word in context_overlap)
    chunk_score = sum(min(sentence_counter[word], chunk_counter[word]) for word in chunk_overlap)
    
    # Combine scores (weighted toward chunk content)
    total_score = (chunk_score * 0.7) + (context_score * 0.3)
    
    # Normalize by sentence length
    normalized_score = total_score / len(sentence_words) if sentence_words else 0
    
    return normalized_score

def contains_number(text, target_number):
    """Check if text contains the target number in any format."""
    import re
    
    # Check for exact dollar format
    dollar_formats = [
        f"${target_number:,.0f}",
        f"${int(target_number)}",
        f"$ {target_number:,.0f}",
        f"$ {int(target_number)}"
    ]
    
    for format_str in dollar_formats:
        if format_str in text:
            return True
    
    # Check for number without dollar sign
    number_formats = [
        f"{target_number:,.0f}",
        f"{int(target_number)}",
        str(int(target_number))
    ]
    
    for format_str in number_formats:
        if re.search(r'\b' + re.escape(format_str) + r'\b', text):
            return True
    
    return False

def find_best_chunk_by_word_frequency(sentence, chunks):
    """Find the chunk with the highest word frequency match to the sentence."""
    import string
    from collections import Counter
    
    # Preprocess sentence
    sentence_words = preprocess_text_for_matching(sentence)
    sentence_counter = Counter(sentence_words)
    
    best_chunk_id = None
    best_score = 0
    
    for chunk in chunks:
        chunk_words = preprocess_text_for_matching(chunk['chunk_text'])
        chunk_counter = Counter(chunk_words)
        
        # Calculate word overlap score
        common_words = sentence_counter & chunk_counter
        if common_words:
            # Score based on number of matching words weighted by frequency
            score = sum(min(sentence_counter[word], chunk_counter[word]) for word in common_words)
            # Normalize by sentence length
            normalized_score = score / len(sentence_words) if sentence_words else 0
            
            if normalized_score > best_score:
                best_score = normalized_score
                best_chunk_id = chunk['chunk_id']
    
    return best_chunk_id, best_score

def preprocess_text_for_matching(text):
    """Preprocess text for word frequency matching."""
    import string
    import re
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove punctuation except dollar signs and commas in numbers
    text = re.sub(r'[^\w\s$,]', ' ', text)
    
    # Split into words
    words = text.split()
    
    # Filter out common stop words and very short words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'this', 'that', 'these', 'those'}
    
    filtered_words = [word for word in words if len(word) > 2 and word not in stop_words]
    
    return filtered_words

def extract_response_metadata(response):
    """
    Extract metadata from Gemini response including citation information,
    grounding attributions, and other metadata that shows which chunks
    contributed to the generated content.
    """
    metadata = {
        "response_text": getattr(response, 'text', None),
        "prompt_feedback": None,
        "usage_metadata": None,
        "candidates": []
    }
    
    # Extract prompt feedback if available
    if hasattr(response, 'prompt_feedback'):
        feedback = response.prompt_feedback
        metadata["prompt_feedback"] = {
            "block_reason": getattr(feedback, 'block_reason', None),
            "safety_ratings": []
        }
        if hasattr(feedback, 'safety_ratings') and feedback.safety_ratings:
            for rating in feedback.safety_ratings:
                metadata["prompt_feedback"]["safety_ratings"].append({
                    "category": str(getattr(rating, 'category', None)),
                    "probability": str(getattr(rating, 'probability', None))
                })
    
    # Extract usage metadata if available
    if hasattr(response, 'usage_metadata'):
        usage = response.usage_metadata
        metadata["usage_metadata"] = {
            "prompt_token_count": getattr(usage, 'prompt_token_count', None),
            "candidates_token_count": getattr(usage, 'candidates_token_count', None),
            "total_token_count": getattr(usage, 'total_token_count', None)
        }
    
    # Extract candidate information
    if hasattr(response, 'candidates'):
        for i, candidate in enumerate(response.candidates):
            candidate_info = {
                "index": i,
                "finish_reason": str(getattr(candidate, 'finish_reason', None)),
                "content": None,
                "citation_metadata": None,
                "safety_ratings": []
            }
            
            # Extract content
            if hasattr(candidate, 'content') and candidate.content:
                content = candidate.content
                candidate_info["content"] = {
                    "role": getattr(content, 'role', None),
                    "parts": []
                }
                if hasattr(content, 'parts'):
                    for part in content.parts:
                        part_info = {
                            "text": getattr(part, 'text', None)
                        }
                        candidate_info["content"]["parts"].append(part_info)
            
            # Extract citation metadata
            if hasattr(candidate, 'citation_metadata') and candidate.citation_metadata:
                citations = []
                if hasattr(candidate.citation_metadata, 'citation_sources'):
                    for citation in candidate.citation_metadata.citation_sources:
                        citations.append({
                            "start_index": getattr(citation, 'start_index', None),
                            "end_index": getattr(citation, 'end_index', None),
                            "uri": getattr(citation, 'uri', None),
                            "license": getattr(citation, 'license', None)
                        })
                candidate_info["citation_metadata"] = {"citations": citations}
            
            # Extract grounding metadata (this is key for document attribution)
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                grounding_meta = {}
                
                # Extract grounding chunks
                if hasattr(candidate.grounding_metadata, 'grounding_chunks') and candidate.grounding_metadata.grounding_chunks:
                    chunks = []
                    for chunk in candidate.grounding_metadata.grounding_chunks:
                        chunk_info = {
                            "chunk_id": getattr(chunk, 'chunk_id', None),
                            "content": getattr(chunk, 'content', None)
                        }
                        if hasattr(chunk, 'retrieved_context') and chunk.retrieved_context:
                            chunk_info["retrieved_context"] = {
                                "uri": getattr(chunk.retrieved_context, 'uri', None),
                                "title": getattr(chunk.retrieved_context, 'title', None),
                                "text": getattr(chunk.retrieved_context, 'text', None)
                            }
                        chunks.append(chunk_info)
                    grounding_meta["grounding_chunks"] = chunks
                
                # Extract grounding support
                if hasattr(candidate.grounding_metadata, 'grounding_support') and candidate.grounding_metadata.grounding_support:
                    grounding_meta["grounding_support"] = {
                        "support_id": getattr(candidate.grounding_metadata.grounding_support, 'support_id', None),
                        "grounding_chunk_indices": list(getattr(candidate.grounding_metadata.grounding_support, 'grounding_chunk_indices', [])),
                        "confidence_scores": list(getattr(candidate.grounding_metadata.grounding_support, 'confidence_scores', []))
                    }
                
                # Extract search entry point
                if hasattr(candidate.grounding_metadata, 'search_entry_point'):
                    grounding_meta["search_entry_point"] = {
                        "rendered_content": getattr(candidate.grounding_metadata.search_entry_point, 'rendered_content', None)
                    }
                
                candidate_info["grounding_metadata"] = grounding_meta
            
            # Extract safety ratings
            if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                for rating in candidate.safety_ratings:
                    candidate_info["safety_ratings"].append({
                        "category": str(getattr(rating, 'category', None)),
                        "probability": str(getattr(rating, 'probability', None)),
                        "blocked": getattr(rating, 'blocked', None)
                    })
            
            metadata["candidates"].append(candidate_info)
    
    return metadata

# Property prompts (from your input)
PROPERTY_PROMPTS = { 
    "overview": { "prompt": "Using the provided legislative documents, statutes, and testimonies, write a clear summary describing the purpose, scope, and key components of the proposed measure or bill, including any pilot or permanent programs, reporting requirements, and sunset clauses. This should be around 3 sentences.", "description": "General overview and summary of the measure" }, 
    "appropriations": { "prompt": "Based on budgetary data and legislative appropriations, detail the funding allocated for the program or measure, including fiscal years, amounts, intended uses such as staffing, training, contracts, technology, etc... This should be around 3 sentences.", "description": "Funding allocation and appropriations details" }, 
    "assumptions_and_methodology": { "prompt": "Explain the assumptions, cost estimation methods, and data sources used to calculate the financial projections for this program or measure, referencing comparable programs or historical budgets where applicable. This should be around 3 sentences.", "description": "Cost estimation methodology and assumptions" }, 
    "agency_impact": { "prompt": "Describe the anticipated operational, administrative, and budgetary impact of the program or measure on the relevant government agency or department, including supervision, staffing, and resource allocation. This should be around 3 sentences.", "description": "Impact on government agencies and departments" }, 
    "economic_impact": { "prompt": "Summarize the expected economic effects of the program or measure, such as cost savings, potential reductions in related expenditures, benefits to the community, and any relevant performance or participation statistics. This should be around 3 sentences.", "description": "Economic effects and community benefits" }, 
    "policy_impact": { "prompt": "Analyze the policy implications of the measure, including how it modifies existing laws or programs, its role within broader legislative strategies, and its potential effects on state or local governance. This should be around 3 sentences.", "description": "Policy implications and legislative analysis" }, 
    "revenue_sources": { "prompt": "Identify and describe the funding sources that will support the program or measure, such as general funds, grants, fees, or other revenue streams, based on the provided fiscal documents. This should be around 3 sentences.", "description": "Funding sources and revenue streams" }, 
    "six_year_fiscal_implications": { "prompt": "Provide a multi-year fiscal outlook (e.g., six years) for the program or measure, projecting costs, staffing changes, recurring expenses, and assumptions about program expansion or permanence using available budget and workload data. This should be around 10 sentences.", "description": "Six-year fiscal projections and outlook" }, 
    "operating_revenue_impact": { "prompt": "Describe any anticipated impacts on operating revenues resulting from the program or measure, including increases, decreases, or changes in revenue streams. This should be around 3 sentences.", "description": "Operating revenue impacts" }, 
    "capital_expenditure_impact": { "prompt": "Outline any expected capital expenditures related to the program or measure, such as investments in facilities, equipment, or technology infrastructure, based on capital budgets or agency plans. This should be around 3 sentences.", "description": "Capital expenditure requirements" }, 
    "fiscal_implications_after_6_years": { "prompt": "Summarize the ongoing fiscal obligations after the initial multi-year period for the program or measure, including annual operating costs, expected number of program sites or units, and the sustainability of funding. This should be around 3 sentences.", "description": "Long-term fiscal obligations beyond six years" },
    "updates_from_previous_fiscal_note" : {"prompt": "If you are given a previous fisacl not. Please summarize the MAIN POINTS that are different from the previous fiscal note and the new fisacl note."}
    }

def generate_fiscal_note_for_context(context_text, numbers_data=None, previous_note=None, document_sources=None):
    """
    Generate a full fiscal note (all properties at once) using PROPERTY_PROMPTS.
    If previous_note is provided, instruct the LLM to avoid repeating information.
    """
    # Build a combined instruction
    combined_prompt = "You are tasked with generating a fiscal note based on the context that you are given on a set of documents.\n"
    combined_prompt += "Extract the following information:\n\n"
    for key, prop in PROPERTY_PROMPTS.items():
        combined_prompt += f"- {key}: {prop['prompt']}\n"

    # Add specific instructions about using numbers
    combined_prompt += "\n**CRITICAL INSTRUCTIONS FOR FINANCIAL NUMBERS:**\n"
    combined_prompt += "1. EVERY financial number MUST be immediately followed by its source in parentheses\n"
    combined_prompt += "2. Use document-type-specific language when citing numbers:\n"
    combined_prompt += "   - For 'introduction' documents: 'The introduction allocates $X (filename)' or 'The bill appropriates $X (filename)'\n"
    combined_prompt += "   - For 'testimony' documents: 'The testimony requests $X (filename)' or 'Testimony indicates $X (filename)'\n"
    combined_prompt += "   - For 'committee_hearing' documents: 'The committee hearing determines $X (filename)' or 'It is decided in the committee hearing that $X (filename)'\n"
    combined_prompt += "   - For 'document' documents: 'The legislative document specifies $X (filename)'\n"
    combined_prompt += "3. Do NOT put citations at the end of sentences - put them immediately after each number\n"
    combined_prompt += "4. Do NOT make up or estimate numbers - only use numbers from the provided financial data\n"
    combined_prompt += "5. Be VERY SPECIFIC about what each dollar amount is for\n"
    combined_prompt += "6. Example: 'The introduction allocates $50,000 (HB123.HTM.txt) for staff training and testimony requests $25,000 (HB123_TESTIMONY_EDU.PDF.txt) for equipment.'\n\n"

    # Add numbers data if available
    if numbers_data:
        combined_prompt += "**FINANCIAL NUMBERS FOUND IN DOCUMENTS:**\n"
        for number_item in numbers_data:
            doc_type_desc = {
                'introduction': 'Bill introduction',
                'committee_hearing': 'Committee hearing',
                'testimony': 'Public testimony',
                'document': 'Legislative document'
            }.get(number_item.get('document_type', 'document'), 'Document')
            
            combined_prompt += f"- ${number_item['number']:,.2f} from {doc_type_desc} ({number_item['filename']})\n"
            combined_prompt += f"  Context: {number_item['text'][:200]}...\n\n"

    combined_prompt += f"\nContext:\n{context_text}\n"

    if previous_note:
        combined_prompt += (
            f"""
            You are generating a **new fiscal note** based on updated documents. 
Compare it to the previous fiscal note (shown below). Only include information that is **new or has changed**. 
If a section has no changes, leave it **blank**. 
Do **not repeat content** from the previous fiscal note.
Ensure that you use numbers according to the numbers.json file. Do not make up numbers.
Previous fiscal note:
            """
            f"{json.dumps(previous_note, ensure_ascii=False, indent=2)}"
            f"\nAccording to the previous fiscal note, focus on what has been discussed and the main points that have changed. Do not repeat the same content. The previous fiscal note should be very different in the new fiscal note. If no new information is needed, leave the section blank\n"
            
        )
    
    # Create chunks from document sources
    chunks = []
    if document_sources:
        chunks = chunk_documents(document_sources, chunk_size=50, overlap=10)
        print(f"📝 Created {len(chunks)} chunks from {len(document_sources)} documents")
    
    text, parsed, full_response, used_chunks = query_gemini(combined_prompt, chunks, numbers_data)
    
    # Extract metadata about chunk contributions
    response_metadata = extract_response_metadata(full_response)
    
    # Add our custom sentence-level chunk attribution analysis
    if text and chunks:
        sentence_attribution = analyze_sentence_chunk_attribution(text, chunks, numbers_data)
        response_metadata["sentence_attribution_analysis"] = sentence_attribution
        response_metadata["chunks_metadata"] = {
            "total_chunks": len(chunks),
            "chunk_details": chunks
        }
        # Include numbers data for the HTML viewer
        response_metadata["numbers_data"] = numbers_data

    # Convert to dict
    fiscal_note = {}
    if parsed:
        try:
            fiscal_note = parsed.dict()  # Pydantic v1
        except AttributeError:
            fiscal_note = parsed.model_dump()  # Pydantic v2

    return fiscal_note, combined_prompt, response_metadata

def generate_fiscal_notes_chronologically(documents, chronological_documents, output_dir, numbers_file_path):
    """
    Generate fiscal notes sequentially for a list of chronologically ordered documents.
    Each fiscal note only processes NEW documents since the last fiscal note generation.
    
    documents: list of dicts with {"name": ..., "text": ...} from retrieved documents
    chronological_documents: list of dicts with {"name": ..., "url": ...} from chronological JSON
    """
    os.makedirs(output_dir, exist_ok=True)
    previous_fiscal_note = None
    all_processed_documents = []  # Track ALL documents processed across all fiscal notes
    last_fiscal_note_index = -1  # Track which document index had the last fiscal note
    
    # Load all numbers data once
    all_numbers = []
    try:
        with open(numbers_file_path, "r") as f:
            all_numbers = json.load(f)
    except Exception as e:
        print(f"Warning: Could not load numbers data: {e}")
    
    # Create a mapping of document names to URLs for committee report detection
    doc_url_map = {doc['name']: doc['url'] for doc in chronological_documents}
    
    for i, doc in enumerate(documents, start=1):
        print(f"Processing document {i}/{len(documents)}: {doc['name']}, text: {doc['text'][:10]}")
        
        # Add this document to the list of all processed documents
        all_processed_documents.append(doc['name'])
        
        # Check if this document should generate a fiscal note:
        # 1. If it's the first document (bill introduction)
        # 2. If the URL contains "CommReports" (committee reports)
        should_generate = False
        if i == 1:  # First document (bill introduction)
            should_generate = True
            print(f"📋 Generating fiscal note for bill introduction: {doc['name']}")
        elif doc['name'] in doc_url_map and "CommReports" in doc_url_map[doc['name']]:
            should_generate = True
            print(f"📋 Generating fiscal note for committee report: {doc['name']}")
        
        if should_generate:
            # Get only NEW documents since the last fiscal note
            new_documents_since_last = documents[last_fiscal_note_index + 1:i]
            new_document_names = [d['name'] for d in new_documents_since_last]
            
            print(f"📋 Processing {len(new_documents_since_last)} NEW documents since last fiscal note:")
            for new_doc in new_documents_since_last:
                print(f"   - {new_doc['name']}")
            
            # Create context from ONLY the new documents
            new_context = ""
            for new_doc in new_documents_since_last:
                new_context += f"\n\n=== Document: {new_doc['name']} ===\n{new_doc['text']}"
            # Filter numbers data to only include NEW documents since last fiscal note
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
                    # Handle various patterns:
                    # - "HB727_.HTM.txt" matches "HB727"
                    # - "HB727_CD1_.HTM.txt" matches "HB727_CD1"
                    # - "HB727_SD1_.HTM.txt" matches "HB727_SD1"
                    
                    matched = False
                    
                    # Exact matches
                    if (number_doc_name == new_doc_name or 
                        number_doc_base == new_doc_name or
                        number_doc_name == new_doc_name + '.txt' or
                        number_doc_base == new_doc_name + '_.HTM'):
                        matched = True
                    
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
                    
                    if matched:
                        numbers_data.append(number_item)
                        print(f"📋 Matched number from {number_doc_name} to NEW doc {new_doc_name}")
                        break
            
            print(f"📊 Using {len(numbers_data)} numbers from {len(new_document_names)} NEW documents")
            print(f"🔍 NEW documents: {new_document_names}")
            if len(numbers_data) == 0 and len(all_numbers) > 0:
                print(f"🔍 Sample number filenames: {[item['filename'] for item in all_numbers[:3]]}")
                print(f"🔍 No matches found between NEW docs and number filenames")
            
            # Create document sources from ONLY the NEW documents
            document_sources = []
            for new_doc in new_documents_since_last:
                document_sources.append({
                    'name': new_doc['name'],
                    'text': new_doc['text'][:5000]  # Limit text length for better processing
                })
            
            # Generate fiscal note for the NEW context only
            fiscal_note, combined_prompt, response_metadata = generate_fiscal_note_for_context(
                new_context, 
                numbers_data=numbers_data, 
                previous_note=previous_fiscal_note,
                document_sources=document_sources
            )
            
            # Save fiscal note to a JSON file (filename = new document name)
            out_path = os.path.join(output_dir, f"{doc['name']}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(fiscal_note, f, ensure_ascii=False, indent=2)
            
            # Save metadata to a separate JSON file
            metadata_path = os.path.join(output_dir, f"{doc['name']}_metadata.json")
            metadata_output = {
                "document_name": doc['name'],
                "new_documents_processed": new_document_names.copy(),  # Only NEW documents
                "all_documents_processed_so_far": all_processed_documents.copy(),  # All documents up to this point
                "numbers_used": len(numbers_data),
                "prompt_length": len(combined_prompt),
                "response_metadata": response_metadata,
                "generation_timestamp": datetime.now().isoformat(),
                "generation_timestamp_unix": time.time()
            }
            
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata_output, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Fiscal note saved: {out_path}")
            print(f"✅ Metadata saved: {metadata_path}")
            
            # Update tracking variables for next iteration
            previous_fiscal_note = fiscal_note
            last_fiscal_note_index = i - 1  # Current document index (0-based)


def generate_fiscal_notes(documents_dir: str, numbers_file_path: str) -> str:
    """
    Takes a documents directory path and generates fiscal notes in chronological order.
    Reads the chronological JSON and processes the retrieved documents.
    Returns the path to the fiscal notes output directory.
    """
    # Find the chronological JSON file in the parent directory
    base_dir = os.path.dirname(documents_dir)
    chronological_files = glob.glob(os.path.join(base_dir, "*_chronological.json"))
    
    if not chronological_files:
        raise FileNotFoundError(f"No chronological JSON file found in {base_dir}")
    
    chronological_json_path = chronological_files[0]
    
    # Load chronological documents
    with open(chronological_json_path, 'r', encoding='utf-8') as f:
        documents_chronological = json.load(f)
    
    # Create fiscal notes output directory
    fiscal_notes_dir = os.path.join(base_dir, "fiscal_notes")
    os.makedirs(fiscal_notes_dir, exist_ok=True)
    
    # Load documents with text content
    documents_with_text = []
    
    for doc in documents_chronological:
        name = doc['name']
        # Look for any file that starts with the document name in the documents directory
        matches = glob.glob(os.path.join(documents_dir, f"{name}*"))
        if matches:
            # Take the first match
            txt_path = matches[0]
            with open(txt_path, "r", encoding="utf-8") as f:
                text = f.read()
            documents_with_text.append({"name": name, "text": text})
        else:
            print(f"⚠️ File not found for {name}")
    
    # Generate fiscal notes in chronological order
    generate_fiscal_notes_chronologically(documents_with_text, documents_chronological, fiscal_notes_dir, numbers_file_path)
    
    print(f"✅ Fiscal notes generated and saved to: {fiscal_notes_dir}")
    return fiscal_notes_dir


__all__ = ["generate_fiscal_notes"]
