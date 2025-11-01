"""
Step 7: Track Chronological Number Changes

This step tracks how financial numbers change across the bill lifecycle chronologically.
It creates organized output files suitable for frontend consumption.

Input: 
  - {bill_dir}/{bill_name}_chronological.json (from step 2)
  - {bill_dir}/{bill_name}_numbers_enhanced.json (from step 6, or falls back to step 4)
  
Output: 
  - {bill_dir}/{bill_name}_chronological_tracking.json (detailed tracking data)
  - {bill_dir}/{bill_name}_number_changes_summary.json (frontend-friendly summary)
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import the chronological tracker
from .track_chronological_numbers import ChronologicalNumberTracker


def track_chronological_changes(bill_dir: str) -> Dict[str, str]:
    """
    Track chronological number changes for a single bill.
    
    Args:
        bill_dir: Path to the bill directory (e.g., "HB_1483_2025")
    
    Returns:
        Dictionary with paths to output files
    """
    bill_path = Path(bill_dir)
    bill_name = bill_path.name
    
    print(f"\n{'='*60}")
    print(f"Step 7: Tracking Chronological Changes for {bill_name}")
    print(f"{'='*60}")
    
    # Check required input files
    chronological_file = bill_path / f"{bill_name}_chronological.json"
    enhanced_numbers_file = bill_path / f"{bill_name}_numbers_enhanced.json"
    regular_numbers_file = bill_path / f"{bill_name}_numbers.json"
    
    if not chronological_file.exists():
        print(f"❌ Chronological file not found: {chronological_file}")
        print(f"   Make sure step 2 has been completed first.")
        return None
    
    # Prefer enhanced numbers, fall back to regular numbers
    if enhanced_numbers_file.exists():
        print(f"📊 Using enhanced numbers from step 6")
        numbers_source = "enhanced"
    elif regular_numbers_file.exists():
        print(f"📊 Using regular numbers from step 4 (step 6 not run)")
        numbers_source = "regular"
    else:
        print(f"❌ No numbers file found")
        print(f"   Make sure step 4 (and optionally step 6) has been completed.")
        return None
    
    # Output files
    tracking_file = bill_path / f"{bill_name}_chronological_tracking.json"
    summary_file = bill_path / f"{bill_name}_number_changes_summary.json"
    
    # Check if already processed
    if tracking_file.exists() and summary_file.exists():
        print(f"⏭️  Tracking files already exist")
        print(f"   - {tracking_file.name}")
        print(f"   - {summary_file.name}")
        print(f"   Delete these files to re-run step 7.")
        return {
            "tracking_file": str(tracking_file),
            "summary_file": str(summary_file),
            "numbers_source": numbers_source
        }
    
    # Initialize tracker with temporary directories
    temp_output_dir = bill_path / ".temp_tracking_output"
    temp_cache_dir = bill_path / ".temp_tracking_cache"
    temp_output_dir.mkdir(exist_ok=True)
    temp_cache_dir.mkdir(exist_ok=True)
    
    try:
        # Create tracker instance
        tracker = ChronologicalNumberTracker(
            data_dir=bill_path.parent,  # Parent directory containing bill directories
            output_dir=temp_output_dir,
            cache_dir=temp_cache_dir
        )
        
        # Process the bill
        print(f"🔄 Processing chronological tracking...")
        result = tracker.process_bill(bill_name)
        
        if not result:
            print(f"❌ Tracking failed")
            return None
        
        # Move the output file to the bill directory
        temp_tracking_file = temp_output_dir / f"{bill_name}_chronological_tracking.json"
        if temp_tracking_file.exists():
            temp_tracking_file.rename(tracking_file)
            print(f"✅ Created tracking file: {tracking_file.name}")
        
        # Create frontend-friendly summary
        summary = create_frontend_summary(result, bill_name, numbers_source)
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"✅ Created summary file: {summary_file.name}")
        
        # Print statistics
        stats = result.get('summary_statistics', {})
        print(f"\n📊 Tracking Statistics:")
        print(f"   Total segments: {stats.get('total_segments', 0)}")
        print(f"   Total entries: {stats.get('total_number_entries', 0)}")
        print(f"   New numbers: {stats.get('new_numbers', 0)}")
        print(f"   Continued: {stats.get('continued_numbers', 0)}")
        print(f"   Modified: {stats.get('modified_numbers', 0)}")
        print(f"   No change: {stats.get('no_change_numbers', 0)}")
        
        return {
            "tracking_file": str(tracking_file),
            "summary_file": str(summary_file),
            "numbers_source": numbers_source,
            "statistics": stats
        }
        
    except Exception as e:
        print(f"❌ Error tracking chronological changes: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        # Cleanup temporary directories
        import shutil
        if temp_output_dir.exists():
            shutil.rmtree(temp_output_dir, ignore_errors=True)
        if temp_cache_dir.exists():
            shutil.rmtree(temp_cache_dir, ignore_errors=True)


def create_frontend_summary(tracking_result: Dict[str, Any], bill_name: str, numbers_source: str) -> Dict[str, Any]:
    """
    Create a frontend-friendly summary from the tracking result.
    
    This organizes the data in a way that's easy for the frontend to consume.
    """
    segments = tracking_result.get('segments', [])
    stats = tracking_result.get('summary_statistics', {})
    
    # Organize by segment for easy frontend rendering
    segment_summaries = []
    for segment in segments:
        segment_summary = {
            "segment_id": segment['segment_id'],
            "segment_name": segment['segment_name'],
            "documents": segment['documents'],
            "ends_with_committee_report": segment['ends_with_committee_report'],
            "counts": {
                "total": segment['number_count'],
                "new": segment['new_in_segment'],
                "continued": segment['continued_in_segment'],
                "modified": segment['modified_in_segment'],
                "carried_forward": segment['carried_forward']
            },
            "numbers": []
        }
        
        # Add simplified number entries for frontend
        for number in segment['numbers']:
            number_entry = {
                "number": number.get('number'),
                "summary": number.get('summary', ''),
                "change_type": number.get('change_type', 'unknown'),
                "first_appeared_in_segment": number.get('first_appeared_in_segment'),
                "source_documents": number.get('source_documents', []),
                "history_length": len(number.get('history', [])),
                "carried_forward": number.get('carried_forward', False)
            }
            
            # Add previous number if modified
            if number.get('previous_number'):
                number_entry['previous_number'] = number['previous_number']
            
            # Add key properties if available
            for key in ['amount_type', 'category', 'fiscal_year', 'expending_agency']:
                if key in number:
                    number_entry[key] = number[key]
            
            segment_summary['numbers'].append(number_entry)
        
        segment_summaries.append(segment_summary)
    
    # Create timeline of changes
    timeline = []
    for segment in segments:
        timeline_entry = {
            "segment_id": segment['segment_id'],
            "segment_name": segment['segment_name'],
            "new_numbers": segment['new_in_segment'],
            "modified_numbers": segment['modified_in_segment'],
            "total_numbers": segment['number_count']
        }
        timeline.append(timeline_entry)
    
    # Summary for frontend
    summary = {
        "bill_name": bill_name,
        "generated_at": datetime.now().isoformat(),
        "numbers_source": numbers_source,
        "statistics": stats,
        "segments": segment_summaries,
        "timeline": timeline,
        "metadata": {
            "total_segments": len(segments),
            "has_committee_reports": any(s['ends_with_committee_report'] for s in segments)
        }
    }
    
    return summary


def main():
    """
    Main function for standalone execution.
    Can be called from the API pipeline or run independently.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Step 7: Track chronological number changes')
    parser.add_argument('bill_dir', type=str, help='Path to bill directory (e.g., HB_1483_2025)')
    
    args = parser.parse_args()
    
    result = track_chronological_changes(args.bill_dir)
    
    if result:
        print(f"\n✨ Step 7 completed successfully!")
        print(f"   Tracking file: {result['tracking_file']}")
        print(f"   Summary file: {result['summary_file']}")
        print(f"   Numbers source: {result['numbers_source']}")
    else:
        print(f"\n❌ Step 7 failed")
        exit(1)


__all__ = ["track_chronological_changes", "create_frontend_summary"]


if __name__ == "__main__":
    main()
