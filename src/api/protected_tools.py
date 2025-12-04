from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from database.connection import get_db
from database.models import User
from auth.middleware import require_permission, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["protected-tools"])

@router.post("/fiscal-note-generation")
async def fiscal_note_generation_endpoint(
    request_data: Dict[Any, Any],
    current_user: User = Depends(require_permission("fiscal-note-generation")),
    db: Session = Depends(get_db)
):
    """
    Protected endpoint for fiscal note generation
    Requires 'fiscal-note-generation' permission
    """
    try:
        # TODO: Integrate with existing fiscal note generation logic
        # This is a placeholder that shows how to protect the endpoint
        
        logger.info(f"User {current_user.email} accessed fiscal note generation")
        
        return {
            "message": "Fiscal note generation endpoint accessed successfully",
            "user": current_user.email,
            "request_data": request_data
        }
        
    except Exception as e:
        logger.error(f"Error in fiscal note generation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/similar-bill-search")
async def similar_bill_search_endpoint(
    request_data: Dict[Any, Any],
    current_user: User = Depends(require_permission("similar-bill-search")),
    db: Session = Depends(get_db)
):
    """
    Protected endpoint for similar bill search
    Requires 'similar-bill-search' permission
    """
    try:
        # TODO: Integrate with existing similar bill search logic
        # This is a placeholder that shows how to protect the endpoint
        
        logger.info(f"User {current_user.email} accessed similar bill search")
        
        return {
            "message": "Similar bill search endpoint accessed successfully",
            "user": current_user.email,
            "request_data": request_data
        }
        
    except Exception as e:
        logger.error(f"Error in similar bill search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/hrs-search")
async def hrs_search_endpoint(
    request_data: Dict[Any, Any],
    current_user: User = Depends(require_permission("hrs-search")),
    db: Session = Depends(get_db)
):
    """
    Protected endpoint for HRS search
    Requires 'hrs-search' permission
    """
    try:
        # TODO: Integrate with existing HRS search logic
        # This is a placeholder that shows how to protect the endpoint
        
        logger.info(f"User {current_user.email} accessed HRS search")
        
        return {
            "message": "HRS search endpoint accessed successfully",
            "user": current_user.email,
            "request_data": request_data
        }
        
    except Exception as e:
        logger.error(f"Error in HRS search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/health")
async def tools_health_check(
    current_user: User = Depends(get_current_user)
):
    """Health check endpoint for authenticated users"""
    return {
        "status": "healthy",
        "user": current_user.email,
        "permissions": "checked"
    }
