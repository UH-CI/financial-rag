#!/usr/bin/env python3
"""
Script to regenerate fiscal notes in parallel with job queue management.
Monitors Redis to ensure no more than 7 jobs run concurrently.
"""

import os
import glob
import time
import redis
import requests
from pathlib import Path

# Configuration
BACKEND_URL = "http://localhost:8200"
MAX_CONCURRENT_JOBS = 7  # Keep below API limit of 10 for safety
REDIS_HOST = "localhost"
REDIS_PORT = 6379
POLL_INTERVAL = 5  # seconds

def get_redis_client():
    """Connect to Redis"""
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def get_active_job_count(redis_client):
    """Get count of active fiscal note generation jobs from Redis"""
    try:
        # Get all keys matching the pattern for fiscal note jobs
        # API stores jobs as "job:HB_727_2025" format
        job_keys = redis_client.keys("job:*")
        
        # All keys that exist are active jobs (they get deleted when complete)
        return len(job_keys)
    except Exception as e:
        print(f"❌ Error checking Redis: {e}")
        return 0

def get_existing_bills():
    """Collect names of bills that already have fiscal notes generated"""
    generation_dir = Path("fiscal_notes/generation")
    bills = []
    
    if not generation_dir.exists():
        print(f"❌ Directory not found: {generation_dir}")
        return bills
    
    # Find all bill directories
    for bill_dir in generation_dir.iterdir():
        if bill_dir.is_dir() and not bill_dir.name.startswith('.'):
            fiscal_notes_dir = bill_dir / "fiscal_notes"
            if fiscal_notes_dir.exists():
                # Check if there are any .json files (fiscal notes)
                json_files = list(fiscal_notes_dir.glob("*.json"))
                # Exclude metadata files
                fiscal_note_files = [f for f in json_files if not f.name.endswith('_metadata.json')]
                
                if fiscal_note_files:
                    # Extract bill info from directory name
                    # Format: HB_727_2025 or SB_933_2025
                    parts = bill_dir.name.split('_')
                    if len(parts) >= 3:
                        bill_type = parts[0]  # HB or SB
                        bill_number = parts[1]  # 727
                        year = parts[2]  # 2025
                        
                        bills.append({
                            'bill_type': bill_type,
                            'bill_number': bill_number,
                            'year': year,
                            'directory': bill_dir.name,
                            'fiscal_note_count': len(fiscal_note_files)
                        })
    
    return bills

def trigger_fiscal_note_generation(bill_type, bill_number, year):
    """Trigger fiscal note generation via API"""
    try:
        url = f"{BACKEND_URL}/generate-fiscal-note"
        params = {
            'bill_type': bill_type,
            'bill_number': bill_number,
            'year': year
        }
        
        print(f"🚀 Triggering generation for {bill_type}{bill_number} ({year})...")
        response = requests.post(url, params=params, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Job queued: {result.get('message', 'Success')}")
            return True
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error triggering generation: {e}")
        return False

def main():
    print("="*80)
    print("FISCAL NOTE REGENERATION SCRIPT")
    print("="*80)
    
    # Connect to Redis
    print("\n📡 Connecting to Redis...")
    redis_client = get_redis_client()
    try:
        redis_client.ping()
        print("✅ Redis connected")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("Please start Redis with: docker start redis")
        return
    
    # Get list of bills to regenerate
    print("\n📋 Collecting bills with existing fiscal notes...")
    bills = get_existing_bills()
    
    if not bills:
        print("❌ No bills found with fiscal notes")
        return
    
    print(f"✅ Found {len(bills)} bills to regenerate:")
    for bill in bills[:10]:  # Show first 10
        print(f"   - {bill['bill_type']}{bill['bill_number']} ({bill['year']}) - {bill['fiscal_note_count']} notes")
    if len(bills) > 10:
        print(f"   ... and {len(bills) - 10} more")
    
    # Process bills with queue management
    print(f"\n🔄 Starting regeneration (max {MAX_CONCURRENT_JOBS} concurrent jobs)...")
    print("Press Ctrl+C to stop\n")
    
    processed = 0
    queued = 0
    
    try:
        for bill in bills:
            # Wait until we have capacity
            while True:
                active_jobs = get_active_job_count(redis_client)
                print(f"📊 Active jobs: {active_jobs}/{MAX_CONCURRENT_JOBS} | Processed: {processed}/{len(bills)} | Queued: {queued}")
                
                if active_jobs < MAX_CONCURRENT_JOBS:
                    break
                
                print(f"⏳ Queue full, waiting {POLL_INTERVAL}s...")
                time.sleep(POLL_INTERVAL)
            
            # Trigger generation
            success = trigger_fiscal_note_generation(
                bill['bill_type'],
                bill['bill_number'],
                bill['year']
            )
            
            if success:
                queued += 1
            
            processed += 1
            
            # Small delay between requests
            time.sleep(1)
        
        # Wait for all jobs to complete
        print("\n⏳ All jobs queued. Waiting for completion...")
        while True:
            active_jobs = get_active_job_count(redis_client)
            if active_jobs == 0:
                break
            print(f"📊 Active jobs: {active_jobs} | Waiting {POLL_INTERVAL}s...")
            time.sleep(POLL_INTERVAL)
        
        print("\n" + "="*80)
        print("✅ ALL FISCAL NOTES REGENERATED")
        print("="*80)
        print(f"Total bills processed: {processed}")
        print(f"Total jobs queued: {queued}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        print(f"Processed: {processed}/{len(bills)}")
        print(f"Queued: {queued}")

if __name__ == "__main__":
    main()
