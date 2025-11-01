"""
Chronological Number Tracking System

This script tracks numerical changes across bill lifecycle stages by:
1. Segmenting documents chronologically (ending segments at committee reports)
2. Extracting and enhancing numbers per segment using LLM
3. Using semantic similarity on summaries to match numbers across segments
4. Tracking number history and changes throughout the bill lifecycle

Features:
- Checkpoint/resume functionality
- Embedding caching for efficiency
- Configurable to run on single bill or all bills
"""

import json
import os
import math
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
import google.generativeai as genai
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)


def cosine_similarity_matrix(embeddings1: List[List[float]], embeddings2: List[List[float]]) -> List[List[float]]:
    """Calculate cosine similarity matrix between two sets of embeddings."""
    matrix = []
    for emb1 in embeddings1:
        row = []
        for emb2 in embeddings2:
            row.append(cosine_similarity(emb1, emb2))
        matrix.append(row)
    return matrix


class ChronologicalNumberTracker:
    """Main class for tracking numbers chronologically across bill lifecycle."""
    
    def __init__(self, data_dir: Path, output_dir: Path, cache_dir: Path):
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.cache_dir = cache_dir
        self.embedding_cache_dir = cache_dir / "embeddings"
        self.checkpoint_dir = cache_dir / "checkpoints"
        
        # Create directories if they don't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_cache_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.similarity_threshold = 0.90
    
    def load_checkpoint(self, bill_name: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint for a bill if it exists."""
        checkpoint_file = self.checkpoint_dir / f"{bill_name}_checkpoint.json"
        if checkpoint_file.exists():
            with open(checkpoint_file, 'r') as f:
                return json.load(f)
        return None
    
    def save_checkpoint(self, bill_name: str, checkpoint_data: Dict[str, Any]):
        """Save checkpoint for a bill."""
        checkpoint_file = self.checkpoint_dir / f"{bill_name}_checkpoint.json"
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
    
    def segment_documents(self, chronological_data: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Segment documents by committee reports.
        First segment is ONLY the introduction bill.
        Subsequent segments end with committee reports.
        """
        segments = []
        
        if not chronological_data:
            return segments
        
        # First segment: ONLY the introduction bill (first document)
        segments.append({
            'segment_id': 0,
            'segment_name': "Introduction",
            'documents': [chronological_data[0]],
            'ends_with_committee_report': False
        })
        
        # Process remaining documents
        current_segment = []
        segment_id = 1
        
        for doc in chronological_data[1:]:  # Skip first document (already in introduction)
            current_segment.append(doc)
            
            # Check if this is a committee report (ends segment)
            if 'CommReports' in doc.get('url', ''):
                segments.append({
                    'segment_id': segment_id,
                    'segment_name': f"Stage {segment_id} (to Committee Report)",
                    'documents': current_segment,
                    'ends_with_committee_report': True
                })
                current_segment = []
                segment_id += 1
        
        # Handle remaining documents (if any)
        if current_segment:
            segments.append({
                'segment_id': segment_id,
                'segment_name': f"Stage {segment_id} (Final)",
                'documents': current_segment,
                'ends_with_committee_report': False
            })
        
        return segments
    
    def _generate_segment_name(self, segment_id: int, documents: List[Dict[str, str]]) -> str:
        """Generate a descriptive name for a segment."""
        if segment_id == 0:
            return "Introduction"
        
        # Check if ends with committee report
        if documents and 'CommReports' in documents[-1].get('url', ''):
            return f"Stage {segment_id} (to Committee Report)"
        else:
            return f"Stage {segment_id} (Final Documents)"
    
    def extract_numbers_for_segment(
        self, 
        bill_dir: Path, 
        segment: Dict[str, Any], 
        all_numbers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract and filter numbers for a specific segment.
        
        Returns list of numbers that belong to documents in this segment.
        """
        # Get document names in this segment
        segment_doc_names = [doc["name"] for doc in segment["documents"]]
        
        # Filter numbers by filename with strict matching
        segment_numbers = []
        for num_entry in all_numbers:
            filename = num_entry.get("filename", "")
            
            # Try to match filename to one of the segment documents
            matched = False
            for doc_name in segment_doc_names:
                # Build possible filename patterns for this document
                possible_patterns = [
                    f"{doc_name}.txt",
                    f"{doc_name}_.HTM.txt",
                    f"{doc_name}_.PDF.txt",
                    f"{doc_name}.PDF.txt",
                    f"{doc_name}_.htm.txt",
                    f"{doc_name}.htm.txt",
                ]
                
                # Check exact matches
                if filename in possible_patterns:
                    segment_numbers.append(num_entry)
                    matched = True
                    break
                
                # For testimony/committee report documents with dates, allow prefix matching
                # e.g., "HB727_HD1_TESTIMONY_JDC" matches "HB727_HD1_TESTIMONY_JDC_03-19-25_.PDF.txt"
                # But ensure we don't match "HB727" to "HB727_HD1"
                if "_TESTIMONY_" in doc_name or "_HSCR" in doc_name or "_SSCR" in doc_name or "_CCR" in doc_name:
                    # These documents can have date suffixes
                    if filename.startswith(doc_name):
                        segment_numbers.append(num_entry)
                        matched = True
                        break
            
            if matched:
                continue
        
        return segment_numbers
    
    def deduplicate_numbers_by_value(
        self,
        numbers: List[Dict[str, Any]],
        bill_name: str,
        segment_id: int
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate numbers with same value within a segment using semantic similarity.
        Groups numbers by value, then merges similar ones.
        """
        if not numbers:
            return []
        
        # Group numbers by value
        by_value = defaultdict(list)
        for num in numbers:
            value = num.get('number')
            by_value[value].append(num)
        
        deduplicated = []
        
        for value, num_list in by_value.items():
            if len(num_list) == 1:
                # Only one occurrence, keep as is
                num_list[0]['source_documents'] = [num_list[0].get('filename', 'unknown')]
                deduplicated.append(num_list[0])
            else:
                # Multiple occurrences with same value - check semantic similarity
                summaries = [n.get('summary', '') for n in num_list]
                
                # Generate embeddings for these summaries
                embeddings = []
                for summary in summaries:
                    if summary:
                        try:
                            result = genai.embed_content(
                                model="models/text-embedding-004",
                                content=summary,
                                task_type="semantic_similarity"
                            )
                            embeddings.append(result['embedding'])
                        except:
                            embeddings.append([0.0] * 768)
                    else:
                        embeddings.append([0.0] * 768)
                
                # Group by similarity (60% threshold)
                # Process in reverse order to keep newest documents as representatives
                merged_groups = []
                used_indices = set()
                
                for i in range(len(num_list) - 1, -1, -1):  # Reverse order - newest first
                    if i in used_indices:
                        continue
                    
                    # Start a new group with newest number as representative
                    group = {
                        'representative': num_list[i],
                        'all_numbers': [num_list[i]],  # Store all merged numbers
                        'source_documents': [num_list[i].get('filename', 'unknown')],
                        'similarity_scores': [],
                        'indices': [i]
                    }
                    
                    # Find similar numbers (looking backwards from current position)
                    for j in range(i - 1, -1, -1):
                        if j in used_indices:
                            continue
                        
                        similarity = cosine_similarity(embeddings[i], embeddings[j])
                        print(f"      Similarity between '{num_list[i].get('summary', '')[:50]}...' and '{num_list[j].get('summary', '')[:50]}...': {similarity:.3f}")
                        
                        if similarity >= 0.60:
                            group['all_numbers'].append(num_list[j])
                            group['source_documents'].append(num_list[j].get('filename', 'unknown'))
                            group['similarity_scores'].append(round(similarity, 3))
                            group['indices'].append(j)
                            used_indices.add(j)
                    
                    used_indices.add(i)
                    merged_groups.insert(0, group)  # Insert at beginning to maintain order
                
                # Add merged groups to result
                for group in merged_groups:
                    merged_num = group['representative'].copy()
                    merged_num['source_documents'] = group['source_documents']
                    merged_num['all_merged_numbers'] = group['all_numbers']  # Store all for expansion
                    merged_num['duplicate_count'] = len(group['source_documents'])
                    merged_num['similarity_scores'] = group['similarity_scores']
                    merged_num['avg_similarity'] = round(sum(group['similarity_scores']) / len(group['similarity_scores']), 3) if group['similarity_scores'] else None
                    deduplicated.append(merged_num)
        
        return deduplicated
    
    def enhance_numbers_with_llm(
        self, 
        bill_dir: Path, 
        numbers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enhance numbers with LLM-generated summaries and properties.
        Adapted from enhance_numbers_with_llm.py
        """
        if not numbers:
            return []
        
        # Group by filename
        grouped = defaultdict(list)
        for item in numbers:
            filename = item.get('filename', 'unknown')
            grouped[filename].append(item)
        
        print(f"   📊 Processing {len(grouped)} unique files with {len(numbers)} total numbers")
        
        enhanced_results = []
        
        # Process each file group
        for idx, (filename, numbers_group) in enumerate(grouped.items(), 1):
            print(f"   [{idx}/{len(grouped)}] Enhancing {filename} ({len(numbers_group)} numbers)...")
            
            # Read document content
            doc_content = self._read_document_content(bill_dir, filename)
            
            # Attach content temporarily
            for item in numbers_group:
                item['_document_content'] = doc_content
            
            # Get LLM analysis
            llm_results = self._analyze_with_llm(filename, numbers_group)
            
            if not llm_results:
                # Keep original data if LLM fails
                for item in numbers_group:
                    item.pop('_document_content', None)
                enhanced_results.extend(numbers_group)
                continue
            
            # Merge LLM properties with original data
            for original, llm_props in zip(numbers_group, llm_results):
                enhanced_item = original.copy()
                enhanced_item.pop('_document_content', None)
                
                # Add LLM properties
                for key, value in llm_props.items():
                    if key != 'number':
                        enhanced_item[key] = value
                
                enhanced_results.append(enhanced_item)
            
            # Small delay to avoid rate limits
            time.sleep(2)
        
        return enhanced_results
    
    def _read_document_content(self, bill_dir: Path, filename: str) -> str:
        """Read document content from documents or fiscal_notes directories."""
        for subdir in ['documents', 'fiscal_notes']:
            doc_path = bill_dir / subdir / filename
            if doc_path.exists():
                try:
                    with open(doc_path, 'r', encoding='utf-8', errors='ignore') as f:
                        return f.read()
                except Exception as e:
                    print(f"      ⚠️  Could not read {filename}: {e}")
                    return ""
        return ""
    
    def _analyze_with_llm(
        self, 
        filename: str, 
        numbers_group: List[Dict[str, Any]], 
        max_retries: int = 3
    ) -> List[Dict[str, Any]]:
        """Use Gemini to analyze numbers and generate properties."""
        
        # Handle large files by chunking
        if len(numbers_group) > 80:
            print(f"      📦 Large file ({len(numbers_group)} numbers), processing in chunks...")
            all_results = []
            chunk_size = 50
            
            for i in range(0, len(numbers_group), chunk_size):
                chunk = numbers_group[i:i+chunk_size]
                chunk_results = self._analyze_with_llm(filename, chunk, max_retries)
                if not chunk_results:
                    return []
                all_results.extend(chunk_results)
                if i + chunk_size < len(numbers_group):
                    time.sleep(5)
            
            return all_results
        
        for attempt in range(max_retries):
            try:
                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                content = numbers_group[0].get('_document_content', '') if numbers_group else ''
                prompt = self._create_llm_prompt(filename, content, numbers_group)
                
                response = model.generate_content(prompt)
                response_text = response.text.strip()
                
                # Remove markdown code blocks if present
                if response_text.startswith('```'):
                    lines = response_text.split('\n')
                    response_text = '\n'.join(lines[1:-1])
                
                llm_results = json.loads(response_text)
                
                # Validate result count
                if len(llm_results) != len(numbers_group):
                    print(f"      ⚠️  LLM returned {len(llm_results)} results but expected {len(numbers_group)}")
                    return []
                
                return llm_results
                
            except Exception as e:
                error_msg = str(e)
                if '429' in error_msg or 'quota' in error_msg.lower():
                    wait_time = 10 * (attempt + 1)
                    print(f"      ⏳ Rate limit hit, waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"      ❌ Error: {error_msg}")
                    return []
        
        return []
    
    def _create_llm_prompt(self, filename: str, content: str, numbers_group: List[Dict[str, Any]]) -> str:
        """Create prompt for LLM analysis."""
        
        numbers_data = []
        for item in numbers_group:
            numbers_data.append({
                "number": item['number'],
                "context": item['text']
            })
        
        prompt = f"""You are analyzing numerical data extracted from a legislative document.

Document: {filename}
Document Content: {content[:5000]}  # Truncate for efficiency

Numbers found in this document:
{json.dumps(numbers_data, indent=2)}

Your task: For EACH number, provide a concise summary and relevant properties.

Required for each number:
- "number": the original number value
- "summary": A concise 1-2 sentence description (REQUIRED)

Optional properties (only if clearly applicable):
- amount_type: (e.g., "fine", "penalty", "appropriation", "cost", "fee", "salary")
- category: (e.g., "insurance", "budget", "enforcement", "infrastructure")
- time_period: (e.g., "annual", "monthly", "fiscal_year_2025")
- fiscal_year: (e.g., "2025", "2026")
- expending_agency: agency abbreviation (e.g., "EDN", "HTH")
- means_of_financing: (e.g., "general_funds", "special_funds")

Return ONLY a JSON array with one object per number, in the SAME ORDER as provided.

Example:
[
  {{
    "number": 5000.0,
    "summary": "Maximum fine for violating fireworks regulations.",
    "amount_type": "fine",
    "category": "enforcement"
  }}
]
"""
        return prompt
    
    def get_or_create_embeddings(
        self, 
        bill_name: str, 
        segment_id: int, 
        summaries: List[str]
    ) -> List[List[float]]:
        """
        Get embeddings from cache or create new ones using Gemini.
        
        Returns: list of embedding vectors
        """
        cache_file = self.embedding_cache_dir / f"{bill_name}_segment_{segment_id}_embeddings.json"
        
        # Check cache
        if cache_file.exists():
            print(f"   📦 Loading cached embeddings for segment {segment_id}")
            with open(cache_file, 'r') as f:
                return json.load(f)
        
        # Generate embeddings
        print(f"   🔄 Generating embeddings for segment {segment_id} ({len(summaries)} summaries)...")
        embeddings = []
        
        # Process in batches to avoid rate limits
        batch_size = 100
        for i in range(0, len(summaries), batch_size):
            batch = summaries[i:i+batch_size]
            
            for summary in batch:
                try:
                    result = genai.embed_content(
                        model="models/text-embedding-004",
                        content=summary,
                        task_type="semantic_similarity"
                    )
                    embeddings.append(result['embedding'])
                    time.sleep(0.1)  # Small delay to avoid rate limits
                except Exception as e:
                    print(f"      ⚠️  Error generating embedding: {e}")
                    # Use zero vector as fallback
                    embeddings.append([0.0] * 768)
            
            if i + batch_size < len(summaries):
                print(f"      Processed {i + batch_size}/{len(summaries)} embeddings...")
                time.sleep(2)
        
        # Cache the embeddings
        with open(cache_file, 'w') as f:
            json.dump(embeddings, f)
        print(f"   💾 Cached embeddings to {cache_file.name}")
        
        return embeddings
    
    def match_numbers_with_history(
        self,
        current_numbers: List[Dict[str, Any]],
        previous_numbers: List[Dict[str, Any]],
        bill_name: str,
        current_segment_id: int
    ) -> List[Dict[str, Any]]:
        """
        Match current numbers with previous numbers using semantic similarity.
        Track history and changes.
        """
        if not previous_numbers:
            # First segment - no history to track
            for num in current_numbers:
                num['first_appeared_in_segment'] = current_segment_id
                num['history'] = []
                num['change_type'] = 'new'
            return current_numbers
        
        # Extract summaries
        current_summaries = [n.get('summary', '') for n in current_numbers]
        previous_summaries = [n.get('summary', '') for n in previous_numbers]
        
        # Get embeddings
        current_embeddings = self.get_or_create_embeddings(
            bill_name, current_segment_id, current_summaries
        )
        previous_embeddings = self.get_or_create_embeddings(
            bill_name, current_segment_id - 1, previous_summaries
        )
        
        # Calculate similarity matrix
        similarity_matrix = cosine_similarity_matrix(current_embeddings, previous_embeddings)
        
        # Verify matrix dimensions
        expected_rows = len(current_numbers)
        expected_cols = len(previous_numbers)
        
        if len(similarity_matrix) != expected_rows:
            print(f"      ⚠️  Warning: Similarity matrix row mismatch. Expected {expected_rows}, got {len(similarity_matrix)}")
            # Pad or truncate as needed
            while len(similarity_matrix) < expected_rows:
                similarity_matrix.append([0.0] * expected_cols)
        
        # Verify each row has correct number of columns
        for i, row in enumerate(similarity_matrix):
            if len(row) != expected_cols:
                print(f"      ⚠️  Warning: Row {i} has {len(row)} columns, expected {expected_cols}")
                # Pad or truncate
                if len(row) < expected_cols:
                    similarity_matrix[i] = row + [0.0] * (expected_cols - len(row))
                else:
                    similarity_matrix[i] = row[:expected_cols]
        
        # Match numbers
        matched_current_indices = set()
        
        for curr_idx, current_num in enumerate(current_numbers):
            # First, try to find exact number match
            exact_number_match_idx = None
            exact_number_match_similarity = None
            
            for prev_idx, prev_num in enumerate(previous_numbers):
                if current_num.get('number') == prev_num.get('number'):
                    exact_number_match_idx = prev_idx
                    # Bounds check before accessing similarity matrix
                    if curr_idx < len(similarity_matrix) and prev_idx < len(similarity_matrix[curr_idx]):
                        exact_number_match_similarity = similarity_matrix[curr_idx][prev_idx]
                    else:
                        exact_number_match_similarity = 0.0
                        print(f"      ⚠️  Matrix bounds error for indices ({curr_idx}, {prev_idx})")
                    break
            
            # Find best semantic match
            similarities = similarity_matrix[curr_idx]
            best_prev_idx = similarities.index(max(similarities))
            best_similarity = similarities[best_prev_idx]
            
            # Decide which match to use
            # If we have an exact number match, prefer it (even with lower similarity)
            # But flag it if similarity is low
            exact_match_low_sim = None
            
            if exact_number_match_idx is not None:
                # We have an exact number match
                if exact_number_match_similarity < 0.60:
                    # Low similarity - flag as warning but still match
                    exact_match_low_sim = {
                        'previous_segment': current_segment_id - 1,
                        'similarity': round(float(exact_number_match_similarity), 3),
                        'previous_summary': previous_numbers[exact_number_match_idx].get('summary', '')[:100]
                    }
                    print(f"      ⚠️  Exact number match with LOW similarity ({exact_number_match_similarity:.3f}): ${current_num.get('number')}")
                
                # Use the exact number match
                best_prev_idx = exact_number_match_idx
                best_similarity = exact_number_match_similarity
            
            if best_similarity >= self.similarity_threshold or exact_number_match_idx is not None:
                # Match found
                matched_current_indices.add(curr_idx)
                previous_num = previous_numbers[best_prev_idx]
                
                # Track history
                current_num['first_appeared_in_segment'] = previous_num.get(
                    'first_appeared_in_segment', current_segment_id - 1
                )
                
                # Build history entry for previous occurrence
                history_entry = {
                    'segment_id': current_segment_id - 1,
                    'number': previous_num.get('number'),
                    'summary': previous_num.get('summary'),
                    'similarity_score': round(float(best_similarity), 3)
                }
                
                # Copy relevant properties from previous
                for key in ['amount_type', 'category', 'fiscal_year', 'expending_agency']:
                    if key in previous_num:
                        history_entry[key] = previous_num[key]
                
                # Add to history
                current_num['history'] = previous_num.get('history', []) + [history_entry]
                
                # Add previous segment's number to merged numbers for expansion view
                if 'all_merged_numbers' not in current_num:
                    current_num['all_merged_numbers'] = [current_num.copy()]
                
                # Add the previous number with segment marker
                prev_num_copy = previous_num.copy()
                prev_num_copy['from_segment'] = current_segment_id - 1
                prev_num_copy['similarity_to_current'] = round(float(best_similarity), 3)
                current_num['all_merged_numbers'].append(prev_num_copy)
                
                # Determine change type
                if current_num.get('number') == previous_num.get('number'):
                    current_num['change_type'] = 'continued'
                else:
                    current_num['change_type'] = 'modified'
                    current_num['previous_number'] = previous_num.get('number')
                
                # Add exact match warning if applicable
                if exact_match_low_sim:
                    current_num['exact_match_low_similarity'] = exact_match_low_sim
            else:
                # No match - new number
                current_num['first_appeared_in_segment'] = current_segment_id
                current_num['history'] = []
                current_num['change_type'] = 'new'
                
                # Add exact match warning if applicable
                if exact_match_low_sim:
                    current_num['exact_match_low_similarity'] = exact_match_low_sim
        
        return current_numbers
    
    def load_numbers_file(self, bill_dir: Path, bill_name: str) -> List[Dict[str, Any]]:
        """Load the numbers JSON file for a bill. Prefer enhanced version if available."""
        # Try enhanced version first (has LLM summaries already)
        enhanced_file = bill_dir / f"{bill_name}_numbers_enhanced.json"
        numbers_file = bill_dir / f"{bill_name}_numbers.json"
        
        if enhanced_file.exists():
            print(f"📊 Using enhanced numbers file: {enhanced_file.name}")
            with open(enhanced_file, 'r') as f:
                return json.load(f)
        elif numbers_file.exists():
            print(f"📊 Using raw numbers file: {numbers_file.name}")
            with open(numbers_file, 'r') as f:
                return json.load(f)
        else:
            print(f"⚠️  Numbers file not found: {numbers_file}")
            return []
    
    def process_bill(self, bill_name: str) -> Dict[str, Any]:
        """
        Process a single bill and track numbers chronologically.
        
        Returns the complete tracking data structure.
        """
        print(f"\n{'='*70}")
        print(f"Processing: {bill_name}")
        print(f"{'='*70}")
        
        bill_dir = self.data_dir / bill_name
        
        # Check for checkpoint
        checkpoint = self.load_checkpoint(bill_name)
        if checkpoint:
            print(f"📋 Found checkpoint at segment {checkpoint.get('last_completed_segment', -1)}")
        
        # Load chronological data
        chronological_file = bill_dir / f"{bill_name}_chronological.json"
        if not chronological_file.exists():
            print(f"❌ Chronological file not found: {chronological_file}")
            return None
        
        with open(chronological_file, 'r') as f:
            chronological_data = json.load(f)
        
        # Load all numbers
        all_numbers = self.load_numbers_file(bill_dir, bill_name)
        
        print(f"📄 Loaded {len(chronological_data)} documents and {len(all_numbers)} number entries")
        
        # Segment documents
        segments = self.segment_documents(chronological_data)
        print(f"📊 Created {len(segments)} segments")
        
        # Process each segment
        result = {
            "bill_name": bill_name,
            "segments": [],
            "summary_statistics": {}
        }
        
        previous_enhanced_numbers = []
        
        for segment in segments:
            segment_id = segment['segment_id']
            
            # Check if already processed (from checkpoint)
            if checkpoint and segment_id <= checkpoint.get('last_completed_segment', -1):
                print(f"\n⏭️  Segment {segment_id} already processed (from checkpoint)")
                # Load from checkpoint
                result['segments'].append(checkpoint['segments'][segment_id])
                previous_enhanced_numbers = checkpoint['segments'][segment_id]['numbers']
                continue
            
            print(f"\n{'─'*70}")
            print(f"Segment {segment_id}: {segment['segment_name']}")
            print(f"Documents: {len(segment['documents'])}")
            print(f"{'─'*70}")
            
            # Extract numbers for this segment
            segment_numbers = self.extract_numbers_for_segment(bill_dir, segment, all_numbers)
            print(f"📊 Found {len(segment_numbers)} numbers in this segment")
            
            if not segment_numbers:
                print(f"⚠️  No numbers found in segment {segment_id}, skipping...")
                continue
            
            # Enhance with LLM
            enhanced_numbers = self.enhance_numbers_with_llm(bill_dir, segment_numbers)
            
            # Deduplicate numbers with same value using semantic similarity
            enhanced_numbers = self.deduplicate_numbers_by_value(enhanced_numbers, bill_name, segment_id)
            
            # Match with previous segment
            enhanced_numbers = self.match_numbers_with_history(
                enhanced_numbers,
                previous_enhanced_numbers,
                bill_name,
                segment_id
            )
            
            # Carry forward numbers from previous segment that weren't mentioned in this segment
            all_segment_numbers = enhanced_numbers.copy()
            
            if previous_enhanced_numbers:
                # Get number values that appear in current segment
                current_number_values = set(n.get('number') for n in enhanced_numbers)
                
                # Add previous numbers that don't appear in current segment
                for prev_num in previous_enhanced_numbers:
                    prev_value = prev_num.get('number')
                    if prev_value not in current_number_values:
                        # Carry forward with "no_change" status
                        carried_num = prev_num.copy()
                        carried_num['change_type'] = 'no_change'
                        carried_num['carried_forward'] = True
                        all_segment_numbers.append(carried_num)
            
            # Store segment results
            segment_result = {
                "segment_id": segment_id,
                "segment_name": segment['segment_name'],
                "documents": [doc['name'] for doc in segment['documents']],
                "ends_with_committee_report": segment['ends_with_committee_report'],
                "number_count": len(all_segment_numbers),
                "new_in_segment": len([n for n in enhanced_numbers if n.get('change_type') == 'new']),
                "continued_in_segment": len([n for n in enhanced_numbers if n.get('change_type') == 'continued']),
                "modified_in_segment": len([n for n in enhanced_numbers if n.get('change_type') == 'modified']),
                "carried_forward": len(all_segment_numbers) - len(enhanced_numbers),
                "numbers": all_segment_numbers
            }
            
            result['segments'].append(segment_result)
            previous_enhanced_numbers = all_segment_numbers
            
            # Save checkpoint
            self.save_checkpoint(bill_name, {
                'last_completed_segment': segment_id,
                'segments': result['segments']
            })
            print(f"💾 Checkpoint saved")
        
        # Calculate summary statistics
        all_tracked_numbers = []
        for seg in result['segments']:
            all_tracked_numbers.extend(seg['numbers'])
        
        unique_numbers = len(set(n.get('first_appeared_in_segment', -1) for n in all_tracked_numbers))
        new_count = sum(1 for n in all_tracked_numbers if n.get('change_type') == 'new')
        continued_count = sum(1 for n in all_tracked_numbers if n.get('change_type') == 'continued')
        modified_count = sum(1 for n in all_tracked_numbers if n.get('change_type') == 'modified')
        no_change_count = sum(1 for n in all_tracked_numbers if n.get('change_type') == 'no_change')
        
        result['summary_statistics'] = {
            "total_segments": len(segments),
            "total_number_entries": len(all_tracked_numbers),
            "new_numbers": new_count,
            "continued_numbers": continued_count,
            "modified_numbers": modified_count,
            "no_change_numbers": no_change_count
        }
        
        # Save final result
        output_file = self.output_dir / f"{bill_name}_chronological_tracking.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"\n{'='*70}")
        print(f"✅ Processing complete!")
        print(f"   Output: {output_file}")
        print(f"   Total segments: {result['summary_statistics']['total_segments']}")
        print(f"   Total entries: {result['summary_statistics']['total_number_entries']}")
        print(f"   New: {new_count} | Continued: {continued_count} | Modified: {modified_count} | No Change: {no_change_count}")
        print(f"{'='*70}")
        
        return result


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Track numbers chronologically across bill lifecycle')
    parser.add_argument('--bill', type=str, help='Specific bill to process (e.g., HB_1483_2025)')
    parser.add_argument('--all', action='store_true', help='Process all bills')
    parser.add_argument('--data-dir', type=str, default='data', help='Data directory path')
    parser.add_argument('--output-dir', type=str, default='number_changes', help='Output directory path')
    parser.add_argument('--cache-dir', type=str, default='.cache', help='Cache directory path')
    
    args = parser.parse_args()
    
    # Setup paths
    script_dir = Path(__file__).parent
    data_dir = script_dir / args.data_dir
    output_dir = script_dir / args.output_dir
    cache_dir = script_dir / args.cache_dir
    
    # Initialize tracker
    tracker = ChronologicalNumberTracker(data_dir, output_dir, cache_dir)
    
    if args.bill:
        # Process single bill
        tracker.process_bill(args.bill)
    elif args.all:
        # Process all bills
        bill_dirs = [d for d in data_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        bill_dirs.sort()
        
        print(f"🔍 Found {len(bill_dirs)} bills to process")
        
        for bill_dir in bill_dirs:
            try:
                tracker.process_bill(bill_dir.name)
            except Exception as e:
                print(f"❌ Error processing {bill_dir.name}: {e}")
                continue
    else:
        print("❌ Please specify --bill <bill_name> or --all")


if __name__ == "__main__":
    main()
