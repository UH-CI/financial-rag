#!/usr/bin/env python3
"""
This script provides functions for chunking extracted PDF text using either
a simple sliding window method or an advanced AI-powered extraction method.
"""
import json
import logging
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

# --- Set up logger ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- LLM Placeholders ---
# NOTE: Replace these with your actual LLM client and logic.
# You might use libraries like 'openai', 'anthropic', 'transformers', etc.

def _call_llm_for_rewriting(prompt_to_rewrite: str) -> str:
    """
    Placeholder for calling an LLM to rewrite a user's prompt for better clarity and performance.
    """
    logger.info("Calling placeholder LLM to rewrite prompt...")
    # In a real implementation, you would send the prompt to an LLM
    # with a meta-prompt like: "Rewrite the following user request for an item
    # extraction task to be clearer and more effective for a large language model.
    # Return only the rewritten prompt."
    rewritten = f"REWRITTEN PROMPT: Extract structured items based on the following rules: {prompt_to_rewrite}"
    return rewritten

def _call_llm_for_extraction(prompt: str) -> List[Dict[str, Any]]:
    """
    Placeholder for calling an LLM to extract structured data based on a prompt.
    """
    logger.info("Calling placeholder LLM for data extraction...")
    # This function should parse the LLM's response, which is expected to be
    # a JSON string representing a list of extracted items.
    # Mock response for demonstration:
    mock_response = [
        {"extracted_item": "Statute 101.5", "text": "The law of placeholders...", "notes": "This is a mock example."},
        {"extracted_item": "Statute 101.6", "text": "Another law...", "notes": "This demonstrates few-shot learning context."}
    ]
    # In a real scenario, you'd handle potential parsing errors.
    return mock_response

# --- End LLM Placeholders ---


def _split_into_sentences(text: str) -> List[str]:
    """
    Splits text into sentences using regex patterns.
    Handles common sentence endings and abbreviations.
    """
    # Pattern to match sentence endings while avoiding common abbreviations
    sentence_pattern = r'(?<![A-Z][a-z]\.)|(?<![A-Z]\.)|(?<=\w[.!?])\s+(?=[A-Z])'
    
    # Split by the pattern and filter out empty strings
    sentences = [s.strip() for s in re.split(sentence_pattern, text) if s.strip()]
    
    # If no sentences found, return the original text as a single sentence
    if not sentences:
        return [text] if text.strip() else []
    
    return sentences


def _simple_chunker(text: str, chunk_size: int, overlap: int, use_sentence: bool = False) -> List[str]:
    """
    Splits a text into overlapping chunks using a sliding window.
    
    Args:
        text: The text to chunk
        chunk_size: Maximum size of each chunk in characters
        overlap: Number of characters to overlap between chunks
        use_sentence: If True, preserves sentence boundaries when possible
    """
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    
    if not use_sentence:
        # Original simple chunking logic
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start += (chunk_size - overlap)
        return chunks
    
    # Sentence-aware chunking
    sentences = _split_into_sentences(text)
    chunks = []
    current_chunk = ""
    
    i = 0
    while i < len(sentences):
        sentence = sentences[i]
        
        # If adding this sentence would exceed chunk_size and we have content
        if current_chunk and len(current_chunk) + len(sentence) + 1 > chunk_size:
            # Save current chunk
            chunks.append(current_chunk.strip())
            
            # Start new chunk with overlap if possible
            if overlap > 0 and chunks:
                # Find sentences to include for overlap
                overlap_text = ""
                temp_sentences = current_chunk.strip().split('. ')
                
                # Add sentences from the end until we reach overlap limit
                for j in range(len(temp_sentences) - 1, -1, -1):
                    test_overlap = '. '.join(temp_sentences[j:]) + ('. ' if j < len(temp_sentences) - 1 else '')
                    if len(test_overlap) <= overlap:
                        overlap_text = test_overlap
                        break
                
                current_chunk = overlap_text
            else:
                current_chunk = ""
        
        # Add sentence to current chunk
        if current_chunk:
            current_chunk += " " + sentence
        else:
            current_chunk = sentence
            
        i += 1
    
    # Add the last chunk if it has content
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


