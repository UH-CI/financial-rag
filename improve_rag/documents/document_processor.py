"""
Document processing module for the Financial Document RAG System.
Handles document loading, chunking, and metadata extraction.
"""

import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import re
import logging
import json

# Handle both relative and absolute imports
try:
    from ..settings import settings, get_document_config
except ImportError:
    from settings import settings, get_document_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DocumentChunk:
    """Represents a document chunk with metadata."""
    content: str
    metadata: Dict[str, Any]
    chunk_id: str

class DocumentProcessor:
    """Processes documents for RAG system ingestion."""
    
    def __init__(self, doc_type: str = "financial"):
        """Initialize document processor.
        
        Args:
            doc_type: Type of documents to process (financial, legislative, general)
        """
        self.doc_type = doc_type
        self.config = get_document_config(doc_type)
        self.chunk_size = self.config.get("chunk_size", settings.chunk_size)
        self.chunk_overlap = self.config.get("chunk_overlap", settings.chunk_overlap)
        
        logger.info(f"DocumentProcessor initialized for type: {doc_type}")
        logger.info(f"Chunk size: {self.chunk_size}, overlap: {self.chunk_overlap}")
    
    def load_document(self, file_path: Path) -> Optional[str]:
        """Load document content from file.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Document content as string, or None if failed
        """
        try:
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return None
            
            if file_path.suffix.lower() not in settings.supported_file_types:
                logger.warning(f"Unsupported file type: {file_path.suffix}")
                return None
            
            # Handle JSON files
            if file_path.suffix.lower() == '.json':
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)
                
                # Convert JSON to searchable text
                content = self._json_to_text(data, file_path.name)
                logger.info(f"Loaded JSON document: {file_path.name} ({len(content)} characters)")
                return content
            
            # Read text file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            logger.info(f"Loaded document: {file_path.name} ({len(content)} characters)")
            return content
            
        except Exception as e:
            logger.error(f"Failed to load document {file_path}: {str(e)}")
            return None
    
    def extract_metadata(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Extract metadata from document.
        
        Args:
            file_path: Path to the document file
            content: Document content
            
        Returns:
            Dictionary of metadata
        """
        metadata = {
            "source": str(file_path),
            "filename": file_path.name,
            "file_size": len(content),
            "doc_type": self.doc_type,
            "processed_at": str(Path.cwd())
        }
        
        # Extract document-specific metadata based on type
        if self.doc_type == "financial":
            metadata.update(self._extract_financial_metadata(content))
        elif self.doc_type == "legislative":
            metadata.update(self._extract_legislative_metadata(content))
        
        return metadata
    
    def _extract_financial_metadata(self, content: str) -> Dict[str, Any]:
        """Extract financial document specific metadata."""
        metadata = {}
        
        # Look for common financial patterns
        if "house bill" in content.lower() or "hb" in content.lower():
            metadata["document_category"] = "budget_bill"
        
        # Look for fiscal year mentions
        fy_matches = re.findall(r'fiscal year (\d{4})', content.lower())
        if fy_matches:
            metadata["fiscal_years"] = ", ".join(list(set(fy_matches)))
        
        # Look for dollar amounts
        dollar_matches = re.findall(r'\$[\d,]+', content)
        if dollar_matches:
            metadata["contains_financial_data"] = True
            metadata["dollar_amount_count"] = len(dollar_matches)
        
        # Look for department mentions
        dept_patterns = [
            r'department of \w+',
            r'office of \w+',
            r'division of \w+'
        ]
        departments = []
        for pattern in dept_patterns:
            matches = re.findall(pattern, content.lower())
            departments.extend(matches)
        
        if departments:
            metadata["departments"] = ", ".join(list(set(departments)))
        
        return metadata
    
    def _extract_legislative_metadata(self, content: str) -> Dict[str, Any]:
        """Extract legislative document specific metadata."""
        metadata = {}
        
        # Look for bill numbers
        bill_matches = re.findall(r'[HS]B\s*\d+', content.upper())
        if bill_matches:
            metadata["bill_numbers"] = ", ".join(list(set(bill_matches)))
        
        # Look for section references
        section_matches = re.findall(r'section \d+', content.lower())
        if section_matches:
            metadata["section_count"] = len(set(section_matches))
        
        return metadata
    
    def _json_to_text(self, data: Any, filename: str) -> str:
        """Convert JSON data to searchable text format.
        
        Args:
            data: JSON data (dict, list, or other)
            filename: Source filename for context
            
        Returns:
            Formatted text representation of JSON data
        """
        text_parts = [f"Document: {filename}\n"]
        
        if isinstance(data, dict):
            # Handle structured budget documents
            if "budget_items" in data:
                text_parts.append(self._format_budget_items(data))
            elif "source_file" in data and "cleaned_text" in data:
                text_parts.append(self._format_structured_document(data))
            else:
                text_parts.append(self._format_generic_dict(data))
        elif isinstance(data, list):
            # Handle list of budget items or other structured data
            if data and isinstance(data[0], dict) and "department" in data[0]:
                text_parts.append(self._format_budget_items_list(data))
            else:
                text_parts.append(self._format_generic_list(data))
        else:
            text_parts.append(str(data))
        
        return "\n\n".join(text_parts)
    
    def _format_budget_items(self, data: Dict) -> str:
        """Format budget document with budget_items structure."""
        parts = []
        
        # Add document metadata
        if "source_file" in data:
            parts.append(f"Source: {data['source_file']}")
        
        # Add summary information
        if "summary" in data:
            summary = data["summary"]
            parts.append(f"Summary: {summary.get('total_items', 0)} budget items, "
                        f"Total amount: ${summary.get('total_amount', 0):,}")
            
            if "departments" in summary and summary["departments"]:
                parts.append(f"Departments: {', '.join(summary['departments'])}")
        
        # Add budget items
        if "budget_items" in data and data["budget_items"]:
            parts.append("Budget Items:")
            for item in data["budget_items"]:
                item_text = self._format_single_budget_item(item)
                parts.append(item_text)
        
        # Add cleaned text if available
        if "cleaned_text" in data and data["cleaned_text"]:
            parts.append("Full Text Content:")
            parts.append(data["cleaned_text"])
        
        return "\n\n".join(parts)
    
    def _format_budget_items_list(self, items: List[Dict]) -> str:
        """Format a list of budget items."""
        parts = [f"Budget Items ({len(items)} total):"]
        
        for item in items:
            item_text = self._format_single_budget_item(item)
            parts.append(item_text)
        
        return "\n\n".join(parts)
    
    def _format_single_budget_item(self, item: Dict) -> str:
        """Format a single budget item."""
        parts = []
        
        # Core information
        if "department" in item:
            parts.append(f"Department: {item['department']}")
        if "program" in item:
            parts.append(f"Program: {item['program']}")
        if "description" in item:
            parts.append(f"Description: {item['description']}")
        
        # Financial information
        if "amount_formatted" in item:
            parts.append(f"Amount: {item['amount_formatted']}")
        elif "amount" in item:
            parts.append(f"Amount: ${item['amount']:,}")
        
        if "fund_type" in item:
            parts.append(f"Fund Type: {item['fund_type']}")
        if "appropriation_type" in item:
            parts.append(f"Type: {item['appropriation_type']}")
        if "fiscal_year" in item:
            parts.append(f"Fiscal Year: {item['fiscal_year']}")
        
        # Additional details
        if "positions" in item and item["positions"]:
            parts.append(f"Positions: {item['positions']}")
        if "notes" in item:
            parts.append(f"Notes: {item['notes']}")
        
        return " | ".join(parts)
    
    def _format_structured_document(self, data: Dict) -> str:
        """Format a structured document with cleaned text."""
        parts = []
        
        if "source_file" in data:
            parts.append(f"Source: {data['source_file']}")
        
        if "summary" in data:
            summary = data["summary"]
            parts.append(f"Summary: {summary.get('total_items', 0)} items processed")
        
        if "cleaned_text" in data:
            parts.append("Content:")
            parts.append(data["cleaned_text"])
        
        return "\n\n".join(parts)
    
    def _format_generic_dict(self, data: Dict) -> str:
        """Format a generic dictionary."""
        parts = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                parts.append(f"{key}: {str(value)[:200]}...")
            else:
                parts.append(f"{key}: {value}")
        return "\n".join(parts)
    
    def _format_generic_list(self, data: List) -> str:
        """Format a generic list."""
        parts = [f"List with {len(data)} items:"]
        for i, item in enumerate(data[:10]):  # Show first 10 items
            parts.append(f"{i+1}. {str(item)[:100]}...")
        if len(data) > 10:
            parts.append(f"... and {len(data) - 10} more items")
        return "\n".join(parts)
    
    def chunk_document(self, content: str, metadata: Dict[str, Any]) -> List[DocumentChunk]:
        """Split document into chunks with overlap.
        
        Args:
            content: Document content
            metadata: Base metadata for the document
            
        Returns:
            List of DocumentChunk objects
        """
        chunks = []
        
        # Simple sentence-aware chunking
        sentences = self._split_into_sentences(content)
        
        current_chunk = ""
        current_sentences = []
        chunk_num = 0
        
        for sentence in sentences:
            # Check if adding this sentence would exceed chunk size
            if len(current_chunk) + len(sentence) > self.chunk_size and current_chunk:
                # Create chunk
                chunk = self._create_chunk(
                    current_chunk.strip(),
                    metadata,
                    chunk_num,
                    current_sentences
                )
                chunks.append(chunk)
                
                # Start new chunk with overlap
                overlap_sentences = current_sentences[-self._calculate_overlap_sentences(current_sentences):]
                current_chunk = " ".join(overlap_sentences)
                current_sentences = overlap_sentences.copy()
                chunk_num += 1
            
            current_chunk += " " + sentence
            current_sentences.append(sentence)
        
        # Add final chunk if there's remaining content
        if current_chunk.strip():
            chunk = self._create_chunk(
                current_chunk.strip(),
                metadata,
                chunk_num,
                current_sentences
            )
            chunks.append(chunk)
        
        logger.info(f"Created {len(chunks)} chunks from document")
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting - can be improved
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _calculate_overlap_sentences(self, sentences: List[str]) -> int:
        """Calculate number of sentences to overlap."""
        # Calculate overlap based on character count
        overlap_chars = 0
        overlap_count = 0
        
        for sentence in reversed(sentences):
            if overlap_chars + len(sentence) <= self.chunk_overlap:
                overlap_chars += len(sentence)
                overlap_count += 1
            else:
                break
        
        return max(1, overlap_count)  # At least 1 sentence overlap
    
    def _create_chunk(self, content: str, base_metadata: Dict[str, Any], 
                     chunk_num: int, sentences: List[str]) -> DocumentChunk:
        """Create a DocumentChunk object."""
        # Create unique chunk ID
        chunk_id = self._generate_chunk_id(base_metadata["filename"], chunk_num)
        
        # Create chunk metadata
        chunk_metadata = base_metadata.copy()
        chunk_metadata.update({
            "chunk_number": chunk_num,
            "chunk_size": len(content),
            "sentence_count": len(sentences),
            "chunk_id": chunk_id
        })
        
        return DocumentChunk(
            content=content,
            metadata=chunk_metadata,
            chunk_id=chunk_id
        )
    
    def _generate_chunk_id(self, filename: str, chunk_num: int) -> str:
        """Generate unique chunk ID."""
        # Create hash from filename and chunk number
        content = f"{filename}_{chunk_num}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def process_document(self, file_path: Path) -> List[DocumentChunk]:
        """Process a single document into chunks.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            List of DocumentChunk objects
        """
        # Load document
        content = self.load_document(file_path)
        if not content:
            return []

        # Extract metadata
        metadata = self.extract_metadata(file_path, content)
        
        # Special handling for JSON files with budget_items
        if file_path.suffix.lower() == '.json':
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)
                
                # Check if this is a budget items file (list of budget items)
                if isinstance(data, list) and data and isinstance(data[0], dict) and "department" in data[0]:
                    return self._create_budget_item_chunks(data, metadata)
                
                # Check if this has a budget_items property
                elif isinstance(data, dict) and "budget_items" in data and data["budget_items"]:
                    return self._create_budget_item_chunks(data["budget_items"], metadata)
                    
            except Exception as e:
                logger.error(f"Error processing JSON structure for {file_path}: {str(e)}")
                # Fall back to regular text chunking
        
        # Regular text-based chunking for non-budget-item files
        chunks = self.chunk_document(content, metadata)
        return chunks
    
    def _create_budget_item_chunks(self, budget_items: List[Dict], base_metadata: Dict[str, Any]) -> List[DocumentChunk]:
        """Create individual chunks for each budget item.
        
        Args:
            budget_items: List of budget item dictionaries
            base_metadata: Base metadata for the document
            
        Returns:
            List of DocumentChunk objects, one per budget item
        """
        chunks = []
        
        for i, item in enumerate(budget_items):
            # Create content for this budget item
            content = self._format_single_budget_item(item)
            
            # Create chunk metadata - ensure no None values
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update({
                "chunk_number": i,
                "chunk_size": len(content),
                "chunk_type": "budget_item",
                "item_id": item.get("item_id", f"item_{i}") or f"item_{i}",
                "budget_department": item.get("department", "Unknown") or "Unknown",
                "budget_program": item.get("program", "Unknown") or "Unknown", 
                "budget_amount": item.get("amount", 0) or 0,
                "budget_fiscal_year": item.get("fiscal_year", "Unknown") or "Unknown",
                "budget_fund_type": item.get("fund_type", "Unknown") or "Unknown",
                "budget_appropriation_type": item.get("appropriation_type", "Unknown") or "Unknown"
            })
            
            # Clean metadata to ensure no None values
            chunk_metadata = {k: v for k, v in chunk_metadata.items() if v is not None}
            
            # Generate chunk ID
            chunk_id = self._generate_chunk_id(base_metadata["filename"], i)
            chunk_metadata["chunk_id"] = chunk_id
            
            # Create chunk
            chunk = DocumentChunk(
                content=content,
                metadata=chunk_metadata,
                chunk_id=chunk_id
            )
            chunks.append(chunk)
        
        logger.info(f"Created {len(chunks)} budget item chunks from {base_metadata['filename']}")
        return chunks
    
    def process_directory(self, directory_path: Path) -> List[DocumentChunk]:
        """Process all documents in a directory.
        
        Args:
            directory_path: Path to directory containing documents
            
        Returns:
            List of all DocumentChunk objects
        """
        all_chunks = []
        
        if not directory_path.exists():
            logger.error(f"Directory not found: {directory_path}")
            return all_chunks
        
        # Find all supported files
        supported_files = []
        for ext in settings.supported_file_types:
            supported_files.extend(directory_path.glob(f"*{ext}"))
        
        logger.info(f"Found {len(supported_files)} documents to process")
        
        # Process each file
        for file_path in supported_files:
            logger.info(f"Processing: {file_path.name}")
            chunks = self.process_document(file_path)
            all_chunks.extend(chunks)
        
        logger.info(f"Total chunks created: {len(all_chunks)}")
        return all_chunks

if __name__ == "__main__":
    # Test the document processor
    processor = DocumentProcessor("financial")
    
    # Test with output directory
    output_dir = Path("output")
    if output_dir.exists():
        chunks = processor.process_directory(output_dir)
        print(f"Processed {len(chunks)} chunks")
        
        if chunks:
            # Show first chunk as example
            first_chunk = chunks[0]
            print(f"\nExample chunk:")
            print(f"ID: {first_chunk.chunk_id}")
            print(f"Content: {first_chunk.content[:200]}...")
            print(f"Metadata: {first_chunk.metadata}")
    else:
        print("Output directory not found. Please run PDF extraction first.") 