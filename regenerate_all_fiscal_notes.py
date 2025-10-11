#!/usr/bin/env python3

import os
import shutil
import requests
import time
import json
import redis
from typing import List, Tuple

def get_bill_names() -> List[Tuple[str, str, str]]:
    """Extract bill names from the generation folder"""
    generation_dir = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation"
    bills = []
    
    for item in os.listdir(generation_dir):
        item_path = os.path.join(generation_dir, item)
        if os.path.isdir(item_path) and item.startswith(('HB_', 'SB_')):
            # Parse bill name: HB_1483_2025 -> HB, 1483, 2025
            parts = item.split('_')
            if len(parts) == 3:
                bill_type = parts[0]  # HB or SB
                bill_number = parts[1]  # 1483
                year = parts[2]  # 2025
                bills.append((bill_type, bill_number, year))
    
    return sorted(bills)

def delete_fiscal_notes(bills: List[Tuple[str, str, str]]):
    """Delete fiscal_notes folders for all bills"""
    generation_dir = "/Users/rodericktabalba/Documents/GitHub/financial-rag/src/fiscal_notes/generation"
    
    for bill_type, bill_number, year in bills:
        bill_folder = f"{bill_type}_{bill_number}_{year}"
        fiscal_notes_path = os.path.join(generation_dir, bill_folder, "fiscal_notes")
        
        if os.path.exists(fiscal_notes_path):
            print(f"🗑️  Deleting fiscal notes for {bill_folder}")
            shutil.rmtree(fiscal_notes_path)
            # Recreate empty folder
            os.makedirs(fiscal_notes_path)
        else:
            print(f"⚠️  No fiscal notes folder found for {bill_folder}")

def check_redis_jobs() -> int:
    """Check how many jobs are currently running in Redis"""
    try:
        # Connect to Redis
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # Count jobs with pattern "job:*"
        job_keys = list(r.scan_iter(match="job:*"))
        return len(job_keys)
    except Exception as e:
        print(f"❌ Error connecting to Redis: {e}")
        return -1

def wait_for_job_completion(job_id: str, max_wait_time: int = 600) -> bool:
    """Wait for a specific job to complete by polling Redis"""
    print(f"⏳ Waiting for job {job_id} to complete...")
    
    start_time = time.time()
    while time.time() - start_time < max_wait_time:
        try:
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            
            # Check if the specific job key exists
            job_key = f"job:{job_id}"
            if not r.exists(job_key):
                print(f"✅ Job {job_id} completed!")
                return True
            
            # Show progress
            elapsed = int(time.time() - start_time)
            print(f"   Still running... ({elapsed}s elapsed)")
            time.sleep(10)  # Check every 10 seconds
            
        except Exception as e:
            print(f"❌ Error checking job status: {e}")
            time.sleep(5)
    
    print(f"⏰ Job {job_id} timed out after {max_wait_time} seconds")
    return False

def generate_fiscal_note(bill_type: str, bill_number: str, year: str = "2025") -> bool:
    """Call the API endpoint to generate a fiscal note"""
    url = "http://localhost:8200/generate-fiscal-note"
    
    params = {
        "bill_type": bill_type,
        "bill_number": bill_number,
        "year": year
    }
    
    try:
        print(f"🚀 Starting generation for {bill_type} {bill_number} ({year})")
        response = requests.post(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                job_id = data.get("job_id")
                print(f"✅ Job queued successfully: {job_id}")
                return job_id
            else:
                print(f"❌ Job failed to queue: {data.get('message')}")
                return None
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error calling API: {e}")
        return None

def main():
    print("🔄 REGENERATING ALL FISCAL NOTES")
    print("=" * 50)
    
    # Step 1: Get all bill names
    print("📋 Step 1: Getting bill names...")
    bills = get_bill_names()
    print(f"Found {len(bills)} bills:")
    for bill_type, bill_number, year in bills:
        print(f"   - {bill_type} {bill_number} ({year})")
    
    # Step 2: Delete existing fiscal notes
    print(f"\n🗑️  Step 2: Deleting existing fiscal notes...")
    delete_fiscal_notes(bills)
    
    # Step 3: Check Redis connection
    print(f"\n🔍 Step 3: Checking Redis connection...")
    active_jobs = check_redis_jobs()
    if active_jobs == -1:
        print("❌ Cannot connect to Redis. Make sure Redis is running.")
        return
    print(f"✅ Redis connected. Current active jobs: {active_jobs}")
    
    # Step 4: Generate fiscal notes one by one
    print(f"\n🚀 Step 4: Generating fiscal notes...")
    successful = 0
    failed = 0
    
    for i, (bill_type, bill_number, year) in enumerate(bills, 1):
        print(f"\n--- Processing {i}/{len(bills)}: {bill_type} {bill_number} ---")
        
        # Generate the fiscal note
        job_id = generate_fiscal_note(bill_type, bill_number, year)
        
        if job_id:
            # Wait for completion
            if wait_for_job_completion(job_id):
                successful += 1
                print(f"✅ {bill_type} {bill_number} completed successfully")
            else:
                failed += 1
                print(f"❌ {bill_type} {bill_number} failed or timed out")
        else:
            failed += 1
            print(f"❌ {bill_type} {bill_number} failed to start")
        
        # Small delay between jobs
        if i < len(bills):
            print("⏳ Waiting 5 seconds before next job...")
            time.sleep(5)
    
    # Summary
    print(f"\n📊 REGENERATION COMPLETE")
    print(f"=" * 30)
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📋 Total: {len(bills)}")
    
    if successful == len(bills):
        print(f"🎉 All fiscal notes regenerated successfully!")
        print(f"   The financial citation fix should now be applied.")
    else:
        print(f"⚠️  Some fiscal notes failed to regenerate.")

if __name__ == "__main__":
    main()