def chunk_document(
    input_json_path: str,
    output_json_path: str,
    chosen_methods: List[str],  # Required: list of property names to extract text from
    identifier: str,            # Required: property name to use as source identifier
    use_ai: bool = False,
    # AI-related parameters
    prompt_description: Optional[str] = None,
    previous_pages_to_include: int = 1, # N: Number of previous pages for context
    context_items_to_show: int = 2,     # J: Number of extracted items for few-shot examples
    rewrite_query: bool = False,
    # Non-AI (simple chunking) parameters
    chunk_size: int = 1000, # N: Character count for simple chunking
    overlap: int = 100,     # J: Character overlap for simple chunking
    use_sentence: bool = False, # Whether to preserve sentence boundaries in simple chunking
):
    """
    Chunks a document from an extracted text JSON using either simple or AI-powered methods.

    Args:
        input_json_path: Path to the input JSON file (from step1_text_extraction).
        output_json_path: Path to save the output chunked JSON file.
        chosen_methods: List of property names to extract text from (e.g., ['text'], ['pymupdf_extraction_text']).
        identifier: Property name to use as source identifier (e.g., 'url', 'filename').
        use_ai: If True, uses the AI-powered extraction method. Otherwise, uses the simple chunker.

        -- AI Parameters --
        prompt_description: The prompt explaining to the LLM how to extract items.
        previous_pages_to_include: How many previous pages' text to include as context.
        context_items_to_show: How many previously extracted items to show as few-shot examples.
        rewrite_query: If True, a preliminary LLM call is made to refine the prompt_description.

        -- Simple Chunker Parameters --
        chunk_size: Size of each chunk in characters.
        overlap: Number of characters to overlap between chunks.
        use_sentence: If True, preserves sentence boundaries when chunking (simple chunking only).
    """
    # --- Parameter Validation ---
    if use_ai:
        if not all([chosen_methods, prompt_description]):
            raise ValueError("For AI chunking, 'chosen_methods' and 'prompt_description' are required.")
    else:
        if not chosen_methods:
            raise ValueError("For simple chunking, 'chosen_methods' is required.")

    # --- Load and Parse Input JSON ---
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Assume the JSON structure is a list of pages/documents, each with various text extraction methods
    pages_data = data if isinstance(data, list) else [data]
    
    final_results = []

    if use_ai:
        logger.info("Starting AI-powered chunking...")
        effective_prompt = prompt_description
        if rewrite_query:
            logger.info("Rewriting user query with LLM...")
            effective_prompt = _call_llm_for_rewriting(prompt_description)
            logger.info(f"Using rewritten prompt: {effective_prompt}")
        
        for i, page in enumerate(pages_data):
            # Extract source identifier from current document
            page_source_identifier = "unknown_source"
            if identifier in page:
                page_source_identifier = page[identifier]
                # If it's a URL, extract a meaningful filename
                if identifier == 'url' and isinstance(page_source_identifier, str):
                    page_source_identifier = page_source_identifier.split('/')[-1] or page_source_identifier.split('/')[-2] or page_source_identifier
            
            # 1. Assemble context from previous pages
            context_start_index = max(0, i - previous_pages_to_include)
            context_pages = pages_data[context_start_index:i]
            previous_pages_text = "\n".join(
                "\n".join(p.get(method, "") for method in chosen_methods)
                for p in context_pages if any(p.get(method) for method in chosen_methods)
            )

            # 2. Assemble few-shot examples from previously extracted items
            examples_start_index = max(0, len(final_results) - context_items_to_show)
            few_shot_examples_json = json.dumps(final_results[examples_start_index:], indent=2)

            # 3. Get current page text
            current_page_text = "\n".join(page.get(method, "") for method in chosen_methods)
            if not current_page_text.strip():
                logger.info(f"Skipping page {page.get('page_number')} as it has no text in chosen methods.")
                continue

            # Escape raw text to prevent breaking the prompt structure or subsequent JSON parsing.
            # This handles backslashes and double quotes which can break JSON strings.
            safe_previous_pages_text = previous_pages_text.replace('\\', r'\\').replace('"', r'\"')
            safe_current_page_text = current_page_text.replace('\\', r'\\').replace('"', r'\"')

            # 4. Construct the final prompt
            full_prompt = (
                f"**Instructions:**\n{effective_prompt}\n\n"
                f"**Format Examples (previously extracted items):**\n{few_shot_examples_json}\n\n"
                f"**Context from Previous Pages:**\n{safe_previous_pages_text}\n\n"
                f"---\n"
                f"**Current Page Text to Process:**\n{safe_current_page_text}\n\n"
                f"---\n"
                f"Based on the instructions, extract items ONLY from the 'Current Page Text to Process'. "
                f"Return the items as a JSON array of objects. If no items are found, return an empty array []."
            )

            # 5. Call LLM and add metadata to results
            extracted_items = _call_llm_for_extraction(full_prompt)
            for item in extracted_items:
                item['source_identifier'] = page_source_identifier
                item['source_page'] = page.get('page_number', i)
            final_results.extend(extracted_items)

    else:
        logger.info("Starting simple sliding-window chunking...")
        
        # Process each document separately to maintain proper source identifiers
        chunk_id_counter = 0
        for page in pages_data:
            # Extract source identifier from current document
            page_source_identifier = "unknown_source"
            if identifier in page:
                page_source_identifier = page[identifier]
                # If it's a URL, extract a meaningful filename
                if identifier == 'url' and isinstance(page_source_identifier, str):
                    page_source_identifier = page_source_identifier.split('/')[-1] or page_source_identifier.split('/')[-2] or page_source_identifier
            
            # Get text from current document
            page_text = "\n".join(page.get(method, "") for method in chosen_methods)
            if not page_text.strip():
                continue
            
            # Chunk the current document's text
            text_chunks = _simple_chunker(page_text, chunk_size, overlap, use_sentence)
            
            # Structure the output with proper source identifier for each chunk
            chunking_method = "sentence_aware_chunking" if use_sentence else "simple_sliding_window"
            for chunk in text_chunks:
                final_results.append({
                    "chunk_id": chunk_id_counter,
                    "text": chunk,
                    "source_identifier": page_source_identifier,
                    "chunking_method": chunking_method,
                    "source_extraction_methods": chosen_methods,
                    "sentence_preserved": use_sentence,
                    "source_page": page.get('page_number', len(final_results))
                })
                chunk_id_counter += 1

    # --- Save Final Results ---
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, indent=2, ensure_ascii=False)
    
    # --- Create Metadata File ---
    metadata_path = output_json_path.replace('.json', '_metadata.json')
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "input_file": input_json_path,
        "output_file": output_json_path,
        "parameters": {
            "chosen_methods": chosen_methods,
            "identifier": identifier,
            "use_ai": use_ai,
            "chunk_size": chunk_size,
            "overlap": overlap,
            "use_sentence": use_sentence
        },
        "results": {
            "total_chunks": len(final_results),
            "source_identifier": identifier,
            "input_documents_count": len(pages_data)
        }
    }
    
    # Add AI-specific metadata if applicable
    if use_ai:
        metadata["parameters"].update({
            "prompt_description": prompt_description,
            "previous_pages_to_include": previous_pages_to_include,
            "context_items_to_show": context_items_to_show,
            "rewrite_query": rewrite_query
        })
        metadata["results"]["chunking_method"] = "ai_extraction"
    else:
        metadata["results"]["chunking_method"] = "sentence_aware_chunking" if use_sentence else "simple_sliding_window"
        
        # Calculate text statistics for simple chunking
        if final_results:
            chunk_lengths = [len(chunk["text"]) for chunk in final_results]
            metadata["results"]["text_statistics"] = {
                "min_chunk_length": min(chunk_lengths),
                "max_chunk_length": max(chunk_lengths),
                "avg_chunk_length": sum(chunk_lengths) / len(chunk_lengths),
                "total_characters": sum(chunk_lengths)
            }
    
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Chunking complete. Saved {len(final_results)} items to {output_json_path}")
    logger.info(f"Metadata saved to {metadata_path}")
    
    # Return the chunked results
    return final_results


