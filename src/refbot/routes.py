import os
import shutil
import time
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel
from redis import Redis
from rq import Queue
from rq.job import Job
from rq.registry import StartedJobRegistry

# Auth imports
from auth.middleware import require_permission
from database.models import User

# Import task and constants
from .tasks import process_refbot_upload_task, DATA_DIR, RESULTS_DIR, CONTEXT_DIR

router = APIRouter(
    prefix="/refbot",
    tags=["RefBot"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_permission("refbot-access"))]
)

# Redis Connection
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
try:
    redis_conn = Redis.from_url(REDIS_URL)
    q = Queue(connection=redis_conn, default_timeout=3600) # 1 hour timeout
except Exception as e:
    logging.warning(f"Failed to connect to Redis: {e}")
    q = None

@router.post("/upload")
async def upload_refbot_data(
    name: str = Form(..., description="Name for the dataset"),
    file: UploadFile = File(..., description="Zip file containing PDF documents")
):
    """
    Upload a zip file and enqueue a processing job.
    """
    if not q:
        raise HTTPException(status_code=503, detail="Job queue not available (Redis down?)")

    # 1. Basic validation
    if not file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="The uploaded file must be a .zip file.")

    try:
        # Ensure directories exist
        DATA_DIR.mkdir(exist_ok=True)
        
        # 2. Prepare target directory
        target_dir = DATA_DIR / name
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        # 3. Save zip file
        zip_file_path = target_dir / file.filename
        with open(zip_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 4. Enqueue Job
        # Pass strings for paths to avoid pickling issues with Path objects across environments sometimes
        job = q.enqueue(
            process_refbot_upload_task,
            args=(name, str(zip_file_path), str(target_dir)),
            job_id=f"refbot_{name}_{int(time.time())}",
            meta={"dataset_name": name}
        )

        return {
            "status": "queued",
            "job_id": job.get_id(),
            "message": f"Job enqueued for dataset '{name}'"
        }

    except Exception as e:
        print(f"❌ Error during upload/enqueue: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue job: {str(e)}")

@router.get("/results")
async def get_refbot_results():
    """
    Retrieve completed results and current job statuses.
    """
    # 1. Completed Results
    completed_list = []
    if RESULTS_DIR.exists():
        for results_file in RESULTS_DIR.glob("*.json"):
            try:
                with open(results_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                item_count = len(data) if isinstance(data, list) else 1
                
                completed_list.append({
                    "filename": results_file.name,
                    "name": results_file.stem,
                    "item_count": item_count,
                    "data": data,
                    "created_at": results_file.stat().st_mtime
                })
            except Exception as e:
                logging.error(f"Error reading result file {results_file}: {e}")
                completed_list.append({
                    "filename": results_file.name,
                    "name": results_file.stem,
                    "error": str(e),
                    "item_count": 0,
                    "created_at": results_file.stat().st_mtime if results_file.exists() else 0
                })
        
        # Sort by creation time descending
        completed_list.sort(key=lambda x: x.get("created_at", 0), reverse=True)

    # 2. Active/Queued Jobs
    jobs_list = []
    if q:
        # Get started jobs
        registry = StartedJobRegistry(queue=q)
        started_job_ids = registry.get_job_ids()
        
        # Get queued jobs
        queued_job_ids = q.job_ids

        all_job_ids = set(started_job_ids + queued_job_ids)

        for job_id in all_job_ids:
            try:
                job = Job.fetch(job_id, connection=redis_conn)
                if job and job.id.startswith("refbot_"):
                    status = job.get_status()
                    name = job.meta.get("dataset_name", "Unknown")
                    jobs_list.append({
                        "job_id": job.id,
                        "name": name,
                        "status": status,
                        "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None
                    })
            except Exception:
                # Job might have expired or been removed
                continue

    return {
        "completed": completed_list,
        "jobs": jobs_list
    }

class RenameRequest(BaseModel):
    new_name: str

@router.delete("/results/{filename}")
async def delete_refbot_result(filename: str):
    """
    Delete a specific refbot result file and its associated data directory.
    """
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = RESULTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        file_path.unlink()
        data_dir_name = file_path.stem
        data_dir = DATA_DIR / data_dir_name
        if data_dir.exists() and data_dir.is_dir():
            shutil.rmtree(data_dir)
            logging.info(f"Deleted associated data directory: {data_dir}")
            
        return {"status": "success", "message": f"Deleted {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")

@router.put("/results/{filename}")
async def rename_refbot_result(filename: str, request: RenameRequest):
    """
    Rename a refbot result file and its associated data directory.
    """
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = RESULTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    new_name_raw = request.new_name.strip()
    if not new_name_raw:
        raise HTTPException(status_code=400, detail="New name cannot be empty")
        
    if not new_name_raw.lower().endswith('.json'):
        new_filename = f"{new_name_raw}.json"
    else:
        new_filename = new_name_raw

    if ".." in new_filename or "/" in new_filename or "\\" in new_filename:
         raise HTTPException(status_code=400, detail="Invalid new filename")

    new_path = RESULTS_DIR / new_filename
    if new_path.exists():
        raise HTTPException(status_code=409, detail="File with new name already exists")
        
    try:
        file_path.rename(new_path)
        old_stem = file_path.stem
        new_stem = new_path.stem
        old_data_dir = DATA_DIR / old_stem
        new_data_dir = DATA_DIR / new_stem
        
        if old_data_dir.exists() and old_data_dir.is_dir():
            if new_data_dir.exists():
                logging.warning(f"Cannot rename data dir {old_stem} to {new_stem} because target exists.")
            else:
                old_data_dir.rename(new_data_dir)
                logging.info(f"Renamed data directory from {old_stem} to {new_stem}")
            
        return {"status": "success", "message": f"Renamed to {new_filename}", "new_filename": new_filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rename: {str(e)}")



class ConstraintItem(BaseModel):
    text: str

@router.get("/context/constraints")
async def get_constraints():
    """Get the list of committee assignment constraints."""
    constraints_file = CONTEXT_DIR / "constraints.json"
    if not constraints_file.exists():
        return []
    try:
        with open(constraints_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load constraints: {e}")

@router.post("/context/constraints")
async def add_constraint(item: ConstraintItem):
    """Add a new constraint to the list."""
    constraints_file = CONTEXT_DIR / "constraints.json"
    data = []
    if constraints_file.exists():
        try:
            with open(constraints_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    data = json.loads(content)
        except Exception:
            data = []
    
    data.append({"text": item.text})
    
    # Ensure directory exists
    constraints_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(constraints_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    
    return {"status": "success", "constraints": data}

@router.put("/context/constraints/{index}")
async def update_constraint(index: int, item: ConstraintItem):
    """Update a specific constraint by index."""
    constraints_file = CONTEXT_DIR / "constraints.json"
    if not constraints_file.exists():
        raise HTTPException(status_code=404, detail="Constraints file not found")
        
    try:
        with open(constraints_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse constraints file")
        
    if index < 0 or index >= len(data):
        raise HTTPException(status_code=404, detail="Constraint index out of range")
        
    data[index]["text"] = item.text
    
    with open(constraints_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
    return {"status": "success", "constraints": data}

@router.delete("/context/constraints/{index}")
async def delete_constraint(index: int):
    """Delete a specific constraint by index."""
    constraints_file = CONTEXT_DIR / "constraints.json"
    if not constraints_file.exists():
        raise HTTPException(status_code=404, detail="Constraints file not found")
        
    try:
        with open(constraints_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse constraints file")
        
    if index < 0 or index >= len(data):
        raise HTTPException(status_code=404, detail="Constraint index out of range")
        
    deleted = data.pop(index)
    
    with open(constraints_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
    return {"status": "success", "deleted": deleted, "constraints": data}
