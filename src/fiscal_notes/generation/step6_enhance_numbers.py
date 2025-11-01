"""
Step 6: Enhance Numbers with RAG Agent

This step enhances financial numbers extracted in step 4 using a LangGraph RAG agent.
It creates a new enhanced numbers file without interfering with the existing pipeline.

Input: {bill_dir}/{bill_name}_numbers.json (from step 4)
Output: {bill_dir}/{bill_name}_numbers_enhanced.json (new file)
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any
import time
from datetime import datetime

# Import the RAG agent functionality
from .enhance_numbers_with_rag_agent import (
    enhance_numbers_with_rag,
    DecisionLogger
)


def enhance_numbers_for_bill(bill_dir: str) -> str:
    """
    Enhance numbers for a single bill using RAG agent.
    
    Args:
        bill_dir: Path to the bill directory (e.g., "HB_1483_2025")
    
    Returns:
        Path to the enhanced numbers file
    """
    bill_path = Path(bill_dir)
    bill_name = bill_path.name
    
    print(f"\n{'='*60}")
    print(f"Step 6: Enhancing Numbers for {bill_name}")
    print(f"{'='*60}")
    
    # Input file from step 4
    numbers_file = bill_path / f"{bill_name}_numbers.json"
    
    # Output file (new, doesn't interfere with existing pipeline)
    enhanced_file = bill_path / f"{bill_name}_numbers_enhanced.json"
    
    # Check if input exists
    if not numbers_file.exists():
        print(f"❌ Numbers file not found: {numbers_file}")
        print(f"   Make sure step 4 has been completed first.")
        return None
    
    # Check if already enhanced
    if enhanced_file.exists():
        print(f"⏭️  Enhanced file already exists: {enhanced_file.name}")
        print(f"   Skipping enhancement. Delete the file to re-run.")
        return str(enhanced_file)
    
    # Initialize decision logger
    log_file = bill_path / f"{bill_name}_enhancement_log.txt"
    logger = DecisionLogger(log_file)
    logger.log(f"\n{'='*80}")
    logger.log(f"STARTING NUMBER ENHANCEMENT: {bill_name}")
    logger.log(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.log(f"{'='*80}\n")
    
    # Load numbers from step 4
    with open(numbers_file, 'r') as f:
        numbers = json.load(f)
    
    print(f"📄 Loaded {len(numbers)} number entries from step 4")
    
    # Enhance with RAG agent
    try:
        enhanced_numbers = enhance_numbers_with_rag(numbers, bill_path)
        
        # Verify same length
        if len(enhanced_numbers) != len(numbers):
            print(f"⚠️  Warning: Enhanced file has {len(enhanced_numbers)} entries but original has {len(numbers)}")
        
        # Write enhanced file
        with open(enhanced_file, 'w') as f:
            json.dump(enhanced_numbers, f, indent=2)
        
        print(f"✅ Created enhanced file: {enhanced_file.name}")
        print(f"   Original entries: {len(numbers)}")
        print(f"   Enhanced entries: {len(enhanced_numbers)}")
        print(f"📝 Enhancement log saved to: {log_file.name}")
        
        # Log completion
        logger.log(f"\n{'='*80}")
        logger.log(f"COMPLETED NUMBER ENHANCEMENT: {bill_name}")
        logger.log(f"Original entries: {len(numbers)}")
        logger.log(f"Enhanced entries: {len(enhanced_numbers)}")
        logger.log(f"{'='*80}\n")
        
        return str(enhanced_file)
        
    except Exception as e:
        print(f"❌ Error enhancing numbers: {e}")
        import traceback
        traceback.print_exc()
        
        logger.log(f"\n{'='*80}")
        logger.log(f"ERROR DURING ENHANCEMENT: {str(e)}")
        logger.log(f"{'='*80}\n")
        
        return None


def main():
    """
    Main function for standalone execution.
    Can be called from the API pipeline or run independently.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Step 6: Enhance numbers with RAG agent')
    parser.add_argument('bill_dir', type=str, help='Path to bill directory (e.g., HB_1483_2025)')
    
    args = parser.parse_args()
    
    result = enhance_numbers_for_bill(args.bill_dir)
    
    if result:
        print(f"\n✨ Step 6 completed successfully!")
        print(f"   Enhanced file: {result}")
    else:
        print(f"\n❌ Step 6 failed")
        exit(1)


__all__ = ["enhance_numbers_for_bill"]


if __name__ == "__main__":
    main()