# This basic setup allows the script to be used as a module.
# You could add argparse here to make it a CLI tool as well.
if __name__ == '__main__':
    # Example of how to run the function
    # The logger is already configured at the top level, so no need to reconfigure here.
    
    # Create a dummy input file for testing
    input_path = "../extracted_text/bills/filtered_documents.json"
    output_path = "../chunked_text/bills/bills_chunked.json"

    # # --- Example 1: Simple Chunker --- ## THIS IS BROKEN. DO NOT USE use_sentence
    # logger.info("--- Running Simple Chunker Example ---")
    # chunk_document(
    #     input_json_path=input_path,
    #     output_json_path=output_path,
    #     chosen_methods=['text'],  # Use 'text' field from your JSON
    #     identifier='url',         # Use 'url' field as source identifier
    #     use_ai=False,
    #     chunk_size=15000,
    #     overlap=500,
    #     use_sentence=True  # Enable sentence preservation
    # )
    # print(f"Simple chunking output saved to {output_path}")
    
    # --- Example 1b: Simple Chunker without sentence preservation ---
    logger.info("--- Running Simple Chunker Example (No Sentence Preservation) ---")
    output_path_no_sentence = output_path.replace('.json', '_no_sentence.json')
    chunk_document(
        input_json_path=input_path,
        output_json_path=output_path_no_sentence,
        chosen_methods=['text'],  # Use 'text' field from your JSON
        identifier='url',         # Use 'url' field as source identifier
        use_ai=False,
        chunk_size=15000,
        overlap=500,
        use_sentence=False  # Disable sentence preservation
    )
    print(f"Simple chunking (no sentence preservation) output saved to {output_path_no_sentence}")

    # # --- Example 2: AI Chunker ---
    # logger.info("--- Running AI Chunker Example ---")
    # chunk_document(
    #     input_json_path=dummy_input_path,
    #     output_json_path=dummy_output_path,
    #     use_ai=True,
    #     chosen_methods=['pymupdf_extraction_text', 'pdfplumber_extraction_text'],
    #     prompt_description="Extract each statute mentioned in the text. Each item should have 'statute_id' and 'description' fields."
    # )
    print(f"AI chunking output saved to {output_path}") 